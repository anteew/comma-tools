"""
Configuration management for CTS CLI client.

Handles loading configuration from files, environment variables,
and command-line arguments with proper defaults and validation.
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib  # type: ignore
    except ImportError:
        tomllib = None  # type: ignore


class Config:
    """Configuration manager for CTS CLI client."""

    def __init__(
        self,
        url: Optional[str] = None,
        api_key: Optional[str] = None,
        out_dir: Optional[str] = None,
        timeout: int = 30,
        no_verify: bool = False,
    ):
        """Initialize configuration with optional overrides."""
        self.url = url or self._get_url()
        self.api_key = api_key or self._get_api_key()
        self.out_dir = Path(out_dir or self._get_out_dir())
        self.timeout = timeout
        self.no_verify = no_verify

    def _get_url(self) -> str:
        """Get base URL from environment or config file."""
        if url := os.getenv("CTS_URL"):
            return url

        config_data = self._load_config_file()
        if config_data and "url" in config_data:
            return config_data["url"]

        return "http://127.0.0.1:8080"

    def _get_api_key(self) -> Optional[str]:
        """Get API key from environment or config file."""
        if api_key := os.getenv("CTS_API_KEY"):
            return api_key

        config_data = self._load_config_file()
        if config_data and "api_key" in config_data:
            return config_data["api_key"]

        return None

    def _get_out_dir(self) -> str:
        """Get output directory from config file or default."""
        config_data = self._load_config_file()
        if config_data and "out_dir" in config_data:
            return os.path.expanduser(config_data["out_dir"])

        return os.path.expanduser("~/Downloads/cts")

    def _load_config_file(self) -> Optional[Dict[str, Any]]:
        """Load configuration from TOML file."""
        if tomllib is None:
            return None

        config_dir = os.getenv("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
        config_path = Path(config_dir) / "cts" / "config.toml"

        if not config_path.exists():
            return None

        try:
            with open(config_path, "rb") as f:
                return tomllib.load(f)
        except Exception:
            return None

    def ensure_out_dir(self) -> None:
        """Ensure output directory exists."""
        self.out_dir.mkdir(parents=True, exist_ok=True)
