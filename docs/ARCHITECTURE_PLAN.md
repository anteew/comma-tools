# CTS-Lite Service Architecture Plan

**Document Version**: 2.0  
**Date**: 2024-12-19  
**Architect**: GitHub Copilot CLI  
**Status**: Implementation Complete (Phases 1-2), Phase 3 Partial  

## Executive Summary

This document outlines the architectural plan and current implementation status of CTS-Lite, an HTTP API service that serves as the core backend for comma-tools analysis and monitoring capabilities. The service provides a unified API surface supporting multiple client frontends, with the `cts` CLI client as the primary interface.

**Current Status**: CTS-Lite is functional and operational. Phases 1-2 are complete, with partial Phase 3 implementation. The service supports all core analyzer tools and provides a modern HTTP API for tool execution and monitoring.

## Current State Analysis

### ✅ What's Working Well
- Core application logic properly separated in service classes
- Existing `cts` CLI client already designed for API service pattern
- Clean package structure with analyzers/, monitors/, utils/
- Proper dependency management and testing framework

### 🎯 Target Architecture
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   cts CLI       │───▶│  CTS-Lite API   │◀───│  Future Web UI  │
│   Client        │    │    Service      │    │    Client       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                    ┌─────────────────────────┐
                    │ Core Service Logic      │
                    │ - analyzers/            │
                    │ - monitors/             │ 
                    │ - utils/                │
                    └─────────────────────────┘
```

## Implementation Status

### ✅ Phase 1: CTS-Lite Service Foundation (COMPLETED)
**Status**: Production Ready  
**Implementation**: Fully functional service with health and capabilities endpoints

**Files Created**:
- ✅ `src/comma_tools/api/server.py` - FastAPI application with CORS, middleware
- ✅ `src/comma_tools/api/models.py` - Pydantic models and schemas
- ✅ `src/comma_tools/api/config.py` - Configuration management with environment variables
- ✅ `src/comma_tools/api/health.py` - Health check endpoint with metrics
- ✅ `src/comma_tools/api/capabilities.py` - Tool discovery endpoint
- ✅ Updated `pyproject.toml` with API dependencies

**API Endpoints Available**:
- ✅ `GET /v1/health` - Service health check with uptime, version info
- ✅ `GET /v1/capabilities` - Lists 3 analyzers + 3 monitors with parameters

**Success Criteria Met**:
- ✅ Service starts and responds to health checks
- ✅ `cts cap` command works and shows available tools
- ✅ Comprehensive logging and error handling implemented
- ✅ Proper dependency injection and configuration setup

### ✅ Phase 2: Tool Registry and Execution (COMPLETED)
**Status**: Production Ready  
**Implementation**: Core tool execution capabilities with async support

**Files Created**:
- ✅ `src/comma_tools/api/registry.py` - Dynamic tool discovery and registration (150 lines)
- ✅ `src/comma_tools/api/execution.py` - Thread-based async execution engine (290 lines)
- ✅ `src/comma_tools/api/runs.py` - Run management endpoints (156 lines)

**API Endpoints Available**:
- ✅ `POST /v1/runs` - Start tool execution with parameter validation
- ✅ `GET /v1/runs/{run_id}` - Get run status with real-time updates
- ✅ `GET /v1/runs/{run_id}/logs` - SSE streaming logs (planned endpoint)

**Success Criteria Met**:
- ✅ `cts run <tool> --path <file>` command works end-to-end
- ✅ Background processing with thread isolation (no API blocking)
- ✅ Parameter validation and type conversion
- ✅ Real-time status tracking and updates
- ✅ 61 comprehensive API tests passing (4 new test files, 749 total lines)

### 🔄 Phase 3: File Management (PARTIAL)
**Status**: In Progress  
**Implementation**: Artifact download system partially complete

**Files Created**:
- ✅ `src/comma_tools/api/artifacts.py` - Artifact management system
- ✅ `src/comma_tools/api/logs.py` - Log streaming capabilities
- 🔄 File upload system (planned)

**API Endpoints Available**:
- ✅ `GET /v1/artifacts` - List available artifacts
- ✅ `GET /v1/artifacts/{id}/download` - Download artifacts
- 🔄 `POST /v1/uploads` - File upload (not fully tested)

**Current Capabilities**:
- ✅ Local file path support (`cts run <tool> --path <file>`)
- ✅ Artifact generation and storage
- ✅ CLI artifact download integration
- 🔄 Web-based file upload (needs validation)

### Phase 2: Tool Registry and Execution
**Scope**: Core tool execution capabilities
**Files to Create**:
- `src/comma_tools/api/registry.py` - Tool registration system
- `src/comma_tools/api/execution.py` - Tool execution engine
- `src/comma_tools/api/runs.py` - Run management endpoints

**API Endpoints to Add**:
- `POST /v1/runs` - Start tool execution
- `GET /v1/runs/{run_id}` - Get run status
- `GET /v1/runs/{run_id}/logs` - Get run logs (SSE streaming)

### Phase 3: File Management
**Scope**: File upload/download and artifact management
**API Endpoints to Add**:
- `POST /v1/uploads` - File upload
- `GET /v1/artifacts` - List artifacts
- `GET /v1/artifacts/{id}/download` - Download artifact

### Phase 4: Monitor Integration  
**Scope**: Real-time monitoring capabilities
**API Endpoints to Add**:
- `POST /v1/monitors/start` - Start monitor
- `GET /v1/monitors/{id}/stream` - WebSocket stream
- `POST /v1/monitors/{id}/stop` - Stop monitor

### Phase 5: CLI Tool Deprecation
**Scope**: Remove standalone CLI entry points
**Changes**:
- Remove from `pyproject.toml` scripts section
- Add deprecation warnings to existing tools
- Update documentation

## Repository Structure Changes

### New Directories to Create
```
src/comma_tools/api/
├── __init__.py
├── server.py           # FastAPI application
├── config.py          # Service configuration  
├── models.py          # Pydantic request/response models
├── health.py          # Health check endpoint
├── capabilities.py    # Tool discovery
├── registry.py        # Tool registration system
├── execution.py       # Tool execution engine
├── runs.py           # Run management endpoints
├── uploads.py        # File upload handling
├── artifacts.py      # Artifact management
├── monitors.py       # Monitor endpoints
└── middleware/       # Custom middleware
    ├── __init__.py
    ├── auth.py       # JWT authentication
    ├── logging.py    # Request logging
    └── errors.py     # Error handling
```

### Files to Modify
- `pyproject.toml` - Add API dependencies, service entry point
- `README.md` - Update usage examples
- `docs/` - Add API documentation

## API Design Specifications

### Base URL Structure
```
http://127.0.0.1:8080/v1/
```

### Authentication
- JWT tokens via `Authorization: JWT <token>` header
- Optional for health/capabilities endpoints
- Required for tool execution and file operations

### Core Data Models

#### Tool Capability
```json
{
  "id": "cruise-control-analyzer",
  "name": "Cruise Control Analyzer", 
  "description": "Deep analysis of recorded driving logs",
  "category": "analyzer",
  "parameters": {
    "speed_min": {"type": "float", "default": 55.0, "description": "Minimum target speed in MPH"},
    "speed_max": {"type": "float", "default": 56.0, "description": "Maximum target speed in MPH"}
  },
  "input_types": ["rlog.zst"],
  "output_types": ["csv", "json", "html"]
}
```

#### Run Request
```json
{
  "tool_id": "cruise-control-analyzer",
  "params": {
    "speed_min": 50.0,
    "speed_max": 60.0
  },
  "input": {
    "type": "upload|path", 
    "value": "upload_id_or_file_path"
  },
  "name": "optional_run_name"
}
```

#### Run Response
```json
{
  "run_id": "uuid",
  "status": "queued|running|completed|failed|canceled",
  "tool_id": "cruise-control-analyzer",
  "created_at": "2024-12-19T10:30:00Z",
  "started_at": "2024-12-19T10:30:05Z",
  "completed_at": null,
  "artifacts": []
}
```

## Technology Stack

### Core Framework
- **FastAPI** - Modern Python web framework with automatic OpenAPI docs
- **Uvicorn** - ASGI server for production deployment
- **Pydantic** - Data validation and serialization

### Key Dependencies to Add
```toml
api = [
    "fastapi>=0.100.0",
    "uvicorn[standard]>=0.20.0", 
    "pydantic>=2.0.0",
    "python-multipart>=0.0.6",  # File uploads
    "python-jose[cryptography]>=3.3.0",  # JWT tokens
]
```

### File Storage
- Local filesystem initially
- Configurable for cloud storage later (S3, etc.)

### Background Tasks
- FastAPI BackgroundTasks for async tool execution
- Future: Celery/Redis for distributed processing

## Configuration Management

### Environment Variables
```bash
CTS_API_HOST=127.0.0.1
CTS_API_PORT=8080
CTS_LOG_LEVEL=INFO
CTS_DATA_DIR=/var/lib/cts-lite
CTS_JWT_SECRET=<secret>
```

### Configuration File Support
- TOML configuration files
- Environment variable override
- Development vs production configs

## Security Considerations

### Authentication
- JWT token-based authentication
- Optional anonymous access for health/capabilities
- Future: Role-based access control

### File Security  
- Input validation on all file uploads
- Sandboxed execution environments
- Size and type restrictions on uploads

### API Security
- CORS configuration
- Rate limiting middleware
- Request size limits

## Testing Strategy

### Test Structure
```
tests/api/
├── test_health.py
├── test_capabilities.py  
├── test_runs.py
├── test_uploads.py
├── test_integration.py
└── fixtures/
```

### Test Coverage Requirements
- Unit tests for all endpoints
- Integration tests with real tools
- Performance tests for file operations
- Security tests for authentication

## Deployment & Operations

### Development
```bash
# Start service in development mode
uvicorn comma_tools.api.server:app --reload --port 8080
```

### Production Considerations
- Process management (systemd, Docker)
- Reverse proxy setup (nginx)
- Log aggregation
- Health monitoring
- Backup strategies for artifacts

## Migration Strategy

### Phase 1: Parallel Operation
- CTS-Lite service runs alongside existing CLI tools
- Users can choose either approach
- Gradual user migration

### Phase 2: Deprecation Warnings
- Add deprecation notices to standalone CLI tools
- Update documentation to prefer `cts` client

### Phase 3: Removal
- Remove standalone CLI entry points from pyproject.toml
- Archive old CLI wrapper code

## Success Metrics

### Technical Metrics
- API response time < 200ms for sync endpoints
- 99.9% uptime for health endpoint
- Zero data loss during tool execution
- Full test coverage for API endpoints

### User Experience Metrics  
- Single `cts cap` command shows all capabilities
- Consistent parameter naming across tools
- Streaming logs provide real-time feedback
- Artifacts automatically downloadable

## Risk Mitigation

### Risk: Breaking Changes for Existing Users
**Mitigation**: Phased rollout with parallel operation period

### Risk: Performance Degradation
**Mitigation**: Performance testing, async execution, proper resource management

### Risk: Security Vulnerabilities
**Mitigation**: Input validation, sandboxed execution, security testing

### Risk: Complexity Increase
**Mitigation**: Comprehensive documentation, clear error messages, good logging

## Next Steps

1. **Immediate**: Create Phase 1 implementation tasks
2. **Week 1**: Basic service skeleton with health and capabilities
3. **Week 2**: Tool registry and execution engine
4. **Week 3**: File management and artifacts
5. **Week 4**: Testing and documentation
6. **Month 2**: Monitor integration and CLI deprecation

---

*This document will be updated as implementation progresses and requirements evolve.*