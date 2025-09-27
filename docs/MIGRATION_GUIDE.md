# Migration Guide: CLI → CTS-Lite

This guide helps migrate from standalone CLI tools to the unified `cts` CLI and CTS-Lite API.

## Command Mapping

- Cruise Control Analyzer:
  - Old: `python -m comma_tools.analyzers.cruise_control_analyzer <rlog.zst> [...params]`
  - New: `cts run cruise-control-analyzer --path <rlog.zst> -p speed_min=55 -p speed_max=56 --wait --follow`

- RLog to CSV:
  - Old: `rlog-to-csv --rlog <rlog.zst> --out out.csv`
  - New: `cts run rlog-to-csv --path <rlog.zst> -p out=out.csv --wait`

- CAN Bitwatch:
  - Old: `can-bitwatch --csv <file.csv> [...params]`
  - New: `cts run can-bitwatch --path <file.csv> [--param KEY=VAL ...] --wait`

## Parameters
Use `cts cap` to inspect available parameters and defaults. Pass parameters with `-p key=value` or repeated `-p` flags.

## Feature Parity
All three analyzers are supported with artifact detection and log streaming. Monitors are supported via WebSockets.

## Timeline
- Phase 4 completes API parity and production readiness. Post-Phase 4 deployments can deprecate direct CLI invocations.

