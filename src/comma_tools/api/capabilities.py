"""Tool discovery endpoint implementation."""

import argparse
import inspect
from typing import Any, Dict, List

from fastapi import APIRouter

from .models import CapabilitiesResponse, ToolCapability, ToolParameter

router = APIRouter()


def _extract_parameters_from_parser(parser: argparse.ArgumentParser) -> Dict[str, ToolParameter]:
    """Extract parameter schema from ArgumentParser."""
    parameters = {}

    for action in parser._actions:
        if action.dest in ("help", "h"):
            continue

        param_name = action.dest
        param_type = "str"  # default
        nargs = None

        if action.type == int:
            param_type = "int"
        elif action.type == float:
            param_type = "float"
        elif isinstance(action, argparse._StoreTrueAction) or isinstance(
            action, argparse._StoreFalseAction
        ):
            param_type = "bool"
        elif hasattr(action, "choices") and action.choices:
            param_type = "str"

        # Handle nargs for list-type parameters
        if hasattr(action, "nargs") and action.nargs is not None:
            if action.nargs in ("*", "+", "?"):
                nargs = str(action.nargs)
                param_type = "list"
            elif isinstance(action.nargs, int):
                nargs = str(action.nargs)
                if action.nargs > 1:
                    param_type = "list"

        required = action.option_strings == [] or getattr(action, "required", False)

        parameters[param_name] = ToolParameter(
            type=param_type,
            default=action.default,
            description=action.help or f"Parameter {param_name}",
            choices=list(action.choices) if hasattr(action, "choices") and action.choices else None,
            required=required,
            nargs=nargs,
        )

    return parameters


def _get_cruise_control_analyzer_capability() -> ToolCapability:
    """Get cruise control analyzer capability."""
    parser = argparse.ArgumentParser()
    parser.add_argument("log_file", help="Path to the rlog.zst file")
    parser.add_argument("--speed-min", type=float, default=55.0, help="Minimum target speed in MPH")
    parser.add_argument("--speed-max", type=float, default=56.0, help="Maximum target speed in MPH")
    parser.add_argument("--repo-root", default=None, help="Path containing the openpilot checkout")
    parser.add_argument("--deps-dir", default=None, help="Directory for local Python dependencies")
    parser.add_argument(
        "--install-missing-deps", action="store_true", help="Install missing dependencies"
    )
    parser.add_argument(
        "--marker-type",
        choices=["none", "blinkers"],
        default="blinkers",
        help="Marker detection strategy",
    )
    parser.add_argument("--marker-pre", type=float, default=1.5, help="Seconds before marker start")
    parser.add_argument("--marker-post", type=float, default=1.5, help="Seconds after marker stop")
    parser.add_argument(
        "--marker-timeout", type=float, default=15.0, help="Maximum seconds between markers"
    )
    parser.add_argument("--export-csv", action="store_true", help="Export analysis results to CSV")
    parser.add_argument(
        "--export-json", action="store_true", help="Export analysis results to JSON"
    )
    parser.add_argument("--output-dir", default=".", help="Directory to save exported files")
    parser.add_argument("--engaged-bit", default=None, help="Bit selector for engaged intervals")
    parser.add_argument(
        "--engaged-bus", type=int, default=None, help="Override bus for engaged bit"
    )
    parser.add_argument(
        "--engaged-mode",
        choices=["annotate", "filter"],
        default="annotate",
        help="Engaged interval handling mode",
    )
    parser.add_argument(
        "--engaged-margin", type=float, default=0.5, help="Seconds to expand engaged intervals"
    )

    return ToolCapability(
        id="cruise-control-analyzer",
        name="Cruise Control Analyzer",
        description="Deep analysis of recorded driving logs with focus on Subaru vehicle cruise control systems",
        category="analyzer",
        version=None,
        parameters=_extract_parameters_from_parser(parser),
    )


def _get_rlog_to_csv_capability() -> ToolCapability:
    """Get rlog to CSV capability."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--rlog", required=True, help="Path to rlog.zst")
    parser.add_argument("--out", required=True, help="Output CSV path")
    parser.add_argument("--window-start", type=float, default=None, help="Window start time")
    parser.add_argument("--window-dur", type=float, default=None, help="Window duration")
    parser.add_argument("--repo-root", type=str, default=None, help="Path to openpilot checkout")

    return ToolCapability(
        id="rlog-to-csv",
        name="RLog to CSV Converter",
        description="Convert openpilot rlog.zst files into CSV format for analysis",
        category="analyzer",
        version=None,
        parameters=_extract_parameters_from_parser(parser),
    )


def _get_can_bitwatch_capability() -> ToolCapability:
    """Get CAN bitwatch capability."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True, help="Input CSV path")
    parser.add_argument("--output-prefix", default="analysis", help="Prefix for output files")
    parser.add_argument(
        "--window-start", type=float, default=None, help="Override window start time"
    )
    parser.add_argument(
        "--watch",
        nargs="*",
        default=["0x027:B4b5", "0x027:B5b1", "0x67A:B3b7", "0x321:B5b1"],
        help="Watch specs",
    )

    return ToolCapability(
        id="can-bitwatch",
        name="CAN Bitwatch Analyzer",
        description="Swiss-army analyzer for CSV dumps of CAN frames with segment labels",
        category="analyzer",
        version=None,
        parameters=_extract_parameters_from_parser(parser),
    )


def _get_monitor_capabilities() -> List[ToolCapability]:
    """Get monitor capabilities."""
    return [
        ToolCapability(
            id="hybrid_rx_trace",
            name="Hybrid RX Trace Monitor",
            description="Trace which CAN signals cause panda safety to flag RX invalid",
            category="monitor",
            version=None,
            parameters={},
        ),
        ToolCapability(
            id="can_bus_check",
            name="CAN Bus Check Monitor",
            description="General CAN message frequency analysis",
            category="monitor",
            version=None,
            parameters={},
        ),
        ToolCapability(
            id="can_hybrid_rx_check",
            name="CAN Hybrid RX Check Monitor",
            description="Subaru hybrid-specific signal monitoring",
            category="monitor",
            version=None,
            parameters={},
        ),
    ]


@router.get("/capabilities", response_model=CapabilitiesResponse)
async def get_capabilities() -> CapabilitiesResponse:
    """
    Get CTS-Lite API capabilities.

    Returns list of available tools and monitors with their parameter schemas.
    Supports tool categories (analyzers, monitors).
    """
    from .. import __version__

    tools = [
        _get_cruise_control_analyzer_capability(),
        _get_rlog_to_csv_capability(),
        _get_can_bitwatch_capability(),
    ]

    monitors = _get_monitor_capabilities()

    return CapabilitiesResponse(
        tools=tools,
        monitors=monitors,
        api_version=__version__,
        features=["health_check", "tool_discovery", "parameter_validation"],
    )
