"""Tool registry for dynamic tool discovery and management."""

import argparse
import inspect
from typing import Any, Dict, Optional

from .capabilities import (
    _get_can_bitwatch_capability,
    _get_cruise_control_analyzer_capability,
    _get_rlog_to_csv_capability,
)
from .models import ToolCapability


class ToolRegistry:
    """Registry for managing available tools and their capabilities."""

    def __init__(self):
        """Initialize the tool registry and discover available tools."""
        self.tools: Dict[str, ToolCapability] = {}
        self.discover_tools()

    def discover_tools(self) -> None:
        """Scan analyzers directory and register tools."""
        tools = [
            _get_cruise_control_analyzer_capability(),
            _get_rlog_to_csv_capability(),
            _get_can_bitwatch_capability(),
        ]

        for tool in tools:
            self.tools[tool.id] = tool

    def get_tool(self, tool_id: str) -> ToolCapability:
        """Get tool capability by ID.

        Args:
            tool_id: Tool identifier

        Returns:
            Tool capability

        Raises:
            KeyError: If tool not found
        """
        if tool_id not in self.tools:
            raise KeyError(f"Tool '{tool_id}' not found")
        return self.tools[tool_id]

    def _initialize_cruise_control_environment(
        self,
        repo_root: Optional[str] = None,
        deps_dir: Optional[str] = None,
        install_missing_deps: bool = False,
    ) -> None:
        """Initialize environment for cruise control analyzer.

        Replicates the initialization sequence from cruise_control_analyzer.main.
        """
        from ..utils.openpilot_utils import (
            ensure_python_packages,
            find_repo_root,
            load_external_modules,
            prepare_environment,
            resolve_deps_dir,
        )

        repo_root_path = find_repo_root(repo_root)

        deps_dir_path = resolve_deps_dir(repo_root_path, deps_dir)

        prepare_environment(repo_root_path, deps_dir_path)

        requirements = [
            ("matplotlib", "matplotlib"),
            ("numpy", "numpy"),
            ("capnp", "pycapnp"),
            ("tqdm", "tqdm"),
            ("zstandard", "zstandard"),
            ("zmq", "pyzmq"),
            ("smbus2", "smbus2"),
        ]
        ensure_python_packages(requirements, deps_dir_path, install_missing_deps)

        modules = load_external_modules()

        import comma_tools.analyzers.cruise_control_analyzer as cca_module

        cca_module.np = modules["np"]
        cca_module.plt = modules["plt"]
        cca_module.LogReader = modules["LogReader"]
        cca_module.messaging = modules["messaging"]

    def create_tool_instance(self, tool_id: str, **kwargs) -> Any:
        """Create tool instance with parameters.

        Args:
            tool_id: Tool identifier
            **kwargs: Tool parameters

        Returns:
            Tool instance or callable

        Raises:
            KeyError: If tool not found
            ValueError: If tool type not supported
        """
        try:
            tool = self.get_tool(tool_id)
        except KeyError:
            raise ValueError(f"Tool instance creation not implemented for '{tool_id}'")

        if tool_id == "cruise-control-analyzer":
            repo_root = kwargs.get("repo_root")
            deps_dir = kwargs.get("deps_dir")
            install_missing_deps = kwargs.get("install_missing_deps", False)

            try:
                self._initialize_cruise_control_environment(
                    repo_root, deps_dir, install_missing_deps
                )
            except (FileNotFoundError, ImportError, RuntimeError) as e:
                raise ValueError(f"Failed to initialize cruise control environment: {e}")

            from ..analyzers.cruise_control_analyzer import CruiseControlAnalyzer

            log_file = kwargs.get("log_file") or kwargs.get("path")
            if not log_file:
                raise ValueError("log_file parameter required for cruise-control-analyzer")
            return CruiseControlAnalyzer(log_file)
        elif tool_id == "rlog-to-csv":
            from ..analyzers.rlog_to_csv import main as rlog_to_csv_main

            return rlog_to_csv_main
        elif tool_id == "can-bitwatch":
            from ..analyzers.can_bitwatch import main as can_bitwatch_main

            return can_bitwatch_main
        else:
            raise ValueError(f"Tool instance creation not implemented for '{tool_id}'")

    def list_tools(self) -> Dict[str, ToolCapability]:
        """List all available tools.

        Returns:
            Dictionary of tool ID to capability
        """
        return self.tools.copy()
