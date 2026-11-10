"""Fixed economic replay: TOP358 Oracle -> A2 -> vol20/regime/native risk.

Three matched entry policies and two fixed cost stresses, research only.
Sealed detection/price archives; no new models/providers/SQL/orders/config.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor,as_completed
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime,timezone
import hashlib
import json
from multiprocessing import get_context
from pathlib import Path
import time
import sys
from unittest.mock import patch

import numpy as np
import pandas as pd
import requests

from scripts.research import us_q051_range_support_a2_20261109 as original
from scripts.research.us_a2_replay_inputs_20261109 import FrozenPriceSource,IndexedSchedule,FixedWait
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest
from scripts.research.us_a2_oracle_top20pct_20261109 import EXT,BASE

ROOT=Path('artifacts/research/us_a2_top20pct_economic/20261109-v1')
FREQUENCY=Path('artifacts/research/us_a2_oracle_top20pct/20261109-v1')
CONTROL=original.CONTROL
REFERENCE=Path('artifacts/research/us_q051_range_support_a2/20261109-v1/reference-postvalidated')
CASES={'A2':dict(timing='A2',cost=8),'OPEN_COMMON':dict(timing='OPEN',cost=8),
    'WAIT_COMMON':dict(timing='WAIT',cost=8),'A2_COST25':dict(timing='A2',cost=25),
    'OPEN_COMMON_COST25':dict(timing='OPEN',cost=25)}


def read(path):return original.read(path)


def scheduled_only_fix_proof():
    """Previous full reference is valid; the sole new core edit is a late mark."""
    old=read(Path('artifacts/research/us_q051_range_support_a2/20261109-v1/request.json'))['source_hashes']
    core={str(Path(k)):v for k,v in old.items() if 'backtesting' in Path(k).parts}
    proof={}
    for path,sha in core.items():
        p=Path(path)
        if digest(p)==sha:proof[path]='UNCHANGED';continue
        if p.name!='winner_daily_entry.py':raise ValueError('Unqualified core change: '+path)
        b=p.read_bytes();nl=b'\r\n' if b'\r\n' in b else b'\n'
        new=nl.join([b'        # A late fill is a newer observed mark than the daily opening carried',
            b'        # by an incomplete-session fallback. Do not restore that stale print.',
            b'        if previous is not None and not scheduled:book.marks[symbol]=previous'])
        reconstructed=b.replace(new,b'        if previous is not None:book.marks[symbol]=previous')
        if new not in b or hashlib.sha256(reconstructed).hexdigest()!=sha:raise ValueError('Scheduled mark fix differs from qualified patch')
        proof[path]='ONLY_SCHEDULED_MARK_FIX; default scheduled=False keeps identical branch'
    return proof


def prepare(root):
    root.mkdir(parents=True,exist_ok=False);inputs=root/'inputs';inputs.mkdir()
    frequency=read(FREQUENCY/'report.json');validation=read(FREQUENCY/'validation.json')
    main=next(x for x in frequency['cohorts'] if x['cohort']=='ORACLE_TOP20PCT_DIRECT')
    if frequency['status']!='COMPLETED_FREQUENCY_ONLY' or not main['frequency_pass'] or validation['status']!='PASS':
        raise ValueError('A2 frequency not qualified')
    for name,sha in read(FREQUENCY/'inputs/manifest.json')['files'].items():
        if digest(FREQUENCY/'inputs'/name)!=sha:raise ValueError('Changed frequency artifact')
    proof=scheduled_only_fix_proof()
    if read(REFERENCE/'validation.json')['status']!='PASS' or read(REFERENCE/'isolation.json')['status']!='COMPLETED':
        raise ValueError('Unqualified prior full reference reproduction')
    cohort=pd.read_parquet(FREQUENCY/'inputs/cohorts.parquet',columns=['trade_date','symbol','rank','entry_year'])
    audit=pd.concat([pd.read_parquet(p,columns=['signal_date','symbol','context_qualified'])
        for p in sorted((FREQUENCY/'inputs/audits').glob('*.parquet'))],ignore_index=True)
    audit['trade_date']=pd.to_datetime(audit.signal_date)
    cohort=cohort.merge(audit[['trade_date','symbol','context_qualified']],on=['trade_date','symbol'],validate='one_to_one')
    common=cohort[cohort.context_qualified].copy();common['selected']=True;common['side']='long'
    if len(common)!=main['context_qualified'] or len(cohort)!=main['candidates']:raise ValueError('Changed known-context cohort')
    models=read(BASE/'protocol.json')['annual_models'];common['oracle_batch_id']=common.entry_year.map(lambda y:models[str(y)]['batch_id'])
    common.to_parquet(inputs/'signals-common.parquet',index=False)
    events=pd.read_parquet(FREQUENCY/'inputs/a2-events.parquet')
    if len(events)!=2835 or events.duplicated(['signal_date','symbol']).any():raise ValueError('Changed A2 event count')
    events['trade_date']=pd.to_datetime(events.signal_date)
    a2=common.merge(events[['trade_date','symbol']],on=['trade_date','symbol'],validate='one_to_one')
    if len(a2)!=len(events):raise ValueError('A2 outside fixed known context')
    a2.to_parquet(inputs/'signals-a2.parquet',index=False);events.to_parquet(inputs/'schedule-a2.parquet',index=False)
    sources=[Path(__file__),Path('scripts/research/us_a2_replay_inputs_20261109.py'),Path('backtesting/winner_daily_entry.py'),
        Path('backtesting/winner_intraday.py'),Path('backtesting/winner_portfolio_budget.py'),Path('backtesting/simulator.py'),
        FREQUENCY/'request.json',FREQUENCY/'report.json',FREQUENCY/'validation.json',FREQUENCY/'inputs/manifest.json',
        REFERENCE/'validation.json',REFERENCE/'result/report.json',CONTROL/'configuration.json',BASE/'protocol.json',
        BASE/'inputs/manifest.json',EXT/'inputs/manifest.json']
    atomic_json(root/'request.json',dict(start='2021-01-01',end='2026-10-01',initial_equity=4000.,annual_reset=False,
        annual_models=models,oracle_pool=358,oracle_percent=.2,per_symbol_filter=False,per_sector_filter=False,cases=CASES,
        signals_common=len(common),confirmed_A2=len(events),regime_A2=main['regime_allowed_signals'],
        settings=read(FREQUENCY/'request.json')['settings'],known_context_selection='46 closed M15 slots before signal J close, no future-path selection',
        risk='Exact Q051 vol20/regime,SL5/open11,full position,risk1.25%,weight20%,entry cap1x,margin capacity2x,B4 off',
        costs='8bps/leg;fixed stress25bps/leg;annual financing6.5%',
        ranking='Original Oracle order among concurrently executable candidates; no per-symbol/SHORT',
        pruning='A2 consumes a causal event tape only; no capital reservation before availability. Full versus pruned native equality tested.',
        controls='Same prior-context cohort, openJ+1 versus fixed10:30NY versus A2. Original per-symbol reference for context only.',
        price_source='Exact frequency audit priority and sealed tapes; includes extra historical data, shared across new cases',
        fallback='Incomplete protection sessions use daily adverse bound; after late entry low may have occurred before purchase',
        core_qualification=proof,reference_reuse=str(REFERENCE),reference_role='Different universe/data footprint; matched new controls isolate entry rule',
        source_hashes={str(p):digest(p) for p in sources},provider_calls=0,SQL_writes=0,orders=0,training=False,
        production_changes=False,retrospective=True,independent_holdout=False,created_at_utc=datetime.now(timezone.utc).isoformat()))
    atomic_json(inputs/'manifest.json',dict(files={p.name:digest(p) for p in inputs.iterdir() if p.is_file()}))
    atomic_json(root/'progress.json',dict(status='INPUTS_FROZEN',completed=0,total=len(CASES),cases=list(CASES)))


def market_data():
    pivots,sectors,actions=original.shared.market_data(BASE);d=pd.read_parquet(EXT/'inputs/daily.parquet')
    for field in pivots:pivots[field]=pd.concat([pivots[field],d.pivot(index='date',columns='symbol',values=field)],axis=1).sort_index()
    sectors=pd.concat([sectors,pd.read_parquet(EXT/'inputs/sectors.parquet')],ignore_index=True)
    if sectors.symbol.duplicated().any():raise ValueError('Duplicate sectors')
    actions=pd.concat([actions,pd.read_parquet(EXT/'inputs/actions.parquet')],ignore_index=True)
    return pivots,sectors,actions


def replay(root,name):
    from backtesting.simulator import BacktestEngine,BacktestResult
    from backtesting.winner_campaign_replay import metrics
    from backtesting.winner_portfolio_budget import replay_protections
    from scripts.research.us_winner_q051_risk_budget_20261109 import matched_configuration,daily_metrics
    from common.config_loader import replay_market_registry
    from backtesting.isolation import ReadOnlyReplay
    root=Path(root);plan=read(root/'request.json');case=CASES[name]
    for p,sha in plan['source_hashes'].items():
        if digest(Path(p))!=sha:raise ValueError('Frozen code/source changed: '+p)
    for p,sha in read(root/'inputs/manifest.json')['files'].items():
        if digest(root/'inputs'/p)!=sha:raise ValueError('Changed replay input')
    folder=root/'cases'/name;out=folder/'result';out.mkdir(parents=True,exist_ok=False);started=time.monotonic()
    try:
        base=read(BASE/'protocol.json');_,cfg=matched_configuration(base,read(BASE/'cases/Q051_050/result/configuration.json'),'REGIME_VOL20')
        if json.loads(json.dumps(asdict(cfg),default=str))!=read(CONTROL/'configuration.json')['portfolio']:
            raise ValueError('Reference configuration differs')
        cfg.cost_round_trip_bps=2.*case['cost']
        signals=pd.read_parquet(root/'inputs'/('signals-a2.parquet' if case['timing']=='A2' else 'signals-common.parquet'))
        timing=IndexedSchedule(pd.read_parquet(root/'inputs/schedule-a2.parquet')) if case['timing']=='A2' else FixedWait() if case['timing']=='WAIT' else None
        prices=FrozenPriceSource(read(FREQUENCY/'inputs/manifest.json'));pivots,sectors,actions=market_data()
        policy,gate=replay_protections(pivots['close'],daily_entry=True,target=.2,regime=True)
        reference=deepcopy(base['reference']);reference['risk']=asdict(cfg.risk_config);reference['per_symbol_selection']=None
        reference['arguments'].update(top_n=358,per_symbol_long=False,per_sector_long=False,
            per_symbol_min_long_probability=None,per_symbol_min_long_auc=None,portfolio_vol_target=.2,
            entry_regime_filter=True,drawdown_controller=False,cost_per_leg_bps=case['cost'])
        protocol=dict(start=plan['start'],end=plan['end'],initial_equity=4000.,annual_models=plan['annual_models'],annual_reset=False,
            reference=reference,profile=name,selection='TOP20% Oracle without per-symbol, A2 or matched control',
            experiment_request_sha256=digest(root/'request.json'),
            replay_command=[sys.executable,'-m','scripts.research.us_a2_top20pct_economic_20261109','--phase','run','--output-dir',str(root)])
        atomic_json(folder/'protocol.json',protocol);atomic_json(out/'configuration.json',dict(profile=name,portfolio=asdict(cfg)))
        def no_http(*a,**kw):raise ValueError('No provider calls in A2 economic test')
        with ReadOnlyReplay(folder).install(),replay_market_registry(original.shared.restore_registry(BASE)),patch.object(requests.Session,'request',no_http):
            def progress(done,total,day):
                atomic_json(folder/'progress.json',dict(status='RUNNING',completed=done,total=total,last_date=str(day),
                    elapsed_seconds=time.monotonic()-started,updated_at_utc=datetime.now(timezone.utc).isoformat()))
            result=BacktestEngine(cfg).run(open_df=pivots['open'],close=pivots['close'],high=pivots['high'],low=pivots['low'],
                volume=pivots['volume'],signals_df=signals,sector_map=sectors.set_index('symbol').sector.to_dict(),
                intraday_source=prices,winner_research_assumptions=True,winner_progress=progress,
                winner_corporate_actions=actions.to_dict('records'),winner_selection_source=gate,
                winner_entry_risk_policy=policy,winner_entry_timing_source=timing)
            result.equity_curve.rename('equity').to_csv(out/'equity-daily.csv');result.intraday_equity_curve.to_parquet(out/'equity-5m.parquet',index=False)
            result.closed_trades_df.to_csv(out/'trades.csv',index=False);result.trade_events_df.to_csv(out/'events.csv',index=False)
            result.drawdown_breaker_df.to_csv(out/'risk-5m.csv',index=False)
            pd.DataFrame(policy.receipts).to_csv(out/'portfolio-risk-decisions.csv',index=False)
            pd.DataFrame(gate.receipts).to_csv(out/'regime-decisions.csv',index=False)
            report=metrics(result,4000.);report.update(daily_metrics(result.equity_curve));annual=[];opening=4000.
            for year in range(2021,2027):
                curve=result.equity_curve[result.equity_curve.index.year==year];trades=result.closed_trades_df;marks=result.intraday_equity_curve
                closed=trades[pd.to_datetime(trades.exit_date,utc=True).dt.year.eq(year)] if len(trades) else trades
                part=BacktestResult(equity_curve=curve,closed_trades_df=closed,
                    intraday_equity_curve=marks[pd.to_datetime(marks.timestamp,utc=True).dt.year.eq(year)],
                    tracker_snapshot={'winner_replay':dict(status=report['status'],full_live_parity=False)})
                row=metrics(part,opening);row['year']=year;annual.append(row);opening=float(curve.iloc[-1])
            pd.DataFrame(annual).to_csv(out/'annual-summary.csv',index=False)
            report.update(profile=name,annual_models=plan['annual_models'],annual_reset=False,selected_signals=len(signals),
                scheduled_input_pruned=case['timing']=='A2',input_A2_after_regime=2452,
                provider_calls=0,SQL_writes=0,orders=0,production_changes=False,
                finished_at_utc=datetime.now(timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-started)
            atomic_json(out/'report.json',report);atomic_json(folder/'progress.json',dict(status='COMPLETED_EXPLORATORY'))
        from ihm.services.backtesting_import import import_continuous_winner
        record=import_continuous_winner(folder,run_id='20261109_a2_20pct_'+name.lower()+'_v1',
            label='TOP20% Oracle → '+name+' — vol20/régime',result_subdir='result')
        atomic_json(folder/'progress.json',dict(status='COMPLETED_EXPLORATORY',ihm_run_id=record['run_id']))
        return dict(profile=name,folder=str(folder),ihm_run_id=record['run_id'])
    except Exception as exc:
        atomic_json(folder/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)));raise


def csv(path):
    try:return pd.read_csv(path)
    except pd.errors.EmptyDataError:return pd.DataFrame()


def finalize(root,results):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    rows=[];annual=[];checks=[];curves={};reference=read(CONTROL/'report.json')
    columns=['final_equity','return_pct','max_drawdown_pct','win_pct','closed_lot_trades','winners','losers',
        'average_winning_pnl','average_losing_pnl','average_winning_holding_days','average_losing_holding_days',
        'average_gross_capital','maximum_gross_capital','average_gross_equity_ratio']
    rows.append(dict(profile='Q051_VOL20_REGIME_REFERENCE',**{k:reference.get(k) for k in columns}))
    curves['Q051 per-symbol vol20/régime — référence']=pd.read_csv(CONTROL/'equity-daily.csv',index_col=0,parse_dates=True).iloc[:,0]
    tape=pd.read_parquet(root/'inputs/schedule-a2.parquet')
    lookup={(x.signal_date,x.symbol):pd.Timestamp(x.execution_at) for x in tape.itertuples()}
    for item in results:
        folder=Path(item['folder'])/'result';name=item['profile'];report=read(folder/'report.json')
        trades=csv(folder/'trades.csv');events=csv(folder/'events.csv');risk=csv(folder/'portfolio-risk-decisions.csv')
        pnl=trades.pnl if len(trades) else pd.Series(dtype=float)
        if len(trades)!=report['closed_lot_trades'] or int(pnl.gt(0).sum())!=report['winners']:raise ValueError('Trade counter mismatch')
        if int(pnl.lt(0).sum())!=report['losers']:raise ValueError('Loss counter mismatch')
        scheduled=events[events.get('execution_proxy',pd.Series(index=events.index,dtype=str)).eq('SCHEDULED_5M_OPEN')]
        for row in scheduled.to_dict('records'):
            if pd.Timestamp(row['available_at'])>pd.Timestamp(row['time']):raise ValueError('Future fill')
            if CASES[name]['timing']=='A2' and pd.Timestamp(row['time'])!=lookup.get((str(row['signal_date']),row['symbol'])):
                raise ValueError('A2 fill not on frozen causal execution clock')
        fallback=events[events.get('event',pd.Series(index=events.index,dtype=str)).eq('DAILY_OHLC_FALLBACK')]
        keys={(str(pd.Timestamp(x['time']).date()),x['symbol']) for x in fallback.to_dict('records')}
        bound=sum((str(pd.Timestamp(x['time']).date()),x['symbol']) in keys for x in scheduled.to_dict('records'))
        if len(risk) and risk.status.eq('QUALIFIED').any():
            positive=risk[risk.status.eq('QUALIFIED')&risk.get('final_quantity',pd.Series(0,index=risk.index)).gt(0)]
            if len(positive) and positive.approved_vol.gt(.2+1e-10).any():raise ValueError('New entry above portfolio-vol budget')
        checks.append(dict(profile=name,counts='PASS',causal_clocks='PASS',volatility_budget='PASS',
            late_entries_daily_adverse_bound=int(bound)))
        rows.append(dict(profile=name,**{k:report.get(k) for k in columns},late_entries_daily_adverse_bound=int(bound)))
        curve=pd.read_csv(folder/'equity-daily.csv',index_col=0,parse_dates=True).iloc[:,0]
        if abs(float(curve.iloc[-1])-report['final_equity'])>1e-6:raise ValueError('Equity mismatch')
        curves[name]=curve
        a=pd.read_csv(folder/'annual-summary.csv');a['profile']=name;annual.append(a)
        for row in a.to_dict('records'):
            closed=trades[pd.to_datetime(trades.exit_date,utc=True).dt.year.eq(row['year'])] if len(trades) else trades
            if len(closed)!=row['closed_lot_trades']:raise ValueError('Annual count mismatch')
    pivots,_,_=original.shared.market_data(BASE);spy=pivots['close']['SPY'].loc['2021-01-01':'2026-10-01']
    curves['SPY prix seuls — sans dividendes/frais']=4000.*spy/float(pivots['open'].loc[spy.index,'SPY'].iloc[0])
    table=pd.DataFrame(curves).sort_index();table.loc[pd.Timestamp('2021-01-01')]=4000.;table=table.sort_index()
    charts=root/'charts';charts.mkdir();table.to_csv(charts/'capital-comparison.csv',index_label='date')
    fig,axes=plt.subplots(2,1,figsize=(15,11),sharex=True)
    for column in table:
        stress=column.endswith('COST25')
        for i,ax in enumerate(axes):
            if i==0 and stress:continue
            if i==1 and not stress and column not in ['A2','OPEN_COMMON'] and not column.startswith(('Q051','SPY')):continue
            ax.plot(table.index,table[column],label=column,linewidth=1.4)
    for i,ax in enumerate(axes):
        ax.set_title('Comparaison principale —8pb/opération' if i==0 else 'Stress des coûts —25pb/opération et témoins8pb')
        ax.set_ylabel('Capital valorisé USD');ax.grid(alpha=.2);ax.legend(fontsize=8)
    fig.suptitle('TOP20% Oracle → A2 → risque vol20/régime —2021–01/10/2026 —4 000USD')
    fig.text(.06,.01,'Exploratoire ; couverture intraday partielle et bornes OHLC défavorables après certaines entrées tardives. SPY prix seuls.',fontsize=9)
    fig.tight_layout(rect=(0,.035,1,.97));fig.savefig(charts/'capital-comparison.png',dpi=140);fig.savefig(charts/'capital-comparison.svg');plt.close(fig)
    pd.DataFrame(rows).to_csv(root/'comparison.csv',index=False);pd.concat(annual,ignore_index=True).to_csv(root/'annual-comparison.csv',index=False)
    atomic_json(root/'validation.json',dict(status='PASS',cases=checks,reference_reuse=str(REFERENCE),
        limitation='Daily adverse bound may include pre-entry extremes; no live execution parity'))
    report=dict(status='COMPLETED_EXPLORATORY',results=rows,imports=results,validation='PASS',
        chart=str(charts/'capital-comparison.png'),provider_calls=0,SQL_writes=0,orders=0,production_changes=False,
        finished_at_utc=datetime.now(timezone.utc).isoformat())
    atomic_json(root/'report.json',report);atomic_json(root/'progress.json',report)


def run(root,workers):
    root=Path(root);read(root/'request.json');results=[];failures=[]
    atomic_json(root/'progress.json',dict(status='RUNNING_FIVE_REPLAYS',completed=0,total=5,cases=list(CASES)))
    with ProcessPoolExecutor(max_workers=workers,mp_context=get_context('spawn')) as pool:
        tasks={pool.submit(replay,str(root),name):name for name in CASES}
        for task in as_completed(tasks):
            try:results.append(task.result())
            except Exception as exc:failures.append(dict(profile=tasks[task],error_type=type(exc).__name__,error=str(exc)))
            atomic_json(root/'progress.json',dict(status='RUNNING_FIVE_REPLAYS',completed=len(results)+len(failures),total=5,
                results=results,failures=failures))
    if failures:
        terminal=dict(status='INCOMPLETE_CASES',results=results,failures=failures)
        atomic_json(root/'report.json',terminal);atomic_json(root/'progress.json',terminal);return
    finalize(root,results)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--phase',choices=['prepare','run'],required=True)
    parser.add_argument('--output-dir',type=Path,default=ROOT);parser.add_argument('--workers',type=int,default=2);args=parser.parse_args()
    try:
        if args.phase=='prepare':prepare(args.output_dir)
        else:run(args.output_dir,args.workers)
    except Exception as exc:
        if args.output_dir.exists():atomic_json(args.output_dir/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)))
        raise
