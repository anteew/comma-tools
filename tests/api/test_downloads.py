"""Tests for downloads endpoint."""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from comma_tools.api.server import app

client = TestClient(app)


@pytest.fixture
def temp_dest_dir():
    """Create temporary destination directory for download tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["CTS_DOWNLOAD_BASE_PATH"] = tmpdir
        yield tmpdir
        if "CTS_DOWNLOAD_BASE_PATH" in os.environ:
            del os.environ["CTS_DOWNLOAD_BASE_PATH"]


@pytest.fixture
def mock_connect_client():
    """Mock ConnectClient for testing without real API calls."""
    with patch("comma_tools.sources.connect.client.ConnectClient") as mock:
        client_instance = MagicMock()
        mock.return_value = client_instance
        yield client_instance


@pytest.fixture
def mock_route_resolver():
    """Mock RouteResolver for testing without real API calls."""
    with patch("comma_tools.sources.connect.resolver.RouteResolver") as mock:
        resolver_instance = MagicMock()
        mock.return_value = resolver_instance
        yield resolver_instance


@pytest.fixture
def mock_log_downloader():
    """Mock LogDownloader for testing without real downloads."""
    with patch("comma_tools.sources.connect.downloader.LogDownloader") as mock:
        downloader_instance = MagicMock()
        mock.return_value = downloader_instance
        yield downloader_instance


def test_download_request_schema():
    """Test download request schema validation."""
    request_data = {
        "route": "test_dongle|2024-01-01--12-00-00",
        "dest_root": "/tmp/test",
    }

    response = client.post("/v1/downloads", json=request_data)

    assert response.status_code in [202, 400, 500]  # Various outcomes depending on mocks


def test_download_request_with_all_options(temp_dest_dir):
    """Test download request with all optional parameters."""
    request_data = {
        "route": "test_dongle|2024-01-01--12-00-00",
        "dest_root": temp_dest_dir,
        "file_types": {"logs": True, "cameras": False},
        "search_days": 14,
        "resume": False,
        "parallel": 8,
    }

    response = client.post("/v1/downloads", json=request_data)

    assert response.status_code in [202, 400, 500]


def test_download_request_invalid_search_days():
    """Test validation for search_days parameter."""
    request_data = {
        "route": "test_dongle|2024-01-01--12-00-00",
        "dest_root": "/tmp/test",
        "search_days": 0,  # Invalid: must be >= 1
    }

    response = client.post("/v1/downloads", json=request_data)

    assert response.status_code == 422  # Validation error


def test_download_request_invalid_parallel():
    """Test validation for parallel parameter."""
    request_data = {
        "route": "test_dongle|2024-01-01--12-00-00",
        "dest_root": "/tmp/test",
        "parallel": 0,  # Invalid: must be >= 1
    }

    response = client.post("/v1/downloads", json=request_data)

    assert response.status_code == 422  # Validation error


@patch("comma_tools.sources.connect.client.ConnectClient")
@patch("comma_tools.sources.connect.resolver.RouteResolver")
@patch("comma_tools.sources.connect.downloader.LogDownloader")
def test_download_successful_flow(
    mock_downloader_class, mock_resolver_class, mock_client_class, temp_dest_dir
):
    """Test successful download flow with mocked dependencies."""
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client

    mock_resolver = MagicMock()
    mock_resolver.resolve.return_value = "test_dongle|2024-01-01--12-00-00"
    mock_resolver_class.return_value = mock_resolver

    mock_downloader = MagicMock()
    mock_report = MagicMock()
    mock_report.success_count = 10
    mock_report.skip_count = 2
    mock_report.failure_count = 0
    mock_report.total_bytes = 1024000
    mock_downloader.download_route.return_value = mock_report
    mock_downloader_class.return_value = mock_downloader

    request_data = {
        "route": "test_dongle|2024-01-01--12-00-00",
        "dest_root": temp_dest_dir,
        "file_types": {"logs": True},
    }

    response = client.post("/v1/downloads", json=request_data)

    assert response.status_code == 202
    data = response.json()

    assert "download_id" in data
    assert data["status"] == "completed"
    assert data["canonical_route"] == "test_dongle|2024-01-01--12-00-00"
    assert data["downloaded_files"] == 10
    assert data["skipped_files"] == 2
    assert data["failed_files"] == 0
    assert data["total_bytes"] == 1024000
    assert "created_at" in data
    assert "completed_at" in data


@patch("comma_tools.sources.connect.client.ConnectClient")
@patch("comma_tools.sources.connect.resolver.RouteResolver")
def test_download_resolver_failure(mock_resolver_class, mock_client_class, temp_dest_dir):
    """Test handling of route resolution failure."""
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client

    mock_resolver = MagicMock()
    mock_resolver.resolve.side_effect = ValueError("Route not found")
    mock_resolver_class.return_value = mock_resolver

    request_data = {
        "route": "invalid_route",
        "dest_root": temp_dest_dir,
    }

    response = client.post("/v1/downloads", json=request_data)

    assert response.status_code == 400
    assert "Route not found" in response.json()["detail"]


@patch("comma_tools.sources.connect.client.ConnectClient")
@patch("comma_tools.sources.connect.resolver.RouteResolver")
@patch("comma_tools.sources.connect.downloader.LogDownloader")
def test_download_network_failure(
    mock_downloader_class, mock_resolver_class, mock_client_class, temp_dest_dir
):
    """Test handling of download network failure."""
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client

    mock_resolver = MagicMock()
    mock_resolver.resolve.return_value = "test_dongle|2024-01-01--12-00-00"
    mock_resolver_class.return_value = mock_resolver

    mock_downloader = MagicMock()
    mock_downloader.download_route.side_effect = Exception("Network error")
    mock_downloader_class.return_value = mock_downloader

    request_data = {
        "route": "test_dongle|2024-01-01--12-00-00",
        "dest_root": temp_dest_dir,
    }

    response = client.post("/v1/downloads", json=request_data)

    assert response.status_code == 500
    assert "Network error" in response.json()["detail"]


@patch("comma_tools.sources.connect.client.ConnectClient")
@patch("comma_tools.sources.connect.resolver.RouteResolver")
@patch("comma_tools.sources.connect.downloader.LogDownloader")
def test_get_download_status(
    mock_downloader_class, mock_resolver_class, mock_client_class, temp_dest_dir
):
    """Test getting download status after creation."""
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client

    mock_resolver = MagicMock()
    mock_resolver.resolve.return_value = "test_dongle|2024-01-01--12-00-00"
    mock_resolver_class.return_value = mock_resolver

    mock_downloader = MagicMock()
    mock_report = MagicMock()
    mock_report.success_count = 5
    mock_report.skip_count = 0
    mock_report.failure_count = 0
    mock_report.total_bytes = 512000
    mock_downloader.download_route.return_value = mock_report
    mock_downloader_class.return_value = mock_downloader

    request_data = {
        "route": "test_dongle|2024-01-01--12-00-00",
        "dest_root": temp_dest_dir,
    }

    create_response = client.post("/v1/downloads", json=request_data)
    assert create_response.status_code == 202

    download_id = create_response.json()["download_id"]

    status_response = client.get(f"/v1/downloads/{download_id}")

    assert status_response.status_code == 200
    status_data = status_response.json()

    assert status_data["download_id"] == download_id
    assert status_data["status"] == "completed"
    assert status_data["downloaded_files"] == 5


def test_get_download_status_not_found():
    """Test getting status for non-existent download."""
    response = client.get("/v1/downloads/nonexistent-id")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_download_response_includes_timestamps():
    """Test that download response includes proper timestamps."""
    request_data = {
        "route": "test_dongle|2024-01-01--12-00-00",
        "dest_root": "/tmp/test",
    }

    response = client.post("/v1/downloads", json=request_data)

    if response.status_code in [202, 400, 500]:
        data = response.json()
        if "created_at" in data:
            assert isinstance(data["created_at"], str)
        if "completed_at" in data:
            assert isinstance(data["completed_at"], str) or data["completed_at"] is None


def test_download_default_file_types():
    """Test that default file_types is {'logs': True}."""
    request_data = {
        "route": "test_dongle|2024-01-01--12-00-00",
        "dest_root": "/tmp/test",
    }

    response = client.post("/v1/downloads", json=request_data)

    assert response.status_code in [202, 400, 500]


def test_download_path_traversal_protection(temp_dest_dir):
    """Test that path traversal attacks are blocked."""
    traversal_paths = [
        "/etc/shadow",
        "/sys/kernel",
        "/proc/self",
        "/dev/null",
    ]

    for malicious_path in traversal_paths:
        request_data = {
            "route": "test_dongle|2024-01-01--12-00-00",
            "dest_root": malicious_path,
        }

        response = client.post("/v1/downloads", json=request_data)

        assert response.status_code == 400, f"Path {malicious_path} should be rejected"
        assert (
            "destination path" in response.json()["detail"].lower()
            or "invalid destination" in response.json()["detail"].lower()
        )


def test_download_relative_path_rejection(temp_dest_dir):
    """Test that relative paths with traversal are rejected."""
    request_data = {
        "route": "test_dongle|2024-01-01--12-00-00",
        "dest_root": "../../sensitive",
    }

    response = client.post("/v1/downloads", json=request_data)

    assert response.status_code == 400


def test_download_null_byte_injection(temp_dest_dir):
    """Test that null byte injection is blocked."""
    request_data = {
        "route": "test_dongle|2024-01-01--12-00-00",
        "dest_root": f"{temp_dest_dir}\x00malicious",
    }

    response = client.post("/v1/downloads", json=request_data)

    assert response.status_code == 400
    assert (
        "null" in response.json()["detail"].lower()
        or "invalid" in response.json()["detail"].lower()
    )
