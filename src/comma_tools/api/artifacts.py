"""Artifact management endpoints and storage."""

import logging
import mimetypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from .config import Config
from .models import ArtifactMetadata, ArtifactsResponse

logger = logging.getLogger(__name__)
router = APIRouter()


class ArtifactManager:
    """Manages artifact storage and retrieval."""

    def __init__(self, storage_base_dir: Path):
        """Initialize artifact manager.

        Args:
            storage_base_dir: Base directory for artifact storage
        """
        self.storage_base_dir = storage_base_dir
        self.artifacts: Dict[str, ArtifactMetadata] = {}

    def register_artifact(self, run_id: str, file_path: Path) -> str:
        """Register a file as an artifact for a run.

        Args:
            run_id: Run identifier
            file_path: Path to file to register

        Returns:
            Artifact identifier
        """
        artifact_id = str(uuid4())

        artifact_dir = self.storage_base_dir / "runs" / run_id / "artifacts"
        artifact_dir.mkdir(parents=True, exist_ok=True)

        stored_path = artifact_dir / file_path.name
        stored_path.write_bytes(file_path.read_bytes())

        content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        metadata = ArtifactMetadata(
            artifact_id=artifact_id,
            run_id=run_id,
            filename=file_path.name,
            content_type=content_type,
            size_bytes=stored_path.stat().st_size,
            created_at=datetime.now(timezone.utc),
            download_url=f"/v1/artifacts/{artifact_id}/download",
        )

        self.artifacts[artifact_id] = metadata
        return artifact_id

    def get_artifacts_for_run(self, run_id: str) -> List[ArtifactMetadata]:
        """Get all artifacts for a specific run.

        Args:
            run_id: Run identifier

        Returns:
            List of artifact metadata
        """
        return [artifact for artifact in self.artifacts.values() if artifact.run_id == run_id]

    def get_artifact_file_path(self, artifact_id: str) -> Path:
        """Get filesystem path for artifact download.

        Args:
            artifact_id: Artifact identifier

        Returns:
            Path to artifact file

        Raises:
            KeyError: If artifact not found
        """
        if artifact_id not in self.artifacts:
            raise KeyError(f"Artifact '{artifact_id}' not found")

        metadata = self.artifacts[artifact_id]
        return self.storage_base_dir / "runs" / metadata.run_id / "artifacts" / metadata.filename


_artifact_manager: Optional[ArtifactManager] = None


def get_artifact_manager() -> ArtifactManager:
    """Get artifact manager instance."""
    global _artifact_manager
    if _artifact_manager is None:
        config = Config.from_env()
        storage_dir = Path(config.storage_dir)
        _artifact_manager = ArtifactManager(storage_dir)
    return _artifact_manager


@router.get("/runs/{run_id}/artifacts", response_model=ArtifactsResponse)
async def list_run_artifacts(
    run_id: str, manager: ArtifactManager = Depends(get_artifact_manager)
) -> ArtifactsResponse:
    """List artifacts for a run.

    Args:
        run_id: Run identifier
        manager: Artifact manager dependency

    Returns:
        Artifacts response with list of artifacts
    """
    artifacts = manager.get_artifacts_for_run(run_id)
    return ArtifactsResponse(run_id=run_id, artifacts=artifacts, total_count=len(artifacts))


@router.get("/artifacts/{artifact_id}")
async def get_artifact_metadata(
    artifact_id: str, manager: ArtifactManager = Depends(get_artifact_manager)
) -> ArtifactMetadata:
    """Get artifact metadata.

    Args:
        artifact_id: Artifact identifier
        manager: Artifact manager dependency

    Returns:
        Artifact metadata

    Raises:
        HTTPException: If artifact not found
    """
    if artifact_id not in manager.artifacts:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return manager.artifacts[artifact_id]


@router.get("/artifacts/{artifact_id}/download")
async def download_artifact(
    artifact_id: str, manager: ArtifactManager = Depends(get_artifact_manager)
) -> FileResponse:
    """Download artifact file.

    Args:
        artifact_id: Artifact identifier
        manager: Artifact manager dependency

    Returns:
        File response for download

    Raises:
        HTTPException: If artifact or file not found
    """
    try:
        file_path = manager.get_artifact_file_path(artifact_id)
        metadata = manager.artifacts[artifact_id]

        return FileResponse(
            path=str(file_path), filename=metadata.filename, media_type=metadata.content_type
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Artifact not found")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Artifact file not found")
