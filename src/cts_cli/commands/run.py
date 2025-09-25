"""
Run command implementation.

Implements 'cts run' command for executing tools with parameter
handling, input management, and artifact downloading.
"""

import json
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
import typer

from ..http import HTTPClient
from ..render import Renderer
from ..sse import stream_logs


def parse_parameters(params: List[str]) -> Dict[str, Any]:
    """Parse -p name=value parameters with type inference."""
    result = {}

    for param in params:
        if "=" not in param:
            raise ValueError(f"Invalid parameter format: {param}. Use -p name=value")

        name, value = param.split("=", 1)

        if value.lower() in ("true", "false"):
            result[name] = value.lower() == "true"
        elif value.isdigit():
            result[name] = int(value)
        elif "," in value:
            result[name] = [v.strip() for v in value.split(",")]
        else:
            try:
                result[name] = float(value)
            except ValueError:
                result[name] = value

    return result


def upload_file(http_client: HTTPClient, file_path: str) -> str:
    """Upload file and return upload ID."""
    file_path_obj = Path(file_path)

    if not file_path_obj.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    sha256_hash = hashlib.sha256()
    with open(file_path_obj, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256_hash.update(chunk)

    file_hash = sha256_hash.hexdigest()

    create_data = {
        "filename": file_path_obj.name,
        "size": file_path_obj.stat().st_size,
        "sha256": file_hash,
    }

    upload_info = http_client.post_json("/v1/uploads", create_data)
    upload_id = upload_info["upload_id"]
    upload_url = upload_info["upload_url"]

    with open(file_path_obj, "rb") as f:
        response = http_client.put(upload_url, content=f.read())
        response.raise_for_status()

    http_client.post(f"/v1/uploads/{upload_id}/finalize")

    return upload_id


def download_artifacts(
    http_client: HTTPClient, run_id: str, out_dir: Path, renderer: Renderer, open_html: bool = False
) -> None:
    """Download artifacts for a completed run."""
    try:
        artifacts = http_client.get_json(f"/v1/runs/{run_id}/artifacts")

        if not artifacts:
            renderer.print("No artifacts to download")
            return

        out_dir.mkdir(parents=True, exist_ok=True)
        html_files = []

        for artifact in artifacts:
            artifact_id = artifact["id"]
            filename = artifact["filename"]
            download_url = artifact["download_url"]

            output_path = out_dir / filename

            renderer.print(f"Downloading {filename}...")
            http_client.download_file(download_url, str(output_path))

            if filename.endswith(".html"):
                html_files.append(output_path)

        renderer.print_success(f"Downloaded {len(artifacts)} artifacts to {out_dir}")

        if open_html and html_files:
            import webbrowser

            for html_file in html_files:
                webbrowser.open(f"file://{html_file.absolute()}")
                renderer.print(f"Opened {html_file}")

    except Exception as e:
        renderer.print_error(f"Failed to download artifacts: {e}")


def run_command(
    tool_id: str,
    params: List[str],
    path: Optional[str] = None,
    upload: Optional[str] = None,
    wait: bool = False,
    follow: bool = False,
    out_dir: Optional[str] = None,
    open_html: bool = False,
    name: Optional[str] = None,
    http_client: HTTPClient = None,
    renderer: Renderer = None,
) -> int:
    """Run a tool with specified parameters."""
    try:
        parsed_params = parse_parameters(params)

        input_ref = None
        if path:
            input_ref = {"type": "path", "value": path}
        elif upload:
            renderer.print(f"Uploading {upload}...")
            upload_id = upload_file(http_client, upload)
            input_ref = {"type": "upload", "value": upload_id}
            renderer.print_success(f"Uploaded file: {upload_id}")

        run_data = {"tool_id": tool_id, "params": parsed_params}

        if input_ref:
            run_data["input"] = input_ref

        if name:
            run_data["name"] = name

        run_info = http_client.post_json("/v1/runs", run_data)
        run_id = run_info["run_id"]

        renderer.print_success(f"Started run: {run_id}")

        if not wait and not follow:
            if renderer.json_output:
                renderer.print_json({"run_id": run_id, "status": "started"})
            return 0

        if follow:
            renderer.print("Streaming logs...")
            try:
                for log_line in stream_logs(
                    http_client, run_id, follow=True, json_output=renderer.json_output
                ):
                    renderer.print(log_line)
            except KeyboardInterrupt:
                renderer.print("\nStopped following logs")

        if wait or follow:
            renderer.print("Waiting for run to complete...")

            while True:
                run_status = http_client.get_json(f"/v1/runs/{run_id}")
                status = run_status["status"]

                if status in ("completed", "failed", "canceled"):
                    break

                import time

                time.sleep(2)

            final_status = http_client.get_json(f"/v1/runs/{run_id}")

            if renderer.json_output:
                renderer.print_json(final_status)
            else:
                status = final_status["status"]
                if status == "completed":
                    renderer.print_success("Run completed successfully")
                elif status == "failed":
                    renderer.print_error("Run failed")
                    error = final_status.get("error", "Unknown error")
                    renderer.print(f"Error: {error}")
                elif status == "canceled":
                    renderer.print_warning("Run was canceled")

            if final_status["status"] == "completed" and out_dir:
                download_artifacts(http_client, run_id, Path(out_dir), renderer, open_html)

            if final_status["status"] == "completed":
                return 0
            elif final_status["status"] == "failed":
                return 3
            elif final_status["status"] == "canceled":
                return 4

        return 0

    except Exception as e:
        renderer.print_error(f"Run failed: {e}")
        return 1
