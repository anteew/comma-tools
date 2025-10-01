"""Configuration management for phone-a-friend MCP server."""

import os
from pathlib import Path
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class PhoneAFriendConfig(BaseSettings):
    """Configuration for phone-a-friend MCP server."""

    model_config = SettingsConfigDict(
        env_prefix="PAF_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    openai_api_key: Optional[str] = Field(
        default=None,
        description="OpenAI API key. Can be set via PAF_OPENAI_API_KEY or OPENAI_API_KEY environment variable.",
    )

    openai_api_key_path: Path = Field(
        default=Path.home() / ".config" / "comma-tools" / "openai.key",
        description="Path to file containing OpenAI API key",
    )

    model_name: str = Field(
        default="gpt-4o", description="OpenAI model to use (e.g., gpt-4o, gpt-4-turbo, o1-preview)"
    )

    max_concurrent_sessions: int = Field(
        default=5, description="Maximum number of concurrent GPT-5 sessions"
    )

    max_requests_per_minute: int = Field(default=60, description="Maximum API requests per minute")

    max_tokens_per_request: int = Field(default=4096, description="Maximum tokens per API request")

    session_timeout_seconds: int = Field(
        default=1800, description="Session idle timeout in seconds"  # 30 minutes
    )

    session_retention_days: int = Field(
        default=30, description="Number of days to retain session transcripts"
    )

    cost_limit_per_session: float = Field(
        default=5.0, description="Maximum cost per session in USD"
    )

    cost_limit_per_day: float = Field(default=50.0, description="Maximum total cost per day in USD")

    def get_api_key(self) -> str:
        """
        Get OpenAI API key from environment or file.

        Returns:
            API key string

        Raises:
            ValueError: If API key cannot be found
        """
        if self.openai_api_key:
            return self.openai_api_key

        if key := os.getenv("OPENAI_API_KEY"):
            return key

        if self.openai_api_key_path.exists():
            try:
                key = self.openai_api_key_path.read_text().strip()
                if key:
                    return key
            except Exception as e:
                raise ValueError(f"Failed to read API key from {self.openai_api_key_path}: {e}")

        raise ValueError(
            "OpenAI API key not found. Set PAF_OPENAI_API_KEY or OPENAI_API_KEY environment variable, "
            f"or create key file at {self.openai_api_key_path} with 0600 permissions"
        )


def load_config() -> PhoneAFriendConfig:
    """Load configuration from environment and files."""
    return PhoneAFriendConfig()
