"""Pydantic request/response models for CTS-Lite API."""

from datetime import datetime
from typing import Any, Dict, List, Optional

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
