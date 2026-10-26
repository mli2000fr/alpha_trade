"""Frozen P04 Dual Thrust LONG pilot, offline local raw SIP archives only.

First upper/lower close on J1, prior four COMPLETE regular-session ranges.
No provider, SQL, training, LLM, orders or production configuration changes.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from common.config_loader import load_config
from scripts.research import us_oracle_compression_p01 as parent
from scripts.research.us_oracle_partial_p02 import validate_config
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes

READ=parent.READ
REFERENCE=parent.OUTPUT
OUTPUT=Path('artifacts/research/us_oracle_dual_thrust_p04/20261022-v1')
ARMS=('WINNER','COMMON_WINNER','J1_WINNER','HIGH_J','TIME_LONG','P04')
TEST_ARMS=ARMS[1:]
CONTROLS=TEST_ARMS[:-1]
FEES=(8,25)
RULE=dict(prior_sessions=4,range_multiplier=.5,trigger_confirmation_bars=1,
          trigger_session='ORACLE_J1_ONLY',first_down='ABSTAIN_NO_REVERSAL',
          stop_pct=.07,trailing_pct=.15,horizon_sessions=20,rounding='SCALAR_8_DECIMALS')


def range_from_prior(prior):
    """Four supplied complete raw regular sessions, ending J; never J1 H/L/C."""
    if len(prior)!=4: raise ValueError('FOUR_PRIOR_SESSIONS_REQUIRED')
    high=max(float(f.high.max()) for f in prior)
    low=min(float(f.low.min()) for f in prior)
    closes=[float(f.close.iloc[-1]) for f in prior]
    value=round(max(high-min(closes),max(closes)-low),8)
    if not np.isfinite(value) or value<=0: raise ValueError('NONPOSITIVE_PRIOR_RANGE')
    return value


def session_entries(frame,prior_high,prior_range):
    """First completed-bar hit only, next SAME-session open, no touch fill.

    TIME_LONG buys at the first UP or DOWN hit; P04 buys only an UP first hit.
    A DOWN first hit ends P04's attempt, no later reversal or tomorrow retry.
    """
    if frame.empty: raise ValueError('EMPTY_J1_SESSION')
    if not (frame.bar_end_timestamp.iloc[:-1].to_numpy()==frame.bar_timestamp.iloc[1:].to_numpy()).all():
        raise ValueError('NONCONTIGUOUS_SESSION')
    if len({t.tz_convert('America/New_York').date() for t in frame.bar_timestamp})!=1:
        raise ValueError('MIXED_SESSIONS')
    opening=float(frame.open.iloc[0]);upper=round(opening+.5*prior_range,8);lower=round(opening-.5*prior_range,8)
    if not np.isfinite([opening,prior_high,prior_range,upper,lower]).all() or not 0<lower<opening<upper:
        raise ValueError('INVALID_OPENING_BANDS')
    closes=frame.close.to_numpy(float);times=frame.bar_timestamp
    found={};notes={};event=dict(opening=opening,prior_range=prior_range,upper=upper,lower=lower,
                              first_direction='NONE',first_trigger_bar=pd.NaT)

    def entry(k,threshold,kind):
        return dict(timestamp=times.iloc[k+1],price=float(frame.open.iloc[k+1]),
            signal_close=float(closes[k]),signal_bar=times.iloc[k],prior_high=float(prior_high),
            opening=opening,prior_range=float(prior_range),upper=upper,lower=lower,
            trigger_direction=kind,entry_threshold=float(threshold))

    winner=np.flatnonzero((closes[:-2]<=prior_high)&(closes[1:-1]>prior_high)&(closes[2:]>prior_high))
    if len(winner) and int(winner[0])+3<len(frame):
        k=int(winner[0])+2;found['J1_WINNER']=entry(k,prior_high,'HIGH_J_TWO_CLOSES');notes['J1_WINNER']='SIGNAL'
    else: notes['J1_WINNER']='NO_SAME_SESSION_WINNER_FILL'
    high=np.flatnonzero(closes>prior_high)
    if len(high) and int(high[0])+1<len(frame):
        k=int(high[0]);found['HIGH_J']=entry(k,prior_high,'HIGH_J_ONE_CLOSE');notes['HIGH_J']='SIGNAL'
    else: notes['HIGH_J']='NO_SAME_SESSION_HIGH_J_FILL'

    hits=np.flatnonzero((closes>upper)|(closes<lower))
    if not len(hits): notes.update(TIME_LONG='NO_DUAL_TRIGGER',P04='NO_DUAL_TRIGGER')
    else:
        k=int(hits[0]);direction='UP' if closes[k]>upper else 'DOWN'
        event.update(first_direction=direction,first_trigger_bar=times.iloc[k])
        if k+1>=len(frame): notes.update(TIME_LONG='LAST_BAR_NO_FILL',P04='LAST_BAR_NO_FILL')
        else:
            trigger=entry(k,upper if direction=='UP' else lower,direction)
            found['TIME_LONG']=trigger;notes['TIME_LONG']='SIGNAL'
            if direction=='UP':found['P04']=dict(trigger);notes['P04']='SIGNAL'
            else: notes['P04']='DOWN_FIRST_ABSTAIN'
    return found,notes,event


def select_entries(row,groups,schedule):
    days=pd.DatetimeIndex(schedule.date);i=days.get_loc(row.oracle_date);sch=schedule.set_index('date')
    if i<3 or any((row.symbol,d) not in groups for d in days[i-3:i+1]):
        return {},{},None,'MISSING_FOUR_PRIOR_SESSIONS'
    if days[i+1]>parent.END:return {},{},None,'J1_IMMATURE'
    if (row.symbol,days[i+1]) not in groups:return {},{},None,'MISSING_J1_SESSION'
    prior=[groups[row.symbol,d] for d in days[i-3:i+1]]
    try:
        span=range_from_prior(prior)
        entries,notes,event=session_entries(groups[row.symbol,days[i+1]],float(prior[-1].high.max()),span)
    except ValueError as exc:return {},{},None,str(exc)
    for entry in entries.values():entry.update(date=days[i+1],delay=1)
    winner,why=parent.history.first_entry(row,groups,schedule)
    if winner is not None:
        j=days.get_loc(winner['date']);g=groups[row.symbol,winner['date']]
        k=pd.DatetimeIndex(g.bar_timestamp).get_loc(winner['timestamp'])
        entries['COMMON_WINNER']=dict(winner,prior_high=float(groups[row.symbol,days[j-1]].high.max()),
            signal_close=float(g.close.iloc[k-1]),signal_bar=g.bar_timestamp.iloc[k-1])
        notes['COMMON_WINNER']='SIGNAL'
    elif why=='NO_CURRENT_RUNTIME_SIGNAL':notes['COMMON_WINNER']='NO_BREAKOUT'
    else:return {},{},None,why
    for entry in entries.values():
        entry.update(range_source_start=days[i-3],range_source_end=days[i],
            range_available_at=sch.loc[days[i],'market_close'],band_known_at=sch.loc[days[i+1],'market_open'])
    event.update(pair_id=int(row.pair_id),symbol=row.symbol,oracle_date=row.oracle_date,
        range_source_start=days[i-3],range_source_end=days[i],range_available_at=sch.loc[days[i],'market_close'],
        band_known_at=sch.loc[days[i+1],'market_open'])
    return entries,notes,event,None


def common_reservation(row,entries,groups,schedule,actions):
    days=pd.DatetimeIndex(schedule.date);i=days.get_loc(row.oracle_date)
    if not actions.empty and ((actions.symbol==row.symbol)&actions.ex_date.between(days[i-3],days[i+1])).any():
        return 'KNOWN_LOOKBACK_CORPORATE_ACTION'
    return parent.common_reservation(row,entries,groups,schedule,actions)


def prepare(root):
    root=Path(root)
    if root.exists():raise ValueError('Fresh immutable output required')
    verify_hashes(REFERENCE,READ(REFERENCE/'report.json')['files'])
    audit=READ(REFERENCE/'final-audit.json')
    if audit['status']!='PASS_P01_SEPARATE_ARITHMETIC_AND_PORTFOLIO_AUDITS' or audit['primary_report_sha256']!=digest(REFERENCE/'report.json'):
        raise ValueError('Verified Winner anchor required')
    verify_hashes(parent.PARENT,READ(parent.PARENT/'snapshot.json')['files'])
    config=load_config()['winner_pyramiding'];validate_config(config)
    sources=dict(READ(REFERENCE/'protocol.json')['sources'])
    paths=[Path(__file__),Path('scripts/research/us_oracle_dual_thrust_p04_audit.py'),
        Path('tests/test_us_oracle_dual_thrust_p04.py'),Path('doc/ml/oracle_dual_thrust_p04_20261022.md'),
        Path('scripts/research/us_oracle_partial_p02.py'),Path('config.yaml'),
        Path('risk_management/concentration.py'),REFERENCE/'report.json',REFERENCE/'final-audit.json']
    sources.update({str(p):digest(p) for p in paths})
    root.mkdir(parents=True)
    atomic_json(root/'protocol.json',dict(created_at_utc=datetime.now(timezone.utc).isoformat(),sources=sources,
        rule=RULE,arms=ARMS,controls=CONTROLS,fees_bps_per_leg=FEES,configured_winner=config,
        selection='Original213researchCatBoostPATH_H20campaigns, no new data or rerank. '
            'Prior4complete regularrawsessions endingOracleJ; J1only for four intraday controls/P04. '
            'COMMON_WINNER retains existing first fresh2close break over20sessions for window control.',
        formula='DailyOHLC aggregated ONLY from complete qualified regularraw5m. '
            'R=round(max(maxH-minC,maxC-minL),8), closes=lastregular5mclose, not claimed auction official close. '
            'At J1open freeze upper/lower=round(open+/-0.5R,8). Never use J1H/L/finalC. '
            'R>0 and 0<lower<open<upper required, no parameter search.',
        trigger='FIRST completedJ1bar strictly beyond upper or lower. '
            'UP:first P04LONG and TIME_LONG at nextcontiguoussame-sessionopen. '
            'DOWN:first P04abstains irrevocably, TIME_LONG neverthelessLONG at sameopen. '
            'Firsthitlastbar cannotfill: no tomorrow entry. No later reversal or retry.',
        controls_description='COMMON_WINNER: old20sessionfresh2close entry on common cohort; '
            'J1_WINNER: samefresh2close priorJhigh onJ1only, distinguishes entry-window change; '
            'HIGH_J:firstoneclose>Jhigh onJ1, distinguishes confirmation count/threshold; '
            'TIME_LONG:alwaysbuy first UP or DOWN Dualhit, same time as observed direction decision. '
            'WINNER:separate original200campaignanchor, four exact reproductions.',
        unchanged='Annual4000USD,1xentrygrosscap,HALF/nativeSL7sizing/constraints/B4DD15, '
            'SL7/TR15/noTP/noadd,20holding sessions entryincluded thenOPEN21. Fees8/25bpsperleg. '
            'Same formulas, actual quantities/cash/B4 admissions may diverge.',
        coverage='Local sealed raw SIP regular unfilled5m only, no SQL/download. '
            'Missingprior4/J1/Winnerscan or emitted entry fullfuturepath throughOPEN21 reservesALLcommonarms. '
            'No signal cash/zero units retained. Known lookback/holding actions reserved; inherited table incomplete.',
        evaluation='Known2025/2026throughSep30, not pristine holdout; no2024absent archive. '
            'Unit opportunity pairing including abstention, conservativeOracleJ40nonoverlap, '
            'monthlybootstrap2000seed731. LONG economic only; DOWN not a qualified SHORT backtest.',
        criteria=dict(min_nonoverlap_p04_per_year=30,min_p04_symbols_per_year=10,
            positive_p04_return_both_years_both_fees=True,positive_increment_vs_all_controls_both_years_both_fees=True,
            dd_not_worse_vs_all_controls_fee8=True,positive_unit_increment_vs_all_controls_fee25=True,
            monthly_lower95_gt_zero_vs_all_controls=True,minimum_months=6),
        limitations=READ(REFERENCE/'protocol.json')['limitations']+[
            'Prior4rawsession coverage adds conditional selection; frozen original cohort already survivor/futurecomplete selected.',
            'First-DOWN abstention is a predeclared LONG policy; no borrow-qualified SHORT PnL or inversion.',
            'Inherited PIT/identity/actions/quotes/latency limitations prevent full live parity.'],
        training=False,provider_calls=False,sql_writes=False,broker_calls=False,production_promoted=False,full_live_parity=False))
    atomic_json(root/'progress.json',dict(status='PREPARED',completed=0,total=24))


def opportunity_checks(frame):
    checks=[]
    for year,g in frame.groupby('year'):
        selected=g[g.P04_signal];controls={}
        for control in CONTROLS:
            delta=g.P04-g[control]
            controls[control]=dict(increment_pp=float(delta.mean()),stress_increment_pp=float((g.P04_cost25-g[control+'_cost25']).mean()),
                ci=parent.history.monthly_interval(g.oracle_date.dt.tz_localize('UTC'),delta))
        checks.append(dict(year=int(year),opportunities=len(g),p04_signals=len(selected),p04_symbols=int(selected.symbol.nunique()),controls=controls))
    return checks


def analyze(root):
    root=Path(root)
    if (root/'report.json').exists():raise ValueError('Already sealed')
    protocol=READ(root/'protocol.json');verify_hashes(Path('.'),protocol['sources'])
    verify_hashes(parent.PARENT,READ(parent.PARENT/'snapshot.json')['files'])
    groups,quality,schedule=parent.load_groups();sch=schedule.set_index('date');days=pd.DatetimeIndex(schedule.date)
    campaigns=pd.read_parquet(parent.PARENT/'campaigns.parquet')
    if len(campaigns)!=213 or campaigns.pair_id.duplicated().any():raise ValueError('Frozen cohort changed')
    actions=pd.read_parquet(parent.PARENT/'corporate-actions.parquet')
    if not actions.empty:actions['ex_date']=pd.to_datetime(actions.ex_date)
    units=[];signals=[];reservations=[];notes=[];bands=[];calendar=parent.history.ArchiveCalendar(schedule)
    for row in campaigns.itertuples():
        entries,reasons,event,why=select_entries(row,groups,schedule)
        why=why or common_reservation(row,entries,groups,schedule,actions)
        if why:
            reservations.append(dict(pair_id=int(row.pair_id),symbol=row.symbol,oracle_date=row.oracle_date,reason=why));continue
        bands.append(event);i=days.get_loc(row.oracle_date)
        unit=dict(pair_id=int(row.pair_id),symbol=row.symbol,rank=int(row.rank),year=row.oracle_date.year,
            oracle_date=row.oracle_date,entry_time=sch.loc[days[i+1],'market_open'],label_available=sch.loc[days[i+40],'market_open'])
        for arm in TEST_ARMS:
            entry=entries.get(arm);unit[arm+'_signal']=entry is not None;unit[arm]=unit[arm+'_cost25']=0.
            notes.append(dict(pair_id=int(row.pair_id),symbol=row.symbol,oracle_date=row.oracle_date,arm=arm,reason=reasons[arm]))
            if entry is None:continue
            j=days.get_loc(entry['date']);due=sch.loc[days[j+20],'market_open']
            path=pd.concat([groups[row.symbol,d] for d in days[j:j+21]],ignore_index=True)
            outcome=parent.history.unit_outcome(path,entry,parent.history.BASE,calendar)
            unit[arm]=outcome['net_pct'];unit[arm+'_cost25']=parent.history.unit_outcome(path,entry,parent.history.BASE,calendar,.0025)['net_pct']
            unit[arm+'_exit']=outcome['exit_time']
            signals.append(dict(pair_id=int(row.pair_id),symbol=row.symbol,rank=int(row.rank),oracle_date=row.oracle_date,
                year=entry['date'].year,arm=arm,due_open=due,**entry))
        units.append(unit)
    frame=pd.DataFrame(units)
    if frame.empty:raise ValueError('No common qualified opportunities')
    new=pd.DataFrame(signals);original=pd.read_parquet(REFERENCE/'signals.parquet');original=original[original.arm.eq('WINNER')].copy()
    all_signals=pd.concat([original,new],ignore_index=True)
    frame.to_parquet(root/'unit-results.parquet',index=False);all_signals.to_parquet(root/'signals.parquet',index=False)
    pd.DataFrame(reservations).to_parquet(root/'reservations.parquet',index=False)
    pd.DataFrame(notes).to_parquet(root/'signal-decisions.parquet',index=False)
    pd.DataFrame(bands).to_parquet(root/'opening-bands.parquet',index=False)
    pd.DataFrame(quality).to_parquet(root/'session-quality.parquet',index=False)
    spaced=parent.history.spaced(frame);spaced.to_parquet(root/'nonoverlap.parquet',index=False)
    checks=opportunity_checks(spaced);results=[]
    for fee in FEES:
        for year in (2025,2026):
            for arm in ARMS:
                atomic_json(root/'progress.json',dict(status='PORTFOLIO_REPLAY',completed=len(results),total=24,year=year,arm=arm,fee_bps=fee))
                r=parent.portfolio(root,arm,year,fee,all_signals,groups,schedule)
                if arm=='WINNER':
                    out=root/f'WINNER-fee{fee}'/'cases'/str(year);old=REFERENCE/f'WINNER-fee{fee}'/'cases'/str(year)
                    for name in ['trades.parquet','marks.parquet','decisions.json','maintenance.json','production-risk-events.json']:
                        if digest(out/name)!=digest(old/name):raise ValueError('Exact Winner anchor changed:'+name)
                r['baseline_exact_reproduction']=arm=='WINNER';results.append(r)
                print(f'{year} {arm} fee{fee}: {r["return_pct"]:.3f}% DD{r["max_drawdown_pct"]:.3f} trades{r["trades"]}',flush=True)
    comparisons=[]
    for p in [r for r in results if r['arm']=='P04']:
        for control in CONTROLS:
            b=next(r for r in results if r['arm']==control and r['year']==p['year'] and r['fee_bps']==p['fee_bps'])
            comparisons.append(dict(year=p['year'],fee_bps=p['fee_bps'],control=control,
                increment_pp=p['return_pct']-b['return_pct'],dd_increment_pp=p['max_drawdown_pct']-b['max_drawdown_pct']))
    enough=all(any(c['year']==y and c['p04_signals']>=30 and c['p04_symbols']>=10 for c in checks) for y in (2025,2026))
    passes=enough and all(r['return_pct']>0 for r in results if r['arm']=='P04') and all(c['increment_pp']>0 for c in comparisons) and all(
        c['dd_increment_pp']<=0 for c in comparisons if c['fee_bps']==8) and all(c['stress_increment_pp']>0 and c['ci']['months']>=6 and c['ci']['lower95']>0
        for year in checks for c in year['controls'].values())
    pd.DataFrame([{k:v for k,v in r.items() if k!='audit'} for r in results]).to_csv(root/'annual-summary.csv',index=False)
    verify_hashes(Path('.'),protocol['sources']);verify_hashes(REFERENCE,READ(REFERENCE/'report.json')['files'])
    report=dict(status='EXPLORATORY_P04_WORTH_CONFIRMATION' if passes else 'INSUFFICIENT_P04_SAMPLE' if not enough else 'NO_GO_P04_NOT_CONFIRMED',
        original_campaigns=213,qualified_common_campaigns=len(frame),symbols=int(frame.symbol.nunique()),
        reserved=dict(Counter(r['reason'] for r in reservations)),
        signal_counts={arm:{str(int(y)):int(n) for y,n in new[new.arm.eq(arm)].groupby('year').size().items()} for arm in TEST_ARMS},
        signal_reasons={arm:dict(Counter(n['reason'] for n in notes if n['arm']==arm)) for arm in TEST_ARMS},
        first_direction_counts=dict(Counter(b['first_direction'] for b in bands)),nonoverlap_checks=checks,
        results=results,comparisons=comparisons,sufficient_sample=enough,production_promoted=False,
        files={str(p.relative_to(root)):digest(p) for p in root.rglob('*') if p.is_file() and p.name not in ['run.lock','progress.json','report.json']})
    atomic_json(root/'report.json',report);atomic_json(root/'progress.json',dict(status=report['status'],completed=24,total=24,failed=0))
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output-dir',type=Path,default=OUTPUT)
    parser.add_argument('--phase',choices=['prepare','analyze','run'],default='run');args=parser.parse_args()
    from scripts.research.oracle_path_confirmation import exclusive_run
    try:
        if args.phase in ('prepare','run'):prepare(args.output_dir)
        if args.phase in ('analyze','run'):
            with exclusive_run(args.output_dir):analyze(args.output_dir)
    except Exception as exc:
        if (args.output_dir/'protocol.json').exists() and not (args.output_dir/'report.json').exists():
            atomic_json(args.output_dir/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)))
        raise


if __name__=='__main__':main()
