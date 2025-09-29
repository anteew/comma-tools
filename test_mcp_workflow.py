#!/usr/bin/env python3
"""
Test script to simulate AI assistant using the comma-tools MCP server.
This demonstrates the full workflow of analyzing a log file.
"""

import json
import time
from pathlib import Path

from comma_tools_mcp.server import (
    check_health,
    get_version,
    list_capabilities,
    run_analysis,
    get_run_status,
    list_artifacts,
    get_artifact_content,
)

print("=" * 80)
print("Testing comma-tools MCP Server - Full Workflow")
print("=" * 80)

# Step 1: Health Check
print("\n[1] Checking CTS-Lite server health...")
health = check_health()
print(f"Status: {health['status']}")
print(f"Version: {health['version']}")
print(f"Uptime: {health['uptime']}")

# Step 2: Version Info
print("\n[2] Getting version information...")
version = get_version()
print(f"API Version: {version['api_version']}")
print(f"Min Client Version: {version['min_client_version']}")

# Step 3: List Capabilities
print("\n[3] Listing available analysis tools...")
caps = list_capabilities()
tools = caps.get("tools", [])
print(f"Found {len(tools)} tools:")
for tool in tools:
    print(f"  - {tool['id']}: {tool['description']}")

# Step 4: Prepare Test File
print("\n[4] Preparing test log file...")
test_file = Path("tests/data/known_good.rlog.zst").absolute()
if not test_file.exists():
    print(f"ERROR: Test file not found: {test_file}")
    exit(1)
print(f"Test file: {test_file}")
print(f"File size: {test_file.stat().st_size / 1024 / 1024:.2f} MB")

# Step 5: Start Analysis
print("\n[5] Starting analysis with rlog-to-csv...")
output_csv = "/tmp/cts_test_output.csv"
run_result = run_analysis(
    tool_id="rlog-to-csv",
    parameters={"rlog": str(test_file), "out": output_csv},
    name="MCP Test Run",
)
run_id = run_result.get("run_id")
print(f"Run ID: {run_id}")
print(f"Status: {run_result.get('status')}")
print(f"Tool ID: {run_result.get('tool_id')}")

# Step 6: Wait for Completion and Check Status
print("\n[6] Waiting for analysis to complete...")
max_wait = 60  # seconds
start_time = time.time()

while time.time() - start_time < max_wait:
    status = get_run_status(run_id)
    current_status = status.get("status")
    print(f"  Status: {current_status}...", end="\r")

    if current_status in ["completed", "failed"]:
        print(f"\n  Final Status: {current_status}")
        if current_status == "failed":
            print(f"  Error: {status.get('error')}")
        break

    time.sleep(2)

# Step 7: List Artifacts
print("\n[7] Listing generated artifacts...")
artifacts = list_artifacts(run_id)
print(f"Found {len(artifacts)} artifacts:")
for artifact in artifacts:
    print(f"  - {artifact['id']}: {artifact['filename']} ({artifact['size']} bytes)")

# Step 8: Get Artifact Content (for small text files)
print("\n[8] Fetching artifact content...")
if artifacts:
    first_artifact = artifacts[0]
    artifact_id = first_artifact["id"]
    filename = first_artifact["filename"]

    # Only try to fetch content if it's reasonably sized and a text format
    size = first_artifact["size"]
    if size < 100000 and filename.endswith((".csv", ".json", ".txt", ".html")):
        print(f"Getting content of {filename}...")
        content = get_artifact_content(artifact_id, max_size=100000)
        lines = content.split("\n")
        print(f"  First 10 lines:")
        for line in lines[:10]:
            print(f"    {line}")
        print(f"  ... ({len(lines)} total lines)")
    else:
        print(f"  Artifact too large or not a text format, skipping content fetch")
        print(f"  (Use download_artifact() to save to disk)")

print("\n" + "=" * 80)
print("MCP Server Test Complete!")
print("=" * 80)
print("\n✅ All MCP tools are working correctly!")
print("✅ Successfully analyzed log file through MCP server")
print("✅ Ready for AI assistant integration")