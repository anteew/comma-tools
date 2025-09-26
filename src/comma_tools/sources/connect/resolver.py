"""
Route resolver for comma connect URLs.

Handles parsing and resolving connect URLs to canonical route names
using device segment search within configurable time windows.
"""

import re
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from urllib.parse import urlparse

from .client import ConnectClient


class RouteResolver:
    """
    Resolves connect URLs to canonical route names.

    Handles both canonical route names and connect URLs by searching
    device segments within a configurable time window.
    """

    def __init__(self, client: ConnectClient):
        self.client = client

    def parse_input(self, input_str: str) -> Tuple[str, str]:
        """
        Parse input string to determine type and extract components.

        Args:
            input_str: Either canonical route or connect URL

        Returns:
            Tuple of (type, canonical_route_or_dongle_id)
            where type is 'canonical' or 'connect'
        """
        canonical_pattern = r"^([a-f0-9]{16})\|(\d{4}-\d{2}-\d{2}--\d{2}-\d{2}-\d{2})$"
        if re.match(canonical_pattern, input_str):
            return ("canonical", input_str)

        connect_pattern = r"https://connect\.comma\.ai/([a-f0-9]{16})/([a-f0-9]{8}--[a-f0-9]{10})"
        match = re.match(connect_pattern, input_str)
        if match:
            dongle_id, url_slug = match.groups()
            return ("connect", dongle_id)

        raise ValueError(
            f"Invalid input format: {input_str}\n"
            "Expected canonical route (dongle|YYYY-MM-DD--HH-MM-SS) "
            "or connect URL (https://connect.comma.ai/dongle/slug)"
        )

    def resolve_connect_url(self, connect_url: str, search_days: int = 7) -> str:
        """
        Resolve connect URL to canonical route name using openpilot-style parsing.

        Args:
            connect_url: Connect URL to resolve
            search_days: Number of days to search backwards (unused, for compatibility)

        Returns:
            Canonical route name

        Raises:
            ValueError: If URL cannot be resolved
        """
        connect_pattern = r"https://connect\.comma\.ai/([a-f0-9]{16})/([a-f0-9]{8}--[a-f0-9]{10})"
        match = re.match(connect_pattern, connect_url)
        if not match:
            raise ValueError(f"Invalid connect URL format: {connect_url}")

        dongle_id, url_slug = match.groups()

        # Use openpilot-style parsing: create canonical route name
        # Convert dcb4c2e18426be55/00000008--0696c823fa -> dcb4c2e18426be55|00000008--0696c823fa
        canonical_route = f"{dongle_id}|{url_slug}"

        # Try to verify the route exists by getting its files
        try:
            route_files = self.client.route_files(canonical_route)
            # If we get files, the route exists and is accessible
            if route_files and any(route_files.values()):
                return canonical_route
            else:
                # Route exists but has no files, still return it
                return canonical_route
        except Exception as e:
            # If direct route lookup fails, fall back to device segments search
            # but only as a last resort
            if "404" in str(e) or "not found" in str(e).lower():
                pass  # Continue to fallback
            else:
                raise ValueError(f"Error accessing route {canonical_route}: {e}") from e

        # Fallback: try to search device segments (original approach)
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=search_days)

        from_ms = int(start_time.timestamp() * 1000)
        to_ms = int(end_time.timestamp() * 1000)

        try:
            segments = self.client.device_segments(dongle_id, from_ms, to_ms)
        except Exception as e:
            raise ValueError(f"Failed to resolve connect URL {connect_url}: {e}") from e

        for segment in segments:
            segment_url = segment.get("url", "")
            if url_slug in segment_url:
                if "start_time_utc" in segment:
                    start_time_utc = datetime.fromisoformat(
                        segment["start_time_utc"].replace("Z", "+00:00")
                    )
                    route_timestamp = start_time_utc.strftime("%Y-%m-%d--%H-%M-%S")
                    canonical_route = f"{dongle_id}|{route_timestamp}"
                    return canonical_route

        raise ValueError(
            f"Couldn't resolve connect URL {connect_url}. "
            f"URL may not be public or route may not exist."
        )

    def resolve(self, input_str: str, search_days: int = 7) -> str:
        """
        Resolve input to canonical route name.

        Args:
            input_str: Canonical route or connect URL
            search_days: Search window for connect URLs

        Returns:
            Canonical route name
        """
        input_type, value = self.parse_input(input_str)

        if input_type == "canonical":
            return value
        elif input_type == "connect":
            return self.resolve_connect_url(input_str, search_days)
        else:
            raise ValueError(f"Unknown input type: {input_type}")
