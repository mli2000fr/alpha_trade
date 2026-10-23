"""Independent P05 channel arithmetic, native cash/B4 audits and final review.

No calls to primary build_channels, unit_outcome, known_stop or finish_day.
Same assistant technical review, NOT independent human review.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes

AUDIT_CHANNELS = {}


def configure_history(groups, schedule):
    global AUDIT_CHANNELS
    table = pd.DataFrame([dict(symbol=s, date=d, low=float(g.low.min())) for (s,d),g in groups.items()])
    wide = table.pivot(index='date', columns='symbol', values='low').reindex(schedule.date)
    rolled = wide.rolling(10, min_periods=10).min()
    # Python scalar rounding is the frozen execution contract. NumPy/pandas
    # vector round differs by one cent at some binary half-cent boundaries.
    AUDIT_CHANNELS = {(symbol, day):round(float(value), 2) for symbol in rolled.columns
                      for day,value in rolled[symbol].dropna().items()}


def scalar_exit(path, entry, expiry, c, maintenance=None):
    price = float(path.open.iloc[entry]); floor = round(price*(1-.07), 2)
    previous = None; symbol = str(path.symbol.iloc[entry])
    for i,r in enumerate(path.iloc[entry:].itertuples(), entry):
        session = pd.Timestamp(r.bar_timestamp.tz_convert('America/New_York').date())
        if previous is not None and session != previous:
            floor = max(floor, AUDIT_CHANNELS[symbol, previous])
        previous = session
        if maintenance is not None and r.bar_timestamp == maintenance: return i,float(r.open),'OPEN'
        if r.open <= floor: return i,float(r.open),'OPEN'
        if r.bar_timestamp >= expiry: return i,float(r.open),'OPEN'
        if r.low <= floor: return i,float(floor),'INTRABAR'
    return None


def final_review(root):
    from scripts.research import us_oracle_low_channel_p05 as main
    root = Path(root); report = main.READ(root/'report.json')
    verify_hashes(root, report['files']); verify_hashes(Path('.'), main.READ(root/'protocol.json')['sources'])
    expected = {(a,y,f) for a in ['WINNER','COMMON_WINNER','P05'] for y in [2025,2026] for f in [8,25]}
    actual = {(r['arm'],r['year'],r['fee_bps']) for r in report['results']}
    if len(report['results']) != 12 or actual != expected: raise ValueError('Twelve distinct cases required')
    if not all(r['audit']['status']=='PASS_PRODUCTION_RISK_CASH_EXITS' for r in report['results']):
        raise ValueError('Cash/risk/exit audit missing')
    groups, _, schedule = main.parent.load_groups(); configure_history(groups, schedule)
    days = pd.DatetimeIndex(schedule.date); sch = schedule.set_index('date')
    channels = pd.read_parquet(root/'channels.parquet')
    recorded = {(r.symbol,r.date):r.channel for r in channels.itertuples()}
    if recorded != AUDIT_CHANNELS: raise ValueError('Channel arithmetic mismatch')
    lows = pd.read_parquet(root/'complete-session-lows.parquet')
    if {(r.symbol,r.date):r.low for r in lows.itertuples()} != {key:float(g.low.min()) for key,g in groups.items()}:
        raise ValueError('Raw lows mismatch')
    full = pd.read_parquet(root/'full-entry-signals.parquet')
    signals = pd.read_parquet(root/'entry-signals.parquet')
    expected_common = set()
    for s in full.itertuples():
        j = days.get_loc(s.date)
        if all((s.symbol,d) in AUDIT_CHANNELS for d in days[j:j+20]): expected_common.add(int(s.pair_id))
    if expected_common != set(signals.pair_id): raise ValueError('Common coverage selection mismatch')
    reserves = main.READ(root/'coverage-reserves.json')
    if set(r['pair_id'] for r in reserves) != set(full.pair_id)-expected_common:
        raise ValueError('Missing reserves')
    units = pd.read_parquet(root/'unit-results.parquet').set_index('pair_id'); verified = 0
    for s in signals.itertuples():
        j = days.get_loc(s.date)
        path = pd.concat([groups[s.symbol,d] for d in days[j:j+21]])
        path = path[path.bar_timestamp.between(s.timestamp,s.due_open)].reset_index(drop=True)
        for arm,fn in [('WINNER',main.ORIGINAL_SCALAR),('P05',scalar_exit)]:
            resolution = fn(path,0,s.due_open,{})
            if resolution is None: raise ValueError('Immature unit')
            k,price,phase = resolution
            for fee in [8,25]:
                value = 100*((price-s.price)/s.price-fee/10000*(1+price/s.price))
                if not np.isclose(value,units.loc[s.pair_id,f'{arm}_{fee}'],atol=1e-9,rtol=0):
                    raise ValueError('Unit return mismatch')
                verified += 1
            if arm == 'P05':
                stamp = path.bar_timestamp.iloc[k] if phase=='OPEN' else path.bar_end_timestamp.iloc[k]
                if units.loc[s.pair_id,'P05_exit']!=stamp or units.loc[s.pair_id,'P05_exit_price']!=price:
                    raise ValueError('Unit exit mismatch')
                stop = round(s.price*(1-.07),2); tightened = False
                exited_day = pd.Timestamp(stamp.tz_convert('America/New_York').date())
                for d in days[j:days.get_loc(exited_day)]:
                    newer = max(stop,AUDIT_CHANNELS[s.symbol,d]); tightened |= newer>stop; stop=newer
                if bool(units.loc[s.pair_id,'tightened']) != bool(tightened): raise ValueError('Tightening mismatch')
    event_count = 0
    for result in report['results']:
        out = root/f'{result["arm"]}-fee{result["fee_bps"]}'/'cases'/str(result['year'])
        offered = {(int(s.pair_id),s.timestamp) for s in (full if result['arm']=='WINNER' else signals).itertuples()
                   if s.year==result['year']}
        trades = pd.read_parquet(out/'trades.parquet'); opened = main.READ(out/'open-positions.json')
        records = trades.to_dict('records')+opened
        if any((int(r['pair_id']),pd.Timestamp(r['entry_timestamp'])) not in offered for r in records):
            raise ValueError('Unexpected entry')
        if result['arm'] == 'WINNER':
            old = main.REFERENCE/f'WINNER-fee{result["fee_bps"]}'/'cases'/str(result['year'])
            for name in ['trades.parquet','marks.parquet','decisions.json','maintenance.json','production-risk-events.json']:
                if digest(out/name)!=digest(old/name): raise ValueError('Baseline changed')
            continue
        if result['arm'] != 'P05': continue
        events = main.READ(out/'channel-updates.json')
        expected_by_key = {}
        # Rebuild every expected update, including unchanged stops, from actual
        # position lifecycle. No exited-at-last-bar position may gain an update.
        for r in records:
            entry = pd.Timestamp(r['entry_timestamp']); price = r['entry_price']
            first = pd.Timestamp(entry.tz_convert('America/New_York').date())
            end = pd.Timestamp(r['exit_timestamp']) if 'exit_timestamp' in r else None
            floor = round(price*(1-.07),2)
            for d in days[(days>=first)&(days.year==result['year'])&(days<=main.parent.END)]:
                close = sch.loc[d,'market_close']
                if end is not None and end<=close: break
                channel = AUDIT_CHANNELS[r['symbol'],d]; newer=max(floor,channel)
                key = (int(r['pair_id']),entry,d)
                expected_by_key[key] = dict(entry_price=price, previous_stop=floor, channel_low=channel, stop=newer,
                    observed_at=close,effective_at=sch.loc[days[days.get_loc(d)+1],'market_open'],expiry=pd.Timestamp(r['expiry']))
                floor = newer
        seen = set()
        for e in events:
            key=(int(e['pair_id']),pd.Timestamp(e['entry_timestamp']),pd.Timestamp(e['asof_session']))
            if key in seen or key not in expected_by_key: raise ValueError('Duplicate/spurious channel update')
            seen.add(key); expected_row=expected_by_key[key]
            for name,value in expected_row.items():
                actual_value=pd.Timestamp(e[name]) if isinstance(value,pd.Timestamp) else e[name]
                if actual_value!=value: raise ValueError('Noncausal/wrong channel update:'+name)
            event_count+=1
        if seen!=set(expected_by_key): raise ValueError('Missing channel update')
    audit = dict(status='PASS_P05_CHANNEL_CAUSALITY_BASELINE_EXIT_CASH_B4_REVIEW', portfolio_cases=12,
        baseline_cases_exactly_reproduced=4, common_campaigns=len(signals), reserved_campaigns=len(reserves),
        channels_verified=len(AUDIT_CHANNELS), unit_cost_results_verified=verified,
        portfolio_updates_verified=event_count, report_sha256=digest(root/'report.json'),
        reviewer_source_sha256=digest(__file__), independent_human_review=False, production_promoted=False)
    atomic_json(root/'final-audit.json',audit); print(audit); return audit


if __name__=='__main__':
    import argparse
    from scripts.research.us_oracle_low_channel_p05 import OUTPUT
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output-dir',type=Path,default=OUTPUT)
    final_review(parser.parse_args().output_dir)
