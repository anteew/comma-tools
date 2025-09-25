import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from comma_tools.analyzers.cruise_control_analyzer import CruiseControlAnalyzer  # noqa: E402
from comma_tools.analyzers.marker_detection import MarkerConfig  # noqa: E402


@pytest.mark.integration
def test_parse_and_report_with_default_options(real_log_path, capsys, integration_env):
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
def test_marker_window_pipeline_on_real_log(real_log_path, integration_env):
    analyzer = CruiseControlAnalyzer(
        str(real_log_path), marker_config=MarkerConfig(marker_type="blinkers")
    )
    assert analyzer.parse_log_file() is True
    windows = analyzer.marker_detector.detect_marker_windows()
    assert isinstance(windows, list)
    if windows:
        out = analyzer.marker_detector.analyze_marker_windows(
            analyzer.all_can_data, analyzer.address_labels, analyzer.compute_bit_change_stats
        )
        assert isinstance(out, list)
