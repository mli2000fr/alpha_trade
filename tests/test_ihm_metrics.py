from __future__ import annotations

from ihm.components.metrics import format_duration_hhmmss


def test_format_duration_hhmmss_basic_values() -> None:
    assert format_duration_hhmmss(0) == "00:00:00"
    assert format_duration_hhmmss(59) == "00:00:59"
    assert format_duration_hhmmss(60) == "00:01:00"
    assert format_duration_hhmmss(3661) == "01:01:01"


def test_format_duration_hhmmss_invalid_values() -> None:
    assert format_duration_hhmmss(None) == "00:00:00"
    assert format_duration_hhmmss("abc") == "00:00:00"
    assert format_duration_hhmmss(-12) == "00:00:00"
    assert format_duration_hhmmss(12.6) == "00:00:13"

