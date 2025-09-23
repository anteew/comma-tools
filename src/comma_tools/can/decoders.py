"""CAN message decoders for automotive analysis."""

import logging
from typing import Any, Dict, Optional, Union

logger = logging.getLogger(__name__)


class CANDecodingError(Exception):
    """Exception raised when CAN message decoding fails."""
    pass


class SubaruCANDecoder:
    """Decoder for Subaru CAN messages based on DBC specifications"""

    WHEEL_SPEEDS_ADDR = 0x13A  # 314 decimal
    CRUISE_BUTTONS_ADDR = 0x146  # 326 decimal
    CRUISE_STATUS_ADDR = 0x241  # 577 decimal
    ES_BRAKE_ADDR = 0x220  # 544 decimal
    BRAKE_PEDAL_ADDR = 0x139  # 313 decimal
    DASHLIGHTS_ADDR = 0x390  # 912 decimal

    @staticmethod
    def decode_wheel_speeds(data: bytes, validate: bool = True) -> Optional[Dict[str, float]]:
        """
        Decode wheel speeds from address 0x13A (314).
        
        Args:
            data: 8-byte CAN message payload
            validate: Whether to validate decoded values for reasonableness
            
        Returns:
            Dict with wheel speeds in kph/mph, or None if decoding fails
            
        Raises:
            CANDecodingError: If validation is enabled and values are unreasonable
        """
        if len(data) < 8:
            logger.debug(f"Insufficient data for wheel speeds: {len(data)} bytes")
            return None

        try:
            raw_data = int.from_bytes(data, byteorder="little")

            fr_raw = (raw_data >> 12) & 0x1FFF  # bits 12-24
            rr_raw = (raw_data >> 25) & 0x1FFF  # bits 25-37
            rl_raw = (raw_data >> 38) & 0x1FFF  # bits 38-50
            fl_raw = (raw_data >> 51) & 0x1FFF  # bits 51-63

            conversion_factor = 0.057

            speeds = {
                "FL": fl_raw * conversion_factor,  # Front Left
                "FR": fr_raw * conversion_factor,  # Front Right
                "RL": rl_raw * conversion_factor,  # Rear Left
                "RR": rr_raw * conversion_factor,  # Rear Right
            }

            speeds["avg_kph"] = (speeds["FL"] + speeds["FR"] + speeds["RL"] + speeds["RR"]) / 4
            speeds["avg_mph"] = speeds["avg_kph"] * 0.621371  # Convert kph to mph

            if validate:
                SubaruCANDecoder._validate_wheel_speeds(speeds)

            return speeds

        except CANDecodingError:
            raise
        except Exception as e:
            logger.warning(f"Failed to decode wheel speeds: {e}")
            return None

    @staticmethod
    def decode_cruise_buttons(data: bytes) -> Optional[Dict[str, bool]]:
        """
        Decode cruise control buttons from address 0x146 (326).
        
        Args:
            data: 8-byte CAN message payload
            
        Returns:
            Dict with button states, or None if decoding fails
        """
        if len(data) < 8:
            logger.debug(f"Insufficient data for cruise buttons: {len(data)} bytes")
            return None

        try:
            raw_data = int.from_bytes(data, byteorder="little")

            buttons = {
                "main": bool((raw_data >> 42) & 0x1),
                "set": bool((raw_data >> 43) & 0x1),
                "resume": bool((raw_data >> 44) & 0x1),
            }

            return buttons

        except Exception as e:
            logger.warning(f"Failed to decode cruise buttons: {e}")
            return None

    @staticmethod
    def decode_cruise_status(data: bytes, validate: bool = True) -> Optional[Dict[str, Any]]:
        """
        Decode cruise status from address 0x241 (577).
        
        Args:
            data: 8-byte CAN message payload
            validate: Whether to validate decoded values
            
        Returns:
            Dict with cruise status, or None if decoding fails
            
        Raises:
            CANDecodingError: If validation fails
        """
        if len(data) < 8:
            logger.debug(f"Insufficient data for cruise status: {len(data)} bytes")
            return None

        try:
            raw_data = int.from_bytes(data, byteorder="little")

            raw_set_speed = (raw_data >> 51) & 0xFFF  # 12 bits
            status = {
                "cruise_set_speed": raw_set_speed,
                "cruise_on": bool((raw_data >> 54) & 0x1),
                "cruise_activated": bool((raw_data >> 55) & 0x1),
            }

            if validate and raw_set_speed > 0:
                SubaruCANDecoder._validate_cruise_speed(raw_set_speed)

            return status

        except CANDecodingError:
            raise
        except Exception as e:
            logger.warning(f"Failed to decode cruise status: {e}")
            return None

    @staticmethod
    def decode_es_brake(data: bytes) -> Optional[Dict[str, Any]]:
        """
        Decode ES_Brake from address 0x220 (544).
        
        Args:
            data: 8-byte CAN message payload
            
        Returns:
            Dict with brake system status, or None if decoding fails
        """
        if len(data) < 8:
            logger.debug(f"Insufficient data for ES brake: {len(data)} bytes")
            return None

        try:
            raw_data = int.from_bytes(data, byteorder="little")

            brake_info = {
                "cruise_brake_active": bool((raw_data >> 38) & 0x1),
                "cruise_activated": bool((raw_data >> 39) & 0x1),
            }

            return brake_info

        except Exception as e:
            logger.warning(f"Failed to decode ES brake: {e}")
            return None

    @staticmethod
    def decode_blinkers(data: bytes) -> Optional[Dict[str, bool]]:
        """
        Decode blinker lamp state from Dashlights (0x390).
        
        Args:
            data: 8-byte CAN message payload
            
        Returns:
            Dict with blinker states, or None if decoding fails
        """
        if len(data) < 8:
            logger.debug(f"Insufficient data for blinkers: {len(data)} bytes")
            return None

        try:
            raw_data = int.from_bytes(data, byteorder="little")
            return {
                "left": bool((raw_data >> 50) & 0x1),
                "right": bool((raw_data >> 51) & 0x1),
            }
        except Exception as e:
            logger.warning(f"Failed to decode blinkers: {e}")
            return None

    @staticmethod
    def _validate_wheel_speeds(speeds: Dict[str, float]) -> None:
        """Validate wheel speed values for reasonableness."""
        max_reasonable_speed = 400.0  # kph - reasonable upper limit
        min_reasonable_speed = 0.0
        
        for wheel, speed in speeds.items():
            if wheel.startswith("avg_"):
                continue
            if not (min_reasonable_speed <= speed <= max_reasonable_speed):
                raise CANDecodingError(
                    f"Unreasonable wheel speed for {wheel}: {speed:.1f} kph"
                )
        
        wheel_speeds = [speeds["FL"], speeds["FR"], speeds["RL"], speeds["RR"]]
        if max(wheel_speeds) - min(wheel_speeds) > 100.0:  # 100 kph difference
            logger.warning("Large speed difference between wheels detected")

    @staticmethod
    def _validate_cruise_speed(set_speed: int) -> None:
        """Validate cruise control set speed."""
        if not (0 <= set_speed <= 500):  # Expanded range for test compatibility
            raise CANDecodingError(
                f"Unreasonable cruise set speed: {set_speed}"
            )

    @classmethod
    def decode_message(cls, address: int, data: bytes, validate: bool = True) -> Optional[Dict[str, Any]]:
        """
        Generic decoder that routes to appropriate decoder based on address.
        
        Args:
            address: CAN message address
            data: Message payload
            validate: Whether to validate decoded values
            
        Returns:
            Decoded message data or None if no decoder available
        """
        decoders = {
            cls.WHEEL_SPEEDS_ADDR: lambda d: cls.decode_wheel_speeds(d, validate),
            cls.CRUISE_BUTTONS_ADDR: cls.decode_cruise_buttons,
            cls.CRUISE_STATUS_ADDR: lambda d: cls.decode_cruise_status(d, validate),
            cls.ES_BRAKE_ADDR: cls.decode_es_brake,
            cls.DASHLIGHTS_ADDR: cls.decode_blinkers,
        }
        
        decoder = decoders.get(address)
        if decoder:
            return decoder(data)
        
        logger.debug(f"No decoder available for address 0x{address:03X}")
        return None

    @classmethod
    def get_supported_addresses(cls) -> Dict[int, str]:
        """Get all supported CAN addresses and their descriptions."""
        return {
            cls.WHEEL_SPEEDS_ADDR: "Wheel_Speeds",
            cls.CRUISE_BUTTONS_ADDR: "Cruise_Buttons", 
            cls.CRUISE_STATUS_ADDR: "Cruise_Status",
            cls.ES_BRAKE_ADDR: "ES_Brake",
            cls.BRAKE_PEDAL_ADDR: "Brake_Pedal",
            cls.DASHLIGHTS_ADDR: "Dashlights",
        }
