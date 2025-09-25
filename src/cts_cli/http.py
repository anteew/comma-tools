"""
HTTP client for CTS-Lite API communication.

Provides authenticated HTTP requests with rate limiting, retries,
and streaming support for SSE and WebSocket connections.
"""

import time
import json
from typing import Dict, Any, Optional, Iterator, Union
from urllib.parse import urljoin
import httpx

from .config import Config


class HTTPClient:
    """HTTP client for CTS-Lite API with authentication and error handling."""

    def __init__(self, config: Config):
        """Initialize HTTP client with configuration."""
        self.config = config
        self.base_url = config.url.rstrip("/")

        verify = not config.no_verify
        self.client = httpx.Client(
            timeout=config.timeout, verify=verify, headers={"User-Agent": "cts-cli/0.1.0"}
        )

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with authentication."""
        headers = {}
        if self.config.api_key:
            headers["Authorization"] = f"JWT {self.config.api_key}"
        return headers

    def _make_request(self, method: str, endpoint: str, **kwargs) -> httpx.Response:
        """Make HTTP request with error handling and retries."""
        url = urljoin(self.base_url + "/", endpoint.lstrip("/"))
        headers = self._get_headers()

        max_retries = 3
        backoff_factor = 1.0

        for attempt in range(max_retries):
            try:
                response = self.client.request(method, url, headers=headers, **kwargs)

                if response.status_code == 429:
                    if attempt < max_retries - 1:
                        wait_time = backoff_factor * (2**attempt)
                        time.sleep(wait_time)
                        continue

                if 500 <= response.status_code < 600:
                    if attempt < max_retries - 1:
                        wait_time = backoff_factor * (2**attempt)
                        time.sleep(wait_time)
                        continue

                return response

            except httpx.RequestError as e:
                if attempt < max_retries - 1:
                    wait_time = backoff_factor * (2**attempt)
                    time.sleep(wait_time)
                    continue
                raise

        return response

    def get(self, endpoint: str, **kwargs) -> httpx.Response:
        """Make GET request."""
        return self._make_request("GET", endpoint, **kwargs)

    def post(self, endpoint: str, **kwargs) -> httpx.Response:
        """Make POST request."""
        return self._make_request("POST", endpoint, **kwargs)

    def put(self, endpoint: str, **kwargs) -> httpx.Response:
        """Make PUT request."""
        return self._make_request("PUT", endpoint, **kwargs)

    def delete(self, endpoint: str, **kwargs) -> httpx.Response:
        """Make DELETE request."""
        return self._make_request("DELETE", endpoint, **kwargs)

    def get_json(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make GET request and return JSON response."""
        response = self.get(endpoint, **kwargs)
        response.raise_for_status()
        return response.json()

    def post_json(self, endpoint: str, data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Make POST request with JSON data and return JSON response."""
        response = self.post(endpoint, json=data, **kwargs)
        response.raise_for_status()
        return response.json()

    def stream_sse(self, endpoint: str, **kwargs) -> Iterator[Dict[str, Any]]:
        """Stream Server-Sent Events from endpoint."""
        url = urljoin(self.base_url + "/", endpoint.lstrip("/"))
        headers = self._get_headers()
        headers["Accept"] = "text/event-stream"

        with httpx.stream("GET", url, headers=headers, timeout=None, **kwargs) as response:
            response.raise_for_status()

            for line in response.iter_lines():
                line = line.strip()
                if not line or line.startswith(":"):
                    continue

                if line.startswith("data: "):
                    data = line[6:]  # Remove "data: " prefix
                    if data == "[DONE]":
                        break

                    try:
                        yield json.loads(data)
                    except json.JSONDecodeError:
                        continue

    def download_file(self, url: str, output_path: str, force: bool = False) -> None:
        """Download file from URL to local path."""
        from pathlib import Path

        output_file = Path(output_path)

        if output_file.exists() and not force:
            raise FileExistsError(f"File {output_path} already exists. Use --force to overwrite.")

        output_file.parent.mkdir(parents=True, exist_ok=True)

        with httpx.stream("GET", url, timeout=None) as response:
            response.raise_for_status()

            with open(output_file, "wb") as f:
                for chunk in response.iter_bytes():
                    f.write(chunk)

    def close(self) -> None:
        """Close HTTP client."""
        self.client.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
