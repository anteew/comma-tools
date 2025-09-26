"""Service configuration management for CTS-Lite API."""

import os
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Config(BaseSettings):
    """CTS-Lite API configuration."""

    model_config = {"env_prefix": "CTS_API_", "env_file": ".env", "case_sensitive": False}

    host: str = Field(default="127.0.0.1", description="API host address")
    port: int = Field(default=8080, description="API port")
    log_level: str = Field(default="INFO", description="Logging level")

    @classmethod
    def from_env(cls) -> "Config":
        """Create config from environment variables."""
        return cls(
            host=os.getenv("CTS_API_HOST", "127.0.0.1"),
            port=int(os.getenv("CTS_API_PORT", "8080")),
            log_level=os.getenv("CTS_API_LOG_LEVEL", "INFO").upper(),
        )
