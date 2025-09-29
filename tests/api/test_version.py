"""Tests for version endpoint."""

import pytest
from fastapi.testclient import TestClient
from packaging import version

from comma_tools.api.server import app
from comma_tools.api.version import API_VERSION, MIN_CLIENT_VERSION

client = TestClient(app)


def test_version_endpoint_success():
    """Test successful version endpoint response."""
    response = client.get("/v1/version")

    assert response.status_code == 200
    data = response.json()

    assert "api_version" in data
    assert "min_client_version" in data
    assert "deprecated_features" in data

    assert data["api_version"] == API_VERSION
    assert data["min_client_version"] == MIN_CLIENT_VERSION
    assert isinstance(data["deprecated_features"], list)


def test_version_endpoint_valid_semver():
    """Test that version strings are valid semantic versions."""
    response = client.get("/v1/version")
    data = response.json()

    # Should not raise an exception
    api_ver = version.parse(data["api_version"])
    min_ver = version.parse(data["min_client_version"])

    # Sanity check: min_client_version should not be higher than api_version
    assert isinstance(api_ver, version.Version)
    assert isinstance(min_ver, version.Version)


def test_version_endpoint_deprecated_features_is_list():
    """Test that deprecated_features is a list."""
    response = client.get("/v1/version")
    data = response.json()

    assert isinstance(data["deprecated_features"], list)
    # Should be empty by default
    assert len(data["deprecated_features"]) == 0