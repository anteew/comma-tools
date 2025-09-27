"""Tests for runs endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from comma_tools.api.runs import get_execution_engine
from comma_tools.api.server import app

client = TestClient(app)


@pytest.fixture
def mock_engine():
    """Create mock execution engine."""
    from datetime import datetime

    from comma_tools.api.models import RunResponse, RunStatus

    engine = MagicMock()

    mock_response = RunResponse(
        run_id="test-run-123",
        status=RunStatus.QUEUED,
        tool_id="cruise-control-analyzer",
        created_at=datetime.fromisoformat("2024-12-19T10:30:00+00:00"),
        started_at=None,
        completed_at=None,
        params={"speed_min": 50.0},
        progress=None,
        artifacts=[],
        error=None,
    )

    engine.start_run = AsyncMock(return_value=mock_response)
    engine.get_run_status = AsyncMock(return_value=mock_response)
    engine.cancel_run = MagicMock(return_value=True)

    return engine


def test_start_run_success(mock_engine):
    """Test successful run start."""
    mock_response = MagicMock()
    mock_response.dict.return_value = {
        "run_id": "test-run-123",
        "status": "queued",
        "tool_id": "cruise-control-analyzer",
        "created_at": "2024-12-19T10:30:00Z",
        "started_at": None,
        "completed_at": None,
        "params": {"speed_min": 50.0},
        "progress": None,
        "artifacts": [],
        "error": None,
    }
    mock_engine.start_run = AsyncMock(return_value=mock_response)

    with patch("comma_tools.api.runs.get_execution_engine", return_value=mock_engine):
        response = client.post(
            "/v1/runs",
            json={
                "tool_id": "cruise-control-analyzer",
                "params": {"speed_min": 50.0},
                "input": {"type": "path", "value": "/path/to/test.zst"},
            },
        )

    assert response.status_code == 200
    data = response.json()

    assert "run_id" in data
    assert data["status"] == "queued"
    assert data["tool_id"] == "cruise-control-analyzer"


def test_start_run_tool_not_found(mock_engine):
    """Test run start with non-existent tool."""
    mock_engine.start_run.side_effect = KeyError("Tool 'nonexistent' not found")

    with patch("comma_tools.api.runs.get_execution_engine", return_value=mock_engine):
        response = client.post("/v1/runs", json={"tool_id": "nonexistent", "params": {}})

    assert response.status_code == 404
    assert "Tool 'nonexistent' not found" in response.json()["detail"]


def test_start_run_validation_error(mock_engine):
    """Test run start with validation error."""
    mock_engine.start_run.side_effect = ValueError("Required parameter 'log_file' missing")

    with patch("comma_tools.api.runs.get_execution_engine", return_value=mock_engine):
        response = client.post(
            "/v1/runs", json={"tool_id": "cruise-control-analyzer", "params": {}}
        )

    assert response.status_code == 400
    assert "Required parameter 'log_file' missing" in response.json()["detail"]


def test_start_run_invalid_json():
    """Test run start with invalid JSON."""
    response = client.post("/v1/runs", json={"invalid": "request"})

    assert response.status_code == 422  # Validation error


def test_get_run_status_success(mock_engine):
    """Test successful run status retrieval."""
    app.dependency_overrides[get_execution_engine] = lambda: mock_engine
    try:
        response = client.get("/v1/runs/test-run-123")

        assert response.status_code == 200
        data = response.json()

        assert data["run_id"] == "test-run-123"
        assert data["status"] == "queued"
        assert data["tool_id"] == "cruise-control-analyzer"
    finally:
        app.dependency_overrides.clear()


def test_get_run_status_not_found(mock_engine):
    """Test run status for non-existent run."""
    mock_engine.get_run_status.side_effect = KeyError("Run 'nonexistent' not found")

    with patch("comma_tools.api.runs.get_execution_engine", return_value=mock_engine):
        response = client.get("/v1/runs/nonexistent")

    assert response.status_code == 404
    assert "Run 'nonexistent' not found" in response.json()["detail"]


def test_get_run_logs_success(mock_engine):
    """Test successful run logs retrieval."""
    from comma_tools.api.logs import get_log_streamer

    # Create mock log streamer with controlled streaming behavior
    mock_log_streamer = MagicMock()

    async def fake_stream_logs(run_id):
        """Fake streaming that yields a few logs and then stops."""
        yield '{"level": "info", "message": "Test log 1", "timestamp": "2024-01-01T00:00:00Z"}'
        yield '{"level": "info", "message": "Test log 2", "timestamp": "2024-01-01T00:00:01Z"}'
        # No infinite loop - just returns these two logs

    mock_log_streamer.stream_logs = fake_stream_logs

    app.dependency_overrides[get_execution_engine] = lambda: mock_engine
    app.dependency_overrides[get_log_streamer] = lambda: mock_log_streamer
    try:
        response = client.get("/v1/runs/test-run-123/logs")

        assert response.status_code == 200
        # For streaming responses, we should check the content type
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

        # Read the streaming content
        content = response.text
        assert "Test log 1" in content
        assert "Test log 2" in content
    finally:
        app.dependency_overrides.clear()


def test_get_run_logs_not_found(mock_engine):
    """Test run logs for non-existent run."""
    from comma_tools.api.logs import get_log_streamer

    # Mock log streamer that returns empty stream for non-existent runs
    mock_log_streamer = MagicMock()

    async def fake_stream_logs(run_id):
        """Returns empty stream for non-existent runs."""
        # Just return immediately - no logs for non-existent run
        return
        yield  # unreachable, but keeps it as generator

    mock_log_streamer.stream_logs = fake_stream_logs

    app.dependency_overrides[get_execution_engine] = lambda: mock_engine
    app.dependency_overrides[get_log_streamer] = lambda: mock_log_streamer
    try:
        response = client.get("/v1/runs/nonexistent/logs")

        # Current implementation returns 200 with empty stream for non-existent runs
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

        # Should have empty or minimal content since run doesn't exist
        content = response.text
        # The stream should be short/empty since we return immediately
        assert len(content) < 50  # Minimal content for non-existent run
    finally:
        app.dependency_overrides.clear()


def test_cancel_run_success(mock_engine):
    """Test successful run cancellation."""
    app.dependency_overrides[get_execution_engine] = lambda: mock_engine
    try:
        response = client.delete("/v1/runs/test-run-123")

        assert response.status_code == 200
        data = response.json()

        assert data["message"] == "Run cancelled"
        assert data["run_id"] == "test-run-123"
    finally:
        app.dependency_overrides.clear()


def test_cancel_run_not_found(mock_engine):
    """Test cancelling non-existent run."""
    mock_engine.cancel_run.return_value = False

    with patch("comma_tools.api.runs.get_execution_engine", return_value=mock_engine):
        response = client.delete("/v1/runs/nonexistent")

    assert response.status_code == 200
    data = response.json()

    assert data["message"] == "Run not found or already completed"
    assert data["run_id"] == "nonexistent"


def test_runs_endpoints_response_time(mock_engine):
    """Test runs endpoints response time."""
    import time

    app.dependency_overrides[get_execution_engine] = lambda: mock_engine
    try:
        start_time = time.time()
        response = client.get("/v1/runs/test-run-123")
        end_time = time.time()

        response_time = (end_time - start_time) * 1000  # Convert to milliseconds

        assert response.status_code == 200
        assert response_time < 100, f"Status endpoint took {response_time:.2f}ms, should be < 100ms"
    finally:
        app.dependency_overrides.clear()
