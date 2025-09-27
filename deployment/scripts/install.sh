#!/usr/bin/env bash
set -euo pipefail

echo "Installing CTS-Lite service..."

python3 -m pip install --upgrade pip
python3 -m pip install .[api]

echo "Done."

