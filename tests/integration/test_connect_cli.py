"""
Integration tests for comma connect CLI.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, Mock

import pytest

from comma_tools.sources.connect.cli import main, create_parser


class TestConnectCLI:
    """Test comma connect CLI functionality."""

    def test_parser_creation(self):
        """Test that argument parser is created correctly."""
        parser = create_parser()

        with pytest.raises(SystemExit):
            parser.parse_args([])  # Should fail without route or url

    def test_parser_route_argument(self):
        """Test parsing with route argument."""
        parser = create_parser()
        args = parser.parse_args(["--route", "dcb4c2e18426be55|2024-04-19--12-33-20", "--logs"])

        assert args.route == "dcb4c2e18426be55|2024-04-19--12-33-20"
        assert args.logs is True
        assert args.url is None

    def test_parser_url_argument(self):
        """Test parsing with URL argument."""
        parser = create_parser()
        args = parser.parse_args(
            [
                "--url",
                "https://connect.comma.ai/dcb4c2e18426be55/00000008--0696c823fa",
                "--logs",
                "--cameras",
            ]
        )

        assert args.url == "https://connect.comma.ai/dcb4c2e18426be55/00000008--0696c823fa"
        assert args.logs is True
        assert args.cameras is True
        assert args.route is None

    def test_parser_file_type_options(self):
        """Test all file type options are parsed correctly."""
        parser = create_parser()
        args = parser.parse_args(
            [
                "--route",
                "test|2024-01-01--00-00-00",
                "--logs",
                "--qlogs",
                "--cameras",
                "--dcameras",
                "--ecameras",
                "--qcameras",
            ]
        )

        assert args.logs is True
        assert args.qlogs is True
        assert args.cameras is True
        assert args.dcameras is True
        assert args.ecameras is True
        assert args.qcameras is True

    def test_parser_defaults(self):
        """Test parser defaults are set correctly."""
        parser = create_parser()
        args = parser.parse_args(["--route", "test|2024-01-01--00-00-00", "--logs"])

        assert args.parallel == 4
        assert args.days == 7
        assert args.no_resume is False
        assert args.dry_run is False
        assert args.verbose is False
        assert args.json is False
        assert args.print_files is False

        expected_dest = Path.home() / ".cache" / "comma-tools" / "downloads"
        assert args.dest == expected_dest

    @patch("comma_tools.sources.connect.cli.load_auth")
    def test_main_missing_file_types(self, mock_load_auth):
        """Test main function with missing file types."""
        mock_load_auth.return_value = "test-token"

        with patch("sys.argv", ["comma-connect-dl", "--route", "test|2024-01-01--00-00-00"]):
            with pytest.raises(SystemExit) as exc_info:
                main()

            assert exc_info.value.code == 1

    @patch("comma_tools.sources.connect.cli.load_auth")
    def test_main_missing_auth(self, mock_load_auth):
        """Test main function with missing authentication."""
        mock_load_auth.side_effect = FileNotFoundError("No comma JWT found")

        with patch(
            "sys.argv", ["comma-connect-dl", "--route", "test|2024-01-01--00-00-00", "--logs"]
        ):
            with pytest.raises(SystemExit) as exc_info:
                main()

            assert exc_info.value.code == 1

    @patch("comma_tools.sources.connect.cli.load_auth")
    @patch("comma_tools.sources.connect.cli.LogDownloader")
    @patch("comma_tools.sources.connect.cli.RouteResolver")
    @patch("comma_tools.sources.connect.cli.ConnectClient")
    def test_main_dry_run(self, mock_client, mock_resolver, mock_downloader, mock_load_auth):
        """Test main function with dry run option."""
        mock_load_auth.return_value = "test-token"

        with patch(
            "sys.argv",
            [
                "comma-connect-dl",
                "--route",
                "dcb4c2e18426be55|2024-04-19--12-33-20",
                "--logs",
                "--dry-run",
            ],
        ):
            result = main()

            assert result == 0
            mock_downloader.assert_not_called()
