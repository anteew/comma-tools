# Deployment Guide

This guide explains how to deploy CTS-Lite in production.

## Requirements
- Python 3.10+
- Optional: Docker and docker-compose
- Systemd for service management (Linux)

## Configuration
Environment variables (prefixed `CTS_API_`):
- `HOST` (default `127.0.0.1`)
- `PORT` (default `8080`)
- `LOG_LEVEL` (default `INFO`)
- `TOOL_TIMEOUT_SECONDS` (default `300`)

See `src/comma_tools/api/config.py` for full settings.

## Docker

Build and run:

```
docker build -f deployment/docker/Dockerfile -t cts-lite .
docker run -p 8080:8080 -e CTS_API_HOST=0.0.0.0 cts-lite
```

Or with compose:

```
cd deployment/docker
docker compose up --build
```

## Systemd

1. Create user and install package
```
sudo useradd -r -s /bin/false cts || true
sudo pip3 install .[api]
```

2. Configure environment
```
sudo install -m 0644 deployment/systemd/cts-lite.env /etc/default/cts-lite
```

3. Install service unit
```
sudo install -m 0644 deployment/systemd/cts-lite.service /etc/systemd/system/cts-lite.service
sudo systemctl daemon-reload
sudo systemctl enable --now cts-lite
```

## Reverse Proxy (nginx)
Use `deployment/nginx/cts-lite.conf` as a template to proxy to the service and support WebSockets.

## Monitoring
- Health endpoint: `/v1/health`
- Internal metrics are tracked in-process; integrate with external systems as needed.

## Backup and Recovery
Artifacts are stored under `/var/lib/cts-lite`. Back up this directory regularly.

