"""Tool execution engine with async support."""

import asyncio
import logging
import sys
import traceback
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set
from uuid import uuid4

from .models import ErrorCategory, RunRequest, RunResponse, RunStatus
from .registry import ToolRegistry

logger = logging.getLogger(__name__)


class RunContext:
    """Context for tracking tool execution state."""

    def __init__(
        self,
        run_id: str,
        tool_id: str,
        params: Dict[str, Any],
        repo_root: Optional[str] = None,
        deps_dir: Optional[str] = None,
        install_missing_deps: bool = False,
    ):
        """Initialize run context.

        Args:
            run_id: Unique run identifier
            tool_id: Tool identifier
            params: Tool parameters
            repo_root: Optional openpilot parent directory path
            deps_dir: Optional dependencies directory path
            install_missing_deps: Whether to install missing dependencies
        """
        self.run_id = run_id
        self.tool_id = tool_id
        self.params = params
        self.repo_root = repo_root
        self.deps_dir = deps_dir
        self.install_missing_deps = install_missing_deps
        self.status = RunStatus.QUEUED
        self.created_at = datetime.now(timezone.utc)
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.progress: Optional[int] = None
        self.error: Optional[str] = None
        self.artifacts: List[str] = []

        # Enhanced error handling fields
        self.error_category: Optional[ErrorCategory] = None
        self.error_details: Dict[str, Any] = {}
        self.recovery_attempted: bool = False
        self.timeout_seconds: int = 300  # 5 minute default
        self.cleanup_handlers: List[Callable] = []

    def to_response(self) -> RunResponse:
        """Convert to RunResponse model.

        Returns:
            RunResponse model
        """
        return RunResponse(
            run_id=self.run_id,
            status=self.status,
            tool_id=self.tool_id,
            created_at=self.created_at,
            started_at=self.started_at,
            completed_at=self.completed_at,
            params=self.params,
            progress=self.progress,
            artifacts=self.artifacts,
            error=self.error,
        )


class ResourceManager:
    """Manages resources and ensures proper cleanup."""

    def __init__(self):
        self.active_processes: Set[asyncio.subprocess.Process] = set()
        self.temp_directories: Set[Path] = set()
        self.open_files: Set = set()

    async def cleanup_run_resources(self, run_context: "RunContext") -> None:
        """Clean up all resources associated with a run.

        Args:
            run_context: Run context to clean up resources for
        """
        # Execute registered cleanup handlers
        for cleanup_handler in run_context.cleanup_handlers:
            try:
                if asyncio.iscoroutinefunction(cleanup_handler):
                    await cleanup_handler(run_context)
                else:
                    cleanup_handler(run_context)
            except Exception as e:
                logger.warning(f"Cleanup handler failed for run {run_context.run_id}: {e}")

        # Force cleanup critical resources
        await self._cleanup_processes(run_context.run_id)
        await self._cleanup_temp_files(run_context.run_id)
        self._cleanup_memory_references(run_context.run_id)

    async def _cleanup_processes(self, run_id: str) -> None:
        """Terminate any running processes for this run.

        Args:
            run_id: Run identifier
        """
        for proc in list(self.active_processes):
            if hasattr(proc, "run_id") and getattr(proc, "run_id") == run_id:
                try:
                    if proc.returncode is None:  # Process still running
                        proc.terminate()
                        await asyncio.wait_for(proc.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    try:
                        proc.kill()  # Force kill if graceful termination fails
                        await proc.wait()
                    except Exception as e:
                        logger.warning(f"Force kill failed for run {run_id}: {e}")
                except Exception as e:
                    logger.warning(f"Process cleanup failed for run {run_id}: {e}")
                finally:
                    self.active_processes.discard(proc)

    async def _cleanup_temp_files(self, run_id: str) -> None:
        """Clean up temporary files for this run.

        Args:
            run_id: Run identifier
        """
        for temp_dir in list(self.temp_directories):
            if run_id in str(temp_dir):
                try:
                    if temp_dir.exists():
                        import shutil

                        shutil.rmtree(temp_dir, ignore_errors=True)
                except Exception as e:
                    logger.warning(f"Temp directory cleanup failed for run {run_id}: {e}")
                finally:
                    self.temp_directories.discard(temp_dir)

    def _cleanup_memory_references(self, run_id: str) -> None:
        """Clean up memory references for this run.

        Args:
            run_id: Run identifier
        """
        # Close any open files related to this run
        for file_obj in list(self.open_files):
            if hasattr(file_obj, "name") and run_id in str(file_obj.name):
                try:
                    file_obj.close()
                except Exception as e:
                    logger.warning(f"File cleanup failed for run {run_id}: {e}")
                finally:
                    self.open_files.discard(file_obj)


class RecoveryManager:
    """Manages error recovery and graceful degradation."""

    async def attempt_recovery(self, run_context: "RunContext") -> bool:
        """Attempt to recover from tool execution failure.

        Args:
            run_context: Failed execution context

        Returns:
            True if recovery successful, False otherwise
        """
        if run_context.error_category == ErrorCategory.TOOL_ERROR:
            # Retry with reduced parameters for some tools
            if self._can_retry_with_fallback(run_context):
                run_context.recovery_attempted = True
                return await self._retry_with_fallback(run_context)

        elif run_context.error_category == ErrorCategory.SYSTEM_ERROR:
            # Wait and retry for transient system issues
            if self._is_transient_error(run_context):
                await asyncio.sleep(2)  # Brief wait
                run_context.recovery_attempted = True
                return await self._retry_execution(run_context)

        return False

    def _can_retry_with_fallback(self, run_context: "RunContext") -> bool:
        """Check if tool supports fallback retry.

        Args:
            run_context: Run context to check

        Returns:
            True if fallback retry is possible
        """
        # For now, allow fallback for specific tools
        return run_context.tool_id in ["cruise-control-analyzer"]

    def _is_transient_error(self, run_context: "RunContext") -> bool:
        """Check if error is transient and worth retrying.

        Args:
            run_context: Run context to check

        Returns:
            True if error appears transient
        """
        error_details = run_context.error_details
        if "system_error" in error_details:
            error_msg = str(error_details["system_error"]).lower()
            return any(
                keyword in error_msg
                for keyword in [
                    "temporarily unavailable",
                    "connection refused",
                    "timeout",
                    "resource temporarily unavailable",
                ]
            )
        return False

    async def _retry_with_fallback(self, run_context: "RunContext") -> bool:
        """Retry execution with fallback parameters.

        Args:
            run_context: Run context to retry

        Returns:
            True if retry successful
        """
        # This would integrate with the main execution engine
        # For now, just log the attempt
        logger.info(f"Attempting fallback retry for run {run_context.run_id}")
        return False

    async def _retry_execution(self, run_context: "RunContext") -> bool:
        """Retry execution with same parameters.

        Args:
            run_context: Run context to retry

        Returns:
            True if retry successful
        """
        # This would integrate with the main execution engine
        # For now, just log the attempt
        logger.info(f"Attempting transient error retry for run {run_context.run_id}")
        return False

    def suggest_tool_fix(self, error: Exception, stderr: str = "") -> str:
        """Generate actionable fix suggestions based on error details.

        Args:
            error: The exception that occurred
            stderr: Standard error output from tool

        Returns:
            User-friendly suggestion string
        """
        error_msg = str(error).lower()
        stderr_msg = stderr.lower()

        if "memory" in stderr_msg or "memoryerror" in error_msg:
            return "Tool ran out of memory. Try with smaller input file or increase system memory."
        elif "permission" in stderr_msg or "permissionerror" in error_msg:
            return "Permission denied. Check file permissions and user access rights."
        elif "not found" in stderr_msg or "filenotfounderror" in error_msg:
            return "Required file or dependency missing. Check file paths or run with --install-missing-deps flag."
        elif "timeout" in error_msg or isinstance(error, (asyncio.TimeoutError, TimeoutError)):
            return (
                "Tool execution timed out. Try increasing timeout or optimizing input parameters."
            )
        else:
            return "Tool execution failed. Check input parameters and tool compatibility."


class ExecutionEngine:
    """Engine for managing tool execution with async support."""

    def __init__(self, registry: ToolRegistry):
        """Initialize execution engine.

        Args:
            registry: Tool registry instance
        """
        self.registry = registry
        self.active_runs: Dict[str, RunContext] = {}
        self.resource_manager = ResourceManager()
        self.recovery_manager = RecoveryManager()

    async def start_run(self, request: RunRequest) -> RunResponse:
        """Start tool execution in background with enhanced error handling.

        Args:
            request: Run request

        Returns:
            Initial run response

        Raises:
            KeyError: If tool not found
            ValueError: If parameters invalid
        """
        run_context = RunContext(
            run_id=str(uuid4()),
            tool_id=request.tool_id,
            params=request.params,
            repo_root=request.repo_root,
            deps_dir=request.deps_dir,
            install_missing_deps=request.install_missing_deps,
        )

        try:
            tool = self.registry.get_tool(request.tool_id)
            self._validate_parameters(tool, request.params, request.input)

        except KeyError as e:
            # Tool not found
            run_context.status = RunStatus.FAILED
            run_context.error_category = ErrorCategory.TOOL_NOT_FOUND
            run_context.error = f"Tool not found: {request.tool_id}"
            run_context.error_details = {
                "validation_error": str(e),
                "suggested_fix": f"Check available tools or verify tool ID '{request.tool_id}'",
            }
            run_context.completed_at = datetime.now(timezone.utc)
            self.active_runs[run_context.run_id] = run_context
            return run_context.to_response()

        except ValueError as e:
            # Parameter validation failed
            run_context.status = RunStatus.FAILED
            run_context.error_category = ErrorCategory.VALIDATION_ERROR
            run_context.error = str(e)
            run_context.error_details = {
                "validation_error": str(e),
                "suggested_fix": "Check parameter names, types, and required values",
            }
            run_context.completed_at = datetime.now(timezone.utc)
            self.active_runs[run_context.run_id] = run_context
            return run_context.to_response()

        self.active_runs[run_context.run_id] = run_context
        asyncio.create_task(self.execute_tool_async(run_context))

        return run_context.to_response()

    async def get_run_status(self, run_id: str) -> RunResponse:
        """Get current run status.

        Args:
            run_id: Run identifier

        Returns:
            Current run status

        Raises:
            KeyError: If run not found
        """
        if run_id not in self.active_runs:
            raise KeyError(f"Run '{run_id}' not found")

        return self.active_runs[run_id].to_response()

    async def execute_tool_async(self, run_context: RunContext) -> None:
        """Execute tool with comprehensive error handling and timeout protection.

        Args:
            run_context: Run context to execute
        """
        try:
            run_context.status = RunStatus.RUNNING
            run_context.started_at = datetime.now(timezone.utc)

            logger.info(f"Starting execution of {run_context.tool_id} (run {run_context.run_id})")

            from .artifacts import get_artifact_manager
            from .logs import get_log_streamer

            artifact_manager = get_artifact_manager()
            log_streamer = get_log_streamer()

            log_streamer.add_log_entry(
                run_context.run_id, "INFO", f"Starting {run_context.tool_id} execution"
            )

            # Set up cleanup handlers
            run_context.cleanup_handlers.append(self._cleanup_temp_files)
            run_context.cleanup_handlers.append(self._release_resources)

            # Execute with timeout protection
            loop = asyncio.get_event_loop()
            try:
                await asyncio.wait_for(
                    loop.run_in_executor(None, self._execute_tool_sync, run_context),
                    timeout=run_context.timeout_seconds,
                )
            except asyncio.TimeoutError:
                run_context.error_category = ErrorCategory.TOOL_ERROR
                run_context.error_details = {
                    "error_type": "timeout",
                    "timeout_seconds": run_context.timeout_seconds,
                    "suggested_fix": "Increase timeout or optimize tool parameters",
                }
                raise asyncio.TimeoutError(
                    f"Tool execution timed out after {run_context.timeout_seconds} seconds"
                )

            artifacts = self._scan_for_artifacts(run_context)
            for artifact_path in artifacts:
                artifact_id = artifact_manager.register_artifact(run_context.run_id, artifact_path)
                run_context.artifacts.append(artifact_id)
                log_streamer.add_log_entry(
                    run_context.run_id, "INFO", f"Registered artifact: {artifact_path.name}"
                )

            run_context.status = RunStatus.COMPLETED
            run_context.completed_at = datetime.now(timezone.utc)
            run_context.progress = 100

            log_streamer.add_log_entry(
                run_context.run_id, "INFO", f"Completed {run_context.tool_id} execution"
            )

            log_streamer.terminate_stream(run_context.run_id)

            logger.info(f"Completed execution of {run_context.tool_id} (run {run_context.run_id})")

        except asyncio.TimeoutError as e:
            await self._handle_tool_failure(run_context, e, "Tool execution timed out")

        except (OSError, PermissionError, FileNotFoundError) as e:
            run_context.error_category = ErrorCategory.SYSTEM_ERROR
            run_context.error_details = {
                "system_error": str(e),
                "error_type": type(e).__name__,
                "suggested_fix": self._suggest_system_fix(e),
            }
            await self._handle_tool_failure(run_context, e, "System error occurred")

        except ValueError as e:
            # Handle validation-like errors from tool execution
            run_context.error_category = ErrorCategory.VALIDATION_ERROR
            run_context.error_details = {
                "validation_error": str(e),
                "suggested_fix": "Check input parameters and file formats",
            }
            await self._handle_tool_failure(run_context, e, "Validation error in tool execution")

        except Exception as e:
            # Generic tool execution error
            run_context.error_category = ErrorCategory.TOOL_ERROR
            run_context.error_details = {
                "tool_error": str(e),
                "error_type": type(e).__name__,
                "suggested_fix": self.recovery_manager.suggest_tool_fix(e),
            }
            await self._handle_tool_failure(run_context, e, "Tool execution failed")

    async def _handle_tool_failure(
        self, run_context: RunContext, error: Exception, message: str
    ) -> None:
        """Handle tool execution failure with cleanup and recovery attempts.

        Args:
            run_context: Failed run context
            error: The exception that occurred
            message: Human-readable error message
        """
        run_context.status = RunStatus.FAILED
        run_context.error = str(error)
        run_context.completed_at = datetime.now(timezone.utc)

        from .logs import get_log_streamer

        log_streamer = get_log_streamer()
        log_streamer.add_log_entry(run_context.run_id, "ERROR", f"{message}: {str(error)}")

        # Attempt recovery if applicable
        try:
            if await self.recovery_manager.attempt_recovery(run_context):
                log_streamer.add_log_entry(
                    run_context.run_id, "INFO", "Recovery attempt successful"
                )
                # Don't return here - let it fall through to cleanup
            else:
                log_streamer.add_log_entry(
                    run_context.run_id, "WARNING", "Recovery attempt failed or not applicable"
                )
        except Exception as recovery_error:
            logger.warning(
                f"Recovery attempt failed for run {run_context.run_id}: {recovery_error}"
            )

        # Always clean up resources
        try:
            await self.resource_manager.cleanup_run_resources(run_context)
        except Exception as cleanup_error:
            logger.error(f"Cleanup failed for run {run_context.run_id}: {cleanup_error}")

        log_streamer.terminate_stream(run_context.run_id)

        logger.error(
            f"Failed execution of {run_context.tool_id} (run {run_context.run_id}): {error}"
        )
        logger.error(traceback.format_exc())

    def _suggest_system_fix(self, error: Exception) -> str:
        """Generate system error fix suggestions.

        Args:
            error: The system exception

        Returns:
            User-friendly suggestion string
        """
        error_msg = str(error).lower()

        if isinstance(error, PermissionError):
            return "Permission denied. Check file permissions and user access rights."
        elif isinstance(error, FileNotFoundError):
            return "Required file not found. Check file paths and ensure all dependencies are available."
        elif isinstance(error, OSError):
            if "disk" in error_msg or "space" in error_msg:
                return "Insufficient disk space. Free up storage and try again."
            elif "memory" in error_msg:
                return "Insufficient memory. Close other applications or increase system memory."
            else:
                return "System resource issue. Check system resources and try again."
        else:
            return "System error occurred. Check system resources and configuration."

    async def _cleanup_temp_files(self, run_context: RunContext) -> None:
        """Cleanup handler for temporary files.

        Args:
            run_context: Run context being cleaned up
        """
        # This is a cleanup handler that would be registered
        logger.debug(f"Cleaning up temporary files for run {run_context.run_id}")

    async def _release_resources(self, run_context: RunContext) -> None:
        """Cleanup handler for releasing resources.

        Args:
            run_context: Run context being cleaned up
        """
        # This is a cleanup handler that would be registered
        logger.debug(f"Releasing resources for run {run_context.run_id}")

    def _execute_tool_sync(self, run_context: RunContext) -> None:
        """Synchronous tool execution - runs in thread.

        Args:
            run_context: Run context to execute
        """
        try:
            if run_context.tool_id == "cruise-control-analyzer":
                run_context.params.update(
                    {
                        "repo_root": run_context.repo_root,
                        "deps_dir": run_context.deps_dir,
                        "install_missing_deps": run_context.install_missing_deps,
                    }
                )

            tool_instance = self.registry.create_tool_instance(
                run_context.tool_id, **run_context.params
            )

            if run_context.tool_id == "cruise-control-analyzer":
                analyzer = tool_instance
                speed_min = run_context.params.get("speed_min", 55.0)
                speed_max = run_context.params.get("speed_max", 56.0)

                success = analyzer.run_analysis(speed_min, speed_max)
                if not success:
                    raise RuntimeError("Analysis failed")

            elif run_context.tool_id in ["rlog-to-csv", "can-bitwatch"]:
                original_argv = sys.argv.copy()
                try:
                    argv = [run_context.tool_id]
                    for key, value in run_context.params.items():
                        if key.startswith("_"):  # Skip internal parameters
                            continue
                        if isinstance(value, bool):
                            if value:
                                argv.append(f"--{key.replace('_', '-')}")
                        elif isinstance(value, list):
                            argv.append(f"--{key.replace('_', '-')}")
                            argv.extend(str(v) for v in value)
                        else:
                            argv.extend([f"--{key.replace('_', '-')}", str(value)])

                    sys.argv = argv
                    tool_instance()  # Call the main function
                finally:
                    sys.argv = original_argv
            else:
                raise ValueError(f"Execution not implemented for tool '{run_context.tool_id}'")

        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            raise

    def _validate_parameters(self, tool, params: Dict[str, Any], input_ref) -> None:
        """Validate parameters against tool schema.

        Args:
            tool: Tool capability
            params: Parameters to validate
            input_ref: Input reference

        Raises:
            ValueError: If validation fails
        """
        if input_ref:
            if input_ref.type == "path":
                if tool.id == "cruise-control-analyzer":
                    params["log_file"] = input_ref.value
                elif tool.id == "rlog-to-csv":
                    params["rlog"] = input_ref.value
                elif tool.id == "can-bitwatch":
                    params["csv"] = input_ref.value

        for param_name, param_def in tool.parameters.items():
            if param_def.required and param_name not in params:
                raise ValueError(f"Required parameter '{param_name}' missing")

        for param_name, value in params.items():
            if param_name in tool.parameters:
                param_def = tool.parameters[param_name]

                if param_def.type == "int" and not isinstance(value, int):
                    try:
                        params[param_name] = int(value)
                    except (ValueError, TypeError):
                        raise ValueError(f"Parameter '{param_name}' must be an integer")
                elif param_def.type == "float" and not isinstance(value, (int, float)):
                    try:
                        params[param_name] = float(value)
                    except (ValueError, TypeError):
                        raise ValueError(f"Parameter '{param_name}' must be a number")
                elif param_def.type == "bool" and not isinstance(value, bool):
                    if isinstance(value, str):
                        params[param_name] = value.lower() in ("true", "1", "yes", "on")
                    else:
                        params[param_name] = bool(value)

                if param_def.choices and params[param_name] not in param_def.choices:
                    raise ValueError(f"Parameter '{param_name}' must be one of {param_def.choices}")

    def cancel_run(self, run_id: str) -> bool:
        """Cancel a running tool execution.

        Args:
            run_id: Run identifier

        Returns:
            True if cancelled, False if not found or already completed
        """
        if run_id not in self.active_runs:
            return False

        run_context = self.active_runs[run_id]
        if run_context.status in [RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELED]:
            return False

        run_context.status = RunStatus.CANCELED
        run_context.completed_at = datetime.now(timezone.utc)
        run_context.error = "Cancelled by user"

        return True

    def _scan_for_artifacts(self, run_context: RunContext) -> List[Path]:
        """Scan for generated artifacts after tool execution.

        Args:
            run_context: Run context to scan for artifacts

        Returns:
            List of artifact file paths
        """
        artifacts: List[Path] = []

        if run_context.tool_id == "cruise-control-analyzer":
            search_dirs = []
            if "output_dir" in run_context.params:
                output_dir = Path(run_context.params["output_dir"])
                if output_dir.exists():
                    search_dirs.append(output_dir)
            else:
                search_dirs.append(Path("."))

            if not search_dirs:
                return artifacts

            patterns = ["*.csv", "*.json", "*.html", "*.png", "*.pdf"]

            for search_dir in search_dirs:
                for pattern in patterns:
                    for file_path in search_dir.glob(pattern):
                        if file_path.is_file() and file_path.stat().st_size > 0:
                            if (
                                run_context.started_at
                                and file_path.stat().st_mtime > run_context.started_at.timestamp()
                            ):
                                artifacts.append(file_path)

        return artifacts
