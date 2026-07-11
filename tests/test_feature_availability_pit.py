"""Tests pour le contrat PIT de disponibilité des données — Sprint Maître 2."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from common.data_availability import (
    DailyQualityReport,
    DataAvailabilityInfo,
    FutureDataError,
    QualityState,
    StaleDataError,
    build_daily_quality_report,
    make_availability_from_bar_date,
    validate_availability,
    validate_availability_or_degraded,
)


# ── DataAvailabilityInfo ─────────────────────────────────────────────────────

def test_availability_info_construction() -> None:
    now = datetime(2026, 7, 10, 16, 0, tzinfo=timezone.utc)
    avail = DataAvailabilityInfo(
        event_time=now - timedelta(hours=1),
        available_at=now,
        source="eodhd",
    )
    assert avail.source == "eodhd"
    assert avail.timezone == "America/New_York"
    assert avail.quality == QualityState.PRESENT


def test_availability_info_rejects_empty_source() -> None:
    with pytest.raises(ValueError, match="source"):
        DataAvailabilityInfo(
            event_time=datetime(2026, 7, 10, tzinfo=timezone.utc),
            available_at=datetime(2026, 7, 10, tzinfo=timezone.utc),
            source="",
        )


def test_availability_info_rejects_available_before_event() -> None:
    with pytest.raises(ValueError, match="antérieur"):
        DataAvailabilityInfo(
            event_time=datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc),
            available_at=datetime(2026, 7, 9, 12, 0, tzinfo=timezone.utc),
            source="eodhd",
        )


def test_availability_info_adds_utc_timezone() -> None:
    avail = DataAvailabilityInfo(
        event_time=datetime(2026, 7, 10, 16, 0),
        available_at=datetime(2026, 7, 10, 21, 0),
        source="eodhd",
    )
    assert avail.event_time.tzinfo == timezone.utc
    assert avail.available_at.tzinfo == timezone.utc


# ── validate_availability ────────────────────────────────────────────────────

def test_validate_ok() -> None:
    cutoff = datetime(2026, 7, 11, 0, 0, tzinfo=timezone.utc)
    avail = DataAvailabilityInfo(
        event_time=datetime(2026, 7, 10, 21, 0, tzinfo=timezone.utc),
        available_at=datetime(2026, 7, 10, 22, 0, tzinfo=timezone.utc),
        source="eodhd",
    )
    validate_availability(avail, cutoff)  # ne doit pas lever


def test_validate_rejects_future_data() -> None:
    cutoff = datetime(2026, 7, 10, 21, 0, tzinfo=timezone.utc)
    avail = DataAvailabilityInfo(
        event_time=datetime(2026, 7, 11, 21, 0, tzinfo=timezone.utc),
        available_at=datetime(2026, 7, 11, 22, 0, tzinfo=timezone.utc),
        source="eodhd",
    )
    with pytest.raises(FutureDataError, match="future"):
        validate_availability(avail, cutoff)


def test_validate_rejects_stale_data() -> None:
    cutoff = datetime(2026, 7, 12, 0, 0, tzinfo=timezone.utc)
    avail = DataAvailabilityInfo(
        event_time=datetime(2026, 7, 10, 21, 0, tzinfo=timezone.utc),
        available_at=datetime(2026, 7, 10, 22, 0, tzinfo=timezone.utc),
        source="eodhd",
    )
    # 26h d'âge, max=24h → stale
    with pytest.raises(StaleDataError, match="stale"):
        validate_availability(avail, cutoff, max_age_hours=24)


# ── validate_availability_or_degraded ────────────────────────────────────────

def test_validate_or_degraded_future_non_critical() -> None:
    cutoff = datetime(2026, 7, 10, 21, 0, tzinfo=timezone.utc)
    avail = DataAvailabilityInfo(
        event_time=datetime(2026, 7, 11, 21, 0, tzinfo=timezone.utc),
        available_at=datetime(2026, 7, 11, 22, 0, tzinfo=timezone.utc),
        source="eodhd",
    )
    quality = validate_availability_or_degraded(avail, cutoff, critical=False)
    assert quality == QualityState.NOT_YET_AVAILABLE


def test_validate_or_degraded_future_critical_raises() -> None:
    cutoff = datetime(2026, 7, 10, 21, 0, tzinfo=timezone.utc)
    avail = DataAvailabilityInfo(
        event_time=datetime(2026, 7, 11, 21, 0, tzinfo=timezone.utc),
        available_at=datetime(2026, 7, 11, 22, 0, tzinfo=timezone.utc),
        source="eodhd",
    )
    with pytest.raises(FutureDataError):
        validate_availability_or_degraded(avail, cutoff, critical=True)


def test_validate_or_degraded_stale_non_critical() -> None:
    cutoff = datetime(2026, 7, 12, 0, 0, tzinfo=timezone.utc)
    avail = DataAvailabilityInfo(
        event_time=datetime(2026, 7, 10, 21, 0, tzinfo=timezone.utc),
        available_at=datetime(2026, 7, 10, 22, 0, tzinfo=timezone.utc),
        source="eodhd",
    )
    quality = validate_availability_or_degraded(avail, cutoff, max_age_hours=24, critical=False)
    assert quality == QualityState.MISSING_STALE


# ── make_availability_from_bar_date ──────────────────────────────────────────

def test_make_availability_from_bar_date() -> None:
    avail = make_availability_from_bar_date("2026-07-10", source="eodhd")
    assert avail.source == "eodhd"
    assert avail.event_time.date().isoformat() == "2026-07-10"
    assert avail.available_at > avail.event_time
    assert avail.quality == QualityState.PRESENT


# ── DailyQualityReport ──────────────────────────────────────────────────────

def test_build_daily_quality_report_all_present() -> None:
    cutoff = datetime(2026, 7, 10, 23, 0, tzinfo=timezone.utc)
    symbols = ["AAPL", "MSFT", "GOOGL"]
    avail_map = {
        sym: DataAvailabilityInfo(
            event_time=datetime(2026, 7, 10, 21, 0, tzinfo=timezone.utc),
            available_at=datetime(2026, 7, 10, 22, 0, tzinfo=timezone.utc),
            source="eodhd",
        )
        for sym in symbols
    }
    report = build_daily_quality_report(symbols, avail_map, cutoff)
    assert report.total_symbols == 3
    assert report.symbols_with_data == 3
    assert report.symbols_with_future_data == 0
    assert report.coverage_ratio == 1.0


def test_build_daily_quality_report_detects_future_data() -> None:
    cutoff = datetime(2026, 7, 10, 23, 0, tzinfo=timezone.utc)
    symbols = ["AAPL", "MSFT"]
    avail_map = {
        "AAPL": DataAvailabilityInfo(
            event_time=datetime(2026, 7, 11, 21, 0, tzinfo=timezone.utc),
            available_at=datetime(2026, 7, 11, 22, 0, tzinfo=timezone.utc),
            source="eodhd",
        ),
        "MSFT": DataAvailabilityInfo(
            event_time=datetime(2026, 7, 10, 21, 0, tzinfo=timezone.utc),
            available_at=datetime(2026, 7, 10, 22, 0, tzinfo=timezone.utc),
            source="eodhd",
        ),
    }
    report = build_daily_quality_report(symbols, avail_map, cutoff)
    assert report.symbols_with_future_data == 1
    assert "FUTURE_DATA_DETECTED" in " ".join(report.alerts)


def test_build_daily_quality_report_missing_data() -> None:
    cutoff = datetime(2026, 7, 10, 23, 0, tzinfo=timezone.utc)
    symbols = ["AAPL", "MSFT"]
    avail_map = {
        "AAPL": DataAvailabilityInfo(
            event_time=datetime(2026, 7, 10, 21, 0, tzinfo=timezone.utc),
            available_at=datetime(2026, 7, 10, 22, 0, tzinfo=timezone.utc),
            source="eodhd",
        ),
    }
    report = build_daily_quality_report(symbols, avail_map, cutoff)
    assert report.symbols_missing_data == 1
    assert report.coverage_ratio == 0.5
    assert "low_coverage" in " ".join(report.alerts)


def test_build_daily_quality_report_stale_data() -> None:
    cutoff = datetime(2026, 7, 12, 0, 0, tzinfo=timezone.utc)
    symbols = ["AAPL"]
    avail_map = {
        "AAPL": DataAvailabilityInfo(
            event_time=datetime(2026, 7, 10, 21, 0, tzinfo=timezone.utc),
            available_at=datetime(2026, 7, 10, 22, 0, tzinfo=timezone.utc),
            source="eodhd",
        ),
    }
    report = build_daily_quality_report(symbols, avail_map, cutoff, max_age_hours=24)
    assert report.symbols_stale_data == 1


def test_daily_quality_report_to_dict() -> None:
    report = DailyQualityReport(
        report_date="2026-07-10",
        total_symbols=100,
        symbols_with_data=95,
        symbols_missing_data=3,
        symbols_stale_data=2,
        symbols_with_future_data=0,
        coverage_ratio=0.95,
        quality_by_source={"eodhd": {"present": 95, "missing_stale": 2}},
        alerts=["stale_data:ILLIQ:eodhd:26.0h"],
    )
    d = report.to_dict()
    assert d["coverage_ratio"] == 0.95
    assert d["symbols_with_future_data"] == 0
    assert len(d["alerts"]) == 1


# ── QualityState enum ────────────────────────────────────────────────────────

def test_quality_state_values() -> None:
    assert QualityState.PRESENT.value == "present"
    assert QualityState.MISSING_STALE.value == "missing_stale"
    assert QualityState.NOT_YET_AVAILABLE.value == "not_yet_available"
    assert QualityState.DELISTED.value == "delisted"
    assert QualityState.HALTED.value == "halted"
