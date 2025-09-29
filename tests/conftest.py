import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from comma_tools.utils import (
    ensure_python_packages,
    find_repo_root,
    load_external_modules,
    prepare_environment,
    resolve_deps_dir,
)


def pytest_addoption(parser):
    parser.addoption(
        "--real-log-file",
        action="store",
        default=None,
        help="Path to a real rlog.zst file for integration tests",
    )


@pytest.fixture(scope="session")
def real_log_path(pytestconfig):
    cli = pytestconfig.getoption("--real-log-file")
    env = os.getenv("LOG_FILE")
    value = cli or env
    if not value:
        fixture = Path(__file__).parent / "data" / "known_good.rlog.zst"
        if fixture.exists():
            return fixture
        pytest.skip("No real log supplied; set env LOG_FILE or pass --real-log-file=PATH")
    p = Path(value).expanduser()
    if not p.exists():
        pytest.skip(f"Real log not found at: {p}")
    return p


@pytest.fixture(scope="session")
def integration_env():
    repo_root = find_repo_root(None)
    deps_dir = resolve_deps_dir(repo_root, None)
    prepare_environment(repo_root, deps_dir)
    try:
        ensure_python_packages(
            [
                ("matplotlib", "matplotlib"),
                ("numpy", "numpy"),
                ("capnp", "pycapnp"),
                ("tqdm", "tqdm"),
                ("zstandard", "zstandard"),
                ("zmq", "pyzmq"),
                ("smbus2", "smbus2"),
                ("urllib3", "urllib3"),
                ("requests", "requests"),
            ],
            deps_dir,
            True,
        )
    except Exception:
        pass

    # cruise_control_analyzer has been deprecated and removed
    # Dependencies are now handled within individual analyzer services
    modules = load_external_modules()
    return True
