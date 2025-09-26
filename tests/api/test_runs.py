"""Tests for runs endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from comma_tools.api.server import app

client = TestClient(app)


@pytest.fixture
def mock_engine():
    """Create mock execution engine."""
    engine = MagicMock()

    mock_response = MagicMock()
    mock_response.run_id = "test-run-123"
    mock_response.status = "queued"
    mock_response.tool_id = "cruise-control-analyzer"
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

    assert data["run_id"] == "test-run-123"
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
    mock_response = MagicMock()
    mock_response.dict.return_value = {
        "run_id": "test-run-123",
        "status": "queued",
        "tool_id": "test-tool",
        "created_at": "2024-12-19T10:30:00Z",
        "started_at": None,
        "completed_at": None,
        "params": {},
        "progress": None,
        "artifacts": [],
        "error": None,
    }
    mock_engine.get_run_status = AsyncMock(return_value=mock_response)

    with patch("comma_tools.api.runs.get_execution_engine", return_value=mock_engine):
        response = client.get("/v1/runs/test-run-123")

    assert response.status_code == 200
    data = response.json()

    assert data["run_id"] == "test-run-123"
    assert data["status"] == "queued"
    assert data["tool_id"] == "test-tool"


def test_get_run_status_not_found(mock_engine):
    """Test run status for non-existent run."""
    mock_engine.get_run_status.side_effect = KeyError("Run 'nonexistent' not found")

    with patch("comma_tools.api.runs.get_execution_engine", return_value=mock_engine):
        response = client.get("/v1/runs/nonexistent")

    assert response.status_code == 404
    assert "Run 'nonexistent' not found" in response.json()["detail"]


def test_get_run_logs_success(mock_engine):
    """Test successful run logs retrieval."""
    mock_response = MagicMock()
    mock_response.dict.return_value = {
        "run_id": "test-run-123",
        "status": "running",
        "tool_id": "test-tool",
        "created_at": "2024-12-19T10:30:00Z",
        "started_at": "2024-12-19T10:30:01Z",
        "completed_at": None,
        "params": {},
        "progress": 50,
        "artifacts": [],
        "error": None,
    }
    mock_engine.get_run_status = AsyncMock(return_value=mock_response)

    with patch("comma_tools.api.runs.get_execution_engine", return_value=mock_engine):
        response = client.get("/v1/runs/test-run-123/logs")

    assert response.status_code == 200
    data = response.json()

    assert "message" in data
    assert data["run_id"] == "test-run-123"


def test_get_run_logs_not_found(mock_engine):
    """Test run logs for non-existent run."""
    mock_engine.get_run_status.side_effect = KeyError("Run 'nonexistent' not found")

    with patch("comma_tools.api.runs.get_execution_engine", return_value=mock_engine):
        response = client.get("/v1/runs/nonexistent/logs")

    assert response.status_code == 404
    assert "Run 'nonexistent' not found" in response.json()["detail"]


def test_cancel_run_success(mock_engine):
    """Test successful run cancellation."""
    mock_engine.cancel_run.return_value = True

    with patch("comma_tools.api.runs.get_execution_engine", return_value=mock_engine):
        response = client.delete("/v1/runs/test-run-123")

    assert response.status_code == 200
    data = response.json()

    assert data["message"] == "Run cancelled"
    assert data["run_id"] == "test-run-123"


def test_cancel_run_not_found(mock_engine):
    """Test cancelling non-existent run."""
    mock_engine.cancel_run.return_value = False

    with patch("comma_tools.api.runs.get_execution_engine", return_value=mock_engine):
        response = client.delete("/v1/runs/nonexistent")

    assert response.status_code == 200
    data = response.json()

    assert data["message"] == "Run not found or already completed"
    assert data["run_id"] == "nonexistent"


def test_runs_endpoints_response_time():
    """Test runs endpoints response time."""
    import time

    mock_engine = MagicMock()
    mock_response = MagicMock()
    mock_response.dict.return_value = {
        "run_id": "test-run",
        "status": "queued",
        "tool_id": "test-tool",
        "created_at": "2024-12-19T10:30:00Z",
        "started_at": None,
        "completed_at": None,
        "params": {},
        "progress": None,
        "artifacts": [],
        "error": None,
    }
    mock_engine.get_run_status = AsyncMock(return_value=mock_response)

    with patch("comma_tools.api.runs.get_execution_engine", return_value=mock_engine):
        start_time = time.time()
        response = client.get("/v1/runs/test-run")
        end_time = time.time()

        response_time = (end_time - start_time) * 1000  # Convert to milliseconds

        assert response.status_code == 200
        assert response_time < 100, f"Status endpoint took {response_time:.2f}ms, should be < 100ms"
