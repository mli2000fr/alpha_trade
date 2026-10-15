"""Paired archived LightGBM/CatBoost TOP5 portfolios, fixed SL5/trail15/TP20.

Use the same causal fold/features/year and native leveraged ledger for both.
No model training, SQL write, broker call or production champion selection.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
import gc
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research import us_oracle_path_top5_leverage_grid as grid
from scripts.research.oracle_path_confirmation import exclusive_run
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_concentrated_live_portfolio import ArchivedMacro
from scripts.research.us_oracle_path_economic_replay import qualify_entries
from scripts.research.us_oracle_tp20_sl10_campaign import code_hashes
from service.market import parse_market_regimes

LOG=logging.getLogger(__name__)
SOURCE=Path('artifacts/research/us_oracle_path_top5_leverage/20261014-v3')
BACKENDS=('lightgbm','catboost')
MODEL_NAMES={'lightgbm':'path_model.txt','catboost':'catboost_model.cbm'}


def freeze_top5(matrix,probabilities,*,year,backend,fold):
    """Rank the full observable pool first. No outcome-based membership."""
    frame=matrix[['date','symbol']].copy()
    frame['date']=pd.to_datetime(frame.date)
    if frame.duplicated(['date','symbol']).any():raise ValueError('Duplicate score key')
    values=np.asarray(probabilities,dtype=float)
    if len(values)!=len(frame) or not np.isfinite(values).all() or (values<0).any() or (values>1).any():
        raise ValueError('Invalid amplitude probabilities')
    frame['score']=values
    frame['proba_extreme']=frame.groupby('date').score.rank(method='average',pct=True)
    frame=frame.sort_values(['date','score','symbol'],ascending=[True,False,True])
    frame['oracle_rank']=frame.groupby('date').cumcount()+1
    frame=frame[frame.oracle_rank.le(5)].copy()
    frame['selected']=True;frame['year']=year;frame['fold_start']=fold;frame['backend']=backend
    return frame


def prepare(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    if (output/'ready.json').exists():
        ready=grid.read(output/'ready.json')
        verify_hashes(Path('.'),ready['sources']);verify_hashes(output,ready['files']);return ready
    if (output/'protocol.json').exists():raise ValueError('Incomplete prepare; choose fresh output ID')
    ready=grid.read(SOURCE/'ready.json');old=grid.read(SOURCE/'protocol.json')
    if grid.read(SOURCE/'report.json')['completed']!=144:raise ValueError('Incomplete reference')
    verify_hashes(Path('.'),ready['sources']);verify_hashes(SOURCE,ready['files'])
    sources=dict(ready['sources']);sources.update(code_hashes())
    for p in [SOURCE/'ready.json',SOURCE/'protocol.json',SOURCE/'report.json',SOURCE/'candidates.parquet',
              Path(__file__),Path('tests/test_us_oracle_path_backend_economic.py')]:sources[str(p)]=digest(p)
    contracts={}
    for year,batch in grid.MODELS.items():
        root,protocol,profile,folds=grid.load_contract('artifacts/models',batch)
        first=grid.nyse_sessions(f'{year}-01-01',grid.ENDS[year])[0]
        fold=grid.select_fold(first,folds)
        if fold!=old['models'][str(year)]['fold']:raise ValueError('Reference fold differs')
        if any(grid.select_fold(d,folds)!=fold for d in grid.nyse_sessions(first,grid.ENDS[year])):
            raise ValueError('Unfrozen intra-year fold')
        folder=root/'folds'/fold;done=grid.read(folder/'done.json')
        files={backend:str(folder/MODEL_NAMES[backend]) for backend in BACKENDS}
        for backend,file in files.items():
            if digest(file)!=done['files'][MODEL_NAMES[backend]]:raise ValueError('Challenger weights changed')
            sources[file]=digest(file)
        contracts[str(year)]=dict(batch_id=batch,fold=fold,files=files,champion=folds[fold]['backend'],
            train_available_max=folds[fold]['metrics']['train_available_max'],
            val_available_max=folds[fold]['metrics']['val_available_max'],
            validation_auc={b:done['validation_candidates'][b]['auc'] for b in BACKENDS})
        baseline=SOURCE/grid.key((year,.05,.15,.20))
        saved=grid.read(baseline/'case-report.json');verify_hashes(baseline,saved['files'])
        for name in ['case-report.json','daily.parquet','trades.parquet']:sources[str(baseline/name)]=digest(baseline/name)
    protocol=dict(frozen_at_utc=datetime.now(timezone.utc).isoformat(),contracts=contracts,
        backends=BACKENDS,years=grid.ENDS,top=5,sl=.05,trailing=.15,tp=.20,
        capital_usd=4000,max_entry_leverage=2,cases=6,source=str(SOURCE),
        direction='LONG_EXPLICIT_NOT_PREDICTED',no_reinforcement=True,no_h20_or_terminal_exit=True,
        data_features_folds_costs_risk_same=True,champion_exact_score_and_portfolio_parity_required=True,
        training=False,sql_writes=False,broker_calls=False,production_changed=False,
        independent_holdout=False,selection_warning='periods/protections already inspected; no champion promotion on these profits',
        reserves=old['reserves'],sources=sources)
    atomic_json(output/'protocol.json',protocol)
    observable=pd.read_parquet(grid.ARCHIVE/'scores.parquet',columns=['date','symbol'])
    observable.date=pd.to_datetime(observable.date)
    prices=pd.read_parquet(ready['prices']);prices.date=pd.to_datetime(prices.date)
    original=pd.read_parquet(SOURCE/'candidates.parquet')
    candidates=[]
    parity=[]
    for year,contract in contracts.items():
        year=int(year);profile=grid.load_contract('artifacts/models',contract['batch_id'])[2]
        parts=[]
        for index,folder in enumerate(sorted((grid.ARCHIVE/'chunks').iterdir())):
            saved=grid.read(folder/'done.json');verify_hashes(folder,{'features.parquet':saved['files']['features.parquet']})
            frame=pd.read_parquet(folder/'features.parquet');frame.date=pd.to_datetime(frame.date)
            frame=frame[frame.date.between(f'{year}-01-01',grid.ENDS[year])].copy()
            frame=frame.drop(columns=[c for c in frame if c.endswith('_xs_rank')])
            parts.append(frame)
            if index%12==0:atomic_json(output/'progress.json',dict(status='PREPARING',year=year,chunks=index,total_chunks=72))
        matrix=grid.restore_ranks(pd.concat(parts,ignore_index=True),profile['generator_options'])
        del parts;gc.collect()
        matrix=matrix.merge(observable,on=['date','symbol'],how='inner',validate='one_to_one')
        columns=profile['feature_columns']
        matrix[columns]=matrix[columns].replace([np.inf,-np.inf],np.nan).astype(np.float32)
        for backend in BACKENDS:
            if backend=='catboost':
                from catboost import CatBoostClassifier
                model=CatBoostClassifier().load_model(contract['files'][backend]);names=model.feature_names_
                if names!=columns:raise ValueError('Feature order mismatch')
                values=model.predict_proba(matrix[columns],thread_count=4)[:,1]
            else:
                import lightgbm as lgb
                model=lgb.Booster(model_file=contract['files'][backend]);names=model.feature_name()
                if names!=columns:raise ValueError('Feature order mismatch')
                values=grid.model_probabilities(model,backend,matrix[columns])
            scores=freeze_top5(matrix,values,year=year,backend=backend,fold=contract['fold'])
            scores=qualify_entries(scores,prices,grid.nyse_sessions('2023-01-01','2026-10-09'))
            if backend==contract['champion']:
                expected=original[original.year.eq(year)].reset_index(drop=True)
                pd.testing.assert_frame_equal(scores.reset_index(drop=True),expected,check_exact=True)
                parity.append(dict(year=year,backend=backend,rows=len(scores),scores_membership_quality_exact=True))
            candidates.append(scores)
            del model;gc.collect()
        del matrix;gc.collect()
        LOG.info('Prepared both backends %s',year)
    frame=pd.concat(candidates,ignore_index=True)
    if frame.duplicated(['date','symbol','backend']).any():raise ValueError('Duplicate candidates')
    frame.to_parquet(output/'candidates.parquet',index=False)
    atomic_json(output/'score-parity.json',parity)
    result=dict(sources=sources,contracts=contracts,
        files={name:digest(output/name) for name in ['candidates.parquet','score-parity.json']})
    atomic_json(output/'ready.json',result);verify_hashes(Path('.'),sources)
    atomic_json(output/'progress.json',dict(status='READY',completed=0,total=6))
    return result


_CACHE=None


def worker_init(output):
    global _CACHE
    output=Path(output);ready=grid.read(SOURCE/'ready.json')
    candidates=pd.read_parquet(output/'candidates.parquet')
    prices=pd.read_parquet(ready['prices']);prices.date=pd.to_datetime(prices.date)
    required=set(candidates.symbol)|{'SPY','VMRK'}
    for event in ready['events']:
        if event['source'] in required:required.add(event['target'])
    prices=prices[prices.symbol.isin(required)].copy()
    calendar=grid.nyse_sessions('2023-01-01','2026-10-09')
    frames={key:prices.pivot(index='date',columns='symbol',values=column).reindex(calendar)
        for key,column in [('opens','open'),('close','close'),('high','high'),('low','low'),('volume','volume')]}
    sectors=pd.read_parquet(grid.SECTORS).set_index('symbol').sector.to_dict();sectors['VMRK']=sectors['EQR']
    sectors['TELWY']=sectors.get('TOELY',sectors.get('TELWY','Unknown'))
    _CACHE=dict(root=output,ready=ready,contracts=grid.read(output/'ready.json')['contracts'],candidates=candidates,
        prices=prices,frames=frames,sectors=sectors,macro=ArchivedMacro(pd.read_parquet(ready['macro'])),
        market=parse_market_regimes(ready['market']))


def run_case(case):
    year,backend=case
    backend_root=_CACHE['root']/backend;backend_root.mkdir(exist_ok=True)
    folder=backend_root/grid.key((year,.05,.15,.20));marker=folder/'backend-report.json'
    if marker.exists():
        prior=grid.read(marker)
        if prior['status']=='COMPLETED_SIMULATED_ASSUMPTIONS':verify_hashes(folder,prior['files']);return prior
    # Reuse the complete previously tested ledger, not a simpler PnL calculation.
    grid._CACHE=dict(_CACHE,root=backend_root,candidates=_CACHE['candidates'][_CACHE['candidates'].backend.eq(backend)])
    result=grid.run_case((year,.05,.15,.20))
    is_champion=backend==_CACHE['contracts'][str(year)]['champion']
    if result['status']=='COMPLETED_SIMULATED_ASSUMPTIONS':
        try:
            if is_champion:
                baseline=SOURCE/grid.key((year,.05,.15,.20))
                for name in ['daily.parquet','trades.parquet']:
                    pd.testing.assert_frame_equal(pd.read_parquet(folder/name),pd.read_parquet(baseline/name),check_exact=True)
            result.update(backend=backend,is_archived_champion=is_champion,champion_exact_portfolio_parity=is_champion,
                case=f'{year}-{backend}',relative_folder=str(folder.relative_to(_CACHE['root'])))
        except Exception as exc:
            result=dict(status='FAILED',year=year,backend=backend,case=f'{year}-{backend}',
                relative_folder=str(folder.relative_to(_CACHE['root'])),error=str(exc),error_type=type(exc).__name__)
    else:
        result.update(backend=backend,case=f'{year}-{backend}',relative_folder=str(folder.relative_to(_CACHE['root'])))
    atomic_json(marker,result);return result


def run(output,phase='all',workers=3):
    output=Path(output)
    with exclusive_run(output):
        ready=prepare(output)
        if phase=='prepare':return
        reports=[]
        cases=[(year,backend) for year in grid.MODELS for backend in BACKENDS]
        with ProcessPoolExecutor(max_workers=workers,initializer=worker_init,initargs=(str(output),)) as pool:
            futures=[pool.submit(run_case,case) for case in cases]
            for future in as_completed(futures):
                result=future.result();reports.append(result)
                atomic_json(output/'progress.json',dict(status='RUNNING',completed=len(reports),total=6,
                    failed=sum(r['status']=='FAILED' for r in reports),last=result['case']))
                atomic_json(output/'report.partial.json',dict(cases=reports))
                LOG.info('%s %s/6 %s',result['case'],len(reports),result['status'])
        verify_hashes(Path('.'),ready['sources']);verify_hashes(output,ready['files'])
        comparisons=[]
        for year in grid.MODELS:
            rows={c['backend']:c for c in reports if c['year']==year and c['status']!='FAILED'}
            if len(rows)!=2:continue
            lgb,cat=rows['lightgbm'],rows['catboost']
            comparisons.append(dict(year=year,lightgbm_net_pct=lgb['net_return_pct'],catboost_net_pct=cat['net_return_pct'],
                delta_lightgbm_points=lgb['net_return_pct']-cat['net_return_pct'],
                lightgbm_dd_pct=lgb['dd_pct'],catboost_dd_pct=cat['dd_pct']))
        failed=sum(r['status']=='FAILED' for r in reports)
        status='COMPLETED_EXPLORATORY' if not failed else 'PARTIAL_FAILED'
        atomic_json(output/'report.json',dict(status=status,cases=reports,comparisons=comparisons,
            source_hashes_verified=True,production_changed=False,independent_holdout=False))
        atomic_json(output/'progress.json',dict(status=status,completed=6-failed,failed=failed,total=6))


if __name__=='__main__':
    parser=argparse.ArgumentParser(__doc__);parser.add_argument('--output',required=True)
    parser.add_argument('--phase',choices=['all','prepare','run'],default='all')
    parser.add_argument('--workers',type=int,choices=[1,2,3],default=3)
    args=parser.parse_args();logging.basicConfig(level=logging.INFO)
    try:run(**vars(args))
    except Exception as exc:
        Path(args.output).mkdir(parents=True,exist_ok=True)
        atomic_json(Path(args.output)/'failure.json',dict(status='FAILED',error=str(exc)));raise
