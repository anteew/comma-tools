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

... (rest of README unchanged)