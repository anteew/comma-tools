#!/usr/bin/env python3
"""
CAN Bit Analysis Library

Unified library for analyzing bit-level changes in CAN message data.
Provides both low-level bit manipulation and high-level statistical analysis.
"""

from __future__ import annotations
from typing import Dict, List, Optional, Union, Tuple
from dataclasses import dataclass
from collections import Counter, defaultdict


@dataclass
class BitChangeEvent:
    """Single bit change event with timing information"""

    timestamp: float
    bit_position: int
    old_value: int
    new_value: int
    address: int


@dataclass
class BitChangeStats:
    """Statistics for bit changes across a sequence of messages"""

    total_changes: int
    bit_frequency: Counter[int]  # bit_position -> change_count
    message_count: int
    change_rate: float  # changes per message
    most_active_bits: List[Tuple[int, int]]  # [(bit_pos, count), ...]


class CanMessage:
    """Standardized CAN message representation"""

    def __init__(self, timestamp: float, address: int, data: bytes, bus: int = 0):
        self.timestamp = timestamp
        self.address = address
        self.data = data
        self.bus = bus

    def __repr__(self) -> str:
        data_hex = " ".join(f"{b:02X}" for b in self.data)
        return f"CanMessage(t={self.timestamp:.3f}, addr=0x{self.address:03X}, data=[{data_hex}])"


class BitAnalyzer:
    """Unified CAN bit analysis functionality"""

    def find_changed_bits(self, old_data: bytes, new_data: bytes) -> List[int]:
        """
        Find bit positions that changed between two payloads.

        Args:
            old_data: Previous message payload
            new_data: Current message payload

        Returns:
            List of bit positions (0-based) that changed
        """
        changed_bits = []
        min_len = min(len(old_data), len(new_data))

        for byte_idx in range(min_len):
            if old_data[byte_idx] != new_data[byte_idx]:
                xor_result = old_data[byte_idx] ^ new_data[byte_idx]
                for bit_idx in range(8):
                    if xor_result & (1 << bit_idx):
                        bit_position = byte_idx * 8 + bit_idx
                        changed_bits.append(bit_position)

        # Handle length differences
        max_len = max(len(old_data), len(new_data))
        longer_data = old_data if len(old_data) > len(new_data) else new_data

        for byte_idx in range(min_len, max_len):
            if longer_data[byte_idx] != 0:
                for bit_idx in range(8):
                    if longer_data[byte_idx] & (1 << bit_idx):
                        bit_position = byte_idx * 8 + bit_idx
                        changed_bits.append(bit_position)

        return changed_bits

    def payload_to_u64(self, payload: bytes, endian: str = "little") -> int:
        """
        Convert payload to 64-bit int for bit operations.

        Args:
            payload: CAN message payload (up to 8 bytes)
            endian: Byte order ("little" or "big")

        Returns:
            64-bit integer representation
        """
        if endian == "little":
            padded = payload + b"\x00" * (8 - len(payload)) if len(payload) < 8 else payload[:8]
        else:  # big endian
            padded = b"\x00" * (8 - len(payload)) + payload if len(payload) < 8 else payload[:8]

        return int.from_bytes(padded, byteorder=endian)  # type: ignore

    def get_bit_value(self, data: Union[bytes, int], bit_position: int) -> int:
        """
        Extract single bit value from data.

        Args:
            data: Either bytes payload or integer representation
            bit_position: 0-based bit position (0 = LSB)

        Returns:
            Bit value (0 or 1)
        """
        if isinstance(data, bytes):
            data = self.payload_to_u64(data)

        return (data >> bit_position) & 1

    def compute_change_stats(self, messages: List[CanMessage]) -> Optional[BitChangeStats]:
        """
        Compute bit change statistics across message sequence.

        Args:
            messages: List of CAN messages (should be sorted by timestamp)

        Returns:
            BitChangeStats object or None if insufficient data
        """
        if len(messages) < 2:
            return None

        bit_frequency: Counter[int] = Counter()
        total_changes = 0

        prev_data = messages[0].data
        for msg in messages[1:]:
            changed_bits = self.find_changed_bits(prev_data, msg.data)
            if changed_bits:
                total_changes += 1
                for bit_pos in changed_bits:
                    bit_frequency[bit_pos] += 1
            prev_data = msg.data

        if total_changes == 0:
            return None

        change_rate = total_changes / len(messages)
        most_active_bits = bit_frequency.most_common(10)

        return BitChangeStats(
            total_changes=total_changes,
            bit_frequency=bit_frequency,
            message_count=len(messages),
            change_rate=change_rate,
            most_active_bits=most_active_bits,
        )

    def track_bit_toggles(
        self, messages: List[CanMessage], watched_bits: Optional[List[int]] = None
    ) -> Dict[int, List[float]]:
        """
        Track toggle timestamps for specific bits.

        Args:
            messages: List of CAN messages (should be sorted by timestamp)
            watched_bits: Specific bit positions to track (None = track all)

        Returns:
            Dict mapping bit_position -> list of toggle timestamps
        """
        toggles_by_bit: Dict[int, List[float]] = defaultdict(list)

        if not messages:
            return dict(toggles_by_bit)

        # Track previous state
        last_u64 = self.payload_to_u64(messages[0].data)

        for msg in messages[1:]:
            current_u64 = self.payload_to_u64(msg.data)
            changed = last_u64 ^ current_u64

            if changed:
                # Check all bits or only watched bits
                bits_to_check = watched_bits if watched_bits else range(64)

                for bit_pos in bits_to_check:
                    if (changed >> bit_pos) & 1:
                        toggles_by_bit[bit_pos].append(msg.timestamp)

            last_u64 = current_u64

        return dict(toggles_by_bit)

    def analyze_multi_address(
        self, messages_by_address: Dict[int, List[CanMessage]]
    ) -> Dict[int, BitChangeStats]:
        """
        Analyze bit changes across multiple CAN addresses.

        Args:
            messages_by_address: Dict mapping address -> list of messages

        Returns:
            Dict mapping address -> BitChangeStats
        """
        results = {}

        for address, messages in messages_by_address.items():
            if not messages:
                continue

            stats = self.compute_change_stats(messages)
            if stats:
                results[address] = stats

        return results

    def find_bits_active_in_window(
        self, messages: List[CanMessage], window_start: float, window_end: float
    ) -> List[int]:
        """
        Find bits that toggle only within a specific time window.

        Args:
            messages: List of CAN messages
            window_start: Start timestamp of window
            window_end: End timestamp of window

        Returns:
            List of bit positions that toggle only in the window
        """
        # Get toggles for all bits
        all_toggles = self.track_bit_toggles(messages)

        window_only_bits = []

        for bit_pos, timestamps in all_toggles.items():
            # Check if all toggles are within the window
            in_window = all(window_start <= ts <= window_end for ts in timestamps)
            has_toggles = len(timestamps) > 0

            if has_toggles and in_window:
                window_only_bits.append(bit_pos)

        return window_only_bits

    def detect_bit_edges(
        self, messages: List[CanMessage], watched_bits: List[int]
    ) -> List[BitChangeEvent]:
        """
        Detect specific bit edge events with full context.

        Args:
            messages: List of CAN messages
            watched_bits: Bit positions to monitor for edges

        Returns:
            List of BitChangeEvent objects
        """
        edges: List[BitChangeEvent] = []

        if not messages:
            return edges

        # Track previous values for watched bits
        prev_values = {}
        first_msg = messages[0]
        first_u64 = self.payload_to_u64(first_msg.data)

        for bit_pos in watched_bits:
            prev_values[bit_pos] = self.get_bit_value(first_u64, bit_pos)

        for msg in messages[1:]:
            current_u64 = self.payload_to_u64(msg.data)

            for bit_pos in watched_bits:
                current_value = self.get_bit_value(current_u64, bit_pos)
                prev_value = prev_values[bit_pos]

                if current_value != prev_value:
                    edges.append(
                        BitChangeEvent(
                            timestamp=msg.timestamp,
                            bit_position=bit_pos,
                            old_value=prev_value,
                            new_value=current_value,
                            address=msg.address,
                        )
                    )

                prev_values[bit_pos] = current_value

        return edges
