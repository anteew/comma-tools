"""Tests for tool registry functionality."""

import pytest

from comma_tools.api.registry import ToolRegistry


def test_registry_initialization():
    """Test registry initializes and discovers tools."""
    registry = ToolRegistry()

    assert len(registry.tools) > 0
    assert "cruise-control-analyzer" in registry.tools
    assert "rlog-to-csv" in registry.tools
    assert "can-bitwatch" in registry.tools


def test_get_tool_success():
    """Test getting existing tool."""
    registry = ToolRegistry()

    tool = registry.get_tool("cruise-control-analyzer")
    assert tool.id == "cruise-control-analyzer"
    assert tool.name == "Cruise Control Analyzer"
    assert tool.category == "analyzer"
    assert "log_file" in tool.parameters


def test_get_tool_not_found():
    """Test getting non-existent tool raises KeyError."""
    registry = ToolRegistry()

    with pytest.raises(KeyError, match="Tool 'nonexistent' not found"):
        registry.get_tool("nonexistent")


def test_create_tool_instance_cruise_control():
    """Test creating cruise control analyzer instance."""
    registry = ToolRegistry()

    instance = registry.create_tool_instance(
        "cruise-control-analyzer", log_file="/path/to/test.zst"
    )

    from comma_tools.analyzers.cruise_control_analyzer import CruiseControlAnalyzer

    assert isinstance(instance, CruiseControlAnalyzer)


def test_create_tool_instance_missing_params():
    """Test creating tool instance with missing required params."""
    registry = ToolRegistry()

    with pytest.raises(ValueError, match="log_file parameter required"):
        registry.create_tool_instance("cruise-control-analyzer")


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
    assert len(tools) >= 3
    assert "cruise-control-analyzer" in tools
    assert "rlog-to-csv" in tools
    assert "can-bitwatch" in tools

    tools.clear()
    assert len(registry.tools) > 0
