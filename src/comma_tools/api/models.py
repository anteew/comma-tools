"""Pydantic request/response models for CTS-Lite API."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str = Field(..., description="Service health status")
    version: str = Field(..., description="Service version")
    uptime: str = Field(..., description="Service uptime in human readable format")
    timestamp: datetime = Field(..., description="Current timestamp")


class ToolParameter(BaseModel):
    """Tool parameter schema model."""

    type: str = Field(..., description="Parameter type (str, int, float, bool, list)")
    default: Optional[Any] = Field(None, description="Default value")
    description: str = Field(..., description="Parameter description")
    choices: Optional[List[str]] = Field(None, description="Valid choices for parameter")
    required: bool = Field(False, description="Whether parameter is required")
    nargs: Optional[str] = Field(
        None, description="Number of arguments (*, +, ?, or specific number)"
    )


class ToolCapability(BaseModel):
    """Tool capability model."""

    id: str = Field(..., description="Unique tool identifier")
    name: str = Field(..., description="Human readable tool name")
    description: str = Field(..., description="Tool description")
    category: str = Field(..., description="Tool category (analyzer or monitor)")
    version: Optional[str] = Field(None, description="Tool version")
    parameters: Dict[str, ToolParameter] = Field(
        default_factory=dict, description="Tool parameters"
    )


class CapabilitiesResponse(BaseModel):
    """Capabilities response model."""

    tools: List[ToolCapability] = Field(
        default_factory=list, description="Available analysis tools"
    )
    monitors: List[ToolCapability] = Field(
        default_factory=list, description="Available monitoring tools"
    )
    api_version: str = Field(..., description="API version")
    features: List[str] = Field(default_factory=list, description="Supported features")


class ErrorResponse(BaseModel):
    """Error response model."""

    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Detailed error information")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")


class RunStatus(str, Enum):
    """Run execution status enumeration."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class ErrorCategory(str, Enum):
    """High-level error categories for executions."""

    TOOL_ERROR = "tool_error"
    VALIDATION_ERROR = "validation_error"
    SYSTEM_ERROR = "system_error"


class InputRef(BaseModel):
    """Input reference for tool execution."""

    type: Literal["path", "upload"] = Field(..., description="Input type")
    value: str = Field(..., description="Input value (path or upload ID)")


class RunRequest(BaseModel):
    """Request model for starting a tool run."""

    tool_id: str = Field(..., description="Tool identifier to execute")
    params: Dict[str, Any] = Field(default_factory=dict, description="Tool parameters")
    input: Optional[InputRef] = Field(None, description="Input file reference")
    name: Optional[str] = Field(None, description="Optional run name")
    repo_root: Optional[str] = Field(None, description="Path to openpilot parent directory")
    deps_dir: Optional[str] = Field(None, description="Directory for Python dependencies")
    install_missing_deps: bool = Field(
        False, description="Install missing dependencies automatically"
    )


class RunResponse(BaseModel):
    """Response model for tool run status."""

    run_id: str = Field(..., description="Unique run identifier")
    status: RunStatus = Field(..., description="Current run status")
    tool_id: str = Field(..., description="Tool identifier")
    created_at: datetime = Field(..., description="Run creation timestamp")
    started_at: Optional[datetime] = Field(None, description="Run start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Run completion timestamp")
    params: Dict[str, Any] = Field(default_factory=dict, description="Tool parameters")
    progress: Optional[int] = Field(None, description="Progress percentage (0-100)")
    artifacts: List[str] = Field(default_factory=list, description="Generated artifact paths")
    error: Optional[str] = Field(None, description="Error message if failed")
    error_category: Optional[ErrorCategory] = Field(
        None, description="Categorized error type when failed"
    )
    error_details: Optional[Dict[str, Any]] = Field(
        default=None, description="Structured error details for troubleshooting"
    )


class ArtifactMetadata(BaseModel):
    """Artifact metadata model."""

    artifact_id: str = Field(..., description="Unique artifact identifier")
    run_id: str = Field(..., description="Run identifier")
    filename: str = Field(..., description="Original filename")
    content_type: str = Field(..., description="MIME content type")
    size_bytes: int = Field(..., description="File size in bytes")
    created_at: datetime = Field(..., description="Creation timestamp")
    download_url: str = Field(..., description="Download URL")


class ArtifactsResponse(BaseModel):
    """Artifacts response model."""

    run_id: str = Field(..., description="Run identifier")
    artifacts: List[ArtifactMetadata] = Field(default_factory=list, description="Artifact list")
    total_count: int = Field(..., description="Total artifact count")


class LogEntry(BaseModel):
    """Log entry model."""

    timestamp: datetime = Field(..., description="Log timestamp")
    level: str = Field(..., description="Log level")
    message: str = Field(..., description="Log message")
    source: str = Field(default="tool", description="Log source")


class LogsResponse(BaseModel):
    """Logs response model."""

    run_id: str = Field(..., description="Run identifier")
    logs: List[LogEntry] = Field(default_factory=list, description="Log entries")
    has_more: bool = Field(default=False, description="More logs available")
