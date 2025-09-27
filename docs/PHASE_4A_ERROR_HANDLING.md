# Phase 4A Implementation Guide: Enhanced Error Handling & Recovery

**Assigned to**: AI Coding Agent  
**Estimated Time**: 2-3 hours  
**Priority**: CRITICAL - Foundation for production readiness  
**Architecture Review Required**: Yes  
**Previous Phase**: Phase 3 (Artifact Management & Log Streaming) - ✅ COMPLETED

## Objective

Implement comprehensive error handling and recovery mechanisms to ensure CTS-Lite service is robust and resilient. This phase focuses on proper error categorization, graceful degradation, resource cleanup, and actionable error reporting.

**Goal**: Transform CTS-Lite from a development prototype to a production-ready service with enterprise-grade error handling.

## Phase 4A Scope: Error Handling & Recovery Foundation

### **1. Enhanced Error Categorization (CRITICAL)**

#### Update `src/comma_tools/api/execution.py`
**Requirements**:
- Implement comprehensive error categorization system
- Add timeout handling for long-running tools
- Ensure proper resource cleanup on failures
- Provide actionable error diagnostics

**Key Enhancements**:
```python
from enum import Enum
from typing import Optional, Dict, Any
import asyncio

class ErrorCategory(str, Enum):
    TOOL_ERROR = "tool_error"           # Analyzer execution failed, including timeouts
    VALIDATION_ERROR = "validation_error" # Invalid parameters/inputs  
    SYSTEM_ERROR = "system_error"       # Infrastructure or resource issues

class EnhancedRunContext:
    def __init__(self, ...):
        # ... existing fields from Phase 2/3 ...
        self.error_category: Optional[ErrorCategory] = None
        self.error_details: Dict[str, Any] = {}
        self.recovery_attempted: bool = False
        self.timeout_seconds: int = 300  # 5 minute default
        self.cleanup_handlers: List[Callable] = []
```

#### Error Handling Implementation Pattern:
```python
async def execute_tool_with_error_handling(self, run_context: RunContext):
    """
    Enhanced tool execution with comprehensive error handling.
    
    Args:
        run_context: RunContext with execution parameters
        
    Returns:
        ExecutionResult with success/failure details
        
    Raises:
        CriticalSystemError: For unrecoverable system failures
    """
    try:
        # Set up cleanup handlers
        run_context.cleanup_handlers.append(self._cleanup_temp_files)
        run_context.cleanup_handlers.append(self._release_resources)
        
        # Execute with timeout
        result = await asyncio.wait_for(
            self.execute_tool_enhanced(run_context),
            timeout=run_context.timeout_seconds
        )
        return result
        
    except asyncio.TimeoutError:
        run_context.error_category = ErrorCategory.TOOL_ERROR
        run_context.error_details = {
            "error_type": "timeout",
            "timeout_seconds": run_context.timeout_seconds,
            "suggested_fix": "Increase timeout or optimize tool parameters"
        }
        await self._execute_cleanup_handlers(run_context)
        
    except ToolExecutionError as e:
        run_context.error_category = ErrorCategory.TOOL_ERROR
        run_context.error_details = {
            "tool_stderr": e.stderr,
            "exit_code": e.exit_code,
            "execution_time": e.duration,
            "suggested_fix": self._suggest_tool_fix(e)
        }
        await self._execute_cleanup_handlers(run_context)
        
    except ValidationError as e:
        run_context.error_category = ErrorCategory.VALIDATION_ERROR  
        run_context.error_details = {
            "validation_errors": e.errors(),
            "suggested_fix": "Check parameter names and values"
        }
        # No cleanup needed for validation errors
        
    except (OSError, PermissionError, FileNotFoundError) as e:
        run_context.error_category = ErrorCategory.SYSTEM_ERROR
        run_context.error_details = {
            "system_error": str(e), 
            "error_type": type(e).__name__,
            "suggested_fix": self._suggest_system_fix(e)
        }
        await self._execute_cleanup_handlers(run_context)
```

### **2. Graceful Degradation & Recovery (REQUIRED)**

#### Add Recovery Mechanisms
**Requirements**:
- Implement automatic retry for transient failures
- Graceful handling when tools fail
- Resource cleanup for partial failures
- Clear user messaging about degraded functionality

```python
class RecoveryManager:
    """Manages error recovery and graceful degradation."""
    
    async def attempt_recovery(self, run_context: RunContext) -> bool:
        """
        Attempt to recover from tool execution failure.
        
        Args:
            run_context: Failed execution context
            
        Returns:
            True if recovery successful, False otherwise
        """
        if run_context.error_category == ErrorCategory.TOOL_ERROR:
            # Retry with reduced parameters for some tools
            if self._can_retry_with_fallback(run_context):
                run_context.recovery_attempted = True
                return await self._retry_with_fallback(run_context)
                
        elif run_context.error_category == ErrorCategory.SYSTEM_ERROR:
            # Wait and retry for transient system issues
            if self._is_transient_error(run_context):
                await asyncio.sleep(2)  # Brief wait
                run_context.recovery_attempted = True
                return await self._retry_execution(run_context)
                
        return False
        
    def _suggest_tool_fix(self, error: ToolExecutionError) -> str:
        """Generate actionable fix suggestions based on error details."""
        if "memory" in error.stderr.lower():
            return "Tool ran out of memory. Try with smaller input file or increase system memory."
        elif "permission" in error.stderr.lower():
            return "Permission denied. Check file permissions and user access rights."
        elif "not found" in error.stderr.lower():
            return "Tool dependency missing. Run with --install-missing-deps flag."
        else:
            return "Tool execution failed. Check input parameters and tool compatibility."
```

### **3. Resource Management & Cleanup (CRITICAL)**

#### Implement Comprehensive Cleanup
**Requirements**:
- Automatic cleanup of temporary files and resources
- Process management for long-running tools  
- Memory management for large artifacts
- Clean shutdown handling

```python
class ResourceManager:
    """Manages resources and ensures proper cleanup."""
    
    def __init__(self):
        self.active_processes: Set[asyncio.subprocess.Process] = set()
        self.temp_directories: Set[Path] = set()
        self.open_files: Set[IO] = set()
        
    async def cleanup_run_resources(self, run_context: RunContext):
        """Clean up all resources associated with a run."""
        # Execute registered cleanup handlers
        for cleanup_handler in run_context.cleanup_handlers:
            try:
                await cleanup_handler(run_context)
            except Exception as e:
                logger.warning(f"Cleanup handler failed: {e}")
                
        # Force cleanup critical resources
        await self._cleanup_processes(run_context.run_id)
        await self._cleanup_temp_files(run_context.run_id)
        self._cleanup_memory_references(run_context.run_id)
        
    async def _cleanup_processes(self, run_id: str):
        """Terminate any running processes for this run."""
        for proc in list(self.active_processes):
            if hasattr(proc, 'run_id') and proc.run_id == run_id:
                try:
                    proc.terminate()
                    await asyncio.wait_for(proc.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    proc.kill()  # Force kill if graceful termination fails
                except Exception as e:
                    logger.warning(f"Process cleanup failed: {e}")
                finally:
                    self.active_processes.discard(proc)
```

### **4. Enhanced Error Reporting (REQUIRED)**

#### Update API Error Responses
**Requirements**:
- Consistent error response format
- Actionable error messages
- Debug information for developers
- User-friendly error explanations

```python
class ErrorResponse(BaseModel):
    """Standardized error response format."""
    error_category: ErrorCategory
    error_code: str
    user_message: str
    technical_details: Dict[str, Any]
    suggested_actions: List[str]
    recovery_attempted: bool
    run_id: Optional[str] = None
    timestamp: str
    
    @classmethod
    def from_run_context(cls, run_context: RunContext) -> "ErrorResponse":
        """Create error response from failed run context."""
        return cls(
            error_category=run_context.error_category,
            error_code=cls._generate_error_code(run_context),
            user_message=cls._generate_user_message(run_context),
            technical_details=run_context.error_details,
            suggested_actions=cls._generate_suggestions(run_context),
            recovery_attempted=run_context.recovery_attempted,
            run_id=run_context.run_id,
            timestamp=datetime.utcnow().isoformat()
        )
```

### **5. Testing Requirements (CRITICAL)**

#### Create `tests/api/test_error_handling.py`
**Purpose**: Comprehensive error handling validation
**Requirements**:
- Test all error categories
- Verify cleanup after failures
- Validate recovery mechanisms
- Check error response formats

```python
class TestErrorHandling:
    """Test comprehensive error handling and recovery."""
    
    async def test_tool_timeout_handling(self):
        """Test: Tool execution timeout triggers proper cleanup."""
        # Set very short timeout and verify timeout handling
        
    async def test_validation_error_handling(self):
        """Test: Invalid parameters return clear validation errors."""
        
    async def test_system_error_recovery(self):
        """Test: System errors trigger appropriate recovery attempts."""
        
    async def test_resource_cleanup_on_failure(self):
        """Test: All resources cleaned up when tool execution fails."""
        
    async def test_error_response_format(self):
        """Test: Error responses follow standardized format."""
        
    async def test_concurrent_failure_isolation(self):
        """Test: One tool failure doesn't affect other concurrent runs."""
```

## Implementation Priority

### **🔥 CRITICAL (Must Complete)**
1. **Error Categorization System**: Implement ErrorCategory enum and enhanced RunContext
2. **Timeout Handling**: Add asyncio timeout to all tool executions
3. **Resource Cleanup**: Implement comprehensive cleanup handlers
4. **Error Response Format**: Standardize API error responses
5. **Basic Testing**: Test all error paths and cleanup mechanisms

### **📋 IMPORTANT (Should Complete)**  
1. **Recovery Mechanisms**: Implement automatic retry logic
2. **Graceful Degradation**: Handle partial failures gracefully
3. **Enhanced Diagnostics**: Provide actionable error messages
4. **Comprehensive Testing**: Test error scenarios and edge cases

## Success Criteria

### **Technical Validation**
- [ ] All tool executions have timeout protection
- [ ] Failed runs trigger proper resource cleanup
- [ ] Error responses follow consistent format
- [ ] Recovery mechanisms handle transient failures
- [ ] No resource leaks during error conditions

### **User Experience Validation**
- [ ] Error messages are clear and actionable
- [ ] Users get helpful suggestions for fixing errors
- [ ] Service remains stable during tool failures
- [ ] Concurrent runs are isolated from each other's failures

### **Testing Validation**
```bash
# Test error handling works correctly:
cts run invalid-tool                    # Clear validation error
cts run cruise-control-analyzer         # Missing params error with suggestions
cts run cruise-control-analyzer --path nonexistent.zst  # File not found with fix
```

## Architecture Compliance

### **Integration with Existing Phases**
- **Preserve Phase 2/3 Logic**: Enhance existing execution without breaking changes
- **Maintain API Compatibility**: Keep existing endpoint contracts intact
- **Follow Established Patterns**: Use consistent code style and error handling
- **Build on Foundations**: Leverage existing RunContext and execution frameworks

### **Error Handling Philosophy**
- **Fail Fast for Validation**: Catch input errors early before execution
- **Fail Safe for Execution**: Graceful handling of tool and system failures
- **Always Clean Up**: No resource leaks regardless of failure mode
- **Actionable Messages**: Help users understand and fix problems

---

**Next Phase**: Phase 4B (Configuration & Monitoring) builds on this error handling foundation to add production configuration management and basic monitoring capabilities.