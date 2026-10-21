"""Two offline extensions of full-universe symbol trust: TP10/SL10 and TP10 only.

Fresh causal memberships for each target; old TP20/SL7 memberships are a frozen
secondary control. No live/SQL/model/LLM changes. No portfolio PnL calculation.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

from scripts.research import us_tradable_symbol_reliability as base
from scripts.research import us_top10_symbol_reliability as gate
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest,verify_hashes

LOG=logging.getLogger(__name__)
BASE=Path('artifacts/research/us_tradable_symbol_reliability/20261019-v1')
PROFILES={'TP10_SL10':dict(tp=.10,sl=.10),'TP10_NO_SL':dict(tp=.10,sl=None)}
HOLD=20
BOUNDARY_RTOL=1e-12


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def paths(bars,positions,side,*,tp,sl):
    """Same next-open/20-session/limit/gap contract, optional stop explicitly None."""
    if side not in ('LONG','SHORT') or not 0<tp<1 or (sl is not None and not 0<sl<1):
        raise ValueError('Invalid side or positive fractional TP/SL')
    positions=np.asarray(positions,dtype=int)
    if (positions<0).any() or (positions+HOLD>=len(bars)).any():raise ValueError('Incomplete window')
    a={k:sliding_window_view(bars[k].to_numpy(float),HOLD)[positions+1] for k in ('open','high','low','close')}
    entry=a['open'][:,0];long=side=='LONG';take=entry*(1+tp if long else 1-tp)
    n=len(positions);stop=None if sl is None else entry*(1-sl if long else 1+sl)
    # 100 * 1.1 can be 110.00000000000001; exact quoted touches must count.
    tt=BOUNDARY_RTOL*np.abs(take)
    stolerance=None if stop is None else BOUNDARY_RTOL*np.abs(stop)
    hit_tp=a['high']>=(take-tt)[:,None] if long else a['low']<=(take+tt)[:,None]
    hit_sl=np.zeros((n,HOLD),dtype=bool) if sl is None else (a['low']<=(stop+stolerance)[:,None] if long else a['high']>=(stop-stolerance)[:,None])
    code=np.zeros(n,dtype=np.int8);exit_price=a['close'][:,-1].copy();age=np.full(n,HOLD,dtype=np.int16)
    ambiguous=np.zeros(n,dtype=bool);gap_stop=np.zeros(n,dtype=bool);at_open=np.zeros(n,dtype=bool)
    for k in range(HOLD):
        active=code==0
        os=np.zeros(n,dtype=bool) if k==0 or sl is None else active & (a['open'][:,k]<=stop+stolerance if long else a['open'][:,k]>=stop-stolerance)
        ot=np.zeros(n,dtype=bool) if k==0 else active & ~os & (a['open'][:,k]>=take-tt if long else a['open'][:,k]<=take+tt)
        st=active & ~os & ~ot & hit_sl[:,k];target=active & ~os & ~ot & ~st & hit_tp[:,k]
        code[os|st]=2;code[ot|target]=1
        exit_price[os]=a['open'][os,k]
        if stop is not None:exit_price[st]=stop[st]
        exit_price[ot|target]=take[ot|target];age[os|ot|st|target]=k+1
        ambiguous[st & hit_tp[:,k]]=True;gap_stop[os]=True;at_open[os|ot]=True
    sign=1 if long else -1
    adverse=(1-a['low']/entry[:,None]) if long else (a['high']/entry[:,None]-1)
    day=np.arange(HOLD)[None,:]
    prior=day<(age[:,None]-1)
    # Lower/upper descriptive bounds, not a claimed intraday ordering at exit.
    mae_before=np.maximum(0,np.where(prior,adverse,0).max(axis=1))
    through=day<age[:,None]
    mae_through=np.maximum(0,np.where(through,adverse,0).max(axis=1))
    open_adverse=np.maximum(0,-sign*(exit_price/entry-1))
    mae_through[at_open]=np.maximum(mae_before[at_open],open_adverse[at_open])
    return dict(outcome=np.array(['TIMEOUT','TP','SL'])[code],tp_first=code==1,sl_first=code==2,
        ambiguity=ambiguous,gap_stop=gap_stop,entry_price=entry,exit_price=exit_price,exit_session=age,
        path_return=sign*(exit_price/entry-1),terminal_direction_right=sign*(a['close'][:,-1]/entry-1)>0,
        mae_before_exit_bar=mae_before,mae_through_exit_bar=mae_through)


def prepare(root):
    root.mkdir(parents=True,exist_ok=False)
    old=read(BASE/'protocol.json');report=read(BASE/'report.json');manifest=read(BASE/'paths-manifest.json')
    verify_hashes(BASE,report['files']);verify_hashes(BASE,manifest['parts'])
    verify_hashes(Path('.'),old['source_hashes'])
    source_paths=[Path(__file__),Path('tests/test_us_tradable_tp10_variants.py'),Path(base.__file__),Path(gate.__file__),
        BASE/'protocol.json',BASE/'paths-manifest.json',BASE/'report.json',BASE/'evaluations.parquet',
        Path(old['prices']),Path(old['universe_path'])]
    protocol=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),base=str(BASE),
        source_hashes={str(p):digest(p) for p in source_paths},profiles=PROFILES,
        universe_count=old['universe_count'],symbols=old['symbols'],universe_path=old['universe_path'],
        prices=old['prices'],initial_history_year=2024,test_years=[2025,2026],holding_sessions=HOLD,
        entry='J+1 open; 20 sessions INCLUDING entry; close20 if no TP/SL; no trailing',
        tp_only_meaning='NO STOP LOSS; TP10 or close20. No margin/liquidity forced liquidation simulated.',
        primary='All 1790 current tradable symbols, no Oracle restriction; rebuild causal memberships for EACH profile',
        secondary='Original TOP10 intersection of each freshly learned full-universe membership',
        frozen_control='Old TP20/SL7 full-universe memberships, same symbol/date/side; new exits only, no requalification',
        gate='Unchanged minimum8 nonoverlap, 504 sessions, Wilson90 vs past same-side global, positive net and two stable chronological halves',
        label_availability='Entire 20-session window must finish strictly before monthly cutoff, even for early TP/SL exits',
        fees_per_leg=gate.COST_PER_LEG,borrow_annual=gate.BORROW_ANNUAL,threshold_search=False,
        exact_touch_relative_tolerance=BOUNDARY_RTOL,
        sql=False,provider_calls=False,llm=False,new_model_fit=False,orders=False,production_changes=False,
        portfolio_backtest=False,
        reserves=['Current survivor universe and previously explored periods, not untouched holdout.',
            'Inherited price/corporate-action discontinuities including KLAC remain UNQUALIFIED, not repaired or capped.',
            'No stop may lose most entry capital LONG and more than entry notional SHORT; no genuine margin simulation.',
            'MAE includes exit bar unless exit open resolves ordering: descriptive bounds, not exact intraday drawdown.',
            'Independent per-entry percentages, repeated overlapping observations, not compounded annual portfolio returns.',
            'Hypothetical proportional costs and borrow; no historic locate, recalls or complete dividends.',
            'Symbol side affinity gate, not accuracy of GPT/consensus or newly trained directional models.'])
    atomic_json(root/'protocol.json',protocol)
    for profile in PROFILES:(root/profile/'parts').mkdir(parents=True)
    return protocol


def build(root):
    protocol=read(root/'protocol.json');verify_hashes(Path('.'),protocol['source_hashes'])
    if (root/'paths-manifest.json').exists():raise ValueError('Immutable completed paths exist')
    original=read(BASE/'paths-manifest.json');verify_hashes(BASE,original['parts'])
    from modelFactory.oracle.build_labels import nyse_sessions
    days=nyse_sessions('2023-01-01','2026-10-09')
    prices=pd.read_parquet(protocol['prices']);prices.date=pd.to_datetime(prices.date)
    groups={str(s):g for s,g in prices.groupby('symbol',sort=False)}
    for i,symbol in enumerate(protocol['symbols'],1):
        old_name=f'parts/{i:04}.parquet';keys=pd.read_parquet(BASE/old_name,columns=['date','symbol','side','year','entry_date','last_path_date'])
        if not keys.symbol.eq(symbol).all():raise ValueError('Original symbol-part order changed')
        old_positions=days.get_indexer(pd.DatetimeIndex(keys[keys.side.eq('LONG')].date))
        bars=groups[symbol].set_index('date').reindex(days)
        for name,profile in protocol['profiles'].items():
            part=root/name/'parts'/f'{i:04}.parquet';meta=part.with_suffix('.json')
            if meta.exists():
                saved=read(meta);verify_hashes(root,{saved['path']:saved['sha256']});continue
            frames=[]
            for side in ('LONG','SHORT'):
                outcomes=paths(bars,old_positions,side,**profile)
                frames.append(pd.DataFrame(dict(date=days[old_positions],symbol=symbol,side=side,year=days[old_positions].year,
                    entry_date=days[old_positions+1],last_path_date=days[old_positions+HOLD],**outcomes)))
            frame=pd.concat(frames,ignore_index=True)
            # Keys fixed from old quality-qualified population; never replace missing/unfavourable outcomes.
            pd.testing.assert_frame_equal(keys.reset_index(drop=True),frame[keys.columns].reset_index(drop=True),check_dtype=False)
            frame.to_parquet(part,index=False)
            atomic_json(meta,dict(symbol=symbol,path=str(part.relative_to(root)),sha256=digest(part)))
        if i%100==0 or i==len(protocol['symbols']):
            LOG.info('Both TP10 profiles %d/%d symbols',i,len(protocol['symbols']))
            atomic_json(root/'progress.json',dict(status='RUNNING',phase='BUILD_BOTH_PROFILES',completed=i,total=len(protocol['symbols'])))
    manifest={name:{str(p.relative_to(root)):digest(p) for p in sorted((root/name/'parts').glob('*.parquet'))}
              for name in protocol['profiles']}
    verify_hashes(Path('.'),protocol['source_hashes']);atomic_json(root/'paths-manifest.json',manifest)


def risk_summary(frame):
    rows=[]
    for year,g in frame.groupby(frame.date.dt.year):
        for arm in gate.ARMS:
            sub=gate.chosen(g,arm)
            positive=sub.net_outcome.gt(0)
            rows.append(dict(year=int(year),arm=arm,n=len(sub),
                profitable_rate=float(positive.mean()) if len(sub) else None,
                mean_winner=float(sub.loc[positive,'net_outcome'].mean()) if positive.any() else None,
                mean_loser=float(sub.loc[~positive,'net_outcome'].mean()) if (~positive).any() else None,
                worst_net_outcome=float(sub.net_outcome.min()) if len(sub) else None,
                adverse_through_exit_p95=float(sub.mae_through_exit_bar.quantile(.95)) if len(sub) else None,
                adverse_over10_lower_rate=float(sub.mae_before_exit_bar.gt(.10).mean()) if len(sub) else None,
                adverse_over10_upper_rate=float(sub.mae_through_exit_bar.gt(.10).mean()) if len(sub) else None,
                severe_price_outcomes_n=int(sub.path_return.lt(-.75).sum()),
                warning='Exit-bar OHLC adverse bounds, not portfolio DD; extreme prices not independently qualified.'))
    return rows


def run_case(root,name):
    p=read(root/'protocol.json');verify_hashes(Path('.'),p['source_hashes'])
    folder=root/name
    if (folder/'report.json').exists():
        report=read(folder/'report.json');verify_hashes(folder,report['files']);return report
    manifest=read(root/'paths-manifest.json')[name];verify_hashes(root,manifest)
    f=pd.concat([pd.read_parquet(root/n) for n in manifest],ignore_index=True)
    f['symbol']=f.symbol.astype('category');f['side']=f.side.astype('category');f=gate.attach_costs(f)
    if f.duplicated(['date','symbol','side']).any():raise ValueError('Duplicate observation key')
    from modelFactory.oracle.build_labels import nyse_sessions
    days=nyse_sessions('2023-01-01','2026-10-09')
    tests=f[f.date.dt.year.isin(p['test_years'])].copy()
    schedule=days[(days>='2025-01-01')&(days<='2026-09-01')].to_series().groupby(lambda d:d.to_period('M')).min()
    states=[];evaluations=[];audit=[]
    for i,cutoff in enumerate(schedule,1):
        membership,h=base.states_fast(f,cutoff,days)
        if not membership.max_known_maturity.lt(cutoff).all():raise AssertionError('Future label leakage')
        states.append(membership);month=tests[tests.date.dt.to_period('M').eq(cutoff.to_period('M'))]
        current=gate.apply_states(month,membership);current['rebalance_date']=cutoff;evaluations.append(current)
        audit.append(dict(date=cutoff,history_rows=len(h),max_known_maturity=h.last_path_date.max(),
            qualified_states=int(membership.passed.sum()),qualified_symbols=int(membership.loc[membership.passed,'symbol'].nunique())))
        LOG.info('%s %s: %d qualified symbols',name,cutoff.date(),audit[-1]['qualified_symbols'])
        atomic_json(root/'progress.json',dict(status='RUNNING',phase='MONTHLY_SELECTION',profile=name,completed=i,total=len(schedule)))
    evaluated=pd.concat(evaluations,ignore_index=True);membership=pd.concat(states,ignore_index=True)
    evaluated.to_parquet(folder/'evaluations.parquet',index=False)
    membership.to_csv(folder/'monthly-memberships.csv',index=False)
    evaluated[evaluated.chosen_side].to_parquet(folder/'selected-occasions.parquet',index=False)
    primary=base.summary_bundle(evaluated,days)
    top=pd.read_parquet(base.TOP10,columns=['date','symbol','side','oracle_rank'])
    secondary=top.merge(evaluated,on=['date','symbol','side'],validate='one_to_one')
    secondary.to_parquet(folder/'secondary-original-top10.parquet',index=False)
    secondary_report=base.summary_bundle(secondary,days)
    # Old membership on exactly the same pairs: isolates exits versus reselection.
    old=pd.read_parquet(BASE/'evaluations.parquet',columns=['date','symbol','side','symbol_pass','opposite_pass','chosen_side','rebalance_date'])
    frozen=tests.merge(old,on=['date','symbol','side'],how='inner',validate='one_to_one')
    if len(frozen)!=len(tests):raise ValueError('Frozen comparator missing original pairs')
    frozen_report=base.summary_bundle(frozen,days)
    reports=dict(primary=primary,secondary_top10=secondary_report,frozen_old_membership=frozen_report)
    files=['evaluations.parquet','monthly-memberships.csv','selected-occasions.parquet','secondary-original-top10.parquet']
    for key,value in reports.items():atomic_json(folder/f'{key}.json',value);files.append(f'{key}.json')
    risks=risk_summary(evaluated)
    severe=evaluated[evaluated.path_return.lt(-.75)]
    severe[['date','symbol','side','entry_price','exit_price','path_return','chosen_side']].to_csv(folder/'price-reserve-cases.csv',index=False)
    files.append('price-reserve-cases.csv')
    report=dict(status='COMPLETED_EXPLORATORY_PRICE_RESERVE_NO_PROMOTION',profile=name,parameters=p['profiles'][name],
        protocol_sha256=digest(root/'protocol.json'),universe_count=p['universe_count'],
        training_rows=int(f.date.dt.year.eq(2024).sum()),evaluated_rows=len(evaluated),
        primary=primary,secondary_top10=secondary_report,frozen_old_membership=frozen_report,
        risk=risks,monthly_audit=audit,selected_unique_symbols=int(evaluated.loc[evaluated.chosen_side,'symbol'].nunique()),
        price_reserve_rows=len(severe),price_reserve_symbols=sorted(severe.symbol.unique().tolist()),
        files={n:digest(folder/n) for n in files},
        interpretation='Percent per hypothetical entry, not yearly capital return or portfolio drawdown; memberships learned separately per TP/SL.')
    verify_hashes(Path('.'),p['source_hashes']);verify_hashes(root,manifest)
    atomic_json(folder/'report.json',report)
    return report


def run(root):
    p=read(root/'protocol.json')
    if (root/'report.json').exists():raise ValueError('Immutable completed root report exists')
    cases={name:run_case(root,name) for name in p['profiles']}
    reference=read(BASE/'report.json')
    comparison=[]
    for name,case in [('REFERENCE_TP20_SL7',reference),*cases.items()]:
        for row in case['primary']['summary']:
            if row['arm'] in ('SYMBOL_LONG','SYMBOL_SHORT','SELECT_SIDE'):
                risk=next((r for r in case.get('risk',[]) if r['year']==row['year'] and r['arm']==row['arm']),{})
                comparison.append(dict(profile=name,year=row['year'],arm=row['arm'],n=row['n'],symbols=row['symbols'],
                    tp_rate=row['tp_rate'],profitable_rate=row['profitable_rate'],mean_net=row['mean_net_outcome'],
                    worst_net=risk.get('worst_net_outcome'),mae95_upper=risk.get('adverse_through_exit_p95')))
    pd.DataFrame(comparison).to_csv(root/'comparison.csv',index=False)
    verify_hashes(Path('.'),p['source_hashes'])
    atomic_json(root/'report.json',dict(status='COMPLETED_EXPLORATORY_PRICE_RESERVE_NO_PROMOTION',
        protocol_sha256=digest(root/'protocol.json'),universe_count=p['universe_count'],comparison=comparison,
        case_reports={name:dict(path=str(Path(name)/'report.json'),sha256=digest(root/name/'report.json')) for name in cases},
        reference=str(BASE/'report.json'),note='Same population/fees/gate, targets and monthly memberships differ. Frozen-old-membership controls supplied.'))
    atomic_json(root/'progress.json',dict(status='COMPLETED_EXPLORATORY_PRICE_RESERVE_NO_PROMOTION',phase='DONE'))
    LOG.info('Both TP10 variants completed')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--phase',choices=['prepare','build','run'],required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    {'prepare':prepare,'build':build,'run':run}[args.phase](args.output)


if __name__=='__main__':main()
