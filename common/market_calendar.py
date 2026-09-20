"""Calendrier multi-marchés et politiques Point-In-Time.

Priorité des sources : table canonique ``market_sessions``, calendrier validé,
puis fallback lundi-vendredi réservé à la compatibilité US. Les anciens helpers
NYSE restent des wrappers afin de préserver les flux US pendant la migration.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from datetime import time as dt_time
from functools import lru_cache
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml
from sqlalchemy import text
from sqlalchemy.engine import Engine

from common.config_loader import resolve_market_context
from common.market_context import MarketCode, MarketContext

LOGGER = logging.getLogger(__name__)
MARKET_TZ = ZoneInfo("America/New_York")
_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_CUTOFFS_PATH = _ROOT / "config" / "markets" / "dataset_cutoffs.yaml"
_LIBRARY_CALENDARS: Mapping[str, str] = {"NYSE": "NYSE", "CN_A": "XSHG", "CN_BJ": "XSHG"}


class MarketCalendarError(RuntimeError):
    """Erreur de contrat du calendrier de marché."""


class MarketCalendarUnavailableError(MarketCalendarError):
    """Aucune source fiable n'est disponible pour le marché demandé."""


class DatasetCutoffError(MarketCalendarError):
    """Politique de publication absente ou invalide."""


@dataclass(frozen=True, slots=True)
class SessionSegment:
    name: str
    open_at_utc: datetime
    close_at_utc: datetime

    def __post_init__(self) -> None:
        if self.open_at_utc.tzinfo is None or self.close_at_utc.tzinfo is None:
            raise MarketCalendarError("Les bornes d'un segment doivent être timezone-aware")
        if self.close_at_utc <= self.open_at_utc:
            raise MarketCalendarError("La fermeture d'un segment doit suivre son ouverture")


@dataclass(frozen=True, slots=True)
class MarketSession:
    market_code: MarketCode
    session_date: date
    status: str
    open_at_utc: datetime
    close_at_utc: datetime
    segments: tuple[SessionSegment, ...]
    source: str

    @property
    def is_open(self) -> bool:
        return self.status in {"open", "half_day", "special"}


@dataclass(frozen=True, slots=True)
class DatasetCutoffPolicy:
    dataset: str
    anchor: str
    offset_minutes: int = 0


def _aware_utc(value: Any) -> datetime:
    if hasattr(value, "to_pydatetime"):
        value = value.to_pydatetime()
    if not isinstance(value, datetime):
        value = datetime.fromisoformat(str(value))
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _local_segment(day: date, tz_name: str, name: str, start: dt_time, end: dt_time) -> SessionSegment:
    tz = ZoneInfo(tz_name)
    return SessionSegment(
        name,
        datetime.combine(day, start, tzinfo=tz).astimezone(UTC),
        datetime.combine(day, end, tzinfo=tz).astimezone(UTC),
    )


def _segments_for_context(
    context: MarketContext, day: date, market_open: datetime, market_close: datetime
) -> tuple[SessionSegment, ...]:
    if context.market_code in {MarketCode.CN_A, MarketCode.CN_BJ}:
        return (
            _local_segment(day, context.timezone, "morning", dt_time(9, 30), dt_time(11, 30)),
            _local_segment(day, context.timezone, "afternoon", dt_time(13), dt_time(15)),
        )
    return (SessionSegment("continuous", market_open, market_close),)


@lru_cache(maxsize=8)
def _get_library_calendar(calendar_id: str):
    try:
        import pandas_market_calendars as mcal

        return mcal.get_calendar(_LIBRARY_CALENDARS[calendar_id])
    except Exception as exc:
        LOGGER.warning("Calendrier bibliothèque indisponible pour %s: %s", calendar_id, exc)
        return None


@lru_cache(maxsize=1)
def _get_nyse_calendar():
    """Point d'extension historique conservé pour compatibilité et tests."""
    return _get_library_calendar("NYSE")


class MarketCalendar:
    """Service de séances lié à un contexte marché explicite."""

    def __init__(
        self,
        context: MarketContext,
        *,
        engine: Engine | None = None,
        allow_us_weekday_fallback: bool = True,
    ) -> None:
        self.context = context
        self.engine = engine
        self.allow_us_weekday_fallback = allow_us_weekday_fallback

    def _database_coverage(self) -> tuple[date, date] | None:
        if self.engine is None:
            return None
        try:
            with self.engine.connect() as connection:
                row = (
                    connection.execute(
                        text(
                            "SELECT MIN(session_date) min_date, MAX(session_date) max_date "
                            "FROM market_sessions WHERE market_code=:market_code"
                        ),
                        {"market_code": self.context.market_code.value},
                    )
                    .mappings()
                    .first()
                )
        except Exception as exc:
            LOGGER.warning("Lecture market_sessions impossible: %s", exc)
            return None
        if not row or row["min_date"] is None or row["max_date"] is None:
            return None
        minimum = row["min_date"] if isinstance(row["min_date"], date) else date.fromisoformat(str(row["min_date"]))
        maximum = row["max_date"] if isinstance(row["max_date"], date) else date.fromisoformat(str(row["max_date"]))
        return minimum, maximum

    def _database_sessions(self, start: date, end: date) -> list[MarketSession] | None:
        coverage = self._database_coverage()
        if coverage is None or start < coverage[0] or end > coverage[1]:
            return None
        with self.engine.connect() as connection:  # type: ignore[union-attr]
            rows = (
                connection.execute(
                    text(
                        "SELECT session_date,session_status,open_at_utc,close_at_utc,"
                        "session_segments_json,source FROM market_sessions "
                        "WHERE market_code=:market_code AND session_date BETWEEN :start AND :end "
                        "ORDER BY session_date"
                    ),
                    {"market_code": self.context.market_code.value, "start": start, "end": end},
                )
                .mappings()
                .all()
            )
        result: list[MarketSession] = []
        for row in rows:
            if row["session_status"] == "closed":
                continue
            if row["open_at_utc"] is None or row["close_at_utc"] is None:
                raise MarketCalendarError(
                    f"Séance ouverte sans bornes: {self.context.market_code.value} {row['session_date']}"
                )
            session_day = (
                row["session_date"]
                if isinstance(row["session_date"], date)
                else date.fromisoformat(str(row["session_date"]))
            )
            market_open, market_close = _aware_utc(row["open_at_utc"]), _aware_utc(row["close_at_utc"])
            raw_segments = row.get("session_segments_json")
            if isinstance(raw_segments, str):
                raw_segments = json.loads(raw_segments)
            segments = tuple(
                SessionSegment(str(item["name"]), _aware_utc(item["open_at_utc"]), _aware_utc(item["close_at_utc"]))
                for item in (raw_segments or [])
            ) or _segments_for_context(self.context, session_day, market_open, market_close)
            result.append(
                MarketSession(
                    self.context.market_code,
                    session_day,
                    row["session_status"],
                    market_open,
                    market_close,
                    segments,
                    f"database:{row['source']}",
                )
            )
        return result

    def _library_sessions(self, start: date, end: date) -> list[MarketSession]:
        calendar = (
            _get_nyse_calendar()
            if self.context.calendar_id == "NYSE"
            else _get_library_calendar(self.context.calendar_id)
        )
        if calendar is not None:
            try:
                schedule = calendar.schedule(start_date=start, end_date=end)
            except Exception as exc:
                LOGGER.warning("Calendrier %s en échec: %s", self.context.calendar_id, exc)
            else:
                result: list[MarketSession] = []
                for index, row in schedule.iterrows():
                    day = index.date() if hasattr(index, "date") else index
                    market_open, market_close = _aware_utc(row["market_open"]), _aware_utc(row["market_close"])
                    result.append(
                        MarketSession(
                            self.context.market_code,
                            day,
                            "open",
                            market_open,
                            market_close,
                            _segments_for_context(self.context, day, market_open, market_close),
                            f"library:{self.context.calendar_id}",
                        )
                    )
                return result
        if self.context.market_code is not MarketCode.US_EQ or not self.allow_us_weekday_fallback:
            raise MarketCalendarUnavailableError(
                f"Calendrier fiable absent pour {self.context.market_code.value}/{self.context.calendar_id}; "
                "fallback weekday-only interdit"
            )
        LOGGER.warning("Calendrier NYSE en fallback weekday-only sur [%s, %s]", start, end)
        result = []
        current = start
        while current <= end:
            if current.weekday() < 5:
                market_open = datetime.combine(current, dt_time(9, 30), tzinfo=MARKET_TZ).astimezone(UTC)
                market_close = datetime.combine(current, dt_time(16), tzinfo=MARKET_TZ).astimezone(UTC)
                result.append(
                    MarketSession(
                        self.context.market_code,
                        current,
                        "open",
                        market_open,
                        market_close,
                        (SessionSegment("continuous", market_open, market_close),),
                        "legacy:weekday-only",
                    )
                )
            current += timedelta(days=1)
        return result

    def sessions(self, start: date, end: date) -> list[MarketSession]:
        if end < start:
            return []
        canonical = self._database_sessions(start, end)
        return canonical if canonical is not None else self._library_sessions(start, end)

    def session_dates(self, start: date, end: date) -> list[date]:
        return [item.session_date for item in self.sessions(start, end) if item.is_open]

    def session(self, day: date) -> MarketSession:
        items = self.sessions(day, day)
        if not items:
            raise MarketCalendarError(f"{day} n'est pas une séance {self.context.market_code.value}")
        return items[0]

    def session_bounds(self, day: date) -> tuple[datetime, datetime]:
        item = self.session(day)
        return item.open_at_utc, item.close_at_utc

    def _seek(self, from_date: date, nth: int, direction: int) -> date:
        if nth < 1:
            raise ValueError("nth doit être >= 1")
        span = max(14, nth * 3)
        for _ in range(8):
            if direction > 0:
                candidates = self.session_dates(from_date + timedelta(days=1), from_date + timedelta(days=span))
            else:
                candidates = self.session_dates(from_date - timedelta(days=span), from_date - timedelta(days=1))
                candidates.reverse()
            if len(candidates) >= nth:
                return candidates[nth - 1]
            span *= 2
        raise MarketCalendarUnavailableError(f"Impossible de trouver {nth} séance(s) depuis {from_date}")

    def next_session(self, from_date: date, nth: int = 1) -> date:
        return self._seek(from_date, nth, 1)

    def previous_session(self, from_date: date, nth: int = 1) -> date:
        return self._seek(from_date, nth, -1)

    def advance_sessions(self, from_date: date, count: int) -> date:
        if count > 0:
            return self.next_session(from_date, count)
        if count < 0:
            return self.previous_session(from_date, -count)
        self.session(from_date)
        return from_date


def _context(value: MarketContext | MarketCode | str) -> MarketContext:
    return value if isinstance(value, MarketContext) else resolve_market_context(str(value))


def get_market_calendar(
    context: MarketContext | MarketCode | str,
    *,
    engine: Engine | None = None,
    allow_us_weekday_fallback: bool = True,
) -> MarketCalendar:
    return MarketCalendar(_context(context), engine=engine, allow_us_weekday_fallback=allow_us_weekday_fallback)


def session_dates(context, start: date, end: date, *, engine: Engine | None = None) -> list[date]:
    return get_market_calendar(context, engine=engine).session_dates(start, end)


def session_bounds(context, day: date, *, engine: Engine | None = None) -> tuple[datetime, datetime]:
    return get_market_calendar(context, engine=engine).session_bounds(day)


def next_session(context, day: date, nth: int = 1, *, engine: Engine | None = None) -> date:
    return get_market_calendar(context, engine=engine).next_session(day, nth)


def previous_session(context, day: date, nth: int = 1, *, engine: Engine | None = None) -> date:
    return get_market_calendar(context, engine=engine).previous_session(day, nth)


def advance_sessions(context, day: date, count: int, *, engine: Engine | None = None) -> date:
    return get_market_calendar(context, engine=engine).advance_sessions(day, count)


@lru_cache(maxsize=4)
def _load_cutoff_policies(path: str = str(_DEFAULT_CUTOFFS_PATH)) -> dict[str, dict[str, DatasetCutoffPolicy]]:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if payload.get("schema_version") != 1:
        raise DatasetCutoffError("schema_version dataset_cutoffs invalide")
    policies: dict[str, dict[str, DatasetCutoffPolicy]] = {}
    for dataset, markets in (payload.get("datasets") or {}).items():
        policies[str(dataset)] = {}
        for market_code, raw in (markets or {}).items():
            anchor = str(raw.get("anchor") or "").strip()
            if anchor not in {"session_open", "session_close"}:
                raise DatasetCutoffError(f"Ancre invalide pour {dataset}/{market_code}: {anchor!r}")
            policies[str(dataset)][str(market_code)] = DatasetCutoffPolicy(
                str(dataset), anchor, int(raw.get("offset_minutes", 0))
            )
    return policies


def dataset_cutoff(
    context: MarketContext | MarketCode | str,
    dataset: str,
    day: date,
    *,
    engine: Engine | None = None,
    policies_path: str | Path | None = None,
) -> datetime:
    resolved = _context(context)
    policies = _load_cutoff_policies(str(policies_path or _DEFAULT_CUTOFFS_PATH))
    try:
        policy = policies[dataset][resolved.market_code.value]
    except KeyError as exc:
        raise DatasetCutoffError(
            f"Politique de cutoff absente pour dataset={dataset!r}, marché={resolved.market_code.value}"
        ) from exc
    market_open, market_close = get_market_calendar(resolved, engine=engine).session_bounds(day)
    anchor = market_open if policy.anchor == "session_open" else market_close
    return anchor + timedelta(minutes=policy.offset_minutes)


# Wrappers US historiques : implémentation volontairement autonome pour
# préserver leurs points d'extension et doubles de tests existants.
def is_trading_day(d: date) -> bool:
    calendar = _get_nyse_calendar()
    if calendar is None:
        return d.weekday() < 5
    return not calendar.schedule(start_date=d, end_date=d).empty


def nyse_session_dates(start: date, end: date) -> list[date]:
    if end < start:
        return []
    calendar = _get_nyse_calendar()
    if calendar is not None:
        try:
            schedule = calendar.schedule(start_date=start, end_date=end)
        except Exception as exc:
            LOGGER.warning("Calendrier NYSE en échec (%s), fallback weekday-only", exc)
        else:
            return [item.date() if hasattr(item, "date") else item for item in schedule.index.tolist()]
    LOGGER.warning("Calendrier NYSE en fallback weekday-only sur [%s, %s]", start, end)
    result: list[date] = []
    current = start
    while current <= end:
        if current.weekday() < 5:
            result.append(current)
        current += timedelta(days=1)
    return result


def get_nyse_session_bounds(session_date: date) -> tuple[datetime, datetime]:
    calendar = _get_nyse_calendar()
    if calendar is not None:
        try:
            schedule = calendar.schedule(start_date=session_date, end_date=session_date)
        except Exception as exc:
            LOGGER.warning("Lecture des bornes NYSE impossible pour %s: %s", session_date, exc)
        else:
            if not schedule.empty:
                row = schedule.iloc[0]
                return _aware_utc(row["market_open"]), _aware_utc(row["market_close"])
    market_open = datetime.combine(session_date, dt_time(9, 30), tzinfo=MARKET_TZ).astimezone(UTC)
    market_close = datetime.combine(session_date, dt_time(16), tzinfo=MARKET_TZ).astimezone(UTC)
    return market_open, market_close


def is_us_market_holiday(d: date) -> bool:
    return not is_trading_day(d)


def getLastDateMarche(ref_date: date | None = None) -> date:
    current = ref_date or date.today()
    while True:
        current -= timedelta(days=1)
        if is_trading_day(current):
            return current


def next_trading_day(from_date: date, *, nth: int = 1) -> date:
    if nth < 1:
        raise ValueError("nth doit être >= 1.")
    current = from_date + timedelta(days=1)
    remaining = nth
    for _ in range(max(14, nth * 3)):
        if is_trading_day(current):
            remaining -= 1
            if remaining == 0:
                return current
        current += timedelta(days=1)
    raise RuntimeError(f"Impossible de trouver le {nth}e jour de bourse après {from_date}")


def trading_days_between(start: date, end: date) -> int:
    return len(nyse_session_dates(start, end)) if end >= start else 0


__all__ = [
    "DatasetCutoffError",
    "DatasetCutoffPolicy",
    "MARKET_TZ",
    "MarketCalendar",
    "MarketCalendarError",
    "MarketCalendarUnavailableError",
    "MarketSession",
    "SessionSegment",
    "advance_sessions",
    "dataset_cutoff",
    "getLastDateMarche",
    "get_market_calendar",
    "get_nyse_session_bounds",
    "is_trading_day",
    "is_us_market_holiday",
    "next_session",
    "next_trading_day",
    "nyse_session_dates",
    "previous_session",
    "session_bounds",
    "session_dates",
    "trading_days_between",
]
