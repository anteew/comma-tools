# CTS-Lite: comma-tools Local Service

CTS-Lite is a local HTTP API service that exposes comma-tools functionality via FastAPI with SQLite backend. It supports batch analyzers, realtime monitors, and utilities with Server-Sent Events (SSE) for log streaming and WebSocket for realtime monitor data.

## Features

- **Batch Analyzers**: Execute CPU-intensive analysis tools like cruise-control-analyzer, rlog-to-csv, and can-bitwatch
- **Realtime Monitors**: Stream live data from CAN bus monitors and panda safety state monitors
- **Artifact Management**: Automatic artifact registration with SHA-256 verification and download endpoints
- **Progress Streaming**: Real-time log streaming via Server-Sent Events
- **SQLite Backend**: Single-file database with WAL mode for concurrent access
- **Process Isolation**: Subprocess execution for stability and compatibility with existing CLI tools

## Quick Start

### Installation

```bash
# Install with service dependencies
pip install -e ".[service]"
```

### Start the Service

```bash
# Start with default settings
cts-lite

# Or with custom configuration
cts-lite --host 0.0.0.0 --port 8080 --workers 4
```

The service will start on `http://127.0.0.1:8080` by default.

### Configuration

Create a `.env` file or set environment variables:

```bash
# Data storage location
CTS_DATA_ROOT=/path/to/data

# Service settings
CTS_HOST=127.0.0.1
CTS_PORT=8080
CTS_MAX_WORKERS=2

# Security (optional)
CTS_API_KEY=your-secret-key
CTS_CORS_ORIGINS=["http://localhost:3000"]

# Hardware access
CTS_ALLOW_HARDWARE=true

# Retention
CTS_RETENTION_DAYS=30
```

## API Usage

### Get Available Tools

```bash
curl http://127.0.0.1:8080/v1/capabilities
```

### Run Batch Analyzer

```bash
# Start cruise control analysis (requires authentication if CTS_API_KEY is set)
curl -X POST http://127.0.0.1:8080/v1/runs \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-secret-key" \
  -d '{
    "tool_id": "cruise-control-analyzer",
    "params": {
      "speed_min": 55.0,
      "speed_max": 56.0,
      "export_csv": true
    },
    "inputs": [
      {"kind": "path", "path": "/path/to/log.rlog.zst"}
    ]
  }'
```

### Stream Run Logs

```bash
# Stream logs via Server-Sent Events
curl -N http://127.0.0.1:8080/v1/runs/{run_id}/logs
```

### Start Realtime Monitor

```bash
# Start panda state monitor (requires authentication if CTS_API_KEY is set)
curl -X POST http://127.0.0.1:8080/v1/monitors \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-secret-key" \
  -d '{
    "tool_id": "panda-state",
    "params": {}
  }'

# Connect to WebSocket stream
# ws://127.0.0.1:8080/v1/monitors/{monitor_id}/stream?token={ws_token}
```

### Download Artifacts

```bash
# Download analysis results
curl -O http://127.0.0.1:8080/v1/artifacts/{artifact_id}/download
```

## Available Tools

### Batch Analyzers

- **cruise-control-analyzer**: Analyze rlog.zst files for Subaru cruise control signals and CAN bit changes
- **rlog-to-csv**: Convert openpilot rlog.zst files to CSV format for CAN analysis  
- **can-bitwatch**: Analyze CAN CSV dumps for bit changes and cruise control patterns

### Realtime Monitors

- **hybrid-rx-trace**: Monitor which CAN signals cause panda safety RX invalid states
- **can-bus-check**: Monitor CAN message frequencies by bus for interesting addresses
- **panda-state**: Monitor panda device safety states and control permissions

## Data Storage

CTS-Lite stores data in `$XDG_DATA_HOME/cts-lite/` (typically `~/.local/share/cts-lite/`):

```
cts-lite/
├── state.db              # SQLite database
├── runs/                 # Per-run working directories
│   └── {run_id}/
│       ├── input/        # Input files
│       ├── work/         # Working directory
│       ├── artifacts/    # Output artifacts
│       └── logs.jsonl    # Structured logs
├── artifacts/            # Flat artifact cache (optional)
└── uploads/              # Temporary uploads
```

## Development

### Running Tests

```bash
# Run existing comma-tools tests
python -m pytest tests/ -v

# Lint code
python -m flake8 src/
python -m mypy src/
```

### Local Development

```bash
# Start with auto-reload
cts-lite --reload

# Or run directly
python -m cts_lite.main --reload
```

## Architecture

- **FastAPI**: Modern async web framework with automatic OpenAPI generation
- **SQLite + WAL**: Single-file database with concurrent read/write support
- **ProcessPoolExecutor**: Isolated subprocess execution for batch jobs
- **Threading**: Realtime monitors run in background threads
- **SSE/WebSocket**: Standards-based streaming for logs and telemetry
- **Pydantic v2**: Type-safe data validation and serialization

## Security

- **Bearer Authentication**: Mutating endpoints (POST/DELETE) require Bearer token authentication via `CTS_API_KEY` environment variable
  - Required for: `POST /v1/runs`, `DELETE /v1/runs/{id}`, `POST /v1/monitors`, `DELETE /v1/monitors/{id}`
  - Read-only endpoints remain public: `GET /v1/capabilities`, `GET /v1/runs/{id}`, `GET /v1/health`, etc.
  - Include `Authorization: Bearer <your-api-key>` header for authenticated requests
- **CORS Support**: Configurable cross-origin resource sharing
- **Hardware Guards**: Optional hardware access controls
- **Process Isolation**: Subprocess execution prevents service crashes

## Monitoring

- **Health Checks**: `/v1/health` endpoint with database and disk space checks
- **Structured Logging**: JSONL format logs for each run
- **Metrics**: Built-in artifact tracking and retention management
