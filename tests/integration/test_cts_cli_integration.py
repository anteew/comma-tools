"""
Integration tests for CTS CLI client.

Tests requiring mock server responses or actual CTS-Lite server
for end-to-end validation of CLI functionality.
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from cts_cli.config import Config
from cts_cli.http import HTTPClient
from cts_cli.main import app
from cts_cli.render import Renderer


@pytest.fixture
def mock_http_client():
    """Create mock HTTP client for testing."""
    client = Mock(spec=HTTPClient)
    client.config = Config()
    return client


@pytest.fixture
def temp_file():
    """Create temporary file for upload tests."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        f.write("test content")
        temp_path = f.name

    yield temp_path

    if os.path.exists(temp_path):
        os.unlink(temp_path)


class TestPingCommand:
    """Test ping command functionality."""

    def test_ping_success(self, mock_http_client):
        """Test successful ping command."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "status": "healthy",
            "version": "1.0.0",
            "uptime": "2h 30m",
        }
        mock_response.raise_for_status.return_value = None
        mock_http_client.get.return_value = mock_response

        renderer = Renderer()

        from cts_cli.commands.cap import ping_command

        result = ping_command(mock_http_client, renderer)

        assert result == 0
        mock_http_client.get.assert_called_once_with("/v1/health")

    def test_ping_failure(self, mock_http_client):
        """Test ping command with server error."""
        mock_http_client.get.side_effect = Exception("Connection failed")

        renderer = Renderer()

        from cts_cli.commands.cap import ping_command

        result = ping_command(mock_http_client, renderer)

        assert result == 2


class TestCapabilitiesCommand:
    """Test capabilities command functionality."""

    def test_capabilities_success(self, mock_http_client):
        """Test successful capabilities command."""
        mock_capabilities = {
            "api_version": "1.0",
            "tools": [
                {
                    "id": "cruise-control-analyzer",
                    "name": "Cruise Control Analyzer",
                    "description": "Analyze cruise control signals",
                    "version": "0.8.0",
                }
            ],
            "monitors": [
                {
                    "id": "hybrid_rx_trace",
                    "name": "Hybrid RX Trace",
                    "description": "Monitor hybrid RX signals",
                }
            ],
            "features": ["streaming", "uploads"],
        }

        mock_http_client.get_json.return_value = mock_capabilities

        renderer = Renderer()

        from cts_cli.commands.cap import capabilities_command

        result = capabilities_command(mock_http_client, renderer)

        assert result == 0
        mock_http_client.get_json.assert_called_once_with("/v1/capabilities")


class TestRunCommand:
    """Test run command functionality."""

    def test_run_with_parameters(self, mock_http_client):
        """Test run command with parameters."""
        mock_http_client.post_json.return_value = {"run_id": "test-run-123", "status": "started"}

        renderer = Renderer()

        from cts_cli.commands.run import run_command

        result = run_command(
            tool_id="cruise-control-analyzer",
            params=["speed_min=50", "speed_max=60", "enabled=true"],
            http_client=mock_http_client,
            renderer=renderer,
        )

        assert result == 0

        call_args = mock_http_client.post_json.call_args
        assert call_args[0][0] == "/v1/runs"

        request_data = call_args[0][1]
        assert request_data["tool_id"] == "cruise-control-analyzer"
        assert request_data["params"] == {"speed_min": 50, "speed_max": 60, "enabled": True}

    def test_run_with_file_upload(self, mock_http_client, temp_file):
        """Test run command with file upload."""
        mock_http_client.post_json.side_effect = [
            {"upload_id": "upload-123", "upload_url": "https://example.com/upload"},
            {"run_id": "test-run-123", "status": "started"},
        ]

        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_http_client.put.return_value = mock_response
        mock_http_client.post.return_value = mock_response

        renderer = Renderer()

        from cts_cli.commands.run import run_command

        result = run_command(
            tool_id="rlog-to-csv",
            params=[],
            upload=temp_file,
            http_client=mock_http_client,
            renderer=renderer,
        )

        assert result == 0


class TestLogsCommand:
    """Test logs command functionality."""

    def test_logs_streaming(self, mock_http_client):
        """Test logs streaming command."""
        mock_events = [
            {"timestamp": "2024-01-01T12:00:00Z", "level": "INFO", "message": "Starting analysis"},
            {"timestamp": "2024-01-01T12:00:01Z", "level": "INFO", "message": "Analysis complete"},
        ]

        with patch("cts_cli.commands.logs.stream_logs") as mock_stream:
            mock_stream.return_value = iter(
                [
                    "[2024-01-01T12:00:00Z] INFO: Starting analysis",
                    "[2024-01-01T12:00:01Z] INFO: Analysis complete",
                ]
            )

            renderer = Renderer()

            from cts_cli.commands.logs import logs_command

            result = logs_command(
                run_id="test-run-123", follow=False, http_client=mock_http_client, renderer=renderer
            )

            assert result == 0
            mock_stream.assert_called_once()


class TestArtifactsCommand:
    """Test artifacts command functionality."""

    def test_list_artifacts(self, mock_http_client):
        """Test list artifacts command."""
        mock_artifacts = [
            {
                "id": "artifact-1",
                "filename": "report.html",
                "size": 1024,
                "type": "html",
                "created_at": "2024-01-01T12:00:00Z",
            },
            {
                "id": "artifact-2",
                "filename": "data.csv",
                "size": 2048,
                "type": "csv",
                "created_at": "2024-01-01T12:00:01Z",
            },
        ]

        mock_http_client.get_json.return_value = mock_artifacts

        renderer = Renderer()

        from cts_cli.commands.artifacts import list_artifacts_command

        result = list_artifacts_command(
            run_id="test-run-123", http_client=mock_http_client, renderer=renderer
        )

        assert result == 0
        mock_http_client.get_json.assert_called_once_with("/v1/runs/test-run-123/artifacts")


class TestMonitorsCommand:
    """Test monitors command functionality."""

    def test_start_monitor(self, mock_http_client):
        """Test start monitor command."""
        mock_http_client.post_json.return_value = {"monitor_id": "monitor-123", "status": "started"}

        renderer = Renderer()

        from cts_cli.commands.monitors import start_monitor_command

        result = start_monitor_command(
            tool_id="hybrid_rx_trace",
            params=["interface=can0"],
            http_client=mock_http_client,
            renderer=renderer,
        )

        assert result == 0

        call_args = mock_http_client.post_json.call_args
        assert call_args[0][0] == "/v1/monitors"

        request_data = call_args[0][1]
        assert request_data["tool_id"] == "hybrid_rx_trace"
        assert request_data["params"] == {"interface": "can0"}

    def test_list_monitors(self, mock_http_client):
        """Test list monitors command."""
        mock_monitors = [
            {
                "id": "monitor-1",
                "tool_id": "hybrid_rx_trace",
                "status": "running",
                "started_at": "2024-01-01T12:00:00Z",
                "uptime": "5m 30s",
            }
        ]

        mock_http_client.get_json.return_value = mock_monitors

        renderer = Renderer()

        from cts_cli.commands.monitors import list_monitors_command

        result = list_monitors_command(http_client=mock_http_client, renderer=renderer)

        assert result == 0
        mock_http_client.get_json.assert_called_once_with("/v1/monitors")


class TestUploadCommand:
    """Test upload command functionality."""

    def test_upload_file(self, mock_http_client, temp_file):
        """Test file upload command."""
        mock_http_client.post_json.return_value = {
            "upload_id": "upload-123",
            "upload_url": "https://example.com/upload",
        }

        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_http_client.put.return_value = mock_response
        mock_http_client.post.return_value = mock_response

        renderer = Renderer()

        from cts_cli.commands.uploads import upload_command

        result = upload_command(
            file_path=temp_file, http_client=mock_http_client, renderer=renderer
        )

        assert result == 0

        create_call = mock_http_client.post_json.call_args
        assert create_call[0][0] == "/v1/uploads"

        create_data = create_call[0][1]
        assert "filename" in create_data
        assert "size" in create_data
        assert "sha256" in create_data

    def test_upload_nonexistent_file(self, mock_http_client):
        """Test upload command with nonexistent file."""
        renderer = Renderer()

        from cts_cli.commands.uploads import upload_command

        result = upload_command(
            file_path="/nonexistent/file.txt", http_client=mock_http_client, renderer=renderer
        )

        assert result == 1
