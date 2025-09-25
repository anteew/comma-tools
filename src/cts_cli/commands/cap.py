"""
Capabilities and health check commands.

Implements 'cts ping' and 'cts cap' commands for API health
and capabilities discovery.
"""

from typing import Dict, Any
import typer

from ..http import HTTPClient
from ..render import Renderer


def ping_command(
    http_client: HTTPClient,
    renderer: Renderer
) -> int:
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


def capabilities_command(
    http_client: HTTPClient,
    renderer: Renderer
) -> int:
    """Get CTS-Lite API capabilities."""
    try:
        data = http_client.get_json("/v1/capabilities")
        
        if renderer.json_output:
            renderer.print_json(data)
        else:
            renderer.print("CTS-Lite API Capabilities:")
            renderer.print("")
            
            tools = data.get("tools", [])
            if tools:
                renderer.print("Available Tools:")
                tool_data = []
                for tool in tools:
                    tool_data.append({
                        "ID": tool.get("id", ""),
                        "Name": tool.get("name", ""),
                        "Description": tool.get("description", ""),
                        "Version": tool.get("version", "")
                    })
                renderer.print_table(tool_data)
                renderer.print("")
            
            monitors = data.get("monitors", [])
            if monitors:
                renderer.print("Available Monitors:")
                monitor_data = []
                for monitor in monitors:
                    monitor_data.append({
                        "ID": monitor.get("id", ""),
                        "Name": monitor.get("name", ""),
                        "Description": monitor.get("description", "")
                    })
                renderer.print_table(monitor_data)
                renderer.print("")
            
            api_version = data.get("api_version", "unknown")
            features = data.get("features", [])
            
            renderer.print(f"API Version: {api_version}")
            if features:
                renderer.print(f"Features: {', '.join(features)}")
        
        return 0
        
    except Exception as e:
        renderer.print_error(f"Failed to get capabilities: {e}")
        return 2
