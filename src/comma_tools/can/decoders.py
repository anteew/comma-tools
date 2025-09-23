"""CAN message decoders for automotive analysis."""

from typing import Any, Dict, Optional


class SubaruCANDecoder:
    """Decoder for Subaru CAN messages based on DBC specifications"""

    WHEEL_SPEEDS_ADDR = 0x13A  # 314 decimal
    CRUISE_BUTTONS_ADDR = 0x146  # 326 decimal
    CRUISE_STATUS_ADDR = 0x241  # 577 decimal
    ES_BRAKE_ADDR = 0x220  # 544 decimal
    BRAKE_PEDAL_ADDR = 0x139  # 313 decimal
    DASHLIGHTS_ADDR = 0x390  # 912 decimal

    @staticmethod
    def decode_wheel_speeds(data: bytes) -> Optional[Dict[str, float]]:
        """Decode wheel speeds from address 0x13A (314)"""
        if len(data) < 8:
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

            return speeds

        except Exception as e:
            return None

    @staticmethod
    def decode_cruise_buttons(data: bytes) -> Optional[Dict[str, bool]]:
        """Decode cruise control buttons from address 0x146 (326)"""
        if len(data) < 8:
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
            return None

    @staticmethod
    def decode_cruise_status(data: bytes) -> Optional[Dict[str, Any]]:
        """Decode cruise status from address 0x241 (577)"""
        if len(data) < 8:
            return None

        try:
            raw_data = int.from_bytes(data, byteorder="little")

            status = {
                "cruise_set_speed": (raw_data >> 51) & 0xFFF,  # 12 bits
                "cruise_on": bool((raw_data >> 54) & 0x1),
                "cruise_activated": bool((raw_data >> 55) & 0x1),
            }

            return status

        except Exception as e:
            return None

    @staticmethod
    def decode_es_brake(data: bytes) -> Optional[Dict[str, Any]]:
        """Decode ES_Brake from address 0x220 (544)"""
        if len(data) < 8:
            return None

        try:
            raw_data = int.from_bytes(data, byteorder="little")

            brake_info = {
                "cruise_brake_active": bool((raw_data >> 38) & 0x1),
                "cruise_activated": bool((raw_data >> 39) & 0x1),
            }

            return brake_info

        except Exception as e:
            return None

    @staticmethod
    def decode_blinkers(data: bytes) -> Optional[Dict[str, bool]]:
        """Decode blinker lamp state from Dashlights (0x390)"""
        if len(data) < 8:
            return None

        try:
            raw_data = int.from_bytes(data, byteorder="little")
            return {
                "left": bool((raw_data >> 50) & 0x1),
                "right": bool((raw_data >> 51) & 0x1),
            }
        except Exception:
            return None
