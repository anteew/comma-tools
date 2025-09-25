"""
Monitors command implementation.

Implements 'cts mon' commands for starting, streaming, stopping,
and listing monitors with WebSocket support.
"""

from typing import Dict, Any, List, Optional
import typer

from ..http import HTTPClient
from ..render import Renderer
from ..ws import stream_monitor
from ..commands.run import parse_parameters


def start_monitor_command(
    tool_id: str,
    params: List[str],
    http_client: Optional[HTTPClient] = None,
    renderer: Optional[Renderer] = None,
) -> int:
    """Start a monitor."""
    if http_client is None or renderer is None:
        raise ValueError("http_client and renderer are required")

    try:
        parsed_params = parse_parameters(params)

        monitor_data = {"tool_id": tool_id, "params": parsed_params}

        monitor_info = http_client.post_json("/v1/monitors", monitor_data)
        monitor_id = monitor_info["monitor_id"]

        if renderer.json_output:
            renderer.print_json(monitor_info)
        else:
            renderer.print_success(f"Started monitor: {monitor_id}")

        return 0

    except Exception as e:
        renderer.print_error(f"Failed to start monitor: {e}")
        return 1


def stream_monitor_command(
    monitor_id: str,
    raw: bool = False,
    ndjson: bool = False,
    http_client: Optional[HTTPClient] = None,
    renderer: Optional[Renderer] = None,
) -> int:
    """Stream data from a monitor."""
    if http_client is None or renderer is None:
        raise ValueError("http_client and renderer are required")

    try:
        renderer.print(f"Streaming monitor: {monitor_id}")

        use_raw = raw or (renderer.json_output and not ndjson)
        use_ndjson = ndjson or renderer.json_output

        for event in stream_monitor(http_client.config, monitor_id, raw=use_raw, ndjson=use_ndjson):
            renderer.print(event)

        return 0

    except KeyboardInterrupt:
        renderer.print("\nStopped streaming monitor")
        return 0

    except Exception as e:
        renderer.print_error(f"Failed to stream monitor: {e}")
        return 2


def stop_monitor_command(
    monitor_id: str, http_client: Optional[HTTPClient] = None, renderer: Optional[Renderer] = None
) -> int:
    """Stop a monitor."""
    if http_client is None or renderer is None:
        raise ValueError("http_client and renderer are required")

    try:
        response = http_client.delete(f"/v1/monitors/{monitor_id}")
        response.raise_for_status()

        if renderer.json_output:
            renderer.print_json({"monitor_id": monitor_id, "status": "stopped"})
        else:
            renderer.print_success(f"Stopped monitor: {monitor_id}")

        return 0

    except Exception as e:
        renderer.print_error(f"Failed to stop monitor: {e}")
        return 2


def list_monitors_command(
    http_client: Optional[HTTPClient] = None, renderer: Optional[Renderer] = None
) -> int:
    """List active monitors."""
    if http_client is None or renderer is None:
        raise ValueError("http_client and renderer are required")

    try:
        monitors = http_client.get_json("/v1/monitors")

        if renderer.json_output:
            renderer.print_json(monitors)
        else:
            if not monitors:
                renderer.print("No active monitors")
                return 0

            monitor_data = []
            for monitor in monitors:
                monitor_dict: Dict[str, Any] = monitor if isinstance(monitor, dict) else {}
                monitor_data.append(
                    {
                        "ID": monitor_dict.get("id", ""),
                        "Tool": monitor_dict.get("tool_id", ""),
                        "Status": monitor_dict.get("status", ""),
                        "Started": monitor_dict.get("started_at", ""),
                        "Uptime": monitor_dict.get("uptime", ""),
                    }
                )

            renderer.print_table(monitor_data, title="Active Monitors")

        return 0

    except Exception as e:
        renderer.print_error(f"Failed to list monitors: {e}")
        return 2
