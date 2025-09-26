"""Integration tests for runs endpoints with real analyzers."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from comma_tools.api.server import app

client = TestClient(app)


@pytest.fixture
def temp_log_file():
    """Create temporary log file for testing."""
    with tempfile.NamedTemporaryFile(suffix=".zst", delete=False) as f:
        f.write(b"test log data")
        temp_path = f.name

    yield temp_path

    Path(temp_path).unlink(missing_ok=True)


@pytest.fixture
def temp_csv_file():
    """Create temporary CSV file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("window,segment,timestamp,address,bus,data_hex\n")
        f.write("1,pre,0.0,0x027,0,0000000000000000\n")
        f.write("1,window,1.0,0x027,0,0000000000000001\n")
        f.write("1,post,2.0,0x027,0,0000000000000000\n")
        temp_path = f.name

    yield temp_path

    Path(temp_path).unlink(missing_ok=True)


def test_cruise_control_analyzer_integration(temp_log_file):
    """Test cruise control analyzer integration with mocked dependencies."""
    with patch(
        "comma_tools.analyzers.cruise_control_analyzer.CruiseControlAnalyzer"
    ) as mock_analyzer_class:
        mock_analyzer = mock_analyzer_class.return_value
        mock_analyzer.run_analysis.return_value = True

        response = client.post(
            "/v1/runs",
            json={
                "tool_id": "cruise-control-analyzer",
                "params": {"speed_min": 50.0, "speed_max": 60.0},
                "input": {"type": "path", "value": temp_log_file},
            },
        )

        assert response.status_code == 200
        data = response.json()

        run_id = data["run_id"]
        assert data["status"] == "queued"
        assert data["tool_id"] == "cruise-control-analyzer"

        status_response = client.get(f"/v1/runs/{run_id}")
        assert status_response.status_code == 200

        status_data = status_response.json()
        assert status_data["status"] in ["queued", "running", "completed"]


def test_rlog_to_csv_integration(temp_log_file):
    """Test rlog to CSV integration with mocked dependencies."""
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as output_file:
        output_path = output_file.name

    try:
        with patch("comma_tools.analyzers.rlog_to_csv.main") as mock_main:
            response = client.post(
                "/v1/runs",
                json={
                    "tool_id": "rlog-to-csv",
                    "params": {"rlog": temp_log_file, "out": output_path},
                },
            )

            assert response.status_code == 200
            data = response.json()

            run_id = data["run_id"]
            assert data["status"] == "queued"
            assert data["tool_id"] == "rlog-to-csv"

            status_response = client.get(f"/v1/runs/{run_id}")
            assert status_response.status_code == 200
    finally:
        Path(output_path).unlink(missing_ok=True)


def test_can_bitwatch_integration(temp_csv_file):
    """Test CAN bitwatch integration."""
    with patch("comma_tools.analyzers.can_bitwatch.main") as mock_main:
        response = client.post(
            "/v1/runs",
            json={
                "tool_id": "can-bitwatch",
                "params": {
                    "csv": temp_csv_file,
                    "output_prefix": "test_analysis",
                    "watch": ["0x027:B4b5"],
                },
            },
        )

        assert response.status_code == 200
        data = response.json()

        run_id = data["run_id"]
        assert data["status"] == "queued"
        assert data["tool_id"] == "can-bitwatch"

        status_response = client.get(f"/v1/runs/{run_id}")
        assert status_response.status_code == 200


def test_run_lifecycle_transitions():
    """Test complete run lifecycle with status transitions."""
    with patch(
        "comma_tools.analyzers.cruise_control_analyzer.CruiseControlAnalyzer"
    ) as mock_analyzer_class:
        mock_analyzer = mock_analyzer_class.return_value
        mock_analyzer.run_analysis.return_value = True

        response = client.post(
            "/v1/runs",
            json={
                "tool_id": "cruise-control-analyzer",
                "params": {"speed_min": 50.0},
                "input": {"type": "path", "value": "/fake/path.zst"},
            },
        )

        assert response.status_code == 200
        run_id = response.json()["run_id"]

        status_response = client.get(f"/v1/runs/{run_id}")
        assert status_response.status_code == 200
        initial_status = status_response.json()["status"]
        assert initial_status in ["queued", "running", "completed"]

        logs_response = client.get(f"/v1/runs/{run_id}/logs")
        assert logs_response.status_code == 200
        assert "message" in logs_response.json()


def test_error_handling_invalid_file():
    """Test error handling with invalid file path."""
    response = client.post(
        "/v1/runs",
        json={
            "tool_id": "cruise-control-analyzer",
            "params": {},
            "input": {"type": "path", "value": "/nonexistent/file.zst"},
        },
    )

    assert response.status_code == 200  # Should start but may fail during execution
    run_id = response.json()["run_id"]

    status_response = client.get(f"/v1/runs/{run_id}")
    assert status_response.status_code == 200


def test_parameter_validation_errors():
    """Test parameter validation error scenarios."""
    response = client.post(
        "/v1/runs", json={"tool_id": "rlog-to-csv", "params": {"out": "/tmp/output.csv"}}
    )

    assert response.status_code == 400
    assert "Required parameter" in response.json()["detail"]


def test_invalid_tool_id():
    """Test error handling for invalid tool ID."""
    response = client.post("/v1/runs", json={"tool_id": "nonexistent-tool", "params": {}})

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_run_cancellation():
    """Test run cancellation functionality."""
    with patch(
        "comma_tools.analyzers.cruise_control_analyzer.CruiseControlAnalyzer"
    ) as mock_analyzer_class:
        mock_analyzer = mock_analyzer_class.return_value
        mock_analyzer.run_analysis.return_value = True

        response = client.post(
            "/v1/runs",
            json={
                "tool_id": "cruise-control-analyzer",
                "params": {"speed_min": 50.0},
                "input": {"type": "path", "value": "/fake/path.zst"},
            },
        )

        assert response.status_code == 200
        run_id = response.json()["run_id"]

        cancel_response = client.delete(f"/v1/runs/{run_id}")
        assert cancel_response.status_code == 200

        cancel_data = cancel_response.json()
        assert (
            "cancelled" in cancel_data["message"].lower()
            or "completed" in cancel_data["message"].lower()
        )
