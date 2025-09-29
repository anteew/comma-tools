"""Tests for tool registry functionality."""

from unittest.mock import patch

import pytest

from comma_tools.api.registry import ToolRegistry


def test_registry_initialization():
    """Test registry initializes and discovers tools."""
    registry = ToolRegistry()

    assert len(registry.tools) > 0
    assert "rlog-to-csv" in registry.tools
    assert "can-bitwatch" in registry.tools


def test_get_tool_success():
    """Test getting existing tool."""
    registry = ToolRegistry()

    tool = registry.get_tool("rlog-to-csv")
    assert tool.id == "rlog-to-csv"
    assert tool.name == "RLog to CSV Converter"
    assert tool.category == "analyzer"


def test_get_tool_not_found():
    """Test getting non-existent tool raises KeyError."""
    registry = ToolRegistry()

    with pytest.raises(KeyError, match="Tool 'nonexistent' not found"):
        registry.get_tool("nonexistent")


# cruise-control-analyzer tests removed - tool has been deprecated


def test_create_tool_instance_rlog_to_csv():
    """Test creating rlog to csv tool instance."""
    registry = ToolRegistry()

    instance = registry.create_tool_instance("rlog-to-csv")

    assert callable(instance)


def test_create_tool_instance_can_bitwatch():
    """Test creating can bitwatch tool instance."""
    registry = ToolRegistry()

    instance = registry.create_tool_instance("can-bitwatch")

    assert callable(instance)


def test_create_tool_instance_unknown_tool():
    """Test creating instance for unknown tool."""
    registry = ToolRegistry()

    with pytest.raises(ValueError, match="Tool instance creation not implemented"):
        registry.create_tool_instance("unknown-tool")


def test_list_tools():
    """Test listing all available tools."""
    registry = ToolRegistry()

    tools = registry.list_tools()

    assert isinstance(tools, dict)
    assert len(tools) >= 2
    assert "rlog-to-csv" in tools
    assert "can-bitwatch" in tools

    tools.clear()
    assert len(registry.tools) > 0
