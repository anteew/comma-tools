"""Tests for health endpoint."""

import time
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from comma_tools.api.server import app

client = TestClient(app)


def test_health_check_success():
    """Test successful health check response."""
    response = client.get("/v1/health")

    assert response.status_code == 200
    data = response.json()

    assert "status" in data
    assert "version" in data
    assert "uptime" in data
    assert "timestamp" in data

    assert data["status"] == "healthy"
    assert isinstance(data["version"], str)
    assert isinstance(data["uptime"], str)
    assert isinstance(data["timestamp"], str)


def test_health_check_response_time():
    """Test health check response time is under 100ms."""
    start_time = time.time()
    response = client.get("/v1/health")
    end_time = time.time()

    response_time = (end_time - start_time) * 1000  # Convert to milliseconds

    assert response.status_code == 200
    assert response_time < 100, f"Health check took {response_time:.2f}ms, should be < 100ms"


def test_health_check_uptime_format():
    """Test uptime format is correct."""
    response = client.get("/v1/health")
    data = response.json()

    uptime = data["uptime"]
    assert "d" in uptime and "h" in uptime and "m" in uptime and "s" in uptime
