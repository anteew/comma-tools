"""Regression tests to ensure API capabilities match real CLI tools."""

import argparse
from typing import Dict

import pytest

from comma_tools.api.capabilities import (
    _extract_parameters_from_parser,
    _get_can_bitwatch_capability,
    _get_rlog_to_csv_capability,
)


def test_can_bitwatch_defaults_match_cli():
    """Test that CAN bitwatch API defaults match the real CLI defaults."""
    real_parser = argparse.ArgumentParser()
    real_parser.add_argument("--csv", required=True, help="Input CSV path")
    real_parser.add_argument("--output-prefix", default="analysis", help="Prefix for output files")
    real_parser.add_argument(
        "--window-start",
        type=float,
        default=None,
        help="Override window start time (s) for mm:ss.mmm",
    )
    real_parser.add_argument(
        "--watch",
        nargs="*",
        default=["0x027:B4b5", "0x027:B5b1", "0x67A:B3b7", "0x321:B5b1"],
        help="Watch specs like '0x027:B4b5'",
    )

    real_params = _extract_parameters_from_parser(real_parser)
    real_watch_default = real_params["watch"].default

    api_capability = _get_can_bitwatch_capability()
    api_watch_default = api_capability.parameters["watch"].default

    assert (
        api_watch_default == real_watch_default
    ), f"API watch defaults {api_watch_default} don't match CLI defaults {real_watch_default}"
    assert len(api_watch_default) == 4, f"Expected 4 watch specs, got {len(api_watch_default)}"


def test_rlog_to_csv_required_args_match_cli():
    """Test that rlog-to-csv required arguments match between API and CLI."""
    real_parser = argparse.ArgumentParser()
    real_parser.add_argument("--rlog", required=True, help="Path to rlog.zst")
    real_parser.add_argument("--out", required=True, help="Output CSV path")
    real_parser.add_argument("--window-start", type=float, default=None, help="Window start time")
    real_parser.add_argument("--window-dur", type=float, default=None, help="Window duration")
    real_parser.add_argument(
        "--repo-root", type=str, default=None, help="Path to openpilot checkout"
    )

    real_params = _extract_parameters_from_parser(real_parser)

    api_capability = _get_rlog_to_csv_capability()

    for param_name, real_param in real_params.items():
        api_param = api_capability.parameters[param_name]
        assert (
            api_param.required == real_param.required
        ), f"Parameter '{param_name}' required mismatch: API={api_param.required}, CLI={real_param.required}"


def test_parameter_extraction_handles_required_correctly():
    """Test that parameter extraction correctly identifies required arguments."""
    parser = argparse.ArgumentParser()

    parser.add_argument("positional", help="Positional argument")
    parser.add_argument("--required-opt", required=True, help="Required option")
    parser.add_argument("--optional-opt", help="Optional option")
    parser.add_argument("--flag", action="store_true", help="Boolean flag")
    parser.add_argument("--list-arg", nargs="*", default=["a", "b"], help="List argument")

    params = _extract_parameters_from_parser(parser)

    assert params["positional"].required is True, "Positional args should be required"
    assert params["required_opt"].required is True, "Args with required=True should be required"
    assert params["optional_opt"].required is False, "Optional args should not be required"
    assert params["flag"].required is False, "Flags should not be required"
    assert params["list_arg"].required is False, "List args with defaults should not be required"

    assert params["list_arg"].nargs == "*", "List args should preserve nargs"
    assert params["list_arg"].type == "list", "List args should have list type"
    assert params["positional"].nargs is None, "Single args should have no nargs"
