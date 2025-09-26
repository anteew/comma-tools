# Phase 1 Implementation Guide: CTS-Lite Service Foundation

**Assigned to**: Coding Agent  
**Estimated Time**: 4-6 hours  
**Priority**: High  
**Architecture Review Required**: Yes  

## Objective

Create the basic HTTP API service skeleton for CTS-Lite with health check and capabilities endpoints. This establishes the foundation for all future API development.

## Files to Implement

### 1. Core Service Files (REQUIRED)

#### `src/comma_tools/api/server.py`
**Purpose**: FastAPI application setup and routing
**Requirements**:
- FastAPI app instance with proper CORS configuration
- Include health and capabilities routers
- Basic error handling middleware
- Logging configuration
- Development vs production settings

**Key Features**:
- `/v1/health` endpoint integration
- `/v1/capabilities` endpoint integration
- Proper OpenAPI documentation setup
- CORS middleware for development

#### `src/comma_tools/api/config.py`
**Purpose**: Service configuration management  
**Requirements**:
- Environment variable support (CTS_API_HOST, CTS_API_PORT, CTS_LOG_LEVEL)
- TOML configuration file support (optional)
- Development/production configuration profiles
- Validation of configuration values

**Key Features**:
- Default values for all settings
- Environment variable override capability
- Configuration validation at startup

#### `src/comma_tools/api/models.py`
**Purpose**: Pydantic request/response models
**Requirements**:
- HealthResponse model
- CapabilitiesResponse model  
- ToolCapability model
- Error response models
- Proper OpenAPI schema generation

**Key Features**:
- Type validation
- Automatic OpenAPI documentation
- Consistent error response format

#### `src/comma_tools/api/health.py`
**Purpose**: Health check endpoint implementation
**Requirements**:
- `GET /v1/health` endpoint
- Returns service status, version, uptime
- Should always return 200 OK unless service is shutting down
- Include system health indicators

**Response Format**:
```json
{
  "status": "healthy",
  "version": "0.1.0", 
  "uptime": "0d 2h 15m 30s",
  "timestamp": "2024-12-19T10:30:00Z"
}
```

#### `src/comma_tools/api/capabilities.py`
**Purpose**: Tool discovery endpoint
**Requirements**:
- `GET /v1/capabilities` endpoint
- Returns list of available tools and monitors
- Include parameter schemas for each tool
- Support for tool categories (analyzers, monitors)

**Response Format**:
```json
{
  "tools": [
    {
      "id": "cruise-control-analyzer",
      "name": "Cruise Control Analyzer",
      "description": "Deep analysis of recorded driving logs",
      "category": "analyzer", 
      "parameters": {
        "speed_min": {
          "type": "float",
          "default": 55.0,
          "description": "Minimum target speed in MPH"
        }
      }
    }
  ],
  "monitors": []
}
```

### 2. Dependencies (REQUIRED)

#### Update `pyproject.toml`
**Add new optional dependency group**:
```toml
[project.optional-dependencies]
api = [
    "fastapi>=0.100.0",
    "uvicorn[standard]>=0.20.0", 
    "pydantic>=2.0.0",
    "python-multipart>=0.0.6",
]
```

**Add new script entry point**:
```toml
[project.scripts]
cts-lite = "comma_tools.api.server:main"
```

### 3. Testing (REQUIRED)

#### `tests/api/test_health.py`
**Purpose**: Test health endpoint
**Requirements**:
- Test successful health check response
- Test response format and required fields
- Test response time (should be < 100ms)

#### `tests/api/test_capabilities.py`
**Purpose**: Test capabilities endpoint  
**Requirements**:
- Test successful capabilities response
- Test response format includes tools array
- Verify at least basic tools are listed
- Test parameter schema validation

## Implementation Details

### FastAPI Application Structure
```python
# server.py structure
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

def create_app() -> FastAPI:
    app = FastAPI(
        title="CTS-Lite API",
        description="Analysis and monitoring API for comma-tools",
        version="0.1.0"
    )
    
    # Add CORS middleware for development
    app.add_middleware(CORSMiddleware, ...)
    
    # Include routers
    app.include_router(health.router, prefix="/v1")
    app.include_router(capabilities.router, prefix="/v1") 
    
    return app

app = create_app()

def main():
    """Entry point for cts-lite command"""
    import uvicorn
    config = Config()
    uvicorn.run(app, host=config.host, port=config.port)
```

### Tool Discovery Implementation
The capabilities endpoint should discover tools by:
1. Scanning the analyzers/ directory for tool modules
2. Reading parameter definitions from existing argument parsers
3. Categorizing tools (analyzer vs monitor)
4. Building capability objects with parameter schemas

**Initial Tools to Include**:
- cruise-control-analyzer
- rlog-to-csv  
- can-bitwatch

**Initial Monitors to Include**:
- hybrid_rx_trace
- can_bus_check
- can_hybrid_rx_check

### Configuration Management
```python
# config.py structure
from pydantic import BaseSettings

class Config(BaseSettings):
    host: str = "127.0.0.1"
    port: int = 8080
    log_level: str = "INFO"
    
    class Config:
        env_prefix = "CTS_API_"
        env_file = ".env"
```

## Testing Requirements

### Unit Tests
- All endpoints must have unit tests
- Test both success and error cases
- Mock external dependencies
- Achieve >90% code coverage

### Integration Tests  
- Test actual HTTP requests/responses
- Test with real FastAPI test client
- Validate OpenAPI schema generation

### Performance Tests
- Health endpoint response time < 100ms
- Capabilities endpoint response time < 500ms

## Success Criteria

### Functional Requirements
- [x] Service starts successfully with `cts-lite` command
- [x] Health endpoint returns proper response
- [x] Capabilities endpoint lists available tools
- [x] OpenAPI documentation accessible at `/docs`
- [x] All tests pass
- [x] `cts ping` command works against the service
- [x] `cts cap` command works against the service

### Non-Functional Requirements
- [x] Service starts within 2 seconds
- [x] Health check response time < 100ms
- [x] Proper error handling and logging
- [x] Clean shutdown on SIGTERM

## Validation Steps

1. **Start the service**: `cts-lite` command should start service on port 8080
2. **Health check**: `curl http://localhost:8080/v1/health` returns valid JSON
3. **Capabilities**: `curl http://localhost:8080/v1/capabilities` returns tool list
4. **CTS client**: `cts ping` command succeeds
5. **CTS capabilities**: `cts cap` command shows available tools
6. **OpenAPI docs**: Browser to `http://localhost:8080/docs` shows interactive API docs
7. **Tests**: `pytest tests/api/` passes all tests

## Common Pitfalls to Avoid

- Don't implement tool execution yet - this is Phase 1 foundation only
- Don't add authentication - keep it simple for now
- Don't implement file uploads - scope creep
- Do ensure proper async/await usage throughout
- Do include proper error handling and logging
- Do validate all configuration at startup

## Architecture Compliance Notes

- All business logic must remain in existing analyzer classes
- API layer is purely HTTP interface - no duplicate logic
- Use dependency injection for testability
- Follow REST conventions for endpoint design
- Maintain backward compatibility with existing cts CLI expectations

---

**Next Phase**: After this is complete and reviewed, Phase 2 will add tool registry and execution capabilities.