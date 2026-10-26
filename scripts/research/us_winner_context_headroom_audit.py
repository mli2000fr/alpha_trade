"""Separate scalar reconstruction of exits/fees and frozen temporal choices."""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from backtesting.winner_campaign_replay import atomic_json
from scripts.research.us_concentrated_historical_tapes import digest, verify_hashes
from scripts.research.us_winner_context_headroom import READ,OUTPUT,GROUPS


def scalar_exit(frame,entry,deadline,policy,fee):
    initial=float(entry);stop=round(initial*(1-policy['stop_loss_pct']),2)
    target=round(initial*(1+policy['take_profit_pct']),2) if policy['take_profit_pct'] else None
    peak=initial
    for row in frame.itertuples():
        price=reason=phase=None
        if row.open<=stop:price,reason,phase=row.open,'STOP_GAP','OPEN'
        elif target is not None and row.open>=target:price,reason,phase=target,'TP_GAP_CAPPED','OPEN'
        elif row.bar_timestamp==deadline:price,reason,phase=row.open,'HORIZON_OPEN','OPEN'
        elif row.low<=stop:price,reason,phase=stop,'STOP','INTRABAR'
        elif target is not None and row.high>=target:price,reason,phase=target,'TP','INTRABAR'
        if price is not None:
            return dict(net_pct=100*(price/initial-1-fee-fee*price/initial),reason=reason,
                        exit_time=row.bar_timestamp if phase=='OPEN' else row.bar_end_timestamp)
        peak=max(peak,row.high)
        if policy['trailing_stop_pct']:
            stop=max(stop,round(peak*(1-policy['trailing_stop_pct']),2))
    raise ValueError('Scalar exit never reached')


def run(root):
    report=READ(root/'report.json');verify_hashes(root,report['files'])
    protocol=READ(root/'protocol.json');verify_hashes(Path('.'),protocol['sources'])
    profiles=protocol['profiles'];snapshot=READ(root/'snapshot.json')
    verify_hashes(root,snapshot['files'])
    bars=pd.concat([pd.read_parquet(root/name) for name in snapshot['files'] if name.startswith('bars-')],ignore_index=True)
    pool={s:g.sort_values('bar_timestamp') for s,g in bars.groupby('symbol')}
    result=pd.read_parquet(root/'unit-results.parquet')
    schedule=pd.read_parquet(root/'calendar.parquet');days=pd.DatetimeIndex(schedule.date)
    opens=schedule.set_index('date').market_open;closes=schedule.set_index('date').market_close
    count=0;error=0.;entry_checks=0
    for row in result.itertuples():
        day=pd.Timestamp(row.entry_time.tz_convert('America/New_York').date());i=days.get_loc(day)
        prior=days[i-1];g=pool[row.symbol]
        previous=g[g.trade_date==prior]
        before=g[(g.trade_date==day)&(g.bar_end_timestamp<=row.entry_time)].tail(3)
        if len(before)!=3 or not (before.bar_end_timestamp.diff().dropna()==pd.Timedelta(minutes=5)).all():
            raise ValueError('Entry freshness mismatch')
        level=float(previous.high.max());a,b,c=before.close.tolist()
        if not a<=level<b or not c>level:raise ValueError('Entry confirmation mismatch')
        at=g[g.bar_timestamp==row.entry_time]
        if len(at)!=1 or float(at.open.iloc[0])!=row.entry_price:raise ValueError('Entry open mismatch')
        if row.source_date>=day or row.label_available!=closes.loc[days[i+20]]:
            raise ValueError('Noncausal factor or wrong common maturity')
        entry_checks+=1
        for name,policy in profiles.items():
            deadline=opens.loc[days[i+policy['horizon_sessions']]]
            path=g[g.bar_timestamp.between(row.entry_time,deadline)]
            for suffix,fee in [('',.0008),('_cost25',.0025)]:
                scalar=scalar_exit(path,row.entry_price,deadline,policy,fee)
                delta=abs(scalar['net_pct']-getattr(row,name+suffix));error=max(error,delta)
                if delta>1e-9 or scalar['reason']!=getattr(row,name+'_reason') or scalar['exit_time']!=getattr(row,name+'_exit'):
                    raise ValueError('Scalar price/stop/fees/date mismatch')
                count+=1
    spaced=pd.read_parquet(root/'nonoverlap.parquet')
    for _,g in spaced.groupby('symbol'):
        g=g.sort_values('entry_time')
        if not (g.entry_time.iloc[1:].to_numpy()>=g.label_available.iloc[:-1].to_numpy()).all():
            raise ValueError('Overlapping same-symbol labels')
    frozen=READ(root/'frozen-2025-policy.json')
    train=spaced[(spaced.year==2025)&(spaced.label_available<pd.Timestamp('2026-01-01',tz='UTC'))]
    test=spaced[spaced.year==2026]
    names=list(profiles);base=train[names].mean().idxmax()
    if frozen['baseline']!=base:raise ValueError('Constant not selected on2025')
    checks=READ(root/'context-checks.json')
    for factor in GROUPS:
        choices={}
        for state,g in train.groupby(factor):
            choices[state]=g[names].mean().idxmax() if len(g)>=12 else base
        if frozen['frozen'][factor]['choices']!=choices:raise ValueError('Non2025state choice')
        gains=[getattr(r,choices.get(getattr(r,factor),base))-getattr(r,base) for r in test.itertuples()]
        actual=next(x for x in checks if x['factor']==factor)
        if abs(np.mean(gains)-actual['gain_pp'])>1e-10:raise ValueError('Context comparison mismatch')
    audited=dict(status='PASS_SCALAR_EXITS_AND_TEMPORAL_CHOICES',unit_results=len(result),
        entry_confirmations=entry_checks,paired_profile_fee_paths=count,max_net_error_pp=error,
        nonoverlap_count=len(spaced),purged_training_count=len(train),confirmation_count=len(test),
        current_code_sha256=digest(__file__),new_tests_sha256=digest('tests/test_us_winner_context_headroom_audit.py'),
        report_sha256=digest(root/'report.json'),reviewer='same_assistant_not_independent_human',
        full_live_parity=False,model_fit=False,sql_writes=False)
    atomic_json(root/'completion-audit.json',audited);print(audited)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,default=OUTPUT)
    run(p.parse_args().output_dir)
