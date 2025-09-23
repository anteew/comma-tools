"""Unit tests for CAN decoder library."""

import pytest
from comma_tools.can import SubaruCANDecoder


class TestSubaruCANDecoder:
    """Test cases for SubaruCANDecoder class."""

    def test_decode_wheel_speeds_valid_data(self):
        """Test decoding valid wheel speed data."""
        test_data = b"\x00\x01\x02\x03\x04\x05\x06\x07"
        result = SubaruCANDecoder.decode_wheel_speeds(test_data)

        assert result is not None
        assert isinstance(result, dict)
        assert "FL" in result
        assert "FR" in result
        assert "RL" in result
        assert "RR" in result
        assert "avg_kph" in result
        assert "avg_mph" in result

        for key in ["FL", "FR", "RL", "RR", "avg_kph", "avg_mph"]:
            assert isinstance(result[key], float)

    def test_decode_wheel_speeds_invalid_data(self):
        """Test decoding with insufficient data."""
        test_data = b"\x00\x01"
        result = SubaruCANDecoder.decode_wheel_speeds(test_data)
        assert result is None

    def test_decode_wheel_speeds_empty_data(self):
        """Test decoding with empty data."""
        test_data = b""
        result = SubaruCANDecoder.decode_wheel_speeds(test_data)
        assert result is None

    def test_decode_cruise_buttons_valid_data(self):
        """Test decoding valid cruise button data."""
        test_data = b"\x00\x01\x02\x03\x04\x05\x06\x07"
        result = SubaruCANDecoder.decode_cruise_buttons(test_data)

        assert result is not None
        assert isinstance(result, dict)
        assert "main" in result
        assert "set" in result
        assert "resume" in result

        for key in ["main", "set", "resume"]:
            assert isinstance(result[key], bool)

    def test_decode_cruise_buttons_invalid_data(self):
        """Test decoding cruise buttons with insufficient data."""
        test_data = b"\x00\x01"
        result = SubaruCANDecoder.decode_cruise_buttons(test_data)
        assert result is None

    def test_decode_cruise_status_valid_data(self):
        """Test decoding valid cruise status data."""
        test_data = b"\x00\x01\x02\x03\x04\x05\x06\x07"
        result = SubaruCANDecoder.decode_cruise_status(test_data)

        assert result is not None
        assert isinstance(result, dict)
        assert "cruise_set_speed" in result
        assert "cruise_on" in result
        assert "cruise_activated" in result

        assert isinstance(result["cruise_set_speed"], int)
        assert isinstance(result["cruise_on"], bool)
        assert isinstance(result["cruise_activated"], bool)

    def test_decode_cruise_status_invalid_data(self):
        """Test decoding cruise status with insufficient data."""
        test_data = b"\x00\x01"
        result = SubaruCANDecoder.decode_cruise_status(test_data)
        assert result is None

    def test_decode_es_brake_valid_data(self):
        """Test decoding valid ES brake data."""
        test_data = b"\x00\x01\x02\x03\x04\x05\x06\x07"
        result = SubaruCANDecoder.decode_es_brake(test_data)

        assert result is not None
        assert isinstance(result, dict)
        assert "cruise_brake_active" in result
        assert "cruise_activated" in result

        assert isinstance(result["cruise_brake_active"], bool)
        assert isinstance(result["cruise_activated"], bool)

    def test_decode_es_brake_invalid_data(self):
        """Test decoding ES brake with insufficient data."""
        test_data = b"\x00\x01"
        result = SubaruCANDecoder.decode_es_brake(test_data)
        assert result is None

    def test_decode_blinkers_valid_data(self):
        """Test decoding valid blinker data."""
        test_data = b"\x00\x01\x02\x03\x04\x05\x06\x07"
        result = SubaruCANDecoder.decode_blinkers(test_data)

        assert result is not None
        assert isinstance(result, dict)
        assert "left" in result
        assert "right" in result

        assert isinstance(result["left"], bool)
        assert isinstance(result["right"], bool)

    def test_decode_blinkers_invalid_data(self):
        """Test decoding blinkers with insufficient data."""
        test_data = b"\x00\x01"
        result = SubaruCANDecoder.decode_blinkers(test_data)
        assert result is None

    def test_address_constants(self):
        """Test that address constants are properly defined."""
        assert SubaruCANDecoder.WHEEL_SPEEDS_ADDR == 0x13A
        assert SubaruCANDecoder.CRUISE_BUTTONS_ADDR == 0x146
        assert SubaruCANDecoder.CRUISE_STATUS_ADDR == 0x241
        assert SubaruCANDecoder.ES_BRAKE_ADDR == 0x220
        assert SubaruCANDecoder.BRAKE_PEDAL_ADDR == 0x139
        assert SubaruCANDecoder.DASHLIGHTS_ADDR == 0x390

    def test_wheel_speeds_conversion_accuracy(self):
        """Test wheel speed conversion accuracy with known values."""
        test_data = b"\x00\x10\x00\x00\x00\x00\x00\x00"
        result = SubaruCANDecoder.decode_wheel_speeds(test_data)

        assert result is not None
        assert result["avg_mph"] == result["avg_kph"] * 0.621371
