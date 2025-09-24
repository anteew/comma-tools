"""
Comma Connect API client.

Provides methods for interacting with the comma API endpoints including
route info, segments, and file listings with proper rate limiting.
"""

import json
import time
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from .auth import load_auth, redact_token


class RateLimiter:
    """Token bucket rate limiter for API calls."""
    
    def __init__(self, max_calls: int = 5, window_seconds: int = 60):
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self.calls: List[float] = []
    
    def can_make_call(self) -> bool:
        """Check if a call can be made without exceeding rate limit."""
        now = time.time()
        self.calls = [call_time for call_time in self.calls 
                     if now - call_time < self.window_seconds]
        return len(self.calls) < self.max_calls
    
    def wait_if_needed(self) -> None:
        """Wait if necessary to respect rate limit."""
        while not self.can_make_call():
            time.sleep(1)
    
    def record_call(self) -> None:
        """Record that a call was made."""
        self.calls.append(time.time())


class ConnectClient:
    """
    Client for comma connect API.
    
    Handles authentication, rate limiting, and API calls with proper
    error handling and retries.
    """
    
    def __init__(self, base_url: str = "https://api.comma.ai"):
        self.base_url = base_url.rstrip('/')
        self.rate_limiter = RateLimiter(max_calls=5, window_seconds=60)
        self._jwt_token: Optional[str] = None
    
    def _get_jwt_token(self) -> str:
        """Get JWT token, loading if necessary."""
        if self._jwt_token is None:
            self._jwt_token = load_auth()
        assert self._jwt_token is not None
        return self._jwt_token
    
    def _make_request(self, endpoint: str, method: str = "GET") -> Dict[str, Any]:
        """
        Make authenticated API request with rate limiting.
        
        Args:
            endpoint: API endpoint path
            method: HTTP method
            
        Returns:
            Parsed JSON response
            
        Raises:
            HTTPError: For HTTP error responses
            URLError: For network errors
            ValueError: For invalid JSON responses
        """
        self.rate_limiter.wait_if_needed()
        
        url = urljoin(self.base_url + "/", endpoint.lstrip('/'))
        jwt_token = self._get_jwt_token()
        
        request = Request(url, method=method)
        request.add_header("Authorization", f"JWT {jwt_token}")
        request.add_header("User-Agent", "comma-tools-connect-downloader/1.0")
        
        try:
            with urlopen(request, timeout=30) as response:
                self.rate_limiter.record_call()
                data = response.read().decode('utf-8')
                return json.loads(data)
        except HTTPError as e:
            if e.code == 401:
                token_redacted = redact_token(jwt_token)
                raise HTTPError(
                    e.url, e.code, 
                    f"Auth failed. Verify token {token_redacted} at jwt.comma.ai "
                    f"and permissions for this device/route.", 
                    e.headers, e.fp
                ) from e
            elif e.code == 404:
                raise HTTPError(
                    e.url, e.code,
                    f"Route not found or you lack access.",
                    e.headers, e.fp
                ) from e
            elif e.code == 429:
                time.sleep(60)
                return self._make_request(endpoint, method)
            else:
                raise
        except URLError as e:
            raise URLError(f"Network error accessing comma API: {e}") from e
    
    def route_info(self, route_name: str) -> Dict[str, Any]:
        """
        Get route metadata.
        
        Args:
            route_name: Canonical route name (dongle|YYYY-MM-DD--HH-MM-SS)
            
        Returns:
            Route metadata dictionary
        """
        return self._make_request(f"/v1/route/{route_name}")
    
    def route_segments(self, route_name: str) -> List[Dict[str, Any]]:
        """
        Get route segments list.
        
        Args:
            route_name: Canonical route name
            
        Returns:
            List of segment dictionaries
        """
        response = self._make_request(f"/v1/route/{route_name}/segments")
        return response.get("segments", [])
    
    def route_files(self, route_name: str) -> Dict[str, List[str]]:
        """
        Get signed URLs for route files.
        
        Args:
            route_name: Canonical route name
            
        Returns:
            Dictionary mapping file types to lists of signed URLs
        """
        return self._make_request(f"/v1/route/{route_name}/files")
    
    def device_segments(self, dongle_id: str, from_ms: int, 
                       to_ms: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get device segments within time range.
        
        Args:
            dongle_id: Device dongle ID
            from_ms: Start timestamp in milliseconds
            to_ms: End timestamp in milliseconds (optional)
            
        Returns:
            List of segment dictionaries with url fields
        """
        endpoint = f"/v1/device/{dongle_id}/segments?from={from_ms}"
        if to_ms is not None:
            endpoint += f"&to={to_ms}"
        
        response = self._make_request(endpoint)
        return response.get("segments", [])
