# Phase 4C Implementation Guide: Container-Based User Experience

**Assigned to**: AI Coding Agent  
**Estimated Time**: 2-3 hours  
**Priority**: CRITICAL - Eliminate dependency complexity with containerization  
**Architecture Review Required**: Yes - Container-first design with native fallback  
**Previous Phase**: Phase 4B (Configuration & Monitoring) - Must be completed first

## Objective

Implement a container-first approach to solve the new user experience problem. Users should be able to analyze openpilot logs without dealing with Python dependency management, openpilot checkouts, or server lifecycle management.

**Goal**: Create a self-contained Docker experience with GitHub Container Registry (GHCR) while preserving client/server architecture for MCP integration and maintaining development workflows.

## Phase 4C Scope: Container-First Implementation

### **Core Requirements (Non-Negotiable)**

1. **Container-Native Design**: Everything runs in Docker containers with GHCR distribution
2. **Preserve Client/Server Architecture**: Maintain separation for future MCP integration
3. **Development Workflow Compatibility**: Native development and CI must continue working
4. **Multi-Mode Operations**: Support interactive, daemon, and external API access modes

### **Container Architecture Overview**

**Three Operational Modes**:

1. **Interactive Mode**: CLI + Server in same container (simplest UX)
2. **Daemon Mode**: Server-only container with external port (for external clients/MCP)  
3. **Native Mode**: Traditional development setup (preserve existing workflows)

**Container Contents**:
- Complete openpilot environment with dependencies
- CTS-Lite server (`cts-lite`)
- CTS CLI client (`cts`)
- Startup launcher app for easy container management

**Distribution**: GitHub Container Registry (`ghcr.io/anteew/comma-tools`)

## **Phase 4C Implementation Plan**

### **Phase 4C-A: Core Containerization (CRITICAL - This Phase)**

#### **1. Docker Infrastructure Setup**

**Create `Dockerfile`** - Multi-stage build for efficiency:
```dockerfile
# Base stage with openpilot environment
FROM python:3.12-slim as openpilot-base
RUN apt-get update && apt-get install -y git
RUN git clone https://github.com/commaai/openpilot.git /openpilot
WORKDIR /openpilot  
RUN git submodule update --init --recursive

# Application stage
FROM python:3.12-slim as app
COPY --from=openpilot-base /openpilot /openpilot
COPY . /comma-tools
WORKDIR /comma-tools

# Install all dependencies
RUN pip install -e ".[api,client,dev]"

# Create startup script
COPY docker/startup.py /usr/local/bin/comma-tools-startup
RUN chmod +x /usr/local/bin/comma-tools-startup

EXPOSE 8080
ENTRYPOINT ["/usr/local/bin/comma-tools-startup"]
```

**Create `docker/startup.py`** - Intelligent container launcher:
```python
#!/usr/bin/env python3
"""
Comma Tools Container Startup Launcher

Modes:
  interactive  - Start shell with CLI available (default)
  daemon      - Start server only, expose port 8080  
  cli         - Direct CLI access (bypasses server)
  shell       - Plain shell access for development
"""
import sys
import subprocess
import os

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "interactive"
    
    if mode == "interactive":
        start_interactive_mode()
    elif mode == "daemon":
        start_daemon_mode()
    elif mode == "cli":
        start_cli_mode(sys.argv[2:])
    elif mode == "shell":
        start_shell_mode()
    else:
        print(f"Unknown mode: {mode}")
        sys.exit(1)

def start_interactive_mode():
    """Start server in background, then interactive shell."""
    print("🚀 Starting Comma Tools Interactive Container")
    print("Server starting in background...")
    
    # Start server in background
    subprocess.Popen(["cts-lite"], stdout=subprocess.DEVNULL)
    
    # Wait for server ready
    import time, httpx
    for _ in range(30):
        try:
            httpx.get("http://localhost:8080/health", timeout=1)
            break
        except:
            time.sleep(1)
    else:
        print("❌ Server failed to start")
        sys.exit(1)
        
    print("✓ Server ready at http://localhost:8080")
    print("💡 Try: cts run cruise-control-analyzer --help")
    print("💡 Exit: type 'exit' or Ctrl+D")
    print()
    
    # Start interactive shell
    os.execv("/bin/bash", ["/bin/bash"])

def start_daemon_mode():
    """Start server only, for external access."""
    print("🚀 Starting CTS-Lite Server (daemon mode)")
    os.execv("/usr/local/bin/cts-lite", ["cts-lite", "--host", "0.0.0.0"])

def start_cli_mode(args):
    """Direct CLI mode - start server and run command."""
    subprocess.Popen(["cts-lite"], stdout=subprocess.DEVNULL)
    # Wait for server, then run CLI command
    # Implementation similar to interactive but exec the CLI command
    
def start_shell_mode():
    """Plain shell for development."""
    print("🐚 Comma Tools Development Shell")
    os.execv("/bin/bash", ["/bin/bash"])

if __name__ == "__main__":
    main()
```

#### **2. GitHub Container Registry Integration**

**Create `.github/workflows/container.yml`**:
```yaml
name: Build and Publish Container

on:
  push:
    branches: [main]
    tags: ['v*']
  pull_request:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
      
    steps:
    - name: Checkout
      uses: actions/checkout@v4
      with:
        lfs: true
        
    - name: Set up Docker Buildx  
      uses: docker/setup-buildx-action@v3
      
    - name: Login to GHCR
      if: github.event_name != 'pull_request'
      uses: docker/login-action@v3
      with:
        registry: ghcr.io
        username: ${{ github.actor }}
        password: ${{ secrets.GITHUB_TOKEN }}
        
    - name: Extract metadata
      id: meta
      uses: docker/metadata-action@v5
      with:
        images: ghcr.io/anteew/comma-tools
        tags: |
          type=ref,event=branch
          type=ref,event=pr
          type=semver,pattern={{version}}
          type=semver,pattern={{major}}.{{minor}}
          
    - name: Build and push
      uses: docker/build-push-action@v5
      with:
        context: .
        platforms: linux/amd64,linux/arm64
        push: ${{ github.event_name != 'pull_request' }}
        tags: ${{ steps.meta.outputs.tags }}
        labels: ${{ steps.meta.outputs.labels }}
        cache-from: type=gha
        cache-to: type=gha,mode=max
```

#### **3. User Experience Implementation**

**Three Usage Patterns**:

```bash
# Pattern 1: Interactive Mode (simplest - everything in container)
docker run -it --rm -v $(pwd):/workspace ghcr.io/anteew/comma-tools
# Drops into shell with server running, CLI available
# Files in /workspace, analysis results saved locally

# Pattern 2: One-shot Analysis (convenient for single runs)
docker run --rm -v $(pwd):/workspace ghcr.io/anteew/comma-tools cli \
  cts run cruise-control-analyzer --path /workspace/my-log.zst

# Pattern 3: Daemon Mode (for external clients/MCP)
docker run -d -p 8080:8080 --name cts-server ghcr.io/anteew/comma-tools daemon
# Server available at localhost:8080 for external clients
```

### **Phase 4C-B: User-Friendly Wrapper (Future Phase)**

**Create `bin/comma-tools`** - Native launcher script (future implementation):
```python
#!/usr/bin/env python3
"""
Comma Tools Launcher - Simplified container management
Usage: comma-tools [interactive|daemon|cli] [args...]
"""
# This will be implemented in a future phase
# Handles: docker pull, container lifecycle, volume mounts, etc.
```

## **Implementation Priority**

### **🔥 CRITICAL (This Phase - 4C-A)**
1. **Dockerfile Creation**: Multi-stage build with openpilot environment
2. **Container Startup Script**: Intelligent mode switching (`startup.py`)
3. **GHCR CI Integration**: Automated builds and publishing
4. **Basic Usage Documentation**: Container usage patterns

### **📋 FUTURE PHASE (4C-B)**  
1. **Native Launcher Script**: User-friendly wrapper for Docker commands
2. **Advanced Container Features**: Volume management, port detection, cleanup
3. **Development Enhancements**: Dev container configuration, hot reload
4. **Integration Testing**: Automated container testing in CI

## **User Journey Examples**

### **New User - Zero Setup**
```bash
# Complete analysis without any local installation
docker run -it --rm -v $(pwd):/workspace ghcr.io/anteew/comma-tools

# Inside container:
# 🚀 Starting Comma Tools Interactive Container  
# ✓ Server ready at http://localhost:8080
# 💡 Try: cts run cruise-control-analyzer --help

cts run cruise-control-analyzer --path /workspace/my-route.zst --wait
# Analysis runs, results saved to /workspace
exit
# Container auto-removed, no cleanup needed
```

### **External Client Integration (MCP Ready)**
```bash
# Start daemon for external access
docker run -d -p 8080:8080 --name cts ghcr.io/anteew/comma-tools daemon

# MCP server or external client connects to localhost:8080
curl http://localhost:8080/v1/capabilities

# Cleanup when done
docker stop cts  # Auto-removes due to --rm
```

### **Developer Workflow (Preserved)**
```bash
# Native development still works
git clone https://github.com/anteew/comma-tools.git
cd comma-tools
pip install -e ".[dev]"
pytest tests/  # All existing workflows unchanged
```

## **Success Criteria**

### **Container Experience Validation**
```bash
# The ultimate new user test - zero local setup
docker run -it --rm -v $(pwd):/workspace ghcr.io/anteew/comma-tools
# Should drop into working environment with server ready

cts run cruise-control-analyzer --path /workspace/test.zst --wait
# Should complete analysis successfully

exit
# Should clean up automatically, no stale containers
```

### **Validation Requirements**
- [ ] Container builds successfully in CI with multi-arch support
- [ ] Interactive mode provides working CLI + server environment
- [ ] Daemon mode exposes server on port 8080 for external access
- [ ] Volume mounts work correctly for file input/output
- [ ] Native development workflows remain unchanged
- [ ] No breaking changes to existing CI/testing
- [ ] Container images published to GHCR automatically

### **Testing Integration**

#### **Container Testing in CI**
```yaml
# Add to existing .github/workflows/test.yml
container-integration:
  runs-on: ubuntu-latest
  steps:
  - name: Test Container Interactive Mode
    run: |
      docker run --rm ghcr.io/anteew/comma-tools:main cli \
        cts cap
        
  - name: Test Container Daemon Mode  
    run: |
      docker run -d -p 8080:8080 --name test-cts ghcr.io/anteew/comma-tools:main daemon
      sleep 5
      curl http://localhost:8080/health
      docker stop test-cts
```

#### **Multi-Mode Validation**
- Container interactive mode works end-to-end
- Daemon mode serves API correctly
- CLI mode executes single commands
- Volume mounts preserve file permissions
- Container cleanup works properly

## Implementation Priority

### **🔥 CRITICAL (Must Complete)**
1. **Server Auto-Detection**: `cts` client detects server availability
2. **Auto-Start Logic**: Client starts server when needed  
3. **Session Management**: Server lifecycle tied to usage
4. **Cleanup Mechanisms**: Proper process cleanup when done

### **📋 IMPORTANT (Should Complete)**  
1. **Enhanced Documentation**: "Just works" quick start guide
2. **Error Handling**: Clear messages for common failure modes
3. **Testing Updates**: Ensure CI/testing compatibility
4. **Backward Compatibility**: Manual server mode still works

## **Architecture Compliance**

### **Preserved Design Principles**
- **Client/Server Separation**: Both CLI and server in container, architecture intact
- **Service-First Design**: Business logic remains in analyzer classes  
- **API Layer Integrity**: FastAPI endpoints stay thin, just containerized
- **MCP Integration Ready**: External clients connect to daemon mode via HTTP

### **Enhanced Deployment Model**
- **Container-First Distribution**: Primary delivery via GHCR
- **Development Flexibility**: Native workflows preserved for contributors
- **Multi-Platform Support**: ARM64 + AMD64 builds
- **Zero Dependency Management**: All deps baked into container

### **Future Phase Extensions**
- **Phase 4D**: Native launcher wrapper (`bin/comma-tools`) for easier Docker management
- **Development Containers**: Dev container configuration for VS Code integration
- **Advanced Features**: Port detection, volume management, container health monitoring

---

**Outcome**: Users get a "just works" experience via containers while developers retain full native workflow flexibility. MCP integration becomes trivial - just point to the daemon mode container endpoint.

**Next Phase**: Phase 4D (User-Friendly Wrapper & Documentation) adds the native launcher script and comprehensive documentation for both container and native usage patterns.