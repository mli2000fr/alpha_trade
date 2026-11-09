"""Missing 2026 sector scores for a continuous extension of frozen rank trials.

Only research files and read-only SQL. Prior years/models/results stay intact.
"""
from copy import deepcopy
from datetime import datetime,timezone
from pathlib import Path
import shutil
from unittest.mock import patch

import joblib
import numpy as np
import pandas as pd

from scripts.research import us_q051_per_sector_20261109 as sector
from scripts.research.us_q051_per_sector_recovery_20261109 import safe_panels
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest

OLD=Path('artifacts/research/us_q051_per_sector/20261109-v4')


def initialize(root):
    from modelFactory.oracle_path.predict import load_contract
    root.mkdir(parents=True,exist_ok=False)
    plan=deepcopy(sector.read(OLD/'request.json'))
    batch=sector.read(sector.BASE/'protocol.json')['annual_models']['2026']['batch_id']
    folder,p,_,folds=load_contract('artifacts/models',batch)
    start=p['training_config']['data']['training_start_date']
    end=p['training_config']['data']['training_end_date']
    if p['horizon']!=10 or pd.Timestamp(end)>=pd.Timestamp('2026-01-01'):
        raise ValueError('Noncausal or wrong-horizon 2026 Oracle')
    if sorted(p['universe'])!=sorted(plan['universe']):raise ValueError('Changed 2026 universe')
    plan['annual_models']['2026']=dict(batch_id=batch,root=str(folder),training_start=start,training_end=end,
        benchmark_file=str(folder/'directional/benchmark.parquet'),oracle_protocol_sha256=digest(folder/'protocol.json'),
        features_sha256=digest(folder/'feature_profile.json'),
        folds={k:dict(model_sha256=v['model_sha256'],metrics=v['metrics']) for k,v in folds.items()})
    plan.update(end='2026-10-01',years=list(range(2021,2027)),extension=dict(previous=str(OLD),
        new_sector_parent_year=2026,new_vintages=[2025,2026],training_cutoff='2025-12-31',
        all_previous_years_reused=True,SQL='READ ONLY',provider_calls=0,orders=0,
        retrospective=True,independent_holdout=False,created_at_utc=datetime.now(timezone.utc).isoformat()))
    shutil.copyfile(OLD/'sectors.csv',root/'sectors.csv')
    for year in range(2021,2026):
        old=OLD/'years'/str(year);new=root/'years'/str(year);new.mkdir(parents=True)
        for name in ['manifest.json','calibration-by-symbol.parquet','probabilities.parquet','signals.parquet','prediction-receipt.json']:
            shutil.copyfile(old/name,new/name)
        receipt=sector.read(old/'prediction-receipt.json')
        if digest(new/'signals.parquet')!=receipt['signals_sha256'] or digest(new/'manifest.json')!=receipt['sector_manifest_sha256']:
            raise ValueError('Copied prior year failed sealed receipt')
        for name in ['manifest.json','probabilities.parquet','prediction-receipt.json']:
            plan['sources'][str(old/name)]=digest(old/name)
    for name in ['protocol.json','report.json','feature_profile.json','directional/manifest.json','directional/benchmark.parquet']:
        plan['sources'][str(folder/name)]=digest(folder/name)
    plan['sources'][str(Path(__file__))]=digest(Path(__file__))
    atomic_json(root/'request.json',plan)
    atomic_json(root/'progress.json',dict(status='PREPARING_2026_SECTOR',prior_years_reused=5))


def freeze_inference(root,pool):
    """Freeze the same native inference inputs, without provider downloads."""
    from database.connection import get_sqlalchemy_engine
    from modelFactory.oracle_path.labels import load_bars
    from modelFactory.data_loader import load_benchmark_bars
    from common.config_loader import replay_market_registry
    from backtesting.isolation import ReadOnlyReplay
    folder=root/'years/2026';inputs=folder/'inference';inputs.mkdir(exist_ok=True)
    if (inputs/'manifest.json').exists():
        saved=sector.read(inputs/'manifest.json')
        for name,sha in saved['files'].items():
            if digest(inputs/name)!=sha:raise ValueError('Changed frozen 2026 inference input')
        return inputs
    names=sorted(set(pool.symbol));first,last=pool.date.min(),pool.date.max();start=first-pd.Timedelta(days=650)
    with ReadOnlyReplay(folder).install(),replay_market_registry(sector.shared.restore_registry(sector.BASE)):
        engine=get_sqlalchemy_engine(db_name='alpha_trade')
        try:
            benchmark=load_benchmark_bars(engine,'SPY',start_date=str(start.date()),end_date=str(last.date()))
            benchmark.reset_index(drop=True).to_parquet(inputs/'benchmark.parquet',index=False)
            for i in range(0,len(names),25):
                bars=load_bars(engine,names[i:i+25],str(start.date()),str(last.date()))
                if bars.duplicated(['date','symbol']).any():raise ValueError('Duplicate inference bars')
                if len(bars) and bars.date.max()>last:raise ValueError('Future inference bars')
                bars.to_parquet(inputs/f'bars-{i//25:03d}.parquet',index=False)
                atomic_json(folder/'progress.json',dict(status='FREEZING_2026_INFERENCE_READ_ONLY',completed=min(i+25,len(names)),total=len(names)))
        finally:engine.dispose()
    atomic_json(inputs/'manifest.json',dict(files={p.name:digest(p) for p in inputs.glob('*.parquet')},
        first_signal=str(first.date()),last_signal=str(last.date()),start=str(start.date()),
        symbols=len(names),SQL_writes=0,provider_calls=0,cutoff_utc=datetime.now(timezone.utc).isoformat(),
        limitation='Current SQL archive, not certified vintage prices; existing per-symbol probability reproduction checked'))
    return inputs


def predict_2026(root):
    from modelFactory.oracle.build_labels import nyse_sessions
    from modelFactory.oracle_path.directional_metrics import predict
    folder=root/'years/2026';manifest=sector.read(folder/'manifest.json')
    if (folder/'prediction-receipt.json').exists():
        receipt=sector.read(folder/'prediction-receipt.json')
        if digest(folder/'probabilities.parquet')!=receipt['probabilities_sha256']:raise ValueError('Changed probabilities')
        return
    ranks=pd.read_parquet(sector.BASE/'inputs/rankings/2026.parquet');ranks['date']=pd.to_datetime(ranks.date)
    pool=ranks.sort_values(['date','proba_extreme','symbol'],ascending=[True,False,True]).groupby('date').head(179)
    inputs=freeze_inference(root,pool);first,last=pool.date.min(),pool.date.max();start=first-pd.Timedelta(days=650)
    benchmark=pd.read_parquet(inputs/'benchmark.parquet');calendar=nyse_sessions(start.date(),last.date())
    mapping=pd.read_csv(root/'sectors.csv').set_index('symbol').gics_sector.dropna().to_dict()
    spec=sector.read(root/'request.json')['annual_models']['2026'];model_root=Path(spec['root'])
    records={(r['sector'],int(r['year'])):r for r in manifest['models']}
    own={(r['symbol'],int(r['year'])):{**r,'file':str(model_root/r['file'])}
        for r in sector.read(model_root/'directional/manifest.json')['models'] if r['side']=='long'}
    auc=pd.read_parquet(folder/'calibration-by-symbol.parquet').set_index(['symbol','year']).to_dict('index')
    by_symbol={s:g for s,g in pool.groupby('symbol')};cache={};rows=[];checks=[]
    def weights(record):
        if record['file'] not in cache:
            if digest(Path(record['file']))!=record['sha256']:raise ValueError('Changed inference model')
            cache[record['file']]=joblib.load(record['file'])
        return cache[record['file']]
    for i,file in enumerate(sorted(inputs.glob('bars-*.parquet'))):
        data=pd.read_parquet(file)
        for symbol,g in data.groupby('symbol'):
            if symbol not in mapping:continue
            features=safe_panels(g,benchmark,calendar).set_index('date')
            for vintage,signals in by_symbol[symbol].groupby(by_symbol[symbol].date.dt.year):
                days=sorted(set(signals.date)&set(features.index));record=records.get((mapping[symbol],int(vintage)))
                if not days or record is None:continue
                if pd.Timestamp(record['available'])>=min(days):raise ValueError('Future sector vintage')
                own_record=own.get((symbol,int(vintage)))
                if own_record is not None:
                    archived=signals.set_index('date').loc[days,'long_probability'].dropna()
                    if len(archived):
                        reproduced=predict(weights(own_record),features.loc[archived.index])
                        error=np.abs(reproduced-archived.to_numpy(float))
                        checks.append(dict(symbol=symbol,year=int(vintage),count=len(error),max_error=float(error.max())))
                probability=predict(weights(record),features.loc[days]);quality=auc.get((symbol,int(vintage)),{})
                for day,p in zip(days,probability):
                    rows.append(dict(date=day,symbol=symbol,long_probability=float(p),short_probability=None,
                        long_model_sha256=record['sha256'],short_model_sha256=None,sector=mapping[symbol],
                        long_auc=quality.get('auc'),long_auc_available_date=quality.get('available'),
                        long_auc_model_sha256=quality.get('model_sha256'),long_auc_source='calibration'))
        atomic_json(folder/'progress.json',dict(status='PREDICTING_2026_AND_CHECKING_ARCHIVED_SYMBOL_SCORES',completed=i+1,total=len(list(inputs.glob('bars-*.parquet')))))
    audit=dict(checked_scores=sum(x['count'] for x in checks),max_error=max((x['max_error'] for x in checks),default=None),
        tolerance=1e-8,groups=checks)
    atomic_json(folder/'per-symbol-reproduction.json',audit)
    if not checks or audit['max_error']>audit['tolerance']:
        raise ValueError('2026 inference does not reproduce archived per-symbol scores: '+str(audit['max_error']))
    probabilities=pd.DataFrame(rows)
    if probabilities.duplicated(['date','symbol']).any():raise ValueError('Duplicate 2026 sector prediction')
    probabilities.to_parquet(folder/'probabilities.parquet',index=False)
    # Existing fusion validation expects a sealed selection receipt. No extra
    # absolute-threshold selection is used; the probabilities are the product.
    probabilities[['date','symbol']].iloc[:0].to_parquet(folder/'signals.parquet',index=False)
    atomic_json(folder/'prediction-receipt.json',dict(status='COMPLETED',oracle_batch_id=spec['batch_id'],
        probabilities_sha256=digest(folder/'probabilities.parquet'),signals_sha256=digest(folder/'signals.parquet'),
        sector_manifest_sha256=digest(folder/'manifest.json'),inference_manifest_sha256=digest(inputs/'manifest.json'),
        per_symbol_reproduction=dict(checked_scores=audit['checked_scores'],max_error=audit['max_error']),
        signals_role='Empty compatibility receipt only; final selection frozen by rank-fusion prepare',
        SQL_writes=0,provider_calls=0,orders=0))


def extend_sector(root):
    root=Path(root)
    if not root.exists():initialize(root)
    with patch('modelFactory.oracle_path.directional.panels',safe_panels):sector.prepare_year(root,2026)
    predict_2026(root)
    manifest=sector.read(root/'years/2026/manifest.json')
    for row in manifest['models']:
        if digest(Path(row['file']))!=row['sha256']:raise ValueError('Changed sector weights')
        if pd.Timestamp(row['available'])>=pd.Timestamp(row['year'],1,1):raise ValueError('Future model')
    atomic_json(root/'validation.json',dict(status='PASS',new_2026_parent_models=len(manifest['models']),
        membership_checks=manifest['per_symbol_membership_checks'],prior_years_reused=5,
        availability_checked=True,SQL_writes=0,provider_calls=0,orders=0))
    atomic_json(root/'progress.json',dict(status='SECTOR_2026_READY',models=len(manifest['models'])))
