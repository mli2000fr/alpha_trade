import logging
import math
from datetime import date, datetime, time, timezone
from typing import Optional

import polars as pl
from sqlalchemy import and_, func, insert, select, update
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.engine import Connection

from database.assets import build_eligible_stock_metadata_filters

# Les tables doivent être passées en argument (stock_bars_daily, cleaning_audit_latest, cleaning_audit_runs, stock_metadata)


LOGGER = logging.getLogger(__name__)
def _active_symbol_clause(stock_metadata):
    return and_(*build_eligible_stock_metadata_filters(stock_metadata))


def _build_stock_bars_daily_records(
    symbol: str,
    df: pl.DataFrame,
    data_adjustment: str = "split",
) -> list[dict]:
    """
    Construit les enregistrements à upsert dans stock_bars_daily.

    :param data_adjustment: Paramètre adjustment Alpaca utilisé lors de l'ingestion
        ('raw' | 'split' | 'dividend' | 'all'). Persisté pour traçabilité (versioning).
    """
    ingested_at = datetime.now(timezone.utc).replace(tzinfo=None)
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
        pl.lit(ingested_at).alias('ingested_at'),
        pl.lit(data_adjustment).alias('data_adjustment'),
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


def get_last_sync_date(conn: Connection, cleaning_audit_latest, symbol: str) -> Optional[date]:
    q = (
        select(cleaning_audit_latest.c.last_sync_date)
        .where(cleaning_audit_latest.c.symbol == symbol)
        .limit(1)
    )
    return conn.execute(q).scalar_one_or_none()


def get_failed_audits(conn: Connection, cleaning_audit_latest, limit: Optional[int] = 20) -> list[dict]:
    q = (
        select(
            cleaning_audit_latest.c.symbol,
            cleaning_audit_latest.c.last_sync_date,
            cleaning_audit_latest.c.status,
            cleaning_audit_latest.c.error_message,
            cleaning_audit_latest.c.latest_run_at,
        )
        .where(cleaning_audit_latest.c.status == 'failed')
        .order_by(cleaning_audit_latest.c.latest_run_at.desc(), cleaning_audit_latest.c.symbol.asc())
    )
    if limit is not None:
        q = q.limit(limit)

    return [dict(row) for row in conn.execute(q).mappings().all()]


def get_first_last_actual_dates(conn: Connection, stock_bars_daily, symbol: str) -> tuple[Optional[date], Optional[date]]:
    q = select(func.min(stock_bars_daily.c.date), func.max(stock_bars_daily.c.date)).where(stock_bars_daily.c.symbol == symbol)
    mn, mx = conn.execute(q).one_or_none() or (None, None)
    return mn, mx


def get_last_actual_daily_date(conn: Connection, stock_bars_daily, symbol: str) -> Optional[date]:
    q = select(func.max(stock_bars_daily.c.date)).where(stock_bars_daily.c.symbol == symbol)
    return conn.execute(q).scalar_one_or_none()


def get_prev_close_before(conn: Connection, stock_bars_daily, symbol: str, d: date) -> Optional[float]:
    q = (
        select(stock_bars_daily.c.close)
        .where(and_(stock_bars_daily.c.symbol == symbol, stock_bars_daily.c.date < d))
        .order_by(stock_bars_daily.c.date.desc())
        .limit(1)
    )
    return conn.execute(q).scalar_one_or_none()


def upsert_stock_bars_daily(
    conn: Connection,
    stock_bars_daily,
    symbol: str,
    df: pl.DataFrame,
    data_adjustment: str = "split",
) -> int:
    """
    :param data_adjustment: Valeur du paramètre adjustment Alpaca ('raw'|'split'|'dividend'|'all').
        Persisté dans la colonne data_adjustment pour versioning et auditabilité.
    """
    if df.is_empty():
        return 0

    records, non_finite_counts = _normalize_mysql_records(
        _build_stock_bars_daily_records(symbol, df, data_adjustment=data_adjustment)
    )
    if non_finite_counts:
        LOGGER.warning(
            'Valeurs non finies neutralisees avant upsert stock_bars_daily | symbol=%s columns=%s',
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
    cleaning_audit_latest,
    cleaning_audit_runs,
    symbol: str,
    last_sync: Optional[date],
    missing_days: Optional[int],
    anomaly_count: Optional[int],
    status: str,
    error_message: Optional[str] = None,
) -> None:
    payload = {
        'symbol': symbol,
        'last_sync_date': last_sync,
        'missing_days_count': missing_days,
        'anomaly_count': anomaly_count,
        'status': status,
        'error_message': error_message,
    }
    if status == 'failed':
        LOGGER.error(
            "Audit en echec | symbol=%s last_sync=%s missing_days=%s anomaly_count=%s error=%s",
            symbol,
            last_sync,
            missing_days,
            anomaly_count,
            error_message,
        )
    conn.execute(insert(cleaning_audit_runs).values(payload))

    symbol_exists = conn.execute(
        select(cleaning_audit_latest.c.symbol)
        .where(cleaning_audit_latest.c.symbol == symbol)
        .limit(1)
    ).scalar_one_or_none()
    if symbol_exists is None:
        conn.execute(insert(cleaning_audit_latest).values(payload))
    else:
        conn.execute(
            update(cleaning_audit_latest)
            .where(cleaning_audit_latest.c.symbol == symbol)
            .values(payload)
        )


def sync_audit_to_stock_scores(
    conn: Connection,
    stock_scores,
    symbol: str,
    missing_days: Optional[int],
    anomaly_count: Optional[int],
    sanitizer_status: str,
) -> int:
    """
    Met à jour stock_scores avec les compteurs d'audit du dernier run traité.
    Les valeurs ÉCRASENT l'état précédent pour refléter le snapshot le plus récent.
    N'est appelé que si was_processed=True (nouvelles barres effectivement traitées).
    """
    result = conn.execute(
        update(stock_scores)
        .where(stock_scores.c.symbol == symbol)
        .values(
            missing_days_count=missing_days,
            anomaly_count=anomaly_count,
            sanitizer_status=sanitizer_status,
            last_updated_audit=func.current_timestamp(),
        )
    )
    return result.rowcount or 0


def get_symbols(conn: Connection, stock_metadata) -> list[str]:
    q = select(stock_metadata.c.symbol).where(_active_symbol_clause(stock_metadata))
    return [row[0] for row in conn.execute(q).all()]

