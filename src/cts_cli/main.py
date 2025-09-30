"""
Main CLI application for CTS client.

Provides the main Typer application with global flags and
command routing for all CTS CLI functionality.
"""

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import typer
from packaging import version
from typing_extensions import Annotated

from . import __version__ as CLIENT_VERSION

from .commands.artifacts import get_artifact_command, list_artifacts_command
from .commands.cap import capabilities_command, ping_command
from .commands.logs import logs_command
from .commands.monitors import (
    list_monitors_command,
    start_monitor_command,
    stop_monitor_command,
    stream_monitor_command,
)
from .commands.run import run_command
from .commands.uploads import upload_command
from .config import Config
from .http import HTTPClient
from .render import Renderer

app = typer.Typer(
    name="cts",
    help="CTS CLI - Command-line interface for CTS-Lite HTTP API",
    no_args_is_help=True,
    add_completion=False,
)

_config: Optional[Config] = None
_http_client: Optional[HTTPClient] = None
_renderer: Optional[Renderer] = None


def get_config() -> Config:
    """Get global config instance."""
    if _config is None:
        raise RuntimeError("Config not initialized")
    return _config


def get_http_client() -> HTTPClient:
    """Get global HTTP client instance."""
    if _http_client is None:
        raise RuntimeError("HTTP client not initialized")
    return _http_client


def get_renderer() -> Renderer:
    """Get global renderer instance."""
    if _renderer is None:
        raise RuntimeError("Renderer not initialized")
    return _renderer


def check_version_compatibility(http_client: HTTPClient, renderer: Renderer) -> None:
    """
    Check if client version is compatible with server API version.

    Exits with error if client is too old.
    """
    try:
        # Try to get version info from server
        response = http_client.get_json("/v1/version")

        # Ensure response is a dict before using .get()
        if not isinstance(response, dict):
            return  # Unexpected response format, skip check

        min_client_version = response.get("min_client_version")
        api_version = response.get("api_version")

        if not min_client_version:
            return  # Server doesn't specify minimum version

        # Parse versions for comparison
        client_ver = version.parse(CLIENT_VERSION)
        min_ver = version.parse(min_client_version)

        if client_ver < min_ver:
            renderer.print_error(
                f"Client version {CLIENT_VERSION} is too old.\n"
                f"Server requires client version {min_client_version} or higher.\n"
                f"Please upgrade: pip install --upgrade comma-tools"
            )
            raise typer.Exit(1)

        # Check for deprecated features (informational only)
        deprecated = response.get("deprecated_features", [])
        if deprecated and isinstance(deprecated, list):
            renderer.print(
                f"[yellow]Warning: The following API features are deprecated: "
                f"{', '.join(deprecated)}[/yellow]"
            )

    except typer.Exit:
        raise  # Re-raise exit exceptions
    except (httpx.HTTPError, httpx.RequestError, ValueError):
        # Silently continue if version check fails (e.g., old server without endpoint)
        # This ensures backward compatibility with servers that don't have /v1/version yet
        pass


@app.callback()
def main(
    url: Annotated[Optional[str], typer.Option("--url", "-u", help="Base URL [default: http://127.0.0.1:8080]")] = None,
    api_key: Annotated[Optional[str], typer.Option("--api-key", "-k", help="Bearer token")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Machine-output mode")] = False,
    timeout: Annotated[int, typer.Option("--timeout", help="Request timeout")] = 30,
    no_verify: Annotated[bool, typer.Option("--no-verify", help="Skip TLS verify")] = False,
    quiet: Annotated[
        bool, typer.Option("--quiet", "-q", help="Suppress non-essential logs")
    ] = False,
):
    """
    CTS CLI - Command-line interface for CTS-Lite HTTP API.
    
    Examples:
      cts cap
      
      cts run cruise-control-analyzer -p log_file=/path/to/file.rlog.zst --follow
      
      cts runs list
      
      cts art list <run_id>
    """
    global _config, _http_client, _renderer

    _config = Config(url=url, api_key=api_key, timeout=timeout, no_verify=no_verify)
    _http_client = HTTPClient(_config)
    _renderer = Renderer(json_output=json_output, quiet=quiet)

    # Check version compatibility with server
    check_version_compatibility(_http_client, _renderer)


@app.command()
def ping():
    """GET /v1/health (pretty print)."""
    exit_code = ping_command(get_http_client(), get_renderer())
    raise typer.Exit(exit_code)


@app.command()
def cap():
    """GET /v1/capabilities - List all available tools and monitors."""
    exit_code = capabilities_command(get_http_client(), get_renderer())
    raise typer.Exit(exit_code)


@app.command()
def capabilities():
    """Alias for 'cap' - List all available tools and monitors."""
    exit_code = capabilities_command(get_http_client(), get_renderer())
    raise typer.Exit(exit_code)


@app.command()
def run(
    tool_id: Annotated[str, typer.Argument(help="Tool ID to run (use 'cts cap' to see available tools)")],
    params: Annotated[
        Optional[List[str]], typer.Option("-p", help="Tool parameters in name=value format (repeatable). Use 'cts cap' to see parameter names for each tool.")
    ] = None,
    path: Annotated[Optional[str], typer.Option("--path", help="Reference a local file path (server must have access to this path)")] = None,
    upload: Annotated[Optional[str], typer.Option("--upload", help="Upload a local file to server first, then use it in the run (use when server can't access your files)")] = None,
    wait: Annotated[
        bool, typer.Option("--wait", help="Block until run completes and exit with run status")
    ] = False,
    follow: Annotated[bool, typer.Option("--follow", help="Like --wait but with real-time log tailing (Server-Sent Events)")] = False,
    out_dir: Annotated[
        Optional[str], typer.Option("--out-dir", help="Download artifacts after successful completion")
    ] = None,
    open_html: Annotated[
        bool, typer.Option("--open", help="Open HTML artifacts in browser after download")
    ] = False,
    name: Annotated[Optional[str], typer.Option("--name", help="Human-readable name for this run")] = None,
):
    """
    Run a tool with specified parameters.
    
    Examples:
      cts run cruise-control-analyzer \\
        -p log_file=/path/to/file.rlog.zst \\
        -p speed_min=55.0 \\
        --follow
      
      cts run rlog-to-csv \\
        --upload /path/to/local/file.rlog.zst \\
        -p out=/tmp/output.csv
    """
    if params is None:
        params = []

    if follow:
        wait = True

    if (wait or follow) and out_dir is None:
        out_dir = str(get_config().out_dir)

    exit_code = run_command(
        tool_id=tool_id,
        params=params,
        path=path,
        upload=upload,
        wait=wait,
        follow=follow,
        out_dir=out_dir,
        open_html=open_html,
        name=name,
        http_client=get_http_client(),
        renderer=get_renderer(),
    )
    raise typer.Exit(exit_code)


@app.command()
def logs(
    run_id: Annotated[str, typer.Argument(help="Run ID (returned by 'cts run' or found with 'cts runs list')")],
    follow: Annotated[bool, typer.Option("--follow", help="Stream logs in real-time")] = False,
):
    """
    Stream logs for a run.
    
    The RUN_ID is returned when you start a run with 'cts run'.
    You can also find run IDs with 'cts runs list'.
    """
    exit_code = logs_command(
        run_id=run_id, follow=follow, http_client=get_http_client(), renderer=get_renderer()
    )
    raise typer.Exit(exit_code)


runs_app = typer.Typer(name="runs", help="Run management commands")
art_app = typer.Typer(name="art", help="Artifact management commands")
mon_app = typer.Typer(name="mon", help="Monitor management commands")

app.add_typer(runs_app)
app.add_typer(art_app)
app.add_typer(mon_app)


@runs_app.command("list")
def runs_list(
    status: Annotated[Optional[str], typer.Option("--status", help="Filter by status")] = None,
):
    """List recent runs."""
    try:
        endpoint = "/v1/runs"
        if status:
            endpoint += f"?status={status}"

        runs = get_http_client().get_json(endpoint)

        renderer = get_renderer()
        if renderer.json_output:
            renderer.print_json(runs)
        else:
            if not isinstance(runs, list):
                renderer.print_error("Unexpected runs response format")
                raise typer.Exit(2)

            if not runs:
                renderer.print("No runs found")
                return

            run_data = []
            for run in runs:
                run_dict: Dict[str, Any] = run if isinstance(run, dict) else {}
                run_data.append(
                    {
                        "ID": run_dict.get("id", ""),
                        "Tool": run_dict.get("tool_id", ""),
                        "Status": run_dict.get("status", ""),
                        "Started": run_dict.get("started_at", ""),
                        "Duration": run_dict.get("duration", ""),
                    }
                )

            renderer.print_table(run_data, title="Recent Runs")

        raise typer.Exit(0)

    except Exception as e:
        get_renderer().print_error(f"Failed to list runs: {e}")
        raise typer.Exit(2)


@runs_app.command("get")
def runs_get(
    run_id: Annotated[str, typer.Argument(help="Run ID (from 'cts run' or 'cts runs list')")],
):
    """
    Show run summary JSON.
    
    See also: 'cts art list <run_id>' to list output artifacts.
    """
    try:
        run_info = get_http_client().get_json(f"/v1/runs/{run_id}")
        get_renderer().print_json(run_info)
        raise typer.Exit(0)

    except Exception as e:
        get_renderer().print_error(f"Failed to get run: {e}")
        raise typer.Exit(2)


@art_app.command("list")
def art_list(
    run_id: Annotated[str, typer.Argument(help="Run ID (from 'cts run' or 'cts runs list')")],
):
    """
    List artifacts for a run.
    
    After a run completes, use this to see what output files were generated.
    Then use 'cts art get <artifact_id>' to download them.
    """
    exit_code = list_artifacts_command(
        run_id=run_id, http_client=get_http_client(), renderer=get_renderer()
    )
    raise typer.Exit(exit_code)


@art_app.command("get")
def art_get(
    artifact_id: Annotated[str, typer.Argument(help="Artifact ID (from 'cts art list <run_id>')")],
    download: Annotated[Optional[str], typer.Option("--download", help="Download to file path")] = None,
    stdout: Annotated[bool, typer.Option("--stdout", help="Print content to stdout")] = False,
    force: Annotated[bool, typer.Option("--force", help="Overwrite existing file")] = False,
):
    """
    Get artifact content or download to file.
    
    Get artifact IDs with: cts art list <run_id>
    
    Example:
      cts art get abc123 --download output.csv
    """
    exit_code = get_artifact_command(
        artifact_id=artifact_id,
        download=download,
        stdout=stdout,
        force=force,
        http_client=get_http_client(),
        renderer=get_renderer(),
    )
    raise typer.Exit(exit_code)


@mon_app.command("start")
def mon_start(
    tool_id: Annotated[str, typer.Argument(help="Monitor ID to start (use 'cts cap' to see available monitors)")],
    params: Annotated[
        Optional[List[str]], typer.Option("-p", help="Monitor parameters in name=value format (repeatable)")
    ] = None,
):
    """
    Start a monitor.
    
    To see available monitors, run: cts cap
    """
    if params is None:
        params = []

    exit_code = start_monitor_command(
        tool_id=tool_id, params=params, http_client=get_http_client(), renderer=get_renderer()
    )
    raise typer.Exit(exit_code)


@mon_app.command("stream")
def mon_stream(
    monitor_id: Annotated[str, typer.Argument(help="Monitor ID (returned by 'cts mon start' or found with 'cts mon ls')")],
    raw: Annotated[bool, typer.Option("--raw", help="Output raw WebSocket frames")] = False,
    ndjson: Annotated[bool, typer.Option("--ndjson", help="Output newline-delimited JSON")] = False,
):
    """
    Stream data from a monitor.
    
    Start a monitor first with: cts mon start <monitor_id>
    """
    exit_code = stream_monitor_command(
        monitor_id=monitor_id,
        raw=raw,
        ndjson=ndjson,
        http_client=get_http_client(),
        renderer=get_renderer(),
    )
    raise typer.Exit(exit_code)


@mon_app.command("stop")
def mon_stop(
    monitor_id: Annotated[str, typer.Argument(help="Monitor ID (from 'cts mon start' or 'cts mon ls')")],
):
    """
    Stop a monitor.
    
    Find running monitors with: cts mon ls
    """
    exit_code = stop_monitor_command(
        monitor_id=monitor_id, http_client=get_http_client(), renderer=get_renderer()
    )
    raise typer.Exit(exit_code)


@mon_app.command("ls")
def mon_ls():
    """List active monitors."""
    exit_code = list_monitors_command(http_client=get_http_client(), renderer=get_renderer())
    raise typer.Exit(exit_code)


@app.command()
def upload(
    file_path: Annotated[str, typer.Argument(help="File to upload")],
):
    """Upload a file and return upload ID."""
    exit_code = upload_command(
        file_path=file_path, http_client=get_http_client(), renderer=get_renderer()
    )
    raise typer.Exit(exit_code)


def cli_main():
    """Entry point for console script."""
    try:
        app()
    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        if _http_client:
            _http_client.close()


if __name__ == "__main__":
    cli_main()
