"""Tests for execution engine functionality."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from comma_tools.api.execution import ExecutionEngine, RunContext
from comma_tools.api.models import RunRequest, RunStatus
from comma_tools.api.registry import ToolRegistry


@pytest.fixture
def mock_registry():
    """Create mock registry for testing."""
    registry = MagicMock(spec=ToolRegistry)

    mock_tool = MagicMock()
    mock_tool.id = "test-tool"
    mock_tool.parameters = {
        "param1": MagicMock(required=True, type="str", choices=None),
        "param2": MagicMock(required=False, type="int", choices=None, default=42),
    }

    registry.get_tool.return_value = mock_tool
    registry.create_tool_instance.return_value = MagicMock()

    return registry


@pytest.fixture
def execution_engine(mock_registry):
    """Create execution engine with mock registry."""
    return ExecutionEngine(mock_registry)


def test_run_context_initialization():
    """Test run context initialization."""
    context = RunContext("test-run", "test-tool", {"param": "value"})

    assert context.run_id == "test-run"
    assert context.tool_id == "test-tool"
    assert context.params == {"param": "value"}
    assert context.status == RunStatus.QUEUED
    assert context.created_at is not None
    assert context.started_at is None
    assert context.completed_at is None
    assert context.progress is None
    assert context.error is None
    assert context.artifacts == []


def test_run_context_to_response():
    """Test converting run context to response."""
    context = RunContext("test-run", "test-tool", {"param": "value"})

    response = context.to_response()

    assert response.run_id == "test-run"
    assert response.tool_id == "test-tool"
    assert response.status == RunStatus.QUEUED
    assert response.params == {"param": "value"}


@pytest.mark.asyncio
async def test_start_run_success(execution_engine, mock_registry):
    """Test successful run start."""
    request = RunRequest(tool_id="test-tool", params={"param1": "value1", "param2": 123})

    with patch("asyncio.create_task") as mock_create_task:
        response = await execution_engine.start_run(request)

    assert response.tool_id == "test-tool"
    assert response.status == RunStatus.QUEUED
    assert response.params == {"param1": "value1", "param2": 123}
    assert response.run_id in execution_engine.active_runs

    mock_create_task.assert_called_once()


@pytest.mark.asyncio
async def test_start_run_tool_not_found(execution_engine, mock_registry):
    """Test run start with non-existent tool."""
    mock_registry.get_tool.side_effect = KeyError("Tool not found")

    request = RunRequest(tool_id="nonexistent-tool")

    response = await execution_engine.start_run(request)

    assert response.status == RunStatus.FAILED
    assert response.tool_id == "nonexistent-tool"
    assert "Tool not found" in response.error


@pytest.mark.asyncio
async def test_start_run_validation_error(execution_engine, mock_registry):
    """Test run start with validation error."""
    request = RunRequest(tool_id="test-tool", params={})  # Missing required param1

    response = await execution_engine.start_run(request)

    assert response.status == RunStatus.FAILED
    assert response.tool_id == "test-tool"
    assert "Required parameter 'param1' missing" in response.error


@pytest.mark.asyncio
async def test_get_run_status_success(execution_engine):
    """Test getting run status for existing run."""
    context = RunContext("test-run", "test-tool", {})
    execution_engine.active_runs["test-run"] = context

    response = await execution_engine.get_run_status("test-run")

    assert response.run_id == "test-run"
    assert response.tool_id == "test-tool"


@pytest.mark.asyncio
async def test_get_run_status_not_found(execution_engine):
    """Test getting run status for non-existent run."""
    with pytest.raises(KeyError, match="Run 'nonexistent' not found"):
        await execution_engine.get_run_status("nonexistent")


@pytest.mark.asyncio
async def test_execute_tool_async_success(execution_engine, mock_registry):
    """Test successful tool execution."""
    context = RunContext("test-run", "test-tool", {})

    with patch.object(execution_engine, "_execute_tool_sync") as mock_sync:
        with patch("asyncio.get_event_loop") as mock_loop:
            mock_executor = AsyncMock()
            mock_loop.return_value.run_in_executor = mock_executor

            await execution_engine.execute_tool_async(context)

    assert context.status == RunStatus.COMPLETED
    assert context.started_at is not None
    assert context.completed_at is not None
    assert context.progress == 100

    mock_executor.assert_called_once()


@pytest.mark.asyncio
async def test_execute_tool_async_failure(execution_engine, mock_registry):
    """Test tool execution failure."""
    context = RunContext("test-run", "test-tool", {})

    with patch.object(execution_engine, "_execute_tool_sync") as mock_sync:
        mock_sync.side_effect = RuntimeError("Tool failed")

        with patch("asyncio.get_event_loop") as mock_loop:
            mock_executor = AsyncMock()
            mock_executor.side_effect = RuntimeError("Tool failed")
            mock_loop.return_value.run_in_executor = mock_executor

            await execution_engine.execute_tool_async(context)

    assert context.status == RunStatus.FAILED
    assert context.error == "Tool failed"
    assert context.completed_at is not None


def test_validate_parameters_success(execution_engine, mock_registry):
    """Test successful parameter validation."""
    tool = mock_registry.get_tool.return_value
    params = {"param1": "value1", "param2": "123"}

    execution_engine._validate_parameters(tool, params, None)

    assert params["param2"] == 123


def test_validate_parameters_missing_required(execution_engine, mock_registry):
    """Test validation with missing required parameter."""
    tool = mock_registry.get_tool.return_value
    params = {"param2": 123}  # Missing required param1

    with pytest.raises(ValueError, match="Required parameter 'param1' missing"):
        execution_engine._validate_parameters(tool, params, None)


def test_validate_parameters_type_conversion(execution_engine, mock_registry):
    """Test parameter type conversion."""
    tool = mock_registry.get_tool.return_value
    tool.parameters["float_param"] = MagicMock(required=False, type="float", choices=None)
    tool.parameters["bool_param"] = MagicMock(required=False, type="bool", choices=None)

    params = {"param1": "value1", "float_param": "3.14", "bool_param": "true"}

    execution_engine._validate_parameters(tool, params, None)

    assert params["float_param"] == 3.14
    assert params["bool_param"] is True


def test_cancel_run_success(execution_engine):
    """Test successful run cancellation."""
    context = RunContext("test-run", "test-tool", {})
    context.status = RunStatus.RUNNING
    execution_engine.active_runs["test-run"] = context

    result = execution_engine.cancel_run("test-run")

    assert result is True
    assert context.status == RunStatus.CANCELED
    assert context.error == "Cancelled by user"
    assert context.completed_at is not None


def test_cancel_run_not_found(execution_engine):
    """Test cancelling non-existent run."""
    result = execution_engine.cancel_run("nonexistent")

    assert result is False


def test_cancel_run_already_completed(execution_engine):
    """Test cancelling already completed run."""
    context = RunContext("test-run", "test-tool", {})
    context.status = RunStatus.COMPLETED
    execution_engine.active_runs["test-run"] = context

    result = execution_engine.cancel_run("test-run")

    assert result is False
