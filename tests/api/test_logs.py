"""Tests for log streaming functionality."""

import asyncio

import pytest

from comma_tools.api.logs import LogStreamer


@pytest.fixture
def log_streamer():
    """Create log streamer instance."""
    return LogStreamer()


def test_add_log_entry(log_streamer):
    """Test adding log entries."""
    log_streamer.add_log_entry("test-run", "INFO", "Test message")

    logs = log_streamer.get_logs("test-run")
    assert len(logs) == 1
    assert logs[0].level == "INFO"
    assert logs[0].message == "Test message"
    assert logs[0].source == "tool"


def test_get_logs_with_limit(log_streamer):
    """Test getting logs with limit."""
    for i in range(10):
        log_streamer.add_log_entry("test-run", "INFO", f"Message {i}")

    logs = log_streamer.get_logs("test-run", limit=5)
    assert len(logs) == 5
    assert logs[-1].message == "Message 9"


def test_get_logs_empty_run(log_streamer):
    """Test getting logs for run with no logs."""
    logs = log_streamer.get_logs("nonexistent-run")
    assert len(logs) == 0


@pytest.mark.asyncio
async def test_stream_logs(log_streamer):
    """Test log streaming."""
    log_streamer.add_log_entry("test-run", "INFO", "Initial message")

    stream_gen = log_streamer.stream_logs("test-run")

    first_log = await stream_gen.__anext__()
    assert "Initial message" in first_log

    log_streamer.add_log_entry("test-run", "DEBUG", "New message")

    if "test-run" in log_streamer.active_streams:
        await log_streamer.active_streams["test-run"].put(None)


def test_add_log_entry_with_custom_source(log_streamer):
    """Test adding log entry with custom source."""
    log_streamer.add_log_entry("test-run", "ERROR", "Error message", source="system")

    logs = log_streamer.get_logs("test-run")
    assert len(logs) == 1
    assert logs[0].source == "system"
