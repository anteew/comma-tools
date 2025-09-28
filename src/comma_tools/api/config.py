"""Service configuration management for CTS-Lite API."""

import inspect
import json
import os
import types
from enum import Enum
from pathlib import Path
from typing import Annotated, Any, Dict, List, Optional, Union, get_args, get_origin

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
        """Load configuration overrides from JSON or TOML files.

        Args:
            config_file: Path to the configuration file provided by the user.

        Returns:
            Parsed key/value pairs that should override the base configuration.

        Raises:
            ValueError: If the file contents cannot be parsed as JSON or TOML.
        """

        config_path = Path(config_file)
        self._config_file_path = str(config_path)

        if not config_path.exists():
            return {}

        try:
            with open(config_path, "r", encoding="utf-8") as handle:
                if config_path.suffix.lower() == ".json":
                    return json.load(handle)

                if config_path.suffix.lower() == ".toml":
                    content = handle.read()
                    return self._parse_toml_content(content, config_file)

                content = handle.read()
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    return self._parse_toml_content(content, config_file)

        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in config file {config_file}: {exc}") from exc
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError(f"Error reading config file {config_file}: {exc}") from exc

        return {}

    def _parse_toml_content(self, content: str, config_file: str) -> Dict[str, Any]:
        """Parse TOML configuration content with appropriate fallbacks.

        Args:
            content: Raw contents read from the candidate TOML file.
            config_file: Path to the file currently being parsed, for messaging.

        Returns:
            Dictionary representation of the TOML document.

        Raises:
            ValueError: If TOML parsing fails or support libraries are unavailable.
        """

        try:
            import tomllib

            return tomllib.loads(content)
        except ModuleNotFoundError:
            pass
        except Exception as exc:
            raise ValueError(f"Invalid TOML in config file {config_file}: {exc}") from exc

        try:
            import tomli

            return tomli.loads(content)
        except ModuleNotFoundError as exc:
            raise ValueError("TOML support requires Python 3.11+ or installing 'tomli'.") from exc
        except Exception as exc:
            raise ValueError(f"Invalid TOML in config file {config_file}: {exc}") from exc

    def _load_from_environment(self) -> Dict[str, Any]:
        """Load configuration overrides from environment variables.

        Returns:
            Mapping of configuration field names to coerced values discovered in
            the process environment. Supports both comma-separated and JSON
            array formats for list fields.
        """

        env_overrides: Dict[str, Any] = {}

        for key, value in os.environ.items():
            if not key.startswith("CTS_") or key == "CTS_ENVIRONMENT":
                continue

            field_name = key[4:].lower()
            if field_name not in ProductionConfig.model_fields:
                continue

            field_info = ProductionConfig.model_fields[field_name]
            try:
                env_overrides[field_name] = self._coerce_env_value(value, field_info.annotation)
            except (ValueError, TypeError):
                continue

        return env_overrides

    @staticmethod
    def _coerce_env_value(raw_value: str, field_type: Any, _depth: int = 0) -> Any:
        """Coerce an environment variable string into the provided field type.

        Args:
            raw_value: Raw string obtained from the environment variable.
            field_type: Target Python type extracted from the Pydantic model.
            _depth: Internal recursion depth counter to prevent infinite recursion.

        Returns:
            The raw value converted into the requested type.

        Raises:
            ValueError: If the conversion to the requested Enum or numeric type
                fails, or if recursion depth is exceeded.
            TypeError: If the target type is not compatible with the raw value.
        """
        # Prevent infinite recursion by limiting depth
        if _depth > 10:  # Allow reasonable nesting but prevent infinite recursion
            raise ValueError(f"Type coercion recursion depth exceeded: {field_type}")

        target_type = ConfigManager._unwrap_type(field_type)
        value = raw_value.strip()

        origin = get_origin(target_type)
        if origin in (list, List):
            item_type = get_args(target_type)[0] if get_args(target_type) else str
            return ConfigManager._parse_list_value(value, item_type, _depth + 1)

        if inspect.isclass(target_type):
            if issubclass(target_type, bool):
                return value.lower() in {"true", "1", "yes", "on"}
            if issubclass(target_type, int) and not issubclass(target_type, bool):
                return int(value)
            if issubclass(target_type, float):
                return float(value)
            if issubclass(target_type, Enum):
                return target_type(value)

        return value

    @staticmethod
    def _parse_list_value(raw_value: str, item_type: Any, _depth: int = 0) -> List[Any]:
        """Parse list values from either JSON arrays or comma-separated strings.

        Args:
            raw_value: The environment-provided raw string representation.
            item_type: Type expected for each item in the resulting list.
            _depth: Internal recursion depth counter to prevent infinite recursion.

        Returns:
            List populated with items converted to the requested type.

        Raises:
            ValueError: If recursion depth is exceeded.
        """
        # Prevent infinite recursion by limiting depth
        if _depth > 10:  # Allow reasonable nesting but prevent infinite recursion
            raise ValueError(f"List parsing recursion depth exceeded: {item_type}")

        values: Optional[List[Any]] = None
        try:
            parsed = json.loads(raw_value)
            if isinstance(parsed, list):
                values = parsed
        except json.JSONDecodeError:
            values = None

        if values is None:
            values = [item.strip() for item in raw_value.split(",") if item.strip()]

        coerced: List[Any] = []
        for item in values:
            # Check if the item is already the correct type for list items
            from typing import get_origin, get_args

            if get_origin(item_type) in (list, List) and isinstance(item, list):
                # Item is already a list and we expect a list type - recursively coerce the list
                inner_item_type = get_args(item_type)[0] if get_args(item_type) else str
                coerced_inner = []
                for inner_item in item:
                    inner_value = inner_item if isinstance(inner_item, str) else str(inner_item)
                    coerced_inner.append(
                        ConfigManager._coerce_env_value(inner_value, inner_item_type, _depth)
                    )
                coerced.append(coerced_inner)
            else:
                # Normal case - convert to string and coerce
                item_value = item if isinstance(item, str) else str(item)
                coerced.append(ConfigManager._coerce_env_value(item_value, item_type, _depth))

        return coerced

    @staticmethod
    def _unwrap_type(field_type: Any) -> Any:
        """Unwrap typing constructs (Annotated/Union/Optional) to base type.

        Args:
            field_type: Possibly wrapped type annotation from the model field.

        Returns:
            Simplified type suitable for runtime inspection and conversions.
        """

        origin = get_origin(field_type)
        if origin is Annotated:
            return ConfigManager._unwrap_type(get_args(field_type)[0])

        if origin in {Union, types.UnionType}:
            args = [arg for arg in get_args(field_type) if arg is not type(None)]
            if len(args) == 1:
                return ConfigManager._unwrap_type(args[0])

        return field_type

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
