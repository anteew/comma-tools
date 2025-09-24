#!/usr/bin/env python3
"""
Cruise Control Analyzer for rlog.zst files

This script analyzes rlog.zst files to identify CAN messages related to cruise control
"set" button presses. It parses raw CAN messages and uses Subaru DBC specifications
to decode wheel speeds and cruise control signals.
"""

import argparse
import csv
import json
import os
import struct
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
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
from .event_detection import EventDetector
from .marker_detection import MarkerDetector, MarkerConfig

np = None  # loaded at runtime
plt = None  # loaded at runtime
LogReader = None  # loaded at runtime
messaging = None  # loaded at runtime


class CruiseControlAnalyzer:
    def __init__(self, log_file: str, marker_config: Optional[MarkerConfig] = None):
        self.log_file = log_file
        self.marker_config = marker_config or MarkerConfig()

        self.speed_data: List[Dict[str, Any]] = []
        self.can_data: Dict[int, List[Dict[str, object]]] = defaultdict(list)
        self.all_can_data: Dict[int, List[Dict[str, object]]] = defaultdict(list)
        self.target_speed_events: List[Dict[str, float]] = []
        self.candidate_addresses: Dict[int, Dict[str, object]] = {}
        self.decoder = SubaruCANDecoder()
        self.bit_analyzer = BitAnalyzer()
        self.marker_detector = MarkerDetector(self.decoder, self.marker_config)

        self.target_addresses = {
            self.decoder.WHEEL_SPEEDS_ADDR: "Wheel_Speeds",
            self.decoder.CRUISE_BUTTONS_ADDR: "Cruise_Buttons",
            self.decoder.CRUISE_STATUS_ADDR: "Cruise_Status",
            self.decoder.ES_BRAKE_ADDR: "ES_Brake",
            self.decoder.BRAKE_PEDAL_ADDR: "Brake_Pedal",
        }

        # Marker tracking
        self.marker_window_analysis: List[Dict[str, object]] = []

        # Cached lookups for naming
        self.address_labels: Dict[int, str] = dict(self.target_addresses)

        self.export_csv: bool = False
        self.export_json: bool = False
        self.output_dir: Path = Path(".")
        self.config_snapshot: Dict[str, Any] = {}

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
                            self.marker_detector.record_blinker_event(timestamp, data)

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
        event_detector = EventDetector(self.decoder, self.speed_data, self.can_data)
        self.target_speed_events = event_detector.find_target_speed_events(
            target_speed_min, target_speed_max
        )

    def analyze_cruise_control_signals(self):
        """Analyze specific cruise control CAN signals"""
        event_detector = EventDetector(self.decoder, self.speed_data, self.can_data)
        return event_detector.analyze_cruise_control_signals()

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
        event_detector = EventDetector(self.decoder, self.speed_data, self.can_data)
        return event_detector.correlate_signals_with_speed(signal_analysis)

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
            if np is not None:
                print(f"Average speed: {np.mean(speeds):.1f} MPH")
            else:
                print(f"Average speed: {sum(speeds)/len(speeds):.1f} MPH")

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
            output_filename="speed_timeline.png",
        )
        print(f"Speed timeline plot saved as: {plot_filename}")

    def set_export_config(
        self, export_csv: bool = False, export_json: bool = False, output_dir: str = "."
    ) -> None:
        """Configure export settings for CSV/JSON output and HTML reports.

        Args:
            export_csv: Whether to export CSV files
            export_json: Whether to export JSON files
            output_dir: Directory to save exported files
        """
        self.export_csv = export_csv
        self.export_json = export_json
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def capture_config_snapshot(
        self, cli_args: Dict[str, Any], input_metadata: Dict[str, Any]
    ) -> None:
        """Capture configuration and input metadata for reproducibility.

        Args:
            cli_args: Command line arguments used
            input_metadata: Metadata about input file
        """
        self.config_snapshot = {
            "timestamp": datetime.now().isoformat(),
            "cli_args": cli_args,
            "input_metadata": input_metadata,
            "analyzer_version": "0.1.0",
            "marker_config": {
                "marker_type": self.marker_config.marker_type,
                "pre_time": self.marker_config.pre_time,
                "post_time": self.marker_config.post_time,
                "timeout": self.marker_config.timeout,
                "enabled": self.marker_config.enabled,
            },
        }

    def export_counts_by_segment(self) -> Optional[str]:
        """Export counts by segment (ID×pre/window/post, delta).

        Returns:
            Path to exported file if successful, None otherwise
        """
        if not (self.export_csv or self.export_json):
            return None

        segments_data = []

        for idx, window_analysis in enumerate(self.marker_window_analysis):
            window = window_analysis.get("window", {})
            address_stats = window_analysis.get("address_stats", [])

            for stat in cast(List[Dict[str, Any]], address_stats):
                addr = stat.get("address", 0)
                name = stat.get("name", "Unknown")
                segments_data.append(
                    {
                        "segment_id": f"marker_{idx + 1}",
                        "address": f"0x{addr:03X}",
                        "name": name,
                        "pre_count": 0,  # Would need pre-window analysis
                        "window_count": stat.get("message_count", 0),
                        "post_count": 0,  # Would need post-window analysis
                        "delta": stat.get("total_changes", 0),
                    }
                )

        if self.export_csv:
            csv_path = self.output_dir / "counts_by_segment.csv"
            with open(csv_path, "w", newline="") as f:
                if segments_data:
                    writer = csv.DictWriter(f, fieldnames=segments_data[0].keys())
                    writer.writeheader()
                    writer.writerows(segments_data)
                else:
                    writer = csv.writer(f)
                    writer.writerow(
                        [
                            "segment_id",
                            "address",
                            "name",
                            "pre_count",
                            "window_count",
                            "post_count",
                            "delta",
                        ]
                    )

        if self.export_json:
            json_path = self.output_dir / "counts_by_segment.json"
            with open(json_path, "w") as f:
                json.dump(segments_data, f, indent=2)

        return str(csv_path if self.export_csv else json_path)

    def export_candidates(self) -> Optional[str]:
        """Export candidate bits with scores and labels.

        Returns:
            Path to exported file if successful, None otherwise
        """
        if not (self.export_csv or self.export_json):
            return None

        candidates_data = []

        for address, name in self.target_addresses.items():
            messages = self.can_data.get(address, [])
            if not messages:
                continue

            stats = self.compute_bit_change_stats(messages, address)
            if not stats:
                continue

            for bit_pos, frequency in stats["bit_frequency"].most_common(10):
                candidates_data.append(
                    {
                        "address": f"0x{address:03X}",
                        "name": name,
                        "bit_position": bit_pos,
                        "frequency": frequency,
                        "score": (
                            frequency / stats["message_count"] if stats["message_count"] > 0 else 0
                        ),
                        "label": f"Byte{bit_pos//8} bit{bit_pos%8}",
                        "total_messages": stats["message_count"],
                    }
                )

        if self.export_csv:
            csv_path = self.output_dir / "candidates.csv"
            with open(csv_path, "w", newline="") as f:
                if candidates_data:
                    writer = csv.DictWriter(f, fieldnames=candidates_data[0].keys())
                    writer.writeheader()
                    writer.writerows(candidates_data)
                else:
                    writer = csv.writer(f)
                    writer.writerow(
                        [
                            "address",
                            "name",
                            "bit_position",
                            "frequency",
                            "score",
                            "label",
                            "total_messages",
                        ]
                    )

        if self.export_json:
            json_path = self.output_dir / "candidates.json"
            with open(json_path, "w") as f:
                json.dump(candidates_data, f, indent=2)

        return str(csv_path if self.export_csv else json_path)

    def export_edges(self) -> Optional[str]:
        """Export edge events (per watched bit: ts, rise/fall, mph, main, brake).

        Returns:
            Path to exported file if successful, None otherwise
        """
        if not (self.export_csv or self.export_json):
            return None

        edges_data = []

        signal_analysis = self.analyze_cruise_control_signals()

        if "cruise_buttons" in signal_analysis:
            buttons = signal_analysis["cruise_buttons"]
            for press in buttons.get("set_button_presses", []):
                timestamp = press["timestamp"]
                speed_mph = 0.0
                for speed_entry in self.speed_data:
                    if abs(speed_entry["timestamp"] - timestamp) < 1.0:  # Within 1 second
                        speed_mph = speed_entry["speed_mph"]
                        break

                edges_data.append(
                    {
                        "timestamp": timestamp,
                        "address": f"0x{self.decoder.CRUISE_BUTTONS_ADDR:03X}",
                        "bit_position": 43,  # Set button bit
                        "edge_type": "rise",
                        "speed_mph": speed_mph,
                        "main_status": "unknown",  # Would need main signal analysis
                        "brake_status": "unknown",  # Would need brake signal analysis
                    }
                )

        if self.export_csv:
            csv_path = self.output_dir / "edges.csv"
            with open(csv_path, "w", newline="") as f:
                if edges_data:
                    writer = csv.DictWriter(f, fieldnames=edges_data[0].keys())
                    writer.writeheader()
                    writer.writerows(edges_data)
                else:
                    writer = csv.writer(f)
                    writer.writerow(
                        [
                            "timestamp",
                            "address",
                            "bit_position",
                            "edge_type",
                            "speed_mph",
                            "main_status",
                            "brake_status",
                        ]
                    )

        if self.export_json:
            json_path = self.output_dir / "edges.json"
            with open(json_path, "w") as f:
                json.dump(edges_data, f, indent=2)

        return str(csv_path if self.export_csv else json_path)

    def export_runs(self) -> Optional[str]:
        """Export run intervals (start/end/duration mm:ss.mmm).

        Returns:
            Path to exported file if successful, None otherwise
        """
        if not (self.export_csv or self.export_json):
            return None

        runs_data = []

        for idx, window_analysis in enumerate(self.marker_window_analysis):
            window = window_analysis.get("window", {})
            if not isinstance(window, dict):
                continue

            start_time = float(window.get("start_time", 0))
            stop_time = float(window.get("stop_time", 0))
            window_start = float(window.get("window_start", 0))
            window_end = float(window.get("window_end", 0))
            partial = bool(window.get("partial", False))

            duration = max(0.0, stop_time - start_time) if not partial else 0.0
            window_span = max(0.0, window_end - window_start)

            def format_time(seconds: float) -> str:
                minutes = int(seconds // 60)
                secs = seconds % 60
                return f"{minutes:02d}:{secs:06.3f}"

            runs_data.append(
                {
                    "run_id": f"marker_{idx + 1}",
                    "start_time": format_time(start_time),
                    "end_time": format_time(stop_time) if not partial else "incomplete",
                    "duration": format_time(duration),
                    "window_start": format_time(window_start),
                    "window_end": format_time(window_end),
                    "window_span": format_time(window_span),
                    "partial": partial,
                    "start_timestamp": start_time,
                    "end_timestamp": stop_time if not partial else None,
                }
            )

        if self.export_csv:
            csv_path = self.output_dir / "runs.csv"
            with open(csv_path, "w", newline="") as f:
                if runs_data:
                    writer = csv.DictWriter(f, fieldnames=runs_data[0].keys())
                    writer.writeheader()
                    writer.writerows(runs_data)
                else:
                    writer = csv.writer(f)
                    writer.writerow(
                        [
                            "run_id",
                            "start_time",
                            "end_time",
                            "duration",
                            "window_start",
                            "window_end",
                            "window_span",
                            "partial",
                            "start_timestamp",
                            "end_timestamp",
                        ]
                    )

        if self.export_json:
            json_path = self.output_dir / "runs.json"
            with open(json_path, "w") as f:
                json.dump(runs_data, f, indent=2)

        return str(csv_path if self.export_csv else json_path)

    def export_timeline(self) -> Optional[str]:
        """Export human-readable timeline summary.

        Returns:
            Path to exported file if successful, None otherwise
        """
        if not (self.export_csv or self.export_json):
            return None

        timeline_data = []

        all_events = []

        for event in self.target_speed_events:
            all_events.append(
                {
                    "timestamp": event["timestamp"],
                    "event_type": "target_speed",
                    "description": f"Vehicle at target speed ({event['speed_mph']:.1f} MPH)",
                    "speed_mph": event["speed_mph"],
                }
            )

        for idx, window_analysis in enumerate(self.marker_window_analysis):
            window = window_analysis.get("window", {})
            if not isinstance(window, dict):
                continue

            start_time = float(window.get("start_time", 0))
            stop_time = float(window.get("stop_time", 0))
            partial = bool(window.get("partial", False))

            all_events.append(
                {
                    "timestamp": start_time,
                    "event_type": "marker_start",
                    "description": f"Marker window {idx + 1} started (left blinker)",
                    "speed_mph": 0.0,
                }
            )

            if not partial:
                all_events.append(
                    {
                        "timestamp": stop_time,
                        "event_type": "marker_end",
                        "description": f"Marker window {idx + 1} ended (right blinker)",
                        "speed_mph": 0.0,
                    }
                )

        all_events.sort(key=lambda x: x["timestamp"])

        for event in all_events:
            minutes = int(event["timestamp"] // 60)
            seconds = event["timestamp"] % 60
            timeline_data.append(
                {
                    "timestamp": f"{minutes:02d}:{seconds:06.3f}",
                    "raw_timestamp": event["timestamp"],
                    "event_type": event["event_type"],
                    "description": event["description"],
                    "speed_mph": event["speed_mph"],
                }
            )

        if self.export_csv:
            csv_path = self.output_dir / "timeline.csv"
            with open(csv_path, "w", newline="") as f:
                if timeline_data:
                    writer = csv.DictWriter(f, fieldnames=timeline_data[0].keys())
                    writer.writeheader()
                    writer.writerows(timeline_data)
                else:
                    writer = csv.writer(f)
                    writer.writerow(
                        ["timestamp", "raw_timestamp", "event_type", "description", "speed_mph"]
                    )

        if self.export_json:
            json_path = self.output_dir / "timeline.json"
            with open(json_path, "w") as f:
                json.dump(timeline_data, f, indent=2)

        return str(csv_path if self.export_csv else json_path)

    def generate_html_report(self) -> Optional[str]:
        """Generate comprehensive HTML report with analysis results.

        Returns:
            Path to generated HTML report if successful, None otherwise
        """
        if not (self.export_csv or self.export_json):
            return None

        html_path = self.output_dir / "analysis_report.html"

        signal_analysis = self.analyze_cruise_control_signals()
        bit_analysis = self.analyze_can_bit_changes()

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cruise Control Analysis Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }}
        .header {{ background: #f4f4f4; padding: 20px; border-radius: 5px; margin-bottom: 30px; }}
        .section {{ margin-bottom: 30px; }}
        .section h2 {{ color: #333; border-bottom: 2px solid #ddd; padding-bottom: 10px; }}
        .section h3 {{ color: #555; }}
        .key-findings {{ background: #e8f5e8; padding: 15px; border-radius: 5px; }}
        .recommendations {{ background: #fff3cd; padding: 15px; border-radius: 5px; }}
        .data-table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
        .data-table th, .data-table td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        .data-table th {{ background-color: #f2f2f2; }}
        .file-links {{ background: #f8f9fa; padding: 15px; border-radius: 5px; }}
        .file-links a {{ display: inline-block; margin: 5px 10px 5px 0; padding: 8px 12px; background: #007bff; color: white; text-decoration: none; border-radius: 3px; }}
        .file-links a:hover {{ background: #0056b3; }}
        .config-snapshot {{ background: #f8f9fa; padding: 15px; border-radius: 5px; font-family: monospace; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Subaru Cruise Control Analysis Report</h1>
        <p><strong>Log File:</strong> {self.log_file}</p>
        <p><strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p><strong>Total Speed Data Points:</strong> {len(self.speed_data)}</p>
        <p><strong>Target CAN Addresses Monitored:</strong> {len([addr for addr in self.target_addresses if addr in self.can_data])}</p>
    </div>

    <div class="section">
        <h2>Key Hypotheses</h2>
        <div class="key-findings">
"""

        if "cruise_buttons" in signal_analysis:
            buttons = signal_analysis["cruise_buttons"]
            if buttons.get("set_button_presses"):
                html_content += f"""
            <h3>✓ Cruise Control Set Button Detected</h3>
            <p>Successfully identified {len(buttons['set_button_presses'])} 'Set' button presses in CAN address 0x{self.decoder.CRUISE_BUTTONS_ADDR:03X}.</p>
            <p>Primary signal: Bit 43 (Set button) - This is your cruise control activation signal.</p>
"""
            else:
                html_content += """
            <h3>⚠ No Clear Set Button Presses Detected</h3>
            <p>No clear 'Set' button presses were detected in the expected CAN address.</p>
"""

        html_content += """
        </div>
    </div>

    <div class="section">
        <h2>Timeline Analysis</h2>
"""

        if self.marker_window_analysis:
            html_content += f"""
        <p>Detected {len(self.marker_window_analysis)} marker windows using {self.marker_config.marker_type} pattern.</p>
        <table class="data-table">
            <tr><th>Window</th><th>Start Time</th><th>End Time</th><th>Duration</th><th>Status</th></tr>
"""
            for idx, window_analysis in enumerate(self.marker_window_analysis):
                window = window_analysis.get("window", {})
                if isinstance(window, dict):
                    start_time = float(window.get("start_time", 0))
                    stop_time = float(window.get("stop_time", 0))
                    partial = bool(window.get("partial", False))
                    duration = max(0.0, stop_time - start_time) if not partial else 0.0

                    status = "Partial" if partial else "Complete"
                    html_content += f"""
            <tr>
                <td>Marker {idx + 1}</td>
                <td>{start_time:.2f}s</td>
                <td>{stop_time:.2f}s</td>
                <td>{duration:.2f}s</td>
                <td>{status}</td>
            </tr>
"""
            html_content += """
        </table>
"""
        else:
            html_content += "<p>No marker windows detected.</p>"

        html_content += """
    </div>

    <div class="section">
        <h2>Scorecards & Metrics</h2>
"""

        if bit_analysis:
            html_content += """
        <h3>CAN Address Activity</h3>
        <table class="data-table">
            <tr><th>Address</th><th>Name</th><th>Total Changes</th><th>Messages</th><th>Top Bits</th></tr>
"""
            active_addresses = sorted(
                bit_analysis.items(), key=lambda x: x[1]["total_changes"], reverse=True
            )
            for addr, analysis in active_addresses[:10]:
                top_bits = list(analysis["bit_frequency"].most_common(3))
                html_content += f"""
            <tr>
                <td>0x{addr:03X}</td>
                <td>{analysis['name']}</td>
                <td>{analysis['total_changes']}</td>
                <td>{analysis['message_count']}</td>
                <td>{top_bits}</td>
            </tr>
"""
            html_content += """
        </table>
"""

        html_content += """
    </div>

    <div class="section">
        <h2>Recommendations</h2>
        <div class="recommendations">
"""

        if "cruise_buttons" in signal_analysis and signal_analysis["cruise_buttons"].get(
            "set_button_presses"
        ):
            html_content += f"""
            <h3>Next Steps for Implementation</h3>
            <ol>
                <li>Monitor address 0x{self.decoder.CRUISE_BUTTONS_ADDR:03X} (Cruise_Buttons) in real-time</li>
                <li>Watch for bit 43 transitions when pressing 'Set' button</li>
                <li>Verify address 0x{self.decoder.CRUISE_STATUS_ADDR:03X} (Cruise_Status) for activation confirmation</li>
                <li>Use openpilot's cabana tool for real-time CAN monitoring</li>
            </ol>
"""
        else:
            html_content += """
            <h3>Investigation Required</h3>
            <p>Further analysis needed to identify cruise control activation signals. Consider:</p>
            <ul>
                <li>Examining additional CAN addresses</li>
                <li>Analyzing different bit patterns</li>
                <li>Correlating with vehicle-specific documentation</li>
            </ul>
"""

        html_content += """
        </div>
    </div>

    <div class="section">
        <h2>Data Files</h2>
        <div class="file-links">
            <h3>Generated Data Files:</h3>
"""

        csv_files = [
            "counts_by_segment.csv",
            "candidates.csv",
            "edges.csv",
            "runs.csv",
            "timeline.csv",
        ]
        for csv_file in csv_files:
            if (self.output_dir / csv_file).exists():
                html_content += f'<a href="{csv_file}">{csv_file}</a>'

        if (self.output_dir / "config_snapshot.json").exists():
            html_content += f'<a href="config_snapshot.json">config_snapshot.json</a>'

        html_content += """
        </div>
    </div>

    <div class="section">
        <h2>Configuration Snapshot</h2>
        <div class="config-snapshot">
"""

        if self.config_snapshot:
            html_content += f"<pre>{json.dumps(self.config_snapshot, indent=2)}</pre>"

        html_content += """
        </div>
    </div>

</body>
</html>
"""

        with open(html_path, "w") as f:
            f.write(html_content)

        return str(html_path)

    def export_all_data(self) -> Dict[str, Optional[str]]:
        """Export all data formats (CSV/JSON) and generate HTML report.

        Returns:
            Dictionary mapping export type to file path
        """
        if not (self.export_csv or self.export_json):
            return {}

        results = {}

        print("Exporting analysis data...")

        results["counts_by_segment"] = self.export_counts_by_segment()
        results["candidates"] = self.export_candidates()
        results["edges"] = self.export_edges()
        results["runs"] = self.export_runs()
        results["timeline"] = self.export_timeline()

        if self.config_snapshot:
            config_path = self.output_dir / "config_snapshot.json"
            with open(config_path, "w") as f:
                json.dump(self.config_snapshot, f, indent=2)
            results["config_snapshot"] = str(config_path)

        results["html_report"] = self.generate_html_report()

        print(f"Data exported to: {self.output_dir}")
        for export_type, path in results.items():
            if path:
                print(f"  {export_type}: {path}")

        return results

    def run_analysis(self, target_speed_min: float = 55.0, target_speed_max: float = 56.0):
        """Run the complete analysis"""
        print("Starting Subaru cruise control analysis...")

        if not self.parse_log_file():
            return False

        if self.marker_config.enabled:
            marker_windows = self.marker_detector.detect_marker_windows()
            self.marker_window_analysis = self.marker_detector.analyze_marker_windows(
                self.all_can_data, self.address_labels, self.compute_bit_change_stats
            )
        else:
            marker_windows = []
            self.marker_window_analysis = []

        self.find_target_speed_events(target_speed_min, target_speed_max)
        self.generate_report()

        if self.speed_data:
            self.plot_speed_timeline()

        if self.export_csv or self.export_json:
            self.export_all_data()

        return True


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
    parser.add_argument(
        "--export-csv",
        action="store_true",
        help="Export analysis results to CSV files",
    )
    parser.add_argument(
        "--export-json",
        action="store_true",
        help="Export analysis results to JSON files",
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Directory to save exported files (default: current directory)",
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

    analyzer.set_export_config(
        export_csv=args.export_csv, export_json=args.export_json, output_dir=args.output_dir
    )

    cli_args = {
        "log_file": args.log_file,
        "speed_min": args.speed_min,
        "speed_max": args.speed_max,
        "repo_root": args.repo_root,
        "deps_dir": args.deps_dir,
        "install_missing_deps": args.install_missing_deps,
        "marker_type": args.marker_type,
        "marker_pre": args.marker_pre,
        "marker_post": args.marker_post,
        "marker_timeout": args.marker_timeout,
        "export_csv": args.export_csv,
        "export_json": args.export_json,
        "output_dir": args.output_dir,
    }

    input_metadata = {
        "file_path": args.log_file,
        "file_size": os.path.getsize(args.log_file) if os.path.exists(args.log_file) else 0,
        "file_extension": Path(args.log_file).suffix,
    }

    analyzer.capture_config_snapshot(cli_args, input_metadata)

    if analyzer.run_analysis(target_speed_min=args.speed_min, target_speed_max=args.speed_max):
        print("\nAnalysis completed successfully!")
        return 0
    else:
        print("\nAnalysis failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
