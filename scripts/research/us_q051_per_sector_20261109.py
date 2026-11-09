"""Matched Q051 sector LONG experiment. Original annual Oracles stay immutable.

Research-only models and signals. No serving registry, production SQL or orders.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor,as_completed
from copy import deepcopy
from dataclasses import asdict
from datetime import date,datetime,timezone
import json
from multiprocessing import get_context
from pathlib import Path
import sys
import time
from unittest.mock import patch

import numpy as np
import pandas as pd
import requests
from sqlalchemy import text

from scripts.research import us_winner_continuous_q051_q088_20261108 as shared
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest
from scripts.research.us_winner_q051_risk_budget_20261109 import daily_metrics

BASE=shared.ROOT
EXT=Path('artifacts/research/us_winner_vol20_extensions/20261109-v1')
ROOT=Path('artifacts/research/us_q051_per_sector/20261109-v3')
YEARS=tuple(range(2021,2026))
PROFILES=('Q051_PER_SECTOR','VOL20_REGIME_PER_SECTOR')
GICS=('Energy','Materials','Industrials','Consumer Discretionary','Consumer Staples',
      'Health Care','Financials','Real Estate','Information Technology','Communication Services','Utilities')


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def merge_benchmark(left,right):
    """Only extend dates; reject any disagreement in overlapping prices."""
    overlap=left.merge(right,on='date',suffixes=('_left','_right'),validate='one_to_one')
    for column in ['open','high','low','close','adj_close','volume']:
        if not np.allclose(overlap[column+'_left'],overlap[column+'_right'],rtol=0,atol=1e-12,equal_nan=True):
            raise ValueError('Benchmark archives disagree: '+column)
    return pd.concat([left,right],ignore_index=True).drop_duplicates('date',keep='first').sort_values('date').reset_index(drop=True)


def sector_name(raw):
    from modelFactory.cross_sectional import _map_to_gics_sector
    if raw is None or pd.isna(raw):return None
    normalized=''.join(c for c in str(raw).lower() if c.isalnum())
    explicit={''.join(c for c in name.lower() if c.isalnum()):name for name in GICS}
    explicit.update(technology='Information Technology',basicmaterials='Materials',
        consumercyclical='Consumer Discretionary',consumerdefensive='Consumer Staples',
        financialservices='Financials',healthcare='Health Care',transportation='Industrials')
    mapped=explicit.get(normalized) or _map_to_gics_sector(str(raw))
    return None if mapped=='Other' else mapped


def prepare(root):
    from scripts.research.us_consensus_observed_revision_pilot import connect_readonly
    from scripts.research.us_collected_directional_refresh_20261105 import query
    from modelFactory.oracle_path.predict import load_contract
    root.mkdir(parents=True,exist_ok=False);plan=read(BASE/'protocol.json')
    atomic_json(root/'progress.json',dict(status='FREEZING_PROTOCOL_AND_SECTORS'))
    models={};universe=None;sources={str(Path(__file__)):digest(Path(__file__))}
    for year in YEARS:
        batch=plan['annual_models'][str(year)]['batch_id'];folder,p,_,folds=load_contract('artifacts/models',batch)
        if p['horizon']!=10 or pd.Timestamp(p['training_config']['data']['training_end_date'])>=pd.Timestamp(year,1,1):
            raise ValueError('Annual Oracle horizon/dates incompatible')
        if universe is None:universe=sorted(p['universe'])
        if universe!=sorted(p['universe']):raise ValueError('Annual universe changed')
        models[str(year)]=dict(batch_id=batch,root=str(folder),
            training_start=p['training_config']['data']['training_start_date'],training_end=p['training_config']['data']['training_end_date'],
            benchmark_file=str(folder/'directional/benchmark.parquet'),
            oracle_protocol_sha256=digest(folder/'protocol.json'),features_sha256=digest(folder/'feature_profile.json'),
            folds={k:dict(model_sha256=v['model_sha256'],metrics=v['metrics']) for k,v in folds.items()})
        for name in ['protocol.json','report.json','feature_profile.json','directional/manifest.json','directional/benchmark.parquet']:
            if name=='directional/benchmark.parquet' and not (folder/name).exists():continue
            sources[str(folder/name)]=digest(folder/name)
        for fold in folds.values():sources[str(fold['model_file'])]=digest(fold['model_file'])
        path=BASE/'inputs/rankings'/f'{year}.parquet'
        frozen_files={k.replace('\\','/'):v for k,v in read(BASE/'inputs/manifest.json')['files'].items()}
        if digest(path)!=frozen_files[f'rankings/{year}.parquet']:
            raise ValueError('Frozen ranking modified')
        sources[str(path)]=digest(path)
    reconstructed=[]
    for year in YEARS:
        if Path(models[str(year)]['benchmark_file']).exists():continue
        # The older November-6 bundle did not persist benchmark bars. Two
        # independent stored benchmark windows cover its full training span;
        # their 1,258 overlapping OHLC/volume rows must agree exactly.
        left=Path(models['2024']['benchmark_file'])
        right=Path('artifacts/models/model-factory-20261107222627-db80b0/oracle_path/directional/benchmark.parquet')
        frame=merge_benchmark(pd.read_parquet(left),pd.read_parquet(right))
        lo,hi=pd.Timestamp(models[str(year)]['training_start']),pd.Timestamp(models[str(year)]['training_end'])
        frame=frame[frame.date.between(lo,hi)].copy()
        target=root/f'reconstructed-benchmark-{year}.parquet';frame.to_parquet(target,index=False)
        models[str(year)]['benchmark_file']=str(target)
        for file in [left,right,target]:sources[str(file)]=digest(file)
        reconstructed.append(dict(year=year,file=str(target),source_files=[str(left),str(right)],
            overlap_policy='identical OHLC/volume, whole-row union; no fabricated values',rows=len(frame)))
    for file in ['modelFactory/oracle_path/directional.py','modelFactory/oracle_path/directional_metrics.py',
        'modelFactory/oracle_path/named_prediction.py','modelFactory/cross_sectional.py',
        'backtesting/per_symbol_selection.py','backtesting/simulator.py','backtesting/winner_intraday.py',
        'backtesting/winner_portfolio_budget.py','config/data_quality/security_discontinuities.json',
        'modelFactory/features.py','modelFactory/factor_features.py','modelFactory/oracle/security_continuity.py',
        'common/daily_bar_sources.py','common/market_calendar.py',
        'scripts/research/us_winner_continuous_q051_q088_20261108.py',
        'scripts/research/us_winner_ui_grid_20261107.py']:
        sources[file]=digest(Path(file))
    engine,conn=connect_readonly()
    try:
        rows=query(conn,'SELECT symbol,sector FROM stock_metadata WHERE symbol IN :symbols',symbols=universe)
        conn.rollback()
    finally:conn.close();engine.dispose()
    sectors=pd.DataFrame(rows)
    if sectors.symbol.duplicated().any():raise ValueError('Duplicate metadata sector')
    sectors['gics_sector']=sectors.sector.map(sector_name);sectors.to_csv(root/'sectors.csv',index=False)
    atomic_json(root/'request.json',dict(start='2021-01-01',end='2025-12-31',initial_equity=4000.,annual_reset=False,
        years=YEARS,annual_models=models,universe=universe,profiles=PROFILES,
        oracle_training='REUSE_EXACT_VERIFIED_ANNUAL_Q051_WEIGHTS_NO_RETRAINING_OF_AMPLITUDE',
        sector_training='GENUINE_POOLED_LONG_CLASSIFIER_PER_GICS_NOT_GLOBAL_RANK_SYNTHESIS',
        target='LONG profitability after SL5 or open11, fee 8bps/leg, same directional labels as per-symbol',
        features='same 24 directional inputs, no symbol identifier, sector chosen by frozen metadata',
        model='LightGBM 120 trees, depth 3, num_leaves 7, min_child_samples 60, seed 42; median imputer, Platt calibration',
        fit='before Jan1 previous calendar year, labels strictly available before that boundary',
        calibration='previous calendar year, labels strictly available before test year',
        boundary='Each annual Oracle bundle trains test-year and previous-year directional vintages, mirroring Q051 for Dec31 signal',
        auc_gate='Per-title AUC of the sector model on previous-year calibration; >=126 rows, >=15 per class; >=0.50. Not test-year AUC',
        selection='TOP10% Oracle -> TOP5 LONG -> probability >.50 and per-title calibration AUC >=.50; no refill',
        grouping='Current GICS metadata frozen, not certified historical sector membership; unknown excluded without fallback',
        input_price_policy='reuse existing frozen bars and historical tapes; no provider download or SQL writes',
        sources=sources,benchmark_reconstruction=reconstructed,
        sector_snapshot_sha256=digest(root/'sectors.csv'),created_at_utc=datetime.now(timezone.utc).isoformat(),
        SQL_writes=0,provider_calls=0,orders=0,production_changes=False))
    atomic_json(root/'progress.json',dict(status='PROTOCOL_READY',mapped_symbols=int(sectors.gics_sector.notna().sum()),
        sectors=sectors.gics_sector.value_counts().to_dict(),unknown=sectors.loc[sectors.gics_sector.isna(),'symbol'].tolist()))
    print(json.dumps(read(root/'progress.json'),ensure_ascii=False))


def model_predictions(weights,frame):
    from modelFactory.oracle_path.directional_metrics import predict
    return predict(weights,frame)


def train_sector(panel,year,sector,folder):
    import joblib
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import make_pipeline
    from sklearn.linear_model import LogisticRegression
    from lightgbm import LGBMClassifier
    from modelFactory.oracle_path.directional import INPUTS,split
    from modelFactory.oracle_path.named_prediction import predict_proba
    from modelFactory.oracle_path.directional_metrics import classification_metrics
    fit,cal=split(panel,year,'long')
    if (len(fit)<756 or len(cal)<126 or fit.symbol.nunique()<3 or cal.symbol.nunique()<3
        or fit.long.value_counts().reindex([0.,1.],fill_value=0).min()<40
        or cal.long.value_counts().reindex([0.,1.],fill_value=0).min()<15):
        return None,[]
    fit=fit.sort_values(['date','symbol']);cal=cal.sort_values(['date','symbol'])
    lo,hi=fit[INPUTS].quantile(.01),fit[INPUTS].quantile(.99)
    x=fit[INPUTS].replace([np.inf,-np.inf],np.nan).clip(lo,hi,axis=1)
    z=cal[INPUTS].replace([np.inf,-np.inf],np.nan).clip(lo,hi,axis=1)
    model=make_pipeline(SimpleImputer(strategy='median').set_output(transform='pandas'),LGBMClassifier(
        n_estimators=120,max_depth=3,num_leaves=7,learning_rate=.03,min_child_samples=60,reg_alpha=1.,reg_lambda=10.,verbosity=-1,n_jobs=2,random_state=42))
    model.fit(x,fit.long.astype(int))
    cp=np.clip(predict_proba(model,z,INPUTS)[:,1],1e-6,1-1e-6)
    if np.std(cp)<=1e-6:return None,[]
    calibrator=LogisticRegression(C=1.,random_state=42).fit(np.log(cp/(1-cp)).reshape(-1,1),cal.long.astype(int))
    weights=dict(model=model,calibrator=calibrator,lo=lo,hi=hi)
    filename=''.join(c if c.isalnum() else '_' for c in sector)+f'-long-{year}.joblib'
    path=folder/filename;joblib.dump(weights,path,compress=3)
    calibrated=calibrator.predict_proba(np.log(cp/(1-cp)).reshape(-1,1))[:,1]
    record=dict(sector=sector,year=year,file=str(path),sha256=digest(path),side='long',
        fit_rows=len(fit),calibration_rows=len(cal),fit_symbols=int(fit.symbol.nunique()),calibration_symbols=int(cal.symbol.nunique()),
        fit_start=str(fit.date.min().date()),fit_end=str(fit.date.max().date()),fit_available_max=str(fit.available.max().date()),
        calibration_start=str(cal.date.min().date()),calibration_end=str(cal.date.max().date()),available=str(cal.available.max().date()),
        calibration_metrics=classification_metrics(cal.long.to_numpy(),calibrated))
    if pd.Timestamp(record['fit_available_max'])>=pd.Timestamp(year-1,1,1) or pd.Timestamp(record['available'])>=pd.Timestamp(year,1,1):
        raise ValueError('Noncausal training/calibration')
    cal=cal.assign(probability=calibrated);title_auc=[]
    for symbol,g in cal.groupby('symbol'):
        valid=len(g)>=126 and g.long.value_counts().reindex([0.,1.],fill_value=0).min()>=15
        metrics=classification_metrics(g.long.to_numpy(),g.probability.to_numpy())
        title_auc.append(dict(symbol=symbol,year=year,sector=sector,model_sha256=record['sha256'],
            auc=metrics['auc'] if valid else None,n=len(g),positives=int(g.long.sum()),
            available=record['available'],source='calibration',qualified=bool(valid)))
    return record,title_auc


def prepare_year(root,year):
    from modelFactory.oracle_path.directional import panels,labels,split,Settings,INPUTS
    from modelFactory.oracle.build_labels import nyse_sessions
    from modelFactory.oracle.security_continuity import load_security_discontinuities
    from common.config_loader import replay_market_registry
    from backtesting.isolation import ReadOnlyReplay
    root=Path(root);folder=root/'years'/str(year);folder.mkdir(parents=True,exist_ok=True)
    plan=read(root/'request.json');spec=plan['annual_models'][str(year)];original=Path(spec['root'])
    if (folder/'manifest.json').exists() and read(folder/'manifest.json').get('status')=='COMPLETED':
        saved=read(folder/'manifest.json')
        for record in saved['models']:
            if digest(Path(record['file']))!=record['sha256']:raise ValueError('Changed sector weights on resume')
        for name,sha in saved['panel_sources'].items():
            if digest(Path(name))!=sha:raise ValueError('Changed training panels on resume')
        return saved
    sector_frame=pd.read_csv(root/'sectors.csv');sectors=sector_frame.set_index('symbol').gics_sector.dropna().to_dict()
    contract=Settings(**read(original/'protocol.json')['directional_contract']);manifest=read(original/'directional/manifest.json')
    expected={(r['symbol'],r['year']):r for r in manifest['models'] if r['side']=='long'}
    benchmark=pd.read_parquet(spec['benchmark_file']);breaks=load_security_discontinuities()
    fragments=folder/'panels';fragments.mkdir(exist_ok=True);sources={};checked=0;unknown=[]
    with ReadOnlyReplay(folder).install(),replay_market_registry(shared.restore_registry(BASE)):
        calendar=nyse_sessions(pd.Timestamp(spec['training_start']).date(),pd.Timestamp(spec['training_end']).date())
        files=sorted((original/'chunks').glob('*/bars.parquet'))
        for i,file in enumerate(files):
            if digest(file)!=read(file.parent/'done.json')['files']['bars.parquet']:raise ValueError('Changed training bar chunk')
            sources[str(file)]=digest(file);out=fragments/(file.parent.name+'.parquet')
            if not out.exists():
                frames=[];bars=pd.read_parquet(file)
                for symbol,g in bars.groupby('symbol'):
                    if symbol not in sectors:unknown.append(symbol);continue
                    f=panels(g,benchmark,calendar)
                    panel=f.merge(labels(g,calendar,contract,breaks.get(symbol,())),on='date',validate='one_to_one')
                    panel['sector']=sectors[symbol]
                    # Membership of pre-existing per-symbol train/cal subsets is
                    # independently checked before pooling across companies.
                    for vintage in [year-1,year]:
                        old=expected.get((symbol,vintage))
                        if old is None:continue
                        fit,cal=split(panel,vintage,'long')
                        if len(fit)!=old['fit_rows'] or len(cal)!=old['calibration_rows']:
                            raise ValueError(f'Panel membership differs from per-symbol: {symbol}/{vintage}')
                        checked+=1
                    frames.append(panel)
                data=pd.concat(frames,ignore_index=True) if frames else pd.DataFrame(columns=['sector',*INPUTS,'date','symbol','available','long','short'])
                data.to_parquet(out,index=False)
            atomic_json(folder/'progress.json',dict(status='BUILDING_CAUSAL_PANELS',completed=i+1,total=len(files),chunk=file.parent.name,year=year))
        # Load one sector at a time to bound memory, using Parquet row filtering.
        weights_dir=folder/'models';weights_dir.mkdir(exist_ok=True);records=[];aucs=[];skipped=[]
        for i,sector in enumerate(sorted(set(sectors.values()))):
            parts=[pd.read_parquet(p,filters=[('sector','==',sector)]) for p in sorted(fragments.glob('*.parquet'))]
            parts=[p for p in parts if len(p)]
            if not parts:
                skipped.append(dict(sector=sector,reason='NO_QUALIFIED_PANEL'));continue
            panel=pd.concat(parts,ignore_index=True)
            for vintage in [year-1,year]:
                atomic_json(folder/'progress.json',dict(status='TRAINING_SECTOR_LONG',sector=sector,vintage=vintage,year=year,completed=i,total=len(set(sectors.values()))))
                record,calibration=train_sector(panel,vintage,sector,weights_dir)
                if record is None:skipped.append(dict(sector=sector,vintage=vintage,reason='INSUFFICIENT_CLASSES_HISTORY_OR_CONSTANT_CALIBRATION'))
                else:records.append(record);aucs.extend(calibration)
        if not records:raise ValueError('No sector models trained')
        pd.DataFrame(aucs).to_parquet(folder/'calibration-by-symbol.parquet',index=False)
        result=dict(status='COMPLETED',year=year,oracle_batch_id=spec['batch_id'],models=records,skipped=skipped,
            features=INPUTS,sector_snapshot_sha256=plan['sector_snapshot_sha256'],
            original_bar_sources=sources,per_symbol_membership_checks=checked,unmapped=unknown,
            target=asdict(contract),oracle_protocol_sha256=spec['oracle_protocol_sha256'],
            panel_sources={str(p):digest(p) for p in fragments.glob('*.parquet')})
        atomic_json(folder/'manifest.json',result);atomic_json(folder/'progress.json',dict(status='TRAINING_COMPLETED',models=len(records),year=year))
    return result


def predict_year(root,year):
    import joblib
    from modelFactory.oracle_path.directional import panels,INPUTS
    from modelFactory.oracle.build_labels import nyse_sessions
    from common.config_loader import replay_market_registry
    from backtesting.isolation import ReadOnlyReplay
    from backtesting.per_symbol_selection import select_per_symbol,PerSymbolSelection
    root=Path(root);folder=root/'years'/str(year);manifest=read(folder/'manifest.json')
    if (folder/'signals.parquet').exists():
        receipt=read(folder/'prediction-receipt.json')
        if digest(folder/'signals.parquet')!=receipt['signals_sha256']:raise ValueError('Changed signals on resume')
        return
    plan=read(root/'request.json');spec=plan['annual_models'][str(year)]
    ranks=pd.read_parquet(BASE/'inputs/rankings'/f'{year}.parquet');ranks['date']=pd.to_datetime(ranks.date)
    pool=ranks.sort_values(['date','proba_extreme','symbol'],ascending=[True,False,True]).groupby('date').head(179)
    wanted=set(pool.symbol);by_symbol={s:g for s,g in pool.groupby('symbol')}
    # Reconstruct feature windows exactly as inference (650 calendar days),
    # without reading a bar beyond the year's last signal.
    first,last=pool.date.min(),pool.date.max();start=first-pd.Timedelta(days=650)
    inference_root=Path('artifacts/models/model-factory-20261107222627-db80b0/oracle_path')
    benchmark=pd.read_parquet(inference_root/'directional/benchmark.parquet')
    benchmark=benchmark[benchmark.date.between(start,last)]
    sectors=pd.read_csv(root/'sectors.csv').set_index('symbol').gics_sector.dropna().to_dict()
    models={(r['sector'],r['year']):r for r in manifest['models']}
    auc=pd.read_parquet(folder/'calibration-by-symbol.parquet').set_index(['symbol','year']).to_dict('index')
    rows=[];cache={};input_hashes={}
    with ReadOnlyReplay(folder).install(),replay_market_registry(shared.restore_registry(BASE)):
        calendar=nyse_sessions(start.date(),last.date())
        files=sorted((inference_root/'chunks').glob('*/bars.parquet'))
        for i,file in enumerate(files):
            data=pd.read_parquet(file);names=set(data.symbol)&wanted
            if not names:continue
            if digest(file)!=read(file.parent/'done.json')['files']['bars.parquet']:raise ValueError('Inference bar source changed')
            input_hashes[str(file)]=digest(file)
            for symbol,g in data[data.symbol.isin(names)&data.date.between(start,last)].groupby('symbol'):
                if symbol not in sectors:continue
                f=panels(g,benchmark,calendar).set_index('date');sector=sectors[symbol]
                for vintage,signals in by_symbol[symbol].groupby(by_symbol[symbol].date.dt.year):
                    record=models.get((sector,int(vintage)))
                    if record is None:continue
                    days=sorted(set(signals.date)&set(f.index))
                    if not days:continue
                    if pd.Timestamp(record['available'])>=min(days):raise ValueError('Future sector model')
                    if record['file'] not in cache:
                        if digest(Path(record['file']))!=record['sha256']:raise ValueError('Sector weights changed')
                        cache[record['file']]=joblib.load(record['file'])
                    probs=model_predictions(cache[record['file']],f.loc[days])
                    quality=auc.get((symbol,int(vintage)),{})
                    for day,prob in zip(days,probs):rows.append(dict(date=day,symbol=symbol,long_probability=float(prob),short_probability=None,
                        long_model_sha256=record['sha256'],short_model_sha256=None,sector=sector,
                        long_auc=quality.get('auc'),long_auc_available_date=quality.get('available'),
                        long_auc_model_sha256=quality.get('model_sha256'),long_auc_source='calibration'))
            atomic_json(folder/'progress.json',dict(status='PREDICTING_SECTOR_LONG',year=year,completed=i+1,total=len(files)))
        probs=pd.DataFrame(rows);probs.to_parquet(folder/'probabilities.parquet',index=False)
        # Drop the own-stock predictions from the archived full Oracle ranking.
        drop=[c for c in ranks if c.startswith(('long_','short_','retain_')) or c in ['side','selected','rank','reason','selection_probability']]
        oracle=ranks.drop(columns=drop).merge(probs,on=['date','symbol'],how='left',validate='one_to_one')
        settings=PerSymbolSelection(oracle_top_n=179,long_top_n=5,allow_long=True,allow_short=False,min_long_probability=.5,min_long_auc=.5)
        decisions=select_per_symbol(oracle,settings)
        decisions.to_parquet(folder/'ranking.parquet',index=False)
        selected=decisions[decisions.selected].rename(columns={'date':'trade_date'}).copy()
        selected['rank']=selected['rank'].astype(int);selected['oracle_amplitude_rank']=selected.oracle_rank
        selected['oracle_batch_id']=spec['batch_id'];selected['entry_year']=year
        selected.to_parquet(folder/'signals.parquet',index=False)
        atomic_json(folder/'prediction-receipt.json',dict(status='COMPLETED',oracle_batch_id=spec['batch_id'],selected=len(selected),symbols=int(selected.symbol.nunique()),
            signals_sha256=digest(folder/'signals.parquet'),inference_bar_sources=input_hashes,
            selection=settings.snapshot(),sector_manifest_sha256=digest(folder/'manifest.json')))
        atomic_json(folder/'progress.json',dict(status='COMPLETED',year=year,selected=len(selected)))


def annual_task(root,year):
    try:prepare_year(root,year);predict_year(root,year);return dict(year=year,status='COMPLETED')
    except Exception as exc:
        atomic_json(Path(root)/'years'/str(year)/'progress.json',dict(status='FAILED',year=year,error_type=type(exc).__name__,error=str(exc)))
        raise


def run(root,workers):
    root=Path(root);plan=read(root/'request.json')
    for file,sha in plan['sources'].items():
        if digest(Path(file))!=sha:raise ValueError('Source changed after protocol: '+file)
    results=[];failures=[]
    with ProcessPoolExecutor(max_workers=workers,mp_context=get_context('spawn')) as pool:
        tasks={pool.submit(annual_task,str(root),year):year for year in YEARS}
        for future in as_completed(tasks):
            try:results.append(future.result())
            except Exception as exc:failures.append(dict(year=tasks[future],error_type=type(exc).__name__,error=str(exc)))
            atomic_json(root/'progress.json',dict(status='TRAINING_PREDICTING',completed=len(results)+len(failures),total=len(YEARS),results=results,failures=failures))
    if failures:raise ValueError('Annual training/prediction failures; no backtest launched')
    for file,sha in plan['sources'].items():
        if digest(Path(file))!=sha:raise ValueError('Source changed during training: '+file)
    signals=pd.concat([pd.read_parquet(root/'years'/str(year)/'signals.parquet') for year in YEARS],ignore_index=True)
    signals.to_parquet(root/'signals.parquet',index=False)
    replay_cases(root,workers)


def replay_case(root,profile):
    from backtesting.simulator import BacktestEngine,BacktestResult
    from backtesting.isolation import ReadOnlyReplay
    from backtesting.winner_campaign_replay import metrics
    from backtesting.winner_portfolio_budget import replay_protections
    from common.config_loader import replay_market_registry
    from scripts.research.us_winner_vol20_extensions_20261109 import ExtendedPrices
    root=Path(root);folder=root/'cases'/profile;out=folder/'result';out.mkdir(parents=True,exist_ok=False)
    source_plan=read(BASE/'protocol.json');case=deepcopy(shared.CASES['Q051_050'])
    cfg=shared.configuration(source_plan['reference'],case);cfg.end_date=date(2025,12,31)
    pivots,sectors,actions=shared.market_data(BASE);extra=pd.read_parquet(EXT/'inputs/daily.parquet')
    for field in pivots:
        pivots[field]=pd.concat([pivots[field],extra.pivot(index='date',columns='symbol',values=field)],axis=1).sort_index()
    sectors=pd.concat([sectors,pd.read_parquet(EXT/'inputs/sectors.parquet')],ignore_index=True)
    actions=pd.concat([actions,pd.read_parquet(EXT/'inputs/actions.parquet')],ignore_index=True)
    signals=pd.read_parquet(root/'signals.parquet');protected=profile.startswith('VOL20')
    policy,gate=replay_protections(pivots['close'],daily_entry=True,target=.2 if protected else None,regime=protected)
    reference=deepcopy(source_plan['reference']);reference['risk']=asdict(cfg.risk_config)
    reference['arguments'].update(top_n=179,per_symbol_top_long=5,per_symbol_min_long_probability=.5,per_symbol_min_long_auc=.5,
        per_symbol_long=False,per_sector_long=True,drawdown_controller=False,
        portfolio_vol_target=.2 if protected else None,entry_regime_filter=protected)
    reference['per_symbol_selection']=None;reference['per_sector_selection']=read(root/'request.json')['selection']
    annual_models={str(y):source_plan['annual_models'][str(y)] for y in YEARS}
    protocol=dict(start='2021-01-01',end='2025-12-31',initial_equity=4000.,annual_reset=False,annual_models=annual_models,
        reference=reference,profile=profile,sector_models={str(y):str(root/'years'/str(y)/'manifest.json') for y in YEARS},
        replay_command=[sys.executable,'-m','scripts.research.us_q051_per_sector_20261109','--phase','run','--output-dir',str(root)])
    atomic_json(folder/'protocol.json',protocol);atomic_json(out/'configuration.json',dict(profile=profile,portfolio=asdict(cfg)))
    def no_http(*a,**kw):raise ValueError('No HTTP in sector experiment')
    with ReadOnlyReplay(folder).install(),replay_market_registry(shared.restore_registry(BASE)),patch.object(requests.Session,'request',no_http):
        def progress(done,total,day):
            p=dict(status='RUNNING',completed=done,total=total,last_date=str(day));atomic_json(folder/'progress.json',p);atomic_json(out/'progress.json',p)
        result=BacktestEngine(cfg).run(open_df=pivots['open'],close=pivots['close'],high=pivots['high'],low=pivots['low'],volume=pivots['volume'],signals_df=signals,
            sector_map=sectors.set_index('symbol').sector.to_dict(),intraday_source=ExtendedPrices(EXT),winner_research_assumptions=True,
            winner_progress=progress,winner_corporate_actions=actions.to_dict('records'),winner_selection_source=gate,winner_entry_risk_policy=policy)
        result.equity_curve.rename('equity').to_csv(out/'equity-daily.csv');result.intraday_equity_curve.to_parquet(out/'equity-5m.parquet',index=False)
        result.closed_trades_df.to_csv(out/'trades.csv',index=False);result.trade_events_df.to_csv(out/'events.csv',index=False)
        result.drawdown_breaker_df.to_csv(out/'risk-5m.csv',index=False)
        pd.DataFrame(policy.receipts if policy else []).to_csv(out/'portfolio-risk-decisions.csv',index=False)
        pd.DataFrame(gate.receipts if gate else []).to_csv(out/'regime-decisions.csv',index=False)
        report=metrics(result,4000.);report.update(daily_metrics(result.equity_curve));annual=[];opening=4000.
        for year in YEARS:
            curve=result.equity_curve[result.equity_curve.index.year==year];trades=result.closed_trades_df;marks=result.intraday_equity_curve
            closed=trades[pd.to_datetime(trades.exit_date,utc=True).dt.year.eq(year)] if len(trades) else trades
            part=BacktestResult(equity_curve=curve,closed_trades_df=closed,
                intraday_equity_curve=marks[pd.to_datetime(marks.timestamp,utc=True).dt.year.eq(year)],
                tracker_snapshot={'winner_replay':dict(status=report['status'],full_live_parity=False)})
            row=metrics(part,opening);row.update(year=year,model=source_plan['annual_models'][str(year)]['batch_id'])
            annual.append(row);opening=float(curve.iloc[-1])
        pd.DataFrame(annual).to_csv(out/'annual-summary.csv',index=False)
        report.update(profile=profile,annual_models=protocol['annual_models'],annual_reset=False,selected_signals=len(signals),
            finished_at_utc=datetime.now(timezone.utc).isoformat(),provider_calls=0,orders=0,SQL_writes=0)
        atomic_json(out/'report.json',report);atomic_json(folder/'progress.json',dict(status='COMPLETED_EXPLORATORY'))
    from ihm.services.backtesting_import import import_continuous_winner
    record=import_continuous_winner(folder,run_id=f'20261109_q051_{profile.lower()}_v1',
        label='Continu 2021–2025 — TOP5 LONG per-sector — '+('Volatilité 20 % + régime' if protected else 'Q051'),result_subdir='result')
    return dict(profile=profile,ihm_run_id=record['run_id'],folder=str(folder))


def replay_cases(root,workers):
    results=[];failures=[]
    with ProcessPoolExecutor(max_workers=min(workers,2),mp_context=get_context('spawn')) as pool:
        tasks={pool.submit(replay_case,str(root),profile):profile for profile in PROFILES}
        for future in as_completed(tasks):
            try:results.append(future.result())
            except Exception as exc:
                failure=dict(profile=tasks[future],error_type=type(exc).__name__,error=str(exc));failures.append(failure)
                atomic_json(root/'cases'/tasks[future]/'progress.json',dict(status='FAILED',**failure))
            atomic_json(root/'progress.json',dict(status='REPLAYING',completed=len(results)+len(failures),total=2,results=results,failures=failures))
    if failures:raise ValueError('Replay failed: '+str(failures))
    consolidate(root,results)


def consolidate(root,results):
    from backtesting.simulator import BacktestResult
    from backtesting.winner_campaign_replay import metrics
    sources={
        'Q051_SANS_FILTRE':EXT/'cases/Q051_NO_PER/result',
        'Q051_PER_SYMBOL':BASE/'cases/Q051_050/result',
        'VOL20_REGIME_SANS_FILTRE':EXT/'cases/VOL20_REGIME_NO_PER/result',
        'VOL20_REGIME_PER_SYMBOL':Path('artifacts/research/us_winner_q051_risk_budget/20261109-v1/REGIME_VOL20/result'),
        **{r['profile']:Path(r['folder'])/'result' for r in results}}
    rows=[];annual=[]
    for name,folder in sources.items():
        curve=pd.read_csv(folder/'equity-daily.csv',index_col=0,parse_dates=True).iloc[:,0];curve=curve[curve.index<=pd.Timestamp('2025-12-31')]
        marks=pd.read_parquet(folder/'equity-5m.parquet');marks=marks[pd.to_datetime(marks.timestamp,utc=True).dt.year.le(2025)]
        trades=pd.read_csv(folder/'trades.csv');trades=trades[pd.to_datetime(trades.exit_date,utc=True).dt.year.le(2025)]
        part=BacktestResult(equity_curve=curve,closed_trades_df=trades,intraday_equity_curve=marks,
            tracker_snapshot={'winner_replay':dict(status='INCOMPLETE_COVERAGE',full_live_parity=False)})
        result=metrics(part,4000.);result.update(daily_metrics(curve));rows.append(dict(profile=name,**result))
        a=pd.read_csv(folder/'annual-summary.csv');a=a[a.year.le(2025)].copy();a['profile']=name;annual.append(a)
    # Keep summary files compact rather than copying coverage arrays into CSV.
    columns=['profile','final_equity','return_pct','max_drawdown_pct','daily_max_drawdown_pct','closed_lot_trades','winners','losers','win_pct','average_gross_capital']
    pd.DataFrame(rows)[columns].to_csv(root/'comparison.csv',index=False)
    pd.concat(annual,ignore_index=True).to_csv(root/'annual-comparison.csv',index=False)
    atomic_json(root/'report.json',dict(status='COMPLETED_EXPLORATORY',results=[{k:r.get(k) for k in columns} for r in rows],
        imports=results,provider_calls=0,SQL_writes=0,orders=0,production_changes=False))
    atomic_json(root/'progress.json',read(root/'report.json'))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--phase',choices=['prepare','run'],required=True)
    parser.add_argument('--output-dir',type=Path,default=ROOT);parser.add_argument('--workers',type=int,default=2);args=parser.parse_args()
    try:
        if args.phase=='prepare':prepare(args.output_dir)
        else:run(args.output_dir,args.workers)
    except Exception as exc:
        if args.output_dir.exists():atomic_json(args.output_dir/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)))
        raise
