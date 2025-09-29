# Comma Tools
[![Test Suite](https://github.com/anteew/comma-tools/actions/workflows/test.yml/badge.svg)](https://github.com/anteew/comma-tools/actions/workflows/test.yml)

## Code Formatting & Contribution Rules (Universal)

> **This section appears verbatim in all agent and contributor guidance files.  
> Read this in every README, AGENTS, CONTRIBUTING, and Copilot instruction file.  
> This policy is identical everywhere—no file takes precedence.**

**All Python code in this repository must be formatted using [black](https://black.readthedocs.io/en/stable/) with a line length of 100.**  
This is enforced automatically by pre-commit hooks and CI.

- If your code is not formatted correctly, your commit will be rejected by pre-commit or CI checks.
- To check formatting locally:
  ```
  pre-commit run --all-files
  black --check src/ tests/
  ```
- To auto-format your code:
  ```
  black src/ tests/
  ```
- **For AI agents and all contributors:**  
  You must generate code that is already black-compatible (line length 100) or run "black" before committing code.  
  Code that does not pass `black --check` will not be accepted.

**Before contributing:**  
- Carefully read this section in all agent and contributor files (README, AGENTS.md, CONTRIBUTING.md, Copilot instructions, etc.).
- When in doubt, always refer to the README.md for the canonical version (which is identical to this).

For full details, see:
- [.pre-commit-config.yaml](.pre-commit-config.yaml)
- README.md
- .github/copilot-instructions.md
- docs/AGENTS.md
- CONTRIBUTING.md


# Comma Tools
[![Test Suite](https://github.com/anteew/comma-tools/actions/workflows/test.yml/badge.svg)](https://github.com/anteew/comma-tools/actions/workflows/test.yml)

## Overview

This repository contains a collection of debugging and analysis tools for the openpilot autonomous driving system. The tools are primarily focused on Controller Area Network (CAN) bus analysis, safety monitoring, and log conversion utilities for research, troubleshooting, and development.

## CTS-Lite API Service

**CTS-Lite** is the modern HTTP API service that provides unified access to all comma-tools analyzers and monitors. It replaces standalone CLI tools with a single, comprehensive interface.

### Quick Start

1. **Install with API support**:
   ```bash
   pip install -e ".[api,client]"
   ```

2. **Start the CTS-Lite service**:
   ```bash
   cts-lite
   # Server starts at http://127.0.0.1:8080
   ```

3. **Use the unified CLI client**:
   ```bash
   # Discover available tools
   cts cap
   
   # Run analysis
   cts run rlog-to-csv --path your-log.zst --wait
   
   # Note: Monitor support is still in development
   # Monitor functionality will be available in future releases
   ```

### Available Tools

- **rlog-to-csv**: Convert openpilot rlog.zst files into CSV format for analysis
- **can-bitwatch**: Swiss-army analyzer for CSV dumps of CAN frames with segment labels

### Available Monitors (In Development)

Monitor support is currently in development. The following monitors are planned:

- **hybrid_rx_trace**: Trace which CAN signals cause panda safety to flag RX invalid
- **can_bus_check**: General CAN message frequency analysis  
- **can_hybrid_rx_check**: Subaru hybrid-specific signal monitoring

*Note: Monitor API endpoints are not yet available in the current CTS-Lite implementation.*

## Legacy CLI Tools

For backward compatibility, individual CLI tools are still available:

```bash
rlog-to-csv your-log.zst
can-bitwatch your-data.csv
comma-connect-dl --help
```

## Development

### Setup Development Environment

```bash
# Clone and install with development dependencies
git clone https://github.com/anteew/comma-tools.git
cd comma-tools
pip install -e ".[dev]"

# Install pre-commit hooks (required)
pre-commit install

# Verify setup
pre-commit run --all-files
```

### Run Tests

```bash
pytest tests/
```

### Build Documentation

```bash
cd docs/
make html
# Open docs/_build/html/index.html
```

## Architecture

The repository follows a service-first architecture:

- **Core Logic**: Service components in `src/comma_tools/analyzers/` and `src/comma_tools/monitors/`
- **API Layer**: FastAPI service in `src/comma_tools/api/`
- **CLI Client**: Modern client in `src/cts_cli/`
- **Legacy Tools**: Backward-compatible CLI tools with individual entry points

## Contributing

All contributions must follow the code formatting rules above and pass pre-commit hooks. See [docs/AGENTS.md](docs/AGENTS.md) for detailed development guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.