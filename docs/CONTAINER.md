Container usage (Phase 4C-A)

Image: ghcr.io/anteew/comma-tools

Modes:
- Interactive (default):
  docker run -it --rm -v $(pwd):/workspace ghcr.io/anteew/comma-tools
- Daemon:
  docker run -d --rm -p 8080:8080 ghcr.io/anteew/comma-tools daemon
- CLI passthrough (starts server, runs CLI):
  docker run --rm -v $(pwd):/workspace ghcr.io/anteew/comma-tools cli cts ping

Notes:
- Health endpoint: http://127.0.0.1:8080/v1/health
- Vendored openpilot minimal dependencies are used inside the container, pinned to openpilot v0.10.0 (commit c085b8af19438956c1559).
- Native development outside the container still expects an openpilot sibling checkout if analyzers require it.
