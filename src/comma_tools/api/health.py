"""Health check endpoint implementation."""

import time
from datetime import datetime, timezone

from fastapi import APIRouter

from .models import HealthResponse

router = APIRouter()

_start_time = time.time()


def format_uptime(start_time: float) -> str:
    """Format uptime as human readable string."""
    uptime_seconds = int(time.time() - start_time)
    days = uptime_seconds // 86400
    hours = (uptime_seconds % 86400) // 3600
    minutes = (uptime_seconds % 3600) // 60
    seconds = uptime_seconds % 60

    return f"{days}d {hours}h {minutes}m {seconds}s"


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint.

    Returns service status, version, uptime and current timestamp.
    Should always return 200 OK unless service is shutting down.
    """
    from .. import __version__

    return HealthResponse(
        status="healthy",
        version=__version__,
        uptime=format_uptime(_start_time),
        timestamp=datetime.now(timezone.utc),
    )
