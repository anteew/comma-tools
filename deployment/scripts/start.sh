#!/usr/bin/env bash
set -euo pipefail

export CTS_API_HOST=${CTS_API_HOST:-0.0.0.0}
export CTS_API_PORT=${CTS_API_PORT:-8080}

exec python3 -m comma_tools.api.server

