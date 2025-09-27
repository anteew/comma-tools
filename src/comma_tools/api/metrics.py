"""Lightweight metrics collection for CTS-Lite.

This module provides an in-process metrics collector suitable for
tracking execution and API metrics without external dependencies.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict


@dataclass
class Metrics:
    # Execution Metrics
    runs_total: int = 0
    runs_successful: int = 0
    runs_failed: int = 0
    execution_duration_sum_seconds: float = 0.0
    execution_duration_count: int = 0

    # API Metrics
    api_requests_total: int = 0
    api_errors: int = 0
    api_response_time_sum_ms: float = 0.0
    api_response_time_count: int = 0

    # System Metrics
    active_runs: int = 0
    artifact_storage_bytes: int = 0
    log_storage_bytes: int = 0

    # Business Metrics (labelled)
    tools_usage: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    artifacts_generated: int = 0
    unique_users: int = 0

    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def inc_runs_total(self, tool_id: str | None = None) -> None:
        with self._lock:
            self.runs_total += 1
            if tool_id:
                self.tools_usage[tool_id] += 1
            self.active_runs += 1

    def mark_run_success(self, duration_seconds: float) -> None:
        with self._lock:
            self.runs_successful += 1
            self._record_duration(duration_seconds)
            self.active_runs = max(0, self.active_runs - 1)

    def mark_run_failure(self, duration_seconds: float) -> None:
        with self._lock:
            self.runs_failed += 1
            self._record_duration(duration_seconds)
            self.active_runs = max(0, self.active_runs - 1)

    def _record_duration(self, duration_seconds: float) -> None:
        self.execution_duration_sum_seconds += max(0.0, duration_seconds)
        self.execution_duration_count += 1

    def observe_api_response_time_ms(self, millis: float) -> None:
        with self._lock:
            self.api_requests_total += 1
            self.api_response_time_sum_ms += max(0.0, millis)
            self.api_response_time_count += 1

    def inc_api_errors(self) -> None:
        with self._lock:
            self.api_errors += 1


_metrics: Metrics | None = None


def get_metrics() -> Metrics:
    global _metrics
    if _metrics is None:
        _metrics = Metrics()
    return _metrics


def time_block_seconds() -> tuple[float, callable]:
    """Helper to measure elapsed seconds.

    Returns start time and a function that returns elapsed seconds.
    """
    start = time.monotonic()

    def elapsed() -> float:
        return time.monotonic() - start

    return start, elapsed

