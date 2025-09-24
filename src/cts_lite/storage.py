"""Storage and artifact management for CTS-Lite."""

import hashlib
import shutil
from pathlib import Path
from typing import Optional

from .config import CTSLiteConfig


class StorageManager:
    """Manages file storage and artifact operations."""
    
    def __init__(self, config: CTSLiteConfig):
        self.config = config
    
    def get_run_dir(self, run_id: str) -> Path:
        """Get the working directory for a run."""
        run_dir = self.config.runs_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir
    
    def get_run_input_dir(self, run_id: str) -> Path:
        """Get the input directory for a run."""
        input_dir = self.get_run_dir(run_id) / "input"
        input_dir.mkdir(exist_ok=True)
        return input_dir
    
    def get_run_work_dir(self, run_id: str) -> Path:
        """Get the work directory for a run."""
        work_dir = self.get_run_dir(run_id) / "work"
        work_dir.mkdir(exist_ok=True)
        return work_dir
    
    def get_run_artifacts_dir(self, run_id: str) -> Path:
        """Get the artifacts directory for a run."""
        artifacts_dir = self.get_run_dir(run_id) / "artifacts"
        artifacts_dir.mkdir(exist_ok=True)
        return artifacts_dir
    
    def get_run_log_path(self, run_id: str) -> Path:
        """Get the log file path for a run."""
        return self.get_run_dir(run_id) / "logs.jsonl"
    
    def compute_sha256(self, file_path: Path) -> str:
        """Compute SHA-256 hash of a file."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    
    def register_artifact(self, run_id: str, artifact_path: Path, name: Optional[str] = None) -> dict:
        """Register an artifact and compute metadata."""
        if not artifact_path.exists():
            raise FileNotFoundError(f"Artifact not found: {artifact_path}")
        
        if name is None:
            name = artifact_path.name
        
        size = artifact_path.stat().st_size
        sha256 = self.compute_sha256(artifact_path)
        
        media_type = self._get_media_type(artifact_path.suffix)
        
        return {
            "name": name,
            "size": size,
            "sha256": sha256,
            "media_type": media_type,
            "path": str(artifact_path),
        }
    
    def _get_media_type(self, extension: str) -> str:
        """Get media type from file extension."""
        extension = extension.lower()
        media_types = {
            ".csv": "text/csv",
            ".json": "application/json",
            ".html": "text/html",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".txt": "text/plain",
            ".log": "text/plain",
            ".jsonl": "application/x-jsonlines",
        }
        return media_types.get(extension, "application/octet-stream")
    
    def cleanup_run(self, run_id: str, keep_artifacts: bool = True) -> None:
        """Clean up run directory, optionally keeping artifacts."""
        run_dir = self.get_run_dir(run_id)
        if not run_dir.exists():
            return
        
        if keep_artifacts:
            for item in run_dir.iterdir():
                if item.name not in ("artifacts", "logs.jsonl"):
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()
        else:
            shutil.rmtree(run_dir)
    
    def get_disk_usage(self) -> dict:
        """Get disk usage information."""
        total, used, free = shutil.disk_usage(self.config.data_root)
        return {
            "total_bytes": total,
            "used_bytes": used,
            "free_bytes": free,
            "free_gb": free / (1024**3),
        }
