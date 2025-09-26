# Phase 3 Implementation Guide: Artifact Management & Log Streaming

**Assigned to**: Devin (AI Coding Agent)  
**Estimated Time**: 8-12 hours  
**Priority**: HIGH - Critical for MVP completion  
**Architecture Review Required**: Yes  
**Previous Phase**: Phase 2 (Core Execution) - ✅ COMPLETED

## Objective

Implement artifact management and log streaming capabilities to complete the core CTS-Lite MVP functionality. This phase enables users to download analysis results and monitor execution progress in real-time, completing the transition from standalone CLI tools to unified API service.

**End Goal**: `cts run cruise-control-analyzer --path file.zst -p speed_min=50 --wait` works end-to-end with automatic result download.

## Files to Implement

### 1. Artifact Management (REQUIRED)

#### `src/comma_tools/api/artifacts.py`
**Purpose**: Artifact storage, retrieval, and download endpoints
**Requirements**:
- `GET /v1/artifacts/{run_id}` - List artifacts for a run
- `GET /v1/artifacts/{artifact_id}/download` - Download specific artifact
- `GET /v1/artifacts/{artifact_id}/metadata` - Get artifact metadata
- File storage management (local filesystem initially)
- Artifact cleanup and retention policies

**Key Features**:
- Artifact registration when tools complete
- Secure file access with proper validation
- Support for multiple file types (CSV, JSON, HTML, PNG)
- Metadata tracking (filename, size, content-type, created_at)

#### `src/comma_tools/api/logs.py`
**Purpose**: Log streaming and retrieval endpoints  
**Requirements**:
- `GET /v1/runs/{run_id}/logs` - Get run logs (with SSE streaming support)
- `GET /v1/runs/{run_id}/logs/stream` - Server-Sent Events endpoint
- Real-time log capture during tool execution
- Log persistence and retrieval

**Key Features**:
- Server-Sent Events (SSE) for real-time streaming
- Log buffering and persistence
- WebSocket alternative support (optional)
- Proper log rotation and cleanup

### 2. Enhanced Execution Engine (REQUIRED)

#### Update `src/comma_tools/api/execution.py`
**Add artifact collection**:
- Monitor tool output directories for generated files
- Register artifacts when tool completes
- Capture stdout/stderr for log streaming
- File path resolution for analyzer outputs

**Key Enhancements**:
- Artifact detection and registration
- Real-time log capture and streaming
- Output directory management
- File cleanup and retention

### 3. Updated Models (REQUIRED)

#### Update `src/comma_tools/api/models.py`
**Add new models**:
```python
class ArtifactMetadata(BaseModel):
    artifact_id: str
    run_id: str
    filename: str
    content_type: str
    size_bytes: int
    created_at: datetime
    download_url: str

class ArtifactsResponse(BaseModel):
    run_id: str
    artifacts: List[ArtifactMetadata]
    total_count: int

class LogEntry(BaseModel):
    timestamp: datetime
    level: str
    message: str
    source: str = "tool"

class LogsResponse(BaseModel):
    run_id: str
    logs: List[LogEntry]
    has_more: bool = False
```

### 4. Server Integration (REQUIRED)

#### Update `src/comma_tools/api/server.py`
**Add new routers**:
```python
from . import artifacts, logs
app.include_router(artifacts.router, prefix="/v1", tags=["artifacts"])
app.include_router(logs.router, prefix="/v1", tags=["logs"])
```

## Implementation Details

### Artifact Management Architecture

```python
class ArtifactManager:
    def __init__(self, storage_base_dir: Path):
        self.storage_base_dir = storage_base_dir
        self.artifacts: Dict[str, ArtifactMetadata] = {}
        
    def register_artifact(self, run_id: str, file_path: Path) -> str:
        """Register a file as an artifact for a run"""
        
    def get_artifacts_for_run(self, run_id: str) -> List[ArtifactMetadata]:
        """Get all artifacts for a specific run"""
        
    def get_artifact_file_path(self, artifact_id: str) -> Path:
        """Get filesystem path for artifact download"""
        
    def cleanup_run_artifacts(self, run_id: str) -> None:
        """Clean up artifacts for a completed run"""
```

### Log Streaming Architecture

```python
class LogStreamer:
    def __init__(self):
        self.active_streams: Dict[str, asyncio.Queue] = {}
        self.log_storage: Dict[str, List[LogEntry]] = {}
        
    async def capture_tool_output(self, run_id: str, process) -> None:
        """Capture stdout/stderr from tool execution"""
        
    async def stream_logs(self, run_id: str) -> AsyncGenerator[str, None]:
        """Stream logs via Server-Sent Events"""
        
    def get_logs(self, run_id: str, limit: int = 100) -> List[LogEntry]:
        """Get persisted logs for a run"""
```

### Server-Sent Events Implementation

```python
@router.get("/runs/{run_id}/logs/stream")
async def stream_run_logs(run_id: str, streamer: LogStreamer = Depends(get_log_streamer)):
    """Stream run logs using Server-Sent Events"""
    
    async def generate():
        async for log_line in streamer.stream_logs(run_id):
            yield f"data: {log_line}\n\n"
    
    return StreamingResponse(generate(), media_type="text/plain")
```

### Integration with Phase 2 Execution Engine

**Enhanced tool execution flow**:
```python
async def execute_tool_with_artifacts(self, run_context: RunContext):
    """Execute tool and collect artifacts and logs"""
    try:
        # Set up log streaming
        log_queue = asyncio.Queue()
        self.log_streamer.start_capture(run_context.run_id, log_queue)
        
        # Execute tool in thread (existing Phase 2 logic)
        result = await self.run_tool_in_thread(run_context)
        
        # Scan for output artifacts
        artifacts = self.scan_for_artifacts(run_context)
        
        # Register artifacts
        for artifact_path in artifacts:
            artifact_id = self.artifact_manager.register_artifact(
                run_context.run_id, artifact_path
            )
            run_context.artifacts.append(artifact_id)
            
        run_context.status = RunStatus.COMPLETED
        
    except Exception as e:
        run_context.status = RunStatus.FAILED
        run_context.error = str(e)
    finally:
        self.log_streamer.stop_capture(run_context.run_id)
```

## File Storage Strategy

### Local Filesystem (Phase 3)
```
/var/lib/cts-lite/
├── runs/
│   ├── {run_id}/
│   │   ├── artifacts/
│   │   │   ├── report.html
│   │   │   ├── analysis.csv
│   │   │   └── data.json
│   │   └── logs/
│   │       └── execution.log
└── temp/
    └── {run_id}/  # Temporary working directory
```

### Artifact Detection Logic
```python
def scan_for_artifacts(self, run_context: RunContext) -> List[Path]:
    """Scan output directory for generated artifacts"""
    artifacts = []
    output_dir = self.get_run_output_dir(run_context.run_id)
    
    # Common analyzer output patterns
    patterns = [
        "*.csv", "*.json", "*.html", "*.png", "*.pdf",
        "*report*", "*analysis*", "*output*"
    ]
    
    for pattern in patterns:
        for file_path in output_dir.glob(pattern):
            if file_path.is_file() and file_path.stat().st_size > 0:
                artifacts.append(file_path)
                
    return artifacts
```

## Testing Requirements

### 1. Unit Tests (REQUIRED)

#### `tests/api/test_artifacts.py`
**Purpose**: Test artifact management functionality
**Requirements**:
- Test artifact registration and retrieval
- Test file download endpoints
- Test metadata generation
- Test artifact cleanup
- Test security (no path traversal attacks)

#### `tests/api/test_logs.py`
**Purpose**: Test log streaming functionality
**Requirements**:
- Test log capture during tool execution
- Test SSE streaming endpoint
- Test log persistence and retrieval
- Test concurrent log streams
- Test log rotation and cleanup

#### `tests/api/test_execution_enhanced.py`
**Purpose**: Test enhanced execution with artifacts
**Requirements**:
- Test end-to-end tool execution with artifact collection
- Test artifact detection for different tool types
- Test log capture integration
- Test cleanup on success and failure

### 2. Integration Tests (REQUIRED)

#### `tests/api/test_phase3_integration.py`
**Purpose**: End-to-end Phase 3 functionality
**Requirements**:
- Test complete run lifecycle: start → execute → artifacts → cleanup
- Test real analyzer execution with artifact collection
- Test log streaming during actual tool runs
- Test `cts` CLI integration with `--wait` and `--follow`

## Success Criteria

### Functional Requirements
- [ ] `GET /v1/artifacts/{run_id}` returns list of generated artifacts
- [ ] `GET /v1/artifacts/{artifact_id}/download` serves files correctly
- [ ] `GET /v1/runs/{run_id}/logs/stream` provides real-time SSE log stream
- [ ] All 3 analyzers generate and register artifacts correctly
- [ ] Artifact detection works for CSV, JSON, HTML outputs
- [ ] Log streaming captures stdout/stderr in real-time
- [ ] File security prevents unauthorized access
- [ ] Cleanup removes artifacts and logs after retention period

### Non-Functional Requirements
- [ ] Artifact download response time < 2 seconds for typical files
- [ ] Log streaming latency < 100ms from tool output to client
- [ ] Support concurrent log streams (5+ simultaneous users)
- [ ] File storage uses < 1GB per run (with cleanup)
- [ ] SSE connections remain stable for long-running tools

## Validation Steps

### Manual Testing Checklist
```bash
# 1. Start service
cts-lite

# 2. Run analyzer and check artifacts
cts run cruise-control-analyzer --path test.zst -p speed_min=50
# Should return run_id immediately

# 3. Check run status
cts logs <run_id>  # Should show execution logs

# 4. Check artifacts (when complete)
cts art list <run_id>  # Should list generated CSV/JSON/HTML files

# 5. Download artifact
cts art get <artifact_id> --download ./report.html
# Should download file successfully

# 6. Test streaming during execution
cts run cruise-control-analyzer --path test.zst --follow
# Should stream logs in real-time
```

### Integration with CTS CLI

The `cts` CLI client should be enhanced to support:
- `cts art list <run_id>` - List available artifacts
- `cts art get <artifact_id>` - Download artifact
- `cts logs <run_id> --follow` - Follow log stream
- `cts run ... --wait` - Wait for completion and auto-download artifacts

## Common Pitfalls to Avoid

### Critical Architecture Issues
- **Don't store artifacts in API server memory** - use filesystem storage
- **Don't block API responses during file operations** - use async file I/O
- **Don't skip file security validation** - prevent path traversal attacks
- **Don't ignore SSE connection management** - handle client disconnections
- **Don't skip artifact cleanup** - implement retention policies
- **Don't hardcode file paths** - use configurable storage locations

### Performance Considerations
- **Do use streaming responses** for large file downloads
- **Do implement log rotation** to prevent unbounded growth
- **Do use background cleanup tasks** for artifact retention
- **Do validate file sizes** before registration
- **Do implement proper error handling** for missing/corrupt files

### Security Requirements
- **Validate all file access** - check run ownership
- **Sanitize file paths** - prevent directory traversal
- **Limit file sizes** - prevent storage exhaustion
- **Implement proper MIME types** - for secure downloads
- **Log security events** - track file access attempts

## Architecture Compliance Notes

### Integration with Phase 2
- **Reuse existing execution engine** - enhance, don't replace
- **Maintain thread-based execution** - don't change the async pattern
- **Preserve run management logic** - add artifact tracking to existing flows
- **Keep API response patterns** - maintain consistency with Phase 2

### Tool Integration Pattern
```python
# CORRECT: Enhance existing analyzer execution
def execute_cruise_control_analyzer(self, params: Dict, run_context: RunContext):
    # Run existing analyzer (Phase 2 logic)
    analyzer = CruiseControlAnalyzer(params['log_file'])
    success = analyzer.analyze_cruise_control(params['speed_min'], params['speed_max'])
    
    # NEW: Collect generated artifacts
    if success:
        # Scan analyzer output directory
        artifacts = self.scan_for_analyzer_outputs(analyzer.output_dir)
        for artifact_path in artifacts:
            self.artifact_manager.register_artifact(run_context.run_id, artifact_path)
    
    return success
```

## Phase 3 Completion Criteria

### MVP Readiness Test
```bash
# Complete MVP functionality test
cts cap  # ✅ Shows analyzers
cts run cruise-control-analyzer --path test.zst -p speed_min=50 --wait --follow
# Expected behavior:
# 1. ✅ Returns run_id immediately  
# 2. ✅ Streams real-time logs during execution
# 3. ✅ Shows completion status
# 4. ✅ Automatically downloads generated artifacts (CSV, JSON, HTML)
# 5. ✅ Files saved to local directory with proper names
```

### Ready for Production
- [ ] All Phase 3 tests pass (100% success rate)
- [ ] Integration tests with real data files pass
- [ ] Security validation passes (no unauthorized file access)
- [ ] Performance benchmarks meet requirements
- [ ] Documentation updated with new endpoints
- [ ] `cts` CLI fully supports artifact and log operations

---

**Next Phase**: After Phase 3, only Phase 4 (production polish) remains for MVP completion.
**Timeline**: With Phase 3 complete, MVP target moves to 1-2 weeks (production deployment ready).

## Architecture Review Checkpoint

After implementation, the architect will verify:
1. **No business logic duplication** - artifacts enhance existing flow
2. **Proper async patterns** - SSE and file I/O don't block API
3. **Security compliance** - file access is properly validated
4. **Integration success** - CTS CLI works end-to-end with all features
5. **MVP criteria met** - all user acceptance tests pass

---

*This completes the core CTS-Lite functionality required for MVP production readiness.*