"""Tool registry for CTS-Lite service."""

from typing import Dict, List, Optional, Type

from pydantic import BaseModel

from .models import (
    CanBitwatchParams,
    CanBusCheckParams,
    CruiseControlAnalyzerParams,
    HybridRxTraceParams,
    PandaStateParams,
    RlogToCsvParams,
    ToolCapability,
    ToolKind,
)


class ToolSpec:
    """Specification for a tool in the registry."""
    
    def __init__(
        self,
        tool_id: str,
        kind: ToolKind,
        version: str,
        description: str,
        params_model: Type[BaseModel],
        accepted_inputs: Optional[List[str]] = None,
        declared_outputs: Optional[List[Dict[str, str]]] = None,
    ):
        self.tool_id = tool_id
        self.kind = kind
        self.version = version
        self.description = description
        self.params_model = params_model
        self.accepted_inputs = accepted_inputs or []
        self.declared_outputs = declared_outputs or []
    
    def to_capability(self) -> ToolCapability:
        """Convert to API capability response."""
        return ToolCapability(
            tool_id=self.tool_id,
            kind=self.kind,
            version=self.version,
            description=self.description,
            params_schema=self.params_model.model_json_schema(),
            accepted_inputs=self.accepted_inputs,
            declared_outputs=self.declared_outputs,
        )


class ToolRegistry:
    """Registry of available tools."""
    
    def __init__(self):
        self._tools: Dict[str, ToolSpec] = {}
        self._register_default_tools()
    
    def _register_default_tools(self) -> None:
        """Register the default set of tools."""
        
        self.register(ToolSpec(
            tool_id="cruise-control-analyzer",
            kind=ToolKind.analyzer,
            version="0.8.0",
            description="Analyze rlog.zst files for Subaru cruise control signals and CAN bit changes",
            params_model=CruiseControlAnalyzerParams,
            accepted_inputs=["rlog.zst"],
            declared_outputs=[
                {"name": "analysis_report.html", "media_type": "text/html", "schema_version": "v1"},
                {"name": "speed_timeline.png", "media_type": "image/png"},
                {"name": "counts_by_segment.csv", "media_type": "text/csv", "schema_version": "v1"},
                {"name": "candidates.csv", "media_type": "text/csv", "schema_version": "v1"},
                {"name": "edges.csv", "media_type": "text/csv", "schema_version": "v1"},
                {"name": "runs.csv", "media_type": "text/csv", "schema_version": "v1"},
                {"name": "timeline.csv", "media_type": "text/csv", "schema_version": "v1"},
            ]
        ))
        
        self.register(ToolSpec(
            tool_id="rlog-to-csv",
            kind=ToolKind.analyzer,
            version="0.8.0",
            description="Convert openpilot rlog.zst files to CSV format for CAN analysis",
            params_model=RlogToCsvParams,
            accepted_inputs=["rlog.zst"],
            declared_outputs=[
                {"name": "output.csv", "media_type": "text/csv", "schema_version": "v1"},
            ]
        ))
        
        self.register(ToolSpec(
            tool_id="can-bitwatch",
            kind=ToolKind.analyzer,
            version="0.8.0",
            description="Analyze CAN CSV dumps for bit changes and cruise control patterns",
            params_model=CanBitwatchParams,
            accepted_inputs=["csv"],
            declared_outputs=[
                {"name": "counts.csv", "media_type": "text/csv"},
                {"name": "per_address.json", "media_type": "application/json"},
                {"name": "bit_edges.csv", "media_type": "text/csv"},
                {"name": "candidates_window_only.csv", "media_type": "text/csv"},
                {"name": "accel_hunt.csv", "media_type": "text/csv"},
            ]
        ))
        
        self.register(ToolSpec(
            tool_id="hybrid-rx-trace",
            kind=ToolKind.monitor,
            version="0.8.0",
            description="Monitor which CAN signals cause panda safety RX invalid states",
            params_model=HybridRxTraceParams,
            accepted_inputs=[],
            declared_outputs=[],
        ))
        
        self.register(ToolSpec(
            tool_id="can-bus-check",
            kind=ToolKind.monitor,
            version="0.8.0",
            description="Monitor CAN message frequencies by bus for interesting addresses",
            params_model=CanBusCheckParams,
            accepted_inputs=[],
            declared_outputs=[],
        ))
        
        self.register(ToolSpec(
            tool_id="panda-state",
            kind=ToolKind.monitor,
            version="0.8.0",
            description="Monitor panda device safety states and control permissions",
            params_model=PandaStateParams,
            accepted_inputs=[],
            declared_outputs=[],
        ))
    
    def register(self, tool_spec: ToolSpec) -> None:
        """Register a tool."""
        self._tools[tool_spec.tool_id] = tool_spec
    
    def get(self, tool_id: str) -> ToolSpec:
        """Get a tool by ID."""
        if tool_id not in self._tools:
            raise ValueError(f"Unknown tool: {tool_id}")
        return self._tools[tool_id]
    
    def list_tools(self) -> List[ToolSpec]:
        """List all registered tools."""
        return list(self._tools.values())
    
    def get_capabilities(self) -> List[ToolCapability]:
        """Get capabilities for all tools."""
        return [tool.to_capability() for tool in self._tools.values()]


registry = ToolRegistry()
