"""
Logs command implementation.

Implements 'cts logs' command for streaming run logs with
optional follow mode and formatting.
"""

from typing import Optional
import typer

from ..http import HTTPClient
from ..render import Renderer
from ..sse import stream_logs


def logs_command(
    run_id: str, follow: bool = False, http_client: HTTPClient = None, renderer: Renderer = None
) -> int:
    """Stream logs for a run."""
    try:
        if not follow:
            renderer.print(f"Getting logs for run: {run_id}")
        else:
            renderer.print(f"Following logs for run: {run_id}")

        for log_line in stream_logs(
            http_client, run_id, follow=follow, json_output=renderer.json_output
        ):
            renderer.print(log_line)

        return 0

    except KeyboardInterrupt:
        if follow:
            renderer.print("\nStopped following logs")
        return 0

    except Exception as e:
        renderer.print_error(f"Failed to get logs: {e}")
        return 2
