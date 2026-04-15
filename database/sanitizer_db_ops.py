import logging
import math
from datetime import date, datetime, time
from typing import Optional

import polars as pl
from sqlalchemy import and_, func, insert, select, update
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.engine import Connection

# Les tables doivent être passées en argument (stock_bars_daily, cleaning_audit_log, stock_metadata)


LOGGER = logging.getLogger(__name__)
MYSQL_TEXT_MAX_BYTES = 65_535


def _latest_audit_id_query(cleaning_audit_log, symbol: str):
    return (
        select(cleaning_audit_log.c.id)
        .where(cleaning_audit_log.c.symbol == symbol)
        .order_by(cleaning_audit_log.c.updated_at.desc(), cleaning_audit_log.c.id.desc())
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


def _normalize_mysql_scalar(value):
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _normalize_mysql_records(records: list[dict]) -> tuple[list[dict], dict[str, int]]:
    normalized_records: list[dict] = []
    non_finite_counts: dict[str, int] = {}

    for record in records:
        normalized_record: dict = {}
        for key, value in record.items():
            normalized_value = _normalize_mysql_scalar(value)
            if normalized_value is None and isinstance(value, float) and not math.isfinite(value):
                non_finite_counts[key] = non_finite_counts.get(key, 0) + 1
            normalized_record[key] = normalized_value
        normalized_records.append(normalized_record)

    return normalized_records, non_finite_counts


def _truncate_utf8_text(value: str, max_bytes: int) -> str:
    encoded = value.encode('utf-8')
    if len(encoded) <= max_bytes:
        return value

    suffix_template = ' … [truncated, original_bytes={original_bytes}]'
    suffix = suffix_template.format(original_bytes=len(encoded))
    suffix_bytes = suffix.encode('utf-8')
    budget = max(max_bytes - len(suffix_bytes), 0)
    truncated = encoded[:budget]
    while truncated:
        try:
            return truncated.decode('utf-8') + suffix
        except UnicodeDecodeError:
            truncated = truncated[:-1]
    return suffix[:max_bytes]


def _resolve_error_msg_max_bytes(cleaning_audit_log) -> int:
    column = cleaning_audit_log.c.error_msg
    length = getattr(column.type, 'length', None)
    if isinstance(length, int) and length > 0:
        return length
    return MYSQL_TEXT_MAX_BYTES


def _normalize_error_msg(cleaning_audit_log, error_msg: Optional[str]) -> Optional[str]:
    if error_msg is None:
        return None
    normalized = error_msg.strip()
    if not normalized:
        return None
    return _truncate_utf8_text(normalized, _resolve_error_msg_max_bytes(cleaning_audit_log))


def _build_mysql_update_cols(table, insert_stmt, record_keys: set[str], key_columns: set[str]) -> dict:
    update_cols = {
        column.name: insert_stmt.inserted[column.name]
        for column in table.columns
        if column.name in record_keys and column.name not in key_columns
    }
    if 'last_updated' in table.c and 'last_updated' not in key_columns:
        update_cols['last_updated'] = func.current_timestamp()
    return update_cols


def _coerce_start_timestamp(start: Optional[date | datetime]) -> Optional[datetime]:
    if start is None:
        return None
    if isinstance(start, datetime):
        return start
    return datetime.combine(start, time.min)


def get_stock_bars(
    conn: Connection,
    stock_bars,
    symbol: str,
    timeframe: str,
    start: Optional[date | datetime] = None,
) -> list[dict]:
    """Retourne les bars `stock_bars` triés par timestamp au format attendu par le pipeline."""
    start_ts = _coerce_start_timestamp(start)
    q = (
        select(
            stock_bars.c.timestamp.label('t'),
            stock_bars.c.open_price.label('o'),
            stock_bars.c.high_price.label('h'),
            stock_bars.c.low_price.label('l'),
            stock_bars.c.close_price.label('c'),
            stock_bars.c.volume.label('v'),
            stock_bars.c.trade_count.label('n'),
            stock_bars.c.vwa_price.label('vw'),
        )
        .where(
            and_(
                stock_bars.c.symbol == symbol,
                stock_bars.c.timeframe == timeframe,
            )
        )
        .order_by(stock_bars.c.timestamp.asc())
    )
    if start_ts is not None:
        q = q.where(stock_bars.c.timestamp >= start_ts)

    rows = conn.execute(q).mappings().all()
    return [
        {
            't': row['t'],
            'o': float(row['o']),
            'h': float(row['h']),
            'l': float(row['l']),
            'c': float(row['c']),
            'v': int(row['v']),
            'n': int(row['n']) if row['n'] is not None else 0,
            'vw': float(row['vw']) if row['vw'] is not None else None,
        }
        for row in rows
    ]


def get_last_sync_date(conn: Connection, cleaning_audit_log, symbol: str) -> Optional[date]:
    q = (
        select(cleaning_audit_log.c.last_sync_date)
        .where(cleaning_audit_log.c.symbol == symbol)
        .order_by(cleaning_audit_log.c.updated_at.desc())
        .limit(1)
    )
    return conn.execute(q).scalar_one_or_none()


def get_failed_audits(conn: Connection, cleaning_audit_log, limit: Optional[int] = 20) -> list[dict]:
    q = (
        select(
            cleaning_audit_log.c.symbol,
            cleaning_audit_log.c.last_sync_date,
            cleaning_audit_log.c.status,
            cleaning_audit_log.c.error_msg,
            cleaning_audit_log.c.updated_at,
        )
        .where(cleaning_audit_log.c.status == 'failed')
        .order_by(cleaning_audit_log.c.updated_at.desc(), cleaning_audit_log.c.id.desc())
    )
    if limit is not None:
        q = q.limit(limit)

    return [dict(row) for row in conn.execute(q).mappings().all()]


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

    records, non_finite_counts = _normalize_mysql_records(_build_stock_bars_daily_records(symbol, df))
    if non_finite_counts:
        LOGGER.warning(
            'Valeurs non finies neutralisées avant upsert stock_bars_daily | symbol=%s columns=%s',
            symbol,
            non_finite_counts,
        )
    ins = mysql_insert(stock_bars_daily).values(records)
    update_cols = _build_mysql_update_cols(
        stock_bars_daily,
        ins,
        set(records[0].keys()),
        {'symbol', 'date'},
    )
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
    normalized_error_msg = _normalize_error_msg(cleaning_audit_log, error_msg)
    payload = {
        'symbol': symbol,
        'last_sync_date': last_sync,
        'missing_days_count': missing_days,
        'anomaly_count': anomaly_count,
        'status': status,
        'error_msg': normalized_error_msg
    }
    if status == 'failed':
        LOGGER.error(
            "Audit en échec | symbol=%s row_id=%s last_sync=%s missing_days=%s anomaly_count=%s error_msg=%s",
            symbol,
            row_id,
            last_sync,
            missing_days,
            anomaly_count,
            normalized_error_msg,
        )
    if row_id is None:
        conn.execute(insert(cleaning_audit_log).values(payload))
    else:
        conn.execute(update(cleaning_audit_log).where(cleaning_audit_log.c.id == row_id).values(payload))


def sync_audit_to_stock_scores(
    conn: Connection,
    stock_scores,
    symbol: str,
    missing_days: int,
    anomaly_count: int,
) -> int:
    result = conn.execute(
        update(stock_scores)
        .where(stock_scores.c.symbol == symbol)
        .values(
            missing_days_count=missing_days,
            anomaly_count=anomaly_count,
            last_updated_audit=func.current_timestamp(),
        )
    )
    return result.rowcount or 0


def get_symbols(conn: Connection, stock_metadata) -> list[str]:
    q = select(stock_metadata.c.symbol).where(_active_symbol_clause(stock_metadata))
    return [row[0] for row in conn.execute(q).all()]

