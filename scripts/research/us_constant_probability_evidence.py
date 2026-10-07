"""Read-only evidence for PENN/ROKU/GH serving; no production mutations."""
import argparse
import json
import tarfile
import time
from pathlib import Path, PurePosixPath

import pandas as pd
from sqlalchemy import bindparam, text
from database.connection import get_sqlalchemy_engine

BATCH='model-factory-20260903174624-014164'
ROOT=Path('artifacts/research/us_common_degradation/constant-probability-20261005-v1')
NAMES=['PENN','ROKU','GH']


def inventory():
    ROOT.mkdir(parents=True,exist_ok=True)
    engine=get_sqlalchemy_engine()
    with engine.connect() as conn:
        if conn.execute(text('SELECT DATABASE()')).scalar()!='alpha_trade':
            raise ValueError('US required')
        query=text('SELECT p.symbol,p.prediction_date,p.run_id,p.selected_model,p.direction_long_model,'
            'p.direction_short_model,p.direction_long_run_id,p.direction_short_run_id,p.calibration_method,'
            'p.proba_long,p.proba_short,p.proba_flat,p.predicted_proba,p.source,p.created_at '
            'FROM model_predictions p WHERE p.symbol IN :symbols AND p.model_role=\'directional_bundle\' '
            'AND p.run_id IN (SELECT run_id FROM model_training_run WHERE batch_id=:batch) '
            'ORDER BY p.symbol,p.prediction_date').bindparams(bindparam('symbols',expanding=True))
        predictions=pd.read_sql(query,conn,params={'symbols':NAMES,'batch':BATCH})
        runs=pd.read_sql(text('SELECT run_id,symbol,model_role,status,epochs_run,best_epoch,'
            'checkpoint_path,scaler_path,config_path FROM model_training_run '
            'WHERE batch_id=:batch AND symbol IN :symbols').bindparams(bindparam('symbols',expanding=True)),
            conn,params={'symbols':NAMES,'batch':BATCH})
    predictions.to_parquet(ROOT/'persisted_predictions.parquet',index=False)
    runs.to_parquet(ROOT/'registered_runs.parquet',index=False)
    groups=[]
    for keys,g in predictions.groupby(['symbol','direction_long_model','direction_short_model','calibration_method'],dropna=False):
        groups.append(dict(symbol=keys[0],long_model=keys[1],short_model=keys[2],calibration=keys[3],
            rows=len(g),first=str(g.prediction_date.min()),last=str(g.prediction_date.max()),
            p_long_min=float(g.proba_long.min()),p_long_max=float(g.proba_long.max()),
            p_long_unique=g.proba_long.nunique(),p_long_std=float(g.proba_long.std()),
            created_first=str(g.created_at.min()),created_last=str(g.created_at.max())))
    paths=[]
    for row in runs.to_dict('records'):
        for field in ['checkpoint_path','scaler_path','config_path']:
            value=row[field]
            paths.append(dict(symbol=row['symbol'],role=row['model_role'],field=field,path=value,
                              exists=bool(value and Path(value).is_file())))
    payload=dict(batch=BATCH,groups=groups,paths=paths,raw_logits_persisted=False)
    (ROOT/'database_evidence.json').write_text(json.dumps(payload,indent=2,default=str),encoding='utf-8')
    print(json.dumps(payload,default=str),flush=True)


def scan(archive):
    ROOT.mkdir(parents=True,exist_ok=True)
    tops=set(); matches=[]; extracted=[]; count=0; started=time.time()
    with archive.open('rb') as file:
        with tarfile.open(fileobj=file,mode='r|gz') as tar:
            for member in tar:
                count+=1
                parts=PurePosixPath(member.name).parts
                if len(parts)>=2: tops.add('/'.join(parts[:2]))
                if BATCH in member.name:
                    matches.append(member.name)
                    allowed=member.isfile() and member.size<=64*1024*1024 and (
                        any('/'+symbol+'/' in member.name for symbol in NAMES)
                        or member.name.endswith('cascade_manifest.json'))
                    if allowed and '..' not in parts and not PurePosixPath(member.name).is_absolute():
                        target=ROOT/'recovered'/Path(*parts)
                        target.parent.mkdir(parents=True,exist_ok=True)
                        handle=tar.extractfile(member)
                        if handle:
                            target.write_bytes(handle.read())
                            extracted.append(str(target))
                if count%100==0:
                    progress=dict(archive=str(archive),members=count,compressed_bytes_read=file.tell(),
                        compressed_bytes_total=archive.stat().st_size,elapsed_seconds=time.time()-started,
                        matching_members=len(matches))
                    (ROOT/'scan_progress.json').write_text(json.dumps(progress),encoding='utf-8')
    result=dict(archive=str(archive),members=count,top_paths=sorted(tops),matches=matches,
        recovered=extracted,complete=True,elapsed_seconds=time.time()-started)
    (ROOT/(archive.stem+'.inventory.json')).write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,default=str),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--archive',type=Path)
    args=parser.parse_args()
    if args.archive: scan(args.archive)
    else: inventory()
