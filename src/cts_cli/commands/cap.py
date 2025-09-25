"""
Capabilities and health check commands.

Implements 'cts ping' and 'cts cap' commands for API health
and capabilities discovery.
"""

from typing import Any, Dict

import typer

from ..http import HTTPClient
from ..render import Renderer


def ping_command(http_client: HTTPClient, renderer: Renderer) -> int:
    """Ping the CTS-Lite API health endpoint."""
    try:
        response = http_client.get("/v1/health")
        response.raise_for_status()

        data = response.json()

        if renderer.json_output:
            renderer.print_json(data)
        else:
            status = data.get("status", "unknown")
            version = data.get("version", "unknown")
            uptime = data.get("uptime", "unknown")

            renderer.print_success(f"CTS-Lite API is healthy")
            renderer.print(f"Status: {status}")
            renderer.print(f"Version: {version}")
            renderer.print(f"Uptime: {uptime}")

        return 0

    except Exception as e:
        renderer.print_error(f"Health check failed: {e}")
        return 2


def capabilities_command(http_client: HTTPClient, renderer: Renderer) -> int:
    """Get CTS-Lite API capabilities."""
    try:
        data = http_client.get_json("/v1/capabilities")

        if renderer.json_output:
            renderer.print_json(data)
        else:
            if not isinstance(data, dict):
                renderer.print_error("Unexpected capabilities response format")
                return 2

            renderer.print("CTS-Lite API Capabilities:")
            renderer.print("")

            tools = data.get("tools", [])
            if isinstance(tools, list) and tools:
                renderer.print("Available Tools:")
                tool_data = []
                for tool in tools:
                    tool_dict: Dict[str, Any] = tool if isinstance(tool, dict) else {}
                    tool_data.append(
                        {
                            "ID": tool_dict.get("id", ""),
                            "Name": tool_dict.get("name", ""),
                            "Description": tool_dict.get("description", ""),
                            "Version": tool_dict.get("version", ""),
                        }
                    )
                renderer.print_table(tool_data)
                renderer.print("")

            monitors = data.get("monitors", [])
            if isinstance(monitors, list) and monitors:
                renderer.print("Available Monitors:")
                monitor_data = []
                for monitor in monitors:
                    monitor_dict: Dict[str, Any] = monitor if isinstance(monitor, dict) else {}
                    monitor_data.append(
                        {
                            "ID": monitor_dict.get("id", ""),
                            "Name": monitor_dict.get("name", ""),
                            "Description": monitor_dict.get("description", ""),
                        }
                    )
                renderer.print_table(monitor_data)
                renderer.print("")

            api_version = data.get("api_version", "unknown")
            features = data.get("features", [])

            renderer.print(f"API Version: {api_version}")
            if isinstance(features, list) and features:
                renderer.print(f"Features: {', '.join(features)}")

        return 0

    except Exception as e:
        renderer.print_error(f"Failed to get capabilities: {e}")
        return 2
