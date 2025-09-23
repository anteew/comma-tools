"""Unit tests for CAN bit analysis library."""

import pytest
from collections import Counter
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from comma_tools.can import BitAnalyzer, CanMessage, BitChangeEvent, BitChangeStats


class TestCanMessage:
    """Test CanMessage data class."""

    def test_can_message_creation(self):
        """Test creating a CAN message."""
        msg = CanMessage(123.45, 0x123, b"\x01\x02\x03\x04", 1)
        assert msg.timestamp == 123.45
        assert msg.address == 0x123
        assert msg.data == b"\x01\x02\x03\x04"
        assert msg.bus == 1

    def test_can_message_repr(self):
        """Test string representation of CAN message."""
        msg = CanMessage(123.456, 0x123, b"\x01\x02", 0)
        repr_str = repr(msg)
        assert "123.456" in repr_str
        assert "0x123" in repr_str
        assert "01 02" in repr_str


class TestBitAnalyzer:
    """Test BitAnalyzer functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.analyzer = BitAnalyzer()

    def test_find_changed_bits_simple(self):
        """Test finding changed bits between two payloads."""
        old_data = b"\x00\x00"  # 0000 0000 0000 0000
        new_data = b"\x01\x02"  # 0000 0001 0000 0010

        changed = self.analyzer.find_changed_bits(old_data, new_data)

        # Bit 0 in byte 0 (position 0) and bit 1 in byte 1 (position 9) changed
        assert 0 in changed  # bit 0 of byte 0
        assert 9 in changed  # bit 1 of byte 1
        assert len(changed) == 2

    def test_find_changed_bits_length_difference(self):
        """Test changed bits when payloads have different lengths."""
        old_data = b"\x00"
        new_data = b"\x00\x01"

        changed = self.analyzer.find_changed_bits(old_data, new_data)

        # Bit 0 of the second byte changed (position 8)
        assert 8 in changed
        assert len(changed) == 1

    def test_payload_to_u64_little_endian(self):
        """Test converting payload to 64-bit integer (little endian)."""
        payload = b"\x01\x02\x03\x04"
        result = self.analyzer.payload_to_u64(payload, "little")

        # Little endian: 01 02 03 04 -> 0x04030201
        assert result == 0x04030201

    def test_payload_to_u64_big_endian(self):
        """Test converting payload to 64-bit integer (big endian)."""
        payload = b"\x01\x02\x03\x04"
        result = self.analyzer.payload_to_u64(payload, "big")

        # Big endian: 01 02 03 04 -> 0x01020304 (padded to 8 bytes)
        assert result == 0x01020304

    def test_payload_to_u64_padding(self):
        """Test u64 conversion with padding."""
        payload = b"\xff"
        result = self.analyzer.payload_to_u64(payload, "little")

        # Should be padded with zeros: FF 00 00 00 00 00 00 00
        assert result == 0xFF

    def test_get_bit_value_from_int(self):
        """Test extracting bit value from integer."""
        data = 0b10101010  # 170 decimal

        assert self.analyzer.get_bit_value(data, 0) == 0  # LSB
        assert self.analyzer.get_bit_value(data, 1) == 1
        assert self.analyzer.get_bit_value(data, 2) == 0
        assert self.analyzer.get_bit_value(data, 3) == 1
        assert self.analyzer.get_bit_value(data, 7) == 1  # MSB

    def test_get_bit_value_from_bytes(self):
        """Test extracting bit value from bytes."""
        data = b"\xaa"  # 10101010 binary

        assert self.analyzer.get_bit_value(data, 0) == 0  # LSB
        assert self.analyzer.get_bit_value(data, 1) == 1
        assert self.analyzer.get_bit_value(data, 7) == 1  # MSB

    def test_compute_change_stats_insufficient_data(self):
        """Test change stats with insufficient data."""
        messages = [CanMessage(1.0, 0x123, b"\x01", 0)]
        result = self.analyzer.compute_change_stats(messages)
        assert result is None

    def test_compute_change_stats_no_changes(self):
        """Test change stats when no bits change."""
        messages = [
            CanMessage(1.0, 0x123, b"\x01", 0),
            CanMessage(2.0, 0x123, b"\x01", 0),
            CanMessage(3.0, 0x123, b"\x01", 0),
        ]
        result = self.analyzer.compute_change_stats(messages)
        assert result is None

    def test_compute_change_stats_with_changes(self):
        """Test change stats with actual bit changes."""
        messages = [
            CanMessage(1.0, 0x123, b"\x00", 0),  # 00000000
            CanMessage(2.0, 0x123, b"\x01", 0),  # 00000001 - bit 0 changed
            CanMessage(3.0, 0x123, b"\x03", 0),  # 00000011 - bit 1 changed
            CanMessage(4.0, 0x123, b"\x02", 0),  # 00000010 - bit 0 changed back
        ]

        result = self.analyzer.compute_change_stats(messages)

        assert result is not None
        assert result.total_changes == 3  # 3 changes total
        assert result.message_count == 4
        assert result.bit_frequency[0] == 2  # bit 0 changed twice
        assert result.bit_frequency[1] == 1  # bit 1 changed once
        assert result.change_rate == 3 / 4  # 3 changes in 4 messages

    def test_track_bit_toggles_all_bits(self):
        """Test tracking toggles for all bits."""
        messages = [
            CanMessage(1.0, 0x123, b"\x00", 0),
            CanMessage(2.0, 0x123, b"\x01", 0),  # bit 0 toggles at t=2.0
            CanMessage(3.0, 0x123, b"\x03", 0),  # bit 1 toggles at t=3.0
            CanMessage(4.0, 0x123, b"\x01", 0),  # bit 1 toggles back at t=4.0
        ]

        toggles = self.analyzer.track_bit_toggles(messages)

        assert 0 in toggles
        assert toggles[0] == [2.0]  # bit 0 toggled once
        assert 1 in toggles
        assert toggles[1] == [3.0, 4.0]  # bit 1 toggled twice

    def test_track_bit_toggles_watched_bits(self):
        """Test tracking toggles for specific watched bits."""
        messages = [
            CanMessage(1.0, 0x123, b"\x00", 0),
            CanMessage(2.0, 0x123, b"\x01", 0),  # bit 0 toggles
            CanMessage(3.0, 0x123, b"\x03", 0),  # bit 1 toggles
        ]

        # Only watch bit 0
        toggles = self.analyzer.track_bit_toggles(messages, watched_bits=[0])

        assert 0 in toggles
        assert toggles[0] == [2.0]
        assert 1 not in toggles  # bit 1 not watched

    def test_analyze_multi_address(self):
        """Test analyzing multiple CAN addresses."""
        messages_by_addr = {
            0x123: [
                CanMessage(1.0, 0x123, b"\x00", 0),
                CanMessage(2.0, 0x123, b"\x01", 0),
            ],
            0x456: [
                CanMessage(1.0, 0x456, b"\x00", 0),
                CanMessage(2.0, 0x456, b"\x02", 0),
            ],
        }

        results = self.analyzer.analyze_multi_address(messages_by_addr)

        assert 0x123 in results
        assert 0x456 in results
        assert results[0x123].bit_frequency[0] == 1  # bit 0 changed in addr 0x123
        assert results[0x456].bit_frequency[1] == 1  # bit 1 changed in addr 0x456

    def test_find_bits_active_in_window(self):
        """Test finding bits that toggle only within a time window."""
        messages = [
            CanMessage(1.0, 0x123, b"\x00", 0),  # before window
            CanMessage(2.0, 0x123, b"\x01", 0),  # bit 0 toggles (in window)
            CanMessage(5.0, 0x123, b"\x03", 0),  # bit 1 toggles (in window)
            CanMessage(8.0, 0x123, b"\x07", 0),  # bit 2 toggles (after window)
        ]

        window_bits = self.analyzer.find_bits_active_in_window(messages, 1.5, 6.0)

        # Only bits 0 and 1 toggled within the window [1.5, 6.0]
        assert 0 in window_bits
        assert 1 in window_bits
        assert 2 not in window_bits

    def test_detect_bit_edges(self):
        """Test detecting specific bit edge events."""
        messages = [
            CanMessage(1.0, 0x123, b"\x00", 0),  # 00000000
            CanMessage(2.0, 0x123, b"\x01", 0),  # 00000001 - bit 0: 0->1
            CanMessage(3.0, 0x123, b"\x03", 0),  # 00000011 - bit 1: 0->1
            CanMessage(4.0, 0x123, b"\x01", 0),  # 00000001 - bit 1: 1->0
        ]

        edges = self.analyzer.detect_bit_edges(messages, watched_bits=[0, 1])

        assert len(edges) == 3

        # Check first edge (bit 0: 0->1)
        assert edges[0].bit_position == 0
        assert edges[0].old_value == 0
        assert edges[0].new_value == 1
        assert edges[0].timestamp == 2.0
        assert edges[0].address == 0x123

        # Check second edge (bit 1: 0->1)
        assert edges[1].bit_position == 1
        assert edges[1].old_value == 0
        assert edges[1].new_value == 1
        assert edges[1].timestamp == 3.0

        # Check third edge (bit 1: 1->0)
        assert edges[2].bit_position == 1
        assert edges[2].old_value == 1
        assert edges[2].new_value == 0
        assert edges[2].timestamp == 4.0


class TestBitChangeStats:
    """Test BitChangeStats data class."""

    def test_bit_change_stats_creation(self):
        """Test creating BitChangeStats."""
        bit_freq = Counter({0: 5, 1: 3, 2: 1})
        most_active = [(0, 5), (1, 3), (2, 1)]

        stats = BitChangeStats(
            total_changes=9,
            bit_frequency=bit_freq,
            message_count=20,
            change_rate=0.45,
            most_active_bits=most_active,
        )

        assert stats.total_changes == 9
        assert stats.bit_frequency[0] == 5
        assert stats.message_count == 20
        assert stats.change_rate == 0.45
        assert stats.most_active_bits[0] == (0, 5)


class TestBitChangeEvent:
    """Test BitChangeEvent data class."""

    def test_bit_change_event_creation(self):
        """Test creating a BitChangeEvent."""
        event = BitChangeEvent(
            timestamp=123.45, bit_position=7, old_value=0, new_value=1, address=0x456
        )

        assert event.timestamp == 123.45
        assert event.bit_position == 7
        assert event.old_value == 0
        assert event.new_value == 1
        assert event.address == 0x456
