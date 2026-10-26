"""Separate P04 threshold, first-hit, coverage, unit and native risk review.

No primary range/selector/signal calls. Same assistant, not human independence.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.us_concentrated_historical_tapes import atomic_json,digest,verify_hashes


def scalar_range(prior):
    if len(prior)!=4:raise ValueError('FOUR_PRIOR_SESSIONS_REQUIRED')
    daily=[]
    for frame in prior:
        daily.append((max(float(r.high) for r in frame.itertuples()),
                      min(float(r.low) for r in frame.itertuples()),float(frame.close.iloc[-1])))
    hh=max(x[0] for x in daily); ll=min(x[1] for x in daily)
    hc=max(x[2] for x in daily); lc=min(x[2] for x in daily)
    result=round(float(max(hh-lc,hc-ll)),8)
    if not np.isfinite(result) or result<=0:raise ValueError('NONPOSITIVE_PRIOR_RANGE')
    return result


def scalar_session(frame,prior_high,span):
    c=list(map(float,frame.close));opening=float(frame.open.iloc[0]);hi=round(opening+span/2,8);lo=round(opening-span/2,8)
    if not np.isfinite([opening,prior_high,span,hi,lo]).all() or not 0<lo<opening<hi:
        raise ValueError('INVALID_OPENING_BANDS')
    found={};notes={}; event=dict(opening=opening,prior_range=span,upper=hi,lower=lo,first_direction='NONE',first_trigger_bar=pd.NaT)

    def emit(k,threshold,direction):
        return dict(timestamp=frame.bar_timestamp.iloc[k+1],price=float(frame.open.iloc[k+1]),
            signal_close=c[k],signal_bar=frame.bar_timestamp.iloc[k],prior_high=prior_high,
            opening=opening,prior_range=span,upper=hi,lower=lo,trigger_direction=direction,entry_threshold=threshold)

    k=next((i for i in range(2,len(c)-1) if c[i-2]<=prior_high and c[i-1]>prior_high and c[i]>prior_high),None)
    if k is not None:found['J1_WINNER']=emit(k,prior_high,'HIGH_J_TWO_CLOSES');notes['J1_WINNER']='SIGNAL'
    else:notes['J1_WINNER']='NO_SAME_SESSION_WINNER_FILL'
    k=next((i for i,value in enumerate(c) if value>prior_high),None)
    if k is not None and k+1<len(c):found['HIGH_J']=emit(k,prior_high,'HIGH_J_ONE_CLOSE');notes['HIGH_J']='SIGNAL'
    else:notes['HIGH_J']='NO_SAME_SESSION_HIGH_J_FILL'
    k=next((i for i,value in enumerate(c) if value>hi or value<lo),None)
    if k is None:notes.update(TIME_LONG='NO_DUAL_TRIGGER',P04='NO_DUAL_TRIGGER')
    else:
        direction='UP' if c[k]>hi else 'DOWN';event.update(first_direction=direction,first_trigger_bar=frame.bar_timestamp.iloc[k])
        if k==len(c)-1:notes.update(TIME_LONG='LAST_BAR_NO_FILL',P04='LAST_BAR_NO_FILL')
        else:
            e=emit(k,hi if direction=='UP' else lo,direction);found['TIME_LONG']=e;notes['TIME_LONG']='SIGNAL'
            if direction=='UP':found['P04']=dict(e);notes['P04']='SIGNAL'
            else:notes['P04']='DOWN_FIRST_ABSTAIN'
    return found,notes,event


def selection(row,groups,schedule,end):
    days=pd.DatetimeIndex(schedule.date);i=days.get_loc(row.oracle_date);sch=schedule.set_index('date')
    if i<3 or not all((row.symbol,d) in groups for d in days[i-3:i+1]):return {},{},None,'MISSING_FOUR_PRIOR_SESSIONS'
    if days[i+1]>end:return {},{},None,'J1_IMMATURE'
    if (row.symbol,days[i+1]) not in groups:return {},{},None,'MISSING_J1_SESSION'
    prior=[groups[row.symbol,d] for d in days[i-3:i+1]]
    try:
        span=scalar_range(prior)
        found,notes,event=scalar_session(groups[row.symbol,days[i+1]],max(float(x) for x in prior[-1].high),span)
    except ValueError as exc:return {},{},None,str(exc)
    for entry in found.values():entry.update(date=days[i+1],delay=1)
    for j in range(i+1,i+21):
        day,previous=days[j],days[j-1]
        if day>end:return {},{},None,'ENTRY_WINDOW_CENSORED'
        if (row.symbol,day) not in groups or (row.symbol,previous) not in groups:return {},{},None,'ENTRY_SCAN_MISSING_SESSION'
        frame=groups[row.symbol,day];h=max(float(x) for x in groups[row.symbol,previous].high);c=list(map(float,frame.close))
        k=next((k for k in range(2,len(c)-1) if c[k-2]<=h and c[k-1]>h and c[k]>h),None)
        if k is not None:
            found['COMMON_WINNER']=dict(timestamp=frame.bar_timestamp.iloc[k+1],price=float(frame.open.iloc[k+1]),
                signal_close=c[k],signal_bar=frame.bar_timestamp.iloc[k],prior_high=h,date=day,delay=j-i)
            notes['COMMON_WINNER']='SIGNAL';break
    else:notes['COMMON_WINNER']='NO_BREAKOUT'
    for entry in found.values():entry.update(range_source_start=days[i-3],range_source_end=days[i],
        range_available_at=sch.loc[days[i],'market_close'],band_known_at=sch.loc[days[i+1],'market_open'])
    event.update(pair_id=int(row.pair_id),symbol=row.symbol,oracle_date=row.oracle_date,
        range_source_start=days[i-3],range_source_end=days[i],range_available_at=sch.loc[days[i],'market_close'],
        band_known_at=sch.loc[days[i+1],'market_open'])
    return found,notes,event,None


def reservation(row,found,groups,schedule,actions,end):
    days=pd.DatetimeIndex(schedule.date);i=days.get_loc(row.oracle_date)
    if not actions.empty and ((actions.symbol==row.symbol)&actions.ex_date.between(days[i-3],days[i+1])).any():
        return 'KNOWN_LOOKBACK_CORPORATE_ACTION'
    for entry in found.values():
        j=days.get_loc(entry['date']);dates=days[j:j+21]
        if dates[-1]>end:return 'COMMON_H20_IMMATURE'
        if not all((row.symbol,d) in groups for d in dates):return 'COMMON_H20_MISSING_SESSION'
        if not actions.empty and ((actions.symbol==row.symbol)&actions.ex_date.between(dates[0],dates[-1])).any():return 'KNOWN_CORPORATE_ACTION'
    return None


def equal(actual,expected,description):
    if pd.isna(actual) and pd.isna(expected):return
    if actual!=expected:raise ValueError(f'{description}: {actual}!={expected}')


def final_review(root):
    from scripts.research import us_oracle_dual_thrust_p04 as main
    from scripts.research.us_oracle_compression_p01_audit import scalar_outcome
    root=Path(root);report=main.READ(root/'report.json');verify_hashes(root,report['files'])
    verify_hashes(Path('.'),main.READ(root/'protocol.json')['sources'])
    expected={(arm,y,f) for arm in main.ARMS for y in [2025,2026] for f in [8,25]}
    if len(report['results'])!=24 or {(r['arm'],r['year'],r['fee_bps']) for r in report['results']}!=expected:
        raise ValueError('Twenty-four distinct cases required')
    if not all(r['audit']['status']=='PASS_PRODUCTION_RISK_CASH_EXITS' for r in report['results']):raise ValueError('Missing native cash/risk/exit audit')
    groups,_,schedule=main.parent.load_groups();days=pd.DatetimeIndex(schedule.date);sch=schedule.set_index('date')
    candidates=pd.read_parquet(main.parent.PARENT/'campaigns.parquet')
    actions=pd.read_parquet(main.parent.PARENT/'corporate-actions.parquet')
    if not actions.empty:actions['ex_date']=pd.to_datetime(actions.ex_date)
    signals=pd.read_parquet(root/'signals.parquet');units=pd.read_parquet(root/'unit-results.parquet').set_index('pair_id')
    bands=pd.read_parquet(root/'opening-bands.parquet').set_index('pair_id');notes=pd.read_parquet(root/'signal-decisions.parquet')
    reserves=pd.read_parquet(root/'reservations.parquet');reserve_map=dict(zip(reserves.pair_id,reserves.reason)) if len(reserves) else {}
    qualified=set();missing=set();checked_signals=checked_units=0
    for row in candidates.itertuples():
        found,reasons,event,why=selection(row,groups,schedule,main.parent.END)
        why=why or reservation(row,found,groups,schedule,actions,main.parent.END)
        if why:
            equal(reserve_map.get(row.pair_id),why,'Reservation');missing.add(row.pair_id);continue
        qualified.add(row.pair_id)
        if row.pair_id not in units.index or row.pair_id not in bands.index:raise ValueError('Missing opportunity/band')
        for name,value in event.items():
            if name!='pair_id':equal(bands.loc[row.pair_id,name],value,'Band/'+name)
        observed=signals[signals.pair_id.eq(row.pair_id)&signals.arm.isin(main.TEST_ARMS)].set_index('arm')
        if set(observed.index)!=set(found):raise ValueError('Signal presence mismatch')
        for arm in main.TEST_ARMS:
            decision=notes[notes.pair_id.eq(row.pair_id)&notes.arm.eq(arm)]
            if len(decision)!=1 or decision.reason.iloc[0]!=reasons[arm]:raise ValueError('Decision reason mismatch')
            u=units.loc[row.pair_id]
            if bool(u[arm+'_signal'])!=(arm in found):raise ValueError('Signal flag mismatch')
            if arm not in found:
                if u[arm]!=0 or u[arm+'_cost25']!=0:raise ValueError('Abstention not zero')
                continue
            e=found[arm];s=observed.loc[arm]
            for name,value in e.items():equal(s[name],value,f'Signal/{row.pair_id}/{arm}/{name}')
            if s.range_available_at>=s.timestamp or s.band_known_at>=s.timestamp:raise ValueError('Uncausal thresholds')
            j=days.get_loc(e['date']);due=sch.loc[days[j+20],'market_open'];equal(s.due_open,due,'Horizon')
            path=pd.concat([groups[row.symbol,d] for d in days[j:j+21]])
            path=path[path.bar_timestamp.between(e['timestamp'],due)]
            price,stamp=scalar_outcome(path,e['price'],due);equal(u[arm+'_exit'],stamp,'Unit exit')
            for bps,col in [(8,arm),(25,arm+'_cost25')]:
                value=100*((price-e['price'])/e['price']-bps/10000*(1+price/e['price']))
                if not np.isclose(u[col],value,atol=1e-9,rtol=0):raise ValueError('Unit return mismatch')
                checked_units+=1
            checked_signals+=1
        if 'P04' in observed.index:
            if observed.loc['P04','trigger_direction']!='UP':raise ValueError('P04 is not first-UP LONG')
            for name in ['timestamp','price','due_open','signal_bar']:
                equal(observed.loc['P04',name],observed.loc['TIME_LONG',name],'Same-time control')
    if qualified!=set(units.index) or qualified!=set(bands.index) or missing!=set(reserve_map):raise ValueError('Coverage population mismatch')
    if checked_signals!=len(signals[signals.arm.isin(main.TEST_ARMS)]):raise ValueError('Unverified signal')
    spaced_ids=[];blocked={}
    for u in units.reset_index().sort_values(['entry_time','rank','symbol','pair_id']).itertuples():
        if u.symbol in blocked and u.entry_time<blocked[u.symbol]:continue
        spaced_ids.append(u.pair_id);blocked[u.symbol]=u.label_available
    spaced=pd.read_parquet(root/'nonoverlap.parquet')
    if list(spaced.pair_id)!=spaced_ids:raise ValueError('Nonoverlap selection mismatch')
    for check in report['nonoverlap_checks']:
        cohort=spaced[spaced.year.eq(check['year'])];selected=cohort[cohort.P04_signal]
        if check['opportunities']!=len(cohort) or check['p04_signals']!=len(selected) or check['p04_symbols']!=selected.symbol.nunique():
            raise ValueError('Sample counts mismatch')
    for result in report['results']:
        out=root/f'{result["arm"]}-fee{result["fee_bps"]}'/'cases'/str(result['year'])
        if result['arm']=='WINNER':
            old=main.REFERENCE/f'WINNER-fee{result["fee_bps"]}'/'cases'/str(result['year'])
            for name in ['trades.parquet','marks.parquet','decisions.json','maintenance.json','production-risk-events.json']:
                if digest(out/name)!=digest(old/name):raise ValueError('Original Winner changed')
        trades=pd.read_parquet(out/'trades.parquet');opened=main.READ(out/'open-positions.json')
        for record in trades.to_dict('records')+opened:
            match=signals[signals.pair_id.eq(record['pair_id'])&signals.arm.eq(result['arm'])&signals.year.eq(result['year'])]
            if len(match)!=1:raise ValueError('Unknown portfolio signal')
            equal(match.timestamp.iloc[0],pd.Timestamp(record['entry_timestamp']),'Portfolio entry')
            equal(match.due_open.iloc[0],pd.Timestamp(record['expiry']),'Portfolio expiry')
    audit=dict(status='PASS_P04_RANGE_FIRST_HIT_UNIT_CASH_B4_REVIEW',portfolio_cases=24,baseline_cases_exactly_reproduced=4,
        qualified_campaigns=len(units),reserved_campaigns=len(reserves),bands_verified=len(bands),
        signals_verified=checked_signals,unit_cost_results_verified=checked_units,
        report_sha256=digest(root/'report.json'),reviewer_source_sha256=digest(__file__),
        independent_human_review=False,production_promoted=False)
    atomic_json(root/'final-audit.json',audit);print(audit);return audit


if __name__=='__main__':
    import argparse
    from scripts.research.us_oracle_dual_thrust_p04 import OUTPUT
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output-dir',type=Path,default=OUTPUT)
    final_review(parser.parse_args().output_dir)
