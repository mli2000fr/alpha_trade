from __future__ import annotations

from datetime import date, datetime
from functools import lru_cache
from typing import Any, Iterable

from sqlalchemy import Column, Date, DateTime, Float, MetaData, String, Table, func
from sqlalchemy import text
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
        "candidates": "active-tradable",
        "stock-bars-daily": "stock-bars-daily",
    }.get(normalized, normalized)


def normalize_start_symbol(start_symbol: str | None) -> str | None:
    cleaned = str(start_symbol or "").strip().upper()
    return cleaned or None


def filter_symbols_from_start(
    symbols: Iterable[str],
    *,
    start_symbol: str | None = None,
) -> list[str]:
    normalized_start = normalize_start_symbol(start_symbol)
    normalized_symbols = [str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()]
    if normalized_start is None:
        return normalized_symbols
    return [symbol for symbol in normalized_symbols if symbol >= normalized_start]


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


def list_active_tradable_symbols(
    limit: int | None = None,
    *,
    start_symbol: str | None = None,
) -> list[str]:
    symbols = list_eligible_stock_symbols(
        limit=None if normalize_start_symbol(start_symbol) is not None else limit,
        engine=get_sqlalchemy_engine(),
    )
    filtered = filter_symbols_from_start(symbols, start_symbol=start_symbol)
    if limit is not None:
        return filtered[:limit]
    return filtered


def list_symbols_for_source(
    symbol_source: str | None = None,
    *,
    limit: int | None = None,
    start_symbol: str | None = None,
) -> list[str]:
    normalized_source = normalize_symbol_source(symbol_source)
    if normalized_source == "active-tradable":
        return list_active_tradable_symbols(limit=limit, start_symbol=start_symbol)

    if limit is not None and limit < 1:
        raise ValueError("limit doit être supérieur ou égal à 1.")

    from modelFactory.db_registry import load_symbols_for_source

    symbols = load_symbols_for_source(get_sqlalchemy_engine(), normalized_source)
    symbols = filter_symbols_from_start(symbols, start_symbol=start_symbol)
    if limit is not None:
        return symbols[:limit]
    return symbols


def upsert_quote_snapshots(records: Iterable[dict[str, Any]]) -> int:
    rows = list(records)
    if not rows:
        return 0

    table = get_stock_quote_snapshots_table()
    available_columns = {column.name for column in table.columns.values()}
    rows = [{key: value for key, value in row.items() if key in available_columns} for row in rows]
    rows = [row for row in rows if {"symbol", "quote_date"}.issubset(row)]
    if not rows:
        return 0

    session = SessionLocal()
    try:
        stmt = mysql_insert(table).values(rows)
        inserted_updates: dict[str, Any] = {}
        if "quote_timestamp" in available_columns:
            inserted_updates["quote_timestamp"] = stmt.inserted.quote_timestamp
        if "bid_price" in available_columns:
            inserted_updates["bid_price"] = stmt.inserted.bid_price
        if "ask_price" in available_columns:
            inserted_updates["ask_price"] = stmt.inserted.ask_price
        if "bid_size" in available_columns:
            inserted_updates["bid_size"] = stmt.inserted.bid_size
        if "ask_size" in available_columns:
            inserted_updates["ask_size"] = stmt.inserted.ask_size
        if "spread_bps" in available_columns:
            inserted_updates["spread_bps"] = stmt.inserted.spread_bps
        update_dict: dict[str, Any] = dict(inserted_updates)
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


def _coerce_sql_date(value: object) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _collapse_contiguous_dates(
    dates: Iterable[date],
    *,
    expected_order: Iterable[date] | None = None,
) -> list[tuple[date, date]]:
    expected_sequence = list(dict.fromkeys(expected_order or ()))
    if expected_sequence:
        expected_positions = {value: index for index, value in enumerate(expected_sequence)}
        ordered_dates = sorted({value for value in dates}, key=lambda value: expected_positions.get(value, 10**9))
    else:
        ordered_dates = sorted({value for value in dates})
        expected_positions = {value: index for index, value in enumerate(ordered_dates)}
    if not ordered_dates:
        return []

    ranges: list[tuple[date, date]] = []
    range_start = ordered_dates[0]
    range_end = ordered_dates[0]
    for current in ordered_dates[1:]:
        if expected_positions.get(current) == expected_positions.get(range_end, -1) + 1:
            range_end = current
            continue
        ranges.append((range_start, range_end))
        range_start = current
        range_end = current
    ranges.append((range_start, range_end))
    return ranges


def get_quote_snapshot_resume_state(
    symbol: str,
    *,
    from_date: date,
    to_date: date,
    expected_dates: Iterable[date] | None = None,
) -> dict[str, object]:
    cleaned_symbol = str(symbol or "").strip().upper()
    if not cleaned_symbol:
        return {
            "symbol": cleaned_symbol,
            "has_expected_days": False,
            "is_complete": True,
            "expected_days": 0,
            "stored_days": 0,
            "missing_days": 0,
            "first_missing_date": None,
        }

    engine = get_sqlalchemy_engine()
    params = {
        "symbol": cleaned_symbol,
        "from_date": from_date,
        "to_date": to_date,
    }
    with engine.connect() as conn:
        stored_raw = conn.execute(
            text(
                """
                SELECT DISTINCT quote_date
                FROM stock_quote_snapshots
                WHERE symbol = :symbol
                  AND quote_date BETWEEN :from_date AND :to_date
                ORDER BY quote_date
                """
            ),
            params,
        ).scalars().all()

    expected_sequence: list[date] = [
        normalized
        for raw in (expected_dates or ())
        if (normalized := _coerce_sql_date(raw)) is not None and from_date <= normalized <= to_date
    ]
    expected_dates_set = set(expected_sequence)
    stored_dates: set[date] = {
        normalized
        for raw in stored_raw
        if (normalized := _coerce_sql_date(raw)) is not None
    }
    missing_dates: list[date] = sorted(expected_dates_set.difference(stored_dates))
    missing_ranges = _collapse_contiguous_dates(missing_dates, expected_order=expected_sequence)
    return {
        "symbol": cleaned_symbol,
        "has_expected_days": bool(expected_dates_set),
        "is_complete": bool(expected_dates_set) and not missing_dates,
        "expected_days": len(expected_dates_set),
        "stored_days": len(expected_dates_set.intersection(stored_dates)),
        "missing_days": len(missing_dates),
        "first_missing_date": missing_dates[0] if missing_dates else None,
        "missing_ranges": missing_ranges,
    }


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

