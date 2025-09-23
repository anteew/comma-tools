import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from comma_tools.can import SubaruCANDecoder  # noqa: E402


def make_payload_from_bits(bits_on):
    b = bytearray(8)
    for bit in bits_on:
        byte = bit // 8
        off = bit % 8
        if 0 <= byte < 8:
            b[byte] |= 1 << off
    return bytes(b)


def int_to_le_bytes64(val: int) -> bytes:
    return int(val).to_bytes(8, "little", signed=False)


class TestDecoderButtons:
    def test_decode_cruise_buttons_all_set(self):
        data = make_payload_from_bits([42, 43, 44])
        out = SubaruCANDecoder.decode_cruise_buttons(data)
        assert out == {"main": True, "set": True, "resume": True}

    def test_decode_cruise_buttons_none(self):
        data = b"\x00" * 8
        out = SubaruCANDecoder.decode_cruise_buttons(data)
        assert out == {"main": False, "set": False, "resume": False}

    def test_decode_cruise_buttons_short(self):
        assert SubaruCANDecoder.decode_cruise_buttons(b"\x00\x01") is None


class TestDecoderBlinkers:
    def test_decode_blinkers_both(self):
        data = make_payload_from_bits([50, 51])
        out = SubaruCANDecoder.decode_blinkers(data)
        assert out == {"left": True, "right": True}

    def test_decode_blinkers_left_only(self):
        data = make_payload_from_bits([50])
        out = SubaruCANDecoder.decode_blinkers(data)
        assert out == {"left": True, "right": False}

    def test_decode_blinkers_short(self):
        assert SubaruCANDecoder.decode_blinkers(b"\x00") is None


class TestDecoderStatus:
    def test_decode_cruise_status_fields(self):
        raw = 0
        raw |= (0x123 & 0xFFF) << 51
        raw |= 1 << 54
        raw |= 1 << 55
        data = int_to_le_bytes64(raw)
        out = SubaruCANDecoder.decode_cruise_status(data)
        assert out is not None
        expected_set_speed = 0x123 | (1 << 3) | (1 << 4)
        assert out["cruise_set_speed"] == expected_set_speed
        assert out["cruise_on"] is True
        assert out["cruise_activated"] is True

    def test_decode_cruise_status_short(self):
        assert SubaruCANDecoder.decode_cruise_status(b"\x00\x00") is None


class TestDecoderEsBrake:
    def test_decode_es_brake_fields(self):
        raw = 0
        raw |= 1 << 38
        raw |= 1 << 39
        data = int_to_le_bytes64(raw)
        out = SubaruCANDecoder.decode_es_brake(data)
        assert out == {"cruise_brake_active": True, "cruise_activated": True}

    def test_decode_es_brake_short(self):
        assert SubaruCANDecoder.decode_es_brake(b"\x00\x00") is None


class TestDecoderWheelSpeeds:
    def test_decode_wheel_speeds_values_and_avg(self):
        fr_raw = 100
        rr_raw = 200
        rl_raw = 300
        fl_raw = 400
        raw = 0
        raw |= (fr_raw & 0x1FFF) << 12
        raw |= (rr_raw & 0x1FFF) << 25
        raw |= (rl_raw & 0x1FFF) << 38
        raw |= (fl_raw & 0x1FFF) << 51
        data = int_to_le_bytes64(raw)
        out = SubaruCANDecoder.decode_wheel_speeds(data)
        assert out is not None
        factor = 0.057
        assert pytest.approx(out["FR"], rel=1e-6) == fr_raw * factor
        assert pytest.approx(out["RR"], rel=1e-6) == rr_raw * factor
        assert pytest.approx(out["RL"], rel=1e-6) == rl_raw * factor
        assert pytest.approx(out["FL"], rel=1e-6) == fl_raw * factor
        avg_kph = (fr_raw + rr_raw + rl_raw + fl_raw) * factor / 4.0
        assert pytest.approx(out["avg_kph"], rel=1e-6) == avg_kph
        assert pytest.approx(out["avg_mph"], rel=1e-6) == avg_kph * 0.621371

    def test_decode_wheel_speeds_short(self):
        assert SubaruCANDecoder.decode_wheel_speeds(b"\x00\x00") is None
