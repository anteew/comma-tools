"""Run management endpoints for tool execution."""

import logging
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException

from .execution import ExecutionEngine
from .models import RunRequest, RunResponse
from .registry import ToolRegistry

logger = logging.getLogger(__name__)

router = APIRouter()

_registry: Optional[ToolRegistry] = None
_engine: Optional[ExecutionEngine] = None


def get_registry() -> ToolRegistry:
    """Get tool registry instance."""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry


def get_execution_engine() -> ExecutionEngine:
    """Get execution engine instance."""
    global _engine
    if _engine is None:
        _engine = ExecutionEngine(get_registry())
    return _engine


@router.post("/runs", response_model=RunResponse)
async def start_run(
    request: RunRequest, engine: ExecutionEngine = Depends(get_execution_engine)
) -> RunResponse:
    """
    Start tool execution.

    Creates a new tool run with the specified parameters and starts execution
    in the background. Returns immediately with run ID and queued status.

    Args:
        request: Run request with tool ID and parameters
        engine: Execution engine dependency

    Returns:
        Run response with run ID and initial status

    Raises:
        HTTPException: If tool not found or parameters invalid
    """
    try:
        response = await engine.start_run(request)
        logger.info(f"Started run {response.run_id} for tool {request.tool_id}")
        return response
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to start run: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/runs/{run_id}", response_model=RunResponse)
async def get_run_status(
    run_id: str, engine: ExecutionEngine = Depends(get_execution_engine)
) -> RunResponse:
    """
    Get run status.

    Returns the current status and details of a tool run including
    progress, artifacts, and any error information.

    Args:
        run_id: Run identifier
        engine: Execution engine dependency

    Returns:
        Current run status and details

    Raises:
        HTTPException: If run not found
    """
    try:
        response = await engine.get_run_status(run_id)
        return response
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get run status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/runs/{run_id}")
async def cancel_run(
    run_id: str, engine: ExecutionEngine = Depends(get_execution_engine)
) -> Dict[str, str]:
    """
    Cancel run.

    Attempts to cancel a running tool execution. Returns success
    status indicating whether the run was cancelled.

    Args:
        run_id: Run identifier
        engine: Execution engine dependency

    Returns:
        Cancellation status
    """
    try:
        cancelled = engine.cancel_run(run_id)
        if cancelled:
            logger.info(f"Cancelled run {run_id}")
            return {"message": "Run cancelled", "run_id": run_id}
        else:
            return {"message": "Run not found or already completed", "run_id": run_id}
    except Exception as e:
        logger.error(f"Failed to cancel run: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
