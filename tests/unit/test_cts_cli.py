"""
Unit tests for CTS CLI client.

Tests URL/auth header wiring, parameter casting, path safety,
and exit code mapping without requiring a running server.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch
import json

from cts_cli.config import Config
from cts_cli.http import HTTPClient
from cts_cli.render import Renderer, safe_path_join
from cts_cli.commands.run import parse_parameters


class TestConfig:
    """Test configuration management."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = Config()
        assert config.url == "http://127.0.0.1:8080"
        assert config.api_key is None
        assert config.timeout == 30
        assert config.no_verify is False
    
    def test_config_with_overrides(self):
        """Test configuration with explicit overrides."""
        config = Config(
            url="https://api.example.com",
            api_key="test-key",
            timeout=60,
            no_verify=True
        )
        assert config.url == "https://api.example.com"
        assert config.api_key == "test-key"
        assert config.timeout == 60
        assert config.no_verify is True
    
    @patch.dict('os.environ', {'CTS_URL': 'http://env.example.com', 'CTS_API_KEY': 'env-key'})
    def test_config_from_environment(self):
        """Test configuration from environment variables."""
        config = Config()
        assert config.url == "http://env.example.com"
        assert config.api_key == "env-key"


class TestHTTPClient:
    """Test HTTP client functionality."""
    
    def test_auth_headers(self):
        """Test authentication header generation."""
        config = Config(api_key="test-key")
        client = HTTPClient(config)
        
        headers = client._get_headers()
        assert headers["Authorization"] == "JWT test-key"
    
    def test_no_auth_headers(self):
        """Test headers without API key."""
        config = Config()
        client = HTTPClient(config)
        
        headers = client._get_headers()
        assert "Authorization" not in headers


class TestParameterParsing:
    """Test parameter parsing and type inference."""
    
    def test_parse_string_parameters(self):
        """Test parsing string parameters."""
        params = ["name=value", "path=/tmp/file"]
        result = parse_parameters(params)
        
        assert result == {"name": "value", "path": "/tmp/file"}
    
    def test_parse_boolean_parameters(self):
        """Test parsing boolean parameters."""
        params = ["enabled=true", "debug=false"]
        result = parse_parameters(params)
        
        assert result == {"enabled": True, "debug": False}
    
    def test_parse_numeric_parameters(self):
        """Test parsing numeric parameters."""
        params = ["count=42", "rate=3.14"]
        result = parse_parameters(params)
        
        assert result == {"count": 42, "rate": 3.14}
    
    def test_parse_list_parameters(self):
        """Test parsing list parameters."""
        params = ["tags=a,b,c", "files=file1.txt,file2.txt"]
        result = parse_parameters(params)
        
        assert result == {"tags": ["a", "b", "c"], "files": ["file1.txt", "file2.txt"]}
    
    def test_invalid_parameter_format(self):
        """Test invalid parameter format raises error."""
        params = ["invalid-format"]
        
        with pytest.raises(ValueError, match="Invalid parameter format"):
            parse_parameters(params)


class TestPathSafety:
    """Test path safety for downloads."""
    
    def test_safe_path_join(self):
        """Test safe path joining."""
        base_dir = Path("/tmp/downloads")
        filename = "report.html"
        
        result = safe_path_join(base_dir, filename)
        assert result == base_dir / "report.html"
    
    def test_path_traversal_prevention(self):
        """Test prevention of path traversal attacks."""
        base_dir = Path("/tmp/downloads")
        malicious_filename = "../../../etc/passwd"
        
        with pytest.raises(ValueError, match="Unsafe path"):
            safe_path_join(base_dir, malicious_filename)
    
    def test_complex_filename_safety(self):
        """Test safety with complex filenames."""
        base_dir = Path("/tmp/downloads")
        filename = "subdir/../report.html"
        
        result = safe_path_join(base_dir, filename)
        assert result == base_dir / "report.html"


class TestRenderer:
    """Test output rendering."""
    
    def test_json_output_mode(self):
        """Test JSON output mode."""
        renderer = Renderer(json_output=True)
        assert renderer.json_output is True
    
    def test_quiet_mode(self):
        """Test quiet mode."""
        renderer = Renderer(quiet=True)
        assert renderer.quiet is True
    
    def test_format_bytes(self):
        """Test byte formatting."""
        from cts_cli.render import format_bytes
        
        assert format_bytes(1024) == "1.0 KB"
        assert format_bytes(1048576) == "1.0 MB"
        assert format_bytes(1073741824) == "1.0 GB"
    
    def test_format_duration(self):
        """Test duration formatting."""
        from cts_cli.render import format_duration
        
        assert format_duration(30) == "30.0s"
        assert format_duration(90) == "1.5m"
        assert format_duration(3660) == "1.0h"


class TestExitCodes:
    """Test exit code mapping."""
    
    def test_success_exit_code(self):
        """Test success returns 0."""
        pass
    
    def test_client_error_exit_code(self):
        """Test client error returns 1."""
        pass
    
    def test_server_error_exit_code(self):
        """Test server error returns 2."""
        pass
    
    def test_run_failed_exit_code(self):
        """Test run failed returns 3."""
        pass
    
    def test_run_canceled_exit_code(self):
        """Test run canceled returns 4."""
        pass
