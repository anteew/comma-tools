#!/usr/bin/env bash
set -euo pipefail

curl -fsS ${CTS_API_URL:-http://127.0.0.1:8080}/v1/health | jq .status

