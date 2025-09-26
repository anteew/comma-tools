"""Integration tests for Phase 3 functionality."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from comma_tools.api.server import create_app


@pytest_asyncio.fixture
async def client():
    """Create test client."""
    from fastapi.testclient import TestClient

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def test_artifact_endpoints_exist(client):
    """Test that artifact endpoints exist and return proper responses."""
    response = client.get("/v1/runs/test-run/artifacts")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_log_streaming_endpoint_exists(client):
    """Test that log streaming endpoint exists (without consuming stream)."""
    from comma_tools.api.server import create_app

    app = create_app()
    routes = [route.path for route in app.routes if hasattr(route, "path")]
    assert "/v1/runs/{run_id}/logs" in routes


def test_log_list_endpoint_exists(client):
    """Test that log list endpoint exists and returns JSON."""
    response = client.get("/v1/runs/test-run/logs/list")
    assert response.status_code == 200
    data = response.json()
    assert "run_id" in data
    assert "logs" in data
    assert "has_more" in data


def test_artifact_metadata_endpoint_not_found(client):
    """Test artifact metadata endpoint with non-existent artifact."""
    response = client.get("/v1/artifacts/nonexistent")
    assert response.status_code == 404


def test_artifact_download_endpoint_not_found(client):
    """Test artifact download endpoint with non-existent artifact."""
    response = client.get("/v1/artifacts/nonexistent/download")
    assert response.status_code == 404
