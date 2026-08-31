"""Contrat PIT : ``resolve_available_at`` (RESEARCH ONLY).

Principe (todo3.txt §2) :
- ``observed_at`` = moment réel où notre collecteur a observé Yahoo.
- ``available_at`` = prochaine clôture de séance STRICTEMENT après
  l'observation → le snapshot est utilisable par toute décision dont le cutoff
  (``decision_cutoff``) satisfait ``available_at <= decision_cutoff``.

Exemple : décision à la clôture J (16:00 ET), collecte à 18:30 ET le jour J →
le snapshot est INTERDIT pour la décision de J ; il devient utilisable à la
clôture de J+1.

Calendrier : ``common.market_calendar`` (NYSE, pandas_market_calendars) — jours
fériés et week-ends gérés. Logique centralisée ici, aucun raccourci basé
uniquement sur la date.
"""
from __future__ import annotations

from datetime import date, datetime, time as dt_time, timedelta, timezone

from common.market_calendar import MARKET_TZ, get_nyse_session_bounds, is_trading_day

# Clôture RTH standard NYSE (16:00 ET) — le cutoff de décision.
DECISION_CLOSE = dt_time(16, 0)

_MAX_LOOKAHEAD_DAYS = 15


def to_utc_naive(dt: datetime) -> datetime:
    """Normalise un datetime en UTC NAIVE (stockage MySQL DATETIME)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc).replace(tzinfo=None)
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def snapshot_date_of(observed_at: datetime) -> date:
    """Date NY (jour de collecte) associée à l'observation."""
    if observed_at.tzinfo is None:
        aware = observed_at.replace(tzinfo=timezone.utc)
    else:
        aware = observed_at
    return aware.astimezone(MARKET_TZ).date()


def resolve_available_at(observed_at: datetime) -> datetime:
    """Prochaine clôture de séance NYSE strictement après ``observed_at`` (UTC naive).

    Retourne un ``datetime`` UTC NAIVE (prêt pour ``available_at``).
    """
    if observed_at.tzinfo is None:
        obs_aware = observed_at.replace(tzinfo=timezone.utc)
    else:
        obs_aware = observed_at.astimezone(timezone.utc)
    d = snapshot_date_of(observed_at)
    for _ in range(_MAX_LOOKAHEAD_DAYS):
        if is_trading_day(d):
            _open_utc, close_utc = get_nyse_session_bounds(d)
            if close_utc > obs_aware:
                return close_utc.replace(tzinfo=None)
        d += timedelta(days=1)
    raise RuntimeError(
        f"resolve_available_at: aucune séance > {observed_at} dans les "
        f"{_MAX_LOOKAHEAD_DAYS} prochains jours"
    )


def decision_cutoff(trading_day: date) -> datetime:
    """Clôture (16:00 ET) d'une séance donnée, en UTC NAIVE."""
    _open_utc, close_utc = get_nyse_session_bounds(trading_day)
    return close_utc.replace(tzinfo=None)
