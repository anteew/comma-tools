"""Application metrics collection and monitoring for CTS-Lite API."""

import time
from collections import Counter as CounterType
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Dict, List

try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


@dataclass
class Metrics:
    """Application metrics collection."""

    # Execution Metrics
    runs_total: int = 0
    runs_successful: int = 0
    runs_failed: int = 0
    execution_times: List[float] = field(default_factory=list)

    # API Metrics
    api_requests_total: int = 0
    api_response_times: List[float] = field(default_factory=list)
    api_errors_by_endpoint: Dict[str, int] = field(default_factory=dict)

    # System Metrics
    active_runs: int = 0
    peak_concurrent_runs: int = 0
    artifact_storage_bytes: int = 0
    log_storage_bytes: int = 0

    # Business Metrics
    tools_usage_count: CounterType[str] = field(default_factory=CounterType)
    artifacts_generated: int = 0

    _lock: Lock = field(default_factory=Lock, init=False)


class MetricsCollector:
    """Collects and manages application metrics."""

    def __init__(self):
        self.metrics = Metrics()
        self.start_time = time.time()

    def record_run_start(self, tool_id: str, run_id: str) -> None:
        """Record the start of a tool execution."""
        with self.metrics._lock:
            self.metrics.runs_total += 1
            self.metrics.active_runs += 1
            self.metrics.peak_concurrent_runs = max(
                self.metrics.peak_concurrent_runs, self.metrics.active_runs
            )
            self.metrics.tools_usage_count[tool_id] += 1

    def record_run_completion(self, run_id: str, success: bool, duration: float) -> None:
        """Record the completion of a tool execution."""
        with self.metrics._lock:
            self.metrics.active_runs -= 1
            self.metrics.execution_times.append(duration)

            if success:
                self.metrics.runs_successful += 1
            else:
                self.metrics.runs_failed += 1

    def record_api_request(self, endpoint: str, response_time: float, success: bool) -> None:
        """Record API request metrics."""
        with self.metrics._lock:
            self.metrics.api_requests_total += 1
            self.metrics.api_response_times.append(response_time)

            if not success:
                self.metrics.api_errors_by_endpoint[endpoint] = (
                    self.metrics.api_errors_by_endpoint.get(endpoint, 0) + 1
                )

    def record_artifact_generated(self, size_bytes: int = 0) -> None:
        """Record artifact generation."""
        with self.metrics._lock:
            self.metrics.artifacts_generated += 1
            self.metrics.artifact_storage_bytes += size_bytes

    def get_system_metrics(self) -> Dict[str, Any]:
        """Get current system metrics."""
        if not HAS_PSUTIL:
            # Fallback if psutil is not available
            return {
                "cpu_percent": 0.0,
                "memory_percent": 0.0,
                "memory_available_bytes": 0,
                "disk_free_bytes": 0,
                "disk_used_percent": 0.0,
                "uptime_seconds": time.time() - self.start_time,
            }

        try:
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage("/")

            return {
                "cpu_percent": psutil.cpu_percent(),
                "memory_percent": memory.percent,
                "memory_available_bytes": memory.available,
                "disk_free_bytes": disk.free,
                "disk_used_percent": (disk.used / disk.total) * 100,
                "uptime_seconds": time.time() - self.start_time,
            }
        except Exception:
            # Fallback if psutil fails
            return {
                "cpu_percent": 0.0,
                "memory_percent": 0.0,
                "memory_available_bytes": 0,
                "disk_free_bytes": 0,
                "disk_used_percent": 0.0,
                "uptime_seconds": time.time() - self.start_time,
            }

    def get_summary(self) -> Dict[str, Any]:
        """Get comprehensive metrics summary."""
        with self.metrics._lock:
            success_rate = (
                self.metrics.runs_successful / self.metrics.runs_total
                if self.metrics.runs_total > 0
                else 0
            )

            avg_execution_time = (
                sum(self.metrics.execution_times) / len(self.metrics.execution_times)
                if self.metrics.execution_times
                else 0
            )

            avg_response_time = (
                sum(self.metrics.api_response_times) / len(self.metrics.api_response_times)
                if self.metrics.api_response_times
                else 0
            )

            return {
                "execution_metrics": {
                    "runs_total": self.metrics.runs_total,
                    "runs_successful": self.metrics.runs_successful,
                    "runs_failed": self.metrics.runs_failed,
                    "success_rate": success_rate,
                    "average_execution_time_seconds": avg_execution_time,
                    "active_runs": self.metrics.active_runs,
                    "peak_concurrent_runs": self.metrics.peak_concurrent_runs,
                },
                "api_metrics": {
                    "requests_total": self.metrics.api_requests_total,
                    "average_response_time_ms": avg_response_time * 1000,
                    "errors_by_endpoint": dict(self.metrics.api_errors_by_endpoint),
                },
                "business_metrics": {
                    "tools_usage": dict(self.metrics.tools_usage_count),
                    "artifacts_generated": self.metrics.artifacts_generated,
                    "artifact_storage_bytes": self.metrics.artifact_storage_bytes,
                },
                "system_metrics": self.get_system_metrics(),
            }

    def reset_metrics(self) -> None:
        """Reset all metrics (useful for testing)."""
        with self.metrics._lock:
            self.metrics = Metrics()
            self.start_time = time.time()
