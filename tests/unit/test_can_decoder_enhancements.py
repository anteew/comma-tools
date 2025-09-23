"""Tests for enhanced CAN decoder functionality."""

import pytest
from comma_tools.can import SubaruCANDecoder, CANDecodingError


class TestCANDecoderEnhancements:
    """Test enhanced decoder functionality."""

    def test_decode_message_wheel_speeds(self):
        """Test generic decode_message for wheel speeds."""
        test_data = b"\x00\x01\x02\x03\x04\x05\x06\x07"
        result = SubaruCANDecoder.decode_message(
            SubaruCANDecoder.WHEEL_SPEEDS_ADDR, test_data, validate=False
        )

        assert result is not None
        assert "FL" in result
        assert "avg_mph" in result

    def test_decode_message_cruise_buttons(self):
        """Test generic decode_message for cruise buttons."""
        test_data = b"\x00\x01\x02\x03\x04\x05\x06\x07"
        result = SubaruCANDecoder.decode_message(SubaruCANDecoder.CRUISE_BUTTONS_ADDR, test_data)

        assert result is not None
        assert "main" in result
        assert "set" in result
        assert "resume" in result

    def test_decode_message_unknown_address(self):
        """Test generic decode_message with unknown address."""
        test_data = b"\x00\x01\x02\x03\x04\x05\x06\x07"
        result = SubaruCANDecoder.decode_message(0x999, test_data)

        assert result is None

    def test_get_supported_addresses(self):
        """Test getting supported addresses."""
        addresses = SubaruCANDecoder.get_supported_addresses()

        assert isinstance(addresses, dict)
        assert SubaruCANDecoder.WHEEL_SPEEDS_ADDR in addresses
        assert SubaruCANDecoder.CRUISE_BUTTONS_ADDR in addresses
        assert SubaruCANDecoder.CRUISE_STATUS_ADDR in addresses
        assert SubaruCANDecoder.ES_BRAKE_ADDR in addresses
        assert SubaruCANDecoder.DASHLIGHTS_ADDR in addresses

        assert addresses[SubaruCANDecoder.WHEEL_SPEEDS_ADDR] == "Wheel_Speeds"
        assert addresses[SubaruCANDecoder.CRUISE_BUTTONS_ADDR] == "Cruise_Buttons"

    def test_wheel_speeds_validation_disabled(self):
        """Test wheel speeds with validation disabled."""
        test_data = b"\x00\x01\x02\x03\x04\x05\x06\x07"
        result = SubaruCANDecoder.decode_wheel_speeds(test_data, validate=False)

        assert result is not None
        assert "FL" in result

    def test_wheel_speeds_validation_error(self):
        """Test wheel speeds validation error."""
        test_data = b"\xff\xff\xff\xff\xff\xff\xff\xff"

        with pytest.raises(CANDecodingError):
            SubaruCANDecoder.decode_wheel_speeds(test_data, validate=True)

    def test_cruise_status_validation_disabled(self):
        """Test cruise status with validation disabled."""
        test_data = b"\x00\x01\x02\x03\x04\x05\x06\x07"
        result = SubaruCANDecoder.decode_cruise_status(test_data, validate=False)

        assert result is not None
        assert "cruise_set_speed" in result

    def test_cruise_status_validation_error(self):
        """Test cruise status validation error."""
        test_data = b"\xff\xff\xff\xff\xff\xff\xff\xff"

        with pytest.raises(CANDecodingError):
            SubaruCANDecoder.decode_cruise_status(test_data, validate=True)

    def test_can_decoding_error_inheritance(self):
        """Test that CANDecodingError is properly defined."""
        error = CANDecodingError("test error")
        assert isinstance(error, Exception)
        assert str(error) == "test error"
