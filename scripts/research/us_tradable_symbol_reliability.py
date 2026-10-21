"""Full current tradable universe, frozen symbol/side trust gate, offline only.

Primary population has NO Oracle restriction. The original TOP10 is a separate
secondary intersection using memberships learned from the full universe.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import re

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

from modelFactory.oracle.build_labels import nyse_sessions
from scripts.research import us_top10_symbol_reliability as gate
from scripts.research.us_top10_liquidity_gap_audit import barrier_path, valid_bar
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes

LOG = logging.getLogger(__name__)
UNIVERSE=Path('config/univers_batch/univers_filtred_tradable.txt')
PRICE_MANIFEST=Path('artifacts/research/us_news_gpt_bullish_portfolio/20261015-v1/ready.json')
TOP10=Path('artifacts/research/us_top10_symbol_reliability/20261019-v2/evaluations.parquet')
TP,SL,HOLD=.20,.07,20


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def symbols_from_file(path):
    return sorted(set(s.upper() for s in re.split(r'[,;\s]+',Path(path).read_text(encoding='utf-8-sig')) if s))


def vector_paths(bars, positions, side):
    """Same gap/limit/collision contract as scalar barrier_path; all windows full."""
    if side not in ('LONG','SHORT'):raise ValueError('Explicit side required')
    positions=np.asarray(positions,dtype=int)
    if (positions<0).any() or (positions+HOLD>=len(bars)).any():raise ValueError('Incomplete forward window')
    arrays={k:sliding_window_view(bars[k].to_numpy(float),HOLD)[positions+1]
            for k in ('open','high','low','close')}
    entry=arrays['open'][:,0];long=side=='LONG'
    stop=entry*(1-SL if long else 1+SL);take=entry*(1+TP if long else 1-TP)
    stop_cross=arrays['low']<=stop[:,None] if long else arrays['high']>=stop[:,None]
    tp_cross=arrays['high']>=take[:,None] if long else arrays['low']<=take[:,None]
    n=len(positions);code=np.zeros(n,dtype=np.int8)
    exit_price=arrays['close'][:,-1].copy();exit_session=np.full(n,HOLD,dtype=np.int16)
    ambiguity=np.zeros(n,dtype=bool);gap_stop=np.zeros(n,dtype=bool)
    for k in range(HOLD):
        active=code==0
        os=active & (arrays['open'][:,k]<=stop if long else arrays['open'][:,k]>=stop) if k else np.zeros(n,dtype=bool)
        ot=active & ~os & (arrays['open'][:,k]>=take if long else arrays['open'][:,k]<=take) if k else np.zeros(n,dtype=bool)
        st=active & ~os & ~ot & stop_cross[:,k]
        tp=active & ~os & ~ot & ~st & tp_cross[:,k]
        code[os|st]=2;code[ot|tp]=1
        exit_price[os]=arrays['open'][os,k];exit_price[st]=stop[st];exit_price[ot|tp]=take[ot|tp]
        exit_session[os|ot|st|tp]=k+1
        ambiguity[st & tp_cross[:,k]]=True;gap_stop[os]=True
    sign=1 if long else -1
    return dict(outcome=np.array(['TIMEOUT','TP','SL'])[code],tp_first=code==1,sl_first=code==2,
        ambiguity=ambiguity,gap_stop=gap_stop,entry_price=entry,exit_price=exit_price,
        exit_session=exit_session,path_return=sign*(exit_price/entry-1),
        terminal_direction_right=sign*(arrays['close'][:,-1]/entry-1)>0)


def qualify_symbol(raw,days,decision_positions,events,symbol):
    b=raw.set_index('date').reindex(days).copy()
    good=valid_bar(b).to_numpy(bool)
    positive_volume=np.isfinite(b.volume)&b.volume.gt(0)
    past=(pd.Series(good & positive_volume.to_numpy(),index=days).rolling(21,min_periods=21).sum().eq(21))
    ids=b.instrument_id.astype(float)
    past &= ids.rolling(21,min_periods=21).min().eq(ids.rolling(21,min_periods=21).max())
    valid_window=sliding_window_view(good,HOLD).all(axis=1)
    id_windows=sliding_window_view(ids.to_numpy(),HOLD)
    same_identity=(id_windows==id_windows[:,[0]]).all(axis=1)
    decisions=days[decision_positions]
    reasons=np.full(len(decision_positions),'',dtype=object)
    # 2024/2025 tails are observed into the following year; 2026 ends Sep30.
    terminals={2024:pd.Timestamp('2025-02-03'),2025:pd.Timestamp('2026-02-02'),2026:pd.Timestamp('2026-09-30')}
    complete=decision_positions+HOLD<len(days)
    for y,terminal in terminals.items():
        for_year=decisions.year==y
        end=days[np.minimum(decision_positions+HOLD,len(days)-1)]
        complete &= ~for_year | (end<=terminal)
    reasons[~complete]='NOT_MATURE_AT_OBSERVATION_END'
    causal=past.iloc[decision_positions].to_numpy()
    reasons[complete & ~causal]='MISSING_OR_INVALID_21_SESSION_CAUSAL_HISTORY'
    candidates=np.flatnonzero(complete & causal)
    j=decision_positions[candidates]
    future_ok=valid_window[j+1]&same_identity[j+1]
    future_ok &= ids.iloc[j].to_numpy()==ids.iloc[j+1].to_numpy()
    reasons[candidates[~future_ok]]='UNQUALIFIED_FUTURE_PATH_OR_IDENTITY'
    for event in events:
        if symbol not in {event.get('source'),event.get('target'),event.get('trading_symbol')}:continue
        event_day=pd.Timestamp(event['day'])
        affected=(decisions[candidates]-pd.Timedelta(days=40)<=event_day)&(days[j+HOLD]>=event_day)
        mask=candidates[affected & (reasons[candidates]=='')]
        reasons[mask]='KNOWN_IDENTITY_EVENT_IN_FEATURE_OR_PATH'
    keep=decision_positions[reasons=='']
    return b,keep,reasons


def independent_fast(frame):
    """Exactly the same earliest-first full-window thinning as the small study."""
    selected=[]
    ordered=frame.sort_values(['symbol','side','date'])
    for _,g in ordered.groupby(['symbol','side'],observed=True,sort=False):
        starts=g.entry_date.to_numpy('datetime64[ns]');ends=g.last_path_date.to_numpy('datetime64[ns]')
        index=g.index.to_numpy();i=0
        while i<len(g):
            selected.append(index[i]);i=int(np.searchsorted(starts,ends[i],side='right'))
    return frame.loc[selected].sort_values(['date','symbol','side']).copy()


def states_fast(frame,cutoff,days):
    h=gate.matured_history(frame,cutoff,days)
    independent=independent_fast(h)
    baseline={side:dict(tp=float(g.groupby('date').tp_first.mean().mean()),
                        net=float(g.groupby('date').net_outcome.mean().mean()))
              for side,g in h.groupby('side',observed=True)}
    rows=[]
    for (symbol,side),g in independent.groupby(['symbol','side'],observed=True):
        g=g.sort_values('date');n=len(g);wins=int(g.tp_first.sum());base=baseline[side]
        lower=gate.wilson_lower(wins,n);mean=float(g.net_outcome.mean())
        half=n//2;a,b=g.iloc[:half],g.iloc[half:]
        enough=n>=gate.MIN_EPISODES;positive=mean>max(0.,base['net']);strong=lower>base['tp']
        stable=enough and all(float(x.net_outcome.mean())>0 and float(x.tp_first.mean())>base['tp'] for x in (a,b))
        passed=bool(enough and positive and strong and stable);failures=[]
        if not enough:failures.append('INSUFFICIENT_NONOVERLAPPING_HISTORY')
        if enough and not positive:failures.append('NET_NOT_POSITIVE_AND_ABOVE_GLOBAL')
        if enough and not strong:failures.append('WILSON_LOWER_NOT_ABOVE_GLOBAL_TP')
        if enough and not stable:failures.append('NOT_STABLE_IN_BOTH_HALVES')
        rows.append(dict(rebalance_date=pd.Timestamp(cutoff),symbol=symbol,side=side,episodes=n,tp_count=wins,
            tp_rate=float(g.tp_first.mean()),wilson90_lower=lower,mean_net_outcome=mean,
            global_tp_rate=base['tp'],global_mean_net=base['net'],
            first_half_tp=float(a.tp_first.mean()) if len(a) else None,
            second_half_tp=float(b.tp_first.mean()) if len(b) else None,
            max_known_maturity=g.last_path_date.max(),passed=passed,
            qualification='PASS_EXPLORATORY' if passed else 'INSUFFICIENT_HISTORY' if not enough else 'NOT_QUALIFIED',
            reasons=';'.join(failures)))
    return pd.DataFrame(rows),h


def prepare(output):
    output.mkdir(parents=True,exist_ok=False)
    old=read(PRICE_MANIFEST);price=Path(old['prices'])
    expected=next(h for n,h in old['sources'].items() if Path(n)==price)
    verify_hashes(Path('.'),{str(price):expected})
    prior=read(TOP10.parent/'report.json');verify_hashes(TOP10.parent,prior['files'])
    symbols=symbols_from_file(UNIVERSE)
    paths=[Path(__file__),Path('tests/test_us_tradable_symbol_reliability.py'),UNIVERSE,PRICE_MANIFEST,price,TOP10,
        Path(gate.__file__),Path('scripts/research/us_top10_liquidity_gap_audit.py')]
    protocol=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),universe_path=str(UNIVERSE),
        symbols=symbols,universe_count=len(symbols),prices=str(price),events=old['events'],
        source_hashes={str(p):digest(p) for p in paths},primary_scope='ALL_CURRENT_TRADABLE_SYMBOLS_EVERY_NYSE_SESSION_NO_ORACLE_FILTER',
        secondary_scope='Original archived TOP10, monthly memberships learned on ALL tradable symbols',
        initial_history_year=2024,test_years=[2025,2026],tp=TP,sl=SL,holding_sessions=HOLD,
        entry='next session open, window20 includes entry, close20 expiry, no trailing',
        quality='21 consecutive prior bars including J: valid unfilled EODHD split OHLC, positive volume, stable identity; complete valid future20',
        observation_end_2026='2026-09-30',lookback_sessions=504,minimum_nonoverlap_episodes=gate.MIN_EPISODES,
        gate='Unchanged Wilson90 lower > past global same-side TP; mean net > max(0,global net); positive net and above-global TP in both chronological halves',
        gate_version_sha256=digest(Path(gate.__file__)),both_sides_pass='SELECT_SIDE abstains',
        historical_selection='Monthly first NYSE session; full maturity strictly BEFORE cutoff; earliest-first nonoverlap training windows',
        proportional_cost_per_leg=gate.COST_PER_LEG,borrow_annual=gate.BORROW_ANNUAL,
        threshold_search=False,new_model_fit=False,sql=False,provider=False,llm=False,orders=False,
        production_universe_change=False,portfolio_backtest=False,
        caveats=['Current tradable universe, not reconstructed historical PIT tradability or all historic delisted stocks.',
            'Previously explored years; temporal validation is not an untouched independent holdout.',
            'More symbols means more selection opportunities: Wilson gate not multiplicity-corrected; no automatic promotion.',
            'Hypothetical repeated overlapping entries, not a deployable capital-constrained portfolio.',
            'Retrospectively split-adjusted prices, OHLC collision convention, hypothetical fees/borrow.',
            'Historical same-side affinity, not accuracy of GPT, consensus or a fitted direction model.',
            'No replacement of missing data, and missing coverage never classified as a losing/short signal.'])
    atomic_json(output/'protocol.json',protocol)
    (output/'parts').mkdir()
    return protocol


def build(output):
    p=read(output/'protocol.json');verify_hashes(Path('.'),p['source_hashes'])
    if (output/'paths-manifest.json').exists():raise ValueError('Immutable completed paths already exist')
    prices=pd.read_parquet(p['prices']);prices=prices[prices.symbol.isin(p['symbols'])].copy()
    prices.date=pd.to_datetime(prices.date)
    if prices.duplicated(['symbol','date']).any():raise ValueError('Duplicate price key')
    grouped={str(s):g for s,g in prices.groupby('symbol',sort=False)}
    present=set(grouped);days=nyse_sessions('2023-01-01','2026-10-09')
    decisions=days[(days>='2024-01-01')&(days<='2026-09-30')];positions=days.get_indexer(decisions)
    coverage=[]
    for i,symbol in enumerate(p['symbols'],1):
        part=output/'parts'/f'{i:04}.parquet';meta=part.with_suffix('.json')
        if meta.exists():
            saved=read(meta);verify_hashes(output,{saved['path']:saved['sha256']});coverage.extend(saved['coverage']);continue
        if symbol not in present:
            records=[dict(symbol=symbol,year=y,requested=int((decisions.year==y).sum()),qualified=0,
                          reasons={'NO_ARCHIVED_PRICE_SYMBOL':int((decisions.year==y).sum())}) for y in (2024,2025,2026)]
            frames=[]
        else:
            raw=grouped[symbol]
            bars,keep,reasons=qualify_symbol(raw,days,positions,p['events'],symbol)
            records=[dict(symbol=symbol,year=y,requested=int((decisions.year==y).sum()),
                qualified=int(((decisions.year==y)&(reasons=='')).sum()),
                reasons=dict(Counter(reasons[(decisions.year==y)&(reasons!='')]))) for y in (2024,2025,2026)]
            frames=[]
            for side in ('LONG','SHORT'):
                paths=vector_paths(bars,keep,side)
                frames.append(pd.DataFrame(dict(date=days[keep],symbol=symbol,side=side,year=days[keep].year,
                    entry_date=days[keep+1],last_path_date=days[keep+HOLD],**paths)))
        frame=pd.concat(frames,ignore_index=True) if frames else pd.DataFrame()
        frame.to_parquet(part,index=False)
        saved=dict(symbol=symbol,path=str(part.relative_to(output)),sha256=digest(part),coverage=records)
        atomic_json(meta,saved);coverage.extend(records)
        if i%100==0 or i==len(p['symbols']):
            atomic_json(output/'progress.json',dict(status='RUNNING',phase='BUILD_FULL_UNIVERSE_PATHS',completed=i,total=len(p['symbols']),symbol=symbol))
            LOG.info('Paths %d/%d symbols',i,len(p['symbols']))
    pd.DataFrame(coverage).to_csv(output/'price-coverage.csv',index=False)
    manifest=dict(symbols=len(p['symbols']),source_hashes=p['source_hashes'],
        parts={str(path.relative_to(output)):digest(path) for path in sorted((output/'parts').glob('*.parquet'))},
        coverage=coverage,coverage_csv_sha256=digest(output/'price-coverage.csv'))
    verify_hashes(Path('.'),p['source_hashes']);atomic_json(output/'paths-manifest.json',manifest)
    LOG.info('Built all %d universe symbols',len(p['symbols']))


def independent_summary(frame):
    rows=[]
    for year,g in frame.groupby(frame.date.dt.year):
        for arm in gate.ARMS:
            subset=independent_fast(gate.chosen(g,arm))
            rows.append(dict(year=int(year),arm=arm,n=len(subset),symbols=int(subset.symbol.nunique()),
                tp_count=int(subset.tp_first.sum()),tp_rate=float(subset.tp_first.mean()) if len(subset) else None,
                profitable_rate=float(subset.net_outcome.gt(0).mean()) if len(subset) else None,
                mean_net_outcome=float(subset.net_outcome.mean()) if len(subset) else None,
                largest_symbol_counts={str(k):int(v) for k,v in subset.symbol.value_counts().head(10).items()}))
    return rows


def summary_bundle(frame,days):
    summary=gate.summarize(frame,days);independent=independent_summary(frame)
    semester=[]
    for (year,half),g in frame.groupby([frame.date.dt.year,(frame.date.dt.month>6).astype(int)+1]):
        for arm in gate.ARMS:
            sub=gate.chosen(g,arm)
            semester.append(dict(year=int(year),half=int(half),arm=arm,n=len(sub),symbols=int(sub.symbol.nunique()),
                tp_rate=float(sub.tp_first.mean()) if len(sub) else None,
                mean_net_outcome=float(sub.net_outcome.mean()) if len(sub) else None))
    return dict(summary=summary,nonoverlapping=independent,semesters=semester)


def run(output):
    p=read(output/'protocol.json');verify_hashes(Path('.'),p['source_hashes'])
    if (output/'report.json').exists():raise ValueError('Immutable completed report exists')
    manifest=read(output/'paths-manifest.json');verify_hashes(output,manifest['parts'])
    f=pd.concat([pd.read_parquet(output/n) for n in manifest['parts']],ignore_index=True)
    f['symbol']=f.symbol.astype('category');f['side']=f.side.astype('category')
    if f.duplicated(['date','symbol','side']).any():raise ValueError('Duplicate observation key')
    f=gate.attach_costs(f)
    days=nyse_sessions('2023-01-01','2026-10-09')
    tests=f[f.date.dt.year.isin(p['test_years'])].copy()
    schedule=days[(days>='2025-01-01')&(days<='2026-09-01')].to_series().groupby(lambda d:d.to_period('M')).min()
    states=[];selected=[];audit=[]
    for i,cutoff in enumerate(schedule,1):
        membership,h=states_fast(f,cutoff,days)
        if not membership.max_known_maturity.lt(cutoff).all():raise AssertionError('Immature history leakage')
        states.append(membership)
        month=tests[tests.date.dt.to_period('M').eq(cutoff.to_period('M'))]
        result=gate.apply_states(month,membership);result['rebalance_date']=cutoff;selected.append(result)
        row=dict(date=cutoff,history_rows=len(h),max_known_maturity=h.last_path_date.max(),
            qualified_states=int(membership.passed.sum()),qualified_symbols=int(membership.loc[membership.passed,'symbol'].nunique()),
            enough_history_states=int(membership.episodes.ge(gate.MIN_EPISODES).sum()),states_with_history=len(membership))
        audit.append(row);LOG.info('Full universe %s: %d qualified symbols, %d side-states',cutoff.date(),row['qualified_symbols'],row['qualified_states'])
        atomic_json(output/'progress.json',dict(status='RUNNING',phase='MONTHLY_SELECTION',completed=i,total=len(schedule)))
    evaluated=pd.concat(selected,ignore_index=True);membership=pd.concat(states,ignore_index=True)
    evaluated.to_parquet(output/'evaluations.parquet',index=False)
    membership.to_parquet(output/'monthly-memberships.parquet',index=False)
    membership.to_csv(output/'monthly-memberships.csv',index=False)
    evaluated[evaluated.chosen_side].to_parquet(output/'selected-occasions.parquet',index=False)
    LOG.info('Summarizing full universe and non-overlapping controls')
    primary=summary_bundle(evaluated,days)
    top=pd.read_parquet(TOP10,columns=['date','symbol','side','oracle_rank'])
    secondary=top.merge(evaluated,on=['date','symbol','side'],how='inner',validate='one_to_one')
    secondary.to_parquet(output/'secondary-original-top10.parquet',index=False)
    subset=summary_bundle(secondary,days)
    # Overlap with old TOP10 training membership, not an outcome-based ticker list.
    per_symbol=evaluated[evaluated.chosen_side].groupby([evaluated.date.dt.year,'symbol','side'],observed=True).agg(
        occasions=('tp_first','size'),tp_rate=('tp_first','mean'),mean_net=('net_outcome','mean')).reset_index()
    per_symbol.to_csv(output/'selected-symbol-results.csv',index=False)
    paths=['evaluations.parquet','monthly-memberships.parquet','monthly-memberships.csv','selected-occasions.parquet',
           'secondary-original-top10.parquet','selected-symbol-results.csv','price-coverage.csv']
    for name,values in [('primary-summary',primary),('secondary-top10-summary',subset)]:
        atomic_json(output/f'{name}.json',values);paths.append(f'{name}.json')
    coverage=[]
    for y in (2024,2025,2026):
        records=[r for r in manifest['coverage'] if r['year']==y];why=Counter()
        for r in records:why.update(r['reasons'])
        coverage.append(dict(year=y,universe_symbols=len(p['symbols']),requested=sum(r['requested'] for r in records),
            qualified=sum(r['qualified'] for r in records),symbols_with_qualified=sum(r['qualified']>0 for r in records),
            missing_symbols=[r['symbol'] for r in records if r['qualified']==0],exclusions=dict(why)))
    report=dict(status='COMPLETED_EXPLORATORY_NO_PROMOTION',protocol_sha256=digest(output/'protocol.json'),
        scope=p['primary_scope'],universe_count=len(p['symbols']),coverage=coverage,
        primary=primary,secondary_top10=subset,secondary_available_rows=len(secondary)//2,
        secondary_original_requested_rows=len(top)//2,
        monthly_audit=audit,selection_qualification='Same historical gate as prior TOP10 test, no thresholds retuned',
        selected_unique_symbols=int(evaluated.loc[evaluated.chosen_side,'symbol'].nunique()),
        files={n:digest(output/n) for n in paths},
        interpretation='Full tradable-universe historical side affinity; not a capital-constrained economic portfolio or GPT/consensus accuracy test.')
    verify_hashes(Path('.'),p['source_hashes']);verify_hashes(output,manifest['parts'])
    atomic_json(output/'report.json',report);atomic_json(output/'progress.json',dict(status=report['status'],phase='DONE'))
    LOG.info('Completed entire universe; %d selected distinct symbols',report['selected_unique_symbols'])
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--phase',choices=['prepare','build','run'],required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    {'prepare':prepare,'build':build,'run':run}[args.phase](args.output)


if __name__=='__main__':main()
