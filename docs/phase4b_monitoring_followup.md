# Phase 4B Configuration Monitoring Follow-up

## Current Status Summary
- Phase 4B introduced configuration management, health reporting, and metrics endpoints, but multiple success criteria remain unmet in `docs/PHASE_4B_CONFIG_MONITORING.md`.
- The configuration override chain is stubbed: `_load_from_file` and `_load_from_environment` in `src/comma_tools/api/config.py` return empty dictionaries, so file and environment overrides never take effect.
- Tool registry health verification is incomplete: `_check_tool_registry` in `src/comma_tools/api/health.py` reports success without validating that any tools are registered.
- Automated coverage stops at unit-level helpers; no HTTP-level tests exercise `/v1/metrics`, `/v1/config/status`, or `/v1/health/comprehensive`.

## Recommended Remediation Tasks

### 1. Implement configuration overrides
- Parse JSON and TOML overrides in `ConfigManager._load_from_file`, caching `self._config_file_path` and raising `ValueError` on parse or format errors.
- Collect `CTS_`-prefixed environment variables (excluding `CTS_ENVIRONMENT`, which is reserved for selecting the deployment environment and not used as a config override) inside `_load_from_environment`, coerce them to the `ProductionConfig` field types, and merge them in the existing priority order (base < file < env).
- Extend `tests/api/test_config_monitoring.py` to cover file- and env-driven overrides, ensuring environment values win over file inputs.
- Update `docs/PHASE_4B_CONFIG_MONITORING.md` to mark the override criteria complete and document accepted file formats.

### 2. Validate tool availability in health checks
- Update `_check_tool_registry` in `src/comma_tools/api/health.py` to call `ToolRegistry().list_tools()` (or another method that returns the current list of registered tools), returning healthy only when at least one tool is registered and raising with a clear error message otherwise.  
- Add unit tests that patch `ToolRegistry.list_tools` to cover empty and populated registry outcomes.
- Document the failure behaviour in Phase 4B's guide once verified.

### 3. Add FastAPI integration coverage for monitoring routes
- Introduce a `TestClient(create_app())` fixture in `tests/api/test_config_monitoring.py` and add tests for `/v1/metrics`, `/v1/config/status`, `/v1/health/comprehensive`, and legacy aliases if present.
- Patch `app.state.metrics_collector`, `app.state.config`, and `app.state.health_manager` in those tests to return deterministic payloads, asserting that config overrides flow into the responses.
- Replace the manual curl checklist in the Phase 4B documentation with references to these automated integration tests.

## Testing Expectations
- Run `pytest tests/api/test_config_monitoring.py` after implementing the above tasks to confirm unit and integration coverage.

## Documentation Expectations
- Refresh `docs/PHASE_4B_CONFIG_MONITORING.md` to reflect the completed override work, describe supported config file formats, and summarize the new automated endpoint coverage.