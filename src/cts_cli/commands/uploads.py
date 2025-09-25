"""
Uploads command implementation.

Implements 'cts upload' command for uploading files with
SHA256 computation and progress reporting.
"""

import hashlib
from pathlib import Path
import typer

from ..http import HTTPClient
from ..render import Renderer, format_bytes


def upload_command(
    file_path: str, http_client: HTTPClient = None, renderer: Renderer = None
) -> int:
    """Upload a file and return upload ID."""
    try:
        file_path_obj = Path(file_path)

        if not file_path_obj.exists():
            renderer.print_error(f"File not found: {file_path}")
            return 1

        file_size = file_path_obj.stat().st_size

        renderer.print(f"Computing SHA256 for {file_path_obj.name}...")
        sha256_hash = hashlib.sha256()

        with open(file_path_obj, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)

        file_hash = sha256_hash.hexdigest()

        create_data = {"filename": file_path_obj.name, "size": file_size, "sha256": file_hash}

        renderer.print(f"Creating upload for {file_path_obj.name} ({format_bytes(file_size)})...")
        upload_info = http_client.post_json("/v1/uploads", create_data)
        upload_id = upload_info["upload_id"]
        upload_url = upload_info["upload_url"]

        renderer.print("Uploading file content...")
        with open(file_path_obj, "rb") as f:
            response = http_client.put(upload_url, content=f.read())
            response.raise_for_status()

        renderer.print("Finalizing upload...")
        finalize_response = http_client.post(f"/v1/uploads/{upload_id}/finalize")
        finalize_response.raise_for_status()

        if renderer.json_output:
            result = {
                "upload_id": upload_id,
                "filename": file_path_obj.name,
                "size": file_size,
                "sha256": file_hash,
                "status": "completed",
            }
            renderer.print_json(result)
        else:
            renderer.print_success(f"Upload completed: {upload_id}")
            renderer.print(f"Filename: {file_path_obj.name}")
            renderer.print(f"Size: {format_bytes(file_size)}")
            renderer.print(f"SHA256: {file_hash}")

        return 0

    except Exception as e:
        renderer.print_error(f"Upload failed: {e}")
        return 1
