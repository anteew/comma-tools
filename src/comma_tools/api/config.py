"""Service configuration management for CTS-Lite API."""

import os
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Environment(str, Enum):
    """Environment types for configuration management."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


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


class ProductionConfig(BaseSettings):
    """Production-grade configuration with environment support."""

    # Environment Settings
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = False
    log_level: str = "INFO"

    # API Settings (maintaining compatibility)
    host: str = "127.0.0.1"
    port: int = 8080

    # Resource Management
    max_concurrent_runs: int = 3
    tool_timeout_seconds: int = 300  # 5 minutes default
    max_artifact_size_mb: int = 100
    artifact_retention_days: int = 7
    max_log_buffer_size: int = 1000

    # Performance Tuning
    artifact_scan_interval_seconds: int = 5
    cleanup_interval_minutes: int = 60
    health_check_interval_seconds: int = 30

    # Security Settings
    enable_rate_limiting: bool = False  # Start disabled
    max_requests_per_minute: int = 60
    require_authentication: bool = False
    cors_allowed_origins: List[str] = ["*"]  # Restrictive in production

    # Monitoring & Observability
    enable_metrics: bool = True
    enable_health_checks: bool = True
    metrics_export_interval_seconds: int = 60

    # File System Settings
    base_storage_path: str = "/var/lib/cts"
    temp_directory: str = "/tmp/cts"
    log_directory: str = "/var/log/cts"
    storage_dir: str = "/var/lib/cts-lite"  # Backward compatibility

    model_config = {"env_file": ".env", "env_prefix": "CTS_", "case_sensitive": False}

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: Environment) -> Environment:
        """Apply environment-specific validations."""
        if v == Environment.PRODUCTION:
            # Production-specific validations will be handled in get_environment_config
            pass
        return v

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, v: str) -> str:
        """Normalize log level to uppercase for logging compatibility."""
        return v.upper()

    @classmethod
    def get_environment_config(cls, env: Environment) -> "ProductionConfig":
        """Get environment-specific configuration."""
        if env == Environment.PRODUCTION:
            return cls(
                environment=env,
                debug=False,
                log_level="WARNING",
                enable_rate_limiting=True,
                require_authentication=True,
                cors_allowed_origins=["https://yourdomain.com"],
                max_concurrent_runs=5,
            )
        elif env == Environment.STAGING:
            return cls(
                environment=env,
                debug=True,
                log_level="INFO",
                enable_rate_limiting=True,
                max_concurrent_runs=2,
            )
        else:  # Development
            return cls(environment=env, debug=True, log_level="DEBUG", max_concurrent_runs=1)


class ConfigManager:
    """Manages configuration loading and environment detection."""

    def __init__(self):
        self._config: Optional[ProductionConfig] = None
        self._config_file_path: Optional[str] = None

    def load_config(self, config_file: Optional[str] = None) -> ProductionConfig:
        """
        Load configuration from environment and/or config file.

        Args:
            config_file: Optional path to configuration file

        Returns:
            Loaded configuration instance
        """
        # Detect environment
        env_name = os.getenv("CTS_ENVIRONMENT", "development")
        try:
            environment = Environment(env_name)
        except ValueError:
            environment = Environment.DEVELOPMENT

        # Load base config for environment
        config = ProductionConfig.get_environment_config(environment)

        # Override with config file if provided
        if config_file and Path(config_file).exists():
            file_config = self._load_from_file(config_file)
            config = self._merge_configs(config, file_config)

        # Override with environment variables (highest priority)
        env_overrides = self._load_from_environment()
        config = self._merge_configs(config, env_overrides)

        self._config = config
        self._validate_config(config)
        return config

    def _validate_config(self, config: ProductionConfig) -> None:
        """Validate configuration for consistency and requirements."""
        # Ensure directories exist
        for dir_path in [config.base_storage_path, config.temp_directory, config.log_directory]:
            Path(dir_path).mkdir(parents=True, exist_ok=True)

        # Validate resource limits
        if config.max_concurrent_runs < 1:
            raise ValueError("max_concurrent_runs must be at least 1")

        if config.tool_timeout_seconds < 30:
            raise ValueError("tool_timeout_seconds must be at least 30")

        # Production-specific validations
        if config.environment == Environment.PRODUCTION:
            if not config.enable_metrics:
                raise ValueError("Metrics must be enabled in production")

    def _load_from_file(self, config_file: str) -> Dict[str, Any]:
        """Load configuration from file."""
        # For now, return empty dict - can be extended for TOML/YAML support
        return {}

    def _load_from_environment(self) -> Dict[str, Any]:
        """Load configuration overrides from environment variables."""
        # This would collect CTS_* environment variables
        # For now, return empty dict as pydantic handles this
        return {}

    def _merge_configs(self, base: ProductionConfig, overrides: Dict[str, Any]) -> ProductionConfig:
        """Merge configuration overrides into base configuration."""
        if not overrides:
            return base

        # Create new config with overrides - simplified for now
        config_dict = base.model_dump()
        config_dict.update(overrides)
        return ProductionConfig(**config_dict)

    @property
    def config(self) -> Optional[ProductionConfig]:
        """Get the current loaded configuration."""
        return self._config
