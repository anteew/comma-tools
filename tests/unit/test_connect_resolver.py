"""
Unit tests for comma connect route resolver.
"""

from unittest.mock import Mock

import pytest

from comma_tools.sources.connect.resolver import RouteResolver


class TestRouteResolver:
    """Test route resolution functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_client = Mock()
        self.resolver = RouteResolver(self.mock_client)

    def test_parse_canonical_route(self):
        """Test parsing canonical route names."""
        canonical = "dcb4c2e18426be55|2024-04-19--12-33-20"
        input_type, value = self.resolver.parse_input(canonical)

        assert input_type == "canonical"
        assert value == canonical

    def test_parse_connect_url(self):
        """Test parsing connect URLs."""
        connect_url = "https://connect.comma.ai/dcb4c2e18426be55/00000008--0696c823fa"
        input_type, value = self.resolver.parse_input(connect_url)

        assert input_type == "connect"
        assert value == "dcb4c2e18426be55"

    def test_parse_invalid_input(self):
        """Test parsing invalid input raises error."""
        invalid_inputs = [
            "not-a-route",
            "https://example.com/invalid",
            "dcb4c2e18426be55|invalid-timestamp",
            "",
        ]

        for invalid_input in invalid_inputs:
            with pytest.raises(ValueError) as exc_info:
                self.resolver.parse_input(invalid_input)

            assert "Invalid input format" in str(exc_info.value)

    def test_resolve_canonical_route(self):
        """Test resolving canonical route (passthrough)."""
        canonical = "dcb4c2e18426be55|2024-04-19--12-33-20"
        result = self.resolver.resolve(canonical)

        assert result == canonical
        self.mock_client.device_segments.assert_not_called()

    def test_resolve_connect_url_success(self):
        """Test successful connect URL resolution."""
        connect_url = "https://connect.comma.ai/dcb4c2e18426be55/00000008--0696c823fa"

        mock_segments = [
            {
                "url": "https://example.com/00000008--0696c823fa/segment",
                "start_time_utc": "2024-04-19T12:33:20Z",
            }
        ]
        self.mock_client.device_segments.return_value = mock_segments

        result = self.resolver.resolve(connect_url)

        assert result == "dcb4c2e18426be55|2024-04-19--12-33-20"
        self.mock_client.device_segments.assert_called_once()

    def test_resolve_connect_url_not_found(self):
        """Test connect URL resolution when URL not found in segments."""
        connect_url = "https://connect.comma.ai/dcb4c2e18426be55/00000008--0696c823fa"

        self.mock_client.device_segments.return_value = []

        with pytest.raises(ValueError) as exc_info:
            self.resolver.resolve(connect_url)

        assert "Couldn't map Connect URL" in str(exc_info.value)
        assert "--days" in str(exc_info.value)
