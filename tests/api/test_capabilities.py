"""Tests for capabilities endpoint."""

import time

import pytest
from fastapi.testclient import TestClient

from comma_tools.api.server import app

client = TestClient(app)


def test_capabilities_success():
    """Test successful capabilities response."""
    response = client.get("/v1/capabilities")

    assert response.status_code == 200
    data = response.json()

    assert "tools" in data
    assert "monitors" in data
    assert "api_version" in data
    assert "features" in data

    assert isinstance(data["tools"], list)
    assert isinstance(data["monitors"], list)
    assert isinstance(data["api_version"], str)
    assert isinstance(data["features"], list)


def test_capabilities_includes_expected_tools():
    """Test capabilities includes expected analyzer tools."""
    response = client.get("/v1/capabilities")
    data = response.json()

    tool_ids = [tool["id"] for tool in data["tools"]]

    assert "cruise-control-analyzer" in tool_ids
    assert "rlog-to-csv" in tool_ids
    assert "can-bitwatch" in tool_ids


def test_capabilities_includes_expected_monitors():
    """Test capabilities includes expected monitor tools."""
    response = client.get("/v1/capabilities")
    data = response.json()

    monitor_ids = [monitor["id"] for monitor in data["monitors"]]

    assert "hybrid_rx_trace" in monitor_ids
    assert "can_bus_check" in monitor_ids
    assert "can_hybrid_rx_check" in monitor_ids


def test_capabilities_tool_schema():
    """Test tool schema validation."""
    response = client.get("/v1/capabilities")
    data = response.json()

    if data["tools"]:
        tool = data["tools"][0]
        assert "id" in tool
        assert "name" in tool
        assert "description" in tool
        assert "category" in tool
        assert "parameters" in tool
        assert tool["category"] == "analyzer"


def test_capabilities_response_time():
    """Test capabilities response time is under 500ms."""
    start_time = time.time()
    response = client.get("/v1/capabilities")
    end_time = time.time()

    response_time = (end_time - start_time) * 1000  # Convert to milliseconds

    assert response.status_code == 200
    assert response_time < 500, f"Capabilities took {response_time:.2f}ms, should be < 500ms"
