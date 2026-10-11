"""Retrospective price peaks on exact exchange sessions; never a live signal."""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
from sqlalchemy import bindparam, text

from modelFactory.oracle.build_labels import nyse_sessions
from modelFactory.oracle.security_continuity import (
    load_security_discontinuities, path_crosses_known_discontinuity,
)

BAR_COLUMNS = ['date', 'symbol', 'open', 'high', 'low', 'close', 'adj_close',
               'volume', 'is_filled', 'instrument_id', 'data_source', 'data_adjustment']


def _prepare_path(bars, sessions, symbol):
    """Convert each symbol only once per tranche, not for every overlapping J."""
    sessions = pd.DatetimeIndex(sessions).tz_localize(None).normalize()
    data = bars.copy()
    data['date'] = pd.to_datetime(data.date).dt.normalize()
    if data.date.duplicated().any():
        raise ValueError(f'Doublons de barres pour {symbol}')
    values = data.set_index('date').reindex(sessions)
    raw = values[['open', 'high', 'low', 'close', 'adj_close', 'volume', 'is_filled']].apply(
        pd.to_numeric, errors='coerce')
    adjusted = raw.adj_close.where(raw.adj_close.notna(), raw.close)
    factor = adjusted/raw.close
    valid = (np.isfinite(raw[['open', 'high', 'low', 'close']]).all(axis=1)
             & raw[['open', 'high', 'low', 'close']].gt(0).all(axis=1)
             & raw.high.ge(raw[['open', 'close', 'low']].max(axis=1))
             & raw.low.le(raw[['open', 'close', 'high']].min(axis=1))
             & np.isfinite(factor) & factor.gt(0)
             & raw.is_filled.eq(0) & raw.volume.gt(0))
    return {'sessions': sessions, 'positions': {day: i for i, day in enumerate(sessions)},
            'valid': valid.to_numpy(), 'present': raw.close.notna().to_numpy(),
            'close': raw.close.to_numpy(dtype=float), 'adjusted': adjusted.to_numpy(dtype=float),
            'factor': factor.to_numpy(dtype=float), 'high': raw.high.to_numpy(dtype=float),
            'range_review': (raw.high/raw.low >= 1.5).to_numpy(),
            'lineage': {column: values[column].fillna('UNKNOWN').astype(str).str.strip().str.upper().to_numpy()
                        for column in ['instrument_id', 'data_source', 'data_adjustment']}}


def _peak_from_prepared(path, *, symbol, trade_date, horizon, as_of, future_return, registry=None):
    if isinstance(horizon, bool) or not isinstance(horizon, int) or horizon < 1:
        raise ValueError('horizon doit être un entier strictement positif')
    day = pd.Timestamp(trade_date).normalize()
    sessions = path['sessions']
    position = path['positions'].get(day, -1)
    result = {'max_price': None, 'max_date': None, 'reason': None,
              'expected_sessions': horizon, 'observed_sessions': 0}

    def unavailable(reason):
        return {**result, 'reason': reason}

    if position < 0 or position+horizon+1 >= len(sessions):
        return unavailable('OUTSIDE_CALENDAR')
    end, available = sessions[position+horizon], sessions[position+horizon+1]
    if available.date() > as_of:
        return unavailable('NOT_YET_AVAILABLE')
    window = slice(position, position+horizon+1)
    future = slice(position+1, position+horizon+1)
    result['observed_sessions'] = int(path['present'][future].sum())
    if not path['valid'][window].all():
        return unavailable('MISSING_FILLED_OR_INVALID_BAR')
    for column, reason in (
        ('instrument_id', 'IDENTITY_CHANGE_OR_UNKNOWN'),
        ('data_source', 'SOURCE_CHANGE_OR_UNKNOWN'),
        ('data_adjustment', 'ADJUSTMENT_CHANGE_OR_UNKNOWN'),
    ):
        lineage = path['lineage'][column][window]
        if len(set(lineage)) != 1 or lineage[0] in {'', 'UNKNOWN'}:
            return unavailable(reason)
    if path_crosses_known_discontinuity(symbol, day, end, registry or {}):
        return unavailable('KNOWN_IDENTITY_BREAK')
    adjusted = path['adjusted'][window]
    ratios = adjusted[1:]/adjusted[:-1]
    if np.any((ratios >= 20) | (ratios <= .05)):
        return unavailable('UNEXPLAINED_20X_PRICE_BREAK')
    terminal = float(adjusted[-1]/adjusted[0]-1)
    archived = pd.to_numeric(pd.Series([future_return]), errors='coerce').iloc[0]
    if not np.isfinite(archived) or not np.isclose(
            terminal, float(archived), rtol=1e-7, atol=1e-8):
        return unavailable('ARCHIVED_RETURN_VS_CURRENT_BARS_MISMATCH')
    highs = path['high'][future]*path['factor'][future]/path['factor'][position]
    best = int(np.argmax(highs))  # Earliest exchange day if identical peaks.
    peak_day = sessions[position+1+best]
    return {**result, 'max_price': float(highs[best]),
            'max_date': str(peak_day.date()),
            'anchor_close': float(path['close'][position]),
            'anchor_adjustment_factor': float(path['factor'][position]),
            'exit_date': str(end.date()), 'available_date': str(available.date()),
            'large_intraday_range_review': bool(path['range_review'][window].any())}


def price_peak(bars, *, symbol, trade_date, sessions, horizon, as_of,
               future_return, registry=None) -> dict:
    """Maximum HIGH of J+1..J+H, expressed in signal-day price units.

    Per-bar adjusted HIGH is divided by J's adjustment factor. Neither missing
    sessions nor unknown identity/adjustments are filled. Availability follows
    the label contract (first exchange session after the final observation).
    """
    return _peak_from_prepared(_prepare_path(bars, sessions, symbol), symbol=symbol,
        trade_date=trade_date, horizon=horizon, as_of=as_of, future_return=future_return, registry=registry)


def load_price_peaks(engine, selections, labels, *, horizon, as_of: date):
    """Bounded bulk reads for the original TOP-N selections, not replacements."""
    wanted = {day: symbols for day, symbols in selections.items() if symbols}
    output = {day: {} for day in selections}
    if not wanted:
        return output
    sessions = nyse_sessions(min(wanted),
        (pd.Timestamp(max(wanted))+pd.Timedelta(days=3*(horizon+1)+30)).date())
    indexes = sessions.get_indexer(pd.to_datetime(list(wanted)))
    if (indexes < 0).any():
        raise ValueError('Sélection de pics hors séance NYSE')
    end = sessions[max(indexes)+horizon]
    symbols = sorted({symbol for items in wanted.values() for symbol in items})
    query = text(f'SELECT {",".join("`"+c+"`" for c in BAR_COLUMNS)} FROM stock_bars_daily '
                 'WHERE symbol IN :symbols AND `date` BETWEEN :start AND :end').bindparams(
                     bindparam('symbols', expanding=True))
    registry = load_security_discontinuities()
    labels = labels.copy()
    labels['prediction_date'] = pd.to_datetime(labels.prediction_date).dt.strftime('%Y-%m-%d')
    if labels.duplicated(['prediction_date', 'symbol']).any():
        raise ValueError('Doublons labels pour le calcul des pics')
    label_map = labels.set_index(['prediction_date', 'symbol']).to_dict('index')
    with engine.connect() as conn:
        for offset in range(0, len(symbols), 150):
            chunk = symbols[offset:offset+150]
            bars = pd.read_sql(query, conn, params={'symbols': chunk, 'start': min(wanted), 'end': end.date()})
            groups = {symbol: group for symbol, group in bars.groupby('symbol')}
            prepared = {symbol: _prepare_path(groups.get(symbol, bars.iloc[:0]), sessions, symbol) for symbol in chunk}
            for day, selection in wanted.items():
                for symbol in set(selection).intersection(chunk):
                    label = label_map.get((day, symbol), {})
                    if label.get('target_quality_valid') != 1:
                        output[day][symbol] = {'max_price': None, 'reason': 'LABEL_UNQUALIFIED'}
                        continue
                    available = pd.to_datetime(label.get('oracle_available_date'), errors='coerce')
                    if pd.isna(available) or available.date() > as_of:
                        output[day][symbol] = {'max_price': None, 'reason': 'LABEL_NOT_AVAILABLE'}
                        continue
                    output[day][symbol] = _peak_from_prepared(prepared[symbol],
                        symbol=symbol, trade_date=day, horizon=horizon,
                        as_of=as_of, future_return=label.get('future_return'), registry=registry)
    return output
