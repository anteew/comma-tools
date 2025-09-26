"""Log streaming and retrieval endpoints."""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import AsyncGenerator, Dict, List, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from .models import LogEntry, LogsResponse

logger = logging.getLogger(__name__)
router = APIRouter()


class LogStreamer:
    """Manages log streaming and storage."""

    def __init__(self):
        """Initialize log streamer."""
        self.active_streams: Dict[str, asyncio.Queue] = {}
        self.log_storage: Dict[str, List[LogEntry]] = {}

    async def capture_tool_output(self, run_id: str, process) -> None:
        """Capture stdout/stderr from tool execution.

        Args:
            run_id: Run identifier
            process: Process to capture output from
        """
        pass

    async def stream_logs(self, run_id: str) -> AsyncGenerator[str, None]:
        """Stream logs via Server-Sent Events.

        Args:
            run_id: Run identifier

        Yields:
            JSON-encoded log entries
        """
        if run_id not in self.active_streams:
            self.active_streams[run_id] = asyncio.Queue()

        queue = self.active_streams[run_id]

        if run_id in self.log_storage:
            for log_entry in self.log_storage[run_id]:
                yield json.dumps(log_entry.model_dump(), default=str)

        try:
            while True:
                log_entry = await queue.get()
                if log_entry is None:
                    break
                yield json.dumps(log_entry.model_dump(), default=str)
        finally:
            if run_id in self.active_streams:
                del self.active_streams[run_id]

    def add_log_entry(self, run_id: str, level: str, message: str, source: str = "tool") -> None:
        """Add a log entry for a run.

        Args:
            run_id: Run identifier
            level: Log level
            message: Log message
            source: Log source
        """
        entry = LogEntry(
            timestamp=datetime.now(timezone.utc), level=level, message=message, source=source
        )

        if run_id not in self.log_storage:
            self.log_storage[run_id] = []
        self.log_storage[run_id].append(entry)

        if run_id in self.active_streams:
            try:
                self.active_streams[run_id].put_nowait(entry)
            except asyncio.QueueFull:
                logger.warning(f"Log queue full for run {run_id}")

    def get_logs(self, run_id: str, limit: int = 100) -> List[LogEntry]:
        """Get persisted logs for a run.

        Args:
            run_id: Run identifier
            limit: Maximum number of logs to return

        Returns:
            List of log entries
        """
        if run_id not in self.log_storage:
            return []
        return self.log_storage[run_id][-limit:]


_log_streamer: Optional[LogStreamer] = None


def get_log_streamer() -> LogStreamer:
    """Get log streamer instance."""
    global _log_streamer
    if _log_streamer is None:
        _log_streamer = LogStreamer()
    return _log_streamer


@router.get("/runs/{run_id}/logs", response_model=LogsResponse)
async def get_run_logs(
    run_id: str, limit: int = 100, streamer: LogStreamer = Depends(get_log_streamer)
) -> LogsResponse:
    """Get run logs.

    Args:
        run_id: Run identifier
        limit: Maximum number of logs to return
        streamer: Log streamer dependency

    Returns:
        Logs response with log entries
    """
    logs = streamer.get_logs(run_id, limit)
    return LogsResponse(run_id=run_id, logs=logs, has_more=len(logs) >= limit)


@router.get("/runs/{run_id}/logs/stream")
async def stream_run_logs(
    run_id: str, streamer: LogStreamer = Depends(get_log_streamer)
) -> StreamingResponse:
    """Stream run logs using Server-Sent Events.

    Args:
        run_id: Run identifier
        streamer: Log streamer dependency

    Returns:
        Streaming response with SSE content
    """

    async def generate():
        async for log_line in streamer.stream_logs(run_id):
            yield f"data: {log_line}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
