"""
OpenPilot environment setup utilities.

This module provides common functions for setting up the OpenPilot environment,
managing dependencies, and preparing the Python path for OpenPilot tools.
"""

import importlib
import importlib.util
import os
import subprocess
import sys
import types
from pathlib import Path
from typing import List, Optional, Tuple


def find_repo_root(explicit: Optional[str] = None) -> Path:
    """Locate the root directory that contains the openpilot checkout."""
    candidates: List[Path] = []
    if explicit:
        candidates.append(Path(explicit).expanduser())

    script_path = Path(__file__).resolve()
    candidates.extend(script_path.parents)
    candidates.append(Path.cwd())

    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if (candidate / "openpilot").exists():
            return candidate

    raise FileNotFoundError(
        "Could not find the openpilot checkout.\n\n"
        "Expected directory structure:\n"
        "  parent-directory/\n"
        "  ├── openpilot/          # Clone from https://github.com/commaai/openpilot\n"
        "  └── comma-tools/        # This repository\n\n"
        "To fix this:\n"
        "1. Clone openpilot: git clone https://github.com/commaai/openpilot.git\n"
        "2. Ensure both repositories are in the same parent directory\n"
        "3. Or use --repo-root to specify the parent directory path\n\n"
        "Example: cruise-control-analyzer logfile.zst --repo-root /path/to/parent-directory"
    )


def resolve_deps_dir(repo_root: Path, override: Optional[str]) -> Path:
    """Resolve the directory for storing Python dependencies."""
    if override:
        deps_dir = Path(override).expanduser()
        if not deps_dir.is_absolute():
            deps_dir = repo_root / deps_dir
    else:
        deps_dir = repo_root / "comma-depends"
    return deps_dir


def prepare_environment(repo_root: Path, deps_dir: Path) -> None:
    """Prepare the Python environment for OpenPilot tools."""
    openpilot_path = repo_root / "openpilot"
    if not openpilot_path.exists():
        raise FileNotFoundError(
            f"openpilot checkout not found under {repo_root}\n\n"
            f"Expected to find: {openpilot_path}\n\n"
            "To fix this:\n"
            "1. Clone openpilot: git clone https://github.com/commaai/openpilot.git\n"
            "2. Ensure the openpilot directory is in the correct location\n"
            "3. Or use --repo-root to specify the correct parent directory"
        )

    deps_dir.mkdir(parents=True, exist_ok=True)

    for path in (deps_dir, repo_root / "openpilot"):
        path_str = str(path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)


def ensure_python_packages(
    requirements: List[Tuple[str, str]], deps_dir: Path, install_missing: bool
) -> None:
    """Ensure required Python packages are available."""
    missing = [
        (module, package)
        for module, package in requirements
        if importlib.util.find_spec(module) is None
    ]

    if missing and install_missing:
        print(f"Installing {len(missing)} missing packages to {deps_dir}...")
        for i, (module, package) in enumerate(missing, 1):
            print(f"  [{i}/{len(missing)}] Installing {package}...", end=" ", flush=True)
            cmd = [sys.executable, "-m", "pip", "install", "--target", str(deps_dir), package]
            try:
                subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                print("✓")
            except subprocess.CalledProcessError as exc:
                print("✗")
                stderr_output = exc.stderr.decode() if exc.stderr else "No error details"
                raise RuntimeError(
                    f"Failed to install {package}:\n{stderr_output}\n\n"
                    "This might be due to:\n"
                    "- Network connectivity issues\n"
                    "- Missing system dependencies\n"
                    "- Python version compatibility\n\n"
                    "Try installing manually: pip install " + " ".join(pkg for _, pkg in missing)
                ) from exc

        missing = [
            (module, package)
            for module, package in missing
            if importlib.util.find_spec(module) is None
        ]

    if missing:
        missing_desc = ", ".join(f"{module} (pip: {package})" for module, package in missing)
        raise ImportError(
            f"Missing Python packages: {missing_desc}\n\n"
            "To fix this:\n"
            "1. Install automatically: rerun with --install-missing-deps\n"
            "2. Install manually: pip install " + " ".join(pkg for _, pkg in missing) + "\n"
            "3. Use virtual environment if needed: python -m venv venv && source venv/bin/activate\n\n"
            "Note: Some packages may require system dependencies (e.g., build tools, headers)"
        )


def ensure_cloudlog_stub():
    """Create a stub for openpilot's cloudlog module to avoid import errors."""
    import sys as _sys

    if "openpilot.common.swaglog" in _sys.modules:
        return

    stub_module = types.ModuleType("openpilot.common.swaglog")

    class _StubLogger:
        def __getattr__(self, _name):
            def _log(*_args, **_kwargs):
                pass

            return _log

    stub_module.cloudlog = _StubLogger()
    _sys.modules["openpilot.common.swaglog"] = stub_module


def load_external_modules():
    """Load external modules required for OpenPilot analysis."""
    ensure_cloudlog_stub()

    try:
        import numpy as np
        import matplotlib.pyplot as plt
        from tools.lib.logreader import LogReader

        return {
            "np": np,
            "plt": plt,
            "LogReader": LogReader,
            "messaging": None,  # Not used in current implementation
        }
    except ImportError as e:
        raise ImportError(
            f"Failed to load required modules: {e}\n\n"
            "Make sure OpenPilot is properly set up and accessible."
        ) from e


def add_openpilot_to_path(repo_root: Optional[str] = None):
    """Add OpenPilot to Python path (alternative approach used by rlog_to_csv)."""
    if repo_root:
        repo_path = Path(repo_root).expanduser()
        openpilot_path = repo_path / "openpilot"
        if not openpilot_path.exists():
            openpilot_path = Path(repo_root).expanduser()
        sys.path.insert(0, str(openpilot_path / "tools"))
        sys.path.insert(0, str(openpilot_path))
    else:
        try:
            repo_root_path = find_repo_root()
            openpilot_path = repo_root_path / "openpilot"
            sys.path.insert(0, str(openpilot_path / "tools"))
            sys.path.insert(0, str(openpilot_path))
        except FileNotFoundError:
            script_path = Path(__file__).resolve()
            cand = script_path.parent.parent.parent.parent / "openpilot"
            if cand.exists():
                sys.path.insert(0, str(cand / "tools"))
                sys.path.insert(0, str(cand))
