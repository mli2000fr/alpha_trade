"""Separate arithmetic verification of P01 selection and unit outcomes, offline.

Does not call the primary indicator/signal/exit functions. Existing native risk
audits independently reconstruct the portfolio cash and exits in each case.
Same assistant, not independent human review. No SQL/provider/broker access.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research import us_oracle_compression_p01 as main
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes


def first_signals(frame, threshold):
    c = frame.close.to_numpy(float); hi = frame.high.to_numpy(float); lo = frame.low.to_numpy(float)
    n = len(c); inside = [False]*n; release = [False]*n; widths = [np.nan]*n
    ema = c[0]; atr = None; ranges = []
    for i in range(n):
        if i: ema = (2/21)*c[i]+(19/21)*ema
        ranges.append(max(hi[i]-lo[i], abs(hi[i]-c[i-1]), abs(lo[i]-c[i-1])) if i else hi[i]-lo[i])
        if i < 19: continue
        atr = sum(ranges)/20 if i == 19 else (19*atr+ranges[-1])/20
        window = c[i-19:i+1]; center = sum(window)/20
        dev = 2*np.sqrt(sum((v-center)**2 for v in window)/20)
        widths[i] = 2*dev
        inside[i] = bool(center+dev < ema+1.5*atr and center-dev > ema-1.5*atr)
        release[i] = bool(i >= 22 and all(inside[i-3:i]) and not inside[i] and widths[i]>widths[i-1])
    result = {}
    for k in range(2, n-1):
        if not c[k-2] <= threshold < c[k-1] or not c[k] > threshold: continue
        stamp = frame.bar_timestamp.iloc[k+1]
        result.setdefault('WINNER', stamp)
        if k < 21: continue
        result.setdefault('WARMUP_CONTROL', stamp)
        for j in range(k-1, max(-1, k-8), -1):
            if release[j]:
                if not any(inside[j:k]): result.setdefault('P01', stamp)
                break
    return result


def scalar_outcome(frame, price, due):
    peak = price
    for r in frame.itertuples():
        stop = max(round(price*(1-.07),2), round(peak*(1-.15),2))
        if r.open <= stop: return float(r.open), r.bar_timestamp
        if r.bar_timestamp == due: return float(r.open), r.bar_timestamp
        if r.low <= stop: return stop, r.bar_end_timestamp
        peak = max(peak,r.high)
    raise ValueError('No mature unit exit')


def audit(root):
    root = Path(root)
    report = main.READ(root/'report.json'); verify_hashes(root, report['files'])
    verify_hashes(Path('.'),main.READ(root/'protocol.json')['sources'])
    expected_cases={(arm,year,fee) for arm in main.ARMS for year in (2025,2026) for fee in (8,25)}
    if {(r['arm'],r['year'],r['fee_bps']) for r in report['portfolio_results']}!=expected_cases or len(report['portfolio_results'])!=12:
        raise ValueError('All twelve distinct portfolio cases required')
    groups, _, schedule = main.load_groups()
    days = pd.DatetimeIndex(schedule.date); sch = schedule.set_index('date')
    units = pd.read_parquet(root/'unit-results.parquet').set_index('pair_id')
    candidates = pd.read_parquet(main.PARENT/'campaigns.parquet').set_index('pair_id')
    signals = pd.read_parquet(root/'signals.parquet')
    checked_signals = checked_units = 0
    for pid, row in units.iterrows():
        r = candidates.loc[pid]; expected = {}
        start = days.get_loc(r.oracle_date)
        for j in range(start+1,start+21):
            g = groups.get((r.symbol,days[j])); prev = groups.get((r.symbol,days[j-1]))
            if g is None or prev is None: raise ValueError('Unexpected missing scan on common cohort')
            for arm, stamp in first_signals(g,float(prev.high.max())).items(): expected.setdefault(arm,stamp)
            if len(expected)==3: break
        observed = signals[signals.pair_id.eq(pid)].set_index('arm')
        if set(expected)!=set(observed.index): raise ValueError(f'Signal presence differs {pid}')
        for arm in main.ARMS:
            if bool(row[arm+'_signal']) != (arm in expected): raise ValueError('Unit population mismatch')
            if arm not in expected:
                if row[arm]!=0 or row[arm+'_cost25']!=0: raise ValueError('No signal is not cash')
                continue
            s = observed.loc[arm]; stamp = expected[arm]
            if s.timestamp!=stamp: raise ValueError(f'Not first causal entry {pid}/{arm}')
            day = pd.Timestamp(stamp.tz_convert('America/New_York').date()); k = days.get_loc(day)
            due = sch.loc[days[k+20],'market_open']
            if s.due_open!=due: raise ValueError('Horizon not from actual entry')
            g = pd.concat([groups[r.symbol,d] for d in days[k:k+21]])
            g = g[g.bar_timestamp.between(stamp,due)]
            price = float(g.open.iloc[0])
            if s.price!=price: raise ValueError('Entry not next observed open')
            px, exit_stamp = scalar_outcome(g,price,due)
            if row[arm+'_exit']!=exit_stamp: raise ValueError('Unit exit time differs')
            for bps, col in [(8,arm),(25,arm+'_cost25')]:
                value = 100*((px-price)/price-(bps/10000)*(1+px/price))
                if not np.isclose(row[col],value,atol=1e-9,rtol=0): raise ValueError('Unit return differs')
                checked_units+=1
            checked_signals+=1
    if len(signals)!=checked_signals: raise ValueError('Unverified persisted signal')
    for r in report['portfolio_results']:
        if r['audit']['status']!='PASS_PRODUCTION_RISK_CASH_EXITS': raise ValueError('Failed native portfolio audit')
        out=root/f'{r["arm"]}-fee{r["fee_bps"]}'/'cases'/str(r['year'])
        trades=pd.read_parquet(out/'trades.parquet')
        opened=main.READ(out/'open-positions.json')
        for item in trades.to_dict('records')+opened:
            match=signals[(signals.pair_id.eq(item['pair_id']))&signals.arm.eq(r['arm'])&signals.year.eq(r['year'])]
            if len(match)!=1 or match.timestamp.iloc[0]!=pd.Timestamp(item['entry_timestamp']):
                raise ValueError('Portfolio entry lacks qualified signal')
            if pd.Timestamp(item['expiry'])!=match.due_open.iloc[0]: raise ValueError('Portfolio horizon mismatch')
    result=dict(status='PASS_P01_SEPARATE_ARITHMETIC_AND_PORTFOLIO_AUDITS',campaigns=len(units),
        signals_verified=checked_signals,unit_cost_results_verified=checked_units,portfolio_cases=12,
        source_hashes={str(Path(__file__)):digest(__file__)},primary_report_sha256=digest(root/'report.json'),
        independent_human_review=False,production_promoted=False)
    atomic_json(root/'final-audit.json',result)
    print(result)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',type=Path,default=main.OUTPUT)
    audit(p.parse_args().output_dir)
