"""Unit tests for plotting utilities."""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("matplotlib")

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from comma_tools.visualization import SpeedTimelinePlotter


class TestSpeedTimelinePlotter:
    """Test cases for SpeedTimelinePlotter class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.plotter = SpeedTimelinePlotter()
        self.sample_speed_data = [
            {"timestamp": 0.0, "speed_mph": 50.0},
            {"timestamp": 1.0, "speed_mph": 55.5},
            {"timestamp": 2.0, "speed_mph": 56.0},
            {"timestamp": 3.0, "speed_mph": 54.0},
        ]
        self.sample_events = [{"start_time": 1.0, "end_time": 2.5}]

    @patch("matplotlib.pyplot.savefig")
    @patch("matplotlib.pyplot.close")
    @patch("matplotlib.pyplot.figure")
    def test_plot_speed_timeline_basic(self, mock_figure, mock_close, mock_savefig):
        """Test basic speed timeline plotting functionality."""
        filename = self.plotter.plot_speed_timeline(
            self.sample_speed_data, target_speed_events=self.sample_events
        )

        assert filename == "speed_timeline.png"
        mock_figure.assert_called()
        mock_savefig.assert_called_once()
        mock_close.assert_called_once()

    @patch("matplotlib.pyplot.savefig")
    @patch("matplotlib.pyplot.close")
    @patch("matplotlib.pyplot.figure")
    def test_plot_speed_timeline_custom_params(self, mock_figure, mock_close, mock_savefig):
        """Test speed timeline plotting with custom parameters."""
        filename = self.plotter.plot_speed_timeline(
            self.sample_speed_data,
            target_speed_min=50.0,
            target_speed_max=60.0,
            output_filename="custom_plot.png",
            title="Custom Title",
        )

        assert filename == "custom_plot.png"
        mock_figure.assert_called()
        mock_savefig.assert_called_once_with("custom_plot.png", dpi=150, bbox_inches="tight")
        mock_close.assert_called_once()

    def test_plot_speed_timeline_no_data(self):
        """Test that plotting with no data raises ValueError."""
        with pytest.raises(ValueError, match="No speed data provided"):
            self.plotter.plot_speed_timeline([])

    @patch("matplotlib.pyplot.savefig")
    @patch("matplotlib.pyplot.close")
    @patch("matplotlib.pyplot.figure")
    def test_plot_signal_timeline_basic(self, mock_figure, mock_close, mock_savefig):
        """Test basic signal timeline plotting."""
        signal_data = [
            {"timestamp": 0.0, "signal_value": 10.0},
            {"timestamp": 1.0, "signal_value": 15.0},
            {"timestamp": 2.0, "signal_value": 12.0},
        ]

        filename = self.plotter.plot_signal_timeline(signal_data, "signal_value")

        assert filename == "signal_value_timeline.png"
        mock_figure.assert_called()
        mock_savefig.assert_called_once()
        mock_close.assert_called_once()

    def test_plot_signal_timeline_missing_signal(self):
        """Test that plotting with missing signal raises ValueError."""
        signal_data = [{"timestamp": 0.0, "other_value": 10.0}]

        with pytest.raises(ValueError, match="Signal 'missing_signal' not found in data"):
            self.plotter.plot_signal_timeline(signal_data, "missing_signal")

    @patch("matplotlib.pyplot.savefig")
    @patch("matplotlib.pyplot.close")
    @patch("matplotlib.pyplot.subplots")
    def test_plot_multi_signal_timeline(self, mock_subplots, mock_close, mock_savefig):
        """Test multi-signal timeline plotting."""
        mock_fig = MagicMock()
        mock_axes = [MagicMock(), MagicMock()]
        mock_subplots.return_value = (mock_fig, mock_axes)

        signals = {
            "signal1": [{"timestamp": 0.0, "value": 10.0}],
            "signal2": [{"timestamp": 0.0, "value": 20.0}],
        }

        filename = self.plotter.plot_multi_signal_timeline(signals)

        assert filename == "multi_signal_timeline.png"
        mock_subplots.assert_called()
        mock_savefig.assert_called_once()
        mock_close.assert_called_once()

    def test_plot_multi_signal_timeline_no_signals(self):
        """Test that multi-signal plotting with no signals raises ValueError."""
        with pytest.raises(ValueError, match="No signals provided"):
            self.plotter.plot_multi_signal_timeline({})
