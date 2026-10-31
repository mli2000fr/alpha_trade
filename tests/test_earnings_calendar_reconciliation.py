import json
from datetime import date, datetime

import pytest
from sqlalchemy import Column, Date, DateTime, Float, Integer, MetaData, String, Table, create_engine, select

from database.earnings_calendar_reconciliation import (
    correction_table, filter_superseded_forecasts, reconcile_confirmed_dates,
)
from dataIntegrityEngine.sync_earnings_calendar import _normalize_rows


@pytest.fixture
def database():
    engine = create_engine("sqlite:///:memory:")
    calendar = Table("stock_earnings_calendar", MetaData(),
        Column("symbol", String, primary_key=True), Column("earnings_date", Date, primary_key=True),
        Column("fiscal_period", String), Column("eps_actual", Float), Column("revenue_actual", Float),
        Column("last_updated", DateTime), Column("instrument_id", Integer))
    archive = correction_table()
    calendar.create(engine)
    archive.create(engine)
    with engine.begin() as connection:
        yield connection, calendar, archive
    engine.dispose()


def row(day, **kwargs):
    return dict(symbol="COHU", earnings_date=date.fromisoformat(day), fiscal_period="3",
                eps_actual=None, revenue_actual=None, last_updated=datetime(2026, 10, 16),
                instrument_id=6667, **kwargs)


def evidence(**overrides):
    result = dict(symbol="COHU", earnings_date="2026-10-28", fiscal_period=3, eps_actual=0.43,
                  revenue_actual=None, _calendar_evidence=dict(provider="finnhub", fiscal_year=2026,
                  observed_at="2026-10-30T00:26:17+00:00"))
    result.update(overrides)
    return result


def seed(connection, calendar, extra=None):
    actual = row("2026-10-28")
    actual["eps_actual"] = 0.43
    connection.execute(calendar.insert(), [row("2026-10-27"), actual, row("2026-10-29"), *(extra or [])])


def test_archive_before_removing_only_stale_forecasts(database):
    connection, calendar, archive = database
    seed(connection, calendar, [row("2025-10-29"), row("2026-12-29")])
    assert reconcile_confirmed_dates(connection, calendar, archive, [evidence()]) == 2
    assert set(connection.execute(select(calendar.c.earnings_date)).scalars()) == {date(2026, 10, 28), date(2025, 10, 29), date(2026, 12, 29)}
    saved = list(connection.execute(select(archive)).mappings())
    assert len(saved) == 2
    assert json.loads(saved[0]["original_row_json"])["instrument_id"] == 6667
    assert json.loads(saved[0]["replacement_evidence_json"])["_calendar_evidence"]["fiscal_year"] == 2026
    assert reconcile_confirmed_dates(connection, calendar, archive, [evidence()]) == 0


@pytest.mark.parametrize("change", [
    {"eps_actual": 0.0}, {"revenue_actual": 100}, {"fiscal_period": "4"},
    {"instrument_id": 123}, {"instrument_id": None}, {"last_updated": datetime(2026, 10, 30, 1)},
])
def test_protect_actual_other_period_identity_and_newer_rows(database, change):
    connection, calendar, archive = database
    actual = row("2026-10-28")
    actual["eps_actual"] = 0.43
    old = row("2026-10-29")
    old.update(change)
    connection.execute(calendar.insert(), [actual, old])
    assert reconcile_confirmed_dates(connection, calendar, archive, [evidence()]) == 0
    assert len(list(connection.execute(select(calendar)))) == 2


@pytest.mark.parametrize("proof", [
    dict(provider="sec", fiscal_year=2026, observed_at="2026-10-30T00:00:00+00:00"),
    dict(provider="finnhub", fiscal_year=None, observed_at="2026-10-30T00:00:00+00:00"),
    dict(provider="finnhub", fiscal_year=2026, observed_at="2026-10-30T00:00:00"),
    dict(provider="finnhub", fiscal_year=2026, observed_at="2026-10-27T00:00:00+00:00"),
])
def test_no_unqualified_or_future_announcement_reconciliation(database, proof):
    connection, calendar, archive = database
    seed(connection, calendar)
    assert reconcile_confirmed_dates(connection, calendar, archive, [evidence(_calendar_evidence=proof)]) == 0


def test_zero_actual_qualifies_and_old_prediction_cannot_return(database):
    connection, calendar, archive = database
    seed(connection, calendar)
    connection.execute(calendar.update().where(calendar.c.earnings_date == date(2026, 10, 28)).values(eps_actual=0))
    assert reconcile_confirmed_dates(connection, calendar, archive, [evidence(eps_actual=0)]) == 2
    forecast = evidence(earnings_date="2026-10-29", eps_actual=None)
    assert filter_superseded_forecasts(connection, calendar, archive, [forecast]) == []
    # Un nouveau réalisé contradictoire est conservé pour diagnostic.
    assert filter_superseded_forecasts(connection, calendar, archive, [evidence(earnings_date="2026-10-29")])


def test_normalizer_attaches_announcement_provenance():
    normalized = _normalize_rows([dict(symbol="COHU", date="2026-10-28", quarter=3, year=2026, epsActual=0)])
    assert normalized[0]["eps_actual"] == 0
    assert normalized[0]["_calendar_evidence"]["provider"] == "finnhub"
    assert normalized[0]["_calendar_evidence"]["fiscal_year"] == 2026
