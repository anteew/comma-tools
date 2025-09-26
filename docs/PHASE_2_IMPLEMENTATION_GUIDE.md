# Phase 2 Implementation Guide: Tool Registry and Execution Engine

**Assigned to**: Coding Agent  
**Estimated Time**: 6-8 hours  
**Priority**: High  
**Architecture Review Required**: Yes  
**Previous Phase**: Phase 1 (Service Foundation) - ✅ COMPLETED

## Objective

Implement the core tool execution capabilities for CTS-Lite, enabling users to run analyzers via the API with async execution, parameter handling, and run management. This phase makes the `cts run` command functional.

## Files to Implement

### 1. Core Execution Files (REQUIRED)

#### `src/comma_tools/api/registry.py`
**Purpose**: Tool registration and management system  
**Requirements**:
- Dynamic tool discovery from existing analyzer modules
- Tool metadata management (parameters, descriptions, categories)
- Tool instance creation and validation
- Support for both analyzers and monitors (focus on analyzers for Phase 2)

**Key Features**:
- Registry class that scans analyzers/ directory
- Tool registration with parameter schema extraction  
- Tool instance factory methods
- Validation of tool parameters against schemas

#### `src/comma_tools/api/execution.py`
**Purpose**: Tool execution engine with async support
**Requirements**:
- Background task execution using FastAPI BackgroundTasks
- Tool parameter validation and preparation  
- Execution environment setup (deps, paths, etc.)
- Progress tracking and status management
- Error handling and logging
- Result capture and storage

**Key Features**:
- ExecutionEngine class for managing tool runs
- RunContext class for execution state
- Background task wrapper for async execution
- Proper error handling and timeout support

#### `src/comma_tools/api/runs.py`  
**Purpose**: Run management endpoints
**Requirements**:
- `POST /v1/runs` - Start tool execution
- `GET /v1/runs/{run_id}` - Get run status
- `GET /v1/runs/{run_id}/logs` - Get run logs (with SSE streaming support)
- `DELETE /v1/runs/{run_id}` - Cancel run (optional)

**Response Formats**:
```json
// POST /v1/runs response
{
  "run_id": "uuid-string",
  "status": "queued",
  "tool_id": "cruise-control-analyzer", 
  "created_at": "2024-12-19T10:30:00Z",
  "params": {"speed_min": 50.0, "speed_max": 60.0}
}

// GET /v1/runs/{run_id} response  
{
  "run_id": "uuid-string",
  "status": "running|completed|failed|canceled",
  "tool_id": "cruise-control-analyzer",
  "created_at": "2024-12-19T10:30:00Z", 
  "started_at": "2024-12-19T10:30:05Z",
  "completed_at": "2024-12-19T10:35:20Z",
  "params": {"speed_min": 50.0},
  "progress": 85,
  "artifacts": [],
  "error": null
}
```

### 2. Model Updates (REQUIRED)

#### Update `src/comma_tools/api/models.py`
**Add new models**:
```python
class RunRequest(BaseModel):
    tool_id: str
    params: Dict[str, Any] = {}
    input: Optional[InputRef] = None
    name: Optional[str] = None

class InputRef(BaseModel):
    type: Literal["path", "upload"]
    value: str

class RunResponse(BaseModel):
    run_id: str
    status: RunStatus
    tool_id: str
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    params: Dict[str, Any]
    progress: Optional[int] = None
    artifacts: List[str] = []
    error: Optional[str] = None

class RunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running" 
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"
```

### 3. Server Integration (REQUIRED)

#### Update `src/comma_tools/api/server.py`
**Add runs router**:
```python
from . import runs
app.include_router(runs.router, prefix="/v1", tags=["runs"])
```

## Implementation Details

### Tool Registry Architecture
```python
class ToolRegistry:
    def __init__(self):
        self.tools: Dict[str, ToolCapability] = {}
        self.monitors: Dict[str, MonitorCapability] = {}
        
    def discover_tools(self) -> None:
        """Scan analyzers/ directory and register tools"""
        # Import analyzer modules dynamically
        # Extract argument parsers and build capabilities
        # Register tools with parameter schemas
        
    def get_tool(self, tool_id: str) -> ToolCapability:
        """Get tool capability by ID"""
        
    def create_tool_instance(self, tool_id: str, **kwargs):
        """Create analyzer instance with parameters"""
```

### Execution Engine Architecture  
```python
class ExecutionEngine:
    def __init__(self, registry: ToolRegistry):
        self.registry = registry
        self.active_runs: Dict[str, RunContext] = {}
        
    async def start_run(self, request: RunRequest) -> RunResponse:
        """Start tool execution in background"""
        
    async def get_run_status(self, run_id: str) -> RunResponse:
        """Get current run status"""
        
    async def execute_tool(self, run_context: RunContext):
        """Execute tool in background task"""
        
class RunContext:
    def __init__(self, run_id: str, tool_id: str, params: Dict[str, Any]):
        self.run_id = run_id
        self.tool_id = tool_id  
        self.params = params
        self.status = RunStatus.QUEUED
        self.created_at = datetime.utcnow()
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.progress: Optional[int] = None
        self.error: Optional[str] = None
        self.artifacts: List[str] = []
```

### Tool Parameter Handling
The execution engine must:
1. **Validate parameters** against tool schemas from registry
2. **Convert parameter types** (string → int/float/bool as needed) 
3. **Handle file inputs** (path validation, future upload support)
4. **Set up tool environment** (dependencies, openpilot paths)
5. **Execute tool safely** with proper error handling

### Background Execution Flow
```python
@router.post("/runs", response_model=RunResponse)
async def start_run(
    request: RunRequest,
    background_tasks: BackgroundTasks,
    engine: ExecutionEngine = Depends(get_execution_engine)
):
    # Validate tool exists and parameters
    tool = engine.registry.get_tool(request.tool_id)
    
    # Create run context
    run_context = RunContext(
        run_id=str(uuid4()),
        tool_id=request.tool_id,
        params=request.params
    )
    
    # Start background execution
    background_tasks.add_task(engine.execute_tool, run_context)
    
    # Return immediate response
    return RunResponse(
        run_id=run_context.run_id,
        status=RunStatus.QUEUED,
        tool_id=request.tool_id,
        created_at=run_context.created_at,
        params=request.params
    )
```

## Testing Requirements

### 2. Unit Tests (REQUIRED)

#### `tests/api/test_registry.py`
**Purpose**: Test tool registry functionality
**Requirements**:
- Test tool discovery from analyzer modules
- Test parameter schema extraction
- Test tool instance creation
- Test error handling for invalid tools

#### `tests/api/test_execution.py`  
**Purpose**: Test execution engine
**Requirements**:
- Test run creation and status tracking
- Test parameter validation 
- Test background execution (with mocks)
- Test error handling and timeout scenarios

#### `tests/api/test_runs.py`
**Purpose**: Test runs endpoints
**Requirements**:  
- Test POST /v1/runs with valid parameters
- Test GET /v1/runs/{run_id} status responses
- Test parameter validation errors
- Test invalid tool_id handling
- Test run status transitions

### 3. Integration Tests (REQUIRED)

#### `tests/api/test_runs_integration.py`
**Purpose**: End-to-end run execution tests
**Requirements**:
- Test actual tool execution with real analyzers
- Test with sample data files (use test fixtures)
- Test full run lifecycle (queued → running → completed)
- Test error scenarios (invalid files, missing deps)

## Success Criteria

### Functional Requirements
- [x] POST /v1/runs endpoint accepts tool requests and returns run_id
- [x] GET /v1/runs/{run_id} endpoint returns current run status  
- [x] Tool registry discovers at least 3 analyzers from existing code
- [x] Background execution actually runs analyzer classes (not dummy tasks)
- [x] Parameter validation prevents invalid requests
- [x] Error handling captures and reports tool execution failures
- [x] `cts run cruise-control-analyzer --path file.zst -p speed_min=50` works end-to-end

### Non-Functional Requirements  
- [x] Run startup time < 1 second (queued → running)
- [x] Status endpoint response time < 100ms
- [x] Proper error logging for debugging
- [x] Background tasks don't block API responses
- [x] Memory usage stays reasonable during execution

## Validation Steps

1. **Start CTS-Lite service**: `cts-lite` 
2. **Test capabilities**: `cts cap` shows available tools
3. **Start a run**: `cts run cruise-control-analyzer --path test.zst -p speed_min=50`
4. **Check run status**: Should return run_id and status="queued" immediately
5. **Monitor run**: Status should transition queued → running → completed  
6. **Verify execution**: Tool should actually execute analyzer logic
7. **Test error handling**: Try invalid tool_id, should get proper error
8. **Test parameter validation**: Try invalid parameters, should get validation error

## Common Pitfalls to Avoid

- **Don't duplicate analyzer logic** - call existing analyzer classes, don't reimplement
- **Don't block API responses** - use BackgroundTasks for all tool execution
- **Don't skip parameter validation** - validate all inputs against tool schemas  
- **Don't ignore error handling** - capture and report all execution errors
- **Don't hardcode tool lists** - dynamically discover from analyzer modules
- **Do handle missing dependencies** - analyzer tools may need openpilot, deps setup
- **Do preserve existing behavior** - analyzers should work exactly as before
- **Do use proper async patterns** - don't mix sync/async incorrectly

## Architecture Compliance Notes

### Critical Requirements:
1. **No Business Logic Duplication**: Import and use existing analyzer classes directly
2. **Service Layer Only**: API layer handles HTTP/validation, analyzer classes do the work
3. **Backward Compatibility**: Existing analyzer functionality must be preserved exactly
4. **Dependency Management**: Respect existing dependency setup patterns from CLI tools
5. **Error Propagation**: Tool errors should be captured and surfaced through API properly

### Integration Pattern:
```python
# CORRECT: Use existing analyzer classes
from comma_tools.analyzers.cruise_control_analyzer import CruiseControlAnalyzer

def execute_cruise_control_analyzer(params: Dict[str, Any]) -> None:
    # Validate parameters
    log_file = params.get('log_file') or params.get('path')  
    speed_min = params.get('speed_min', 55.0)
    speed_max = params.get('speed_max', 56.0)
    
    # Use existing analyzer class - no duplication!
    analyzer = CruiseControlAnalyzer(log_file)
    success = analyzer.analyze_cruise_control(speed_min, speed_max)
    
    if not success:
        raise RuntimeError("Analysis failed")

# WRONG: Don't reimplement analyzer logic
def execute_cruise_control_analyzer_wrong(params: Dict[str, Any]) -> None:
    # This would be duplicating business logic - DON'T DO THIS
    pass
```

## File Input Handling (Phase 2 Scope)

For Phase 2, support **path-based inputs only**:
```python
# POST /v1/runs request body
{
  "tool_id": "cruise-control-analyzer",
  "params": {"speed_min": 50.0, "speed_max": 60.0},
  "input": {"type": "path", "value": "/path/to/file.zst"}
}
```

File uploads will be handled in Phase 3. For now, assume users provide local file paths that the service can access.

## Logging and Monitoring

Implement comprehensive logging:
- **Run lifecycle events**: start, progress, completion, errors
- **Parameter validation**: what was requested vs validated
- **Execution details**: which analyzer was called, with what parameters  
- **Performance metrics**: execution time, memory usage
- **Error details**: full stack traces for debugging

---

**Next Phase**: After Phase 2 is complete, Phase 3 will add file upload/download and artifact management capabilities.