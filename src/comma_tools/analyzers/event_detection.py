"""Event Detection & Analysis Engine for CAN bus analysis.

This module provides reusable event detection functionality extracted from the
CruiseControlAnalyzer for use across different CAN analysis tools.
"""

from typing import Dict, List, Optional, Any, cast
from ..can import SubaruCANDecoder


class EventDetector:
    """Reusable event detection and analysis engine for CAN bus data."""

    def __init__(
        self,
        decoder: SubaruCANDecoder,
        speed_data: List[Dict[str, float]],
        can_data: Dict[int, List[Dict[str, object]]],
    ):
        """Initialize the EventDetector with required data.

        Args:
            decoder: SubaruCANDecoder instance for decoding CAN messages
            speed_data: List of speed data points with timestamps
            can_data: Dictionary mapping CAN addresses to message lists
        """
        self.decoder = decoder
        self.speed_data = speed_data
        self.can_data = can_data
        self.target_speed_events: List[Dict[str, float]] = []

    def find_target_speed_events(
        self, target_speed_min=55.0, target_speed_max=56.0
    ) -> List[Dict[str, float]]:
        """Find time windows when the vehicle was at target speed (55-56 MPH)"""
        print(f"Looking for events at {target_speed_min}-{target_speed_max} MPH...")

        if not self.speed_data:
            print("No speed data available - could not extract from wheel speed CAN messages")
            print("Will analyze all CAN message patterns during the entire drive")
            return []

        target_events = []
        in_target_range = False
        event_start = None

        for data_point in self.speed_data:
            speed = data_point["speed_mph"]
            timestamp = data_point["timestamp"]

            if target_speed_min <= speed <= target_speed_max:
                if not in_target_range:
                    in_target_range = True
                    event_start = timestamp
            else:
                if in_target_range:
                    in_target_range = False
                    if event_start is not None:
                        target_events.append(
                            {
                                "start_time": event_start,
                                "end_time": timestamp,
                                "duration": timestamp - event_start,
                            }
                        )

        if in_target_range and event_start is not None:
            target_events.append(
                {
                    "start_time": event_start,
                    "end_time": self.speed_data[-1]["timestamp"],
                    "duration": self.speed_data[-1]["timestamp"] - event_start,
                }
            )

        self.target_speed_events = target_events
        print(f"Found {len(target_events)} events at target speed")

        for i, event in enumerate(target_events):
            print(
                f"Event {i+1}: {event['start_time']:.1f}s - {event['end_time']:.1f}s (duration: {event['duration']:.1f}s)"
            )

        return target_events

    def analyze_cruise_control_signals(self) -> Dict[str, Dict]:
        """Analyze specific cruise control CAN signals"""
        print("Analyzing Subaru cruise control signals...")

        signal_analysis = {}

        if self.decoder.CRUISE_BUTTONS_ADDR in self.can_data:
            button_messages = self.can_data[self.decoder.CRUISE_BUTTONS_ADDR]
            print(
                f"\nAnalyzing Cruise Buttons (0x{self.decoder.CRUISE_BUTTONS_ADDR:03X}): {len(button_messages)} messages"
            )

            button_changes = []
            prev_buttons = None

            for msg in button_messages:
                data = msg["data"] if isinstance(msg["data"], bytes) else b""
                buttons = self.decoder.decode_cruise_buttons(data)
                if buttons:
                    buttons_dict = cast(Dict[str, Any], buttons)
                    if prev_buttons and buttons_dict != prev_buttons:
                        button_changes.append(
                            {
                                "timestamp": msg["timestamp"],
                                "old_state": prev_buttons.copy(),
                                "new_state": buttons_dict.copy(),
                                "changes": {
                                    k: v
                                    for k, v in buttons_dict.items()
                                    if prev_buttons.get(k) != v
                                },
                            }
                        )
                    prev_buttons = buttons_dict

            signal_analysis["cruise_buttons"] = {
                "total_messages": len(button_messages),
                "changes": button_changes,
                "set_button_presses": [
                    c
                    for c in button_changes
                    if cast(Dict[str, Any], c["changes"]).get("set") == True
                ],
            }

            print(f"  Button state changes: {len(button_changes)}")
            set_button_presses = cast(
                List[Any], signal_analysis["cruise_buttons"]["set_button_presses"]
            )
            print(f"  'Set' button presses detected: {len(set_button_presses)}")

        if self.decoder.CRUISE_STATUS_ADDR in self.can_data:
            status_messages = self.can_data[self.decoder.CRUISE_STATUS_ADDR]
            print(
                f"\nAnalyzing Cruise Status (0x{self.decoder.CRUISE_STATUS_ADDR:03X}): {len(status_messages)} messages"
            )

            status_changes = []
            prev_status = None

            for msg in status_messages:
                data = msg["data"] if isinstance(msg["data"], bytes) else b""
                status = self.decoder.decode_cruise_status(data)
                if status:
                    status_dict = cast(Dict[str, Any], status)
                    if prev_status and status_dict != prev_status:
                        status_changes.append(
                            {
                                "timestamp": msg["timestamp"],
                                "old_state": prev_status.copy(),
                                "new_state": status_dict.copy(),
                                "changes": {
                                    k: v for k, v in status_dict.items() if prev_status.get(k) != v
                                },
                            }
                        )
                    prev_status = status_dict

            signal_analysis["cruise_status"] = {
                "total_messages": len(status_messages),
                "changes": status_changes,
                "activation_events": [
                    c
                    for c in status_changes
                    if cast(Dict[str, Any], c["changes"]).get("cruise_activated") == True
                ],
            }

            print(f"  Status changes: {len(status_changes)}")
            activation_events = cast(
                List[Any], signal_analysis["cruise_status"]["activation_events"]
            )
            print(f"  Cruise activation events: {len(activation_events)}")

        if self.decoder.ES_BRAKE_ADDR in self.can_data:
            brake_messages = self.can_data[self.decoder.ES_BRAKE_ADDR]
            print(
                f"\nAnalyzing ES_Brake (0x{self.decoder.ES_BRAKE_ADDR:03X}): {len(brake_messages)} messages"
            )

            brake_changes = []
            prev_brake = None

            for msg in brake_messages:
                data = msg["data"] if isinstance(msg["data"], bytes) else b""
                brake_info = self.decoder.decode_es_brake(data)
                if brake_info:
                    brake_dict = cast(Dict[str, Any], brake_info)
                    if prev_brake and brake_dict != prev_brake:
                        brake_changes.append(
                            {
                                "timestamp": msg["timestamp"],
                                "old_state": prev_brake.copy(),
                                "new_state": brake_dict.copy(),
                                "changes": {
                                    k: v for k, v in brake_dict.items() if prev_brake.get(k) != v
                                },
                            }
                        )
                    prev_brake = brake_dict

            signal_analysis["es_brake"] = {
                "total_messages": len(brake_messages),
                "changes": brake_changes,
                "cruise_activation_events": [
                    c
                    for c in brake_changes
                    if cast(Dict[str, Any], c["changes"]).get("cruise_activated") == True
                ],
            }

            print(f"  Brake signal changes: {len(brake_changes)}")
            cruise_activation_events = cast(
                List[Any], signal_analysis["es_brake"]["cruise_activation_events"]
            )
            print(f"  Cruise activation via brake signal: {len(cruise_activation_events)}")

        return signal_analysis

    def correlate_signals_with_speed(self, signal_analysis: Dict[str, Dict]) -> Dict[str, List]:
        """Correlate cruise control signals with speed data"""
        print("\nCorrelating cruise control signals with speed data...")

        if not self.speed_data:
            print("No speed data available for correlation")
            return {}

        correlations = {}

        if "cruise_buttons" in signal_analysis:
            set_presses = signal_analysis["cruise_buttons"]["set_button_presses"]
            speed_correlations = []

            for press in set_presses:
                press_time = press["timestamp"]
                closest_speed = None
                min_time_diff = float("inf")

                for speed_data in self.speed_data:
                    time_diff = abs(speed_data["timestamp"] - press_time)
                    if time_diff < min_time_diff:
                        min_time_diff = time_diff
                        closest_speed = speed_data

                if closest_speed and min_time_diff < 2.0:
                    speed_correlations.append(
                        {
                            "press_time": press_time,
                            "speed_mph": closest_speed["speed_mph"],
                            "time_diff": min_time_diff,
                        }
                    )

            correlations["set_button_speeds"] = speed_correlations

            target_range_presses = [c for c in speed_correlations if 55.0 <= c["speed_mph"] <= 56.0]

            print(f"Set button presses: {len(set_presses)}")
            print(f"Set presses with speed data: {len(speed_correlations)}")
            print(f"Set presses in target range (55-56 MPH): {len(target_range_presses)}")

            if target_range_presses:
                print("Set button presses in target speed range:")
                for i, press in enumerate(target_range_presses):
                    print(
                        f"  {i+1}. Time {press['press_time']:.1f}s, Speed {press['speed_mph']:.1f} MPH"
                    )

        return correlations
