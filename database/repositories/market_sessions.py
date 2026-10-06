"""Persistance idempotente des séances de marché canoniques."""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.engine import Engine

from common.market_calendar import MarketSession


def _segments_json(session: MarketSession) -> str:
    return json.dumps(
        [
            {
                "name": segment.name,
                "open_at_utc": segment.open_at_utc.astimezone(UTC).isoformat(),
                "close_at_utc": segment.close_at_utc.astimezone(UTC).isoformat(),
            }
            for segment in session.segments
        ],
        separators=(",", ":"),
        sort_keys=True,
    )


def upsert_market_sessions(
    engine: Engine,
    sessions: Iterable[MarketSession],
    *,
    observed_at: datetime | None = None,
    available_at: datetime | None = None,
) -> int:
    """Insère ou actualise les séances, sans modifier leur identité marché/date."""
    observed = observed_at or datetime.now(UTC)
    available = available_at or observed
    rows = [
        {
            "market_code": item.market_code.value,
            "session_date": item.session_date,
            "session_status": item.status,
            "open_at_utc": item.open_at_utc.astimezone(UTC).replace(tzinfo=None),
            "close_at_utc": item.close_at_utc.astimezone(UTC).replace(tzinfo=None),
            "segments": _segments_json(item),
            "source": item.source[:64],
            "observed_at": observed.astimezone(UTC).replace(tzinfo=None),
            "available_at": available.astimezone(UTC).replace(tzinfo=None),
        }
        for item in sessions
    ]
    if not rows:
        return 0
    mysql = engine.dialect.name in {"mysql", "mariadb"}
    statement = text(
        "INSERT INTO market_sessions "
        "(market_code,session_date,session_status,open_at_utc,close_at_utc,session_segments_json,"
        "source,observed_at,available_at) VALUES "
        "(:market_code,:session_date,:session_status,:open_at_utc,:close_at_utc,:segments,"
        ":source,:observed_at,:available_at) "
        + (
            "ON DUPLICATE KEY UPDATE session_status=VALUES(session_status),open_at_utc=VALUES(open_at_utc),"
            "close_at_utc=VALUES(close_at_utc),session_segments_json=VALUES(session_segments_json),"
            "source=VALUES(source),observed_at=VALUES(observed_at),available_at=VALUES(available_at)"
            if mysql
            else "ON CONFLICT(market_code,session_date) DO UPDATE SET "
            "session_status=excluded.session_status,open_at_utc=excluded.open_at_utc,"
            "close_at_utc=excluded.close_at_utc,session_segments_json=excluded.session_segments_json,"
            "source=excluded.source,observed_at=excluded.observed_at,available_at=excluded.available_at"
        )
    )
    with engine.begin() as connection:
        connection.execute(statement, rows)
    return len(rows)


__all__ = ["upsert_market_sessions"]
