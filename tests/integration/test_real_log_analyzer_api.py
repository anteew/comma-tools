import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from comma_tools.analyzers.cruise_control_analyzer import (  # noqa: E402
    CruiseControlAnalyzer,
    MarkerConfig,
)


@pytest.mark.integration
def test_parse_and_report_with_default_options(real_log_path, capsys):
    analyzer = CruiseControlAnalyzer(str(real_log_path))
    assert analyzer.parse_log_file() is True
    analyzer.generate_report()
    out = capsys.readouterr().out
    assert "SUBARU CRUISE CONTROL ANALYSIS REPORT" in out
    assert "CAN messages" in out or "Analyzing Subaru cruise control signals" in out

    if analyzer.speed_data:
        speeds = [d["speed_mph"] for d in analyzer.speed_data]
        assert min(speeds) >= 0
        assert max(speeds) <= 130


@pytest.mark.integration
def test_marker_window_pipeline_on_real_log(real_log_path):
    analyzer = CruiseControlAnalyzer(str(real_log_path), marker_config=MarkerConfig(marker_type="blinkers"))
    assert analyzer.parse_log_file() is True
    windows = analyzer.detect_marker_windows()
    assert isinstance(windows, list)
    if windows:
        analyzer.marker_windows = windows
        out = analyzer.analyze_marker_windows()
        assert isinstance(out, list)
