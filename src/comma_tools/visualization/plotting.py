"""Plotting utilities for automotive data visualization."""

import matplotlib.pyplot as plt
from typing import List, Dict, Any, Optional


class SpeedTimelinePlotter:
    """Utility class for creating speed timeline plots with event highlighting."""

    def __init__(self, figsize: tuple = (12, 6)):
        """Initialize the plotter with default figure size."""
        self.figsize = figsize

    def plot_speed_timeline(
        self,
        speed_data: List[Dict[str, Any]],
        target_speed_events: List[Dict[str, Any]] = None,
        target_speed_min: float = 55.0,
        target_speed_max: float = 56.0,
        output_filename: str = "speed_timeline.png",
        title: str = "Vehicle Speed Timeline - Extracted from Wheel Speed CAN Messages",
    ) -> str:
        """
        Create a plot showing speed over time with target events highlighted.

        Args:
            speed_data: List of dicts with 'timestamp' and 'speed_mph' keys
            target_speed_events: List of events with 'start_time' and 'end_time' keys
            target_speed_min: Minimum target speed for highlighting
            target_speed_max: Maximum target speed for highlighting
            output_filename: Name of the output file
            title: Plot title

        Returns:
            Path to the saved plot file
        """
        if not speed_data:
            raise ValueError("No speed data provided")

        timestamps = [d["timestamp"] for d in speed_data]
        speeds = [d["speed_mph"] for d in speed_data]

        plt.figure(figsize=self.figsize)
        plt.plot(timestamps, speeds, "b-", linewidth=1, alpha=0.7, label="Vehicle Speed")

        plt.axhline(
            y=target_speed_min, color="r", linestyle="--", alpha=0.5, label="Target Speed Range"
        )
        plt.axhline(y=target_speed_max, color="r", linestyle="--", alpha=0.5)
        plt.fill_between(timestamps, target_speed_min, target_speed_max, alpha=0.2, color="red")

        if target_speed_events:
            for i, event in enumerate(target_speed_events):
                plt.axvspan(
                    event["start_time"],
                    event["end_time"],
                    alpha=0.3,
                    color="green",
                    label="Target Speed Event" if i == 0 else "",
                )

        plt.xlabel("Time (seconds)")
        plt.ylabel("Speed (MPH)")
        plt.title(title)
        plt.legend()
        plt.grid(True, alpha=0.3)

        plt.savefig(output_filename, dpi=150, bbox_inches="tight")
        plt.close()

        return output_filename

    def plot_signal_timeline(
        self,
        signal_data: List[Dict[str, Any]],
        signal_name: str,
        events: List[Dict[str, Any]] = None,
        output_filename: Optional[str] = None,
        title: Optional[str] = None,
    ) -> str:
        """
        Create a generic signal timeline plot with event highlighting.

        Args:
            signal_data: List of dicts with 'timestamp' and signal value keys
            signal_name: Name of the signal to plot (key in signal_data dicts)
            events: List of events to highlight with 'timestamp' key
            output_filename: Name of the output file (auto-generated if None)
            title: Plot title (auto-generated if None)

        Returns:
            Path to the saved plot file
        """
        if not signal_data:
            raise ValueError("No signal data provided")

        if output_filename is None:
            output_filename = f"{signal_name}_timeline.png"

        if title is None:
            title = f"{signal_name.replace('_', ' ').title()} Timeline"

        timestamps = [d["timestamp"] for d in signal_data]
        values = [d[signal_name] for d in signal_data if signal_name in d]

        if not values:
            raise ValueError(f"Signal '{signal_name}' not found in data")

        plt.figure(figsize=self.figsize)
        plt.plot(timestamps[: len(values)], values, "b-", linewidth=1, alpha=0.7, label=signal_name)

        if events:
            for i, event in enumerate(events):
                plt.axvline(
                    x=event["timestamp"],
                    color="red",
                    linestyle="--",
                    alpha=0.7,
                    label="Event" if i == 0 else "",
                )

        plt.xlabel("Time (seconds)")
        plt.ylabel(signal_name.replace("_", " ").title())
        plt.title(title)
        plt.legend()
        plt.grid(True, alpha=0.3)

        plt.savefig(output_filename, dpi=150, bbox_inches="tight")
        plt.close()

        return output_filename

    def plot_multi_signal_timeline(
        self,
        signals: Dict[str, List[Dict[str, Any]]],
        output_filename: str = "multi_signal_timeline.png",
        title: str = "Multi-Signal Timeline",
        subplot_height: float = 3,
    ) -> str:
        """
        Create a multi-subplot plot for multiple signals.

        Args:
            signals: Dict mapping signal names to their data lists
            output_filename: Name of the output file
            title: Overall plot title
            subplot_height: Height of each subplot

        Returns:
            Path to the saved plot file
        """
        if not signals:
            raise ValueError("No signals provided")

        num_signals = len(signals)
        fig, axes = plt.subplots(
            num_signals, 1, figsize=(self.figsize[0], subplot_height * num_signals), sharex=True
        )

        if num_signals == 1:
            axes = [axes]

        for i, (signal_name, signal_data) in enumerate(signals.items()):
            if not signal_data:
                continue

            timestamps = [d["timestamp"] for d in signal_data]

            value_key = None
            for key in signal_data[0].keys():
                if key != "timestamp":
                    value_key = key
                    break

            if value_key:
                values = [d[value_key] for d in signal_data if value_key in d]
                axes[i].plot(timestamps[: len(values)], values, "b-", linewidth=1, alpha=0.7)
                axes[i].set_ylabel(value_key.replace("_", " ").title())

            axes[i].set_title(f"{signal_name.replace('_', ' ').title()}")
            axes[i].grid(True, alpha=0.3)

        axes[-1].set_xlabel("Time (seconds)")
        plt.suptitle(title)
        plt.tight_layout()

        plt.savefig(output_filename, dpi=150, bbox_inches="tight")
        plt.close()

        return output_filename
