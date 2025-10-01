"""Rate limiting and cost controls for phone-a-friend MCP server."""

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, Optional


@dataclass
class UsageMetrics:
    """Usage metrics for rate limiting and cost tracking."""

    requests_per_minute: Deque[float] = field(default_factory=deque)
    total_requests: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    daily_cost: float = 0.0
    daily_reset_timestamp: float = field(default_factory=time.time)

    def reset_daily_if_needed(self) -> None:
        """Reset daily metrics if a day has passed."""
        current_time = time.time()
        if current_time - self.daily_reset_timestamp >= 86400:  # 24 hours
            self.daily_cost = 0.0
            self.daily_reset_timestamp = current_time


class RateLimiter:
    """
    Rate limiter with cost controls for OpenAI API usage.

    Implements:
    - Requests per minute throttling
    - Per-session cost limits
    - Daily cost limits
    - Usage tracking and reporting
    """

    def __init__(
        self,
        max_requests_per_minute: int = 60,
        cost_limit_per_session: float = 5.0,
        cost_limit_per_day: float = 50.0,
    ):
        """
        Initialize rate limiter.

        Args:
            max_requests_per_minute: Maximum requests per minute
            cost_limit_per_session: Maximum cost per session in USD
            cost_limit_per_day: Maximum daily cost in USD
        """
        self.max_requests_per_minute = max_requests_per_minute
        self.cost_limit_per_session = cost_limit_per_session
        self.cost_limit_per_day = cost_limit_per_day

        self.global_metrics = UsageMetrics()

        self.session_metrics: Dict[str, UsageMetrics] = {}

    def check_rate_limit(self) -> tuple[bool, str]:
        """
        Check if request is allowed under rate limits.

        Returns:
            Tuple of (allowed, reason_if_denied)
        """
        current_time = time.time()

        self.global_metrics.reset_daily_if_needed()

        if self.global_metrics.daily_cost >= self.cost_limit_per_day:
            return (
                False,
                f"Daily cost limit reached (${self.global_metrics.daily_cost:.2f} / ${self.cost_limit_per_day:.2f})",
            )

        cutoff_time = current_time - 60
        while (
            self.global_metrics.requests_per_minute
            and self.global_metrics.requests_per_minute[0] < cutoff_time
        ):
            self.global_metrics.requests_per_minute.popleft()

        if len(self.global_metrics.requests_per_minute) >= self.max_requests_per_minute:
            return (
                False,
                f"Rate limit exceeded ({len(self.global_metrics.requests_per_minute)} / {self.max_requests_per_minute} requests per minute)",
            )

        return True, ""

    def check_session_cost_limit(self, session_id: str) -> tuple[bool, str]:
        """
        Check if session is within cost limits.

        Args:
            session_id: Session identifier

        Returns:
            Tuple of (allowed, reason_if_denied)
        """
        if session_id not in self.session_metrics:
            return True, ""

        metrics = self.session_metrics[session_id]
        if metrics.total_cost >= self.cost_limit_per_session:
            return (
                False,
                f"Session cost limit reached (${metrics.total_cost:.2f} / ${self.cost_limit_per_session:.2f})",
            )

        return True, ""

    def record_request(self, session_id: str, tokens: int = 0, cost: float = 0.0) -> None:
        """
        Record a request for rate limiting and cost tracking.

        Args:
            session_id: Session identifier
            tokens: Number of tokens used
            cost: Estimated cost in USD
        """
        current_time = time.time()

        self.global_metrics.requests_per_minute.append(current_time)
        self.global_metrics.total_requests += 1
        self.global_metrics.total_tokens += tokens
        self.global_metrics.total_cost += cost
        self.global_metrics.daily_cost += cost

        if session_id not in self.session_metrics:
            self.session_metrics[session_id] = UsageMetrics()

        session_metrics = self.session_metrics[session_id]
        session_metrics.requests_per_minute.append(current_time)
        session_metrics.total_requests += 1
        session_metrics.total_tokens += tokens
        session_metrics.total_cost += cost

    def get_usage_summary(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get usage summary.

        Args:
            session_id: Optional session ID for session-specific metrics

        Returns:
            Dictionary with usage metrics
        """
        if session_id and session_id in self.session_metrics:
            metrics = self.session_metrics[session_id]
            return {
                "session_id": session_id,
                "total_requests": metrics.total_requests,
                "total_tokens": metrics.total_tokens,
                "total_cost": metrics.total_cost,
                "cost_limit": self.cost_limit_per_session,
                "cost_remaining": max(0, self.cost_limit_per_session - metrics.total_cost),
                "utilization_percent": (metrics.total_cost / self.cost_limit_per_session) * 100,
            }

        self.global_metrics.reset_daily_if_needed()
        return {
            "total_requests": self.global_metrics.total_requests,
            "total_tokens": self.global_metrics.total_tokens,
            "total_cost": self.global_metrics.total_cost,
            "daily_cost": self.global_metrics.daily_cost,
            "daily_cost_limit": self.cost_limit_per_day,
            "daily_cost_remaining": max(
                0, self.cost_limit_per_day - self.global_metrics.daily_cost
            ),
            "requests_per_minute": len(self.global_metrics.requests_per_minute),
            "requests_per_minute_limit": self.max_requests_per_minute,
        }

    def cleanup_session(self, session_id: str) -> None:
        """
        Clean up session metrics.

        Args:
            session_id: Session identifier
        """
        if session_id in self.session_metrics:
            del self.session_metrics[session_id]
