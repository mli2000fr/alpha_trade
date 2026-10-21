"""Research-only H10/H20 targets and frozen causal feature eligibility.

Production path modules stay fixed H20. No module-global monkeypatch or serving
change. Future-quality exclusions affect labels, never score/rank membership.
"""
import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view


def feature_eligible(frame, reserves, columns):
    good = pd.Series(np.isfinite(frame[columns].to_numpy(float)).all(axis=1), index=frame.index)
    for event in reserves:
        good &= ~(frame.symbol.eq(event['symbol']) & frame.date.ge(pd.Timestamp(event['start'])))
    return good


def symbol_targets(bars, sessions, *, horizon, start, end, identity_events=(), price_reserve=None):
    if type(horizon) is not int or horizon not in (10, 20): raise ValueError('H10/H20 only')
    if bars.duplicated('date').any(): raise ValueError('Duplicate price date')
    symbol = str(bars.symbol.iloc[0]); days = pd.DatetimeIndex(sessions)
    if len(days) <= horizon: raise ValueError('Short calendar')
    grid = bars.set_index('date').reindex(days)
    raw = grid[['open', 'high', 'low', 'close', 'adj_close', 'volume', 'is_filled']].apply(pd.to_numeric, errors='coerce')
    adjusted = raw.adj_close.where(raw.adj_close.notna(), raw.close); factor = adjusted/raw.close
    good = (np.isfinite(raw[['open', 'high', 'low', 'close']]).all(axis=1) & raw[['open', 'high', 'low', 'close']].gt(0).all(axis=1)
        & raw.high.ge(raw[['open', 'close', 'low']].max(axis=1)) & raw.low.le(raw[['open', 'close', 'high']].min(axis=1))
        & np.isfinite(factor) & factor.gt(0) & raw.volume.gt(0) & raw.is_filled.eq(0))
    n = len(days)-horizon; dates = days[:n]
    with np.errstate(divide='ignore', invalid='ignore'):
        close = sliding_window_view(adjusted.to_numpy(float), horizon+1)
        high = sliding_window_view((raw.high*factor).to_numpy(float), horizon+1)[:, 1:]
        low = sliding_window_view((raw.low*factor).to_numpy(float), horizon+1)[:, 1:]
        up = np.maximum(0., high.max(axis=1)/close[:, 0]-1)
        down = np.maximum(0., 1-low.min(axis=1)/close[:, 0])
        ratios = close[:, 1:]/close[:, :-1]; terminal = close[:, -1]/close[:, 0]-1
    reasons = np.full(n, '', dtype=object)
    def reject(mask, reason): reasons[(reasons == '') & mask] = reason
    reject(~sliding_window_view(good.to_numpy(), horizon+1).all(axis=1), 'INVALID_OR_MISSING_PATH')
    for field in ('instrument_id', 'data_source', 'data_adjustment'):
        codes = pd.factorize(grid[field])[0]; w = sliding_window_view(codes, horizon+1)
        stable = (w == w[:, :1]).all(axis=1) & (w[:, 0] >= 0)
        if field != 'instrument_id': stable &= ~grid[field].iloc[:n].astype(str).str.upper().isin(['UNKNOWN', '']).to_numpy()
        reject(~stable, 'UNKNOWN_OR_CHANGED_'+field.upper())
    reject(((ratios >= 20) | (ratios <= .05)).any(axis=1), 'UNEXPLAINED_20X_PRICE_BREAK')
    for event in identity_events:
        reject((dates <= pd.Timestamp(event['last_predecessor_date'])) & (days[horizon:] >= pd.Timestamp(event['first_successor_date'])), 'KNOWN_IDENTITY_BREAK')
    if price_reserve:
        reject(days[horizon:] >= pd.Timestamp(price_reserve['start']), 'UNRESOLVED_PRICE_OR_DISTRIBUTION_BASIS')
    available = pd.Series(days).shift(-(horizon+1)).iloc[:n].to_numpy()
    reject(pd.isna(available) | (available > np.datetime64(pd.Timestamp(end))), 'IMMATURE_WINDOW')
    f = pd.DataFrame(dict(date=dates, symbol=symbol, path_qualified=reasons == '', path_quality_reason=reasons,
        oracle_exit_date=days[horizon:], oracle_available_date=available, up_excursion=up, down_excursion=down,
        path_amplitude=np.maximum(up, down), terminal_return=terminal))
    f = f[f.date.between(pd.Timestamp(start), pd.Timestamp(end)) & good.iloc[:n].to_numpy()]
    for column in ('up_excursion', 'down_excursion', 'path_amplitude', 'terminal_return'):
        f.loc[~f.path_qualified, column] = np.nan
    return f.reset_index(drop=True), grid, good


def frozen_annual_dates(days, year, train_size=504, val_size=126, embargo=21):
    days = pd.DatetimeIndex(days)
    start = days.searchsorted(pd.Timestamp(f'{year}-01-01'))
    val_end = start-embargo-1
    val = days[val_end-val_size+1:val_end+1]
    train_end = days.get_indexer([val[0]])[0]-embargo-1
    train = days[train_end-train_size+1:train_end+1]
    if len(train) != train_size or len(val) != val_size: raise ValueError('Insufficient common history')
    return dict(train=train, val=val, test=days[(days >= f'{year}-01-01') & (days <= min(f'{year}-12-31', '2026-09-01'))])
