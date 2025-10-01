"""
Phone-A-Friend MCP Server

MCP server that exposes OpenAI GPT-5 agent to Claude, enabling Claude to
delegate complex reasoning tasks to GPT-5 and orchestrate between GPT-5
and comma-tools analysis capabilities.
"""

import asyncio
import os
from typing import Any, Dict, Optional

from agents import Agent
from mcp.server.fastmcp import FastMCP

from .config import load_config
from .rate_limiter import RateLimiter
from .session import SessionManager

# Create MCP server
mcp = FastMCP("phone-a-friend")

_config = None
_session_manager = None
_rate_limiter = None


def initialize_server() -> None:
    """Initialize server components."""
    global _config, _session_manager, _rate_limiter

    _config = load_config()

    try:
        _config.get_api_key()
    except ValueError as e:
        raise RuntimeError(f"Failed to initialize: {e}")

    os.environ["OPENAI_API_KEY"] = _config.get_api_key()

    _session_manager = SessionManager(
        max_concurrent=_config.max_concurrent_sessions,
        timeout_seconds=_config.session_timeout_seconds,
    )

    _rate_limiter = RateLimiter(
        max_requests_per_minute=_config.max_requests_per_minute,
        cost_limit_per_session=_config.cost_limit_per_session,
        cost_limit_per_day=_config.cost_limit_per_day,
    )


def _get_globals():
    """Get initialized global components."""
    assert _config is not None, "Server not initialized"
    assert _session_manager is not None, "Server not initialized"
    assert _rate_limiter is not None, "Server not initialized"
    return _config, _session_manager, _rate_limiter


initialize_server()


@mcp.tool()
async def start_gpt5_session(
    instructions: str,
    context: Optional[Dict[str, Any]] = None,
    model: Optional[str] = None,
    reasoning_effort: Optional[str] = None,
    enable_code_interpreter: bool = False,
    enable_file_search: bool = False,
) -> Dict[str, Any]:
    """
    Start a new GPT-5 agent session for collaboration.

    Use this when you (Claude) want to consult with GPT-5 on a complex problem
    involving comma.ai vehicle logs, cruise control analysis, or CAN bus debugging.

    Args:
        instructions: System instructions for GPT-5 (describe the problem domain,
                     vehicle context, and what kind of expertise is needed)
        context: Optional context dict with vehicle info, log paths, or analysis goals
        model: OpenAI model to use (e.g., "gpt-4o", "o1-preview", "o1-mini").
               Defaults to configured model (gpt-4o)
        reasoning_effort: Reasoning effort for o1 models - "low", "medium", or "high".
                         Only applies to o1-preview and o1-mini models
        enable_code_interpreter: Enable Python code execution for data analysis
        enable_file_search: Enable file search capabilities for document analysis

    Returns:
        Dictionary with session_id and status

    Example:
        >>> start_gpt5_session(
        ...     instructions="You are an expert in automotive CAN bus analysis. "
        ...                  "Help debug a Subaru cruise control issue.",
        ...     model="o1-preview",
        ...     reasoning_effort="high",
        ...     enable_code_interpreter=True,
        ...     context={"vehicle": "2019 Subaru Outback", "issue": "cruise_control"}
        ... )
    """
    config, session_manager, rate_limiter = _get_globals()

    allowed, reason = rate_limiter.check_rate_limit()
    if not allowed:
        return {
            "status": "error",
            "error": reason,
            "usage": rate_limiter.get_usage_summary(),
        }

    try:
        session = await session_manager.create_session(
            instructions=instructions,
            metadata=context or {},
            model=model or config.model_name,
            reasoning_effort=reasoning_effort,
            enable_code_interpreter=enable_code_interpreter,
            enable_file_search=enable_file_search,
        )

        return {
            "status": "success",
            "session_id": session.session_id,
            "message": "GPT-5 session started. Use send_message() to interact.",
            "model": session.agent.model if session.agent else model or config.model_name,
            "tools_enabled": {
                "code_interpreter": enable_code_interpreter,
                "file_search": enable_file_search,
            },
            "usage": rate_limiter.get_usage_summary(session.session_id),
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
        }


@mcp.tool()
async def send_message_to_gpt5(
    session_id: str,
    message: str,
) -> Dict[str, Any]:
    """
    Send a message to GPT-5 and get a response.

    Args:
        session_id: Session ID from start_gpt5_session()
        message: Your message to GPT-5 (can include analysis results, questions, etc.)

    Returns:
        Dictionary with GPT-5's response and metadata

    Example:
        >>> send_message_to_gpt5(
        ...     session_id="abc-123",
        ...     message="I've run rlog-to-csv on the log file. Here's what I found: ..."
        ... )
    """
    config, session_manager, rate_limiter = _get_globals()

    allowed, reason = rate_limiter.check_rate_limit()
    if not allowed:
        return {
            "status": "error",
            "error": reason,
            "usage": rate_limiter.get_usage_summary(),
        }

    allowed, reason = rate_limiter.check_session_cost_limit(session_id)
    if not allowed:
        return {
            "status": "error",
            "error": reason,
            "usage": rate_limiter.get_usage_summary(session_id),
        }

    try:
        result = await session_manager.send_message(session_id, message)

        estimated_cost = 0.01  # Placeholder
        rate_limiter.record_request(session_id, tokens=0, cost=estimated_cost)

        return {
            "status": "success",
            "response": result.final_output,
            "session_id": session_id,
            "usage": rate_limiter.get_usage_summary(session_id),
        }
    except ValueError as e:
        return {
            "status": "error",
            "error": str(e),
        }
    except Exception as e:
        return {
            "status": "error",
            "error": f"Unexpected error: {e}",
        }


@mcp.tool()
async def end_gpt5_session(session_id: str) -> Dict[str, Any]:
    """
    End a GPT-5 session and clean up resources.

    Args:
        session_id: Session ID to end

    Returns:
        Dictionary with status and final usage metrics
    """
    config, session_manager, rate_limiter = _get_globals()

    try:
        usage = rate_limiter.get_usage_summary(session_id)

        ended = await session_manager.end_session(session_id)
        rate_limiter.cleanup_session(session_id)

        if ended:
            return {
                "status": "success",
                "message": "Session ended successfully",
                "final_usage": usage,
            }
        else:
            return {
                "status": "error",
                "error": "Session not found",
            }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
        }


@mcp.tool()
async def list_gpt5_sessions() -> Dict[str, Any]:
    """
    List all active GPT-5 sessions.

    Returns:
        Dictionary with list of active sessions
    """
    config, session_manager, rate_limiter = _get_globals()

    try:
        sessions = await session_manager.list_sessions()
        return {
            "status": "success",
            "sessions": sessions,
            "count": len(sessions),
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
        }


@mcp.tool()
async def get_usage_stats(session_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Get usage statistics and cost information.

    Args:
        session_id: Optional session ID for session-specific stats

    Returns:
        Dictionary with usage and cost metrics
    """
    config, session_manager, rate_limiter = _get_globals()

    try:
        return {
            "status": "success",
            "usage": rate_limiter.get_usage_summary(session_id),
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
        }


@mcp.tool()
async def get_model_capabilities() -> Dict[str, Any]:
    """
    Get matrix of available OpenAI models and their supported capabilities.

    Use this to understand which models support reasoning_effort, code_interpreter,
    file_search, and other features before starting a session.

    Returns:
        Dictionary with model capabilities matrix and feature descriptions

    Example:
        >>> capabilities = get_model_capabilities()
        >>> # Check if o1-preview supports reasoning_effort
        >>> capabilities["models"]["o1-preview"]["supports_reasoning_effort"]
    """
    config, session_manager, rate_limiter = _get_globals()

    models = {
        "gpt-4o": {
            "description": "Most capable GPT-4 model, multimodal",
            "context_window": 128000,
            "supports_reasoning_effort": False,
            "supports_code_interpreter": True,
            "supports_file_search": True,
            "supports_function_calling": True,
            "use_cases": ["General intelligence", "Complex problem solving", "Code generation"],
        },
        "gpt-4o-mini": {
            "description": "Faster, more affordable GPT-4o",
            "context_window": 128000,
            "supports_reasoning_effort": False,
            "supports_code_interpreter": True,
            "supports_file_search": True,
            "supports_function_calling": True,
            "use_cases": ["Faster responses", "Cost optimization"],
        },
        "gpt-4-turbo": {
            "description": "Previous generation GPT-4 Turbo",
            "context_window": 128000,
            "supports_reasoning_effort": False,
            "supports_code_interpreter": True,
            "supports_file_search": True,
            "supports_function_calling": True,
            "use_cases": ["Legacy applications", "Proven reliability"],
        },
        "o1-preview": {
            "description": "Advanced reasoning model with extended thinking",
            "context_window": 128000,
            "supports_reasoning_effort": True,
            "supports_code_interpreter": True,
            "supports_file_search": False,
            "supports_function_calling": False,
            "reasoning_effort_levels": ["low", "medium", "high"],
            "use_cases": ["Complex reasoning", "Math/science", "Code analysis"],
        },
        "o1-mini": {
            "description": "Faster reasoning model, optimized for STEM",
            "context_window": 128000,
            "supports_reasoning_effort": True,
            "supports_code_interpreter": True,
            "supports_file_search": False,
            "supports_function_calling": False,
            "reasoning_effort_levels": ["low", "medium", "high"],
            "use_cases": ["STEM reasoning", "Faster than o1-preview", "Cost-effective reasoning"],
        },
    }

    features = {
        "reasoning_effort": {
            "description": "Control depth of reasoning for o1 models",
            "levels": {
                "low": "Faster response, less thorough reasoning",
                "medium": "Balanced reasoning depth (default)",
                "high": "Maximum reasoning depth, slower but most thorough",
            },
            "supported_models": ["o1-preview", "o1-mini"],
        },
        "code_interpreter": {
            "description": "Execute Python code for calculations and data analysis",
            "capabilities": [
                "Run Python code in sandboxed environment",
                "Data analysis and visualization",
                "File processing and manipulation",
            ],
            "supported_models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "o1-preview", "o1-mini"],
        },
        "file_search": {
            "description": "Search through uploaded documents and files",
            "capabilities": [
                "Semantic search across documents",
                "Extract information from files",
                "Cite sources from documents",
            ],
            "supported_models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
        },
    }

    available_models = []
    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=config.get_api_key())
        models_response = await client.models.list()
        available_models = [
            m.id
            for m in models_response.data
            if any(known in m.id for known in ["gpt-4", "gpt-3.5", "o1"])
        ]
    except Exception:
        available_models = list(models.keys())

    return {
        "status": "success",
        "models": models,
        "features": features,
        "available_models": available_models,
        "default_model": config.model_name,
        "recommendations": {
            "general_use": "gpt-4o - Best balance of capability and speed",
            "complex_reasoning": "o1-preview with reasoning_effort='high' - Maximum thinking depth",
            "fast_reasoning": "o1-mini with reasoning_effort='medium' - Fast STEM reasoning",
            "cost_effective": "gpt-4o-mini - Cheaper, still very capable",
            "can_bus_analysis": "o1-preview or gpt-4o with code_interpreter enabled",
        },
    }


@mcp.tool()
def check_health() -> Dict[str, Any]:
    """
    Check if phone-a-friend server is healthy.

    Returns:
        Dictionary with health status
    """
    config, session_manager, rate_limiter = _get_globals()

    try:
        config.get_api_key()

        return {
            "status": "healthy",
            "model": config.model_name,
            "max_concurrent_sessions": config.max_concurrent_sessions,
            "active_sessions": len(session_manager.sessions),
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
        }


@mcp.resource("paf://config")
def get_server_config() -> str:
    """Get current phone-a-friend server configuration and status."""
    config, session_manager, rate_limiter = _get_globals()

    health = check_health()
    usage = rate_limiter.get_usage_summary()

    return f"""Phone-A-Friend Server Configuration:

Status: {health.get('status', 'unknown')}
Model: {health.get('model', 'unknown')}
Max Concurrent Sessions: {health.get('max_concurrent_sessions', 'unknown')}
Active Sessions: {health.get('active_sessions', 0)}

Usage:
- Daily Cost: ${usage.get('daily_cost', 0):.2f} / ${usage.get('daily_cost_limit', 0):.2f}
- Requests Per Minute: {usage.get('requests_per_minute', 0)} / {usage.get('requests_per_minute_limit', 0)}
- Total Requests: {usage.get('total_requests', 0)}
- Total Cost: ${usage.get('total_cost', 0):.2f}
"""


@mcp.resource("paf://usage")
def get_usage_info() -> str:
    """Get detailed usage and cost information."""
    config, session_manager, rate_limiter = _get_globals()

    usage = rate_limiter.get_usage_summary()

    return f"""Phone-A-Friend Usage Statistics:

Cost Controls:
- Daily Cost: ${usage.get('daily_cost', 0):.2f} / ${usage.get('daily_cost_limit', 0):.2f}
- Daily Remaining: ${usage.get('daily_cost_remaining', 0):.2f}

Rate Limits:
- Current Requests/Min: {usage.get('requests_per_minute', 0)} / {usage.get('requests_per_minute_limit', 0)}

Totals:
- Total Requests: {usage.get('total_requests', 0)}
- Total Tokens: {usage.get('total_tokens', 0)}
- Total Cost: ${usage.get('total_cost', 0):.2f}
"""


if __name__ == "__main__":
    config, session_manager, rate_limiter = _get_globals()
    asyncio.run(session_manager.start_cleanup_task())

    # Run the server
    mcp.run()
