"""Shared optional Oracle/ATR amplitude gate for backtest and live (read-only)."""
from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import bindparam, text

LOGGER = logging.getLogger(__name__)


def resolve_oracle_atr_enabled(value: Any = True) -> bool:
    if not isinstance(value, bool):
        raise ValueError('cascade.oracle_atr_enabled doit être un booléen YAML true/false')
    return value


def atr20_percent_panel(bars: pd.DataFrame) -> pd.DataFrame:
    """Same adjusted rolling-mean TR as ML features, with 21 valid observed bars."""
    if bars.empty:
        return pd.DataFrame(columns=['date', 'symbol', 'atr20_pct'])
    data = bars.copy()
    data['date'] = pd.to_datetime(data.date).dt.normalize()
    data['symbol'] = data.symbol.astype(str).str.strip().str.upper()
    if data.duplicated(['date', 'symbol']).any():
        raise ValueError('Doublons OHLC pour le filtre Oracle/ATR')
    data = data.sort_values(['symbol', 'date']).reset_index(drop=True)
    for col in ['high', 'low', 'close', 'adj_close']:
        data[col] = pd.to_numeric(data[col], errors='coerce')
    valid = (np.isfinite(data[['high', 'low', 'close', 'adj_close']]).all(axis=1)
             & data[['high', 'low', 'close', 'adj_close']].gt(0).all(axis=1)
             & data.high.ge(data.low))
    if 'is_filled' in data:
        valid &= ~data.is_filled.fillna(True).astype(bool)
    ratio = (data.adj_close / data.close).where(valid)
    high, low, close = data.high * ratio, data.low * ratio, data.adj_close.where(valid)
    prev = close.groupby(data.symbol).shift(1)
    tr = pd.concat([high-low, (high-prev).abs(), (low-prev).abs()], axis=1).max(axis=1).where(valid)
    atr = tr.groupby(data.symbol).transform(lambda s: s.rolling(20, min_periods=20).mean())
    support = valid.astype(int).groupby(data.symbol).transform(lambda s: s.rolling(21, min_periods=21).sum()).eq(21)
    data['atr20_pct'] = (atr / close).where(support)
    return data[['date', 'symbol', 'atr20_pct']]


def load_oracle_atr_by_date(engine: Any, symbols: list[str], dates: list[str]) -> dict[str, dict[str, float]]:
    """One bulk history load per backtest, or one bounded history load live."""
    if not dates or not symbols:
        return {}
    if engine is None:
        raise RuntimeError('Filtre Oracle/ATR actif : connexion prix requise')
    target = {str(day)[:10] for day in dates}
    start = (pd.Timestamp(min(target)) - pd.Timedelta(days=90)).date()
    end = pd.Timestamp(max(target)).date()
    symbols = sorted({str(s).strip().upper() for s in symbols})
    query = text('SELECT date,symbol,high,low,close,adj_close FROM stock_bars_daily '
                 'WHERE symbol IN :symbols AND date BETWEEN :start AND :end').bindparams(bindparam('symbols', expanding=True))
    output: dict[str, dict[str, float]] = {day: {} for day in target}
    with engine.connect() as conn:
        for offset in range(0, len(symbols), 150):
            bars = pd.read_sql(query, conn, params={'symbols': symbols[offset:offset+150], 'start': start, 'end': end})
            panel = atr20_percent_panel(bars)
            if panel.empty:
                continue
            panel['day'] = panel.date.dt.strftime('%Y-%m-%d')
            panel = panel[panel.day.isin(target) & panel.atr20_pct.notna() & panel.atr20_pct.gt(0)]
            for row in panel.itertuples():
                output[row.day][row.symbol] = float(row.atr20_pct)
    return output


def filter_oracle_atr_percentiles(percentiles: dict[str, float], atr_values: dict[str, float],
                                  *, oracle_pool_pct: float = .20, trade_date: str = '') -> tuple[dict[str, float], dict[str, int]]:
    """Intersect Oracle gate with ATR TOP20; preserve original Oracle percentiles."""
    oracle = {s for s, p in percentiles.items() if p >= 1.0-oracle_pool_pct}
    values = {s: float(atr_values[s]) for s in percentiles if s in atr_values
              and atr_values[s] is not None and np.isfinite(float(atr_values[s])) and float(atr_values[s]) > 0}
    if percentiles and not values:
        raise RuntimeError(f'Filtre Oracle/ATR actif : aucun ATR20/prix valide à {trade_date}')
    ranks = pd.Series(values, dtype=float).rank(pct=True)
    atr_top = set(ranks[ranks.ge(.80)].index)
    kept = oracle & atr_top
    diag = {'rank_population': len(percentiles), 'atr_valid': len(values),
            'atr_missing': len(percentiles)-len(values), 'oracle_before': len(oracle),
            'atr_top20': len(atr_top), 'intersection': len(kept), 'rejected': len(oracle)-len(kept)}
    LOGGER.info('ORACLE_ATR date=%s period=20 atr_top_pct=0.20 %s', trade_date, diag)
    return {s: p for s, p in percentiles.items() if s in kept}, diag
