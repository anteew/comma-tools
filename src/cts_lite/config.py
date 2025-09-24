"""Configuration management for CTS-Lite service."""

import os
from pathlib import Path
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class CTSLiteConfig(BaseSettings):
    """Configuration for CTS-Lite service."""
    
    data_root: Path = Field(
        default_factory=lambda: Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "cts-lite"
    )
    
    host: str = "127.0.0.1"
    port: int = 8080
    max_workers: int = 2
    
    api_key: str = ""  # Empty means auth disabled
    cors_origins: List[str] = Field(default_factory=list)  # Empty means CORS disabled
    
    allow_hardware: bool = True
    
    retention_days: int = 30
    
    @property
    def state_db_path(self) -> Path:
        return self.data_root / "state.db"
    
    @property
    def runs_dir(self) -> Path:
        return self.data_root / "runs"
    
    @property
    def artifacts_dir(self) -> Path:
        return self.data_root / "artifacts"
    
    @property
    def uploads_dir(self) -> Path:
        return self.data_root / "uploads"
    
    def ensure_directories(self) -> None:
        """Create all necessary directories."""
        self.data_root.mkdir(parents=True, exist_ok=True)
        self.runs_dir.mkdir(exist_ok=True)
        self.artifacts_dir.mkdir(exist_ok=True)
        self.uploads_dir.mkdir(exist_ok=True)
    
    class Config:
        env_prefix = "CTS_"
        env_file = ".env"
