"""Service configuration management for CTS-Lite API."""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Config(BaseSettings):
    """CTS-Lite API configuration."""

    model_config = {"env_prefix": "CTS_API_", "env_file": ".env", "case_sensitive": False}

    host: str = Field(default="127.0.0.1", description="API host address")
    port: int = Field(default=8080, description="API port")
    log_level: str = Field(default="INFO", description="Logging level")
    storage_dir: str = Field(default="/var/lib/cts-lite", description="Artifact storage directory")

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, v: str) -> str:
        """Normalize log level to uppercase for logging compatibility."""
        return v.upper()

    @classmethod
    def from_env(cls) -> "Config":
        """Create config from environment variables and .env files."""
        return cls()
