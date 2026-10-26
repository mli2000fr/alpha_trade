"""Separate scalar arithmetic for P06; no primary gain_stop/ledger calls.

Native case audit reconstructs cash/valuation and every B4 opening snapshot.
This final pass additionally checks unit paths and activation timestamps.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.us_concentrated_historical_tapes import atomic_json,digest,verify_hashes


def scalar_exit(path,entry,expiry,c,maintenance=None):
    price=float(path.open.iloc[entry]);high_seen=price
    for i,r in enumerate(path.iloc[entry:].itertuples(),entry):
        threshold=round(price*1.10,2)
        stop=round(price*(1-.07),2)
        if high_seen>=threshold:
            stop=max(stop,round(price+0.5*(high_seen-price),2))
        if maintenance is not None and r.bar_timestamp==maintenance:return i,float(r.open),'OPEN'
        if r.open<=stop:return i,float(r.open),'OPEN'
        if r.bar_timestamp>=expiry:return i,float(r.open),'OPEN'
        if r.low<=stop:return i,float(stop),'INTRABAR'
        high_seen=max(high_seen,float(r.high))
    return None


def final_review(root):
    from scripts.research import us_oracle_gain_lock_p06 as main
    root=Path(root);report=main.READ(root/'report.json');verify_hashes(root,report['files'])
    verify_hashes(Path('.'),main.READ(root/'protocol.json')['sources'])
    expected={(a,y,f) for a in ['WINNER','P06'] for y in [2025,2026] for f in [8,25]}
    if len(report['results'])!=8 or {(r['arm'],r['year'],r['fee_bps']) for r in report['results']}!=expected:
        raise ValueError('Eight distinct cases required')
    if not all(r['audit']['status']=='PASS_PRODUCTION_RISK_CASH_EXITS' for r in report['results']):
        raise ValueError('Portfolio cash/risk/exit audit missing')
    groups,_,schedule=main.parent.load_groups();days=pd.DatetimeIndex(schedule.date)
    signals=pd.read_parquet(root/'entry-signals.parquet');units=pd.read_parquet(root/'unit-results.parquet').set_index('pair_id')
    verified=0;activation_count=0
    for s in signals.itertuples():
        j=days.get_loc(s.date);frame=pd.concat([groups[s.symbol,d] for d in days[j:j+21]])
        frame=frame[frame.bar_timestamp.between(s.timestamp,s.due_open)].reset_index(drop=True)
        for arm,fn in [('WINNER',main.ORIGINAL_SCALAR),('P06',scalar_exit)]:
            resolution=fn(frame,0,s.due_open,{})
            if resolution is None:raise ValueError('Immature unit')
            index,price,phase=resolution
            for fee in [8,25]:
                value=100*((price-s.price)/s.price-(fee/10000)*(1+price/s.price))
                if not np.isclose(value,units.loc[s.pair_id,f'{arm}_{fee}'],atol=1e-9,rtol=0):
                    raise ValueError('Unit outcome mismatch')
                verified+=1
            if arm=='P06':
                time=frame.bar_timestamp.iloc[index] if phase=='OPEN' else frame.bar_end_timestamp.iloc[index]
                if units.loc[s.pair_id,'P06_exit']!=time or units.loc[s.pair_id,'P06_exit_price']!=price:
                    raise ValueError('Unit execution mismatch')
                # Only bars survived before exit may contribute to activation.
                surviving=frame.iloc[:index]
                active=bool(len(surviving) and surviving.high.max()>=round(s.price*1.10,2))
                if bool(units.loc[s.pair_id,'activated'])!=active:raise ValueError('Activation used future/same-exit-bar high')
    for result in report['results']:
        out=root/f'{result["arm"]}-fee{result["fee_bps"]}'/'cases'/str(result['year'])
        if result['arm']=='WINNER':
            old=main.REFERENCE/f'WINNER-fee{result["fee_bps"]}'/'cases'/str(result['year'])
            for n in ['trades.parquet','marks.parquet','decisions.json','maintenance.json','production-risk-events.json']:
                if digest(out/n)!=digest(old/n):raise ValueError('Baseline changed')
            continue
        events=main.READ(out/'gain-lock-activations.json');trades=pd.read_parquet(out/'trades.parquet')
        opened=main.READ(out/'open-positions.json');records=trades.to_dict('records')+opened
        by_id={int(r['pair_id']):r for r in records};seen=set()
        for e in events:
            pid=int(e['pair_id'])
            if pid in seen or pid not in by_id:raise ValueError('Duplicate/unqualified activation')
            seen.add(pid);r=by_id[pid];day=pd.Timestamp(pd.Timestamp(r['entry_timestamp']).tz_convert('America/New_York').date())
            entry=pd.Timestamp(r['entry_timestamp']);available=pd.Timestamp(e['observed_at'])
            if pd.Timestamp(e['effective_no_earlier_than'])!=available or available<=entry:raise ValueError('Noncausal stop update')
            frames=[g for (sym,d),g in groups.items() if sym==e['symbol'] and d.year==result['year']]
            path=pd.concat(frames).sort_values('bar_timestamp')
            prefix=path[(path.bar_timestamp>=entry)&(path.bar_end_timestamp<=available)]
            if prefix.empty:raise ValueError('No completed observation for activation')
            peak=max(r['entry_price'],float(prefix.high.max()))
            if peak<round(r['entry_price']*1.10,2):raise ValueError('Premature activation')
            older=prefix.iloc[:-1]
            if len(older) and older.high.max()>=round(r['entry_price']*1.10,2):raise ValueError('Not first activation')
            stop=max(round(r['entry_price']*(1-.07),2),round(r['entry_price']+.5*(peak-r['entry_price']),2))
            if e['stop']!=stop or e['observed_peak']!=peak or pd.Timestamp(e['expiry'])!=pd.Timestamp(r['expiry']):
                raise ValueError('Activation stop/peak/horizon mismatch')
            activation_count+=1
        for pid,r in by_id.items():
            entry=pd.Timestamp(r['entry_timestamp'])
            end=(pd.Timestamp(r['exit_timestamp']) if r.get('exit_phase')=='OPEN' else
                 pd.Timestamp(r['exit_timestamp'])-pd.Timedelta(minutes=5)) if 'exit_timestamp' in r else None
            frames=[g for (sym,d),g in groups.items() if sym==r['symbol'] and d.year==result['year']]
            path=pd.concat(frames)
            prefix=path[path.bar_timestamp.ge(entry)]
            if end is not None:prefix=prefix[prefix.bar_timestamp.lt(end)]
            active=bool(len(prefix) and prefix.high.max()>=round(r['entry_price']*1.10,2))
            if active!=(pid in seen):raise ValueError('Missing/spurious activation record')
    audit=dict(status='PASS_P06_BASELINE_EXIT_CASH_B4_AND_ACTIVATION_REVIEW',portfolio_cases=8,
        baseline_cases_exactly_reproduced=4,unit_cost_results_verified=verified,
        portfolio_activations_verified=activation_count,report_sha256=digest(root/'report.json'),
        reviewer_source_sha256=digest(__file__),independent_human_review=False,production_promoted=False)
    atomic_json(root/'final-audit.json',audit);print(audit);return audit


if __name__=='__main__':
    import argparse
    from scripts.research.us_oracle_gain_lock_p06 import OUTPUT
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,default=OUTPUT)
    final_review(p.parse_args().output_dir)
