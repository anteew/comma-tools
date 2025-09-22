import os
from pathlib import Path
import pytest


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
