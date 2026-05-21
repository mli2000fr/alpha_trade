from __future__ import annotations

from functools import lru_cache
from typing import Any, Iterable

from sqlalchemy import Column, Date, DateTime, Float, MetaData, String, Table, func
from sqlalchemy.dialects.mysql import insert as mysql_insert

from database.assets import list_eligible_stock_symbols
from database.connection import SessionLocal, get_sqlalchemy_engine


def normalize_symbol_source(symbol_source: str | None) -> str:
    normalized = str(symbol_source or "").strip().lower().replace("_", "-")
    if normalized in {"", "active-tradable", "eligible", "stock-metadata"}:
        return "active-tradable"
    return {
        "stock-scores": "stock-scores",
        "stock-scores-history": "stock-scores-history",
        "stock-scores-all": "stock-scores-all",
        "candidates": "candidates",
        "stock-bars-daily": "stock-bars-daily",
    }.get(normalized, normalized)


@lru_cache(maxsize=1)
def get_stock_quote_snapshots_table() -> Table:
    metadata = MetaData()
    return Table("stock_quote_snapshots", metadata, autoload_with=get_sqlalchemy_engine())


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
    return list_eligible_stock_symbols(limit=limit, engine=get_sqlalchemy_engine())


def list_symbols_for_source(
    symbol_source: str | None = None,
    *,
    limit: int | None = None,
) -> list[str]:
    normalized_source = normalize_symbol_source(symbol_source)
    if normalized_source == "active-tradable":
        return list_active_tradable_symbols(limit=limit)

    if limit is not None and limit < 1:
        raise ValueError("limit doit être supérieur ou égal à 1.")

    from modelFactory.db_registry import load_symbols_for_source

    symbols = load_symbols_for_source(get_sqlalchemy_engine(), normalized_source)
    if limit is not None:
        return symbols[:limit]
    return symbols


def upsert_quote_snapshots(records: Iterable[dict[str, Any]]) -> int:
    rows = list(records)
    if not rows:
        return 0

    table = get_stock_quote_snapshots_table()
    available_columns = {column.name for column in table.columns}
    rows = [{key: value for key, value in row.items() if key in available_columns} for row in rows]
    rows = [row for row in rows if {"symbol", "quote_date"}.issubset(row)]
    if not rows:
        return 0

    session = SessionLocal()
    try:
        stmt = mysql_insert(table).values(rows)
        update_dict = {
            column_name: getattr(stmt.inserted, column_name)
            for column_name in ("quote_timestamp", "bid_price", "ask_price", "bid_size", "ask_size", "spread_bps")
            if column_name in available_columns
        }
        if "last_updated" in available_columns:
            update_dict["last_updated"] = func.current_timestamp()
        if not update_dict:
            first_pk_column = next(iter(table.primary_key.columns), None)
            if first_pk_column is not None:
                update_dict[first_pk_column.name] = getattr(stmt.inserted, first_pk_column.name)
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

