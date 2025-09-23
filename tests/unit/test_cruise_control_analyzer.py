"""Unit tests for cruise control analyzer."""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from comma_tools.analyzers.cruise_control_analyzer import MarkerConfig
from comma_tools.can import SubaruCANDecoder


class TestSubaruCANDecoder:
    """Test cases for SubaruCANDecoder class."""

    def test_decode_wheel_speeds_valid_data(self):
        """Test decoding valid wheel speed data."""
        test_data = b"\x00\x01\x02\x03\x04\x05\x06\x07"
        result = SubaruCANDecoder.decode_wheel_speeds(test_data)

        if result is not None:
            assert isinstance(result, dict)
            expected_keys = ["front_left", "front_right", "rear_left", "rear_right"]
            for key in expected_keys:
                if key in result:
                    assert isinstance(result[key], (int, float))

    def test_decode_wheel_speeds_invalid_data(self):
        """Test decoding with invalid data."""
        test_data = b"\x00\x01"
        result = SubaruCANDecoder.decode_wheel_speeds(test_data)
        assert result is None

    def test_decode_cruise_buttons_valid_data(self):
        """Test decoding valid cruise button data."""
        test_data = b"\x00\x01\x02\x03\x04\x05\x06\x07"
        result = SubaruCANDecoder.decode_cruise_buttons(test_data)

        if result is not None:
            assert isinstance(result, dict)
            button_fields = ["set", "resume", "cancel", "distance"]
            for field in button_fields:
                if field in result:
                    assert isinstance(result[field], bool)


class TestMarkerConfig:
    """Test cases for MarkerConfig class."""

    def test_marker_config_creation(self):
        """Test creating a MarkerConfig instance."""
        config = MarkerConfig(marker_type="blinkers", pre_time=5.0, post_time=10.0, timeout=30.0)

        assert config.marker_type == "blinkers"
        assert config.pre_time == 5.0
        assert config.post_time == 10.0
        assert config.timeout == 30.0

    def test_marker_config_enabled(self):
        """Test marker config enabled property."""
        config = MarkerConfig(marker_type="blinkers")
        assert config.enabled is True

        config_disabled = MarkerConfig(marker_type="none")
        assert config_disabled.enabled is False


class TestCruiseControlAnalyzerIntegration:
    """Integration tests for the full analyzer."""

    @pytest.mark.skip(reason="Requires actual log files and openpilot environment")
    def test_analyzer_end_to_end(self):
        """Test the analyzer with a real log file."""
        pass
