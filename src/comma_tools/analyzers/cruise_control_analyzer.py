#!/usr/bin/env python3
"""
Cruise Control Analyzer for rlog.zst files

This script analyzes rlog.zst files to identify CAN messages related to cruise control
"set" button presses. It parses raw CAN messages and uses Subaru DBC specifications
to decode wheel speeds and cruise control signals.
"""

import argparse
import os
import struct
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, cast

from ..utils import (
    find_repo_root,
    resolve_deps_dir,
    prepare_environment,
    ensure_python_packages,
    load_external_modules,
)
from ..can import SubaruCANDecoder, BitAnalyzer, CanMessage
from ..visualization import SpeedTimelinePlotter

np = None  # loaded at runtime
plt = None  # loaded at runtime
LogReader = None  # loaded at runtime
messaging = None  # loaded at runtime


@dataclass
class MarkerConfig:
    marker_type: str = "blinkers"
    pre_time: float = 1.5
    post_time: float = 1.5
    timeout: float = 15.0

    @property
    def enabled(self) -> bool:
        return self.marker_type != "none"


class CruiseControlAnalyzer:
    def __init__(self, log_file: str, marker_config: Optional[MarkerConfig] = None):
        self.log_file = log_file
        self.marker_config = marker_config or MarkerConfig()

        self.speed_data: List[Dict[str, float]] = []
        self.can_data: Dict[int, List[Dict[str, object]]] = defaultdict(list)
        self.all_can_data: Dict[int, List[Dict[str, object]]] = defaultdict(list)
        self.target_speed_events: List[Dict[str, float]] = []
        self.candidate_addresses: Dict[int, Dict[str, object]] = {}
        self.decoder = SubaruCANDecoder()
        self.bit_analyzer = BitAnalyzer()

        self.target_addresses = {
            self.decoder.WHEEL_SPEEDS_ADDR: "Wheel_Speeds",
            self.decoder.CRUISE_BUTTONS_ADDR: "Cruise_Buttons",
            self.decoder.CRUISE_STATUS_ADDR: "Cruise_Status",
            self.decoder.ES_BRAKE_ADDR: "ES_Brake",
            self.decoder.BRAKE_PEDAL_ADDR: "Brake_Pedal",
        }

        # Marker tracking
        self.marker_events: List[Dict[str, object]] = []
        self.marker_windows: List[Dict[str, float]] = []
        self.marker_window_analysis: List[Dict[str, object]] = []
        self._prev_blinker_state = {"left": False, "right": False}

        # Cached lookups for naming
        self.address_labels: Dict[int, str] = dict(self.target_addresses)

    def parse_log_file(self):
        """Parse the rlog.zst file and extract speed and CAN data"""
        print(f"Parsing log file: {self.log_file}")

        try:
            lr = LogReader(self.log_file)
            message_count = 0
            can_count = 0
            speed_extracted_count = 0

            for msg in lr:
                message_count += 1

                if msg.which() == "can":
                    can_count += 1
                    timestamp = msg.logMonoTime / 1e9

                    for can_msg in msg.can:
                        address = can_msg.address
                        data = bytes(can_msg.dat)
                        entry = {
                            "timestamp": timestamp,
                            "data": data,
                            "bus": can_msg.src,
                        }

                        if address in self.target_addresses:
                            self.can_data[address].append(entry)

                        if self.marker_config.enabled:
                            self.all_can_data[address].append(entry)

                        if (
                            self.marker_config.marker_type == "blinkers"
                            and address == self.decoder.DASHLIGHTS_ADDR
                        ):
                            self._record_blinker_event(timestamp, data)

                        if address == self.decoder.WHEEL_SPEEDS_ADDR:
                            speeds = self.decoder.decode_wheel_speeds(data)
                            if speeds:
                                self.speed_data.append(
                                    {
                                        "timestamp": timestamp,
                                        "speed_mph": speeds["avg_mph"],
                                        "speed_kph": speeds["avg_kph"],
                                        "wheel_speeds": speeds,
                                    }
                                )
                                speed_extracted_count += 1

                if message_count > 100000:
                    break

            print(f"Processed {message_count} messages")
            print(f"Found {can_count} CAN messages")
            print(f"Extracted {speed_extracted_count} speed data points")
            print(
                f"Monitoring {len([addr for addr in self.target_addresses if addr in self.can_data])} target CAN addresses"
            )

            for addr, name in self.target_addresses.items():
                count = len(self.can_data.get(addr, []))
                print(f"  0x{addr:03X} ({name}): {count} messages")

        except Exception as e:
            print(f"Error parsing log file: {e}")
            return False

        return True

    def find_target_speed_events(self, target_speed_min=55.0, target_speed_max=56.0):
        """Find time windows when the vehicle was at target speed (55-56 MPH)"""
        print(f"Looking for events at {target_speed_min}-{target_speed_max} MPH...")

        if not self.speed_data:
            print("No speed data available - could not extract from wheel speed CAN messages")
            print("Will analyze all CAN message patterns during the entire drive")
            return

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

    def analyze_cruise_control_signals(self):
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
                buttons = self.decoder.decode_cruise_buttons(msg["data"])
                if buttons:
                    if prev_buttons and buttons != prev_buttons:
                        button_changes.append(
                            {
                                "timestamp": msg["timestamp"],
                                "old_state": prev_buttons.copy(),
                                "new_state": buttons.copy(),
                                "changes": {
                                    k: v for k, v in buttons.items() if prev_buttons.get(k) != v
                                },
                            }
                        )
                    prev_buttons = buttons

            signal_analysis["cruise_buttons"] = {
                "total_messages": len(button_messages),
                "changes": button_changes,
                "set_button_presses": [
                    c for c in button_changes if c["changes"].get("set") == True
                ],
            }

            print(f"  Button state changes: {len(button_changes)}")
            print(
                f"  'Set' button presses detected: {len(signal_analysis['cruise_buttons']['set_button_presses'])}"
            )

        if self.decoder.CRUISE_STATUS_ADDR in self.can_data:
            status_messages = self.can_data[self.decoder.CRUISE_STATUS_ADDR]
            print(
                f"\nAnalyzing Cruise Status (0x{self.decoder.CRUISE_STATUS_ADDR:03X}): {len(status_messages)} messages"
            )

            status_changes = []
            prev_status = None

            for msg in status_messages:
                status = self.decoder.decode_cruise_status(msg["data"])
                if status:
                    if prev_status and status != prev_status:
                        status_changes.append(
                            {
                                "timestamp": msg["timestamp"],
                                "old_state": prev_status.copy(),
                                "new_state": status.copy(),
                                "changes": {
                                    k: v for k, v in status.items() if prev_status.get(k) != v
                                },
                            }
                        )
                    prev_status = status

            signal_analysis["cruise_status"] = {
                "total_messages": len(status_messages),
                "changes": status_changes,
                "activation_events": [
                    c for c in status_changes if c["changes"].get("cruise_activated") == True
                ],
            }

            print(f"  Status changes: {len(status_changes)}")
            print(
                f"  Cruise activation events: {len(signal_analysis['cruise_status']['activation_events'])}"
            )

        if self.decoder.ES_BRAKE_ADDR in self.can_data:
            brake_messages = self.can_data[self.decoder.ES_BRAKE_ADDR]
            print(
                f"\nAnalyzing ES_Brake (0x{self.decoder.ES_BRAKE_ADDR:03X}): {len(brake_messages)} messages"
            )

            brake_changes = []
            prev_brake = None

            for msg in brake_messages:
                brake_info = self.decoder.decode_es_brake(msg["data"])
                if brake_info:
                    if prev_brake and brake_info != prev_brake:
                        brake_changes.append(
                            {
                                "timestamp": msg["timestamp"],
                                "old_state": prev_brake.copy(),
                                "new_state": brake_info.copy(),
                                "changes": {
                                    k: v for k, v in brake_info.items() if prev_brake.get(k) != v
                                },
                            }
                        )
                    prev_brake = brake_info

            signal_analysis["es_brake"] = {
                "total_messages": len(brake_messages),
                "changes": brake_changes,
                "cruise_activation_events": [
                    c for c in brake_changes if c["changes"].get("cruise_activated") == True
                ],
            }

            print(f"  Brake signal changes: {len(brake_changes)}")
            print(
                f"  Cruise activation via brake signal: {len(signal_analysis['es_brake']['cruise_activation_events'])}"
            )

        return signal_analysis

    def _convert_to_can_messages(
        self, messages: List[Dict[str, object]], address: int
    ) -> List[CanMessage]:
        """Convert internal message format to CanMessage objects"""
        can_messages = []
        for msg in messages:
            timestamp = float(msg["timestamp"])  # type: ignore
            data = msg["data"] if isinstance(msg["data"], bytes) else b""
            bus_val = msg.get("bus", 0) or 0
            bus = int(bus_val)  # type: ignore
            can_messages.append(CanMessage(timestamp, address, data, bus))
        return can_messages

    def compute_bit_change_stats(self, messages: List[Dict[str, object]], address: int = 0):
        """Compute bit change statistics using the new library"""
        can_messages = self._convert_to_can_messages(messages, address)
        stats = self.bit_analyzer.compute_change_stats(can_messages)

        if not stats:
            return None

        # Convert to old format for compatibility
        return {
            "total_changes": stats.total_changes,
            "bit_frequency": stats.bit_frequency,
            "message_count": stats.message_count,
        }

    def analyze_can_bit_changes(self):
        """Analyze bit-level changes in all target CAN addresses"""
        print("Analyzing bit-level changes in target CAN addresses...")

        bit_analysis = {}

        for address, name in self.target_addresses.items():
            messages = self.can_data.get(address)
            if not messages:
                continue

            stats = self.compute_bit_change_stats(messages, address)
            if not stats:
                continue

            bit_analysis[address] = {
                "name": name,
                **stats,
            }

            print(f"\nAnalyzing {name} (0x{address:03X}): {len(messages)} messages")
            print(f"  Total bit changes: {stats['total_changes']}")
            print(f"  Most frequently changing bits: {list(stats['bit_frequency'].most_common(5))}")

        return bit_analysis

    def find_changed_bits(self, old_data: bytes, new_data: bytes) -> List[int]:
        """Find which bits changed between two CAN messages - now uses library"""
        return self.bit_analyzer.find_changed_bits(old_data, new_data)

    def correlate_signals_with_speed(self, signal_analysis):
        """Correlate cruise control signals with speed data"""
        print("\nCorrelating cruise control signals with speed data...")

        if not self.speed_data:
            print("No speed data available for correlation")
            return

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

    def generate_report(self):
        """Generate a detailed analysis report"""
        print("\n" + "=" * 80)
        print("SUBARU CRUISE CONTROL ANALYSIS REPORT")
        print("=" * 80)

        print(f"\nLog file: {self.log_file}")
        print(f"Total speed data points: {len(self.speed_data)}")
        print(
            f"Target CAN addresses monitored: {len([addr for addr in self.target_addresses if addr in self.can_data])}"
        )

        if self.speed_data:
            speeds = [d["speed_mph"] for d in self.speed_data]
            print(f"Speed range: {min(speeds):.1f} - {max(speeds):.1f} MPH")
            print(f"Average speed: {np.mean(speeds):.1f} MPH")

        signal_analysis = self.analyze_cruise_control_signals()

        bit_analysis = self.analyze_can_bit_changes()

        marker_analysis = self.marker_window_analysis if self.marker_config.enabled else []

        correlations = self.correlate_signals_with_speed(signal_analysis)

        if self.marker_config.enabled:
            self.report_marker_windows(marker_analysis)

        print(f"\nKEY FINDINGS:")
        print("-" * 50)

        if "cruise_buttons" in signal_analysis:
            buttons = signal_analysis["cruise_buttons"]
            print(f"1. CRUISE BUTTONS (0x{self.decoder.CRUISE_BUTTONS_ADDR:03X}):")
            print(f"   - Total messages: {buttons['total_messages']}")
            print(f"   - Button state changes: {len(buttons['changes'])}")
            print(f"   - 'Set' button presses: {len(buttons['set_button_presses'])}")

            if buttons["set_button_presses"]:
                print("   - Set button press times:")
                for i, press in enumerate(buttons["set_button_presses"][:10]):
                    print(f"     {i+1}. Time {press['timestamp']:.1f}s")

        if "cruise_status" in signal_analysis:
            status = signal_analysis["cruise_status"]
            print(f"\n2. CRUISE STATUS (0x{self.decoder.CRUISE_STATUS_ADDR:03X}):")
            print(f"   - Total messages: {status['total_messages']}")
            print(f"   - Status changes: {len(status['changes'])}")
            print(f"   - Activation events: {len(status['activation_events'])}")

        if "es_brake" in signal_analysis:
            brake = signal_analysis["es_brake"]
            print(f"\n3. ES_BRAKE (0x{self.decoder.ES_BRAKE_ADDR:03X}):")
            print(f"   - Total messages: {brake['total_messages']}")
            print(f"   - Signal changes: {len(brake['changes'])}")
            print(f"   - Cruise activation events: {len(brake['cruise_activation_events'])}")

        print(f"\n4. BIT-LEVEL ANALYSIS:")
        active_addresses = sorted(
            bit_analysis.items(), key=lambda x: x[1]["total_changes"], reverse=True
        )
        for addr, analysis in active_addresses[:5]:
            print(f"   - {analysis['name']} (0x{addr:03X}): {analysis['total_changes']} changes")
            if analysis["bit_frequency"]:
                top_bits = list(analysis["bit_frequency"].most_common(3))
                print(f"     Most active bits: {top_bits}")

        print(f"\nRECOMMENDATIONS:")
        print("-" * 20)

        if (
            "cruise_buttons" in signal_analysis
            and signal_analysis["cruise_buttons"]["set_button_presses"]
        ):
            print("✓ SUCCESS: Detected 'Set' button presses in cruise control CAN messages!")
            print(f"  - Address: 0x{self.decoder.CRUISE_BUTTONS_ADDR:03X} (Cruise_Buttons)")
            print("  - Signal: Bit 43 (Set button)")
            print("  - This is your primary cruise control activation signal")
        else:
            print("⚠ No clear 'Set' button presses detected in expected address")

        print(f"\nNEXT STEPS:")
        print(
            "1. Monitor address 0x{:03X} (Cruise_Buttons) in real-time".format(
                self.decoder.CRUISE_BUTTONS_ADDR
            )
        )
        print("2. Watch for bit 43 transitions when pressing 'Set' button")
        print(
            "3. Verify address 0x{:03X} (Cruise_Status) for activation confirmation".format(
                self.decoder.CRUISE_STATUS_ADDR
            )
        )
        print("4. Use openpilot's cabana tool for real-time CAN monitoring")

        print(f"\nCABANA COMMANDS:")
        print(f"cd /home/ubuntu/repos/openpilot && tools/cabana")
        print(
            f"# Focus on addresses: 0x{self.decoder.CRUISE_BUTTONS_ADDR:03X}, 0x{self.decoder.CRUISE_STATUS_ADDR:03X}, 0x{self.decoder.ES_BRAKE_ADDR:03X}"
        )

    def report_marker_windows(self, marker_analysis: List[Dict[str, object]]) -> None:
        print("\nMARKER WINDOWS:")

        if not marker_analysis:
            print(f"No marker windows detected using {self.marker_config.marker_type} pattern.")
            return

        for idx, item in enumerate(marker_analysis, start=1):
            window = item["window"]
            if not isinstance(window, dict):
                continue
            start_time = float(window["start_time"])
            stop_time = float(window["stop_time"])
            window_start = float(window["window_start"])
            window_end = float(window["window_end"])
            partial = bool(window.get("partial", False))
            duration = max(0.0, stop_time - start_time)
            window_span = max(0.0, window_end - window_start)

            label = "partial " if partial else ""
            print(
                f"  Marker {idx}: {label}window {window_start:.2f}s → {window_end:.2f}s (span {window_span:.2f}s)"
            )
            print(f"    Left blinker on at {start_time:.2f}s")
            if not partial:
                print(f"    Right blinker on at {stop_time:.2f}s (duration {duration:.2f}s)")
            else:
                print("    Right blinker marker not detected within timeout")

            address_stats = cast(List[Dict[str, Any]], item["address_stats"])
            if not address_stats:
                print("    No notable CAN bit changes captured in this window")
                continue

            print("    Top CAN activity:")
            stats_slice = cast(List[Dict[str, Any]], address_stats[:5])
            for stat in stats_slice:
                addr = int(stat.get("address", 0))
                name = str(stat.get("name", "Unknown"))
                label_name = name if name != "Unknown" else "Unknown address"
                print(
                    f"      - 0x{addr:03X} ({label_name}): {stat['total_changes']} changes over {stat['message_count']} msgs"
                )
                top_bits = stat["bit_frequency"].most_common(3)
                if top_bits:
                    print(f"        Bits: {top_bits}")

    def plot_speed_timeline(self):
        """Create a plot showing speed over time with target events highlighted"""
        if not self.speed_data:
            print("No speed data to plot")
            return

        plotter = SpeedTimelinePlotter()
        plot_filename = plotter.plot_speed_timeline(
            speed_data=self.speed_data,
            target_speed_events=self.target_speed_events,
            target_speed_min=55.0,
            target_speed_max=56.0,
            output_filename="speed_timeline.png"
        )
        print(f"Speed timeline plot saved as: {plot_filename}")

    def run_analysis(self, target_speed_min: float = 55.0, target_speed_max: float = 56.0):
        """Run the complete analysis"""
        print("Starting Subaru cruise control analysis...")

        if not self.parse_log_file():
            return False

        if self.marker_config.enabled:
            self.marker_windows = self.detect_marker_windows()
            self.marker_window_analysis = self.analyze_marker_windows()
        else:
            self.marker_windows = []
            self.marker_window_analysis = []

        self.find_target_speed_events(target_speed_min, target_speed_max)
        self.generate_report()

        if self.speed_data:
            self.plot_speed_timeline()

        return True

    def _record_blinker_event(self, timestamp: float, data: bytes) -> None:
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

        return windows

    def analyze_marker_windows(self) -> List[Dict[str, Any]]:
        if not self.marker_config.enabled or not self.marker_windows:
            return []

        analysis: List[Dict[str, Any]] = []

        source = self.all_can_data if self.marker_config.enabled else self.can_data

        for window in self.marker_windows:
            window_start = window["window_start"]
            window_end = window["window_end"]
            address_stats: List[Dict[str, Any]] = []

            for address, messages in source.items():
                window_messages = []
                for m in messages:
                    if isinstance(m, dict) and "timestamp" in m:
                        timestamp_val = m["timestamp"]
                        if isinstance(timestamp_val, (int, float, str)):
                            ts = float(timestamp_val)
                            if window_start <= ts <= window_end:
                                window_messages.append(m)
                stats = self.compute_bit_change_stats(window_messages)
                if not stats:
                    continue

                address_stats.append(
                    {
                        "address": address,
                        "name": self.address_labels.get(address, "Unknown"),
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


def main():
    parser = argparse.ArgumentParser(
        description="Analyze rlog.zst files for Subaru cruise control signals"
    )
    parser.add_argument("log_file", help="Path to the rlog.zst file")
    parser.add_argument(
        "--speed-min", type=float, default=55.0, help="Minimum target speed in MPH (default: 55.0)"
    )
    parser.add_argument(
        "--speed-max", type=float, default=56.0, help="Maximum target speed in MPH (default: 56.0)"
    )
    parser.add_argument(
        "--repo-root",
        default=None,
        help="Path containing the openpilot checkout (auto-detected by default). "
        "Expected structure: /parent-dir/openpilot/ and /parent-dir/comma-tools/",
    )
    parser.add_argument(
        "--deps-dir",
        default=None,
        help="Directory for local Python dependencies (default: <repo-root>/comma-depends)",
    )
    parser.add_argument(
        "--install-missing-deps",
        action="store_true",
        help="Install missing third-party Python packages into the deps directory",
    )
    parser.add_argument(
        "--marker-type",
        choices=["none", "blinkers"],
        default="blinkers",
        help="Marker detection strategy (default: blinkers)",
    )
    parser.add_argument(
        "--marker-pre",
        type=float,
        default=1.5,
        help="Seconds before marker start to include in window (default: 1.5)",
    )
    parser.add_argument(
        "--marker-post",
        type=float,
        default=1.5,
        help="Seconds after marker stop to include in window (default: 1.5)",
    )
    parser.add_argument(
        "--marker-timeout",
        type=float,
        default=15.0,
        help="Maximum seconds to wait between marker start and stop (default: 15)",
    )

    args = parser.parse_args()
    try:
        repo_root = find_repo_root(args.repo_root)
        deps_dir = resolve_deps_dir(repo_root, args.deps_dir)
        prepare_environment(repo_root, deps_dir)
    except FileNotFoundError as err:
        parser.error(str(err))

    try:
        ensure_python_packages(
            [
                ("matplotlib", "matplotlib"),
                ("numpy", "numpy"),
                ("capnp", "pycapnp"),
                ("tqdm", "tqdm"),
                ("zstandard", "zstandard"),
                ("zmq", "pyzmq"),
                ("smbus2", "smbus2"),
                ("urllib3", "urllib3"),
                ("requests", "requests"),
            ],
            deps_dir,
            args.install_missing_deps,
        )
    except (ImportError, RuntimeError) as err:
        print(f"Dependency error: {err}")
        return 2

    if not os.path.exists(args.log_file):
        print(f"Error: Log file not found: {args.log_file}")
        return 1

    if not args.log_file.endswith(".zst"):
        print(f"Error: Expected .zst log file, got: {args.log_file}")
        print("This tool analyzes compressed openpilot log files (rlog.zst format)")
        print("Typical log files are named like: rlog.zst, segment_name--0--rlog.zst")
        return 1

    try:
        file_size = os.path.getsize(args.log_file)
        if file_size < 1024:  # Less than 1KB is suspicious for a log file
            print(f"Warning: Log file seems very small ({file_size} bytes)")
            print("This might not be a valid rlog.zst file")
    except OSError as e:
        print(f"Error: Cannot read log file: {e}")
        return 1

    print("Dependencies ready; loading openpilot modules...", flush=True)
    modules = load_external_modules()
    global np, plt, LogReader, messaging
    np = modules["np"]
    plt = modules["plt"]
    LogReader = modules["LogReader"]
    messaging = modules["messaging"]
    print("Openpilot modules loaded.", flush=True)

    if args.marker_pre < 0 or args.marker_post < 0:
        parser.error("Marker window durations must be non-negative")

    marker_config = MarkerConfig(
        marker_type=args.marker_type,
        pre_time=args.marker_pre,
        post_time=args.marker_post,
        timeout=args.marker_timeout,
    )

    analyzer = CruiseControlAnalyzer(args.log_file, marker_config=marker_config)

    if analyzer.run_analysis(target_speed_min=args.speed_min, target_speed_max=args.speed_max):
        print("\nAnalysis completed successfully!")
        return 0
    else:
        print("\nAnalysis failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
