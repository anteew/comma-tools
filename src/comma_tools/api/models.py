"""Pydantic request/response models for CTS-Lite API."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class ErrorCategory(str, Enum):
    """Error categorization for enhanced error handling."""

    TOOL_ERROR = "tool_error"  # Analyzer execution failed, including timeouts
    VALIDATION_ERROR = "validation_error"  # Invalid parameters/inputs
    SYSTEM_ERROR = "system_error"  # Infrastructure or resource issues


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
    """Enhanced error response model with actionable information."""

    error_category: ErrorCategory = Field(..., description="Error category for classification")
    error_code: str = Field(..., description="Specific error code")
    user_message: str = Field(..., description="User-friendly error message")
    technical_details: Dict[str, Any] = Field(
        default_factory=dict, description="Technical error details"
    )
    suggested_actions: List[str] = Field(
        default_factory=list, description="Suggested actions to fix the error"
    )
    recovery_attempted: bool = Field(default=False, description="Whether recovery was attempted")
    run_id: Optional[str] = Field(None, description="Associated run ID if applicable")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="Error timestamp"
    )

    @classmethod
    def from_run_context(cls, run_context) -> "ErrorResponse":
        """Create error response from failed run context.

        Args:
            run_context: Failed RunContext instance

        Returns:
            ErrorResponse with details from run context
        """
        from .execution import \
            RunContext  # Import here to avoid circular import

        return cls(
            error_category=run_context.error_category or ErrorCategory.TOOL_ERROR,
            error_code=cls._generate_error_code(run_context),
            user_message=cls._generate_user_message(run_context),
            technical_details=run_context.error_details,
            suggested_actions=cls._generate_suggestions(run_context),
            recovery_attempted=run_context.recovery_attempted,
            run_id=run_context.run_id,
            timestamp=datetime.now(timezone.utc),
        )

    @staticmethod
    def _generate_error_code(run_context) -> str:
        """Generate specific error code from run context.

        Args:
            run_context: RunContext instance

        Returns:
            Error code string
        """
        if run_context.error_category:
            error_type = run_context.error_details.get("error_type", "unknown")
            return f"{run_context.error_category.value}_{error_type}".upper()
        return "UNKNOWN_ERROR"

    @staticmethod
    def _generate_user_message(run_context) -> str:
        """Generate user-friendly error message.

        Args:
            run_context: RunContext instance

        Returns:
            User-friendly error message
        """
        if run_context.error_category == ErrorCategory.VALIDATION_ERROR:
            return f"Invalid input for {run_context.tool_id}: {run_context.error}"
        elif run_context.error_category == ErrorCategory.SYSTEM_ERROR:
            return f"System error occurred while running {run_context.tool_id}: {run_context.error}"
        elif run_context.error_category == ErrorCategory.TOOL_ERROR:
            return f"Tool {run_context.tool_id} failed to execute: {run_context.error}"
        else:
            return f"Unknown error occurred: {run_context.error}"

    @staticmethod
    def _generate_suggestions(run_context) -> List[str]:
        """Generate suggested actions from run context.

        Args:
            run_context: RunContext instance

        Returns:
            List of suggested actions
        """
        suggestions = []

        # Add fix suggestion from error details
        if "suggested_fix" in run_context.error_details:
            suggestions.append(run_context.error_details["suggested_fix"])

        # Add category-specific suggestions
        if run_context.error_category == ErrorCategory.VALIDATION_ERROR:
            suggestions.extend(
                [
                    "Verify all required parameters are provided",
                    "Check parameter types and formats",
                    "Review tool documentation for parameter requirements",
                ]
            )
        elif run_context.error_category == ErrorCategory.SYSTEM_ERROR:
            suggestions.extend(
                [
                    "Check system resources (disk space, memory)",
                    "Verify file permissions",
                    "Ensure all dependencies are installed",
                ]
            )
        elif run_context.error_category == ErrorCategory.TOOL_ERROR:
            suggestions.extend(
                [
                    "Try with different input parameters",
                    "Check input file format and content",
                    "Review tool logs for specific error details",
                ]
            )

        return suggestions[:5]  # Limit to 5 suggestions


class RunStatus(str, Enum):
    """Run execution status enumeration."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


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
