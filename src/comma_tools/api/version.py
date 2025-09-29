"""Version information and compatibility checking for CTS-Lite API."""

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

# API version follows semantic versioning
API_VERSION = "0.1.0"

# Minimum client version required to use this API
# Set this when making breaking changes to the API
MIN_CLIENT_VERSION = "0.8.0"

router = APIRouter()


class VersionInfo(BaseModel):
    """Version information response."""

    api_version: str
    min_client_version: str
    deprecated_features: list[str] = []


@router.get("/version", response_model=VersionInfo)
async def get_version() -> VersionInfo:
    """
    Get API version and compatibility information.

    This endpoint helps clients determine if they are compatible with the API.
    If a client's version is lower than min_client_version, it should prompt
    the user to upgrade.

    Returns:
        VersionInfo: API version, minimum client version, and deprecated features
    """
    return VersionInfo(
        api_version=API_VERSION,
        min_client_version=MIN_CLIENT_VERSION,
        deprecated_features=[],
    )
