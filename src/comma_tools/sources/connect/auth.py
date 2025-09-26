"""
Authentication provider for comma API.

Handles JWT token discovery from environment variables or auth files.
"""

import json
import os
from pathlib import Path
from typing import Optional


def load_auth() -> str:
    """
    Load comma API JWT token from environment or auth file.

    Lookup order:
    1. COMMA_JWT environment variable
    2. ~/.comma/auth.json file

    Returns:
        JWT token string

    Raises:
        FileNotFoundError: If no authentication is found
    """
    jwt_token = os.getenv("COMMA_JWT")
    if jwt_token:
        return jwt_token.strip()

    auth_file = Path.home() / ".comma" / "auth.json"
    if auth_file.exists():
        try:
            with open(auth_file, "r") as f:
                auth_data = json.load(f)
                if "access_token" in auth_data:
                    return auth_data["access_token"].strip()
        except (json.JSONDecodeError, KeyError, IOError):
            pass

    raise FileNotFoundError(
        "No comma JWT found. Set COMMA_JWT environment variable or run "
        "openpilot/tools/lib/auth.py to create ~/.comma/auth.json"
    )


def try_load_auth() -> Optional[str]:
    """
    Try to load comma API JWT token, returning None if not found.

    This is useful for attempting public access before requiring authentication.

    Returns:
        JWT token string if found, None otherwise
    """
    try:
        return load_auth()
    except FileNotFoundError:
        return None


def redact_token(token: str, show_chars: int = 4) -> str:
    """
    Redact JWT token for safe logging.

    Args:
        token: JWT token to redact
        show_chars: Number of characters to show at start/end

    Returns:
        Redacted token string
    """
    if len(token) <= show_chars * 2:
        return "*" * len(token)

    return f"{token[:show_chars]}...{token[-show_chars:]}"
