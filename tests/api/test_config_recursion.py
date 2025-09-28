"""Tests for configuration recursion issues in type coercion."""

import pytest
from typing import List

from comma_tools.api.config import ConfigManager


class TestConfigRecursionIssues:
    """Test configuration type coercion recursion protection."""

    def test_recursion_depth_protection(self):
        """Test: Recursion depth protection prevents infinite loops."""
        # Create a deeply nested type that will hit the recursion limit
        deep_type = List[List[List[List[List[List[List[List[List[List[List[str]]]]]]]]]]]

        # This should raise a ValueError due to recursion depth limit
        with pytest.raises(ValueError, match="recursion depth exceeded"):
            ConfigManager._coerce_env_value("test", deep_type)

    def test_reasonable_nesting_still_works(self):
        """Test: Reasonable levels of nesting still work."""
        # A reasonably nested type should still work
        result = ConfigManager._coerce_env_value("a,b,c", List[List[List[str]]])
        # This should work without hitting recursion limits
        assert result == [[["a"]], [["b"]], [["c"]]]

    def test_simple_list_type_works(self):
        """Test: Simple list types work correctly."""
        result = ConfigManager._coerce_env_value("a,b,c", List[str])
        assert result == ["a", "b", "c"]

    def test_nested_list_current_behavior(self):
        """Test: Nested list behavior is consistent."""
        result = ConfigManager._coerce_env_value("a,b,c", List[List[str]])
        assert result == [["a"], ["b"], ["c"]]

    def test_json_array_nested_case(self):
        """Test: JSON array case with nested structure."""
        result = ConfigManager._coerce_env_value('[["a", "b"], ["c", "d"]]', List[List[str]])
        # This should work correctly with JSON input
        assert result == [["a", "b"], ["c", "d"]]

    def test_direct_parse_list_recursion_protection(self):
        """Test: Direct call to _parse_list_value also has recursion protection."""
        deep_type = List[List[List[List[List[List[List[List[List[List[List[str]]]]]]]]]]]

        with pytest.raises(ValueError, match="recursion depth exceeded"):
            ConfigManager._parse_list_value("test", deep_type)
