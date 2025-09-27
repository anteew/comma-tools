# API Reference

Base URL: `/v1`

## Health
- `GET /health` → service status

## Capabilities
- `GET /capabilities` → tools and monitors list

## Runs
- `POST /runs` → start analyzer run
- `GET /runs/{run_id}` → get status
- `DELETE /runs/{run_id}` → cancel
- `GET /runs/{run_id}/logs` → stream logs (SSE)
- `GET /runs/{run_id}/logs/list` → get logs list
- `GET /runs/{run_id}/artifacts` → list artifacts
- `GET /artifacts/{artifact_id}` → download

RunResponse fields include `error_category` and `error_details` when failed.

## Monitors
- `POST /monitors` → start monitor `{ tool_id, params }`
- `GET /monitors` → list active monitors
- `GET /monitors/{monitor_id}/status` → status and uptime
- `DELETE /monitors/{monitor_id}` → stop monitor
- `WS /monitors/{monitor_id}/stream` → WebSocket data stream

Supported monitor `tool_id` values:
- `hybrid_rx_trace`
- `can_bus_check`
- `can_hybrid_rx_check`

