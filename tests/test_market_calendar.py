from __future__ import annotations

from datetime import date, datetime, timezone

from common import market_calendar


class _FakeSchedule:
    def __init__(self, market_open: datetime, market_close: datetime) -> None:
        self.empty = False
        self.iloc = [{"market_open": market_open, "market_close": market_close}]


class _FakeNyseCalendar:
    def __init__(self, market_open: datetime, market_close: datetime) -> None:
        self._market_open = market_open
        self._market_close = market_close

    def schedule(self, start_date, end_date):  # noqa: ANN001 - signature de fake
        return _FakeSchedule(self._market_open, self._market_close)


def test_get_nyse_session_bounds_prefers_calendar_schedule(monkeypatch) -> None:
    fake_calendar = _FakeNyseCalendar(
        datetime(2026, 7, 3, 13, 30, tzinfo=timezone.utc),
        datetime(2026, 7, 3, 17, 0, tzinfo=timezone.utc),
    )
    monkeypatch.setattr(market_calendar, "_get_nyse_calendar", lambda: fake_calendar)

    market_open, market_close = market_calendar.get_nyse_session_bounds(date(2026, 7, 3))

    assert market_open == datetime(2026, 7, 3, 13, 30, tzinfo=timezone.utc)
    assert market_close == datetime(2026, 7, 3, 17, 0, tzinfo=timezone.utc)


