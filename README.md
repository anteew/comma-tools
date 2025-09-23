# Comma Tools
[![Test Suite](https://github.com/anteew/comma-tools/actions/workflows/test.yml/badge.svg)](https://github.com/anteew/comma-tools/actions/workflows/test.yml)

Debugging and analysis tools for the openpilot autonomous driving system.

## Overview

This repository contains a collection of debugging and analysis tools for the openpilot autonomous driving system. The tools are primarily focused on Controller Area Network (CAN) bus analysis, safety system monitoring, and vehicle behavior debugging.

## Installation

```bash
# Clone the repository
git clone https://github.com/anteew/comma-tools.git
cd comma-tools

# Install in development mode
pip install -e .

# Or install with development dependencies
pip install -e ".[dev]"
```

## Tools

### Analyzers
- **Cruise Control Analyzer** (`cruise-control-analyzer`): Deep analysis of recorded driving logs (`rlog.zst` files) with focus on Subaru vehicle cruise control systems

### Monitors
- **Hybrid RX Trace** (`hybrid_rx_trace.py`): Real-time monitoring of Panda safety states
- **Panda State** (`panda-state.py`): General Panda device status reporting  
- **CAN Bus Check** (`can_bus_check.py`): General CAN message frequency analysis
- **CAN Hybrid RX Check** (`can_hybrid_rx_check.py`): Subaru hybrid-specific signal monitoring

### Utilities
- **Simple Panda** (`simple-panda.py`): Basic Panda health check utility

### Scripts
- Various shell script wrappers for common operations

## Usage

### Cruise Control Analyzer

```bash
# Analyze a log file (first run - installs dependencies)
cruise-control-analyzer /path/to/logfile.zst --install-missing-deps

# Subsequent runs
cruise-control-analyzer /path/to/logfile.zst

# With custom speed range
cruise-control-analyzer /path/to/logfile.zst --speed-min 50 --speed-max 60
```

### Real-time Monitoring

```bash
# Monitor Panda safety states
python -m comma_tools.monitors.hybrid_rx_trace

# Check CAN bus activity
python -m comma_tools.monitors.can_bus_check
```

## Development

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black src/ tests/

# Type checking
mypy src/
```

## Project Structure

```
comma-tools/
├── src/comma_tools/           # Main package
│   ├── analyzers/            # Log analysis tools
│   ├── monitors/             # Real-time monitoring
│   └── utils/                # Shared utilities
├── tests/                    # Test suite
├── scripts/                  # Shell script wrappers
└── docs/                     # Documentation
```

## Requirements

- Python 3.12
- openpilot installation (for some tools)
- Panda device (for real-time monitoring tools)
## Integration tests with a real rlog.zst

By default, the repo includes a known-good real log fixture stored via Git LFS:
- Path: `tests/data/known_good.rlog.zst`
- CI and local runs will use this fixture automatically for integration tests.

Override the fixture with your own log if desired:

Option A: environment variable
```bash
LOG_FILE=/absolute/path/to/your.rlog.zst pytest tests/integration -v -m integration
```

Option B: pytest option
```bash
pytest tests/integration -v -m integration --real-log-file=/absolute/path/to/your.rlog.zst
```

Notes:
- If neither CLI nor env is provided and the fixture is present, tests will use the fixture. If no fixture is present, tests are skipped automatically.
- Ensure Git LFS is installed locally to fetch the fixture (`git lfs install`).
- To also test dependency bootstrap, keep `openpilot/` checked out next to `comma-tools/` or pass `--repo-root` to the CLI.

## License

MIT License - see LICENSE file for details.
