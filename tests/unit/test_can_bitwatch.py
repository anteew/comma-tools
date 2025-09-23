"""Unit tests for can_bitwatch module."""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from comma_tools.analyzers.can_bitwatch import (
    parse_hex_bytes,
    norm_address,
    msb_label_to_indices,
    global_idx_from_msb,
    WatchBit,
    fmt_time_rel,
    payload_to_u64_le,
    bit_value,
    analyze_counts,
    analyze_per_address,
)


class TestParseHexBytes:
    """Test cases for parse_hex_bytes function."""

    def test_parse_hex_bytes_normal(self):
        """Test parsing normal hex string."""
        result = parse_hex_bytes("DEADBEEF")
        assert result == b"\xde\xad\xbe\xef"

    def test_parse_hex_bytes_with_spaces(self):
        """Test parsing hex string with spaces."""
        result = parse_hex_bytes("DE AD BE EF")
        assert result == b"\xde\xad\xbe\xef"

    def test_parse_hex_bytes_with_0x(self):
        """Test parsing hex string with 0x prefix."""
        result = parse_hex_bytes("0xDEADBEEF")
        assert result == b"\xde\xad\xbe\xef"

    def test_parse_hex_bytes_odd_length(self):
        """Test parsing hex string with odd length."""
        result = parse_hex_bytes("ABC")
        assert result == b"\x0a\xbc"

    def test_parse_hex_bytes_empty(self):
        """Test parsing empty string."""
        result = parse_hex_bytes("")
        assert result == b""


class TestNormAddress:
    """Test cases for norm_address function."""

    def test_norm_address_hex_prefix(self):
        """Test normalizing address with 0x prefix."""
        assert norm_address("0x123") == 0x123
        assert norm_address("0X456") == 0x456

    def test_norm_address_decimal(self):
        """Test normalizing decimal address."""
        assert norm_address("123") == 123
        assert norm_address("456") == 456

    def test_norm_address_bare_hex(self):
        """Test normalizing bare hex address."""
        assert norm_address("ABC") == 0xABC
        assert norm_address("def") == 0xDEF


class TestMSBLabelToIndices:
    """Test cases for msb_label_to_indices function."""

    def test_msb_label_valid(self):
        """Test valid MSB label conversion."""
        byte, msb, lsb = msb_label_to_indices("B4b5")
        assert byte == 4
        assert msb == 5
        assert lsb == 2  # 7 - 5

    def test_msb_label_edge_cases(self):
        """Test MSB label edge cases."""
        byte, msb, lsb = msb_label_to_indices("B0b0")
        assert byte == 0
        assert msb == 0
        assert lsb == 7

        byte, msb, lsb = msb_label_to_indices("B7b7")
        assert byte == 7
        assert msb == 7
        assert lsb == 0

    def test_msb_label_invalid(self):
        """Test invalid MSB label."""
        with pytest.raises(ValueError, match="Bad MSB label"):
            msb_label_to_indices("invalid")

        with pytest.raises(ValueError, match="MSB bit out of range"):
            msb_label_to_indices("B0b8")


class TestGlobalIdxFromMSB:
    """Test cases for global_idx_from_msb function."""

    def test_global_idx_calculation(self):
        """Test global index calculation."""
        assert global_idx_from_msb(0, 7) == 0  # byte 0, bit 7 -> LSB 0
        assert global_idx_from_msb(0, 0) == 7  # byte 0, bit 0 -> LSB 7
        assert global_idx_from_msb(1, 7) == 8  # byte 1, bit 7 -> LSB 8
        assert global_idx_from_msb(4, 5) == 34  # byte 4, bit 5 -> LSB 34


class TestWatchBit:
    """Test cases for WatchBit class."""

    def test_watch_bit_from_spec(self):
        """Test creating WatchBit from spec string."""
        wb = WatchBit.from_spec("0x027:B4b5")
        assert wb.addr == 0x027
        assert wb.byte == 4
        assert wb.msb == 5
        assert wb.lsb == 2
        assert wb.gidx == 34

    def test_watch_bit_invalid_spec(self):
        """Test invalid WatchBit spec."""
        with pytest.raises(ValueError, match="Bad watch spec"):
            WatchBit.from_spec("invalid")


class TestFmtTimeRel:
    """Test cases for fmt_time_rel function."""

    def test_fmt_time_rel_basic(self):
        """Test basic time formatting."""
        assert fmt_time_rel(65.123) == "01:05.123"
        assert fmt_time_rel(0.5) == "00:00.500"
        assert fmt_time_rel(125.999) == "02:05.999"


class TestPayloadToU64Le:
    """Test cases for payload_to_u64_le function."""

    def test_payload_to_u64_le_full(self):
        """Test converting full 8-byte payload."""
        payload = b"\x01\x02\x03\x04\x05\x06\x07\x08"
        result = payload_to_u64_le(payload)
        expected = int.from_bytes(payload, "little")
        assert result == expected

    def test_payload_to_u64_le_short(self):
        """Test converting short payload."""
        payload = b"\x01\x02"
        result = payload_to_u64_le(payload)
        expected = int.from_bytes(b"\x01\x02\x00\x00\x00\x00\x00\x00", "little")
        assert result == expected

    def test_payload_to_u64_le_long(self):
        """Test converting long payload (truncated)."""
        payload = b"\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a"
        result = payload_to_u64_le(payload)
        expected = int.from_bytes(b"\x01\x02\x03\x04\x05\x06\x07\x08", "little")
        assert result == expected


class TestBitValue:
    """Test cases for bit_value function."""

    def test_bit_value_basic(self):
        """Test basic bit value extraction."""
        u64 = 0b1010101010101010
        assert bit_value(u64, 0) == 0
        assert bit_value(u64, 1) == 1
        assert bit_value(u64, 2) == 0
        assert bit_value(u64, 3) == 1


class TestAnalyzeCounts:
    """Test cases for analyze_counts function."""

    def test_analyze_counts_basic(self):
        """Test basic count analysis."""
        rows = [
            {"address": 0x123, "segment": "pre"},
            {"address": 0x123, "segment": "window"},
            {"address": 0x123, "segment": "window"},
            {"address": 0x456, "segment": "post"},
        ]

        result = analyze_counts(rows)

        assert len(result) == 2
        addr_123 = next(r for r in result if r["address"] == "0x123")
        assert addr_123["pre"] == 1
        assert addr_123["window"] == 2
        assert addr_123["post"] == 0
        assert addr_123["delta"] == 1  # window - max(pre, post)


class TestAnalyzePerAddress:
    """Test cases for analyze_per_address function."""

    def test_analyze_per_address_basic(self):
        """Test basic per-address analysis."""
        rows = [
            {"address": 0x123, "segment": "pre", "payload": b"\x01\x02"},
            {"address": 0x123, "segment": "pre", "payload": b"\x01\x02"},
            {"address": 0x123, "segment": "window", "payload": b"\x03\x04"},
        ]

        result = analyze_per_address(rows)

        assert "0x123" in result
        addr_data = result["0x123"]
        assert "pre" in addr_data
        assert "window" in addr_data
        assert addr_data["pre"]["unique_payloads"] == 1
        assert addr_data["window"]["unique_payloads"] == 1
