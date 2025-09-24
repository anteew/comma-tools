"""Pydantic models for CTS-Lite API contracts."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field


class InputRef(BaseModel):
    """Reference to input data for a run."""

    kind: Literal["path", "upload"]
    path: Optional[str] = None
    id: Optional[str] = None  # upload id


class ArtifactRef(BaseModel):
    """Reference to an output artifact."""

    id: str
    name: str
    media_type: str
    size: Optional[int] = None
    sha256: Optional[str] = None
    schema_version: Optional[str] = None
    download_uri: str


class RunStatus(str, Enum):
    """Status of a batch run."""

    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    canceled = "canceled"


class Run(BaseModel):
    """A batch analyzer run."""

    id: str
    tool_id: str
    version: Optional[str] = None
    status: RunStatus
    submitted_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    params: Dict[str, Any]
    inputs: List[InputRef]
    outputs: Optional[Dict[str, Any]] = None  # summary JSON
    artifacts: List[ArtifactRef] = Field(default_factory=list)
    logs_uri: str


class MonitorStatus(str, Enum):
    """Status of a realtime monitor."""

    starting = "starting"
    running = "running"
    stopped = "stopped"
    failed = "failed"


class Monitor(BaseModel):
    """A realtime monitor session."""

    id: str
    tool_id: str
    version: Optional[str] = None
    status: MonitorStatus
    params: Dict[str, Any]
    stream_uri: str


class ToolKind(str, Enum):
    """Type of tool."""

    analyzer = "analyzer"
    monitor = "monitor"
    utility = "utility"


class ToolCapability(BaseModel):
    """Tool capability description."""

    tool_id: str
    kind: ToolKind
    version: Optional[str] = None
    description: str
    params_schema: Dict[str, Any]  # JSON Schema
    accepted_inputs: List[str] = Field(default_factory=list)  # file extensions
    declared_outputs: List[Dict[str, str]] = Field(default_factory=list)  # artifact types


class CreateRunRequest(BaseModel):
    """Request to create a new run."""

    tool_id: str
    params: Dict[str, Any] = Field(default_factory=dict)
    inputs: List[InputRef] = Field(default_factory=list)


class CreateMonitorRequest(BaseModel):
    """Request to create a new monitor."""

    tool_id: str
    params: Dict[str, Any] = Field(default_factory=dict)


class ExecRequest(BaseModel):
    """Request to execute a utility function."""

    tool_id: str
    params: Dict[str, Any] = Field(default_factory=dict)
    timeout: int = 10


class HealthResponse(BaseModel):
    """Health check response."""

    status: Literal["ok", "degraded", "error"]
    checks: Dict[str, Any]
    timestamp: datetime


class VersionResponse(BaseModel):
    """Version information response."""

    service_version: str
    tool_versions: Dict[str, str]


class CruiseControlAnalyzerParams(BaseModel):
    """Parameters for cruise control analyzer."""

    speed_min: float = 55.0
    speed_max: float = 56.0
    marker_type: str = "blinkers"
    marker_pre: float = 5.0
    marker_post: float = 5.0
    marker_timeout: float = 10.0
    export_csv: bool = False
    export_json: bool = False
    repo_root: Optional[str] = None
    deps_dir: Optional[str] = None
    install_missing_deps: bool = False


class RlogToCsvParams(BaseModel):
    """Parameters for rlog to CSV converter."""

    window_start: Optional[float] = None
    window_dur: Optional[float] = None
    repo_root: Optional[str] = None


class CanBitwatchParams(BaseModel):
    """Parameters for CAN bitwatch analyzer."""

    output_prefix: str = "analysis"
    watch: List[str] = Field(default_factory=list)  # bit specifications like "0x027:B4b5"


class HybridRxTraceParams(BaseModel):
    """Parameters for hybrid RX trace monitor."""

    pass  # No parameters for this monitor


class CanBusCheckParams(BaseModel):
    """Parameters for CAN bus check monitor."""

    sample_seconds: float = 5.0


class PandaStateParams(BaseModel):
    """Parameters for panda state monitor."""

    pass  # No parameters for this monitor
