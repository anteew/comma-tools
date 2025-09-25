"""
Artifacts command implementation.

Implements 'cts art' commands for listing and downloading
run artifacts with path safety and overwrite protection.
"""

import sys
from pathlib import Path
from typing import Optional
import typer

from ..http import HTTPClient
from ..render import Renderer, safe_path_join, format_bytes


def list_artifacts_command(
    run_id: str,
    http_client: HTTPClient = None,
    renderer: Renderer = None
) -> int:
    """List artifacts for a run."""
    try:
        artifacts = http_client.get_json(f"/v1/runs/{run_id}/artifacts")
        
        if renderer.json_output:
            renderer.print_json(artifacts)
        else:
            if not artifacts:
                renderer.print("No artifacts found")
                return 0
            
            artifact_data = []
            for artifact in artifacts:
                artifact_data.append({
                    "ID": artifact.get("id", ""),
                    "Filename": artifact.get("filename", ""),
                    "Size": format_bytes(artifact.get("size", 0)),
                    "Type": artifact.get("type", ""),
                    "Created": artifact.get("created_at", "")
                })
            
            renderer.print_table(artifact_data, title=f"Artifacts for run {run_id}")
        
        return 0
        
    except Exception as e:
        renderer.print_error(f"Failed to list artifacts: {e}")
        return 2


def get_artifact_command(
    artifact_id: str,
    download: Optional[str] = None,
    stdout: bool = False,
    force: bool = False,
    http_client: HTTPClient = None,
    renderer: Renderer = None
) -> int:
    """Get artifact content or download to file."""
    try:
        artifact_info = http_client.get_json(f"/v1/artifacts/{artifact_id}")
        download_url = artifact_info["download_url"]
        filename = artifact_info["filename"]
        
        if stdout:
            response = http_client.get(download_url)
            response.raise_for_status()
            
            if renderer.json_output:
                content = response.text
                renderer.print_json({
                    "artifact_id": artifact_id,
                    "filename": filename,
                    "content": content
                })
            else:
                sys.stdout.write(response.text)
            
            return 0
        
        elif download:
            download_path = Path(download)
            
            if download_path.is_absolute():
                output_path = download_path
            else:
                try:
                    safe_filename = Path(download).name
                    output_path = Path.cwd() / safe_filename
                except ValueError as e:
                    renderer.print_error(f"Unsafe download path: {e}")
                    return 1
            
            if output_path.exists() and not force:
                renderer.print_error(f"File {output_path} already exists. Use --force to overwrite.")
                return 1
            
            renderer.print(f"Downloading {filename} to {output_path}...")
            http_client.download_file(download_url, str(output_path), force=force)
            
            if renderer.json_output:
                renderer.print_json({
                    "artifact_id": artifact_id,
                    "filename": filename,
                    "downloaded_to": str(output_path),
                    "size": artifact_info.get("size", 0)
                })
            else:
                renderer.print_success(f"Downloaded {filename} to {output_path}")
            
            return 0
        
        else:
            renderer.print_error("Must specify either --download PATH or --stdout")
            return 1
        
    except Exception as e:
        renderer.print_error(f"Failed to get artifact: {e}")
        return 2
