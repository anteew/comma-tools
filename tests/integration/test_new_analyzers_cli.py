"""Integration tests for new analyzer CLI tools."""

import csv
import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest


class TestRlogToCsvCLI:
    """Integration tests for rlog-to-csv CLI."""

    def test_rlog_to_csv_help(self):
        """Test that rlog-to-csv --help works."""
        result = subprocess.run(["rlog-to-csv", "--help"], capture_output=True, text=True)
        assert result.returncode == 0
        assert "rlog" in result.stdout
        assert "CSV" in result.stdout

    @pytest.mark.integration
    def test_rlog_to_csv_missing_openpilot(self):
        """Test rlog-to-csv with missing openpilot dependency."""
        with tempfile.NamedTemporaryFile(suffix=".zst") as temp_rlog:
            with tempfile.NamedTemporaryFile(suffix=".csv") as temp_csv:
                result = subprocess.run(
                    [
                        "rlog-to-csv",
                        "--rlog",
                        temp_rlog.name,
                        "--out",
                        temp_csv.name,
                        "--repo-root",
                        "/nonexistent/path",
                    ],
                    capture_output=True,
                    text=True,
                )
                assert result.returncode != 0
                assert "couldn't import LogReader" in result.stderr


class TestCanBitwatchCLI:
    """Integration tests for can-bitwatch CLI."""

    def test_can_bitwatch_help(self):
        """Test that can-bitwatch --help works."""
        result = subprocess.run(["can-bitwatch", "--help"], capture_output=True, text=True)
        assert result.returncode == 0
        assert "CSV" in result.stdout
        assert "bitwatch" in result.stdout.lower()

    def test_can_bitwatch_with_sample_csv(self):
        """Test can-bitwatch with a sample CSV file."""
        sample_data = [
            {
                "window": "1",
                "segment": "pre",
                "timestamp": "1.0",
                "address": "0x123",
                "bus": "0",
                "data_hex": "0102030405060708",
            },
            {
                "window": "1",
                "segment": "window",
                "timestamp": "2.0",
                "address": "0x123",
                "bus": "0",
                "data_hex": "0102030405060709",
            },
            {
                "window": "1",
                "segment": "window",
                "timestamp": "3.0",
                "address": "0x456",
                "bus": "0",
                "data_hex": "DEADBEEFCAFEBABE",
            },
            {
                "window": "1",
                "segment": "post",
                "timestamp": "4.0",
                "address": "0x123",
                "bus": "0",
                "data_hex": "0102030405060708",
            },
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as temp_csv:
            try:
                writer = csv.DictWriter(
                    temp_csv,
                    fieldnames=["window", "segment", "timestamp", "address", "bus", "data_hex"],
                )
                writer.writeheader()
                writer.writerows(sample_data)
                temp_csv.flush()

                with tempfile.TemporaryDirectory() as temp_dir:
                    output_prefix = os.path.join(temp_dir, "test_analysis")

                    result = subprocess.run(
                        [
                            "can-bitwatch",
                            "--csv",
                            temp_csv.name,
                            "--output-prefix",
                            output_prefix,
                            "--watch",
                            "0x123:B0b0",
                        ],
                        capture_output=True,
                        text=True,
                    )

                    assert result.returncode == 0

                    expected_files = [
                        f"{output_prefix}.counts.csv",
                        f"{output_prefix}.per_address.json",
                        f"{output_prefix}.bit_edges.csv",
                        f"{output_prefix}.candidates_window_only.csv",
                        f"{output_prefix}.accel_hunt.csv",
                    ]

                    for expected_file in expected_files:
                        assert os.path.exists(
                            expected_file
                        ), f"Expected file {expected_file} was not created"

                    with open(f"{output_prefix}.counts.csv", "r") as f:
                        reader = csv.DictReader(f)
                        rows = list(reader)
                        assert len(rows) >= 1
                        assert "address" in rows[0]
                        assert "pre" in rows[0]
                        assert "window" in rows[0]
                        assert "post" in rows[0]
                        assert "delta" in rows[0]

                    with open(f"{output_prefix}.per_address.json", "r") as f:
                        data = json.load(f)
                        assert isinstance(data, dict)
                        assert len(data) >= 1

            finally:
                os.unlink(temp_csv.name)

    def test_can_bitwatch_missing_csv(self):
        """Test can-bitwatch with missing CSV file."""
        result = subprocess.run(
            ["can-bitwatch", "--csv", "/nonexistent/file.csv", "--output-prefix", "test"],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0


class TestToolsIntegration:
    """Integration tests for tools working together."""

    def test_tools_import_correctly(self):
        """Test that tools can be imported as modules."""
        try:
            import comma_tools.analyzers.can_bitwatch as can_bitwatch
            import comma_tools.analyzers.rlog_to_csv as rlog_to_csv

            assert hasattr(rlog_to_csv, "main")
            assert hasattr(can_bitwatch, "main")
            assert callable(rlog_to_csv.main)
            assert callable(can_bitwatch.main)
        except ImportError as e:
            pytest.fail(f"Failed to import analyzer modules: {e}")

    def test_cli_entry_points_exist(self):
        """Test that CLI entry points are properly installed."""
        commands = ["rlog-to-csv", "can-bitwatch"]

        for cmd in commands:
            result = subprocess.run([cmd, "--help"], capture_output=True, text=True)
            assert (
                result.returncode == 0
            ), f"Command {cmd} failed with return code {result.returncode}"
            assert len(result.stdout) > 0, f"Command {cmd} produced no help output"
