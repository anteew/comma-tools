# Container Usage Documentation

## Quick Start

The comma-tools Docker image is available at: `ghcr.io/anteew/comma-tools`

### Available Modes

#### 1. Interactive Mode (Default)
Start a bash shell with the tools available:
```bash
docker run -it --rm -v $(pwd):/workspace ghcr.io/anteew/comma-tools
```

#### 2. Daemon Mode
Run the CTS-Lite API server:
```bash
# Note: Use CTS_HOST environment variable to bind to all interfaces
docker run -d --rm -e CTS_HOST=0.0.0.0 -p 8080:8080 ghcr.io/anteew/comma-tools daemon
```

#### 3. CLI Passthrough Mode
Execute CLI commands directly (starts internal server automatically):
```bash
docker run --rm -v $(pwd):/workspace ghcr.io/anteew/comma-tools cli cts ping
```

## Testing the Container

### Basic Functionality Tests

1. **Pull the image:**
   ```bash
   docker pull ghcr.io/anteew/comma-tools:main
   ```

2. **Test CLI mode:**
   ```bash
   docker run --rm ghcr.io/anteew/comma-tools:main cli cts ping
   ```
   Expected output: `CTS-Lite API is healthy`

3. **Test daemon mode:**
   ```bash
   # Start the container
   docker run -d --name cts-test -e CTS_HOST=0.0.0.0 -p 8080:8080 ghcr.io/anteew/comma-tools:main daemon

   # Check health endpoint
   curl http://localhost:8080/v1/health

   # Clean up
   docker stop cts-test && docker rm cts-test
   ```

4. **Test interactive mode:**
   ```bash
   docker run -it --rm ghcr.io/anteew/comma-tools:main interactive
   # This should drop you into a bash shell with cts-lite running
   # Type 'exit' to leave
   ```

## Building Locally

To build the container locally for testing changes:

```bash
# Build the image
docker build -t comma-tools-local .

# Test your local build
docker run --rm comma-tools-local cli cts ping
```

## Known Issues

### 1. Missing OpenPilot Vendor Dependencies (Critical)
**Issue:** The container references vendor directories that don't exist:
- `/comma-tools/vendor/openpilot/tools`
- `/comma-tools/vendor/openpilot/cereal`

**Impact:** OpenPilot-dependent analyzers (like `cruise-control-analyzer`) will fail with import errors.

**Status:** Tracked in [Issue #103](https://github.com/anteew/comma-tools/issues/103)

### 2. Daemon Mode Host Binding
**Issue:** The `--host 0.0.0.0` command-line argument in `startup.py` is not processed by the server.

**Workaround:** Use the `CTS_HOST` environment variable:
```bash
docker run -d -e CTS_HOST=0.0.0.0 -p 8080:8080 ghcr.io/anteew/comma-tools:main daemon
```

## Troubleshooting

### Container won't start
Check the logs:
```bash
docker logs <container-name>
```

### Permission denied errors
If you encounter Docker permission issues:
1. Add your user to the docker group: `sudo usermod -aG docker $USER`
2. Log out and back in for changes to take effect
3. Verify with: `docker run hello-world`

### Port already in use
If port 8080 is already in use, map to a different port:
```bash
docker run -d -e CTS_HOST=0.0.0.0 -p 8081:8080 ghcr.io/anteew/comma-tools:main daemon
```

### Checking container status
```bash
# List running containers
docker ps

# Check container processes
docker exec <container-name> ps aux

# Access container shell for debugging
docker exec -it <container-name> /bin/bash
```

## Architecture Notes

- Base image: `python:3.12-slim`
- Exposed port: 8080
- Working directory: `/comma-tools`
- Entry point: `/usr/local/bin/comma-tools-startup`
- OpenPilot version: v0.10.0 (commit c085b8af19438956c1559) - currently not included

## Caching
Subsequent builds are faster due to Docker layer caching and GitHub Actions cache. Avoid changing pyproject.toml unnecessarily to maximize cache hits.
