"""Tests du contrat PIT ``resolve_available_at`` (RESEARCH ONLY)."""
from __future__ import annotations

from datetime import date, datetime, time as dt_time, timedelta

from analyst_research.available_at import (
    decision_cutoff,
    resolve_available_at,
    snapshot_date_of,
)
from common.market_calendar import MARKET_TZ, get_nyse_session_bounds, is_trading_day, next_trading_day


def _trading_day(base: date) -> date:
    d = base
    while not is_trading_day(d):
        d += timedelta(days=1)
    return d


def test_snapshot_after_cutoff_hidden_pit_critical():
    """PIT critique : snapshot observé APRÈS la clôture (18:30 ET) → utilisable
    uniquement à la clôture de la SÉANCE SUIVANTE (pas à la clôture du jour)."""
    day = _trading_day(date(2026, 8, 27))
    observed = datetime.combine(day, dt_time(18, 30), tzinfo=MARKET_TZ)  # après 16:00 ET
    avail = resolve_available_at(observed)
    expected_day = next_trading_day(day)  # J+1
    _open, close_utc = get_nyse_session_bounds(expected_day)
    assert avail == close_utc.replace(tzinfo=None)
    # Le snapshot n'est PAS visible au cutoff du jour même :
    assert avail > decision_cutoff(day)


def test_snapshot_before_cutoff_visible():
    """Observation AVANT la clôture (10:00 ET) → utilisable à la clôture du jour."""
    day = _trading_day(date(2026, 8, 27))
    observed = datetime.combine(day, dt_time(10, 0), tzinfo=MARKET_TZ)
    avail = resolve_available_at(observed)
    assert avail == decision_cutoff(day)


def test_weekend_collection_moves_to_monday():
    """Collecte un week-end → available_at = clôture du prochain jour de bourse."""
    sat = date(2026, 8, 29)
    while not (sat.weekday() == 5):
        sat += timedelta(days=1)  # garantit un samedi
    observed = datetime.combine(sat, dt_time(12, 0), tzinfo=MARKET_TZ)
    avail = resolve_available_at(observed)
    expected_day = next_trading_day(sat)
    _open, close_utc = get_nyse_session_bounds(expected_day)
    assert avail == close_utc.replace(tzinfo=None)


def test_snapshot_date_is_ny_date():
    """``snapshot_date`` = date NY de l'observation (pas UTC)."""
    observed = datetime(2026, 8, 27, 22, 30)  # UTC → encore le 27 en NY (18:30)
    assert snapshot_date_of(observed) == date(2026, 8, 27)
