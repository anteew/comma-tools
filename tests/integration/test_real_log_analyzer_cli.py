import os
import sys
import subprocess
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _run(args, cwd=None, env=None):
    proc = subprocess.run(
        [sys.executable, "-m", "comma_tools.analyzers.cruise_control_analyzer"] + args,
        cwd=cwd or REPO_ROOT,
        env=env or os.environ.copy(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return proc


@pytest.mark.integration
def test_cli_default_parse(real_log_path):
    proc = _run([str(real_log_path)])
    assert proc.returncode == 0, f"stderr:\n{proc.stderr}\nstdout:\n{proc.stdout}"
    assert "Parsing log file:" in proc.stdout


@pytest.mark.integration
def test_cli_marker_none(real_log_path):
    proc = _run([str(real_log_path), "--marker-type", "none"])
    assert proc.returncode == 0, proc.stderr


@pytest.mark.integration
def test_cli_marker_blinkers_and_speed_bounds(real_log_path):
    proc = _run(
        [str(real_log_path), "--marker-type", "blinkers", "--speed-min", "40", "--speed-max", "70"]
    )
    assert proc.returncode == 0, proc.stderr


@pytest.mark.integration
def test_cli_custom_deps_dir_without_install(real_log_path, tmp_path):
    deps = tmp_path / "deps"
    proc = _run([str(real_log_path), "--deps-dir", str(deps), "--install-missing-deps"])
    assert proc.returncode == 0, proc.stderr


@pytest.mark.integration
def test_cli_with_repo_root_if_openpilot_present(real_log_path):
    parent = REPO_ROOT.parent
    if not (parent / "openpilot").exists():
        pytest.skip("openpilot directory not found next to repo; skipping --repo-root test")
    proc = _run([str(real_log_path), "--repo-root", str(parent)])
    assert proc.returncode == 0, proc.stderr
