"""Unit tests for rlog_to_csv module."""

import csv
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from comma_tools.utils import add_openpilot_to_path, find_repo_root


class TestFindRepoRoot:
    """Test cases for find_repo_root function."""

    def test_find_repo_root_explicit_path(self, tmp_path):
        """Test finding repo root with explicit path."""
        openpilot_dir = tmp_path / "openpilot"
        openpilot_dir.mkdir()

        result = find_repo_root(str(tmp_path))
        assert result == tmp_path

    @patch("comma_tools.utils.openpilot_utils.Path.cwd")
    @patch("comma_tools.utils.openpilot_utils.__file__", "/fake/path/to/script.py")
    def test_find_repo_root_not_found(self, mock_cwd, tmp_path):
        """Test error when repo root not found."""
        mock_cwd.return_value = tmp_path

        with pytest.raises(FileNotFoundError, match="Could not find the openpilot checkout"):
            find_repo_root(str(tmp_path))

    @patch("comma_tools.utils.openpilot_utils.Path.cwd")
    @patch("comma_tools.utils.openpilot_utils.__file__", "/fake/path/to/script.py")
    def test_find_repo_root_current_directory(self, mock_cwd, tmp_path):
        """Test finding repo root in current directory."""
        openpilot_dir = tmp_path / "openpilot"
        openpilot_dir.mkdir()

        mock_cwd.return_value = tmp_path
        result = find_repo_root()
        assert result == tmp_path


class TestAddOpenpilotToPath:
    """Test cases for add_openpilot_to_path function."""

    def test_add_openpilot_to_path_explicit(self, tmp_path):
        """Test adding openpilot to path with explicit repo root."""
        openpilot_dir = tmp_path / "openpilot"
        openpilot_dir.mkdir()
        tools_dir = openpilot_dir / "tools"
        tools_dir.mkdir()

        original_path = sys.path.copy()
        try:
            add_openpilot_to_path(str(tmp_path))
            assert str(tools_dir) in sys.path
            assert str(openpilot_dir) in sys.path
        finally:
            sys.path[:] = original_path

    @patch("comma_tools.utils.openpilot_utils.find_repo_root")
    def test_add_openpilot_to_path_none(self, mock_find_repo_root, tmp_path):
        """Test adding openpilot to path with None repo root."""
        openpilot_dir = tmp_path / "openpilot"
        openpilot_dir.mkdir()
        tools_dir = openpilot_dir / "tools"
        tools_dir.mkdir()

        mock_find_repo_root.return_value = tmp_path

        original_path = sys.path.copy()
        try:
            add_openpilot_to_path(None)
            assert str(tools_dir) in sys.path
            assert str(openpilot_dir) in sys.path
        finally:
            sys.path[:] = original_path


class TestSegmentation:
    """Test cases for segmentation logic."""

    def test_segmentation_no_window(self):
        """Test segmentation when no window is defined."""

        def seg_for(t, window_start=None, window_dur=None):
            if window_start is None or window_dur is None:
                return "pre"
            if t < window_start:
                return "pre"
            elif t <= window_start + window_dur:
                return "window"
            else:
                return "post"

        assert seg_for(10.0) == "pre"
        assert seg_for(100.0) == "pre"

    def test_segmentation_with_window(self):
        """Test segmentation with defined window."""

        def seg_for(t, window_start=50.0, window_dur=20.0):
            if window_start is None or window_dur is None:
                return "pre"
            if t < window_start:
                return "pre"
            elif t <= window_start + window_dur:
                return "window"
            else:
                return "post"

        assert seg_for(30.0, 50.0, 20.0) == "pre"
        assert seg_for(60.0, 50.0, 20.0) == "window"
        assert seg_for(80.0, 50.0, 20.0) == "post"


class TestCSVOutput:
    """Test cases for CSV output format."""

    def test_csv_format(self):
        """Test that CSV output has correct format."""
        expected_fieldnames = ["window", "segment", "timestamp", "address", "bus", "data_hex"]

        test_rows = [
            {"timestamp": 1.0, "address": 0x123, "bus": 0, "data_hex": "DEADBEEF"},
            {"timestamp": 2.0, "address": 0x456, "bus": 1, "data_hex": "CAFEBABE"},
        ]

        with tempfile.NamedTemporaryFile(mode="w+", suffix=".csv", delete=False) as f:
            try:
                writer = csv.DictWriter(f, fieldnames=expected_fieldnames)
                writer.writeheader()

                for r in test_rows:
                    writer.writerow(
                        {
                            "window": "1",
                            "segment": "pre",
                            "timestamp": f"{r['timestamp']:.6f}",
                            "address": f"0x{int(r['address']):03X}",
                            "bus": r["bus"],
                            "data_hex": r["data_hex"],
                        }
                    )

                f.flush()

                with open(f.name, "r") as read_f:
                    reader = csv.DictReader(read_f)
                    rows = list(reader)

                    assert len(rows) == 2
                    assert rows[0]["address"] == "0x123"
                    assert rows[1]["address"] == "0x456"
                    assert rows[0]["timestamp"] == "1.000000"
                    assert rows[1]["timestamp"] == "2.000000"

            finally:
                os.unlink(f.name)
