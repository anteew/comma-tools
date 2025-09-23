"""Marker Detection System for CAN bus analysis.

This module provides reusable marker detection functionality for identifying
time windows of interest in automotive log data using various detection strategies.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, cast
from ..can import SubaruCANDecoder


@dataclass
class MarkerConfig:
    """Configuration for marker-based time window detection."""
    
    marker_type: str = "blinkers"
    pre_time: float = 1.5
    post_time: float = 1.5
    timeout: float = 15.0

    @property
    def enabled(self) -> bool:
        """Check if marker detection is enabled."""
        return self.marker_type != "none"


class MarkerDetector:
    """Detects time windows of interest using configurable marker strategies."""
    
    def __init__(self, decoder: SubaruCANDecoder, marker_config: Optional[MarkerConfig] = None):
        """Initialize the MarkerDetector.
        
        Args:
            decoder: SubaruCANDecoder instance for decoding CAN messages
            marker_config: Configuration for marker detection behavior
        """
        self.decoder = decoder
        self.marker_config = marker_config or MarkerConfig()
        self.marker_events: List[Dict[str, object]] = []
        self.marker_windows: List[Dict[str, float]] = []
        self._prev_blinker_state = {"left": False, "right": False}
    
    def record_blinker_event(self, timestamp: float, data: bytes) -> None:
        """Record a blinker state change event.
        
        Args:
            timestamp: Timestamp of the CAN message
            data: Raw CAN message data
        """
        decoded = self.decoder.decode_blinkers(data)
        if not decoded:
            return

        left = bool(decoded.get("left"))
        right = bool(decoded.get("right"))
        prev_left = self._prev_blinker_state["left"]
        prev_right = self._prev_blinker_state["right"]

        if left == prev_left and right == prev_right:
            return

        event = {
            "timestamp": timestamp,
            "left": left,
            "right": right,
            "left_prev": prev_left,
            "right_prev": prev_right,
            "left_changed": left != prev_left,
            "right_changed": right != prev_right,
        }
        self.marker_events.append(event)  # type: ignore[arg-type]
        self._prev_blinker_state["left"] = left
        self._prev_blinker_state["right"] = right

    def detect_marker_windows(self) -> List[Dict[str, float]]:
        """Detect time windows based on marker events.
        
        Returns:
            List of time windows with start/stop times and window boundaries
        """
        if not self.marker_config.enabled or self.marker_config.marker_type != "blinkers":
            return []

        windows: List[Dict[str, float]] = []
        start_event: Optional[Dict[str, Any]] = None

        for event in self.marker_events:
            timestamp_val = event.get("timestamp")
            if isinstance(timestamp_val, (int, float, str)):
                ts = float(timestamp_val)
            else:
                ts = 0.0

            if event.get("left_changed") and event.get("left"):
                start_event = event
                continue

            if not start_event:
                continue

            if ts - float(start_event["timestamp"]) > self.marker_config.timeout:
                start_event = None
                continue

            if event.get("right_changed") and event.get("right"):
                start_time = float(start_event["timestamp"])
                stop_time = ts
                window_start = max(0.0, start_time - self.marker_config.pre_time)
                window_end = stop_time + self.marker_config.post_time
                windows.append(
                    {
                        "start_time": start_time,
                        "stop_time": stop_time,
                        "window_start": window_start,
                        "window_end": window_end,
                        "partial": False,
                    }
                )
                start_event = None

        if start_event:
            start_time = float(start_event["timestamp"])
            window_start = max(0.0, start_time - self.marker_config.pre_time)
            window_end = start_time + self.marker_config.post_time
            windows.append(
                {
                    "start_time": start_time,
                    "stop_time": start_time,
                    "window_start": window_start,
                    "window_end": window_end,
                    "partial": True,
                }
            )

        self.marker_windows = windows
        return windows

    def analyze_marker_windows(
        self, 
        all_can_data: Dict[int, List[Dict[str, object]]],
        address_labels: Dict[int, str],
        bit_analyzer_func
    ) -> List[Dict[str, Any]]:
        """Analyze CAN activity within detected marker windows.
        
        Args:
            all_can_data: Dictionary mapping CAN addresses to message lists
            address_labels: Mapping of CAN addresses to human-readable names
            bit_analyzer_func: Function to compute bit change statistics
            
        Returns:
            List of analysis results for each marker window
        """
        if not self.marker_config.enabled or not self.marker_windows:
            return []

        analysis: List[Dict[str, Any]] = []

        for window in self.marker_windows:
            window_start = window["window_start"]
            window_end = window["window_end"]
            address_stats: List[Dict[str, Any]] = []

            for address, messages in all_can_data.items():
                window_messages = []
                for m in messages:
                    if isinstance(m, dict) and "timestamp" in m:
                        timestamp_val = m["timestamp"]
                        if isinstance(timestamp_val, (int, float, str)):
                            ts = float(timestamp_val)
                            if window_start <= ts <= window_end:
                                window_messages.append(m)
                
                stats = bit_analyzer_func(window_messages)
                if not stats:
                    continue

                address_stats.append(
                    {
                        "address": address,
                        "name": address_labels.get(address, "Unknown"),
                        **stats,
                    }
                )

            address_stats.sort(key=lambda x: x["total_changes"], reverse=True)
            analysis.append(
                {
                    "window": window,
                    "address_stats": address_stats,
                }
            )

        return analysis

    def get_marker_events(self) -> List[Dict[str, object]]:
        """Get all recorded marker events."""
        return self.marker_events.copy()

    def get_marker_windows(self) -> List[Dict[str, float]]:
        """Get all detected marker windows."""
        return self.marker_windows.copy()

    def reset(self) -> None:
        """Reset the detector state for processing a new log file."""
        self.marker_events.clear()
        self.marker_windows.clear()
        self._prev_blinker_state = {"left": False, "right": False}
