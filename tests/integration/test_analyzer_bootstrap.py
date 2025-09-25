"""Integration tests for cruise control analyzer bootstrap functionality."""

import shutil
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from comma_tools.utils import (
    ensure_python_packages,
    find_repo_root,
    prepare_environment,
    resolve_deps_dir,
)


class TestAnalyzerBootstrap:
    """Integration tests for analyzer environment bootstrap."""

    def test_find_repo_root_with_openpilot(self):
        """Test finding repo root when openpilot directory exists."""
        try:
            repo_root = find_repo_root()
            assert repo_root.exists()
            assert (repo_root / "openpilot").exists()
        except FileNotFoundError:
            pytest.skip("openpilot directory not found - expected in CI environment")

    def test_resolve_deps_dir_default(self):
        """Test resolving dependencies directory with default path."""
        repo_root = Path("/tmp/test_repo")
        deps_dir = resolve_deps_dir(repo_root, None)
        assert deps_dir == repo_root / "comma-depends"

    def test_resolve_deps_dir_override(self):
        """Test resolving dependencies directory with override."""
        repo_root = Path("/tmp/test_repo")
        deps_dir = resolve_deps_dir(repo_root, "custom-deps")
        assert deps_dir == repo_root / "custom-deps"

    def test_prepare_environment_missing_openpilot(self):
        """Test prepare_environment raises error when openpilot is missing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            deps_dir = repo_root / "deps"

            with pytest.raises(FileNotFoundError, match="openpilot checkout not found"):
                prepare_environment(repo_root, deps_dir)

    def test_prepare_environment_success(self):
        """Test prepare_environment succeeds when openpilot exists."""
        try:
            repo_root = find_repo_root()
            deps_dir = repo_root / "test-deps"

            if deps_dir.exists():
                shutil.rmtree(deps_dir)

            prepare_environment(repo_root, deps_dir)

            assert deps_dir.exists()

            assert str(deps_dir) in sys.path
            assert str(repo_root / "openpilot") in sys.path

            shutil.rmtree(deps_dir)

        except FileNotFoundError:
            pytest.skip("openpilot directory not found - expected in CI environment")

    def test_ensure_python_packages_no_install(self):
        """Test package checking without installation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            deps_dir = Path(temp_dir)

            requirements = [("sys", "sys")]

            ensure_python_packages(requirements, deps_dir, install_missing=False)

    def test_ensure_python_packages_missing_no_install(self):
        """Test package checking with missing packages and no install."""
        with tempfile.TemporaryDirectory() as temp_dir:
            deps_dir = Path(temp_dir)

            requirements = [("nonexistent_package_12345", "nonexistent_package_12345")]

            with pytest.raises(ImportError, match="Missing Python packages"):
                ensure_python_packages(requirements, deps_dir, install_missing=False)


class TestAnalyzerStubbing:
    """Test the openpilot stubbing functionality."""

    def test_cloudlog_stub_import(self):
        """Test that cloudlog stub can be imported."""
        from comma_tools.utils import ensure_cloudlog_stub

        ensure_cloudlog_stub()

        assert "openpilot.common.swaglog" in sys.modules

        stub_module = sys.modules["openpilot.common.swaglog"]
        assert hasattr(stub_module, "cloudlog")

        logger = stub_module.cloudlog
        logger.info("test message")  # Should not raise
        logger.warning("test warning")  # Should not raise
