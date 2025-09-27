"""Resource management and cleanup for Phase 4A."""

import asyncio
import logging
import shutil
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional, Set
from typing import IO

logger = logging.getLogger(__name__)


class ResourceManager:
    """Manages and cleans up resources during tool execution."""

    def __init__(self):
        self.active_processes: Set[asyncio.subprocess.Process] = set()

        self.temp_files: Set[Path] = set()
        self.temp_directories: Set[Path] = set()
        self.open_file_handles: Set[IO] = set()

        self.large_objects: Dict[str, Any] = {}  # Run ID -> objects

        self.active_connections: Set = set()

        self.tool_resources: Dict[str, List[Callable[[], Awaitable[None]]]] = {}

    def register_process(self, process: asyncio.subprocess.Process) -> None:
        """Register an active subprocess for cleanup.

        Args:
            process: Subprocess to track
        """
        self.active_processes.add(process)
        logger.debug(f"Registered process {process.pid} for cleanup")

    def register_temp_file(self, file_path: Path) -> None:
        """Register a temporary file for cleanup.

        Args:
            file_path: Path to temporary file
        """
        self.temp_files.add(file_path)
        logger.debug(f"Registered temp file {file_path} for cleanup")

    def register_temp_directory(self, dir_path: Path) -> None:
        """Register a temporary directory for cleanup.

        Args:
            dir_path: Path to temporary directory
        """
        self.temp_directories.add(dir_path)
        logger.debug(f"Registered temp directory {dir_path} for cleanup")

    def register_file_handle(self, file_handle: IO) -> None:
        """Register an open file handle for cleanup.

        Args:
            file_handle: Open file handle
        """
        self.open_file_handles.add(file_handle)
        logger.debug(f"Registered file handle {file_handle.name} for cleanup")

    def register_large_object(self, run_id: str, obj: Any) -> None:
        """Register a large object for memory cleanup.

        Args:
            run_id: Run identifier
            obj: Large object to track
        """
        if run_id not in self.large_objects:
            self.large_objects[run_id] = []
        self.large_objects[run_id].append(obj)
        logger.debug(f"Registered large object for run {run_id}")

    def register_tool_cleanup(
        self, tool_id: str, cleanup_func: Callable[[], Awaitable[None]]
    ) -> None:
        """Register a tool-specific cleanup function.

        Args:
            tool_id: Tool identifier
            cleanup_func: Async cleanup function
        """
        if tool_id not in self.tool_resources:
            self.tool_resources[tool_id] = []
        self.tool_resources[tool_id].append(cleanup_func)
        logger.debug(f"Registered cleanup function for tool {tool_id}")

    async def cleanup_all(self, run_id: Optional[str] = None) -> None:
        """Execute comprehensive cleanup in priority order.

        Args:
            run_id: Optional run ID to clean up specific run resources
        """
        logger.info(f"Starting comprehensive cleanup for run {run_id or 'all'}")

        await self._cleanup_processes()

        await self._cleanup_file_handles()

        await self._cleanup_temp_files()
        await self._cleanup_temp_directories()

        await self._cleanup_memory(run_id)

        await self._cleanup_network()

        await self._cleanup_tool_resources()

        logger.info("Comprehensive cleanup completed")

    async def _cleanup_processes(self) -> None:
        """Clean up active processes."""
        if not self.active_processes:
            return

        logger.info(f"Cleaning up {len(self.active_processes)} active processes")

        for process in list(self.active_processes):
            try:
                if process.returncode is None:  # Process still running
                    logger.debug(f"Terminating process {process.pid}")
                    process.terminate()

                    try:
                        await asyncio.wait_for(process.wait(), timeout=5.0)
                    except asyncio.TimeoutError:
                        logger.warning(f"Force killing process {process.pid}")
                        process.kill()
                        await process.wait()

                self.active_processes.remove(process)
                logger.debug(f"Successfully cleaned up process {process.pid}")

            except Exception as e:
                logger.error(f"Error cleaning up process {getattr(process, 'pid', 'unknown')}: {e}")
                self.active_processes.discard(process)

    async def _cleanup_file_handles(self) -> None:
        """Clean up open file handles."""
        if not self.open_file_handles:
            return

        logger.info(f"Cleaning up {len(self.open_file_handles)} file handles")

        for handle in list(self.open_file_handles):
            try:
                if not handle.closed:
                    handle.close()
                    logger.debug(f"Closed file handle {handle.name}")
                self.open_file_handles.remove(handle)
            except Exception as e:
                logger.error(f"Error closing file handle: {e}")
                self.open_file_handles.discard(handle)

    async def _cleanup_temp_files(self) -> None:
        """Clean up temporary files."""
        if not self.temp_files:
            return

        logger.info(f"Cleaning up {len(self.temp_files)} temporary files")

        for file_path in list(self.temp_files):
            try:
                if file_path.exists():
                    file_path.unlink()
                    logger.debug(f"Removed temp file {file_path}")
                self.temp_files.remove(file_path)
            except Exception as e:
                logger.error(f"Error removing temp file {file_path}: {e}")
                self.temp_files.discard(file_path)

    async def _cleanup_temp_directories(self) -> None:
        """Clean up temporary directories."""
        if not self.temp_directories:
            return

        logger.info(f"Cleaning up {len(self.temp_directories)} temporary directories")

        for dir_path in list(self.temp_directories):
            try:
                if dir_path.exists():
                    shutil.rmtree(dir_path)
                    logger.debug(f"Removed temp directory {dir_path}")
                self.temp_directories.remove(dir_path)
            except Exception as e:
                logger.error(f"Error removing temp directory {dir_path}: {e}")
                self.temp_directories.discard(dir_path)

    async def _cleanup_memory(self, run_id: Optional[str] = None) -> None:
        """Clean up large object references."""
        if not self.large_objects:
            return

        if run_id:
            if run_id in self.large_objects:
                logger.info(f"Cleaning up large objects for run {run_id}")
                del self.large_objects[run_id]
        else:
            logger.info(f"Cleaning up large objects for {len(self.large_objects)} runs")
            self.large_objects.clear()

    async def _cleanup_network(self) -> None:
        """Clean up network connections (placeholder for future implementation)."""
        if not self.active_connections:
            return

        logger.info(f"Cleaning up {len(self.active_connections)} network connections")
        self.active_connections.clear()

    async def _cleanup_tool_resources(self) -> None:
        """Execute tool-specific cleanup handlers."""
        if not self.tool_resources:
            return

        logger.info(f"Executing tool-specific cleanup for {len(self.tool_resources)} tools")

        for tool_id, cleanup_funcs in self.tool_resources.items():
            for cleanup_func in cleanup_funcs:
                try:
                    await cleanup_func()
                    logger.debug(f"Executed cleanup function for tool {tool_id}")
                except Exception as e:
                    logger.error(f"Error in tool cleanup for {tool_id}: {e}")

        self.tool_resources.clear()
