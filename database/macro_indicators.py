from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import date, datetime, timezone
from functools import lru_cache
from typing import Any, cast

from sqlalchemy import Boolean, Column, Date, DateTime, Float, Integer, MetaData, String, Table, inspect, select

from database.connection import get_sqlalchemy_engine

LOGGER = logging.getLogger(__name__)
_ALLOWED_MACRO_COLUMNS = {"vix", "vix9d", "ten_y", "vxn", "vix3m", "move", "rvx"}


@lru_cache(maxsize=1)
def get_macro_indicators_daily_table() -> Table:
    metadata = MetaData()
    return Table(
        "stock_macro_indicators_daily",
        metadata,
        Column("trade_date", Date, primary_key=True),
        Column("vix", Float, nullable=True),
        Column("vix9d", Float, nullable=True),
        Column("vxn", Float, nullable=True),
        Column("vix3m", Float, nullable=True),
        Column("move", Float, nullable=True),
        Column("rvx", Float, nullable=True),
        Column("ten_y", Float, nullable=True),
        Column("mode", String(32), nullable=True),
        Column("risk_multiplier", Float, nullable=True),
        Column("effective_max_positions", Integer, nullable=True),
        Column("allow_new_entries", Boolean, nullable=True),
        Column("vix_curve_inverted", Boolean, nullable=True),
        Column("yield_10y_5d_pct", Float, nullable=True),
        Column("sentiment_score", Float, nullable=True),
        Column("sentiment_level", String(16), nullable=True),
        Column("sentiment_source", String(64), nullable=True),
        Column("created_at", DateTime, nullable=True),
        Column("updated_at", DateTime, nullable=True),
    )


def _coerce_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        try:
            return date.fromisoformat(cleaned[:10])
        except ValueError:
            return None
    return None


def _coerce_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_bool(value: Any) -> bool | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        cleaned = value.strip().lower()
        if cleaned in {"1", "true", "yes", "y", "on"}:
            return True
        if cleaned in {"0", "false", "no", "n", "off"}:
            return False
    return None


def _coerce_str(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _table_exists(engine) -> bool:
    if engine is None:
        return False
    try:
        return inspect(engine).has_table(get_macro_indicators_daily_table().name)
    except Exception:
        return False


def _resolve_engine(engine=None):
    if engine is not None:
        return engine
    try:
        return get_sqlalchemy_engine()
    except Exception:
        LOGGER.debug("Engine SQLAlchemy indisponible pour stock_macro_indicators_daily.", exc_info=True)
        return None


def persist_macro_indicator_daily(
    *,
    trade_date: Any,
    vix: Any = None,
    vix9d: Any = None,
    vxn: Any = None,
    vix3m: Any = None,
    move: Any = None,
    rvx: Any = None,
    ten_y: Any = None,
    mode: Any = None,
    risk_multiplier: Any = None,
    effective_max_positions: Any = None,
    allow_new_entries: Any = None,
    vix_curve_inverted: Any = None,
    yield_10y_5d_pct: Any = None,
    sentiment_score: Any = None,
    sentiment_level: Any = None,
    sentiment_source: Any = None,
    engine=None,
) -> int:
    resolved_trade_date = _coerce_date(trade_date)
    if resolved_trade_date is None:
        return 0

    payload = {
        "trade_date": resolved_trade_date,
        "vix": _coerce_float(vix),
        "vix9d": _coerce_float(vix9d),
        "vxn": _coerce_float(vxn),
        "vix3m": _coerce_float(vix3m),
        "move": _coerce_float(move),
        "rvx": _coerce_float(rvx),
        "ten_y": _coerce_float(ten_y),
        "mode": _coerce_str(mode),
        "risk_multiplier": _coerce_float(risk_multiplier),
        "effective_max_positions": _coerce_int(effective_max_positions),
        "allow_new_entries": _coerce_bool(allow_new_entries),
        "vix_curve_inverted": _coerce_bool(vix_curve_inverted),
        "yield_10y_5d_pct": _coerce_float(yield_10y_5d_pct),
        "sentiment_score": _coerce_float(sentiment_score),
        "sentiment_level": _coerce_str(sentiment_level),
        "sentiment_source": _coerce_str(sentiment_source),
    }
    if all(value is None for key, value in payload.items() if key != "trade_date"):
        return 0

    resolved_engine = _resolve_engine(engine)
    if not _table_exists(resolved_engine):
        LOGGER.debug("Table stock_macro_indicators_daily absente ; persistance macro ignorée.")
        return 0

    table = get_macro_indicators_daily_table()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    with resolved_engine.begin() as conn:
        exists = conn.execute(
            select(table.c.trade_date).where(table.c.trade_date == resolved_trade_date).limit(1)
        ).scalar_one_or_none()
        if exists is None:
            conn.execute(table.insert().values(**payload, created_at=now, updated_at=now))
        else:
            conn.execute(
                table.update()
                .where(table.c.trade_date == resolved_trade_date)
                .values(**payload, updated_at=now)
            )
    return 1


def load_macro_indicator_daily_asof(
    *,
    trade_date: Any,
    engine=None,
    strict_before: bool = False,
) -> dict[str, Any] | None:
    resolved_trade_date = _coerce_date(trade_date)
    if resolved_trade_date is None:
        return None

    resolved_engine = _resolve_engine(engine)
    if not _table_exists(resolved_engine):
        return None

    table = get_macro_indicators_daily_table()
    predicate = (
        table.c.trade_date < resolved_trade_date
        if strict_before
        else table.c.trade_date <= resolved_trade_date
    )
    query = (
        select(
            table.c.trade_date,
            table.c.vix,
            table.c.vix9d,
            table.c.vxn,
            table.c.vix3m,
            table.c.move,
            table.c.rvx,
            table.c.ten_y,
            table.c.mode,
            table.c.risk_multiplier,
            table.c.effective_max_positions,
            table.c.allow_new_entries,
            table.c.vix_curve_inverted,
            table.c.yield_10y_5d_pct,
            table.c.sentiment_score,
            table.c.sentiment_level,
            table.c.sentiment_source,
        )
        .where(predicate)
        .order_by(table.c.trade_date.desc())
        .limit(1)
    )
    with resolved_engine.begin() as conn:
        row = conn.execute(query).mappings().first()

    result = cast(dict[str, Any], dict(row)) if row is not None else None
    # ── PIT enrichment (Section 17 Point 2.1) ───────────────────────────
    if result is not None:
        from datetime import datetime, timezone as dt_timezone

        trade_dt = result.get("trade_date")
        if isinstance(trade_dt, date) and not isinstance(trade_dt, datetime):
            trade_dt = datetime.combine(trade_dt, datetime.min.time())
        if isinstance(trade_dt, datetime):
            result["event_time"] = trade_dt.replace(tzinfo=dt_timezone.utc)
            result["available_at"] = trade_dt.replace(
                hour=21, minute=0, second=0, tzinfo=dt_timezone.utc
            )
        result["data_source"] = "macro_indicators"
        result["source_revision"] = None
        result["ingested_at"] = datetime.now(dt_timezone.utc)
        result["data_timezone"] = "America/New_York"
        result["data_quality"] = "present"
    return result


def load_macro_indicator_history_asof(
    *,
    trade_date: Any,
    column: str,
    lookback_days: int,
    engine=None,
    strict_before: bool = False,
) -> list[float] | None:
    resolved_trade_date = _coerce_date(trade_date)
    if resolved_trade_date is None:
        return None
    resolved_column = str(column or "").strip().lower()
    if resolved_column not in _ALLOWED_MACRO_COLUMNS:
        raise ValueError(f"Colonne macro non supportée: {column}")
    resolved_lookback = max(int(lookback_days), 0)
    if resolved_lookback <= 0:
        return None

    resolved_engine = _resolve_engine(engine)
    if not _table_exists(resolved_engine):
        return None

    table = get_macro_indicators_daily_table()
    selected_column = getattr(table.c, resolved_column)
    predicate = (
        table.c.trade_date < resolved_trade_date
        if strict_before
        else table.c.trade_date <= resolved_trade_date
    )
    query = (
        select(table.c.trade_date, selected_column.label("value"))
        .where(predicate)
        .where(selected_column.is_not(None))
        .order_by(table.c.trade_date.desc())
        .limit(resolved_lookback)
    )
    with resolved_engine.begin() as conn:
        rows = list(conn.execute(query).mappings().all())
    if not rows:
        return None
    rows.reverse()
    history = [_coerce_float(row.get("value")) for row in rows]
    filtered = [value for value in history if value is not None]
    return filtered or None


def persist_market_macro_snapshot_daily(
    *,
    trade_date: Any,
    macro_payload: object,
    engine=None,
) -> int:
    payload = macro_payload if isinstance(macro_payload, Mapping) else {}

    def _value(*paths: tuple[Any, ...]) -> Any:
        for path in paths:
            current: Any = payload
            for key in path:
                if not isinstance(current, Mapping):
                    current = None
                    break
                current = current.get(key)
            if current not in (None, ""):
                return current
        return None

    try:
        persisted = persist_macro_indicator_daily(
            trade_date=trade_date,
            vix=_value(("vix",), ("macro", "vix")),
            vix9d=_value(("vix9d",), ("vix_short",), ("macro", "vix_short")),
            vxn=_value(("vxn",), ("macro", "vxn")),
            vix3m=_value(("vix3m",), ("macro", "vix3m")),
            move=_value(("move",), ("macro", "move")),
            rvx=_value(("rvx",), ("macro", "rvx")),
            ten_y=_value(("ten_y",), ("yield_10y",), ("macro", "yield_10y")),
            mode=_value(("mode",)),
            risk_multiplier=_value(("risk_multiplier",)),
            effective_max_positions=_value(("effective_max_positions",)),
            allow_new_entries=_value(("allow_new_entries",)),
            vix_curve_inverted=_value(("vix_curve_inverted",), ("macro", "vix_curve_inverted")),
            yield_10y_5d_pct=_value(("yield_10y_5d_pct",), ("macro", "yield_10y_5d_pct")),
            sentiment_score=_value(("sentiment_score",), ("sentiment", "score")),
            sentiment_level=_value(("sentiment_level",), ("sentiment", "level")),
            sentiment_source=_value(("sentiment_source",), ("sentiment", "source")),
            engine=engine,
        )
    except Exception:
        LOGGER.debug("Persistance stock_macro_indicators_daily indisponible.", exc_info=True)
        return 0
    if persisted:
        LOGGER.info(
            "macro_daily persisted trade_date=%s vix=%s vix9d=%s ten_y=%s mode=%s sentiment_level=%s",
            _coerce_date(trade_date),
            _value(("vix",), ("macro", "vix")),
            _value(("vix9d",), ("vix_short",), ("macro", "vix_short")),
            _value(("ten_y",), ("yield_10y",), ("macro", "yield_10y")),
            _value(("mode",)),
            _value(("sentiment_level",), ("sentiment", "level")),
        )
    return persisted


