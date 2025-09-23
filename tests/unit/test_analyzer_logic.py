import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import comma_tools.analyzers.cruise_control_analyzer as mod  # noqa: E402
from comma_tools.analyzers.cruise_control_analyzer import (  # noqa: E402
    CruiseControlAnalyzer,
    SubaruCANDecoder,
)
from comma_tools.analyzers.event_detection import EventDetector  # noqa: E402


def make_payload_from_bits(bits_on):
    b = bytearray(8)
    for bit in bits_on:
        byte = bit // 8
        off = bit % 8
        if 0 <= byte < 8:
            b[byte] |= 1 << off
    return bytes(b)


def int_to_le_bytes64(val: int) -> bytes:
    return int(val).to_bytes(8, "little", signed=False)


class StubCAN:
    def __init__(self, addr, dat, src=0):
        self.address = addr
        self.dat = dat
        self.src = src


class StubMsg:
    def __init__(self, which_name, entries, t_sec):
        self._which = which_name
        self._entries = entries
        self.logMonoTime = int(t_sec * 1e9)

    def which(self):
        return self._which

    @property
    def can(self):
        return self._entries


def stub_logreader_messages():
    yield StubMsg(
        "can",
        [
            StubCAN(
                SubaruCANDecoder.WHEEL_SPEEDS_ADDR,
                int_to_le_bytes64(
                    ((100 & 0x1FFF) << 12)
                    | ((100 & 0x1FFF) << 25)
                    | ((100 & 0x1FFF) << 38)
                    | ((100 & 0x1FFF) << 51)
                ),
            )
        ],
        0.1,
    )
    yield StubMsg(
        "can",
        [
            StubCAN(SubaruCANDecoder.CRUISE_BUTTONS_ADDR, make_payload_from_bits([])),
        ],
        0.2,
    )
    yield StubMsg(
        "can",
        [
            StubCAN(SubaruCANDecoder.CRUISE_BUTTONS_ADDR, make_payload_from_bits([43])),
        ],
        0.3,
    )
    yield StubMsg(
        "can",
        [
            StubCAN(SubaruCANDecoder.DASHLIGHTS_ADDR, make_payload_from_bits([50])),
        ],
        1.0,
    )
    yield StubMsg(
        "can",
        [
            StubCAN(SubaruCANDecoder.DASHLIGHTS_ADDR, make_payload_from_bits([51])),
        ],
        2.0,
    )


class StubLR(list):
    def __init__(self, _):
        super().__init__(stub_logreader_messages())


def test_parse_log_file_and_buttons_change(monkeypatch):
    monkeypatch.setattr(mod, "LogReader", StubLR)
    analyzer = CruiseControlAnalyzer(log_file="dummy.zst")
    ok = analyzer.parse_log_file()
    assert ok is True
    assert len(analyzer.speed_data) >= 1
    buttons_analysis = analyzer.analyze_cruise_control_signals().get("cruise_buttons")
    assert buttons_analysis is not None
    assert buttons_analysis["total_messages"] >= 2
    assert len(buttons_analysis["changes"]) >= 1
    assert len(buttons_analysis["set_button_presses"]) >= 1


def test_marker_pipeline_detects_window(monkeypatch):
    monkeypatch.setattr(mod, "LogReader", StubLR)
    analyzer = CruiseControlAnalyzer(log_file="dummy.zst")
    assert analyzer.parse_log_file() is True
    analyzer.marker_config.marker_type = "blinkers"
    windows = analyzer.detect_marker_windows()
    assert isinstance(windows, list)
    assert len(windows) >= 1
    analyzer.marker_windows = windows
    res = analyzer.analyze_marker_windows()
    assert isinstance(res, list)


def test_find_target_speed_events_boundaries():
    analyzer = CruiseControlAnalyzer(log_file="dummy.zst")
    analyzer.speed_data = [
        {"timestamp": 0.0, "speed_mph": 54.9, "speed_kph": 0.0, "wheel_speeds": {}},
        {"timestamp": 1.0, "speed_mph": 55.1, "speed_kph": 0.0, "wheel_speeds": {}},
        {"timestamp": 2.0, "speed_mph": 56.0, "speed_kph": 0.0, "wheel_speeds": {}},
        {"timestamp": 3.0, "speed_mph": 56.1, "speed_kph": 0.0, "wheel_speeds": {}},
    ]
    analyzer.find_target_speed_events(55.0, 56.0)
    assert len(analyzer.target_speed_events) >= 1
    evt = analyzer.target_speed_events[0]
    assert evt["start_time"] >= 1.0
    assert evt["end_time"] <= 3.0


def test_generate_report_and_plot_no_speed_data(monkeypatch, capsys):
    analyzer = CruiseControlAnalyzer(log_file="dummy.zst")
    analyzer.generate_report()
    captured = capsys.readouterr()
    assert "SUBARU CRUISE CONTROL ANALYSIS REPORT" in captured.out
    analyzer.plot_speed_timeline()


def test_event_detector_find_target_speed_events():
    """Test EventDetector find_target_speed_events method directly."""
    decoder = SubaruCANDecoder()
    speed_data = [
        {"timestamp": 0.0, "speed_mph": 54.9, "speed_kph": 0.0, "wheel_speeds": {}},
        {"timestamp": 1.0, "speed_mph": 55.1, "speed_kph": 0.0, "wheel_speeds": {}},
        {"timestamp": 2.0, "speed_mph": 56.0, "speed_kph": 0.0, "wheel_speeds": {}},
        {"timestamp": 3.0, "speed_mph": 56.1, "speed_kph": 0.0, "wheel_speeds": {}},
    ]
    can_data = {}

    event_detector = EventDetector(decoder, speed_data, can_data)
    events = event_detector.find_target_speed_events(55.0, 56.0)

    assert len(events) >= 1
    evt = events[0]
    assert evt["start_time"] >= 1.0
    assert evt["end_time"] <= 3.0


def test_event_detector_analyze_cruise_control_signals():
    """Test EventDetector analyze_cruise_control_signals method directly."""
    decoder = SubaruCANDecoder()
    speed_data = []
    can_data = {
        decoder.CRUISE_BUTTONS_ADDR: [
            {"timestamp": 0.2, "data": make_payload_from_bits([])},
            {"timestamp": 0.3, "data": make_payload_from_bits([43])},
        ]
    }

    event_detector = EventDetector(decoder, speed_data, can_data)
    analysis = event_detector.analyze_cruise_control_signals()

    assert "cruise_buttons" in analysis
    buttons_analysis = analysis["cruise_buttons"]
    assert buttons_analysis["total_messages"] >= 2
    assert len(buttons_analysis["changes"]) >= 1


def test_event_detector_correlate_signals_with_speed():
    """Test EventDetector correlate_signals_with_speed method directly."""
    decoder = SubaruCANDecoder()
    speed_data = [
        {"timestamp": 0.25, "speed_mph": 55.5, "speed_kph": 0.0, "wheel_speeds": {}},
    ]
    can_data = {}

    signal_analysis = {
        "cruise_buttons": {"set_button_presses": [{"timestamp": 0.3, "changes": {"set": True}}]}
    }

    event_detector = EventDetector(decoder, speed_data, can_data)
    correlations = event_detector.correlate_signals_with_speed(signal_analysis)

    assert "set_button_speeds" in correlations
    assert len(correlations["set_button_speeds"]) >= 0
