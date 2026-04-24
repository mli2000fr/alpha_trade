from __future__ import annotations

from functools import lru_cache
from typing import Any, Iterable

from sqlalchemy import Column, Date, DateTime, Float, MetaData, String, Table, func, select, and_, or_
from sqlalchemy.dialects.mysql import insert as mysql_insert

from database.assets import HISTORY_STATUS_PENDING, HISTORY_STATUS_READY
from database.connection import SessionLocal, get_sqlalchemy_engine


@lru_cache(maxsize=1)
def get_stock_quote_snapshots_table() -> Table:
    metadata = MetaData()
    return Table(
        "stock_quote_snapshots",
        metadata,
        Column("symbol", String(20), primary_key=True),
        Column("quote_date", Date, primary_key=True),
        Column("quote_timestamp", DateTime),
        Column("bid_price", Float),
        Column("ask_price", Float),
        Column("bid_size", Float),
        Column("ask_size", Float),
        Column("spread_bps", Float),
        Column("last_updated", DateTime),
        autoload_with=get_sqlalchemy_engine(),
    )


@lru_cache(maxsize=1)
def get_stock_earnings_calendar_table() -> Table:
    metadata = MetaData()
    return Table(
        "stock_earnings_calendar",
        metadata,
        Column("symbol", String(20), primary_key=True),
        Column("earnings_date", Date, primary_key=True),
        Column("eps_estimate", Float),
        Column("eps_actual", Float),
        Column("revenue_estimate", Float),
        Column("revenue_actual", Float),
        Column("fiscal_period", String(32)),
        Column("last_updated", DateTime),
        autoload_with=get_sqlalchemy_engine(),
    )


def list_active_tradable_symbols(limit: int | None = None) -> list[str]:
    metadata = MetaData()
    stock_metadata = Table("stock_metadata", metadata, autoload_with=get_sqlalchemy_engine())
    filters: list[Any] = [
        stock_metadata.c.status == "active",
        stock_metadata.c.tradable.is_(True),
        stock_metadata.c.bars_available.is_(True),
        stock_metadata.c.asset_class == "us_equity",
    ]
    if "history_status" in stock_metadata.c:
        filters.append(
            or_(
                stock_metadata.c.history_status.is_(None),
                func.trim(stock_metadata.c.history_status) == "",
                func.lower(func.trim(stock_metadata.c.history_status)).in_(
                    (HISTORY_STATUS_PENDING, HISTORY_STATUS_READY)
                ),
            )
        )
    stmt = (
        select(stock_metadata.c.symbol)
        .where(and_(*filters))
        .order_by(stock_metadata.c.symbol)
    )
    if limit is not None:
        stmt = stmt.limit(limit)

    with get_sqlalchemy_engine().connect() as conn:
        return [str(symbol) for symbol in conn.execute(stmt).scalars().all()]


def upsert_quote_snapshots(records: Iterable[dict[str, Any]]) -> int:
    rows = list(records)
    if not rows:
        return 0

    table = get_stock_quote_snapshots_table()
    session = SessionLocal()
    try:
        stmt = mysql_insert(table).values(rows)
        update_dict = {
            "quote_timestamp": stmt.inserted.quote_timestamp,
            "bid_price": stmt.inserted.bid_price,
            "ask_price": stmt.inserted.ask_price,
            "bid_size": stmt.inserted.bid_size,
            "ask_size": stmt.inserted.ask_size,
            "spread_bps": stmt.inserted.spread_bps,
            "last_updated": func.current_timestamp(),
        }
        session.execute(stmt.on_duplicate_key_update(**update_dict))
        session.commit()
        return len(rows)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def upsert_earnings_calendar(records: Iterable[dict[str, Any]]) -> int:
    rows = list(records)
    if not rows:
        return 0

    table = get_stock_earnings_calendar_table()
    session = SessionLocal()
    try:
        stmt = mysql_insert(table).values(rows)
        update_dict = {
            "eps_estimate": stmt.inserted.eps_estimate,
            "eps_actual": stmt.inserted.eps_actual,
            "revenue_estimate": stmt.inserted.revenue_estimate,
            "revenue_actual": stmt.inserted.revenue_actual,
            "fiscal_period": stmt.inserted.fiscal_period,
            "last_updated": func.current_timestamp(),
        }
        session.execute(stmt.on_duplicate_key_update(**update_dict))
        session.commit()
        return len(rows)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

