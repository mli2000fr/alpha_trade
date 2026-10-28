"""US daily-bar read preference, independent of ingestion and live quote feeds."""
from __future__ import annotations

import logging
import re
from collections.abc import Mapping

import pandas as pd

from common.config_loader import load_config

LOGGER = logging.getLogger(__name__)
SOURCES = {'eodhd': 'eodhd_eod', 'alpaca_sip': 'alpaca_sip'}


def preferred_daily_source(config=None):
    config = load_config() if config is None else config
    market = config.get('market_data', {})
    if not isinstance(market, Mapping):
        raise ValueError('market_data doit être un mapping')
    value = market.get('daily_bars_preferred_source', 'eodhd')
    if not isinstance(value, str) or value not in SOURCES:
        raise ValueError('market_data.daily_bars_preferred_source : eodhd | alpaca_sip')
    return SOURCES[value]


def select_daily_bars(frame, *, config=None, date_column='date', symbol_column='symbol'):
    """Select entire preferred rows, not a price/volume mixture; never fill gaps.

    Unique legacy frames remain supported. Duplicate keys without provenance,
    duplicate rows within one source, or competing unknown feeds fail closed.
    """
    preferred = preferred_daily_source(config)
    if frame.empty:
        return frame.copy()
    keys = [symbol_column, date_column]
    if frame[keys].isna().any().any():
        raise ValueError('Daily bars: null symbol/date')
    duplicate = frame.duplicated(keys, keep=False)
    if not duplicate.any():
        return frame.copy()
    if 'data_source' not in frame:
        raise ValueError('Daily bars: duplicate keys without data_source')
    repeated = frame.loc[duplicate]
    if (repeated.duplicated(keys+['data_source']).any()
            or not repeated.data_source.isin(SOURCES.values()).all()):
        raise ValueError('Daily bars: ambiguous duplicates outside EODHD/Alpaca SIP pair')
    # Only the known pair may compete. Priority applies to all original fields.
    keep = ~duplicate | frame.data_source.eq(preferred)
    result = frame.loc[keep].copy()
    if result.duplicated(keys).any():
        raise ValueError('Daily bars: unresolved duplicate keys')
    LOGGER.info('Daily bars preference=%s removed_alternative_rows=%d', preferred, len(frame)-len(result))
    return result.reset_index(drop=True)


def daily_source_filter(*, alias='stock_bars_daily', date_column='date', config=None):
    """SQL pair selection BEFORE ORDER/LIMIT; known other source fills absent days.

    Caller must apply PIT/freshness filters to candidate and competing rows when
    reconstructing availability; prefer the DataFrame selector in that case.
    """
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', alias) or date_column not in ('date', 'trade_date'):
        raise ValueError('Invalid daily source SQL identifier')
    preferred = preferred_daily_source(config)
    other = next(s for s in SOURCES.values() if s != preferred)
    sql = f'''AND {alias}.data_source IN (:required_data_source, :alternate_data_source)
        AND ({alias}.data_source = :required_data_source OR NOT EXISTS (
            SELECT 1 FROM stock_bars_daily preferred_daily_bar
            WHERE preferred_daily_bar.symbol = {alias}.symbol
              AND preferred_daily_bar.`{date_column}` = {alias}.`{date_column}`
              AND preferred_daily_bar.data_source = :required_data_source))'''
    return sql, dict(required_data_source=preferred, alternate_data_source=other)


def load_daily_close_series(engine, symbol, asof, *, config=None):
    """Qualified raw closes through one completed session, with canonical priority.

    Preserve duplicate/source checks: never average feeds, keep an arbitrary
    duplicate, invent missing sessions or read prices after the decision date.
    """
    from sqlalchemy import text
    cutoff = pd.Timestamp(asof)
    if pd.isna(cutoff) or cutoff.tzinfo is not None or cutoff != cutoff.normalize():
        raise ValueError('Daily close cutoff must be an explicit session date')
    symbol = str(symbol).strip().upper()
    if not symbol:
        raise ValueError('Daily close symbol required')
    with engine.connect() as conn:
        rows = conn.execute(text('SELECT symbol, date, close, data_source FROM stock_bars_daily '
            'WHERE symbol=:symbol AND date<=:asof ORDER BY date'),
            {'symbol': symbol, 'asof': cutoff.date()}).mappings().all()
    frame = pd.DataFrame(rows, columns=['symbol', 'date', 'close', 'data_source'])
    if frame.empty:
        raise ValueError(f'{symbol}: daily closes unavailable')
    if not frame['data_source'].isin(SOURCES.values()).all():
        raise ValueError(f'{symbol}: unqualified daily source')
    frame['date'] = pd.to_datetime(frame['date'], errors='raise')
    frame = select_daily_bars(frame, config=config).sort_values('date')
    values = pd.to_numeric(frame['close'], errors='raise').astype(float)
    import numpy as np
    if (not np.isfinite(values).all() or (values <= 0).any()
            or (frame['date'] > cutoff).any() or frame['date'].max() != cutoff
            or (frame['date'] != frame['date'].dt.normalize()).any()):
        raise ValueError(f'{symbol}: invalid or missing as-of daily close')
    return pd.Series(values.to_numpy(), index=pd.DatetimeIndex(frame['date']), name='close')
