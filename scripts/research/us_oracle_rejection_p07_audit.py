"""P07 frequency-only audit with separate feature and entry arithmetic.

No primary feature/scan/inspect calls, no economic replay or price outcomes.
Same assistant technical review, not independent human review.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.us_concentrated_historical_tapes import atomic_json,digest,verify_hashes


def features(frames):
    if len(frames)!=10:raise ValueError('TEN_PRIOR_COMPLETE_SESSIONS_REQUIRED')
    high=np.array([f.high.max() for f in frames],dtype=float)
    low=np.array([f.low.min() for f in frames],dtype=float)
    close=np.array([f.close.iloc[-1] for f in frames],dtype=float)
    if not (np.isfinite(np.r_[high,low,close]).all() and (low>0).all() and (low<=close).all() and (close<=high).all()):
        raise ValueError('INVALID_DAILY_OBSERVATIONS')
    spans=high-low;where=(close[-1]-low[-1])/spans[-1] if spans[-1]>0 else None
    new=bool((low[-1]<low[:-1]).all());wide=bool((spans[-1]>spans[:-1]).all());upper=where is not None and where>=.75
    return dict(high_j=float(high[-1]),low_j=float(low[-1]),close_j=float(close[-1]),range_j=float(spans[-1]),
        min_prior9_low=float(low[:-1].min()),max_prior9_range=float(spans[:-1].max()),close_location=where,
        new_low=new,widest_range=wide,upper_quarter=bool(upper),pattern=bool(spans[-1]>0 and new and wide and upper))


def entry(symbol,day,high,low,groups,schedule,end):
    days=pd.DatetimeIndex(schedule.date);i=days.get_loc(day)
    for d in days[i+1:i+3]:
        if d>end:return dict(status='ENTRY_SCREEN_CENSORED')
        f=groups.get((symbol,d))
        if f is None:return dict(status='MISSING_ENTRY_SESSION',missing_date=d)
        breaches=np.flatnonzero(f.low.to_numpy(float)<low)
        confirmations=np.flatnonzero(f.close.to_numpy(float)>high)
        first_breach=int(breaches[0]) if len(breaches) else len(f)
        first_confirm=int(confirmations[0]) if len(confirmations) else len(f)
        if first_breach<len(f) and first_breach<=first_confirm:
            return dict(status='LOW_J_INVALIDATED',decision_time=f.bar_end_timestamp.iloc[first_breach])
        if first_confirm==len(f):continue
        if first_confirm==len(f)-1:
            return dict(status='FIRST_CONFIRMATION_LAST_BAR_NO_FILL',decision_time=f.bar_end_timestamp.iloc[first_confirm])
        k=first_confirm+1
        if float(f.open.iloc[k])<low:
            return dict(status='GAP_BELOW_LOW_J_BEFORE_FILL',decision_time=f.bar_timestamp.iloc[k])
        return dict(status='SIGNAL',timestamp=f.bar_timestamp.iloc[k],date=d,delay=days.get_loc(d)-i,
            price=float(f.open.iloc[k]),signal_bar=f.bar_timestamp.iloc[first_confirm],
            signal_close=float(f.close.iloc[first_confirm]),decision_time=f.bar_end_timestamp.iloc[first_confirm])
    return dict(status='NO_BREAKOUT_TWO_SESSIONS')


def inspect(row,groups,schedule,actions,end):
    days=pd.DatetimeIndex(schedule.date);sch=schedule.set_index('date');i=days.get_loc(row.oracle_date)
    base=dict(pair_id=int(row.pair_id),symbol=row.symbol,rank=int(row.rank),oracle_date=row.oracle_date,
        year=row.oracle_date.year,feature_status='MISSING_TEN_SESSION_LOOKBACK',pattern=None,
        entry_status='NOT_SCREENED',entry_evaluable=False,break_control_signal=None,P07_signal=None,
        entry_time=sch.loc[days[i+1],'market_open'],label_available=sch.loc[days[i+40],'market_open'])
    window=days[max(0,i-9):i+1];missing=[d for d in window if (row.symbol,d) not in groups]
    if len(window)<10 or missing:return dict(base,missing_lookback_dates='|'.join(str(d.date()) for d in missing))
    if not actions.empty and ((actions.symbol==row.symbol)&actions.ex_date.between(window[0],row.oracle_date)).any():
        return dict(base,feature_status='KNOWN_LOOKBACK_CORPORATE_ACTION')
    try:f=features([groups[row.symbol,d] for d in window])
    except ValueError as exc:return dict(base,feature_status=str(exc))
    e=entry(row.symbol,row.oracle_date,f['high_j'],f['low_j'],groups,schedule,end)
    known=e['status'] not in {'ENTRY_SCREEN_CENSORED','MISSING_ENTRY_SESSION'}
    result=dict(base,feature_status='QUALIFIED',**f,entry_status=e['status'],entry_evaluable=known,
        break_control_signal=e['status']=='SIGNAL',P07_signal=bool(f['pattern'] and e['status']=='SIGNAL') if known else None,
        feature_source_start=window[0],feature_available_at=sch.loc[row.oracle_date,'market_close'])
    result.update({f'entry_{name}':value for name,value in e.items() if name!='status'})
    return result


def equal(actual,expected,context):
    if pd.isna(actual) and pd.isna(expected):return
    if actual!=expected:raise ValueError(f'{context}: {actual}!={expected}')


def final_review(root):
    from scripts.research import us_oracle_rejection_p07 as main
    root=Path(root);report=main.READ(root/'report.json');verify_hashes(root,report['files'])
    verify_hashes(Path('.'),main.READ(root/'protocol.json')['sources'])
    if report['performance_calculated'] or report['economic_backtest_launched']:raise ValueError('Frequency-only scope violated')
    if (root/'annual-summary.csv').exists() or any(root.glob('*/cases')):raise ValueError('Unexpected economic replay')
    groups,_,schedule=main.parent.load_groups();candidates=pd.read_parquet(main.parent.PARENT/'campaigns.parquet')
    actions=pd.read_parquet(main.parent.PARENT/'corporate-actions.parquet')
    if not actions.empty:actions['ex_date']=pd.to_datetime(actions.ex_date)
    records=pd.read_parquet(root/'coverage-and-signals.parquet').set_index('pair_id')
    if len(records)!=213 or set(records.index)!=set(candidates.pair_id):raise ValueError('Population mismatch')
    checked_features=checked_signals=0
    for row in candidates.itertuples():
        expected=inspect(row,groups,schedule,actions,main.parent.END)
        for name,value in expected.items():
            if name!='pair_id':equal(records.loc[row.pair_id,name],value,f'{row.pair_id}/{name}')
        if expected['feature_status']=='QUALIFIED':checked_features+=1
        if expected['P07_signal'] is True:
            if expected['entry_timestamp']<=expected['feature_available_at']:raise ValueError('Noncausal feature')
            equal(expected['entry_timestamp'],expected['entry_decision_time'],'Contiguous next open')
            checked_signals+=1
    qualified=records[records.feature_status.eq('QUALIFIED')]
    evaluable=qualified[qualified.entry_evaluable.eq(True)].reset_index()
    blocked={};retained=[]
    for row in evaluable.sort_values(['entry_time','rank','symbol','pair_id']).itertuples():
        if row.symbol in blocked and row.entry_time<blocked[row.symbol]:continue
        retained.append(row.pair_id);blocked[row.symbol]=row.label_available
    spaced=pd.read_parquet(root/'nonoverlap.parquet')
    if list(spaced.pair_id)!=retained:raise ValueError('Nonoverlap mismatch')
    chosen=pd.read_parquet(root/'P07-entry-signals.parquet')
    expected_ids=set(records[records.P07_signal.eq(True)].index)
    if set(chosen.pair_id)!=expected_ids:raise ValueError('Persisted P07signals mismatch')
    gate=True
    for counts in report['counts']:
        year=counts['year'];f=qualified[qualified.year.eq(year)];e=evaluable[evaluable.year.eq(year)]
        n=spaced[spaced.year.eq(year)];s=n[n.P07_signal.eq(True)]
        actual=dict(original=int(candidates.year.eq(year).sum()),features_qualified=len(f),patterns=int(f.pattern.eq(True).sum()),
            entry_evaluable=len(e),break_control_signals=int(e.break_control_signal.sum()),p07_signals=int(e.P07_signal.eq(True).sum()),
            nonoverlap_opportunities=len(n),nonoverlap_signals=len(s),symbols=int(s.symbol.nunique()),signal_months=int(s.oracle_date.dt.month.nunique()))
        passed=len(s)>=30 and actual['symbols']>=10 and actual['signal_months']>=6
        for name,value in actual.items():equal(counts[name],value,f'Counts/{year}/{name}')
        equal(counts['gate_pass'],passed,'Gate');gate=gate and passed
    equal(report['sufficient_sample'],bool(gate),'Overall gate')
    equal(report['feature_qualified'],checked_features,'Qualified count')
    equal(report['p07_signals'],checked_signals,'Signal count')
    audit=dict(status='PASS_P07_FEATURE_ENTRY_FREQUENCY_NO_PNL_REVIEW',campaigns_verified=len(records),
        qualified_features_verified=checked_features,p07_signals_verified=checked_signals,
        report_sha256=digest(root/'report.json'),reviewer_source_sha256=digest(__file__),
        performance_calculated=False,economic_backtest_launched=False,
        independent_human_review=False,production_promoted=False)
    atomic_json(root/'final-audit.json',audit);print(audit);return audit


if __name__=='__main__':
    import argparse
    from scripts.research.us_oracle_rejection_p07 import OUTPUT
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output-dir',type=Path,default=OUTPUT)
    final_review(parser.parse_args().output_dir)
