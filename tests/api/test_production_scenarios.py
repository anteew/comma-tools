"""Production scenario smoke tests.

These are lightweight checks to validate production-readiness aspects
without requiring real data or hardware during CI.
"""

import time

from fastapi.testclient import TestClient

from comma_tools.api.server import app


client = TestClient(app)


def test_endpoints_basic_latency():
    start = time.time()
    r = client.get("/v1/health")
    assert r.status_code == 200
    assert (time.time() - start) * 1000 < 2000  # < 2s

    start = time.time()
    r = client.get("/v1/capabilities")
    assert r.status_code == 200
    assert (time.time() - start) * 1000 < 2000


def test_error_scenarios_invalid_tool():
    r = client.post("/v1/runs", json={"tool_id": "does-not-exist", "params": {}})
    assert r.status_code in (400, 404)


def test_monitor_routes_exist():
    # List (should succeed and return list)
    r = client.get("/v1/monitors")
    assert r.status_code == 200
    assert isinstance(r.json(), list)

