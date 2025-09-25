"""
Main CLI application for CTS client.

Provides the main Typer application with global flags and
command routing for all CTS CLI functionality.
"""

from typing import List, Optional
import sys
from pathlib import Path

import typer
from typing_extensions import Annotated

from .config import Config
from .http import HTTPClient
from .render import Renderer
from .commands.cap import ping_command, capabilities_command
from .commands.run import run_command
from .commands.logs import logs_command
from .commands.artifacts import list_artifacts_command, get_artifact_command
from .commands.monitors import (
    start_monitor_command,
    stream_monitor_command,
    stop_monitor_command,
    list_monitors_command
)
from .commands.uploads import upload_command


app = typer.Typer(
    name="cts",
    help="CTS CLI - Command-line interface for CTS-Lite HTTP API",
    no_args_is_help=True,
    add_completion=False
)

_config: Optional[Config] = None
_http_client: Optional[HTTPClient] = None
_renderer: Optional[Renderer] = None


def get_config() -> Config:
    """Get global config instance."""
    global _config
    if _config is None:
        raise RuntimeError("Config not initialized")
    return _config


def get_http_client() -> HTTPClient:
    """Get global HTTP client instance."""
    global _http_client
    if _http_client is None:
        raise RuntimeError("HTTP client not initialized")
    return _http_client


def get_renderer() -> Renderer:
    """Get global renderer instance."""
    global _renderer
    if _renderer is None:
        raise RuntimeError("Renderer not initialized")
    return _renderer


@app.callback()
def main(
    url: Annotated[Optional[str], typer.Option("--url", "-u", help="Base URL")] = None,
    api_key: Annotated[Optional[str], typer.Option("--api-key", "-k", help="Bearer token")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Machine-output mode")] = False,
    timeout: Annotated[int, typer.Option("--timeout", help="Request timeout")] = 30,
    no_verify: Annotated[bool, typer.Option("--no-verify", help="Skip TLS verify")] = False,
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress non-essential logs")] = False,
):
    """CTS CLI - Command-line interface for CTS-Lite HTTP API."""
    global _config, _http_client, _renderer
    
    _config = Config(
        url=url,
        api_key=api_key,
        timeout=timeout,
        no_verify=no_verify
    )
    _http_client = HTTPClient(_config)
    _renderer = Renderer(json_output=json_output, quiet=quiet)


@app.command()
def ping():
    """GET /v1/health (pretty print)."""
    exit_code = ping_command(get_http_client(), get_renderer())
    raise typer.Exit(exit_code)


@app.command()
def cap():
    """GET /v1/capabilities."""
    exit_code = capabilities_command(get_http_client(), get_renderer())
    raise typer.Exit(exit_code)


@app.command()
def run(
    tool_id: Annotated[str, typer.Argument(help="Tool ID to run")],
    params: Annotated[Optional[List[str]], typer.Option("-p", help="Parameters (name=value)")] = None,
    path: Annotated[Optional[str], typer.Option("--path", help="Use local path")] = None,
    upload: Annotated[Optional[str], typer.Option("--upload", help="Upload then reference")] = None,
    wait: Annotated[bool, typer.Option("--wait", help="Stream logs and exit with job status")] = False,
    follow: Annotated[bool, typer.Option("--follow", help="Implies --wait, tail SSE logs")] = False,
    out_dir: Annotated[Optional[str], typer.Option("--out-dir", help="Download artifacts after success")] = None,
    open_html: Annotated[bool, typer.Option("--open", help="Open HTML artifacts after download")] = False,
    name: Annotated[Optional[str], typer.Option("--name", help="Run name")] = None,
):
    """Run a tool with specified parameters."""
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
        renderer=get_renderer()
    )
    raise typer.Exit(exit_code)


@app.command()
def logs(
    run_id: Annotated[str, typer.Argument(help="Run ID")],
    follow: Annotated[bool, typer.Option("--follow", help="Follow logs")] = False,
):
    """Stream logs for a run."""
    exit_code = logs_command(
        run_id=run_id,
        follow=follow,
        http_client=get_http_client(),
        renderer=get_renderer()
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
            if not runs:
                renderer.print("No runs found")
                return
            
            run_data = []
            for run in runs:
                run_data.append({
                    "ID": run.get("id", ""),
                    "Tool": run.get("tool_id", ""),
                    "Status": run.get("status", ""),
                    "Started": run.get("started_at", ""),
                    "Duration": run.get("duration", "")
                })
            
            renderer.print_table(run_data, title="Recent Runs")
        
        raise typer.Exit(0)
        
    except Exception as e:
        get_renderer().print_error(f"Failed to list runs: {e}")
        raise typer.Exit(2)


@runs_app.command("get")
def runs_get(
    run_id: Annotated[str, typer.Argument(help="Run ID")],
):
    """Show run summary JSON."""
    try:
        run_info = get_http_client().get_json(f"/v1/runs/{run_id}")
        get_renderer().print_json(run_info)
        raise typer.Exit(0)
        
    except Exception as e:
        get_renderer().print_error(f"Failed to get run: {e}")
        raise typer.Exit(2)


@art_app.command("list")
def art_list(
    run_id: Annotated[str, typer.Argument(help="Run ID")],
):
    """List artifacts for a run."""
    exit_code = list_artifacts_command(
        run_id=run_id,
        http_client=get_http_client(),
        renderer=get_renderer()
    )
    raise typer.Exit(exit_code)


@art_app.command("get")
def art_get(
    artifact_id: Annotated[str, typer.Argument(help="Artifact ID")],
    download: Annotated[Optional[str], typer.Option("--download", help="Download to path")] = None,
    stdout: Annotated[bool, typer.Option("--stdout", help="Output to stdout")] = False,
    force: Annotated[bool, typer.Option("--force", help="Force overwrite")] = False,
):
    """Get artifact content or download to file."""
    exit_code = get_artifact_command(
        artifact_id=artifact_id,
        download=download,
        stdout=stdout,
        force=force,
        http_client=get_http_client(),
        renderer=get_renderer()
    )
    raise typer.Exit(exit_code)


@mon_app.command("start")
def mon_start(
    tool_id: Annotated[str, typer.Argument(help="Tool ID")],
    params: Annotated[Optional[List[str]], typer.Option("-p", help="Parameters (name=value)")] = None,
):
    """Start a monitor."""
    if params is None:
        params = []
    
    exit_code = start_monitor_command(
        tool_id=tool_id,
        params=params,
        http_client=get_http_client(),
        renderer=get_renderer()
    )
    raise typer.Exit(exit_code)


@mon_app.command("stream")
def mon_stream(
    monitor_id: Annotated[str, typer.Argument(help="Monitor ID")],
    raw: Annotated[bool, typer.Option("--raw", help="Raw frame output")] = False,
    ndjson: Annotated[bool, typer.Option("--ndjson", help="NDJSON output")] = False,
):
    """Stream data from a monitor."""
    exit_code = stream_monitor_command(
        monitor_id=monitor_id,
        raw=raw,
        ndjson=ndjson,
        http_client=get_http_client(),
        renderer=get_renderer()
    )
    raise typer.Exit(exit_code)


@mon_app.command("stop")
def mon_stop(
    monitor_id: Annotated[str, typer.Argument(help="Monitor ID")],
):
    """Stop a monitor."""
    exit_code = stop_monitor_command(
        monitor_id=monitor_id,
        http_client=get_http_client(),
        renderer=get_renderer()
    )
    raise typer.Exit(exit_code)


@mon_app.command("ls")
def mon_ls():
    """List active monitors."""
    exit_code = list_monitors_command(
        http_client=get_http_client(),
        renderer=get_renderer()
    )
    raise typer.Exit(exit_code)


@app.command()
def upload(
    file_path: Annotated[str, typer.Argument(help="File to upload")],
):
    """Upload a file and return upload ID."""
    exit_code = upload_command(
        file_path=file_path,
        http_client=get_http_client(),
        renderer=get_renderer()
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
        global _http_client
        if _http_client:
            _http_client.close()


if __name__ == "__main__":
    cli_main()
