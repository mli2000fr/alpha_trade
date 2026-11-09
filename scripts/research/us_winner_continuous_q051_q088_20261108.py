"""Three user-specified continuous annual-model profiles, frozen before replay.

Only SQL reads for missing archived scores/prices. No provider calls, inference,
production writes or orders. Every completed result is imported into IHM history.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor,as_completed
from copy import deepcopy
from dataclasses import asdict
from datetime import date,datetime,timedelta,timezone
from functools import lru_cache
import json
import math
from multiprocessing import get_context
import os
from pathlib import Path
import shutil
import time

import numpy as np
import pandas as pd
from sqlalchemy import bindparam,text

from scripts.research.us_concentrated_historical_tapes import atomic_json,digest
from scripts.research.us_winner_continuous_annual_models_20261108 import read,annual_signal_days
from scripts.research.us_winner_continuous_registry_recovery_20261108 import restore_registry

BASE=Path('artifacts/research/us_winner_continuous_annual_models/20261108-v6')
ROOT=Path('artifacts/research/us_winner_continuous_q051_q088/20261108-v2')
PREVIOUS=Path('artifacts/research/us_winner_continuous_q051_q088/20261108-v1')
GRID=Path('artifacts/research/us_winner_ui_grid/20261107-v3')
Q051=Path('artifacts/research/us_winner_risk_tradeoff/20261107-v1/cases/Q051_SIZE125_GROSS1')
CASES={
    'Q051_060':dict(profile='Q051',pool=.10,long_top_n=5,score=.60,auc=.60,controller=False,gross=1.),
    'Q088_050':dict(profile='Q088',pool=.20,long_top_n=10,score=.50,auc=.50,controller=True,gross=2.),
    'Q051_050':dict(profile='Q051',pool=.10,long_top_n=5,score=.50,auc=.50,controller=False,gross=1.),
}


def settings(case,size):
    from backtesting.per_symbol_selection import PerSymbolSelection
    return PerSymbolSelection(oracle_top_n=math.ceil(size*case['pool']),long_top_n=case['long_top_n'],
        allow_long=True,allow_short=False,min_long_probability=case['score'],min_long_auc=case['auc'])


def configuration(reference,case):
    from scripts.research.us_winner_ui_grid_20261107 import configuration as build
    overrides=dict(risk_per_trade_pct=.0125,max_position_weight=.20,
        max_gross_exposure=case['gross'],force_close_on_breaker=case['controller'])
    cfg=build(reference,dict(risk=overrides,policy={},daily=True,controller=case['controller']))
    cfg.start_date=date(2021,1,1);cfg.end_date=date(2026,10,1)
    cfg.cost_round_trip_bps=2.*reference['arguments']['cost_per_leg_bps']
    return cfg


def supplemental_windows(selections,sessions,known,horizon=10):
    """Price inventory only; never use future availability to screen entries."""
    from bisect import bisect_right
    days=sorted(sessions);result={d:set() for d in days}
    for frame in selections:
        for row in frame.itertuples():
            if row.symbol in known:continue
            first=bisect_right(days,pd.Timestamp(row.trade_date).date())
            for day in days[first:first+horizon+1]:result[day].add(row.symbol)
    return result


def copy_owned(source,target):
    target.parent.mkdir(parents=True,exist_ok=True)
    try:os.link(source,target)
    except PermissionError:shutil.copyfile(source,target)


def verify_branches(frame,manifest):
    records={(r['symbol'],r['year'],r['side']):r for r in manifest['models']}
    for side in ('long','short'):
        column=side+'_probability';values=pd.to_numeric(frame[column],errors='coerce')
        if (frame[column].notna()&~values.between(0,1)).any():raise ValueError('Probabilité invalide : '+side)
        for (symbol,year),g in frame[values.notna()].groupby(['symbol',frame.loc[values.notna(),'date'].dt.year]):
            r=records.get((symbol,int(year),side))
            if r is None or not g[side+'_model_sha256'].eq(r['sha256']).all() or not g.date.gt(pd.Timestamp(r['available'])).all():
                raise ValueError('Score per-symbol incompatible/futur : '+symbol)


def normalize_ranking_dates(frame):
    frame=frame.copy()
    for column in ('date','fold_start','lineage_fold_start','model_available_date','long_auc_available_date'):
        if column in frame:frame[column]=pd.to_datetime(frame[column],errors='raise')
    return frame


def recover_2026(engine,batch,start,end,manifest_hash):
    query=text('SELECT p.prediction_date AS date,p.symbol,p.proba_extreme,p.fold_start, '
        'l.fold_start AS lineage_fold_start,l.model_available_date,l.target_name,l.target_horizon, '
        'l.model_sha256,l.feature_profile_sha256,d.long_probability,d.short_probability, '
        'd.long_model_sha256,d.short_model_sha256,d.manifest_sha256 '
        'FROM oracle_extreme_predictions p LEFT JOIN oracle_path_prediction_lineage l '
        'ON p.batch_id=l.batch_id AND p.symbol=l.symbol AND p.prediction_date=l.prediction_date '
        'LEFT JOIN oracle_path_directional_predictions d ON p.batch_id=d.batch_id AND p.symbol=d.symbol '
        'AND p.prediction_date=d.prediction_date WHERE p.batch_id=:batch '
        'AND p.prediction_date BETWEEN :start AND :end AND UNIX_TIMESTAMP(d.updated_at)<=:epoch')
    with engine.connect() as conn,conn.begin():
        conn.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
        frame=pd.read_sql(query,conn,params=dict(batch=batch,start=start,end=end,epoch=time.time()))
    if not frame.manifest_sha256.eq(manifest_hash).all():raise ValueError('Manifeste SQL directionnel différent')
    frame['date']=pd.to_datetime(frame.date)
    return frame


def prepare(root):
    from database.connection import get_sqlalchemy_engine
    from common.market_calendar import get_market_calendar
    from common.config_loader import replay_market_registry
    from modelFactory.oracle_path.predict import load_contract
    from modelFactory.oracle_path.directional import load_manifest
    from backtesting.winner_campaign_replay import validate_scores,SqlIntradaySource
    from backtesting.per_symbol_selection import select_per_symbol,attach_calibration_auc
    from backtesting.winner_data import daily_bars
    from backtesting.isolation import ReadOnlyReplay
    base=read(BASE/'protocol.json');bm=read(BASE/'inputs/manifest.json')
    root.mkdir(parents=True,exist_ok=False);inputs=root/'inputs';inputs.mkdir()
    atomic_json(root/'progress.json',dict(status='VERIFYING_FROZEN_BASE'))
    for name,sha in bm['files'].items():
        if digest(BASE/'inputs'/name)!=sha:raise ValueError('Archive de base modifiée : '+name)
    # The native engine must match the completed reference. Deleted IHM source
    # exports are documented and replaced with verified archives/SQL receipts.
    missing=[]
    for name,sha in base['sources'].items():
        path=Path(name)
        if not path.exists():
            if 'ihm_backtesting_runs' in name:missing.append(name);continue
            raise ValueError('Source absente : '+name)
        if digest(path)!=sha:raise ValueError('Source de référence modifiée : '+name)
    atomic_json(root/'request.json',dict(cases=CASES,start=base['start'],end=base['end'],initial_equity=4000.,
        annual_reset=False,model_mapping=base['annual_models'],missing_original_IHM_exports=missing,
        approved_at_utc=datetime.now(timezone.utc).isoformat()))
    for name in bm['files']:
        copy_owned(BASE/'inputs'/name,inputs/'base'/name)
    copy_owned(BASE/'inputs/market-registry.json',inputs/'market-registry.json')
    registry=restore_registry(root)
    engine=get_sqlalchemy_engine(db_name='alpha_trade')
    selected={name:[] for name in CASES};baseline=[];annual={};score_receipts={};symbols=set()
    with replay_market_registry(registry):
        calendar=get_market_calendar('US_EQ',allow_us_weekday_fallback=False)
        for year,old in base['annual_models'].items():
            year=int(year);atomic_json(root/'progress.json',dict(status='QUALIFYING_ANNUAL_SELECTIONS',year=year,completed=year-2021,total=6))
            model,contract,_,folds=load_contract('artifacts/models',old['batch_id'])
            manifest,mhash=load_manifest(model)
            if contract['horizon']!=10 or pd.Timestamp(contract['training_config']['data']['training_end_date'])>=pd.Timestamp(year,1,1):
                raise ValueError('Horizon ou dates du modèle annuel incompatibles')
            actual,days=annual_signal_days(calendar,year)
            path=Path('artifacts/ihm_backtesting_runs/run')/old['run_id']/'artifacts/per-symbol-ranking.csv'
            cached=PREVIOUS/'inputs/rankings'/f'{year}.parquet'
            if cached.exists():
                frame=pd.read_parquet(cached)
                origin=dict(kind='PARTIAL_PREPARATION_REVALIDATED',path=str(cached),sha256=digest(cached),
                    observed_at_utc=datetime.fromtimestamp(cached.stat().st_mtime,timezone.utc).isoformat())
            elif path.exists():
                frame=pd.read_csv(path,parse_dates=['date'],low_memory=False)
                origin=dict(kind='ORIGINAL_IHM_EXPORT',path=str(path),sha256=digest(path))
            elif year==2025:
                path=GRID/'inputs/ranked-source.parquet';gm=read(GRID/'inputs/manifest.json')
                if digest(path)!=gm['files']['ranked-source.parquet']:raise ValueError('Archive 2025 modifiée')
                frame=pd.read_parquet(path);origin=dict(kind='FROZEN_GRID_ARCHIVE',path=str(path),sha256=digest(path))
            elif year==2026:
                with ReadOnlyReplay(root).install():
                    frame=recover_2026(engine,old['batch_id'],days[0],days[-1],mhash)
                origin=dict(kind='EXISTING_SQL_PREDICTIONS_READ_ONLY',observed_at_utc=datetime.now(timezone.utc).isoformat())
            else:raise ValueError('Archive de scores annuelle introuvable : '+str(year))
            frame=normalize_ranking_dates(frame)
            if not set(frame.symbol).issubset(contract['universe']):raise ValueError('Scores hors univers du modèle')
            if set(frame.date.dt.date)!=set(days):raise ValueError('Calendrier annuel incomplet ou excédentaire')
            validate_scores(frame.rename(columns={'date':'trade_date'}),profile_hash=digest(model/'feature_profile.json'),
                folds=folds,expected_days=days,top_n=358,horizon=10,universe_size=len(contract['universe']),min_coverage=.93)
            verify_branches(frame,manifest)
            auc_columns=[c for c in frame if c.startswith('long_auc')]
            frame=attach_calibration_auc(frame.drop(columns=auc_columns),model)
            path=inputs/'rankings'/f'{year}.parquet';path.parent.mkdir(exist_ok=True)
            frame.to_parquet(path,index=False);origin.update(archive_sha256=digest(path),rows=len(frame),manifest_sha256=mhash)
            score_receipts[str(year)]=origin;counts={}
            # Reproduce the completed Q088 selector for every year, including
            # recovered 2026 scores, before applying any requested new threshold.
            for name,case in {**CASES,'BASELINE_Q088':dict(pool=.2,long_top_n=10,score=.6,auc=.6)}.items():
                choice=select_per_symbol(frame,settings(case,len(contract['universe'])))
                choice=choice[choice.selected].rename(columns={'date':'trade_date'}).copy()
                choice['rank']=choice['rank'].astype(int);choice['oracle_amplitude_rank']=choice.oracle_rank
                choice['source_run_id']=old['run_id'];choice['oracle_batch_id']=old['batch_id'];choice['entry_year']=year
                if name=='BASELINE_Q088':baseline.append(choice)
                else:selected[name].append(choice);symbols.update(choice.symbol)
                counts[name]=dict(signals=len(choice),symbols=int(choice.symbol.nunique()),selection=settings(case,len(contract['universe'])).snapshot())
            annual[str(year)]={**old,'selection':counts}
    reproduced=pd.concat(baseline,ignore_index=True).sort_values(['trade_date','symbol']).reset_index(drop=True)
    old=pd.read_parquet(inputs/'base/signals-uniform20pct.parquet').sort_values(['trade_date','symbol']).reset_index(drop=True)
    for field in ['trade_date','symbol','rank','long_probability','oracle_amplitude_rank']:
        if field=='long_probability':same=np.allclose(reproduced[field],old[field],rtol=1e-10,atol=1e-12)
        else:same=reproduced[field].equals(old[field])
        if not same:raise ValueError('Sélection Q088 originale non reproduite : '+field)
    frames={name:pd.concat(parts,ignore_index=True).sort_values(['trade_date','rank','symbol']) for name,parts in selected.items()}
    for name,frame in frames.items():frame.to_parquet(inputs/f'signals-{name}.parquet',index=False)
    known=set(bm['symbols']);extra=sorted(symbols-known)
    with replay_market_registry(registry):
        sessions=[s.session_date for s in calendar.sessions(date(2021,1,1),date(2026,10,1)) if s.is_open]
        windows=supplemental_windows(frames.values(),sessions,known)
    atomic_json(root/'progress.json',dict(status='FREEZING_SUPPLEMENTAL_PRICES_READ_ONLY',extra_symbols=len(extra),completed=0,total=len(sessions)))
    old_daily=pd.read_parquet(inputs/'base/daily.parquet')
    from scripts.research.us_winner_ui_grid_20261107 import partitioned_intraday
    with ReadOnlyReplay(root).install(),engine.connect() as conn,conn.begin():
        conn.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
        pieces=[daily_bars(conn,extra[i:i+100],old_daily.date.min().date(),date(2026,10,1)) for i in range(0,len(extra),100)]
        daily=pd.concat(pieces,ignore_index=True) if pieces else old_daily.iloc[:0].copy()
        daily.to_parquet(inputs/'extra-daily.parquet',index=False)
        if extra:
            sectors=pd.read_sql(text('SELECT symbol,sector FROM stock_metadata WHERE symbol IN :symbols').bindparams(bindparam('symbols',expanding=True)),conn,params={'symbols':extra})
            actions=pd.read_sql(text('SELECT symbol,ca_type,ex_date,payable_date,amount_per_share,currency FROM corporate_actions_events '
                'WHERE symbol IN :symbols AND ex_date BETWEEN :start AND :end').bindparams(bindparam('symbols',expanding=True)),conn,
                params=dict(symbols=extra,start=date(2021,1,1),end=date(2026,10,1)))
        else:
            sectors=pd.read_parquet(inputs/'base/sectors.parquet').iloc[:0];actions=pd.read_parquet(inputs/'base/actions.parquet').iloc[:0]
        sectors.to_parquet(inputs/'extra-sectors.parquet',index=False);actions.to_parquet(inputs/'extra-actions.parquet',index=False)
        tape=inputs/'extra-intraday';tape.mkdir()
        source=SqlIntradaySource(conn,discard_unqualified=True,allow_daily_fallback=True)
        for i,day in enumerate(sessions):
            names=sorted(windows[day])
            data=partitioned_intraday(source,day,names) if names else pd.DataFrame()
            if not data.empty and set(data.symbol)&known:raise ValueError('Un prix original serait remplacé')
            data.to_parquet(tape/f'{day}.parquet',index=False)
            atomic_json(root/'progress.json',dict(status='FREEZING_SUPPLEMENTAL_PRICES_READ_ONLY',completed=i+1,total=len(sessions),last_date=str(day),extra_symbols=len(extra)))
        atomic_json(inputs/'extra-price-receipts.json',source.receipts)
    source_files={str(Path(__file__)):digest(Path(__file__))}
    for folder,pattern in [('backtesting','winner*.py'),('risk_management','*.py'),('execution_engine','winner*.py'),('common','winner*.py')]:
        source_files.update({str(p):digest(p) for p in Path(folder).glob(pattern)})
    for name in ['backtesting/simulator.py','backtesting/per_symbol_selection.py','backtesting/production_risk_replay.py',
        'backtesting/adaptive_breaker.py','backtesting/regime_trailing.py','backtesting/frozen_market_registry.py',
        'common/config_loader.py','common/market_context.py','common/market_calendar.py','common/trading_costs.py','execution_engine/config.py']:
        source_files[name]=digest(Path(name))
    protocol=dict(start=base['start'],end=base['end'],initial_equity=4000.,reference=base['reference'],
        annual_models=annual,cases=CASES,sources=source_files,selection_sources=score_receipts,
        base_root=str(BASE),base_protocol_sha256=digest(BASE/'protocol.json'),baseline_selection_reproduction='PASS',
        baseline_candidates=len(reproduced),baseline_report=str(BASE/'continuous-uniform20pct/report.json'),
        extra_symbols=extra,original_prices_unchanged=True,supplement_scope='NEW_SYMBOLS_ONLY_NEXT_OPEN_THROUGH_OPEN11',
        missing_original_IHM_exports=missing,annual_reset=False,provider_calls=0,broker_calls=0,SQL_writes=0,
        prepared_at_utc=datetime.now(timezone.utc).isoformat(),strict_pit=False)
    atomic_json(root/'protocol.json',protocol)
    files={str(p.relative_to(inputs)):digest(p) for p in inputs.rglob('*') if p.is_file()}
    atomic_json(inputs/'manifest.json',dict(files=files,known_symbols=sorted(known),extra_symbols=extra,sessions=len(sessions)))
    atomic_json(root/'progress.json',dict(status='INPUTS_FROZEN',cases=list(CASES),baseline_selection_reproduction='PASS',extra_symbols=len(extra)))
    return protocol


class FrozenPrices:
    def __init__(self,root):self.root=Path(root)
    @lru_cache(maxsize=6)
    def day(self,day):
        frames=[pd.read_parquet(self.root/'inputs'/part/f'{day}.parquet') for part in ('base/intraday','extra-intraday')]
        frames=[f for f in frames if not f.empty]
        combined=pd.concat(frames,ignore_index=True) if frames else pd.DataFrame()
        if not combined.empty and combined.duplicated(['symbol','timestamp']).any():raise ValueError('Bougies figées ambiguës')
        return {s:g for s,g in combined.groupby('symbol')} if not combined.empty else {}
    def __call__(self,day,symbols):
        groups=self.day(day);parts=[groups[s] for s in sorted(symbols) if s in groups]
        return pd.concat(parts,ignore_index=True) if parts else pd.DataFrame()


def market_data(root):
    root=Path(root);inputs=root/'inputs'
    daily=pd.concat([pd.read_parquet(inputs/'base/daily.parquet'),pd.read_parquet(inputs/'extra-daily.parquet')],ignore_index=True)
    sectors=pd.concat([pd.read_parquet(inputs/'base/sectors.parquet'),pd.read_parquet(inputs/'extra-sectors.parquet')],ignore_index=True)
    if daily.duplicated(['date','symbol']).any() or sectors.duplicated('symbol').any():raise ValueError('Prix/secteurs dupliqués')
    pivots={k:daily.pivot(index='date',columns='symbol',values=k).astype(float) for k in ('open','high','low','close','volume')}
    actions=pd.concat([pd.read_parquet(inputs/'base/actions.parquet'),pd.read_parquet(inputs/'extra-actions.parquet')],ignore_index=True)
    return pivots,sectors,actions


def run_case(root,name):
    from backtesting.simulator import BacktestEngine,BacktestResult
    from backtesting.winner_campaign_replay import metrics
    from backtesting.isolation import ReadOnlyReplay
    from common.config_loader import replay_market_registry
    from unittest.mock import patch
    import requests
    root=Path(root);plan=read(root/'protocol.json');case=plan['cases'][name]
    folder=root/'cases'/name;folder.mkdir(parents=True,exist_ok=False);out=folder/'result';out.mkdir()
    for file,sha in plan['sources'].items():
        if digest(Path(file))!=sha:raise ValueError('Source de moteur modifiée : '+file)
    cfg=configuration(plan['reference'],case);pivots,sectors,actions=market_data(root)
    signals=pd.read_parquet(root/'inputs'/f'signals-{name}.parquet')
    reference=deepcopy(plan['reference']);reference['risk']=asdict(cfg.risk_config)
    reference['arguments'].update(top_n=math.ceil(1790*case['pool']),per_symbol_top_long=case['long_top_n'],
        per_symbol_min_long_probability=case['score'],per_symbol_min_long_auc=case['auc'],drawdown_controller=case['controller'])
    reference['per_symbol_selection']=settings(case,1790).snapshot()
    reference['drawdown_controller']={'enabled':case['controller']}
    local={**plan,'reference':reference,'profile':case,'case':name}
    atomic_json(folder/'protocol.json',local)
    atomic_json(out/'configuration.json',dict(profile=case,portfolio=asdict(cfg),source_protocol_sha256=digest(root/'protocol.json')))
    def no_http(*args,**kwargs):raise ValueError('HTTP interdit dans le replay figé')
    try:
        with ReadOnlyReplay(folder).install(),replay_market_registry(restore_registry(root)),patch.object(requests.Session,'request',no_http):
            def progress(done,total,day):
                state=dict(status='REPLAYING_CONTINUOUS',case=name,completed=done,total=total,last_date=str(day))
                atomic_json(folder/'progress.json',state);atomic_json(out/'progress.json',state)
            result=BacktestEngine(cfg).run(open_df=pivots['open'],close=pivots['close'],high=pivots['high'],low=pivots['low'],
                volume=pivots['volume'],signals_df=signals,sector_map=sectors.set_index('symbol').sector.to_dict(),
                intraday_source=FrozenPrices(root),winner_research_assumptions=True,winner_progress=progress,
                winner_corporate_actions=actions.to_dict('records'))
            result.equity_curve.rename('equity').to_csv(out/'equity-daily.csv');result.intraday_equity_curve.to_parquet(out/'equity-5m.parquet',index=False)
            result.closed_trades_df.to_csv(out/'trades.csv',index=False);result.trade_events_df.to_csv(out/'events.csv',index=False)
            result.drawdown_breaker_df.to_csv(out/'risk-5m.csv',index=False)
            report=metrics(result,4000.);annual=[];opening=4000.
            for year in sorted(result.equity_curve.index.year.unique()):
                curve=result.equity_curve[result.equity_curve.index.year==year]
                trades=result.closed_trades_df
                closed=trades[pd.to_datetime(trades.exit_date,utc=True).dt.year.eq(year)] if len(trades) else trades
                marks=result.intraday_equity_curve
                part=BacktestResult(equity_curve=curve,closed_trades_df=closed,
                    intraday_equity_curve=marks[pd.to_datetime(marks.timestamp,utc=True).dt.year.eq(year)],
                    tracker_snapshot={'winner_replay':dict(status=report['status'],full_live_parity=False)})
                row=metrics(part,opening);row.update(year=int(year),model=plan['annual_models'][str(year)]['batch_id'])
                annual.append(row);opening=float(curve.iloc[-1])
            pd.DataFrame(annual).to_csv(out/'annual-summary.csv',index=False)
            report.update(case=name,profile=case,annual_models=plan['annual_models'],annual_reset=False,
                selected_signals=len(signals),provider_calls=0,broker_calls=0,SQL_writes=0,strict_pit=False,
                finished_at_utc=datetime.now(timezone.utc).isoformat())
            atomic_json(out/'report.json',report)
            atomic_json(out/'progress.json',dict(status=report['status'],completed=len(result.equity_curve),total=len(result.equity_curve)))
            atomic_json(folder/'progress.json',dict(status='COMPLETED_EXPLORATORY'))
        return dict(case=name,folder=str(folder),report={k:report[k] for k in ('final_equity','return_pct','max_drawdown_pct','closed_lot_trades','win_pct','average_gross_capital')})
    except Exception as exc:
        atomic_json(folder/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)))
        raise


def validate_2025(root):
    from scripts.research import us_winner_ui_grid_20261107 as grid
    from backtesting.simulator import BacktestEngine
    from backtesting.winner_campaign_replay import metrics
    from backtesting.isolation import ReadOnlyReplay
    from common.config_loader import replay_market_registry
    plan=read(root/'protocol.json');grid.verify_inputs(GRID);grid.initialize_worker(GRID)
    frame=pd.read_parquet(root/'inputs/signals-Q051_060.parquet')
    frame=frame[frame.entry_year.eq(2025)];expected=read(Q051/'report.json')
    if len(frame)!=expected['selected_signals']:raise ValueError('Sélection 2025 Q051 différente')
    cfg=configuration(plan['reference'],CASES['Q051_060']);cfg.start_date=date(2025,1,1);cfg.end_date=date(2025,12,31)
    saved=read(Q051/'configuration.json')
    if asdict(cfg.risk_config)!=saved['risk'] or asdict(cfg.exec_config.winner_pyramiding)!=saved['policy']:
        raise ValueError('Paramètres différents du Q051 historique')
    with ReadOnlyReplay(root).install(),replay_market_registry(restore_registry(root)):
        def progress(done,total,day):atomic_json(root/'progress.json',dict(status='VALIDATING_Q051_2025',completed=done,total=total,last_date=str(day)))
        result=BacktestEngine(cfg).run(open_df=grid.DATA['pivots']['open'],close=grid.DATA['pivots']['close'],high=grid.DATA['pivots']['high'],
            low=grid.DATA['pivots']['low'],volume=grid.DATA['pivots']['volume'],signals_df=frame,sector_map=grid.DATA['sectors'],
            intraday_source=grid.DATA['source'],winner_research_assumptions=True,winner_progress=progress,winner_corporate_actions=grid.DATA['actions'])
        report=metrics(result,4000.)
        for k in ('final_equity','return_pct','max_drawdown_pct','average_gross_capital','maximum_gross_capital','costs','margin_interest','closed_lot_trades','winners','losers'):
            if not np.isclose(report[k],expected[k],rtol=1e-10,atol=1e-6):raise ValueError('Q051 2025 non reproduit : '+k)
        atomic_json(root/'validation-Q051-2025.json',dict(status='PASS',return_pct=report['return_pct'],max_drawdown_pct=report['max_drawdown_pct'],
            original_report_sha256=digest(Q051/'report.json')))


def run(root,workers):
    prepare(root);validate_2025(root)
    manifest=read(root/'inputs/manifest.json')
    for name,sha in manifest['files'].items():
        if digest(root/'inputs'/name)!=sha:raise ValueError('Entrée figée modifiée : '+name)
    results=[];failures=[]
    with ProcessPoolExecutor(max_workers=workers,mp_context=get_context('spawn')) as pool:
        futures={pool.submit(run_case,str(root),name):name for name in CASES}
        atomic_json(root/'progress.json',dict(status='REPLAYING_THREE_CASES',cases=list(CASES),completed=0,total=3))
        for future in as_completed(futures):
            name=futures[future]
            try:
                value=future.result()
                from ihm.services.backtesting_import import import_continuous_winner
                score='0,60' if name.endswith('060') else '0,50'
                record=import_continuous_winner(value['folder'],run_id=f'20261108_continu_{name}_v1',
                    label=f"Continu 2021–2026 — {CASES[name]['profile']} score > {score} / AUC ≥ {score}",result_subdir='result')
                value['ihm_run_id']=record['run_id'];results.append(value)
            except Exception as exc:failures.append(dict(case=name,error_type=type(exc).__name__,error=str(exc)))
            atomic_json(root/'progress.json',dict(status='REPLAYING_THREE_CASES',completed=len(results)+len(failures),total=3,results=results,failures=failures))
    baseline=read(BASE/'continuous-uniform20pct/report.json')
    rows=[dict(case='Q088_060_REFERENCE',**{k:baseline[k] for k in ('final_equity','return_pct','max_drawdown_pct','closed_lot_trades','win_pct','average_gross_capital')})]
    rows += [dict(case=r['case'],**r['report']) for r in results]
    pd.DataFrame(rows).to_csv(root/'comparison.csv',index=False)
    report=dict(status='COMPLETED_EXPLORATORY' if not failures else 'INCOMPLETE_CASES',results=results,failures=failures,
        provider_calls=0,broker_calls=0,SQL_writes=0)
    atomic_json(root/'report.json',report);atomic_json(root/'progress.json',report)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output-dir',type=Path,default=ROOT);parser.add_argument('--workers',type=int,default=3)
    args=parser.parse_args()
    if not 1<=args.workers<=3:raise ValueError('1 à 3 workers')
    try:result=run(args.output_dir,args.workers)
    except Exception as exc:
        if args.output_dir.exists():atomic_json(args.output_dir/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)))
        raise
    print(json.dumps(result,ensure_ascii=False))
