"""Tool execution engine with async support."""

import asyncio
import logging
import sys
import traceback
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import uuid4

from .models import RunRequest, RunResponse, RunStatus
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
        self.created_at = datetime.utcnow()
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.progress: Optional[int] = None
        self.error: Optional[str] = None
        self.artifacts: list[str] = []

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


class ExecutionEngine:
    """Engine for managing tool execution with async support."""

    def __init__(self, registry: ToolRegistry):
        """Initialize execution engine.

        Args:
            registry: Tool registry instance
        """
        self.registry = registry
        self.active_runs: Dict[str, RunContext] = {}

    async def start_run(self, request: RunRequest) -> RunResponse:
        """Start tool execution in background.

        Args:
            request: Run request

        Returns:
            Initial run response

        Raises:
            KeyError: If tool not found
            ValueError: If parameters invalid
        """
        tool = self.registry.get_tool(request.tool_id)

        self._validate_parameters(tool, request.params, request.input)

        run_context = RunContext(
            run_id=str(uuid4()),
            tool_id=request.tool_id,
            params=request.params,
            repo_root=request.repo_root,
            deps_dir=request.deps_dir,
            install_missing_deps=request.install_missing_deps,
        )

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
        """Execute tool in separate thread to avoid blocking API.

        Args:
            run_context: Run context to execute
        """
        try:
            run_context.status = RunStatus.RUNNING
            run_context.started_at = datetime.utcnow()

            logger.info(f"Starting execution of {run_context.tool_id} (run {run_context.run_id})")

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None, self._execute_tool_sync, run_context  # Use default ThreadPoolExecutor
            )

            run_context.status = RunStatus.COMPLETED
            run_context.completed_at = datetime.utcnow()
            run_context.progress = 100

            logger.info(f"Completed execution of {run_context.tool_id} (run {run_context.run_id})")

        except Exception as e:
            run_context.status = RunStatus.FAILED
            run_context.error = str(e)
            run_context.completed_at = datetime.utcnow()

            logger.error(
                f"Failed execution of {run_context.tool_id} (run {run_context.run_id}): {e}"
            )
            logger.error(traceback.format_exc())

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
        run_context.completed_at = datetime.utcnow()
        run_context.error = "Cancelled by user"

        return True
