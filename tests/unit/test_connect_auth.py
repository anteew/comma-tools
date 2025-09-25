"""
Unit tests for comma connect authentication.
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from comma_tools.sources.connect.auth import load_auth, redact_token


class TestLoadAuth:
    """Test authentication loading functionality."""

    def test_load_auth_from_env_var(self):
        """Test loading JWT from environment variable."""
        test_token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.test.token"

        with patch.dict(os.environ, {"COMMA_JWT": test_token}):
            token = load_auth()
            assert token == test_token

    def test_load_auth_from_file(self):
        """Test loading JWT from auth file."""
        test_token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.test.token"
        auth_data = {"access_token": test_token}

        with tempfile.TemporaryDirectory() as temp_dir:
            comma_dir = Path(temp_dir) / ".comma"
            comma_dir.mkdir()
            auth_file = comma_dir / "auth.json"
            with open(auth_file, "w") as f:
                json.dump(auth_data, f)

            with patch.dict(os.environ, {}, clear=True):
                if "COMMA_JWT" in os.environ:
                    del os.environ["COMMA_JWT"]

                with patch("comma_tools.sources.connect.auth.Path.home") as mock_home:
                    mock_home.return_value = Path(temp_dir)
                    token = load_auth()
                    assert token == test_token

    def test_load_auth_missing_raises_error(self):
        """Test that missing auth raises appropriate error."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("comma_tools.sources.connect.auth.Path.home") as mock_home:
                mock_home.return_value = Path("/nonexistent")

                with pytest.raises(FileNotFoundError) as exc_info:
                    load_auth()

                assert "No comma JWT found" in str(exc_info.value)
                assert "openpilot/tools/lib/auth.py" in str(exc_info.value)


class TestRedactToken:
    """Test token redaction functionality."""

    def test_redact_token_normal(self):
        """Test normal token redaction."""
        token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.test.token"
        redacted = redact_token(token)
        assert redacted.startswith("eyJ0")
        assert redacted.endswith("oken")
        assert "..." in redacted
        assert len(redacted) < len(token)

    def test_redact_token_short(self):
        """Test redaction of short tokens."""
        token = "short"
        redacted = redact_token(token)
        assert redacted == "*****"
        assert len(redacted) == len(token)

    def test_redact_token_custom_chars(self):
        """Test redaction with custom character count."""
        token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.test.token"
        redacted = redact_token(token, show_chars=2)
        assert redacted.startswith("ey")
        assert redacted.endswith("en")
        assert "..." in redacted
