"""Four H20 annual-model continuous replays; await existing prediction jobs first."""
import argparse
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor,as_completed
from copy import deepcopy
from dataclasses import asdict
from datetime import date,datetime,timedelta,timezone
import json
from multiprocessing import get_context
from pathlib import Path
import sys
import time

import numpy as np
import pandas as pd
import psutil
from sqlalchemy import bindparam,text

from scripts.research.us_concentrated_historical_tapes import atomic_json,digest
from scripts.research.us_winner_continuous_annual_models_20261108 import annual_signal_days,read
from scripts.research.us_winner_continuous_registry_recovery_20261108 import restore_registry
from scripts.research import us_winner_continuous_q051_q088_20261108 as shared

ROOT=Path('artifacts/research/us_winner_continuous_h20/20261108-v1')
PRICE_BASE=Path('artifacts/research/us_winner_continuous_q051_q088/20261108-v2')
MODEL_IDS={2021:'model-factory-20261108113730-607284',2022:'model-factory-20261108113738-f4ed09',
    2023:'model-factory-20261108113750-fc2601',2024:'model-factory-20261108130316-b54c49',
    2025:'model-factory-20261108130325-addb06',2026:'model-factory-20261108130333-7a5385'}
CASES={
    'H20_Q088_060':dict(profile='Q088',pool=.20,long_top_n=10,score=.60,auc=.60,controller=True,gross=2.),
    'H20_Q088_050':dict(profile='Q088',pool=.20,long_top_n=10,score=.50,auc=.50,controller=True,gross=2.),
    'H20_Q051_060':dict(profile='Q051',pool=.10,long_top_n=5,score=.60,auc=.60,controller=False,gross=1.),
    'H20_Q051_050':dict(profile='Q051',pool=.10,long_top_n=5,score=.50,auc=.50,controller=False,gross=1.),
}
ANNUAL_REFERENCE=Path('artifacts/ihm_backtesting_runs/run/20261108_163907_bc5802de/artifacts')


def prediction_processes():
    result=defaultdict(list)
    for process in psutil.process_iter(['pid','cmdline']):
        try:
            cmd=process.info['cmdline'] or []
            if '--mode' not in cmd or 'predict' not in cmd or '--batch-id' not in cmd:continue
            batch=cmd[cmd.index('--batch-id')+1]
            if batch in MODEL_IDS.values():result[batch].append(process.pid)
        except (psutil.NoSuchProcess,psutil.AccessDenied,IndexError):pass
    return dict(result)


def coverage(engine,batch,days):
    counts=[]
    with engine.connect() as conn,conn.begin():
        conn.execute(text('SET TRANSACTION READ ONLY'))
        for table in ('oracle_extreme_predictions','oracle_path_directional_predictions'):
            frame=pd.read_sql(text(f'SELECT prediction_date,COUNT(*) n FROM {table} WHERE batch_id=:batch '
                'AND prediction_date BETWEEN :start AND :end GROUP BY prediction_date'),conn,
                params=dict(batch=batch,start=days[0],end=days[-1]))
            counts.append({pd.Timestamp(r.prediction_date).date():int(r.n) for r in frame.itertuples()})
    missing=[str(d) for d in days if min(c.get(d,0) for c in counts)<1665]
    return dict(complete=not missing,required_days=len(days),qualified_days=len(days)-len(missing),
        oracle_days=len(counts[0]),directional_days=len(counts[1]),first_missing=missing[:4])


def initialize(root):
    from common.config_loader import replay_market_registry
    from common.market_calendar import get_market_calendar
    if root.exists():
        request=read(root/'request.json')
        if (read(root/'progress.json').get('status')!='WAITING_FOR_H20_PREDICTIONS'
                or (root/'protocol.json').exists() or request['cases']!=CASES
                or {int(y):m['batch_id'] for y,m in request['annual_models'].items()}!=MODEL_IDS):
            raise ValueError('Reprise autorisée seulement avant le gel des scores, avec la même demande')
        freeze_annual_reference(root)
        return request['annual_models']
    root.mkdir(parents=True,exist_ok=False)
    inputs=root/'inputs';inputs.mkdir()
    shared.copy_owned(PRICE_BASE/'inputs/market-registry.json',inputs/'market-registry.json')
    models={}
    with replay_market_registry(restore_registry(root)):
        calendar=get_market_calendar('US_EQ',allow_us_weekday_fallback=False)
        for year,batch in MODEL_IDS.items():
            folder=Path('artifacts/models')/batch/'oracle_path'
            p=read(folder/'protocol.json');r=read(folder/'report.json')
            if (p['horizon']!=20 or p['directional_contract']['horizon_sessions']!=20
                    or p['directional_contract']['stop_loss_pct']!=.05 or r['status']!='completed'
                    or len(p['universe'])!=1790
                    or pd.Timestamp(p['training_config']['data']['training_end_date'])>=pd.Timestamp(year,1,1)):
                raise ValueError('Modèle annuel H20 non qualifié : '+batch)
            actual,days=annual_signal_days(calendar,year)
            models[str(year)]=dict(batch_id=batch,universe_size=len(p['universe']),
                training_start=p['training_config']['data']['training_start_date'],
                training_end=p['training_config']['data']['training_end_date'],horizon=20,
                first_signal=str(days[0]),last_signal=str(days[-1]),
                protocol_sha256=digest(folder/'protocol.json'),signal_days=[str(d) for d in days])
    atomic_json(root/'request.json',dict(start='2021-01-01',end='2026-10-01',initial_equity=4000.,
        annual_reset=False,horizon=20,exit='OPEN21',cases=CASES,annual_models=models,
        requested_at_utc=datetime.now(timezone.utc).isoformat(),price_base=str(PRICE_BASE),
        prediction_preparation='Existing CLI jobs only; no second predictor for an active batch',
        broker_orders=False,training=False))
    freeze_annual_reference(root)
    return models


def freeze_annual_reference(root):
    folder=root/'reference-H20-2021';folder.mkdir(exist_ok=True)
    proof=folder/'manifest.json'
    if proof.exists():
        for name,sha in read(proof)['files'].items():
            if digest(folder/name)!=sha:raise ValueError('Témoin H20 archivé modifié')
        return
    for name in ('protocol.json','report.json','signals.csv'):
        shared.copy_owned(ANNUAL_REFERENCE/name,folder/name)
    atomic_json(proof,dict(origin=str(ANNUAL_REFERENCE),files={name:digest(folder/name)
        for name in ('protocol.json','report.json','signals.csv')}))


def wait_predictions(root,models,engine):
    states={};last_query=0.;absent=defaultdict(int);began=time.monotonic()
    while True:
        active=prediction_processes()
        if time.monotonic()-last_query>60 or not states or not active:
            for year,model in models.items():
                if year not in states or not states[year]['complete']:
                    days=[date.fromisoformat(d) for d in model['signal_days']]
                    states[year]=coverage(engine,model['batch_id'],days)
            last_query=time.monotonic()
        for year,model in models.items():
            running=active.get(model['batch_id'],[])
            absent[year]=0 if states[year]['complete'] or running else absent[year]+1
            if absent[year]>=3:
                raise ValueError(f'Prédictions H20 {year} incomplètes et aucun processus actif : {states[year]}')
            states[year]['active_pids']=running
        atomic_json(root/'progress.json',dict(status='WAITING_FOR_H20_PREDICTIONS',years=states,
            qualified_years=sum(s['complete'] for s in states.values()),total_years=6,
            updated_at_utc=datetime.now(timezone.utc).isoformat()))
        if all(s['complete'] for s in states.values()) and not active:return
        if time.monotonic()-began>24*3600:raise TimeoutError('Prédictions non terminées après24h ; aucun replay publié')
        time.sleep(10)


def prepare(root,models,engine):
    from common.config_loader import replay_market_registry
    from common.market_calendar import get_market_calendar
    from modelFactory.oracle_path.predict import load_contract
    from modelFactory.oracle_path.directional import load_manifest
    from backtesting.per_symbol_selection import attach_calibration_auc,select_per_symbol
    from backtesting.winner_campaign_replay import validate_scores,SqlIntradaySource
    from backtesting.winner_data import daily_bars
    from backtesting.isolation import ReadOnlyReplay
    inputs=root/'inputs';old=PRICE_BASE/'inputs';pm=read(old/'manifest.json')
    for name,sha in pm['files'].items():
        if digest(old/name)!=sha:raise ValueError('Archive de prix source modifiée : '+name)
    # Keep the original 300-symbol tape and the first set of supplemental prices.
    for path in (old/'base').rglob('*'):
        if path.is_file():shared.copy_owned(path,inputs/'base'/path.relative_to(old/'base'))
    reference=deepcopy(read(PRICE_BASE/'protocol.json')['reference'])
    reference['winner_policy']['horizon_sessions']=20
    reference['arguments']['oracle_batch_id']=MODEL_IDS[2021]
    reference['arguments']['policy_overrides_json']=json.dumps(dict(horizon_sessions=20,confirmation_bars=0,entry_valid_sessions=1,market_data_delay_seconds=0))
    selections={name:[] for name in CASES};annual={};receipts={};names=set()
    with replay_market_registry(restore_registry(root)):
        calendar=get_market_calendar('US_EQ',allow_us_weekday_fallback=False)
        sessions=[s.session_date for s in calendar.sessions(date(2021,1,1),date(2026,10,1)) if s.is_open]
        for year,entry in models.items():
            atomic_json(root/'progress.json',dict(status='QUALIFYING_H20_SCORES',year=int(year),completed=int(year)-2021,total=6))
            model,p,_,folds=load_contract('artifacts/models',entry['batch_id'])
            manifest,mhash=load_manifest(model)
            if digest(model/'protocol.json')!=entry['protocol_sha256']:raise ValueError('Contrat annuel modifié pendant le calcul')
            days=[date.fromisoformat(d) for d in entry['signal_days']]
            with ReadOnlyReplay(root).install():
                frame=shared.recover_2026(engine,entry['batch_id'],days[0],days[-1],mhash)
            frame=shared.normalize_ranking_dates(frame)
            if set(frame.date.dt.date)!=set(days) or not set(frame.symbol).issubset(p['universe']):
                raise ValueError('Périmètre SQL H20 incompatible')
            validate_scores(frame.rename(columns={'date':'trade_date'}),profile_hash=digest(model/'feature_profile.json'),
                folds=folds,expected_days=days,top_n=358,horizon=20,universe_size=len(p['universe']),min_coverage=.93)
            shared.verify_branches(frame,manifest)
            frame=attach_calibration_auc(frame,model)
            path=inputs/'rankings'/f'{year}.parquet';path.parent.mkdir(exist_ok=True);frame.to_parquet(path,index=False)
            counts={}
            for name,case in CASES.items():
                selected=select_per_symbol(frame,shared.settings(case,len(p['universe'])))
                selected=selected[selected.selected].rename(columns={'date':'trade_date'}).copy()
                selected['rank']=selected['rank'].astype(int);selected['oracle_amplitude_rank']=selected.oracle_rank
                selected['oracle_batch_id']=entry['batch_id'];selected['entry_year']=int(year)
                selections[name].append(selected);names.update(selected.symbol)
                counts[name]=dict(signals=len(selected),symbols=int(selected.symbol.nunique()),
                    selection=shared.settings(case,len(p['universe'])).snapshot())
            annual[year]={**entry,'selection':counts,'model_manifest_sha256':mhash}
            receipts[year]=dict(ranking_sha256=digest(path),rows=len(frame),
                feature_profile_sha256=digest(model/'feature_profile.json'),manifest_sha256=mhash)
    frames={name:pd.concat(parts,ignore_index=True).sort_values(['trade_date','rank','symbol']) for name,parts in selections.items()}
    for name,frame in frames.items():frame.to_parquet(inputs/f'signals-{name}.parquet',index=False)
    base_names=set(pm['known_symbols'])
    old_extra_daily=pd.read_parquet(old/'extra-daily.parquet')
    existing_daily=set(pd.read_parquet(old/'base/daily.parquet',columns=['symbol']).symbol)|set(old_extra_daily.symbol)
    extra=sorted(names-existing_daily)
    known_pairs=defaultdict(set)
    for receipt in read(old/'extra-price-receipts.json'):
        known_pairs[date.fromisoformat(str(receipt['day'])[:10])].update(receipt['symbols'])
    windows=shared.supplemental_windows(frames.values(),sessions,base_names,horizon=20)
    first=pd.read_parquet(old/'base/daily.parquet',columns=['date']).date.min().date()
    atomic_json(root/'progress.json',dict(status='FREEZING_H20_PRICES_READ_ONLY',completed=0,total=len(sessions),new_symbols=len(extra)))
    with ReadOnlyReplay(root).install(),replay_market_registry(restore_registry(root)),engine.connect() as conn,conn.begin():
        conn.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
        pieces=[old_extra_daily]+[daily_bars(conn,extra[i:i+100],first,date(2026,10,1)) for i in range(0,len(extra),100)]
        pd.concat(pieces,ignore_index=True).to_parquet(inputs/'extra-daily.parquet',index=False)
        sectors=pd.read_parquet(old/'extra-sectors.parquet');actions=pd.read_parquet(old/'extra-actions.parquet')
        if extra:
            new_sectors=pd.read_sql(text('SELECT symbol,sector FROM stock_metadata WHERE symbol IN :symbols')
                .bindparams(bindparam('symbols',expanding=True)),conn,params={'symbols':extra})
            new_actions=pd.read_sql(text('SELECT symbol,ca_type,ex_date,payable_date,amount_per_share,currency FROM corporate_actions_events '
                'WHERE symbol IN :symbols AND ex_date BETWEEN :start AND :end').bindparams(bindparam('symbols',expanding=True)),
                conn,params=dict(symbols=extra,start=date(2021,1,1),end=date(2026,10,1)))
            sectors=pd.concat([sectors,new_sectors],ignore_index=True);actions=pd.concat([actions,new_actions],ignore_index=True)
        sectors.to_parquet(inputs/'extra-sectors.parquet',index=False);actions.to_parquet(inputs/'extra-actions.parquet',index=False)
        source=SqlIntradaySource(conn,discard_unqualified=True,allow_daily_fallback=True)
        tape=inputs/'extra-intraday';tape.mkdir()
        from scripts.research.us_winner_ui_grid_20261107 import partitioned_intraday
        for i,day in enumerate(sessions):
            cached=pd.read_parquet(old/'extra-intraday'/f'{day}.parquet')
            unknown=sorted(windows[day]-known_pairs[day])
            fresh=partitioned_intraday(source,day,unknown) if unknown else pd.DataFrame()
            parts=[f for f in (cached,fresh) if not f.empty]
            merged=pd.concat(parts,ignore_index=True) if parts else pd.DataFrame()
            if not merged.empty and merged.duplicated(['symbol','timestamp']).any():raise ValueError('Prix H20 supplémentaires dupliqués')
            merged.to_parquet(tape/f'{day}.parquet',index=False)
            atomic_json(root/'progress.json',dict(status='FREEZING_H20_PRICES_READ_ONLY',completed=i+1,total=len(sessions),last_date=str(day),new_symbols=len(extra)))
        atomic_json(inputs/'h20-price-receipts.json',source.receipts)
    # Seal every dependency used by the reused, unchanged native replay worker.
    sources={str(Path(__file__)):digest(Path(__file__)),str(Path(shared.__file__)):digest(Path(shared.__file__))}
    previous=read(PRICE_BASE/'protocol.json')
    for filename in previous['sources']:
        if Path(filename).is_file():sources[filename]=digest(Path(filename))
    for filename in ['common/config_loader.py','common/market_context.py','common/market_calendar.py',
        'backtesting/frozen_market_registry.py','ihm/services/backtesting_import.py']:
        sources[filename]=digest(Path(filename))
    plan=dict(start='2021-01-01',end='2026-10-01',initial_equity=4000.,horizon=20,annual_reset=False,
        cases=CASES,reference=reference,annual_models=annual,sources=sources,selection_sources=receipts,
        price_base=str(PRICE_BASE),base_manifest_sha256=digest(old/'manifest.json'),
        old_daily_and_intraday_prices_preserved=True,new_daily_symbols=extra,
        supplemental_scope='MISSING_SYMBOL_SESSION_PAIRS_ONLY_J1_THROUGH_OPEN21',
        prediction_SQL_writes=True,replay_SQL_writes=False,provider_calls=0,broker_calls=0,strict_pit=False,
        prepared_at_utc=datetime.now(timezone.utc).isoformat(),
        replay_command=[sys.executable,'-m','scripts.research.us_winner_continuous_h20_20261108','--output-dir',str(root)])
    atomic_json(root/'protocol.json',plan)
    atomic_json(inputs/'manifest.json',dict(files={str(f.relative_to(inputs)):digest(f) for f in inputs.rglob('*') if f.is_file()},sessions=len(sessions)))
    atomic_json(root/'progress.json',dict(status='INPUTS_FROZEN',cases=list(CASES)))


def validate_annual_reference(root):
    from backtesting.simulator import BacktestEngine
    from backtesting.winner_campaign_replay import metrics
    from backtesting.isolation import ReadOnlyReplay
    from common.config_loader import replay_market_registry
    from unittest.mock import patch
    import requests
    freeze_annual_reference(root)
    reference=root/'reference-H20-2021'
    plan=read(root/'protocol.json');prior=read(reference/'protocol.json')
    case=CASES['H20_Q088_060'];cfg=shared.configuration(plan['reference'],case)
    cfg.start_date=date(2021,1,1);cfg.end_date=date(2021,12,31)
    if asdict(cfg.risk_config)!=prior['risk'] or asdict(cfg.exec_config.winner_pyramiding)!=prior['winner_policy']:
        raise ValueError('Paramètres de la référence H20 annuelle différents')
    signals=pd.read_parquet(root/'inputs/signals-H20_Q088_060.parquet')
    signals=signals[signals.entry_year.eq(2021)]
    archived=pd.read_csv(reference/'signals.csv',parse_dates=['trade_date'])
    if set(zip(signals.trade_date,signals.symbol))!=set(zip(archived.trade_date,archived.symbol)):
        raise ValueError('Sélection H20 2021 originale non reproduite')
    pivots,sectors,actions=shared.market_data(root)
    def no_http(*args,**kwargs):raise ValueError('HTTP interdit dans la validation H20')
    with ReadOnlyReplay(root).install(),replay_market_registry(restore_registry(root)),patch.object(requests.Session,'request',no_http):
        def progress(done,total,day):atomic_json(root/'progress.json',dict(status='VALIDATING_H20_2021',completed=done,total=total,last_date=str(day)))
        result=BacktestEngine(cfg).run(open_df=pivots['open'],close=pivots['close'],high=pivots['high'],low=pivots['low'],
            volume=pivots['volume'],signals_df=signals,sector_map=sectors.set_index('symbol').sector.to_dict(),
            intraday_source=shared.FrozenPrices(root),winner_research_assumptions=True,winner_progress=progress,
            winner_corporate_actions=actions.to_dict('records'))
        report=metrics(result,4000.);old=read(reference/'report.json')
        for key in ('final_equity','return_pct','max_drawdown_pct','closed_lot_trades','winners','losers','costs','margin_interest','average_gross_capital'):
            if not np.isclose(report[key],old[key],rtol=1e-10,atol=1e-6):raise ValueError('Référence H20 2021 différente : '+key)
        atomic_json(root/'validation-H20-2021.json',dict(status='PASS',return_pct=report['return_pct'],max_drawdown_pct=report['max_drawdown_pct'],
            original_report_sha256=digest(reference/'report.json')))


def run(root,workers):
    from database.connection import get_sqlalchemy_engine
    models=initialize(root);engine=get_sqlalchemy_engine(db_name='alpha_trade')
    wait_predictions(root,models,engine);prepare(root,models,engine);validate_annual_reference(root)
    for name,sha in read(root/'inputs/manifest.json')['files'].items():
        if digest(root/'inputs'/name)!=sha:raise ValueError('Entrée figée modifiée : '+name)
    results=[];failures=[]
    with ProcessPoolExecutor(max_workers=workers,mp_context=get_context('spawn')) as pool:
        futures={pool.submit(shared.run_case,str(root),name):name for name in CASES}
        atomic_json(root/'progress.json',dict(status='REPLAYING_FOUR_H20_CASES',cases=list(CASES),completed=0,total=4))
        for future in as_completed(futures):
            name=futures[future]
            try:
                value=future.result()
                from ihm.services.backtesting_import import import_continuous_winner
                score=f"{CASES[name]['score']:.2f}".replace('.',',')
                record=import_continuous_winner(value['folder'],run_id=f'20261108_continu_{name}_v1',
                    label=f"Continu H20 2021–2026 — {CASES[name]['profile']} score > {score} / AUC ≥ {score} — open21",result_subdir='result')
                value['ihm_run_id']=record['run_id'];results.append(value)
            except Exception as exc:failures.append(dict(case=name,error_type=type(exc).__name__,error=str(exc)))
            atomic_json(root/'progress.json',dict(status='REPLAYING_FOUR_H20_CASES',completed=len(results)+len(failures),total=4,results=results,failures=failures))
    pd.DataFrame([dict(case=r['case'],**r['report']) for r in results]).to_csv(root/'comparison.csv',index=False)
    report=dict(status='COMPLETED_EXPLORATORY' if not failures else 'INCOMPLETE_CASES',results=results,failures=failures,
        provider_calls=0,broker_calls=0,replay_SQL_writes=False,prediction_SQL_writes=True)
    atomic_json(root/'report.json',report);atomic_json(root/'progress.json',report)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output-dir',type=Path,default=ROOT);parser.add_argument('--workers',type=int,default=4)
    args=parser.parse_args()
    if not 1<=args.workers<=4:raise ValueError('1 à 4 workers')
    try:result=run(args.output_dir,args.workers)
    except Exception as exc:
        if args.output_dir.exists():atomic_json(args.output_dir/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)))
        raise
    print(json.dumps(result,ensure_ascii=False))
