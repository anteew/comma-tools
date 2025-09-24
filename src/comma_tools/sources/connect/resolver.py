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
        canonical_pattern = r'^([a-f0-9]{16})\|(\d{4}-\d{2}-\d{2}--\d{2}-\d{2}-\d{2})$'
        if re.match(canonical_pattern, input_str):
            return ('canonical', input_str)
        
        connect_pattern = r'https://connect\.comma\.ai/([a-f0-9]{16})/([a-f0-9]{8}--[a-f0-9]{10})'
        match = re.match(connect_pattern, input_str)
        if match:
            dongle_id, url_slug = match.groups()
            return ('connect', dongle_id)
        
        raise ValueError(
            f"Invalid input format: {input_str}\n"
            "Expected canonical route (dongle|YYYY-MM-DD--HH-MM-SS) "
            "or connect URL (https://connect.comma.ai/dongle/slug)"
        )
    
    def resolve_connect_url(self, connect_url: str, search_days: int = 7) -> str:
        """
        Resolve connect URL to canonical route name.
        
        Args:
            connect_url: Connect URL to resolve
            search_days: Number of days to search backwards
            
        Returns:
            Canonical route name
            
        Raises:
            ValueError: If URL cannot be resolved within search window
        """
        connect_pattern = r'https://connect\.comma\.ai/([a-f0-9]{16})/([a-f0-9]{8}--[a-f0-9]{10})'
        match = re.match(connect_pattern, connect_url)
        if not match:
            raise ValueError(f"Invalid connect URL format: {connect_url}")
        
        dongle_id, url_slug = match.groups()
        
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=search_days)
        
        from_ms = int(start_time.timestamp() * 1000)
        to_ms = int(end_time.timestamp() * 1000)
        
        try:
            segments = self.client.device_segments(dongle_id, from_ms, to_ms)
        except Exception as e:
            raise ValueError(
                f"Failed to search device segments for {dongle_id}: {e}"
            ) from e
        
        for segment in segments:
            segment_url = segment.get('url', '')
            if url_slug in segment_url:
                if 'start_time_utc' in segment:
                    start_time_utc = datetime.fromisoformat(
                        segment['start_time_utc'].replace('Z', '+00:00')
                    )
                    route_timestamp = start_time_utc.strftime('%Y-%m-%d--%H-%M-%S')
                    canonical_route = f"{dongle_id}|{route_timestamp}"
                    return canonical_route
        
        raise ValueError(
            f"Couldn't map Connect URL within the last {search_days} days. "
            f"Pass the canonical route (dongle|YYYY-MM-DD--HH-MM-SS) "
            f"or widen the search window with --days."
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
        
        if input_type == 'canonical':
            return value
        elif input_type == 'connect':
            return self.resolve_connect_url(input_str, search_days)
        else:
            raise ValueError(f"Unknown input type: {input_type}")
