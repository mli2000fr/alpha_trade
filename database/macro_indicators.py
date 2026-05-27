from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import date, datetime, timezone
from functools import lru_cache
from typing import Any

from sqlalchemy import Column, Date, DateTime, Float, MetaData, Table, inspect, select

from database.connection import get_sqlalchemy_engine

LOGGER = logging.getLogger(__name__)
_ALLOWED_MACRO_COLUMNS = {"vix", "vix9d", "ten_y"}


@lru_cache(maxsize=1)
def get_macro_indicators_daily_table() -> Table:
    metadata = MetaData()
    return Table(
        "stock_macro_indicators_daily",
        metadata,
        Column("trade_date", Date, primary_key=True),
        Column("vix", Float, nullable=True),
        Column("vix9d", Float, nullable=True),
        Column("ten_y", Float, nullable=True),
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
    ten_y: Any = None,
    engine=None,
) -> int:
    resolved_trade_date = _coerce_date(trade_date)
    if resolved_trade_date is None:
        return 0

    payload = {
        "trade_date": resolved_trade_date,
        "vix": _coerce_float(vix),
        "vix9d": _coerce_float(vix9d),
        "ten_y": _coerce_float(ten_y),
    }
    if payload["vix"] is None and payload["vix9d"] is None and payload["ten_y"] is None:
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
        select(table.c.trade_date, table.c.vix, table.c.vix9d, table.c.ten_y)
        .where(predicate)
        .order_by(table.c.trade_date.desc())
        .limit(1)
    )
    with resolved_engine.begin() as conn:
        row = conn.execute(query).mappings().first()
    return dict(row) if row is not None else None


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
    try:
        persisted = persist_macro_indicator_daily(
            trade_date=trade_date,
            vix=payload.get("vix"),
            vix9d=payload.get("vix_short"),
            ten_y=payload.get("yield_10y"),
            engine=engine,
        )
    except Exception:
        LOGGER.debug("Persistance stock_macro_indicators_daily indisponible.", exc_info=True)
        return 0
    if persisted:
        LOGGER.info(
            "macro_daily persisted trade_date=%s vix=%s vix9d=%s ten_y=%s",
            _coerce_date(trade_date),
            payload.get("vix"),
            payload.get("vix_short"),
            payload.get("yield_10y"),
        )
    return persisted


