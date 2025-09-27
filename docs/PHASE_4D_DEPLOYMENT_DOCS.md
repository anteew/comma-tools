# Phase 4D Implementation Guide: Deployment & Documentation

**Assigned to**: AI Coding Agent  
**Estimated Time**: 2-3 hours  
**Priority**: CRITICAL - Final MVP completion  
**Architecture Review Required**: Yes  
**Previous Phase**: Phase 4C (Testing & Quality Assurance) - Must be completed first

## Objective

Complete the final deployment preparation and documentation for CTS-Lite MVP. This phase makes the service production-ready with containerization, deployment scripts, operational documentation, and user migration guides.

**Goal**: Deliver a complete, production-ready MVP that can replace standalone CLI tools with superior user experience and enterprise-grade reliability.

## Phase 4D Scope: Deployment & Documentation Completion

### **1. Docker Containerization (CRITICAL)**

#### Create `deployment/docker/Dockerfile`
**Purpose**: Production-ready container for CTS-Lite service
**Requirements**:
- Optimized multi-stage build
- Security best practices
- Minimal attack surface
- Proper dependency management

```dockerfile
# Multi-stage build for production optimization
FROM python:3.12-slim as builder

# Build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir build && \
    python -m build --wheel

# Production stage
FROM python:3.12-slim as production

# Create non-root user for security
RUN groupadd -r cts && useradd -r -g cts cts

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create application directories
RUN mkdir -p /app /var/lib/cts /var/log/cts /tmp/cts && \
    chown -R cts:cts /app /var/lib/cts /var/log/cts /tmp/cts

# Copy application code
COPY --from=builder dist/*.whl /tmp/
COPY src/ /app/src/
COPY deployment/docker/entrypoint.sh /app/entrypoint.sh

# Install application
RUN pip install --no-cache-dir /tmp/*.whl && \
    chmod +x /app/entrypoint.sh && \
    rm /tmp/*.whl

# Switch to non-root user
USER cts
WORKDIR /app

# Environment configuration
ENV CTS_ENVIRONMENT=production \
    CTS_BASE_STORAGE_PATH=/var/lib/cts \
    CTS_LOG_DIRECTORY=/var/log/cts \
    CTS_TEMP_DIRECTORY=/tmp/cts \
    CTS_LOG_LEVEL=INFO \
    CTS_ENABLE_METRICS=true

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health/simple || exit 1

# Expose port
EXPOSE 8000

# Start application
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["cts-lite"]
```

#### Create `deployment/docker/entrypoint.sh`
**Purpose**: Container startup script with proper initialization
**Requirements**:
- Environment validation
- Dependency verification
- Graceful startup
- Signal handling

```bash
#!/bin/bash
set -e

# Container entrypoint script for CTS-Lite
echo "=== CTS-Lite Container Starting ==="

# Environment validation
if [ -z "$CTS_ENVIRONMENT" ]; then
    export CTS_ENVIRONMENT="production"
fi

echo "Environment: $CTS_ENVIRONMENT"
echo "Storage Path: $CTS_BASE_STORAGE_PATH"
echo "Log Level: $CTS_LOG_LEVEL"

# Create required directories
mkdir -p "$CTS_BASE_STORAGE_PATH" "$CTS_LOG_DIRECTORY" "$CTS_TEMP_DIRECTORY"

# Validate configuration
echo "Validating configuration..."
python -c "
from comma_tools.api.config import ConfigManager
config_manager = ConfigManager()
config = config_manager.load_config()
print(f'Configuration loaded successfully: {config.environment}')
"

# Wait for dependencies (if any external services required)
echo "Checking service dependencies..."
# Add dependency checks here if needed

# Start the application
echo "Starting CTS-Lite service..."
echo "=== CTS-Lite Ready ==="

# Execute the main command
exec "$@"
```

#### Create `deployment/docker/docker-compose.yml`
**Purpose**: Complete Docker Compose setup for development and testing
**Requirements**:
- Volume mounts for data persistence
- Environment configuration
- Network setup
- Development overrides

```yaml
version: '3.8'

services:
  cts-lite:
    build:
      context: ../../
      dockerfile: deployment/docker/Dockerfile
    container_name: cts-lite
    restart: unless-stopped
    ports:
      - "8000:8000"
    volumes:
      # Persistent storage for artifacts and logs
      - cts_storage:/var/lib/cts
      - cts_logs:/var/log/cts
      # Mount test data for development
      - ../../tests/data:/app/test_data:ro
    environment:
      - CTS_ENVIRONMENT=production
      - CTS_LOG_LEVEL=INFO
      - CTS_MAX_CONCURRENT_RUNS=3
      - CTS_ENABLE_METRICS=true
      - CTS_ENABLE_HEALTH_CHECKS=true
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health/simple"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    networks:
      - cts_network

  # Optional: nginx reverse proxy for production
  nginx:
    image: nginx:alpine
    container_name: cts-nginx
    restart: unless-stopped
    ports:
      - "80:80"
    volumes:
      - ../nginx/cts-lite.conf:/etc/nginx/conf.d/default.conf:ro
    depends_on:
      - cts-lite
    networks:
      - cts_network

volumes:
  cts_storage:
    driver: local
  cts_logs:
    driver: local

networks:
  cts_network:
    driver: bridge
```

### **2. System Service Integration (REQUIRED)**

#### Create `deployment/systemd/cts-lite.service`
**Purpose**: SystemD service for production deployment
**Requirements**:
- Proper service management
- Automatic restart capabilities
- Environment isolation
- Logging integration

```ini
[Unit]
Description=CTS-Lite API Service
Documentation=https://github.com/anteew/comma-tools
After=network.target
Wants=network.target

[Service]
Type=exec
User=cts
Group=cts
WorkingDirectory=/opt/cts-lite

# Environment configuration
EnvironmentFile=/etc/cts-lite/cts-lite.env

# Service execution
ExecStart=/opt/cts-lite/venv/bin/uvicorn comma_tools.api.main:app --host 0.0.0.0 --port 8000
ExecReload=/bin/kill -HUP $MAINPID

# Process management
Restart=always
RestartSec=10
KillMode=process
TimeoutStopSec=30

# Security settings
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/cts /var/log/cts /tmp/cts
PrivateTmp=true

# Resource limits
LimitNOFILE=65536
MemoryLimit=4G

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=cts-lite

[Install]
WantedBy=multi-user.target
```

#### Create `deployment/systemd/cts-lite.env`
**Purpose**: Environment configuration for SystemD service
```bash
# CTS-Lite Service Configuration
CTS_ENVIRONMENT=production
CTS_LOG_LEVEL=INFO
CTS_BASE_STORAGE_PATH=/var/lib/cts
CTS_LOG_DIRECTORY=/var/log/cts
CTS_TEMP_DIRECTORY=/tmp/cts
CTS_MAX_CONCURRENT_RUNS=5
CTS_TOOL_TIMEOUT_SECONDS=600
CTS_ENABLE_METRICS=true
CTS_ENABLE_HEALTH_CHECKS=true
CTS_ENABLE_RATE_LIMITING=true
CTS_MAX_REQUESTS_PER_MINUTE=120
```

### **3. Deployment Scripts & Automation (REQUIRED)**

#### Create `deployment/scripts/install.sh`
**Purpose**: Automated installation script for production deployment
**Requirements**:
- System requirements validation
- User and directory creation
- Service installation
- Configuration setup

```bash
#!/bin/bash
set -e

# CTS-Lite Production Installation Script
echo "=== CTS-Lite Production Installation ==="

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (use sudo)"
    exit 1
fi

# System requirements check
echo "Checking system requirements..."

# Check Python version
python3_version=$(python3 --version 2>&1 | cut -d' ' -f2)
required_version="3.12"

if ! python3 -c "import sys; exit(0 if sys.version_info >= (3, 12) else 1)" 2>/dev/null; then
    echo "Error: Python 3.12 or higher required (found: $python3_version)"
    exit 1
fi

echo "✓ Python $python3_version detected"

# Check available disk space (require at least 2GB)
available_space=$(df / | awk 'NR==2 {print $4}')
required_space=2097152  # 2GB in KB

if [ "$available_space" -lt "$required_space" ]; then
    echo "Error: Insufficient disk space (need 2GB, have $(($available_space/1024/1024))GB)"
    exit 1
fi

echo "✓ Sufficient disk space available"

# Install system dependencies
echo "Installing system dependencies..."
apt-get update
apt-get install -y python3-pip python3-venv curl nginx

# Create cts user and group
echo "Creating cts user and directories..."
if ! id -u cts >/dev/null 2>&1; then
    useradd -r -s /bin/false -d /opt/cts-lite cts
    echo "✓ Created cts user"
fi

# Create directories
directories=(
    "/opt/cts-lite"
    "/var/lib/cts"
    "/var/log/cts"
    "/etc/cts-lite"
    "/tmp/cts"
)

for dir in "${directories[@]}"; do
    mkdir -p "$dir"
    chown cts:cts "$dir"
done

echo "✓ Created application directories"

# Install CTS-Lite application
echo "Installing CTS-Lite application..."
cd /opt/cts-lite

# Create virtual environment
sudo -u cts python3 -m venv venv
sudo -u cts ./venv/bin/pip install --upgrade pip

# Install from PyPI or local wheel
if [ -f "/tmp/cts-lite.whl" ]; then
    echo "Installing from local wheel..."
    sudo -u cts ./venv/bin/pip install /tmp/cts-lite.whl
else
    echo "Installing from PyPI..."
    sudo -u cts ./venv/bin/pip install comma-tools[api]
fi

echo "✓ CTS-Lite application installed"

# Install service files
echo "Installing service configuration..."
cp /opt/cts-lite/deployment/systemd/cts-lite.service /etc/systemd/system/
cp /opt/cts-lite/deployment/systemd/cts-lite.env /etc/cts-lite/

# Install nginx configuration
cp /opt/cts-lite/deployment/nginx/cts-lite.conf /etc/nginx/sites-available/
ln -sf /etc/nginx/sites-available/cts-lite.conf /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Reload systemd and enable services
systemctl daemon-reload
systemctl enable cts-lite
systemctl enable nginx

echo "✓ Service configuration installed"

# Validate installation
echo "Validating installation..."
sudo -u cts /opt/cts-lite/venv/bin/python -c "
from comma_tools.api.config import ConfigManager
config = ConfigManager().load_config()
print(f'✓ Configuration valid: {config.environment}')
"

echo ""
echo "=== Installation Complete ==="
echo ""
echo "Next steps:"
echo "1. Review configuration in /etc/cts-lite/cts-lite.env"
echo "2. Start services: systemctl start cts-lite nginx"
echo "3. Check status: systemctl status cts-lite"
echo "4. Test service: curl http://localhost/health"
echo ""
```

#### Create `deployment/scripts/health-check.sh`
**Purpose**: Health monitoring script for operational use
```bash
#!/bin/bash

# CTS-Lite Health Check Script
set -e

SERVICE_URL="http://localhost:8000"
TIMEOUT=10

echo "=== CTS-Lite Health Check ==="

# Check if service is responding
echo -n "Service availability... "
if curl -sf --max-time $TIMEOUT "$SERVICE_URL/health/simple" > /dev/null; then
    echo "✓ OK"
else
    echo "✗ FAILED - Service not responding"
    exit 1
fi

# Detailed health check
echo -n "Detailed health status... "
health_response=$(curl -sf --max-time $TIMEOUT "$SERVICE_URL/health")
overall_status=$(echo "$health_response" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(data.get('status', 'unknown'))
")

case "$overall_status" in
    "healthy")
        echo "✓ HEALTHY"
        ;;
    "degraded")
        echo "⚠ DEGRADED"
        echo "Some health checks failed, but service is operational"
        ;;
    *)
        echo "✗ UNHEALTHY"
        echo "Service health checks failed"
        exit 1
        ;;
esac

# Check tool registry
echo -n "Tool registry... "
tools_response=$(curl -sf --max-time $TIMEOUT "$SERVICE_URL/v1/capabilities")
tool_count=$(echo "$tools_response" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(len(data.get('tools', [])))
")

if [ "$tool_count" -gt 0 ]; then
    echo "✓ $tool_count tools available"
else
    echo "✗ No tools registered"
    exit 1
fi

# Check metrics
echo -n "Metrics collection... "
metrics_response=$(curl -sf --max-time $TIMEOUT "$SERVICE_URL/metrics")
if echo "$metrics_response" | grep -q "execution_metrics"; then
    echo "✓ Metrics available"
else
    echo "⚠ Metrics not available"
fi

echo ""
echo "=== Health Check Complete ==="
exit 0
```

### **4. Production Documentation (CRITICAL)**

#### Create `docs/DEPLOYMENT.md`
**Purpose**: Comprehensive production deployment guide
**Requirements**:
- System requirements
- Installation procedures
- Configuration guidance
- Security recommendations
- Operational procedures

```markdown
# CTS-Lite Production Deployment Guide

## Overview

This guide covers the production deployment of CTS-Lite, the API service that replaces standalone comma-tools CLI utilities with a unified, web-accessible service.

## System Requirements

### Hardware Requirements
- **CPU**: 2+ cores (4+ cores recommended for high load)
- **Memory**: 4GB RAM minimum (8GB recommended) 
- **Storage**: 10GB available disk space (more for artifact storage)
- **Network**: Stable internet connection for dependency installation

### Software Requirements
- **Operating System**: Ubuntu 20.04 LTS or newer (other Linux distributions supported)
- **Python**: 3.12 or higher
- **Docker**: 20.10+ (optional, for containerized deployment)
- **SystemD**: For service management
- **Nginx**: For reverse proxy (recommended)

## Installation Methods

### Method 1: Automated Installation (Recommended)

```bash
# Download and run installation script
curl -fsSL https://raw.githubusercontent.com/anteew/comma-tools/main/deployment/scripts/install.sh | sudo bash

# Or download first to review:
wget https://raw.githubusercontent.com/anteew/comma-tools/main/deployment/scripts/install.sh
sudo bash install.sh
```

### Method 2: Docker Deployment

```bash
# Clone repository
git clone https://github.com/anteew/comma-tools.git
cd comma-tools

# Deploy with Docker Compose
docker-compose -f deployment/docker/docker-compose.yml up -d

# Check status
docker-compose -f deployment/docker/docker-compose.yml ps
```

### Method 3: Manual Installation

See [MANUAL_INSTALLATION.md](MANUAL_INSTALLATION.md) for step-by-step manual setup.

## Configuration

### Environment Configuration

Edit `/etc/cts-lite/cts-lite.env`:

```bash
# Production Environment Settings
CTS_ENVIRONMENT=production
CTS_LOG_LEVEL=INFO

# Resource Limits
CTS_MAX_CONCURRENT_RUNS=5           # Concurrent tool executions
CTS_TOOL_TIMEOUT_SECONDS=600        # 10 minute timeout
CTS_MAX_ARTIFACT_SIZE_MB=200        # Maximum artifact size

# Storage Paths
CTS_BASE_STORAGE_PATH=/var/lib/cts  # Artifact storage
CTS_LOG_DIRECTORY=/var/log/cts      # Log files
CTS_TEMP_DIRECTORY=/tmp/cts         # Temporary files

# Security & Performance
CTS_ENABLE_RATE_LIMITING=true
CTS_MAX_REQUESTS_PER_MINUTE=120
CTS_CORS_ALLOWED_ORIGINS="https://yourdomain.com"

# Monitoring
CTS_ENABLE_METRICS=true
CTS_ENABLE_HEALTH_CHECKS=true
```

### Security Configuration

1. **User Isolation**: Service runs as dedicated `cts` user
2. **File Permissions**: Restrict access to configuration and data directories
3. **Rate Limiting**: Enable request rate limiting in production
4. **CORS**: Configure allowed origins for web access
5. **Firewall**: Only expose necessary ports (80, 443)

```bash
# Configure firewall
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
```

## Service Management

### Start/Stop/Restart Service

```bash
# Start service
sudo systemctl start cts-lite

# Stop service  
sudo systemctl stop cts-lite

# Restart service
sudo systemctl restart cts-lite

# Check status
sudo systemctl status cts-lite

# View logs
sudo journalctl -u cts-lite -f
```

### Health Monitoring

```bash
# Quick health check
curl http://localhost:8000/health/simple

# Detailed health check
curl http://localhost:8000/health | jq

# Run health check script
sudo /opt/cts-lite/deployment/scripts/health-check.sh
```

## Backup & Recovery

### Backup Strategy

1. **Configuration**: Backup `/etc/cts-lite/`
2. **Artifacts**: Backup `/var/lib/cts/` (can be large)
3. **Logs**: Optional backup of `/var/log/cts/`

```bash
# Create backup
sudo tar -czf cts-lite-backup-$(date +%Y%m%d).tar.gz \
  /etc/cts-lite/ \
  /var/lib/cts/ \
  /opt/cts-lite/deployment/
```

### Recovery Procedure

1. Restore configuration files
2. Restore artifact storage
3. Restart service
4. Validate health checks

## Troubleshooting

### Common Issues

#### Service Won't Start
```bash
# Check service status
sudo systemctl status cts-lite

# Check configuration
sudo -u cts /opt/cts-lite/venv/bin/python -c "
from comma_tools.api.config import ConfigManager
ConfigManager().load_config()
"
```

#### High Memory Usage
```bash
# Check memory usage
ps aux | grep cts-lite

# Reduce concurrent runs
sudo sed -i 's/CTS_MAX_CONCURRENT_RUNS=.*/CTS_MAX_CONCURRENT_RUNS=2/' /etc/cts-lite/cts-lite.env
sudo systemctl restart cts-lite
```

#### Storage Full
```bash
# Check disk usage
df -h /var/lib/cts

# Clean old artifacts (adjust days as needed)
find /var/lib/cts -type f -mtime +7 -delete
```

## Performance Tuning

### Production Optimization

1. **Concurrent Runs**: Adjust based on CPU/memory capacity
2. **Timeout Values**: Increase for large files, decrease for responsiveness
3. **Artifact Retention**: Balance storage space with user needs
4. **Log Levels**: Use INFO or WARNING in production

### Monitoring Metrics

Access metrics at `http://localhost:8000/metrics`:

- Execution success rates
- Response times
- Resource usage
- Tool usage patterns

## Security Hardening

### Additional Security Measures

1. **SSL/TLS**: Configure HTTPS with valid certificates
2. **Authentication**: Enable authentication for production use
3. **Network Isolation**: Use VPN or private networks
4. **Log Monitoring**: Monitor logs for suspicious activity

```bash
# Enable authentication (example)
echo "CTS_REQUIRE_AUTHENTICATION=true" >> /etc/cts-lite/cts-lite.env
sudo systemctl restart cts-lite
```

## Maintenance

### Regular Maintenance Tasks

1. **Log Rotation**: Configured automatically via systemd
2. **Artifact Cleanup**: Clean old artifacts based on retention policy
3. **Security Updates**: Keep system packages updated
4. **Health Monitoring**: Regular health check validation

```bash
# Weekly maintenance script example
#!/bin/bash
# Clean old artifacts
find /var/lib/cts -type f -mtime +30 -delete

# Update system packages
apt update && apt upgrade -y

# Restart service to clear memory
systemctl restart cts-lite

# Validate health
curl -f http://localhost:8000/health/simple || systemctl restart cts-lite
```

## Scaling & High Availability

For high-traffic deployments:

1. **Load Balancing**: Multiple CTS-Lite instances behind load balancer
2. **Shared Storage**: NFS or similar for artifact sharing
3. **Database**: External database for run metadata (future enhancement)
4. **Monitoring**: Prometheus + Grafana for comprehensive monitoring

Contact the development team for assistance with high-availability deployments.
```

#### Create `docs/MIGRATION_GUIDE.md`
**Purpose**: Guide users migrating from standalone CLI tools
```markdown
# Migration Guide: From Standalone Tools to CTS-Lite

## Overview

This guide helps users migrate from standalone comma-tools CLI utilities to the new CTS-Lite API service, providing better user experience, unified interface, and enhanced capabilities.

## Quick Migration Reference

### Command Translation

| Old Standalone Command | New CTS Command | Notes |
|------------------------|----------------|-------|
| `python cruise_control_analyzer.py file.zst` | `cts run cruise-control-analyzer --path file.zst --wait` | Automatic result download |
| `python rlog_to_csv.py --input file.zst` | `cts run rlog-to-csv --path file.zst --wait` | Simplified parameters |
| `python can_bitwatch.py --csv file.csv` | `cts run can-bitwatch --path file.csv --wait` | Enhanced bit monitoring |

### Parameter Mapping

#### Cruise Control Analyzer
```bash
# Old way
python cruise_control_analyzer.py route.zst --speed-min 50 --speed-max 65

# New way  
cts run cruise-control-analyzer --path route.zst -p speed_min=50 -p speed_max=65 --wait
```

#### RLog to CSV Converter
```bash
# Old way
python rlog_to_csv.py --input route.zst --output converted.csv

# New way
cts run rlog-to-csv --path route.zst --wait
# Output automatically saved with meaningful names
```

### Migration Benefits

1. **Unified Interface**: Single `cts` command for all tools
2. **Better Error Messages**: Clear, actionable error reporting
3. **Automatic Downloads**: Results automatically saved locally
4. **Progress Tracking**: Real-time progress with `--follow`
5. **Background Execution**: Run without `--wait` for async operation
6. **Web Interface**: Optional web UI for analysis management

## Step-by-Step Migration

### Step 1: Install CTS CLI

```bash
# Install the new CLI tool
pip install comma-tools[cli]

# Verify installation
cts --help
cts cap  # List available tools
```

### Step 2: Test with Existing Data

```bash
# Test with your existing log files
cts run cruise-control-analyzer --path your_existing_log.zst --wait --follow

# Compare results with standalone tool
python cruise_control_analyzer.py your_existing_log.zst
```

### Step 3: Update Scripts and Workflows

#### Before (Standalone)
```bash
#!/bin/bash
# Old analysis script
for file in *.zst; do
    echo "Processing $file..."
    python cruise_control_analyzer.py "$file" --speed-min 45
    if [ $? -eq 0 ]; then
        echo "✓ Success: $file"
    else
        echo "✗ Failed: $file"
    fi
done
```

#### After (CTS-Lite)
```bash
#!/bin/bash
# New analysis script
for file in *.zst; do
    echo "Processing $file..."
    if cts run cruise-control-analyzer --path "$file" -p speed_min=45 --wait; then
        echo "✓ Success: $file (artifacts downloaded automatically)"
    else
        echo "✗ Failed: $file"
    fi
done
```

### Step 4: Leverage New Capabilities

```bash
# Async execution - start multiple analyses
cts run cruise-control-analyzer --path file1.zst -p speed_min=45 &
cts run cruise-control-analyzer --path file2.zst -p speed_min=50 &
cts run cruise-control-analyzer --path file3.zst -p speed_min=55 &

# Monitor progress
cts runs list --active

# Get results when ready
cts runs get --run-id abc123 --download
```

## Advanced Features

### 1. Batch Processing
```bash
# Process multiple files efficiently
cts batch cruise-control-analyzer *.zst --params speed_min=45,speed_max=65
```

### 2. Result Management
```bash
# List previous runs
cts runs list --tool cruise-control-analyzer --last 10

# Re-download results
cts runs get --run-id abc123 --download

# Clean up old results
cts runs clean --older-than 30d
```

### 3. Configuration Profiles
```bash
# Save common parameter sets
cts config save-profile highway-analysis speed_min=55,speed_max=75

# Use saved profile
cts run cruise-control-analyzer --path route.zst --profile highway-analysis --wait
```

## Troubleshooting Migration Issues

### Common Migration Problems

#### Old Scripts Still Using Standalone Tools
**Problem**: Existing scripts call Python files directly
**Solution**: 
```bash
# Create aliases for gradual migration
alias cruise_control_analyzer="cts run cruise-control-analyzer --path"
alias rlog_to_csv="cts run rlog-to-csv --path" 
```

#### Different Output File Names
**Problem**: Scripts expect specific output file names
**Solution**: Use `--output-dir` and symbolic links
```bash
cts run cruise-control-analyzer --path file.zst --wait --output-dir results/
ln -s results/candidates.v1.csv expected_output.csv
```

#### Parameter Format Differences  
**Problem**: Parameter names or formats changed
**Solution**: Check parameter mapping with `cts run tool-name --help`

#### Performance Differences
**Problem**: CTS-Lite seems slower than standalone
**Solution**: 
- Use `--wait` to avoid API polling overhead
- Run CTS-Lite service locally to eliminate network latency
- Consider batch processing for multiple files

### Getting Help

#### Built-in Help
```bash
# General help
cts --help

# Tool-specific help
cts run cruise-control-analyzer --help

# Parameter details
cts describe cruise-control-analyzer
```

#### Service Information
```bash
# Check service status
cts status

# View service capabilities  
cts cap

# Test service connectivity
cts ping
```

## Performance Comparison

### Standalone vs CTS-Lite Performance

| Metric | Standalone | CTS-Lite | Notes |
|--------|------------|----------|-------|
| First run (cold start) | ~30s | ~35s | CTS includes setup overhead |
| Subsequent runs | ~25s | ~25s | CTS caches dependencies |
| Multiple concurrent | Manual | Automatic | CTS handles concurrency |
| Error recovery | Manual | Automatic | CTS includes retry logic |
| Result organization | Manual | Automatic | CTS organizes outputs |

### Optimization Tips

1. **Local Service**: Run CTS-Lite locally for best performance
2. **Batch Processing**: Use batch operations for multiple files
3. **Concurrent Execution**: Leverage automatic concurrency management
4. **Caching**: CTS-Lite caches dependencies and intermediate results

## Timeline & Support

### Migration Timeline
- **Phase 1**: Install and test CTS-Lite alongside existing tools
- **Phase 2**: Migrate non-critical scripts and workflows
- **Phase 3**: Migrate production workflows with validation
- **Phase 4**: Deprecate standalone tools (future)

### Standalone Tool Support
- **Current**: Full support for both standalone and CTS-Lite
- **6 months**: Standalone tools in maintenance mode  
- **12 months**: CTS-Lite becomes primary supported method
- **18 months**: Standalone tools deprecated (planned)

### Getting Support
- **Documentation**: Comprehensive docs at https://comma-tools.readthedocs.io
- **Issues**: Report problems at https://github.com/anteew/comma-tools/issues  
- **Discussions**: Community support at https://github.com/anteew/comma-tools/discussions

## Success Stories

### Example: Automated CI Pipeline
**Before**: Complex bash scripts managing Python environments
**After**: Single `cts` commands with automatic result collection

### Example: Team Collaboration
**Before**: Manual result sharing and version management
**After**: Centralized CTS-Lite service with automatic result organization

Ready to migrate? Start with `cts cap` to see available tools!
```

## Implementation Priority

### **🔥 CRITICAL (Must Complete)**
1. **Docker Containerization**: Production-ready container with multi-stage build
2. **SystemD Integration**: Service files for production deployment
3. **Installation Scripts**: Automated deployment and health checking
4. **Deployment Documentation**: Complete production deployment guide
5. **Migration Guide**: Help users transition from standalone tools

### **📋 IMPORTANT (Should Complete)**  
1. **Nginx Configuration**: Reverse proxy setup for production
2. **Security Hardening**: Production security best practices
3. **Backup Procedures**: Data protection and recovery processes
4. **Monitoring Integration**: Integration with external monitoring systems

## Success Criteria

### **Deployment Readiness**
- [ ] Docker container builds and runs successfully
- [ ] SystemD service installs and starts properly
- [ ] Health checks pass in containerized environment
- [ ] Installation script completes without errors
- [ ] Service survives system reboots

### **Documentation Completeness**
- [ ] Deployment guide covers all installation methods
- [ ] Migration guide provides clear command translations
- [ ] Security recommendations are comprehensive
- [ ] Troubleshooting section addresses common issues
- [ ] Performance tuning guidance is actionable

### **Production Validation**
```bash
# Ultimate production deployment test:
sudo ./deployment/scripts/install.sh     # Install succeeds
systemctl start cts-lite                 # Service starts
curl http://localhost:8000/health        # Health check passes
cts cap                                   # CLI works with service
cts run cruise-control-analyzer --path test.zst --wait  # End-to-end success
```

## Architecture Compliance

### **Integration with All Previous Phases**
- **Error Handling (4A)**: Production deployment includes error recovery
- **Monitoring (4B)**: Health checks and metrics integrated into deployment
- **Testing (4C)**: Deployment validated through comprehensive test suite
- **Maintain Quality**: Production deployment meets MVP quality standards

### **Deployment Philosophy**
- **Production First**: All deployment artifacts ready for enterprise use
- **Security Conscious**: Follow security best practices by default
- **Operational Excellence**: Include monitoring, backup, and recovery procedures
- **User Experience**: Make deployment and migration as smooth as possible

---

## 🎉 MVP COMPLETION!

**After Phase 4D completion, CTS-Lite MVP is 100% COMPLETE:**

✅ **Full Feature Parity**: All standalone CLI tools available via unified API
✅ **Superior User Experience**: Better error handling, progress tracking, result management  
✅ **Production Ready**: Docker deployment, service integration, monitoring
✅ **Enterprise Grade**: Security, scalability, operational procedures
✅ **Complete Documentation**: Deployment guides, migration assistance, troubleshooting

**Timeline**: CTS-Lite ready for production deployment and CLI tool replacement within 1-2 weeks of Phase 4D completion.

*Congratulations! You've successfully transformed comma-tools from standalone utilities into a production-grade API service with superior user experience and enterprise reliability.*