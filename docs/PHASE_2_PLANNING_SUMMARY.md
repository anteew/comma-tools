# Phase 2 Planning Summary

> **⚠️ ARCHIVE NOTICE**: This planning document is now OBSOLETE and archived for historical reference.  
> **Status**: ✅ IMPLEMENTATION COMPLETED - Phase 2 successfully implemented  
> **See**: `src/comma_tools/api/registry.py`, `execution.py`, `runs.py` for actual implementation

**Phase**: Tool Registry and Execution Engine  
**Status**: Ready for Implementation  
**Previous Phase**: Phase 1 (Service Foundation) - ✅ COMPLETED & REVIEWED  

## Phase 1 Review Results

### ✅ **APPROVED - Coding agent delivered excellent Phase 1 implementation**

**Architectural Compliance**: Full compliance with service-first architecture
- No business logic duplication in API layer
- Proper separation of concerns maintained
- All core logic remains in existing analyzer classes

**Functional Verification**:
- ✅ `cts-lite` command starts service correctly
- ✅ Health endpoint returns proper JSON response  
- ✅ Capabilities endpoint lists 3 tools with parameter schemas
- ✅ All 11 tests pass consistently
- ✅ Performance requirements met (health < 100ms)
- ✅ OpenAPI documentation available at /docs

**Quality Assessment**:
- Clean, well-structured FastAPI application  
- Comprehensive test coverage including regression tests
- Proper configuration management with environment variables
- Good error handling and logging

## Phase 2 Objectives

**Primary Goal**: Enable `cts run` command functionality through tool execution API

**Key Deliverables**:
1. **Tool Registry System** - Dynamic discovery of analyzer modules
2. **Execution Engine** - Background task execution with status tracking  
3. **Runs API Endpoints** - POST /v1/runs, GET /v1/runs/{id}
4. **Parameter Handling** - Validation and type conversion
5. **Background Processing** - Async tool execution without blocking API

**Success Criteria**:
```bash
# This should work after Phase 2:
cts run cruise-control-analyzer --path test.zst -p speed_min=50 -p speed_max=60 --wait
```

## Architecture Compliance Requirements for Phase 2

### 🔒 **Critical - Must Not Violate**:
1. **No Logic Duplication**: Import existing analyzer classes, don't reimplement
2. **Service Layer Pattern**: API handles HTTP/validation, analyzers do the work
3. **Background Execution**: Use FastAPI BackgroundTasks for all tool execution
4. **Parameter Validation**: Validate all inputs against tool schemas
5. **Error Handling**: Capture and surface tool errors through API

### ✅ **Required Integration Pattern**:
```python
# CORRECT: Use existing classes
from comma_tools.analyzers.cruise_control_analyzer import CruiseControlAnalyzer

def execute_tool(tool_id: str, params: Dict[str, Any]):
    if tool_id == "cruise-control-analyzer":
        analyzer = CruiseControlAnalyzer(params['log_file'])
        return analyzer.analyze_cruise_control(params['speed_min'], params['speed_max'])
```

## File Structure for Phase 2

**New Files**:
- `src/comma_tools/api/registry.py` - Tool registration system
- `src/comma_tools/api/execution.py` - Execution engine
- `src/comma_tools/api/runs.py` - Runs API endpoints

**Updated Files**:
- `src/comma_tools/api/models.py` - Add RunRequest/RunResponse models  
- `src/comma_tools/api/server.py` - Add runs router

**New Tests**:
- `tests/api/test_registry.py` - Tool registry tests
- `tests/api/test_execution.py` - Execution engine tests  
- `tests/api/test_runs.py` - Runs API tests
- `tests/api/test_runs_integration.py` - End-to-end tests

## Implementation Guidance for Coding Agent

**See**: `docs/PHASE_2_IMPLEMENTATION_GUIDE.md` for complete implementation details

**Key Points**:
- Focus on analyzers first (monitors in Phase 4)
- Use path-based file inputs only (uploads in Phase 3)  
- Implement proper background task execution
- Maintain all existing analyzer functionality exactly
- Add comprehensive error handling and logging

## Expected Timeline

**Implementation**: 6-8 hours  
**Testing**: 2-3 hours  
**Review & Polish**: 1-2 hours  
**Total**: ~8-12 hours

---

*Ready for coding agent assignment*