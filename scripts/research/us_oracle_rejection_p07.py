"""P07 bounded frequency/coverage screen; absolutely no returns or PnL.

Only past10 regular raw sessions and causal entry observations in J1/J2.
Stop before an economic replay if the predeclared frequency gate fails.
No SQL, provider, LLM, training, broker, orders or production changes.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research import us_oracle_compression_p01 as parent
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest,verify_hashes

READ=parent.READ
REFERENCE=parent.OUTPUT
OUTPUT=Path('artifacts/research/us_oracle_rejection_p07/20261022-v1')
RULE=dict(lookback_sessions=10,close_location_min=.75,entry_valid_sessions=2,
          confirmation_bars=1,min_nonoverlap_signals_per_year=30,
          min_symbols_per_year=10,min_signal_months_per_year=6,
          nonoverlap_until='ORACLE_J40_OPEN')
KNOWN_ENTRY_STATES={'SIGNAL','LOW_J_INVALIDATED','GAP_BELOW_LOW_J_BEFORE_FILL',
                    'FIRST_CONFIRMATION_LAST_BAR_NO_FILL','NO_BREAKOUT_TWO_SESSIONS'}


def daily_features(frames):
    if len(frames)!=10:raise ValueError('TEN_PRIOR_COMPLETE_SESSIONS_REQUIRED')
    daily=[dict(high=float(f.high.max()),low=float(f.low.min()),close=float(f.close.iloc[-1])) for f in frames]
    if not all(np.isfinite(list(d.values())).all() and 0<d['low']<=d['close']<=d['high'] for d in daily):
        raise ValueError('INVALID_DAILY_OBSERVATIONS')
    j=daily[-1];previous=daily[:-1];span=j['high']-j['low']
    minimum=min(d['low'] for d in previous);max_range=max(d['high']-d['low'] for d in previous)
    location=(j['close']-j['low'])/span if span>0 else None
    new_low=j['low']<minimum;wide=span>max_range;upper=location is not None and location>=.75
    return dict(high_j=j['high'],low_j=j['low'],close_j=j['close'],range_j=span,
        min_prior9_low=minimum,max_prior9_range=max_range,close_location=location,
        new_low=bool(new_low),widest_range=bool(wide),upper_quarter=bool(upper),
        pattern=bool(span>0 and new_low and wide and upper))


def scan_entry(symbol,oracle_date,high_j,low_j,groups,schedule):
    """First confirmed close >Jhigh, stop waiting if Jlow breaks beforehand.

    A completed bar breaking both boundaries is invalidated conservatively.
    The next open may cancel a pending entry if it gaps below Jlow; its future
    low/high NEVER cancel an entry that was valid at that open.
    """
    days=pd.DatetimeIndex(schedule.date);i=days.get_loc(oracle_date)
    for offset in (1,2):
        day=days[i+offset]
        if day>parent.END:return dict(status='ENTRY_SCREEN_CENSORED')
        frame=groups.get((symbol,day))
        if frame is None:return dict(status='MISSING_ENTRY_SESSION',missing_date=day)
        times=frame.bar_timestamp
        if not (frame.bar_end_timestamp.iloc[:-1].to_numpy()==times.iloc[1:].to_numpy()).all():
            raise ValueError('NONCONTIGUOUS_ENTRY_SESSION')
        for k,row in enumerate(frame.itertuples()):
            if row.low<low_j:return dict(status='LOW_J_INVALIDATED',decision_time=row.bar_end_timestamp)
            if row.close<=high_j:continue
            if k+1==len(frame):return dict(status='FIRST_CONFIRMATION_LAST_BAR_NO_FILL',decision_time=row.bar_end_timestamp)
            next_bar=frame.iloc[k+1]
            if next_bar.open<low_j:
                return dict(status='GAP_BELOW_LOW_J_BEFORE_FILL',decision_time=next_bar.bar_timestamp)
            return dict(status='SIGNAL',timestamp=next_bar.bar_timestamp,date=day,delay=offset,
                price=float(next_bar.open),signal_bar=row.bar_timestamp,signal_close=float(row.close),
                decision_time=row.bar_end_timestamp)
    return dict(status='NO_BREAKOUT_TWO_SESSIONS')


def inspect_candidate(row,groups,schedule,actions):
    days=pd.DatetimeIndex(schedule.date);sch=schedule.set_index('date');i=days.get_loc(row.oracle_date)
    base=dict(pair_id=int(row.pair_id),symbol=row.symbol,rank=int(row.rank),oracle_date=row.oracle_date,
              year=row.oracle_date.year,feature_status='MISSING_TEN_SESSION_LOOKBACK',
              pattern=None,entry_status='NOT_SCREENED',entry_evaluable=False,
              break_control_signal=None,P07_signal=None,
              entry_time=sch.loc[days[i+1],'market_open'],label_available=sch.loc[days[i+40],'market_open'])
    window=days[max(0,i-9):i+1]
    missing=[d for d in window if (row.symbol,d) not in groups]
    if len(window)!=10 or missing:
        return dict(base,missing_lookback_dates='|'.join(str(d.date()) for d in missing))
    if not actions.empty and ((actions.symbol==row.symbol)&actions.ex_date.between(window[0],row.oracle_date)).any():
        return dict(base,feature_status='KNOWN_LOOKBACK_CORPORATE_ACTION')
    try:features=daily_features([groups[row.symbol,d] for d in window])
    except ValueError as exc:return dict(base,feature_status=str(exc))
    entry=scan_entry(row.symbol,row.oracle_date,features['high_j'],features['low_j'],groups,schedule)
    known=entry['status'] in KNOWN_ENTRY_STATES
    p07_signal=features['pattern'] and entry['status']=='SIGNAL'
    record=dict(base,feature_status='QUALIFIED',**features,entry_status=entry['status'],entry_evaluable=known,
        break_control_signal=entry['status']=='SIGNAL',P07_signal=bool(p07_signal) if known else None,
        feature_source_start=window[0],feature_available_at=sch.loc[row.oracle_date,'market_close'],
        entry_time=sch.loc[days[i+1],'market_open'],label_available=sch.loc[days[i+40],'market_open'])
    record.update({f'entry_{key}':value for key,value in entry.items() if key!='status'})
    return record


def prepare(root):
    root=Path(root)
    if root.exists():raise ValueError('Fresh immutable output required')
    verify_hashes(REFERENCE,READ(REFERENCE/'report.json')['files'])
    audit=READ(REFERENCE/'final-audit.json')
    if audit['primary_report_sha256']!=digest(REFERENCE/'report.json'):raise ValueError('Verified reference required')
    verify_hashes(parent.PARENT,READ(parent.PARENT/'report.json')['files'])
    verify_hashes(parent.PARENT,READ(parent.PARENT/'snapshot.json')['files'])
    sources=dict(READ(REFERENCE/'protocol.json')['sources'])
    paths=[Path(__file__),Path('scripts/research/us_oracle_rejection_p07_audit.py'),
        Path('tests/test_us_oracle_rejection_p07.py'),Path('doc/ml/oracle_rejection_p07_20261022.md'),
        REFERENCE/'report.json',REFERENCE/'final-audit.json']
    sources.update({str(p):digest(p) for p in paths})
    root.mkdir(parents=True)
    atomic_json(root/'protocol.json',dict(created_at_utc=datetime.now(timezone.utc).isoformat(),sources=sources,rule=RULE,
        scope='FREQUENCY_AND_COVERAGE_ONLY before any return/path/PnL. Original213researchcampaigns, no universe expansion/download.',
        feature='Ten complete regularrawsessions endingOracleJ. L_J<min prior9L, '
            'rangeJ>max prior9ranges, (C_J-L_J)/rangeJ>=.75 and rangeJ>0. '
            'Lastregular5mclose, not auctionofficialclose. Zero range=known no pattern, not missing.',
        entry='J1/J2 only, FIRST complete5mclose>frozenJhigh, nextcontiguoussame-sessionopen. '
            'Any preentrybar low<Jlow invalidates first, even if samebar recovers. '
            'If next actualopen<Jlow cancel before fill. NEVER inspect its futurehigh/low for cancellation. '
            'Lastbar firstconfirmation cannotfill or retry tomorrow. One attempt, no limit-touch fill/reentry.',
        control='Same highJbreak and same Jlowinvalidation/J1J2window WITHOUT pattern filter. '
            'No model, RSI, volume, retest, partial or trailing change. Signal counts not profits.',
        coverage='Local sealed raw SIP regular unfilled sessions, NYSEcalendar including early closes. '
            'Missinglookback means UNKNOWN, not false pattern. Feature counts reported separately from entrycoverage. '
            'Entry scan stops causally once filled/invalidated; missinglaterJ2 not required after knownJ1decision. '
            'No futureH20path or maturity selection at this stage; counts upper bound before economic price qualification.',
        gate='Per Oracleyear2025/2026, at least30nonoverlap P07signals,10symbols,6signalmonths. '
            'Conservative per-symbolOracleJ40blocks ALL evaluable opportunities, including patternfalse. '
            'No after-outcome relaxation. Fail means NO ECONOMIC BACKTEST, not proven inefficacy.',
        possible_economic_followup='Only if gatepasses: qualify prices and freeze new economic protocol before PnL. '
            'Same annual4000USD/1x/HALF/SL7/TR15/noTP/noadd/nativeB4DD15,20holding sessions thenOPEN21, '
            'fee8/25bps, Winner plus same-window break control, no trailing from published bot. '
            'This script cannot launch economic replay.',
        limitations=READ(REFERENCE/'protocol.json')['limitations']+[
            'Original213campaigns already selected by older signals/future-complete survivor research cohort, not all dailyTOP10.',
            'No new futureH20selection but inherited survivor bias remains; original corporate-action table empty/incomplete.',
            'No2024screen on absent frozen archive, known2025/2026notpristineholdout; no SHORT inference or full live parity.'],
        performance_calculated=False,economic_backtest_launched=False,training=False,sql_writes=False,
        provider_calls=False,broker_calls=False,production_promoted=False))
    atomic_json(root/'progress.json',dict(status='PREPARED_SCREEN_ONLY',completed=0,total=213))


def screen(root):
    root=Path(root)
    if (root/'report.json').exists():raise ValueError('Already sealed')
    protocol=READ(root/'protocol.json');verify_hashes(Path('.'),protocol['sources'])
    verify_hashes(parent.PARENT,READ(parent.PARENT/'report.json')['files'])
    groups,quality,schedule=parent.load_groups();candidates=pd.read_parquet(parent.PARENT/'campaigns.parquet')
    if len(candidates)!=213 or candidates.pair_id.duplicated().any():raise ValueError('Frozen cohort changed')
    actions=pd.read_parquet(parent.PARENT/'corporate-actions.parquet')
    if not actions.empty:actions['ex_date']=pd.to_datetime(actions.ex_date)
    records=[inspect_candidate(r,groups,schedule,actions) for r in candidates.itertuples()]
    frame=pd.DataFrame(records);frame.to_parquet(root/'coverage-and-signals.parquet',index=False)
    pd.DataFrame(quality).to_parquet(root/'session-quality.parquet',index=False)
    feature=frame[frame.feature_status.eq('QUALIFIED')].copy()
    evaluable=feature[feature.entry_evaluable.eq(True)].copy()
    spaced=parent.history.spaced(evaluable);spaced.to_parquet(root/'nonoverlap.parquet',index=False)
    if 'entry_timestamp' in frame:
        selected=frame[frame.P07_signal.eq(True)].copy()
    else:selected=frame.iloc[:0].copy()
    selected.to_parquet(root/'P07-entry-signals.parquet',index=False)
    counts=[]
    for year in (2025,2026):
        f=feature[feature.year.eq(year)];e=evaluable[evaluable.year.eq(year)];n=spaced[spaced.year.eq(year)]
        s=n[n.P07_signal.eq(True)]
        months=int(s.oracle_date.dt.month.nunique())
        counts.append(dict(year=year,original=int(candidates.year.eq(year).sum()),features_qualified=len(f),
            patterns=int(f.pattern.eq(True).sum()),entry_evaluable=len(e),break_control_signals=int(e.break_control_signal.sum()),
            p07_signals=int(e.P07_signal.eq(True).sum()),nonoverlap_opportunities=len(n),
            nonoverlap_signals=len(s),symbols=int(s.symbol.nunique()),signal_months=months,
            gate_pass=bool(len(s)>=30 and s.symbol.nunique()>=10 and months>=6)))
    enough=all(c['gate_pass'] for c in counts)
    pd.DataFrame(counts).to_csv(root/'frequency-summary.csv',index=False)
    verify_hashes(Path('.'),protocol['sources']);verify_hashes(parent.PARENT,READ(parent.PARENT/'report.json')['files'])
    report=dict(status='P07_FREQUENCY_GATE_PASS_PRICE_QUALIFICATION_REQUIRED' if enough else 'INSUFFICIENT_P07_FREQUENCY_NO_BACKTEST',
        original_campaigns=213,feature_status_counts=dict(Counter(frame.feature_status)),feature_qualified=len(feature),
        feature_patterns=int(feature.pattern.eq(True).sum()),entry_status_counts=dict(Counter(feature.entry_status)),
        p07_signals=len(selected),counts=counts,sufficient_sample=enough,
        performance_calculated=False,economic_backtest_launched=False,production_promoted=False,
        files={str(p.relative_to(root)):digest(p) for p in root.rglob('*') if p.is_file() and p.name not in ['run.lock','progress.json','report.json']})
    atomic_json(root/'report.json',report);atomic_json(root/'progress.json',dict(status=report['status'],completed=213,total=213,failed=0))
    print(report['status']);print(pd.DataFrame(counts).to_string(index=False));return report


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output-dir',type=Path,default=OUTPUT)
    parser.add_argument('--phase',choices=['prepare','screen','run'],default='run');args=parser.parse_args()
    from scripts.research.oracle_path_confirmation import exclusive_run
    try:
        if args.phase in ('prepare','run'):prepare(args.output_dir)
        if args.phase in ('screen','run'):
            with exclusive_run(args.output_dir):screen(args.output_dir)
    except Exception as exc:
        if (args.output_dir/'protocol.json').exists() and not (args.output_dir/'report.json').exists():
            atomic_json(args.output_dir/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)))
        raise


if __name__=='__main__':main()
