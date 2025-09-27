"""Test comprehensive error handling and recovery mechanisms."""

import asyncio
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from comma_tools.api.execution import ExecutionEngine, RunContext, ResourceManager, RecoveryManager
from comma_tools.api.models import RunRequest, RunStatus, ErrorCategory, ErrorResponse
from comma_tools.api.registry import ToolRegistry


@pytest.fixture
def mock_registry():
    """Create a mock tool registry."""
    registry = MagicMock(spec=ToolRegistry)
    
    # Mock tool with parameters
    mock_tool = MagicMock()
    mock_tool.id = "test-tool"
    mock_tool.parameters = {
        "param1": MagicMock(required=True, type="str"),
        "param2": MagicMock(required=False, type="int", default=10)
    }
    
    registry.get_tool.return_value = mock_tool
    registry.create_tool_instance.return_value = MagicMock()
    
    return registry


@pytest.fixture
def execution_engine(mock_registry):
    """Create execution engine for testing."""
    return ExecutionEngine(mock_registry)


@pytest.fixture
def sample_run_context():
    """Create a sample run context for testing."""
    return RunContext(
        run_id="test-run-123",
        tool_id="test-tool",
        params={"param1": "value1"},
    )


class TestErrorHandling:
    """Test comprehensive error handling and recovery."""
    
    @pytest.mark.asyncio
    async def test_tool_timeout_handling(self, execution_engine, sample_run_context):
        """Test: Tool execution timeout triggers proper cleanup."""
        # Mock the wait_for function to raise TimeoutError directly
        with patch('asyncio.wait_for') as mock_wait_for:
            mock_wait_for.side_effect = asyncio.TimeoutError("Timeout")
            
            # Mock cleanup methods
            with patch.object(execution_engine.resource_manager, 'cleanup_run_resources') as mock_cleanup:
                await execution_engine.execute_tool_async(sample_run_context)
        
        # Verify timeout was handled
        assert sample_run_context.status == RunStatus.FAILED
        assert sample_run_context.error_category == ErrorCategory.TOOL_ERROR
        assert "timeout" in sample_run_context.error_details.get("error_type", "")
        assert "timeout" in sample_run_context.error.lower() or "timed out" in sample_run_context.error.lower()
        
        # Verify cleanup was called
        mock_cleanup.assert_called_once_with(sample_run_context)
    
    @pytest.mark.asyncio
    async def test_validation_error_handling(self, execution_engine):
        """Test: Invalid parameters return clear validation errors."""
        # Create request with missing required parameter
        request = RunRequest(tool_id="test-tool", params={})  # Missing param1
        
        response = await execution_engine.start_run(request)
        
        # Get the run context to check error details
        run_context = execution_engine.active_runs[response.run_id]
        
        assert response.status == RunStatus.FAILED
        assert run_context.error_category == ErrorCategory.VALIDATION_ERROR
        assert "Required parameter 'param1' missing" in run_context.error
        assert "suggested_fix" in run_context.error_details
    
    @pytest.mark.asyncio
    async def test_system_error_recovery(self, execution_engine, sample_run_context):
        """Test: System errors trigger appropriate recovery attempts."""
        # Mock system error during execution
        with patch.object(execution_engine, '_execute_tool_sync') as mock_sync:
            mock_sync.side_effect = FileNotFoundError("Required file not found")
            
            # Mock recovery attempt
            with patch.object(execution_engine.recovery_manager, 'attempt_recovery') as mock_recovery:
                mock_recovery.return_value = False  # Recovery failed
                
                await execution_engine.execute_tool_async(sample_run_context)
        
        # Verify system error was categorized correctly
        assert sample_run_context.status == RunStatus.FAILED
        assert sample_run_context.error_category == ErrorCategory.SYSTEM_ERROR
        assert "filenotfounderror" in sample_run_context.error_details.get("error_type", "").lower()
        
        # Verify recovery was attempted
        mock_recovery.assert_called_once_with(sample_run_context)
    
    @pytest.mark.asyncio
    async def test_resource_cleanup_on_failure(self, execution_engine, sample_run_context):
        """Test: All resources cleaned up when tool execution fails."""
        # Mock execution failure
        with patch.object(execution_engine, '_execute_tool_sync') as mock_sync:
            mock_sync.side_effect = RuntimeError("Tool crashed")
            
            # Mock cleanup
            with patch.object(execution_engine.resource_manager, 'cleanup_run_resources') as mock_cleanup:
                await execution_engine.execute_tool_async(sample_run_context)
        
        # Verify cleanup was called
        mock_cleanup.assert_called_once_with(sample_run_context)
        
        # Verify cleanup handlers were set up
        assert len(sample_run_context.cleanup_handlers) > 0
    
    @pytest.mark.asyncio
    async def test_error_response_format(self, sample_run_context):
        """Test: Error responses follow standardized format."""
        # Set up error context
        sample_run_context.error_category = ErrorCategory.TOOL_ERROR
        sample_run_context.error = "Tool execution failed"
        sample_run_context.error_details = {
            "tool_error": "Mock tool error",
            "suggested_fix": "Try different parameters"
        }
        sample_run_context.recovery_attempted = True
        
        # Create error response
        error_response = ErrorResponse.from_run_context(sample_run_context)
        
        # Verify response format
        assert error_response.error_category == ErrorCategory.TOOL_ERROR
        assert error_response.run_id == sample_run_context.run_id
        assert error_response.recovery_attempted is True
        assert len(error_response.suggested_actions) > 0
        assert error_response.user_message is not None
        assert error_response.error_code is not None
    
    @pytest.mark.asyncio
    async def test_concurrent_failure_isolation(self, execution_engine):
        """Test: One tool failure doesn't affect other concurrent runs."""
        # Create two run requests
        request1 = RunRequest(tool_id="test-tool", params={"param1": "value1"})
        request2 = RunRequest(tool_id="test-tool", params={"param1": "value2"})
        
        # Start both runs
        response1 = await execution_engine.start_run(request1)
        response2 = await execution_engine.start_run(request2)
        
        # Verify both runs are tracked separately
        assert response1.run_id != response2.run_id
        assert response1.run_id in execution_engine.active_runs
        assert response2.run_id in execution_engine.active_runs
        
        # Verify runs have separate contexts
        context1 = execution_engine.active_runs[response1.run_id]
        context2 = execution_engine.active_runs[response2.run_id]
        assert context1 is not context2
        assert context1.run_id != context2.run_id


class TestResourceManager:
    """Test resource management and cleanup functionality."""
    
    @pytest.fixture
    def resource_manager(self):
        """Create resource manager for testing."""
        return ResourceManager()
    
    @pytest.mark.asyncio
    async def test_cleanup_handlers_execution(self, resource_manager, sample_run_context):
        """Test: Cleanup handlers are executed properly."""
        cleanup_called = []
        
        # Add test cleanup handlers
        def sync_cleanup(ctx):
            cleanup_called.append("sync")
        
        async def async_cleanup(ctx):
            cleanup_called.append("async")
        
        sample_run_context.cleanup_handlers = [sync_cleanup, async_cleanup]
        
        await resource_manager.cleanup_run_resources(sample_run_context)
        
        # Verify both handlers were called
        assert "sync" in cleanup_called
        assert "async" in cleanup_called
    
    @pytest.mark.asyncio
    async def test_cleanup_handler_failure_isolation(self, resource_manager, sample_run_context):
        """Test: Failing cleanup handlers don't prevent other cleanups."""
        cleanup_called = []
        
        def failing_cleanup(ctx):
            raise RuntimeError("Cleanup failed")
        
        def working_cleanup(ctx):
            cleanup_called.append("working")
        
        sample_run_context.cleanup_handlers = [failing_cleanup, working_cleanup]
        
        # Should not raise exception
        await resource_manager.cleanup_run_resources(sample_run_context)
        
        # Working cleanup should still be called
        assert "working" in cleanup_called


class TestRecoveryManager:
    """Test error recovery and graceful degradation."""
    
    @pytest.fixture
    def recovery_manager(self):
        """Create recovery manager for testing."""
        return RecoveryManager()
    
    @pytest.mark.asyncio
    async def test_tool_error_recovery_attempt(self, recovery_manager, sample_run_context):
        """Test: Tool errors trigger recovery attempts for supported tools."""
        sample_run_context.tool_id = "cruise-control-analyzer"  # Supported tool
        sample_run_context.error_category = ErrorCategory.TOOL_ERROR
        
        with patch.object(recovery_manager, '_retry_with_fallback') as mock_retry:
            mock_retry.return_value = True
            
            result = await recovery_manager.attempt_recovery(sample_run_context)
            
            assert result is True
            assert sample_run_context.recovery_attempted is True
            mock_retry.assert_called_once_with(sample_run_context)
    
    @pytest.mark.asyncio
    async def test_transient_system_error_recovery(self, recovery_manager, sample_run_context):
        """Test: Transient system errors trigger retry."""
        sample_run_context.error_category = ErrorCategory.SYSTEM_ERROR
        sample_run_context.error_details = {
            "system_error": "Connection temporarily unavailable"
        }
        
        with patch.object(recovery_manager, '_retry_execution') as mock_retry:
            mock_retry.return_value = True
            
            result = await recovery_manager.attempt_recovery(sample_run_context)
            
            assert result is True
            assert sample_run_context.recovery_attempted is True
            mock_retry.assert_called_once_with(sample_run_context)
    
    def test_error_fix_suggestions(self, recovery_manager):
        """Test: Error fix suggestions are generated appropriately."""
        # Test memory error
        suggestion = recovery_manager.suggest_tool_fix(
            RuntimeError("Tool failed"), 
            stderr="MemoryError: out of memory"
        )
        assert "memory" in suggestion.lower()
        
        # Test permission error
        suggestion = recovery_manager.suggest_tool_fix(
            PermissionError("Access denied"),
            stderr="Permission denied"
        )
        assert "permission" in suggestion.lower()
        
        # Test file not found
        suggestion = recovery_manager.suggest_tool_fix(
            FileNotFoundError("File not found"),
            stderr="file not found"
        )
        assert "missing" in suggestion.lower() or "not found" in suggestion.lower()
        
        # Test timeout
        suggestion = recovery_manager.suggest_tool_fix(
            TimeoutError("Operation timed out"),
            stderr=""
        )
        assert "timeout" in suggestion.lower()


class TestErrorResponseGeneration:
    """Test enhanced error response generation."""
    
    def test_error_code_generation(self, sample_run_context):
        """Test: Error codes are generated correctly."""
        sample_run_context.error_category = ErrorCategory.TOOL_ERROR
        sample_run_context.error_details = {"error_type": "RuntimeError"}
        
        error_response = ErrorResponse.from_run_context(sample_run_context)
        
        assert error_response.error_code == "TOOL_ERROR_RUNTIMEERROR"
    
    def test_user_message_generation(self, sample_run_context):
        """Test: User-friendly messages are generated for each error category."""
        # Test validation error message
        sample_run_context.error_category = ErrorCategory.VALIDATION_ERROR
        sample_run_context.error = "Invalid parameter"
        
        error_response = ErrorResponse.from_run_context(sample_run_context)
        assert "Invalid input" in error_response.user_message
        
        # Test system error message
        sample_run_context.error_category = ErrorCategory.SYSTEM_ERROR
        error_response = ErrorResponse.from_run_context(sample_run_context)
        assert "System error occurred" in error_response.user_message
        
        # Test tool error message
        sample_run_context.error_category = ErrorCategory.TOOL_ERROR
        error_response = ErrorResponse.from_run_context(sample_run_context)
        assert "failed to execute" in error_response.user_message
    
    def test_suggestion_generation(self, sample_run_context):
        """Test: Actionable suggestions are generated for each error category."""
        sample_run_context.error_details = {"suggested_fix": "Custom suggestion"}
        
        # Test validation error suggestions
        sample_run_context.error_category = ErrorCategory.VALIDATION_ERROR
        error_response = ErrorResponse.from_run_context(sample_run_context)
        
        suggestions = error_response.suggested_actions
        assert "Custom suggestion" in suggestions
        assert any("parameter" in s.lower() for s in suggestions)
        
        # Verify suggestion limit
        assert len(suggestions) <= 5