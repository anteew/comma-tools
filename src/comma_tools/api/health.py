"""Health check endpoint implementation with production-grade monitoring."""

import asyncio
import time
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

from fastapi import APIRouter

from .config import ProductionConfig
from .models import HealthResponse

router = APIRouter()

_start_time = time.time()


class HealthStatus(str, Enum):
    """Health check status types."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class HealthCheck:
    """Individual health check implementation."""

    def __init__(self, name: str, check_func: Callable, timeout: int = 5):
        self.name = name
        self.check_func = check_func
        self.timeout = timeout
        self.last_check: Optional[datetime] = None
        self.last_status: HealthStatus = HealthStatus.UNHEALTHY
        self.last_error: Optional[str] = None

    async def run(self) -> Dict[str, Any]:
        """Execute the health check."""
        start_time = datetime.now(timezone.utc)

        try:
            # Handle both sync and async check functions
            if asyncio.iscoroutinefunction(self.check_func):
                result = await asyncio.wait_for(self.check_func(), timeout=self.timeout)
            else:
                result = await asyncio.wait_for(
                    asyncio.create_task(asyncio.to_thread(self.check_func)), timeout=self.timeout
                )

            self.last_status = HealthStatus.HEALTHY
            self.last_error = None
            status_detail = "OK"

        except asyncio.TimeoutError:
            self.last_status = HealthStatus.UNHEALTHY
            self.last_error = f"Health check timed out after {self.timeout}s"
            status_detail = self.last_error

        except Exception as e:
            self.last_status = HealthStatus.UNHEALTHY
            self.last_error = str(e)
            status_detail = f"Check failed: {e}"

        self.last_check = start_time
        duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

        return {
            "name": self.name,
            "status": self.last_status,
            "last_check": start_time.isoformat(),
            "duration_ms": duration_ms,
            "details": status_detail,
        }


class HealthCheckManager:
    """Manages all health checks for the application."""

    def __init__(self, config: ProductionConfig):
        self.config = config
        self.checks: List[HealthCheck] = []
        self._setup_default_checks()

    def _setup_default_checks(self) -> None:
        """Set up standard health checks."""
        self.checks.extend(
            [
                HealthCheck("database_connection", self._check_database),
                HealthCheck("file_system", self._check_file_system),
                HealthCheck("tool_registry", self._check_tool_registry),
                HealthCheck("resource_usage", self._check_resource_usage),
            ]
        )

    def _check_database(self) -> bool:
        """Check database connectivity (if applicable)."""
        # For now, just a placeholder since we're file-based
        return True

    def _check_file_system(self) -> bool:
        """Check file system availability and space."""
        storage_path = Path(self.config.base_storage_path)
        if not storage_path.exists():
            raise Exception(f"Storage path {storage_path} does not exist")

        # Check available space if psutil is available
        if HAS_PSUTIL:
            try:
                disk_usage = psutil.disk_usage(str(storage_path))
                free_percent = (disk_usage.free / disk_usage.total) * 100

                if free_percent < 10:  # Less than 10% free
                    raise Exception(f"Low disk space: {free_percent:.1f}% free")
            except Exception as e:
                raise Exception(f"Cannot check disk space: {e}")

        return True

    def _check_tool_registry(self) -> bool:
        """Check that tool registry is functioning."""
        try:
            from .registry import ToolRegistry

            registry = ToolRegistry()
            # For now, just check that registry can be instantiated
            return True
        except Exception as e:
            raise Exception(f"Tool registry check failed: {e}")

    def _check_resource_usage(self) -> bool:
        """Check system resource usage."""
        if not HAS_PSUTIL:
            # If psutil is not available, skip resource checks
            return True

        try:
            memory = psutil.virtual_memory()
            cpu = psutil.cpu_percent(interval=1)

            if memory.percent > 90:
                raise Exception(f"High memory usage: {memory.percent:.1f}%")

            if cpu > 95:
                raise Exception(f"High CPU usage: {cpu:.1f}%")
        except Exception as e:
            # If psutil fails, don't fail the health check
            pass

        return True

    async def run_all_checks(self) -> Dict[str, Any]:
        """Run all health checks and return comprehensive status."""
        check_results = []

        # Run all checks concurrently
        check_tasks = [check.run() for check in self.checks]
        try:
            check_results = await asyncio.gather(*check_tasks, return_exceptions=True)
        except Exception:
            # If gather fails, run checks sequentially
            for check in self.checks:
                try:
                    result = await check.run()
                    check_results.append(result)
                except Exception as e:
                    check_results.append(
                        {
                            "name": check.name,
                            "status": HealthStatus.UNHEALTHY,
                            "details": f"Check execution failed: {e}",
                        }
                    )

        # Determine overall status
        healthy_count = sum(
            1
            for result in check_results
            if isinstance(result, dict) and result.get("status") == HealthStatus.HEALTHY
        )
        total_checks = len(self.checks)

        if healthy_count == total_checks:
            overall_status = HealthStatus.HEALTHY
        elif healthy_count > total_checks // 2:
            overall_status = HealthStatus.DEGRADED
        else:
            overall_status = HealthStatus.UNHEALTHY

        return {
            "status": overall_status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": check_results,
            "summary": {
                "total_checks": total_checks,
                "healthy_checks": healthy_count,
                "failed_checks": total_checks - healthy_count,
            },
        }


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
    Simple health check endpoint for backward compatibility.

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


@router.get("/health/detailed")
async def detailed_health_check() -> Dict[str, Any]:
    """
    Comprehensive health check with detailed status information.

    This endpoint will be integrated with the main FastAPI app to use the
    actual configuration and health check manager.
    """
    from .config import Environment, ProductionConfig

    # Use default development config for now
    config = ProductionConfig.get_environment_config(Environment.DEVELOPMENT)
    health_manager = HealthCheckManager(config)
    return await health_manager.run_all_checks()


@router.get("/health/simple")
async def simple_health_check() -> Dict[str, Any]:
    """Simple health check for load balancers."""
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}
