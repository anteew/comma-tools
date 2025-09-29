"""
Download endpoint for comma connect integration.

Provides REST API for downloading logs from comma.ai directly into
the CTS-Lite working directory for subsequent analysis.
"""

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

from fastapi import APIRouter, HTTPException, status

from .models import DownloadRequest, DownloadResponse, DownloadStatus

router = APIRouter(prefix="/v1/downloads", tags=["downloads"])

_active_downloads: Dict[str, DownloadResponse] = {}


@router.post("", response_model=DownloadResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_download(request: DownloadRequest) -> DownloadResponse:
    """
    Initiate download of log files from comma connect.

    This endpoint downloads log files from comma.ai into the specified
    destination directory. Files are organized by canonical route structure:
    `<dest_root>/<dongle_id>/<YYYY-MM-DD--HH-MM-SS>/<segment>/<filename>`

    Authentication is handled via COMMA_JWT environment variable or
    ~/.comma/auth.json file (see comma.ai documentation).

    Args:
        request: Download request with route and options

    Returns:
        DownloadResponse with download status and identifier

    Raises:
        HTTPException: If authentication fails, route not found, or other errors
    """
    download_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc)

    response = DownloadResponse(
        download_id=download_id,
        status=DownloadStatus.QUEUED,
        canonical_route=None,
        dest_root=request.dest_root,
        error=None,
        created_at=created_at,
        completed_at=None,
    )

    _active_downloads[download_id] = response

    try:
        from ..sources.connect.client import ConnectClient
        from ..sources.connect.downloader import LogDownloader
        from ..sources.connect.resolver import RouteResolver

        client = ConnectClient()

        response.status = DownloadStatus.RESOLVING
        resolver = RouteResolver(client)
        canonical_route = resolver.resolve(request.route, search_days=request.search_days)
        response.canonical_route = canonical_route

        response.status = DownloadStatus.DOWNLOADING
        downloader = LogDownloader(client, parallel=request.parallel)
        dest_path = Path(request.dest_root)

        report = downloader.download_route(
            canonical_route, dest_path, request.file_types, resume=request.resume
        )

        response.status = DownloadStatus.COMPLETED
        response.downloaded_files = report.success_count
        response.skipped_files = report.skip_count
        response.failed_files = report.failure_count
        response.total_bytes = report.total_bytes
        response.completed_at = datetime.now(timezone.utc)

        _active_downloads[download_id] = response
        return response

    except ValueError as e:
        response.status = DownloadStatus.FAILED
        response.error = str(e)
        response.completed_at = datetime.now(timezone.utc)
        _active_downloads[download_id] = response

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Download failed: {e}",
        ) from e

    except Exception as e:
        response.status = DownloadStatus.FAILED
        response.error = str(e)
        response.completed_at = datetime.now(timezone.utc)
        _active_downloads[download_id] = response

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Download failed: {e}",
        ) from e


@router.get("/{download_id}", response_model=DownloadResponse)
async def get_download_status(download_id: str) -> DownloadResponse:
    """
    Get status of a download operation.

    Args:
        download_id: Download identifier from create_download

    Returns:
        DownloadResponse with current status

    Raises:
        HTTPException: If download_id not found
    """
    if download_id not in _active_downloads:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Download {download_id} not found"
        )

    return _active_downloads[download_id]
