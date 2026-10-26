"""Frozen P03: first confirmed retest, fixed-delay control, offline native replay.

No SQL, provider, LLM, training, orders or production mutations. Known research
cohort, not all daily Oracle TOP10. Every timing rule frozen before outcomes.
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

READ = parent.READ
REFERENCE = parent.OUTPUT
OUTPUT = Path('artifacts/research/us_oracle_retest_p03/20261022-v1')
ARMS = ('WINNER', 'COMMON_WINNER', 'DELAY_CONTROL', 'P03')
TEST_ARMS = ARMS[1:]
FEES = (8, 25)
RULE = dict(atr_period=20, tolerance_atr=1., confirmation_bars=2,
            max_wait_bars=12, delay_control_bars=6, entry_valid_sessions=20,
            stop_pct=.07, trailing_pct=.15, horizon_sessions=20)


def previous_atr(frame):
    """Last Wilder ATR20 of previous COMPLETE regular raw5m session.

    First TR high-low; SMA20 seed; session reset, so no overnight gap. Round
    scalar ATR to eight decimals to stabilize independent arithmetic. Never
    use split-adjusted daily ATR as a raw intraday retest distance.
    """
    close = frame.close.to_numpy(float); high = frame.high.to_numpy(float); low = frame.low.to_numpy(float)
    if len(frame) < RULE['atr_period']: raise ValueError('ATR_WARMUP_MISSING')
    ranges = np.maximum(high-low, np.maximum(np.abs(high-np.r_[close[0],close[:-1]]),
                                             np.abs(low-np.r_[close[0],close[:-1]])))
    value = float(ranges[:20].mean())
    for tr in ranges[20:]: value = (19*value+float(tr))/20
    value = round(value,8)
    if not np.isfinite(value) or value <= 0: raise ValueError('ATR_NONPOSITIVE')
    return value


def timing_signals(frame, anchor, atr):
    """Anchor is the FIRST Winner confirmation; no subsequent breakout retry.

    Retest starts in a bar AFTER the anchor confirmation. A low below lower
    bound invalidates BEFORE any same-bar recovery; a touch bar never counts
    as one of its own two recovery bars. Buy only at next contiguous open.
    """
    if not np.isfinite(atr) or atr <= 0: raise ValueError('Invalid prior ATR')
    times = pd.DatetimeIndex(frame.bar_timestamp)
    if not (frame.bar_end_timestamp.iloc[:-1].to_numpy()==frame.bar_timestamp.iloc[1:].to_numpy()).all():
        raise ValueError('Noncontiguous regular session')
    if len({t.tz_convert('America/New_York').date() for t in times}) != 1:
        raise ValueError('One regular session required')
    fill = times.get_loc(anchor['timestamp']); confirm = fill-1
    level = float(anchor['prior_high']); tolerance = round(float(atr)*RULE['tolerance_atr'],8)
    upper, lower = round(level+tolerance,8), round(level-tolerance,8)
    if fill < 3 or not (frame.close.iloc[confirm-2] <= level < frame.close.iloc[confirm-1]
                        and frame.close.iloc[confirm] > level):
        raise ValueError('Unqualified Winner anchor')
    found = {}; notes = {}

    def signal(index, touched=None):
        return dict(anchor, timestamp=times[index], price=float(frame.open.iloc[index]),
            signal_close=float(frame.close.iloc[index-1]), signal_bar=times[index-1],
            anchor_timestamp=anchor['timestamp'], atr_previous=atr, tolerance=tolerance,
            lower_bound=lower, upper_bound=upper, retest_bar=times[touched] if touched is not None else pd.NaT,
            delay_bars=index-fill)

    # Fixed wait chosen ex ante, NOT derived from this occasion's future retest.
    delayed_index = fill+RULE['delay_control_bars']
    if delayed_index >= len(frame): notes['DELAY_CONTROL']='FIXED_DELAY_NO_SAME_SESSION_FILL'
    elif float(frame.low.iloc[fill:delayed_index].min()) < lower:
        notes['DELAY_CONTROL']='INVALIDATED_DURING_FIXED_WAIT'
    elif not frame.close.iloc[delayed_index-2:delayed_index].gt(level).all():
        notes['DELAY_CONTROL']='FIXED_DELAY_LAST_TWO_NOT_ABOVE'
    else:
        found['DELAY_CONTROL']=signal(delayed_index); notes['DELAY_CONTROL']='SIGNAL'

    touched = None; consecutive = 0; invalidated = False
    last = min(confirm+RULE['max_wait_bars'],len(frame)-2)
    for k in range(fill,last+1):
        if float(frame.low.iloc[k]) < lower:
            invalidated=True; break
        if touched is None:
            if float(frame.low.iloc[k]) <= upper: touched=k
            continue
        consecutive = consecutive+1 if float(frame.close.iloc[k]) > level else 0
        if consecutive >= RULE['confirmation_bars']:
            found['P03']=signal(k+1,touched); break
    notes['P03'] = ('SIGNAL' if 'P03' in found else 'INVALIDATED_BEFORE_RETEST_CONFIRMATION'
                    if invalidated else 'NO_RETEST_IN_WINDOW' if touched is None else 'RETEST_NOT_CONFIRMED_IN_WINDOW')
    return found, notes


def select_entries(row, groups, schedule):
    entry, why = parent.history.first_entry(row,groups,schedule)
    if entry is None:
        if why == 'NO_CURRENT_RUNTIME_SIGNAL': return {},dict(COMMON_WINNER='NO_BREAKOUT',DELAY_CONTROL='NO_BREAKOUT',P03='NO_BREAKOUT'),None
        return {},{},why
    days = pd.DatetimeIndex(schedule.date); j=days.get_loc(entry['date'])
    frame=groups[row.symbol,entry['date']]; prev=groups[row.symbol,days[j-1]]
    k=pd.DatetimeIndex(frame.bar_timestamp).get_loc(entry['timestamp'])
    anchor=dict(entry,prior_high=float(prev.high.max()),signal_close=float(frame.close.iloc[k-1]),
        signal_bar=frame.bar_timestamp.iloc[k-1],cross_bar=frame.bar_timestamp.iloc[k-2],
        atr_source_date=days[j-1],atr_available_at=schedule.set_index('date').loc[days[j-1],'market_close'])
    try: atr=previous_atr(prev)
    except ValueError as exc: return {},{},str(exc)
    variants, notes=timing_signals(frame,anchor,atr)
    notes['COMMON_WINNER']='SIGNAL'
    return dict(COMMON_WINNER=anchor,**variants),notes,None


def prepare(root):
    root=Path(root)
    if root.exists(): raise ValueError('Fresh immutable output required')
    verify_hashes(REFERENCE,READ(REFERENCE/'report.json')['files'])
    audit=READ(REFERENCE/'final-audit.json')
    if audit['status']!='PASS_P01_SEPARATE_ARITHMETIC_AND_PORTFOLIO_AUDITS' or audit['primary_report_sha256']!=digest(REFERENCE/'report.json'):
        raise ValueError('Verified Winner reference required')
    verify_hashes(parent.PARENT,READ(parent.PARENT/'snapshot.json')['files'])
    config=load_config()['winner_pyramiding']; validate_config(config)
    sources=dict(READ(REFERENCE/'protocol.json')['sources'])
    paths=[Path(__file__),Path('scripts/research/us_oracle_retest_p03_audit.py'),
        Path('tests/test_us_oracle_retest_p03.py'),Path('doc/ml/oracle_retest_p03_20261022.md'),
        Path('scripts/research/us_oracle_partial_p02.py'),Path('config.yaml'),
        Path('risk_management/concentration.py'),REFERENCE/'report.json',REFERENCE/'final-audit.json']
    sources.update({str(p):digest(p) for p in paths})
    root.mkdir(parents=True)
    atomic_json(root/'protocol.json',dict(created_at_utc=datetime.now(timezone.utc).isoformat(),sources=sources,
        rule=RULE,arms=ARMS,fees_bps_per_leg=FEES,configured_winner=config,
        selection='All213 frozen research campaigns, first Winner break only in20sessions afterOracle. '
            'No alternate day/breakout retry after missing retest, risk rejection or delayed-control abstention.',
        retest='Freeze prior raw daily high at first Winner break. Prior COMPLETE regular5m WilderATR20 '
            '(reset each session, SMAseed, scalarround8) supplies1ATR tolerance. '
            'Start AFTER two-close breakout. First low<=level+tolerance touches; '
            'any completed-bar low<level-tolerance cancels first, even same-bar recovery. '
            'Then TWO distinct later completed closes>level; reset count on close<=level. '
            'Max12post-confirmation bars, SAME SESSION, fill next contiguous open. '
            'Touch bar never counts toward recovery. No limit-touch fill or future-minimum timing.',
        control='Wait fixed6completed bars/30min after Winner execution time, chosen BEFORE outcomes. '
            'Same frozen level/band; all waiting lows>=lower and finaltwo closes>level required. '
            'Nextopen fill same session. No requirement to touch/retest. '
            'Do NOT match this delay to each future P03entry. Native3%signal-fill gap rule identical.',
        execution='All timing signals from completed bars only; nextopen execution not a hindsight filter. '
            'No additional stop widening or fill-price band filter. HardSL7/TR15 unchanged, noTP/add/partial. '
            '20holding sessions entry included thenOPEN21; standing gaps and nativeB4 keep priority.',
        portfolio='Annual4000USD,1x entry gross cap,HALF/nativeSL7sizing/B4DD15, fees8/25bps. '
            'Four original WINNER anchors/200campaigns must reproduce byte-exactly; '
            'three common arms compared separately, coverage may differ from oldP01cohort.',
        coverage='Only local sealed raw regular unfilled SIP, no SQL/download. '
            'Missing scan/ATR reserves campaign ALLarms. Full future paths throughOPEN21 '
            'required for every emitted signal, even if eventual exit earlier. '
            'No signal included as cash/zero unit opportunity, not dropped. '
            'Known corporate actions reserved, inherited event table not complete.',
        evaluation='2025/2026known exploratory, no2024 absent archive. '
            'Paired opportunity units, conservativeOracleJ40 nonoverlap, monthly bootstrap2000seed731. '
            'Portfolio plus sample/concentration/no-signal costs, not just selected winners.',
        criteria=dict(min_p03_nonoverlap_per_year=30,min_p03_symbols_per_year=10,
            positive_portfolio_increment_vs_both_controls_both_years_both_fees=True,
            dd_not_worse_vs_both_fee8=True,positive_unit_increment_vs_both_costs25=True,
            monthly_lower95_gt_zero_vs_both=True,minimum_months=6),
        limitations=READ(REFERENCE/'protocol.json')['limitations']+[
            '213 research campaigns already conditioned on older signals/future completeness; NOT all dailyTOP10.',
            'Tolerance ATR is prior-session5m, not daily ATR used separately by inherited risk sizing.',
            'Partial/missing PIT/identity/action/quotes/latency evidence prevents full live parity.'],
        production_promoted=False,training=False,sql_writes=False,provider_calls=False,broker_calls=False,full_live_parity=False))
    atomic_json(root/'progress.json',dict(status='PREPARED',completed=0,total=16))


def opportunity_checks(frame):
    checks=[]
    for year,g in frame.groupby('year'):
        selected=g[g.P03_signal]; deltas={}
        for control in ('COMMON_WINNER','DELAY_CONTROL'):
            delta=g.P03-g[control]
            deltas[control]=dict(increment_pp=float(delta.mean()),stress_increment_pp=float((g.P03_cost25-g[control+'_cost25']).mean()),
                ci=parent.history.monthly_interval(g.oracle_date.dt.tz_localize('UTC'),delta))
        checks.append(dict(year=int(year),opportunities=len(g),p03_signals=len(selected),p03_symbols=int(selected.symbol.nunique()),
            controls=deltas))
    return checks


def analyze(root):
    root=Path(root)
    if (root/'report.json').exists(): raise ValueError('Already sealed')
    protocol=READ(root/'protocol.json'); verify_hashes(Path('.'),protocol['sources'])
    verify_hashes(parent.PARENT,READ(parent.PARENT/'snapshot.json')['files'])
    groups,quality,schedule=parent.load_groups(); sch=schedule.set_index('date'); days=pd.DatetimeIndex(schedule.date)
    campaigns=pd.read_parquet(parent.PARENT/'campaigns.parquet')
    if len(campaigns)!=213 or campaigns.pair_id.duplicated().any(): raise ValueError('Frozen cohort changed')
    actions=pd.read_parquet(parent.PARENT/'corporate-actions.parquet')
    if not actions.empty: actions['ex_date']=pd.to_datetime(actions.ex_date)
    reservations=[]; notes=[]; signals=[]; units=[]
    calendar=parent.history.ArchiveCalendar(schedule)
    for row in campaigns.itertuples():
        entries,reasons,why=select_entries(row,groups,schedule)
        why=why or parent.common_reservation(row,entries,groups,schedule,actions)
        if why:
            reservations.append(dict(pair_id=int(row.pair_id),symbol=row.symbol,oracle_date=row.oracle_date,reason=why)); continue
        i=days.get_loc(row.oracle_date)
        unit=dict(pair_id=int(row.pair_id),symbol=row.symbol,rank=int(row.rank),year=row.oracle_date.year,
            oracle_date=row.oracle_date,entry_time=sch.loc[days[i+1],'market_open'],label_available=sch.loc[days[i+40],'market_open'])
        for arm in TEST_ARMS:
            notes.append(dict(pair_id=int(row.pair_id),symbol=row.symbol,oracle_date=row.oracle_date,arm=arm,reason=reasons[arm]))
            entry=entries.get(arm);unit[arm+'_signal']=entry is not None;unit[arm]=unit[arm+'_cost25']=0.
            if entry is None: continue
            j=days.get_loc(entry['date']); due=sch.loc[days[j+20],'market_open']
            path=pd.concat([groups[row.symbol,d] for d in days[j:j+21]],ignore_index=True)
            outcome=parent.history.unit_outcome(path,entry,parent.history.BASE,calendar)
            unit[arm]=outcome['net_pct'];unit[arm+'_cost25']=parent.history.unit_outcome(path,entry,parent.history.BASE,calendar,.0025)['net_pct']
            unit[arm+'_exit']=outcome['exit_time']
            signals.append(dict(pair_id=int(row.pair_id),symbol=row.symbol,rank=int(row.rank),oracle_date=row.oracle_date,
                year=entry['date'].year,arm=arm,due_open=due,**entry))
        units.append(unit)
    frame=pd.DataFrame(units)
    if frame.empty: raise ValueError('No common qualified opportunities')
    new=pd.DataFrame(signals)
    original=pd.read_parquet(REFERENCE/'signals.parquet');original=original[original.arm.eq('WINNER')].copy()
    all_signals=pd.concat([original,new],ignore_index=True)
    frame.to_parquet(root/'unit-results.parquet',index=False);all_signals.to_parquet(root/'signals.parquet',index=False)
    pd.DataFrame(reservations).to_parquet(root/'reservations.parquet',index=False)
    pd.DataFrame(notes).to_parquet(root/'signal-decisions.parquet',index=False)
    pd.DataFrame(quality).to_parquet(root/'session-quality.parquet',index=False)
    spaced=parent.history.spaced(frame);spaced.to_parquet(root/'nonoverlap.parquet',index=False)
    checks=opportunity_checks(spaced);results=[]
    for fee in FEES:
        for year in (2025,2026):
            for arm in ARMS:
                atomic_json(root/'progress.json',dict(status='PORTFOLIO_REPLAY',completed=len(results),total=16,arm=arm,year=year,fee_bps=fee))
                result=parent.portfolio(root,arm,year,fee,all_signals,groups,schedule)
                if arm=='WINNER':
                    out=root/f'WINNER-fee{fee}'/'cases'/str(year);old=REFERENCE/f'WINNER-fee{fee}'/'cases'/str(year)
                    for name in ['trades.parquet','marks.parquet','decisions.json','maintenance.json','production-risk-events.json']:
                        if digest(out/name)!=digest(old/name): raise ValueError('Exact Winner anchor changed:'+name)
                result['baseline_exact_reproduction']=arm=='WINNER'; results.append(result)
                print(f'{year} {arm} fee{fee}: {result["return_pct"]:.3f}% DD{result["max_drawdown_pct"]:.3f} trades{result["trades"]}',flush=True)
    comparisons=[]
    for p in [r for r in results if r['arm']=='P03']:
        for control in ('COMMON_WINNER','DELAY_CONTROL'):
            b=next(r for r in results if r['arm']==control and r['year']==p['year'] and r['fee_bps']==p['fee_bps'])
            comparisons.append(dict(year=p['year'],fee_bps=p['fee_bps'],control=control,
                increment_pp=p['return_pct']-b['return_pct'],dd_increment_pp=p['max_drawdown_pct']-b['max_drawdown_pct']))
    enough=all(any(c['year']==y and c['p03_signals']>=30 and c['p03_symbols']>=10 for c in checks) for y in (2025,2026))
    passes=enough and all(c['increment_pp']>0 for c in comparisons) and all(c['dd_increment_pp']<=0 for c in comparisons if c['fee_bps']==8) and all(
        c['stress_increment_pp']>0 and c['ci']['months']>=6 and c['ci']['lower95']>0 for year in checks for c in year['controls'].values())
    pd.DataFrame([{k:v for k,v in r.items() if k!='audit'} for r in results]).to_csv(root/'annual-summary.csv',index=False)
    verify_hashes(Path('.'),protocol['sources']);verify_hashes(REFERENCE,READ(REFERENCE/'report.json')['files'])
    report=dict(status='EXPLORATORY_P03_WORTH_CONFIRMATION' if passes else 'INSUFFICIENT_P03_SAMPLE' if not enough else 'NO_GO_P03_NOT_CONFIRMED',
        original_campaigns=213,qualified_common_campaigns=len(frame),symbols=int(frame.symbol.nunique()),
        reserved=dict(Counter(r['reason'] for r in reservations)),
        signal_counts={arm:{str(int(y)):int(n) for y,n in new[new.arm.eq(arm)].groupby('year').size().items()} for arm in TEST_ARMS},
        signal_reasons={arm:dict(Counter(n['reason'] for n in notes if n['arm']==arm)) for arm in TEST_ARMS},
        nonoverlap_checks=checks,comparisons=comparisons,results=results,sufficient_sample=enough,production_promoted=False,
        files={str(p.relative_to(root)):digest(p) for p in root.rglob('*') if p.is_file() and p.name not in ['run.lock','progress.json','report.json']})
    atomic_json(root/'report.json',report);atomic_json(root/'progress.json',dict(status=report['status'],completed=16,total=16,failed=0))
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--phase',choices=['prepare','analyze','run'],default='run')
    parser.add_argument('--output-dir',type=Path,default=OUTPUT);args=parser.parse_args()
    from scripts.research.oracle_path_confirmation import exclusive_run
    try:
        if args.phase in ('prepare','run'): prepare(args.output_dir)
        if args.phase in ('analyze','run'):
            with exclusive_run(args.output_dir): analyze(args.output_dir)
    except Exception as exc:
        if (args.output_dir/'protocol.json').exists() and not (args.output_dir/'report.json').exists():
            atomic_json(args.output_dir/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)))
        raise


if __name__=='__main__': main()
