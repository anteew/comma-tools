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
        """Load configuration from file.

        Args:
            config_file: Path to configuration file (JSON or TOML)

        Returns:
            Dictionary of configuration overrides

        Raises:
            ValueError: If file cannot be parsed or has invalid format
        """
        import json

        config_path = Path(config_file)
        self._config_file_path = str(config_path)

        if not config_path.exists():
            return {}

        try:
            with open(config_path, "r") as f:
                if config_path.suffix.lower() == ".json":
                    return json.load(f)
                elif config_path.suffix.lower() == ".toml":
                    try:
                        import tomllib
                    except ImportError:
                        try:
                            import tomli as tomllib
                        except ImportError:
                            raise ValueError("TOML support requires Python 3.11+ or tomli package")

                    with open(config_path, "rb") as toml_file:
                        return tomllib.load(toml_file)
                else:
                    # Try JSON first, then TOML
                    content = f.read()
                    try:
                        return json.loads(content)
                    except json.JSONDecodeError:
                        try:
                            import tomllib

                            return tomllib.loads(content)
                        except ImportError:
                            raise ValueError(
                                f"Unsupported config file format: {config_path.suffix}"
                            )
                        except Exception:
                            raise ValueError(
                                f"Could not parse config file as JSON or TOML: {config_file}"
                            )

        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in config file {config_file}: {e}")
        except Exception as e:
            raise ValueError(f"Error reading config file {config_file}: {e}")

    def _load_from_environment(self) -> Dict[str, Any]:
        """Load configuration overrides from environment variables.

        Collects all CTS_* environment variables (excluding CTS_ENVIRONMENT,
        which is reserved for selecting the deployment environment) and
        coerces them to ProductionConfig field types.

        Returns:
            Dictionary of configuration overrides from environment
        """
        env_overrides = {}

        # Get all environment variables with CTS_ prefix
        for key, value in os.environ.items():
            if key.startswith("CTS_") and key != "CTS_ENVIRONMENT":
                # Convert CTS_* to lowercase field names
                field_name = key[4:].lower()  # Remove "CTS_" prefix

                # Skip if this isn't a known ProductionConfig field
                if field_name not in ProductionConfig.model_fields:
                    continue

                # Get the field type from ProductionConfig
                try:
                    field_info = ProductionConfig.model_fields[field_name]
                    field_type = field_info.annotation

                    # Coerce the string value to the appropriate type
                    if field_type == bool or str(field_type) == "<class 'bool'>":
                        # Handle various boolean representations
                        env_overrides[field_name] = value.lower() in ("true", "1", "yes", "on")
                    elif field_type == int or str(field_type) == "<class 'int'>":
                        env_overrides[field_name] = int(value)
                    elif field_type == float or str(field_type) == "<class 'float'>":
                        env_overrides[field_name] = float(value)
                    elif hasattr(field_type, "__origin__") and field_type.__origin__ is list:
                        # Handle list types (like cors_allowed_origins)
                        env_overrides[field_name] = [item.strip() for item in value.split(",")]
                    else:
                        # Default to string
                        env_overrides[field_name] = value

                except (ValueError, TypeError, AttributeError) as e:
                    # Skip invalid values but don't fail completely
                    continue

        return env_overrides

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
