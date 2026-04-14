from datetime import date
from typing import Optional

import polars as pl
from sqlalchemy import and_, func, insert, select, update
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.engine import Connection

# Les tables doivent être passées en argument (stock_bars_daily, cleaning_audit_log, stock_metadata)


def _latest_audit_id_query(cleaning_audit_log, symbol: str):
    return (
        select(cleaning_audit_log.c.id)
        .where(cleaning_audit_log.c.symbol == symbol)
        .order_by(cleaning_audit_log.c.updated_at.desc())
        .limit(1)
    )


def _active_symbol_clause(stock_metadata):
    return and_(
        stock_metadata.c.status == 'active',
        stock_metadata.c.tradable.is_(True),
        stock_metadata.c.bars_available.is_(True),
    )


def _build_stock_bars_daily_records(symbol: str, df: pl.DataFrame) -> list[dict]:
    return df.select([
        pl.lit(symbol).alias('symbol'),
        pl.col('date'),
        pl.col('open'),
        pl.col('high'),
        pl.col('low'),
        pl.col('close'),
        pl.col('volume'),
        pl.col('adj_close'),
        pl.col('vwap'),
        pl.col('daily_return'),
        pl.col('is_filled'),
    ]).to_dicts()


def get_last_sync_date(conn: Connection, cleaning_audit_log, symbol: str) -> Optional[date]:
    q = (
        select(cleaning_audit_log.c.last_sync_date)
        .where(cleaning_audit_log.c.symbol == symbol)
        .order_by(cleaning_audit_log.c.updated_at.desc())
        .limit(1)
    )
    return conn.execute(q).scalar_one_or_none()


def get_first_last_actual_dates(conn: Connection, stock_bars_daily, symbol: str) -> tuple[Optional[date], Optional[date]]:
    q = select(func.min(stock_bars_daily.c.date), func.max(stock_bars_daily.c.date)).where(stock_bars_daily.c.symbol == symbol)
    mn, mx = conn.execute(q).one_or_none() or (None, None)
    return mn, mx


def get_prev_close_before(conn: Connection, stock_bars_daily, symbol: str, d: date) -> Optional[float]:
    q = (
        select(stock_bars_daily.c.close)
        .where(and_(stock_bars_daily.c.symbol == symbol, stock_bars_daily.c.date < d))
        .order_by(stock_bars_daily.c.date.desc())
        .limit(1)
    )
    return conn.execute(q).scalar_one_or_none()


def upsert_stock_bars_daily(conn: Connection, stock_bars_daily, symbol: str, df: pl.DataFrame) -> int:
    if df.is_empty():
        return 0

    records = _build_stock_bars_daily_records(symbol, df)
    ins = mysql_insert(stock_bars_daily).values(records)
    update_cols = {c.name: ins.inserted[c.name] for c in stock_bars_daily.columns if c.name not in ('symbol', 'date')}
    ondup = ins.on_duplicate_key_update(**update_cols)
    conn.execute(ondup)
    return len(records)


def upsert_audit(
    conn: Connection,
    cleaning_audit_log,
    symbol: str,
    last_sync: Optional[date],
    missing_days: int,
    anomaly_count: int,
    status: str,
    error_msg: Optional[str],
) -> None:
    row_id = conn.execute(_latest_audit_id_query(cleaning_audit_log, symbol)).scalar_one_or_none()
    payload = {
        'symbol': symbol,
        'last_sync_date': last_sync,
        'missing_days_count': missing_days,
        'anomaly_count': anomaly_count,
        'status': status,
        'error_msg': error_msg
    }
    if row_id is None:
        conn.execute(insert(cleaning_audit_log).values(payload))
    else:
        conn.execute(update(cleaning_audit_log).where(cleaning_audit_log.c.id == row_id).values(payload))


def get_symbols(conn: Connection, stock_metadata) -> list[str]:
    q = select(stock_metadata.c.symbol).where(_active_symbol_clause(stock_metadata))
    return [row[0] for row in conn.execute(q).all()]

