from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from functools import lru_cache
from typing import Any

from sqlalchemy import Column, Date, DateTime, Float, MetaData, Table, inspect, select

from database.connection import get_sqlalchemy_engine

LOGGER = logging.getLogger(__name__)


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
    try:
        return inspect(engine).has_table(get_macro_indicators_daily_table().name)
    except Exception:
        return False


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

    resolved_engine = engine or get_sqlalchemy_engine()
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

