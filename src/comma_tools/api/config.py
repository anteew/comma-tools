"""Service configuration management for CTS-Lite API."""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Config(BaseSettings):
    """CTS-Lite API configuration."""

    model_config = {"env_prefix": "CTS_API_", "env_file": ".env", "case_sensitive": False}

    # Network
    host: str = Field(default="127.0.0.1", description="API host address")
    port: int = Field(default=8080, description="API port")
    log_level: str = Field(default="INFO", description="Logging level")

    # Storage
    storage_dir: str = Field(default="/var/lib/cts-lite", description="Artifact storage directory")

    # Resource Management
    max_concurrent_runs: int = Field(default=3, description="Maximum concurrent analyzer runs")
    tool_timeout_seconds: int = Field(default=300, description="Default tool timeout in seconds")
    max_artifact_size_mb: int = Field(default=100, description="Max artifact size in MB")
    artifact_retention_days: int = Field(default=7, description="Days to retain artifacts")

    # Performance Tuning
    log_buffer_size: int = Field(default=1000, description="Log buffer queue size")
    artifact_scan_interval: int = Field(default=5, description="Seconds between artifact scans")
    cleanup_interval_minutes: int = Field(default=60, description="Minutes between cleanup tasks")

    # Security
    enable_rate_limiting: bool = Field(default=False, description="Enable simple rate limiting")
    max_requests_per_minute: int = Field(default=60, description="Requests per minute per client")
    require_authentication: bool = Field(default=False, description="Require JWT auth for endpoints")

    # Monitoring
    enable_metrics: bool = Field(default=True, description="Enable internal metrics collection")
    health_check_interval: int = Field(default=30, description="Seconds between health checks")

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, v: str) -> str:
        """Normalize log level to uppercase for logging compatibility."""
        return v.upper()

    @classmethod
    def from_env(cls) -> "Config":
        """Create config from environment variables and .env files."""
        return cls()


class ProductionConfig(Config):
    """Production tuned defaults.

    Inherits from Config but sets conservative defaults suitable for
    production deployments.
    """

    max_concurrent_runs: int = 3
    tool_timeout_seconds: int = 300
    max_artifact_size_mb: int = 100
    artifact_retention_days: int = 7

    log_buffer_size: int = 1000
    artifact_scan_interval: int = 5
    cleanup_interval_minutes: int = 60

    enable_rate_limiting: bool = True
    max_requests_per_minute: int = 60
    require_authentication: bool = False

    enable_metrics: bool = True
    health_check_interval: int = 30
