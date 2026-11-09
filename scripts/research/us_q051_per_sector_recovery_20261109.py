"""Reuse verified trained sector models; correct only SPY index alignment.

The frozen first campaign and all failed predictions remain untouched. No
retraining, changed weights, SQL, provider requests or production change.
"""
from concurrent.futures import ProcessPoolExecutor,as_completed
from datetime import datetime,timezone
import json
from multiprocessing import get_context
from pathlib import Path
import shutil
from unittest.mock import patch

import pandas as pd

from scripts.research import us_q051_per_sector_20261109 as original
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest
from modelFactory.oracle_path.directional import panels as original_panels

PREVIOUS=Path('artifacts/research/us_q051_per_sector/20261109-v3')
ROOT=Path('artifacts/research/us_q051_per_sector/20261109-v4')


def safe_panels(bars,benchmark,calendar):
    # compute_features constructs a benchmark frame from a reset-index price
    # series and its date Series. Slicing must not leave an unrelated old index.
    return original_panels(bars,benchmark.reset_index(drop=True),calendar)


def prepare(root):
    root.mkdir(parents=True,exist_ok=False)
    plan=original.read(PREVIOUS/'request.json')
    for name,sha in plan['sources'].items():
        if digest(Path(name))!=sha:raise ValueError('Original source changed: '+name)
    if digest(PREVIOUS/'sectors.csv')!=plan['sector_snapshot_sha256']:raise ValueError('Sector snapshot changed')
    plan['recovery']=dict(previous=str(PREVIOUS),previous_request_sha256=digest(PREVIOUS/'request.json'),
        reason='Reset sliced benchmark index before feature construction; previous 2021 predictions also invalidated',
        model_weights_unchanged=True,retraining=False,source_code_sha256=digest(Path(__file__)))
    plan['sources'][str(Path(__file__))]=digest(Path(__file__))
    shutil.copyfile(PREVIOUS/'sectors.csv',root/'sectors.csv')
    weights=[]
    for year in original.YEARS:
        old=PREVIOUS/'years'/str(year);folder=root/'years'/str(year);folder.mkdir(parents=True)
        manifest=original.read(old/'manifest.json')
        if manifest['status']!='COMPLETED':raise ValueError('Incomplete training: '+str(year))
        for record in manifest['models']:
            if digest(Path(record['file']))!=record['sha256']:raise ValueError('Changed trained model')
            weights.append(dict(parent_year=year,sector=record['sector'],vintage=record['year'],sha256=record['sha256'],file=record['file']))
        for file in ['manifest.json','calibration-by-symbol.parquet']:
            shutil.copyfile(old/file,folder/file)
        atomic_json(folder/'model-reuse.json',dict(source=str(old),manifest_sha256=digest(old/'manifest.json'),
            calibration_sha256=digest(old/'calibration-by-symbol.parquet'),models=len(manifest['models']),retrained=False))
        atomic_json(folder/'progress.json',dict(status='WAITING_PREDICTION_REPAIR',year=year))
    atomic_json(root/'verified-model-reuse.json',dict(status='PASS',weights=weights,count=len(weights)))
    atomic_json(root/'request.json',plan)
    atomic_json(root/'progress.json',dict(status='REPAIRING_PREDICTIONS',completed=0,total=5,trained_models_reused=len(weights)))


def predict_one(root,year):
    import traceback
    try:
        with patch('modelFactory.oracle_path.directional.panels',safe_panels):
            original.predict_year(root,year)
        return dict(year=year,status='COMPLETED')
    except Exception as exc:
        atomic_json(Path(root)/'years'/str(year)/'progress.json',dict(status='FAILED',year=year,error_type=type(exc).__name__,
            error=str(exc),traceback=traceback.format_exc()))
        raise


def run(root=ROOT):
    prepare(root);results=[];failures=[]
    with ProcessPoolExecutor(max_workers=2,mp_context=get_context('spawn')) as pool:
        tasks={pool.submit(predict_one,str(root),year):year for year in original.YEARS}
        for future in as_completed(tasks):
            try:results.append(future.result())
            except Exception as exc:failures.append(dict(year=tasks[future],error_type=type(exc).__name__,error=str(exc)))
            atomic_json(root/'progress.json',dict(status='REPAIRING_PREDICTIONS',completed=len(results)+len(failures),total=5,results=results,failures=failures))
    if failures:raise ValueError('Prediction repair failed; no backtest: '+str(failures))
    for name,sha in original.read(root/'request.json')['sources'].items():
        if digest(Path(name))!=sha:raise ValueError('Source changed during recovery')
    frames=[pd.read_parquet(root/'years'/str(year)/'signals.parquet') for year in original.YEARS]
    pd.concat(frames,ignore_index=True).to_parquet(root/'signals.parquet',index=False)
    original.replay_cases(root,2)


if __name__=='__main__':
    try:run()
    except Exception as exc:
        if ROOT.exists():atomic_json(ROOT/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)))
        raise
