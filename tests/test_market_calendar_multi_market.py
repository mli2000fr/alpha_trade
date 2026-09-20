from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import create_engine, text

from common import market_calendar
from common.config_loader import resolve_market_context
from common.data_availability import (
    DataAvailabilityInfo,
    FutureDataError,
    make_market_availability_from_bar_date,
    validate_availability,
)
from common.market_calendar import (
    DatasetCutoffError,
    MarketCalendarUnavailableError,
    dataset_cutoff,
    get_market_calendar,
    nyse_session_dates,
)
from database.repositories.market_sessions import upsert_market_sessions


def test_us_generic_calendar_has_identical_historical_session_hash() -> None:
    start, end = date(2020, 1, 1), date(2026, 12, 31)
    legacy = nyse_session_dates(start, end)
    generic = get_market_calendar(resolve_market_context("US_EQ")).session_dates(start, end)
    def digest(values) -> str:
        return hashlib.sha256("|".join(map(str, values)).encode()).hexdigest()

    assert digest(generic) == digest(legacy)


def test_us_dst_uses_variable_utc_bounds() -> None:
    calendar = get_market_calendar(resolve_market_context("US_EQ"))
    winter_open, winter_close = calendar.session_bounds(date(2026, 1, 5))
    summer_open, summer_close = calendar.session_bounds(date(2026, 7, 6))
    assert (winter_open.hour, winter_close.hour) == (14, 21)
    assert (summer_open.hour, summer_close.hour) == (13, 20)


def test_cn_calendar_has_shanghai_segments_and_no_dst() -> None:
    calendar = get_market_calendar(resolve_market_context("CN_A"))
    session = calendar.session(date(2026, 9, 18))
    assert session.open_at_utc == datetime(2026, 9, 18, 1, 30, tzinfo=UTC)
    assert session.close_at_utc == datetime(2026, 9, 18, 7, 0, tzinfo=UTC)
    assert [segment.name for segment in session.segments] == ["morning", "afternoon"]
    assert session.segments[0].close_at_utc.hour == 3
    assert session.segments[1].open_at_utc.hour == 5


def test_us_and_cn_holidays_are_not_interchangeable() -> None:
    us = get_market_calendar(resolve_market_context("US_EQ"))
    cn = get_market_calendar(resolve_market_context("CN_A"))
    assert not us.session_dates(date(2026, 7, 3), date(2026, 7, 3))
    assert cn.session_dates(date(2026, 7, 3), date(2026, 7, 3))
    assert us.session_dates(date(2026, 10, 1), date(2026, 10, 1))
    assert not cn.session_dates(date(2026, 10, 1), date(2026, 10, 1))


def test_h20_is_twenty_market_sessions_for_each_market() -> None:
    for code in ("US_EQ", "CN_A", "CN_BJ"):
        calendar = get_market_calendar(resolve_market_context(code))
        start = date(2026, 1, 5)
        target = calendar.next_session(start, 20)
        assert len(calendar.session_dates(start, target)) == 21
        assert calendar.advance_sessions(start, 20) == target


def test_cn_refuses_weekday_only_when_library_is_missing(monkeypatch) -> None:
    monkeypatch.setattr(market_calendar, "_get_library_calendar", lambda _calendar_id: None)
    calendar = get_market_calendar(resolve_market_context("CN_A"))
    with pytest.raises(MarketCalendarUnavailableError, match="fallback weekday-only interdit"):
        calendar.session_dates(date(2026, 9, 14), date(2026, 9, 18))


def test_dataset_cutoff_uses_real_close_and_dst() -> None:
    us = resolve_market_context("US_EQ")
    winter = dataset_cutoff(us, "daily_bars", date(2026, 1, 5))
    summer = dataset_cutoff(us, "daily_bars", date(2026, 7, 6))
    assert winter == datetime(2026, 1, 5, 21, 15, tzinfo=UTC)
    assert summer == datetime(2026, 7, 6, 20, 15, tzinfo=UTC)
    with pytest.raises(DatasetCutoffError, match="Politique de cutoff absente"):
        dataset_cutoff(us, "unknown_dataset", date(2026, 7, 6))


def test_market_availability_carries_explicit_market_dataset_and_timezone() -> None:
    context = resolve_market_context("CN_A")
    info = make_market_availability_from_bar_date("2026-09-18", context=context, source="tushare", dataset="daily_bars")
    assert info.market_code == "CN_A"
    assert info.dataset == "daily_bars"
    assert info.timezone == "Asia/Shanghai"
    assert info.event_time == datetime(2026, 9, 18, 7, 0, tzinfo=UTC)
    assert info.available_at == datetime(2026, 9, 18, 7, 15, tzinfo=UTC)


def test_publication_after_decision_cutoff_is_rejected() -> None:
    info = DataAvailabilityInfo(
        event_time=datetime(2026, 9, 18, 7, 0, tzinfo=UTC),
        available_at=datetime(2026, 9, 18, 7, 15, tzinfo=UTC),
        source="tushare",
        timezone="Asia/Shanghai",
        market_code="CN_A",
        dataset="daily_bars",
    )
    with pytest.raises(FutureDataError):
        validate_availability(info, datetime(2026, 9, 18, 7, 10, tzinfo=UTC))


def _sqlite_calendar_engine():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(
            text("""
            CREATE TABLE market_sessions (
                market_code TEXT NOT NULL, session_date DATE NOT NULL,
                session_status TEXT NOT NULL, open_at_utc DATETIME,
                close_at_utc DATETIME, session_segments_json TEXT,
                source TEXT NOT NULL, observed_at DATETIME NOT NULL,
                available_at DATETIME NOT NULL,
                PRIMARY KEY(market_code, session_date)
            )
        """)
        )
    return engine


def test_canonical_database_has_priority_and_upsert_is_idempotent(monkeypatch) -> None:
    engine = _sqlite_calendar_engine()
    context = resolve_market_context("CN_A")
    source_calendar = get_market_calendar(context)
    sessions = source_calendar.sessions(date(2026, 9, 14), date(2026, 9, 18))
    assert upsert_market_sessions(engine, sessions) == 5
    assert upsert_market_sessions(engine, sessions) == 5
    monkeypatch.setattr(
        market_calendar,
        "_get_library_calendar",
        lambda _calendar_id: (_ for _ in ()).throw(AssertionError("library called")),
    )
    canonical = get_market_calendar(context, engine=engine)
    loaded = canonical.sessions(date(2026, 9, 14), date(2026, 9, 18))
    assert len(loaded) == 5
    assert all(item.source.startswith("database:") for item in loaded)
