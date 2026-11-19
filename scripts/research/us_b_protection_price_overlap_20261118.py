"""Bounded post-run check of missing/zero daily volume on actual held dates.

This is an additional anomaly screen, not certification of all historical prices.
No market data are changed, downloaded or substituted.
"""
import json
import numpy as np
import pandas as pd

from scripts.research.us_b_protection_partial_20261118 import ROOT as PRIMARY, CASES
from scripts.research.us_b_protection_timing_replay_20261118 import ROOT, CASE
from scripts.research.us_q051_b_early_sl_20261116 import FULL


def main():
    volume = pd.read_parquet(FULL / 'inputs/volume.parquet')
    rows = []
    checks = []
    for root, case in [(PRIMARY, k) for k in CASES] + [(ROOT, CASE)]:
        folder = root / 'cases' / case / 'result'
        equity = pd.read_csv(folder / 'equity-daily.csv', index_col=0, parse_dates=True)
        events = pd.read_csv(folder / 'events.csv')
        flows = events[events.event.isin(['BUY_FILL', 'SELL_FILL'])].copy()
        flows['day'] = pd.to_datetime(flows.time, utc=True).dt.tz_convert('America/New_York').dt.tz_localize(None).dt.normalize()
        flows['delta'] = flows.quantity * np.where(flows.event.eq('BUY_FILL'), 1, -1)
        changes = flows.pivot_table(index='day', columns='symbol', values='delta', aggfunc='sum', fill_value=0)
        positions = changes.reindex(equity.index, fill_value=0).cumsum()
        buys = flows[flows.event.eq('BUY_FILL')].pivot_table(index='day', columns='symbol', values='quantity', aggfunc='sum', fill_value=0)
        prior = positions.shift(1, fill_value=0)
        held = prior.gt(0) | positions.gt(0) | buys.reindex(index=positions.index, columns=positions.columns, fill_value=0).gt(0)
        actual_volume = volume.reindex(index=positions.index, columns=positions.columns)
        bad = held & (actual_volume.isna() | actual_volume.le(0))
        for offset, column in np.argwhere(bad.to_numpy()):
            day = positions.index[offset]
            symbol = positions.columns[column]
            details = flows[flows.day.eq(day) & flows.symbol.eq(symbol)]
            rows.append(dict(case=case, date=str(day.date()), symbol=symbol,
                             volume=None if pd.isna(actual_volume.iloc[offset, column]) else float(actual_volume.iloc[offset, column]),
                             prior_quantity=float(prior.iloc[offset, column]),
                             ending_quantity=float(positions.iloc[offset, column]),
                             fills=details[['event', 'quantity', 'price', 'time']].to_dict('records')))
        checks.append(dict(case=case, actual_held_symbol_days=int(held.sum().sum()),
                           missing_or_zero_volume_symbol_days=int(bad.sum().sum())))
    (ROOT / 'actual-held-volume-screen.json').write_text(json.dumps(dict(
        status='NO_ACTUAL_OVERLAP' if not rows else 'REVIEW_REQUIRED', checks=checks, anomalies=rows,
        scope='Missing/nonpositive daily volume on actual intraday or opening holdings; not full price certification',
        provider_calls=0, SQL_writes=0, market_data_changes=0), indent=2), encoding='utf-8')
    print(json.dumps(dict(checks=checks, anomalies=rows), indent=2))


if __name__ == '__main__':
    main()
