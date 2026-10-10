"""Fail-closed US new-entry checks. Never reads future labels or sells holdings."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
from sqlalchemy import bindparam, text

from common.market_calendar import _get_nyse_calendar


def entry_sessions(trade_date, *, now=None, min_sessions=61, publication_delay_minutes=15):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError('Horloge sans fuseau horaire')
    if min_sessions < 21 or publication_delay_minutes < 0:
        raise ValueError('Historique requis >= 21 séances ; délai de publication >= 0')
    calendar = _get_nyse_calendar()
    if calendar is None:
        raise ValueError('Calendrier NYSE fiable indisponible')
    end = now.astimezone(timezone.utc).date()
    schedule = calendar.schedule(start_date=end-timedelta(days=max(400, min_sessions*2+30)), end_date=end)
    available = pd.to_datetime(schedule.market_close, utc=True) + pd.Timedelta(minutes=publication_delay_minutes)
    closed = schedule.loc[available.le(pd.Timestamp(now))]
    if closed.empty or trade_date != closed.index[-1].date():
        raise ValueError('Date du signal différente de la dernière séance NYSE clôturée et disponible')
    sessions = [day.date() for day in closed.index[-min_sessions:]]
    if len(sessions) != min_sessions:
        raise ValueError('Calendrier insuffisant pour les indicateurs')
    return sessions


def validate_entry_bars(frame, symbols, sessions, *, now):
    """Every required session must have one real, finite, positive OHLCV bar."""
    rejected = {}
    required = {'symbol', 'date', 'open', 'high', 'low', 'close', 'volume',
                'is_filled', 'data_source', 'data_adjustment', 'ingested_at', 'last_updated'}
    if not required.issubset(frame.columns):
        return {symbol: 'BAR_METADATA_MISSING' for symbol in symbols}
    for symbol in symbols:
        rows = frame.loc[frame.symbol.eq(symbol)].copy()
        days = pd.to_datetime(rows['date'], errors='coerce').dt.date
        if days.duplicated().any() or set(days) != set(sessions):
            rejected[symbol] = 'MISSING_OR_DUPLICATE_SESSIONS'
            continue
        rows = rows.sort_values('date')
        values = rows[['open', 'high', 'low', 'close', 'volume']].apply(pd.to_numeric, errors='coerce')
        if not np.isfinite(values.to_numpy(dtype=float)).all() or not values.gt(0).all().all():
            rejected[symbol] = 'INVALID_OHLCV'
        elif (values.high.lt(values[['open', 'close', 'low']].max(axis=1)).any()
              or values.low.gt(values[['open', 'close', 'high']].min(axis=1)).any()):
            rejected[symbol] = 'INCONSISTENT_OHLC'
        elif not pd.to_numeric(rows.is_filled, errors='coerce').eq(0).all():
            rejected[symbol] = 'SYNTHETIC_OR_UNKNOWN_BAR'
        elif not rows.data_adjustment.eq('split').all() or not rows.data_source.fillna('').str.strip().ne('').all():
            rejected[symbol] = 'UNQUALIFIED_PRICE_SOURCE_OR_ADJUSTMENT'
        elif not pd.concat([values.high-values.low, (values.high-values.close.shift()).abs(),
                            (values.low-values.close.shift()).abs()], axis=1).max(axis=1).tail(20).gt(0).any():
            rejected[symbol] = 'ZERO_TRUE_RANGE_HISTORY'
        else:
            for column in ('ingested_at', 'last_updated'):
                timestamps = pd.to_datetime(rows[column], utc=True, errors='coerce')
                if timestamps.isna().any() or timestamps.gt(pd.Timestamp(now)).any():
                    rejected[symbol] = 'BAR_NOT_YET_AVAILABLE'
                    break
    return rejected


def check_new_entry_data(engine, symbols, trade_date, *, now=None, required_sessions=21, raw_config=None):
    """Returns rejection reasons; a failed SQL/calendar check blocks all entries.

    This is an operational gate at the current decision time, not a historical
    PIT reconstruction: last_updated cannot recover earlier bar revisions.
    """
    symbols = sorted(set(symbols))
    if not symbols:
        return {}
    now = now or datetime.now(timezone.utc)
    try:
        if raw_config is None:
            from common.config_loader import load_config
            raw_config = load_config()
        cfg = raw_config.get('new_entry_data_guard') or {}
        configured_count = cfg.get('min_sessions', 61)
        if isinstance(configured_count, bool) or int(configured_count) < 21:
            raise ValueError('min_sessions doit être un entier >= 21')
        count = max(int(configured_count), required_sessions)
        sessions = entry_sessions(trade_date, now=now, min_sessions=count,
                                  publication_delay_minutes=int(cfg.get('publication_delay_minutes', 15)))
        with engine.connect() as conn:
            if conn.execute(text('SELECT DATABASE()')).scalar() != 'alpha_trade':
                raise ValueError('Contrôle nouvelles entrées US réservé à alpha_trade')
            statement = text('SELECT symbol,date,open,high,low,close,volume,is_filled,data_source,'
                'data_adjustment,ingested_at,last_updated FROM stock_bars_daily '
                'WHERE symbol IN :symbols AND date BETWEEN :start AND :end')
            statement = statement.bindparams(bindparam('symbols', expanding=True))
            frame = pd.read_sql(statement, conn, params={'symbols': symbols, 'start': sessions[0], 'end': sessions[-1]})
        return validate_entry_bars(frame, symbols, sessions, now=now)
    except Exception as exc:
        return {symbol: f'DATA_GUARD_UNAVAILABLE: {exc}' for symbol in symbols}


def validate_entry_prices(prices, symbols, trade_date):
    """Validate the actual price/ATR/ADV objects passed to the sizing engine."""
    rejected = {}
    for symbol in symbols:
        price = prices.get(symbol)
        if (price is None or price.price_asof_date != trade_date or price.atr_asof_date != trade_date):
            rejected[symbol] = 'PRICE_OR_ATR_DATE_UNQUALIFIED'
            continue
        try:
            values = [float(price.last_close), float(price.atr_20), float(price.adv_usd)]
            if not all(np.isfinite(value) and value > 0 for value in values):
                raise ValueError('nonfinite/nonpositive')
        except (TypeError, ValueError):
            rejected[symbol] = 'PRICE_ATR_ADV_INVALID'
    return rejected
