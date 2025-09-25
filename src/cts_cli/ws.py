"""
WebSocket streaming support for monitor data.

Provides WebSocket client for streaming monitor data from
CTS-Lite API with connection management and cleanup.
"""

import asyncio
import json
from typing import Any, AsyncIterator, Dict, Iterator, Optional, Union

import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

from .config import Config


class WebSocketStream:
    """WebSocket stream for monitor data."""

    def __init__(self, config: Config, monitor_id: str):
        """Initialize WebSocket stream."""
        self.config = config
        self.monitor_id = monitor_id
        self.ws_url = self._build_ws_url()

    def _build_ws_url(self) -> str:
        """Build WebSocket URL from HTTP URL."""
        base_url = self.config.url
        if base_url.startswith("http://"):
            ws_url = base_url.replace("http://", "ws://", 1)
        elif base_url.startswith("https://"):
            ws_url = base_url.replace("https://", "wss://", 1)
        else:
            ws_url = f"ws://{base_url}"

        return f"{ws_url}/v1/monitors/{self.monitor_id}/stream"

    def _get_headers(self) -> Dict[str, str]:
        """Get WebSocket headers with authentication."""
        headers = {}
        if self.config.api_key:
            headers["Authorization"] = f"JWT {self.config.api_key}"
        return headers

    async def stream_async(self, raw: bool = False) -> AsyncIterator[Union[str, Dict[str, Any]]]:
        """Stream monitor data asynchronously."""
        headers = self._get_headers()

        try:
            async with websockets.connect(
                self.ws_url, extra_headers=headers, ping_interval=30, ping_timeout=10
            ) as websocket:
                async for message in websocket:
                    if raw:
                        yield str(message)
                    else:
                        try:
                            data = json.loads(str(message))
                            yield data
                        except json.JSONDecodeError:
                            continue

        except (ConnectionClosed, WebSocketException) as e:
            raise ConnectionError(f"WebSocket connection failed: {e}")

    def stream(self, raw: bool = False) -> Iterator[Union[str, Dict[str, Any]]]:
        """Stream monitor data synchronously."""

        async def _async_wrapper():
            results = []
            async for item in self.stream_async(raw=raw):
                results.append(item)
            return results

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        try:
            results = loop.run_until_complete(_async_wrapper())
            for item in results:
                yield item
        finally:
            if loop.is_running():
                pass
            else:
                loop.close()


def format_monitor_event(event: Union[str, Dict[str, Any]], ndjson: bool = False) -> str:
    """Format monitor event for display."""
    if isinstance(event, str):
        return event

    if ndjson:
        return json.dumps(event)

    timestamp = event.get("timestamp", "")
    event_type = event.get("type", "data")
    data = event.get("data", event)

    if timestamp:
        return f"[{timestamp}] {event_type}: {json.dumps(data, indent=2)}"
    else:
        return f"{event_type}: {json.dumps(data, indent=2)}"


def stream_monitor(
    config: Config, monitor_id: str, raw: bool = False, ndjson: bool = False
) -> Iterator[str]:
    """Stream monitor data with formatting."""
    ws_stream = WebSocketStream(config, monitor_id)

    for event in ws_stream.stream(raw=raw):
        if raw:
            yield str(event)
        else:
            yield format_monitor_event(event, ndjson=ndjson)
