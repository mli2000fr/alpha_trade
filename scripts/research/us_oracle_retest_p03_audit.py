"""Separate P03 signal/ATR/reservation arithmetic and native replay review.

No primary selector/timing/ATR calls. Same assistant, not independent human.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes


def scalar_atr(frame):
    values=[]; previous=None; estimate=None
    for row in frame.itertuples():
        value=float(row.high-row.low)
        if previous is not None: value=max(value,abs(row.high-previous),abs(row.low-previous))
        previous=float(row.close);values.append(value)
        if len(values)==20: estimate=sum(values)/20
        elif len(values)>20: estimate=(19*estimate+value)/20
    if estimate is None: raise ValueError('ATR_WARMUP_MISSING')
    estimate=round(float(estimate),8)
    if not np.isfinite(estimate) or estimate<=0: raise ValueError('ATR_NONPOSITIVE')
    return estimate


def timing(frame, start, level, atr):
    """Enumerate first touch and first subsequent valid pair, not state machine."""
    close=list(map(float,frame.close)); low=list(map(float,frame.low)); n=len(close)
    lower=round(level+(-1)*round(atr,8),8);upper=round(level+round(atr,8),8)
    expected={}; reasons={}; delayed=start+6
    if delayed>=n: reasons['DELAY_CONTROL']='FIXED_DELAY_NO_SAME_SESSION_FILL'
    elif any(x<lower for x in low[start:delayed]): reasons['DELAY_CONTROL']='INVALIDATED_DURING_FIXED_WAIT'
    elif any(x<=level for x in close[delayed-2:delayed]): reasons['DELAY_CONTROL']='FIXED_DELAY_LAST_TWO_NOT_ABOVE'
    else: expected['DELAY_CONTROL']=(delayed,None); reasons['DELAY_CONTROL']='SIGNAL'
    last=min(start+11,n-2)
    invalid=next((i for i in range(start,last+1) if low[i]<lower),None)
    ceiling=invalid if invalid is not None else last+1
    touch=next((i for i in range(start,ceiling) if low[i]<=upper),None)
    confirm=next((i for i in range(touch+2,ceiling) if close[i-1]>level and close[i]>level),None) if touch is not None else None
    if confirm is not None: expected['P03']=(confirm+1,touch); reasons['P03']='SIGNAL'
    else:
        reasons['P03']=('INVALIDATED_BEFORE_RETEST_CONFIRMATION' if invalid is not None else
                        'NO_RETEST_IN_WINDOW' if touch is None else 'RETEST_NOT_CONFIRMED_IN_WINDOW')
    return expected,reasons


def selection(row,groups,schedule,end):
    days=pd.DatetimeIndex(schedule.date); sch=schedule.set_index('date'); first=days.get_loc(row.oracle_date)
    for j in range(first+1,first+21):
        day,previous=days[j],days[j-1]
        if day>end: return {},{},'ENTRY_WINDOW_CENSORED'
        if (row.symbol,day) not in groups or (row.symbol,previous) not in groups:
            return {},{},'ENTRY_SCAN_MISSING_SESSION'
        frame=groups[row.symbol,day];prev=groups[row.symbol,previous];level=float(prev.high.max())
        c=list(map(float,frame.close))
        start=next((i for i in range(3,len(c)) if c[i-3]<=level and c[i-2]>level and c[i-1]>level),None)
        if start is None: continue
        try: atr=scalar_atr(prev)
        except ValueError as exc: return {},{},str(exc)
        indices,reasons=timing(frame,start,level,atr)
        reasons['COMMON_WINNER']='SIGNAL'; indices['COMMON_WINNER']=(start,None)
        found={}
        for arm,(i,touched) in indices.items():
            found[arm]=dict(timestamp=frame.bar_timestamp.iloc[i],price=float(frame.open.iloc[i]),date=day,
                delay=j-first,signal_close=c[i-1],signal_bar=frame.bar_timestamp.iloc[i-1],
                cross_bar=frame.bar_timestamp.iloc[start-2],prior_high=level,
                atr_source_date=previous,atr_available_at=sch.loc[previous,'market_close'])
            if arm!='COMMON_WINNER':
                found[arm].update(anchor_timestamp=frame.bar_timestamp.iloc[start],atr_previous=atr,
                    tolerance=round(atr,8),lower_bound=round(level-atr,8),upper_bound=round(level+atr,8),
                    delay_bars=i-start,retest_bar=frame.bar_timestamp.iloc[touched] if touched is not None else pd.NaT)
        return found,reasons,None
    return {},dict(COMMON_WINNER='NO_BREAKOUT',DELAY_CONTROL='NO_BREAKOUT',P03='NO_BREAKOUT'),None


def reservation(row,entries,groups,schedule,actions,end):
    days=pd.DatetimeIndex(schedule.date)
    for entry in entries.values():
        i=days.get_loc(entry['date']); dates=days[i:i+21]
        if dates[-1]>end: return 'COMMON_H20_IMMATURE'
        if any((row.symbol,d) not in groups for d in dates): return 'COMMON_H20_MISSING_SESSION'
        if not actions.empty and ((actions.symbol==row.symbol)&actions.ex_date.between(dates[0],dates[-1])).any():
            return 'KNOWN_CORPORATE_ACTION'
    return None


def final_review(root):
    from scripts.research import us_oracle_retest_p03 as main
    from scripts.research.us_oracle_compression_p01_audit import scalar_outcome
    root=Path(root);report=main.READ(root/'report.json');verify_hashes(root,report['files'])
    verify_hashes(Path('.'),main.READ(root/'protocol.json')['sources'])
    expected_cases={(a,y,f) for a in main.ARMS for y in [2025,2026] for f in [8,25]}
    if len(report['results'])!=16 or {(r['arm'],r['year'],r['fee_bps']) for r in report['results']}!=expected_cases:
        raise ValueError('Sixteen distinct cases required')
    if not all(r['audit']['status']=='PASS_PRODUCTION_RISK_CASH_EXITS' for r in report['results']):
        raise ValueError('Native cash/risk/exit audit missing')
    groups,_,schedule=main.parent.load_groups(); days=pd.DatetimeIndex(schedule.date);sch=schedule.set_index('date')
    original=pd.read_parquet(main.parent.PARENT/'campaigns.parquet')
    actions=pd.read_parquet(main.parent.PARENT/'corporate-actions.parquet')
    if not actions.empty: actions['ex_date']=pd.to_datetime(actions.ex_date)
    signals=pd.read_parquet(root/'signals.parquet');units=pd.read_parquet(root/'unit-results.parquet').set_index('pair_id')
    reserves=pd.read_parquet(root/'reservations.parquet'); notes=pd.read_parquet(root/'signal-decisions.parquet')
    reserve_map=dict(zip(reserves.pair_id,reserves.reason)) if len(reserves) else {}
    checked_signals=checked_units=0; qualified=set(); missing=set()
    for row in original.itertuples():
        expected,reasons,why=selection(row,groups,schedule,main.parent.END)
        why=why or reservation(row,expected,groups,schedule,actions,main.parent.END)
        if why:
            if reserve_map.get(row.pair_id)!=why: raise ValueError('Reservation mismatch')
            missing.add(row.pair_id);continue
        qualified.add(row.pair_id)
        if row.pair_id not in units.index: raise ValueError('Missing opportunity')
        observed=signals[signals.pair_id.eq(row.pair_id)&signals.arm.isin(main.TEST_ARMS)].set_index('arm')
        if set(observed.index)!=set(expected): raise ValueError('Signal presence mismatch')
        for arm in main.TEST_ARMS:
            decision=notes[notes.pair_id.eq(row.pair_id)&notes.arm.eq(arm)]
            if len(decision)!=1 or decision.reason.iloc[0]!=reasons[arm]: raise ValueError('Missing/wrong abstention reason')
            u=units.loc[row.pair_id]
            if bool(u[arm+'_signal'])!=(arm in expected): raise ValueError('Unit signal flag mismatch')
            if arm not in expected:
                if u[arm]!=0 or u[arm+'_cost25']!=0: raise ValueError('Abstention not zero')
                continue
            signal=observed.loc[arm]; e=expected[arm]
            for name,value in e.items():
                actual=signal[name]
                if pd.isna(value) and pd.isna(actual): continue
                if actual!=value: raise ValueError(f'Signal mismatch {row.pair_id}/{arm}/{name}: {actual}!={value}')
            if signal.atr_available_at>=signal.timestamp: raise ValueError('Uncausal ATR')
            k=days.get_loc(e['date']); due=sch.loc[days[k+20],'market_open']
            if signal.due_open!=due: raise ValueError('Wrong holding horizon')
            path=pd.concat([groups[row.symbol,d] for d in days[k:k+21]])
            path=path[path.bar_timestamp.between(e['timestamp'],due)]
            price,stamp=scalar_outcome(path,e['price'],due)
            if u[arm+'_exit']!=stamp: raise ValueError('Wrong unit exit')
            for bps,column in [(8,arm),(25,arm+'_cost25')]:
                net=100*((price-e['price'])/e['price']-bps/10000*(1+price/e['price']))
                if not np.isclose(u[column],net,atol=1e-9,rtol=0): raise ValueError('Unit return mismatch')
                checked_units+=1
            checked_signals+=1
    if qualified!=set(units.index) or missing!=set(reserve_map): raise ValueError('Population mismatch')
    if checked_signals!=len(signals[signals.arm.isin(main.TEST_ARMS)]): raise ValueError('Unverified signal')
    for r in report['results']:
        out=root/f'{r["arm"]}-fee{r["fee_bps"]}'/'cases'/str(r['year'])
        if r['arm']=='WINNER':
            reference=main.REFERENCE/f'WINNER-fee{r["fee_bps"]}'/'cases'/str(r['year'])
            for name in ['trades.parquet','marks.parquet','decisions.json','maintenance.json','production-risk-events.json']:
                if digest(out/name)!=digest(reference/name): raise ValueError('Changed Winner anchor')
        trades=pd.read_parquet(out/'trades.parquet'); opened=main.READ(out/'open-positions.json')
        for trade in trades.to_dict('records')+opened:
            matching=signals[signals.pair_id.eq(trade['pair_id'])&signals.arm.eq(r['arm'])&signals.year.eq(r['year'])]
            if len(matching)!=1 or matching.timestamp.iloc[0]!=pd.Timestamp(trade['entry_timestamp']):
                raise ValueError('Portfolio entry without signal')
            if matching.due_open.iloc[0]!=pd.Timestamp(trade['expiry']): raise ValueError('Portfolio expiry mismatch')
    audit=dict(status='PASS_P03_INDEPENDENT_SIGNALS_ATR_UNITS_CASH_B4_REVIEW',portfolio_cases=16,
        baseline_cases_exactly_reproduced=4,qualified_campaigns=len(units),reserved_campaigns=len(reserves),
        signals_verified=checked_signals,unit_cost_results_verified=checked_units,
        report_sha256=digest(root/'report.json'),reviewer_source_sha256=digest(__file__),
        independent_human_review=False,production_promoted=False)
    atomic_json(root/'final-audit.json',audit);print(audit);return audit


if __name__=='__main__':
    import argparse
    from scripts.research.us_oracle_retest_p03 import OUTPUT
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output-dir',type=Path,default=OUTPUT)
    final_review(parser.parse_args().output_dir)
