"""
Server-Sent Events (SSE) streaming support for log tailing.

Provides SSE iterator with connection retry and backoff for
streaming logs from CTS-Lite API endpoints.
"""

import json
import time
from typing import Iterator, Dict, Any, Optional
import httpx

from .http import HTTPClient


class SSEStream:
    """Server-Sent Events stream with retry logic."""

    def __init__(self, http_client: HTTPClient, endpoint: str):
        """Initialize SSE stream."""
        self.http_client = http_client
        self.endpoint = endpoint
        self.max_retries = 5
        self.backoff_factor = 1.0

    def stream(self, follow: bool = False) -> Iterator[Dict[str, Any]]:
        """Stream events from SSE endpoint with retry logic."""
        retry_count = 0

        while True:
            try:
                for event in self.http_client.stream_sse(self.endpoint):
                    yield event
                    retry_count = 0  # Reset retry count on successful event

                if not follow:
                    break

            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                if not follow or retry_count >= self.max_retries:
                    raise

                wait_time = self.backoff_factor * (2**retry_count)
                time.sleep(min(wait_time, 60))  # Cap at 60 seconds
                retry_count += 1
                continue

            if not follow:
                break


def format_log_event(event: Dict[str, Any], json_output: bool = False) -> str:
    """Format log event for display."""
    if json_output:
        return json.dumps(event)

    timestamp = event.get("timestamp", "")
    level = event.get("level", "INFO")
    message = event.get("message", "")

    if timestamp:
        return f"[{timestamp}] {level}: {message}"
    else:
        return f"{level}: {message}"


def stream_logs(
    http_client: HTTPClient, run_id: str, follow: bool = False, json_output: bool = False
) -> Iterator[str]:
    """Stream logs for a run with formatting."""
    endpoint = f"/v1/runs/{run_id}/logs"
    sse_stream = SSEStream(http_client, endpoint)

    for event in sse_stream.stream(follow=follow):
        yield format_log_event(event, json_output=json_output)
