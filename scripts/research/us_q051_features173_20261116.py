"""Annual Oracle + own-stock LONG/SHORT 173-input campaign, frozen datasets.

New fits and model files; original campaigns remain immutable. Native estimators,
targets and splits are retained. No provider/LLM call or broker submission.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor,as_completed
from copy import deepcopy
from dataclasses import fields,is_dataclass,replace,asdict
from datetime import date,datetime,timezone
from multiprocessing import get_context
from pathlib import Path
import json
import logging
import os
import shutil
import subprocess
import sys
import time
import typing
from unittest.mock import patch
from uuid import uuid4
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from scripts.research.us_concentrated_historical_tapes import atomic_json,digest
from scripts.research import us_winner_continuous_q051_q088_20261108 as shared

ROOT=Path('artifacts/research/us_q051_features173/20261116-v2')


class OracleMemorySlot:
    """Windows file lock, released by the OS even if a worker exits."""
    def acquire(self):
        import msvcrt
        self.stream=(ROOT/'oracle-memory.lock').open('a+b')
        if self.stream.tell()==0:self.stream.write(b'0');self.stream.flush()
        while True:
            self.stream.seek(0)
            try:msvcrt.locking(self.stream.fileno(),msvcrt.LK_NBLCK,1);return
            except OSError:time.sleep(1)
    def release(self):
        import msvcrt
        self.stream.seek(0);msvcrt.locking(self.stream.fileno(),msvcrt.LK_UNLCK,1);self.stream.close()


def workers(tasks,limit,on_finished):
    """File-backed subprocess coordination; no Manager/named-pipe service."""
    waiting=list(tasks);active=[]
    try:
        while waiting or active:
            while waiting and len(active)<limit:
                key,args,logbase=waiting.pop(0);logbase.parent.mkdir(parents=True,exist_ok=True)
                stdout=Path(str(logbase)+'.stdout.log').open('ab');stderr=Path(str(logbase)+'.stderr.log').open('ab')
                process=subprocess.Popen([sys.executable,'-X','utf8','-u','-m',
                    'scripts.research.us_q051_features173_20261116',*args],cwd=Path.cwd(),
                    stdout=stdout,stderr=stderr,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                active.append((process,key,stdout,stderr))
            for item in active[:]:
                process,key,stdout,stderr=item
                if process.poll() is None:continue
                stdout.close();stderr.close();active.remove(item)
                if process.returncode:raise RuntimeError(f'Worker {key} failed ({process.returncode}); inspect its file logs')
                on_finished(key)
            if active:time.sleep(1)
    finally:
        for process,key,stdout,stderr in active:
            if process.poll() is None:process.terminate();process.wait()
            stdout.close();stderr.close()


def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))


def restore_config(default,values):
    hints=typing.get_type_hints(type(default));names={f.name for f in fields(default)};changes={}
    for key,value in values.items():
        if key not in names:raise ValueError('Unknown frozen configuration field: '+key)
        prior=getattr(default,key);hint=hints.get(key)
        if is_dataclass(prior) and isinstance(value,dict):value=restore_config(prior,value)
        elif value is not None and (hint is date or 'datetime.date' in str(hint)):value=date.fromisoformat(value)
        elif value is not None and (hint is Path or 'pathlib.Path' in str(hint)):value=Path(value)
        changes[key]=value
    return replace(default,**changes)


def link(source,target):
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists():
        if digest(source)!=digest(target):raise ValueError('Conflicting frozen file: '+str(target))
        return
    try:os.link(source,target)
    except OSError:shutil.copyfile(source,target)


def prepare():
    from modelFactory.config import TrainingConfig
    ROOT.mkdir(parents=True,exist_ok=False);old=read(shared.ROOT/'protocol.json')
    stamp=datetime.now(ZoneInfo('Europe/Paris')).strftime('%Y%m%d%H%M%S')
    models={};universe=None;columns=None
    for year,record in old['annual_models'].items():
        source=Path('artifacts/models')/record['batch_id']/'oracle_path'
        p=read(source/'protocol.json');profile=read(source/'feature_profile.json')
        if len(profile['feature_columns'])!=173:raise ValueError('Expected 173 Oracle inputs')
        if universe is None:universe=p['universe'];columns=profile['feature_columns']
        if p['universe']!=universe or profile['feature_columns']!=columns:raise ValueError('Annual input contracts differ')
        if pd.Timestamp(p['training_config']['data']['training_end_date'])>=pd.Timestamp(int(year),1,1):raise ValueError('Future training')
        batch=f'model-factory-{stamp}-{uuid4().hex[:6]}'
        destination=Path('artifacts/models')/batch
        cfg=restore_config(TrainingConfig(),p['training_config'])
        cfg=replace(cfg,batch_id=batch,artifacts_dir=destination,
            oracle_path_directional_feature_mode='oracle')
        datasets={}
        for marker in sorted((source/'chunks').glob('*/done.json')):
            done=read(marker)
            for name,h in done['files'].items():
                original=marker.parent/name
                if digest(original)!=h:raise ValueError('Changed source dataset: '+str(original))
                target=destination/'oracle_path/chunks'/marker.parent.name/name
                link(original,target)
                datasets[str(target)]=h
            link(marker,destination/'oracle_path/chunks'/marker.parent.name/'done.json')
        models[year]=dict(batch_id=batch,root=str(destination/'oracle_path'),source_root=str(source),
            comment=f'Recherche Q051 H10 Oracle+LONG/SHORT 173 features, test {year}',
            source_batch=record['batch_id'],configuration=json.loads(json.dumps(asdict(cfg),default=str)),
            dataset_hashes=datasets,directional_years=[int(year)-1,int(year)],
            original_annual_record=record,benchmark=str(source/'directional/benchmark.parquet'))
    sources={str(p):digest(p) for base in ['modelFactory/oracle_path','modelFactory'] for p in (
        list(Path(base).glob('*.py')) if base.endswith('oracle_path') else [Path(base)/'config.py'])}
    sources[str(Path(__file__))]=digest(Path(__file__))
    atomic_json(ROOT/'protocol.json',dict(start='2021-01-01',end='2026-10-01',initial_equity=4000.,
        universe=universe,features=columns,models=models,sources=sources,
        training='Fresh Oracle folds and per-symbol LONG/SHORT fits, unchanged native hyperparameters',
        per_symbol_year_scope='Test year plus its preceding signal year; same fit/calibration boundaries, no unused earlier model years',
        profiles=['Q051_TOP10_SIMPLE','Q051_TOP10_VOL20_REGIME'],oracle_fraction=.10,long_top_n=10,
        min_long_probability=.50,min_long_auc=.50,provider_calls=0,LLM_calls=0,orders=0,
        production_changes=False,created_at_utc=datetime.now(timezone.utc).isoformat()))
    atomic_json(ROOT/'progress.json',dict(status='READY',annual_batches={y:r['batch_id'] for y,r in models.items()}))


def chunk_train(year,number):
    from modelFactory.config import TrainingConfig
    from modelFactory.oracle_path.directional import train
    plan=read(ROOT/'protocol.json');item=plan['models'][str(year)]
    root=Path(item['root']);work=root/'directional_jobs'/number;cfg=restore_config(TrainingConfig(),item['configuration'])
    marker=work/'directional/manifest.json'
    if marker.is_file() and read(marker).get('status')=='COMPLETED':return str(marker)
    work.mkdir(parents=True,exist_ok=True)
    for name in ['protocol.json','feature_profile.json']:link(root/name,work/name)
    link(root/'chunks'/number/'bars.parquet',work/'chunks'/number/'bars.parquet')
    f=pd.read_parquet(root/'directional_inputs'/f'{number}.parquet')
    benchmark=pd.read_parquet(item['benchmark'])
    def tick(phase,current,total,symbol):
        atomic_json(work/'progress.json',dict(status='RUNNING',completed=current,total=len(f.symbol.unique()),symbol=symbol))
    train(cfg,None,work,tick,oracle_features=f,benchmark=benchmark,years=item['directional_years'])
    atomic_json(work/'progress.json',dict(status='COMPLETED'))
    return str(marker)


def train_directions_parallel(year,root,progress,workers=4):
    from modelFactory.oracle_path.directional_features import training_matrix
    from modelFactory.oracle_path.directional import load_manifest
    root=Path(root);item=read(ROOT/'protocol.json')['models'][str(year)]
    if (root/'directional/manifest.json').is_file() and read(root/'directional/manifest.json').get('status')=='COMPLETED':
        return load_manifest(root)[0]
    matrix=training_matrix(root);inputs=root/'directional_inputs';inputs.mkdir(exist_ok=True)
    numbers=[]
    for path in sorted((root/'chunks').glob('*/bars.parquet')):
        number=path.parent.name;numbers.append(number)
        names=pd.read_parquet(path,columns=['symbol']).symbol.unique()
        matrix[matrix.symbol.isin(names)].to_parquet(inputs/f'{number}.parquet',index=False)
    del matrix
    manifests=[]
    def finished(number):
        manifests.append(root/'directional_jobs'/number/'directional/manifest.json')
        progress('directional_chunks',len(manifests),len(numbers),number)
    tasks=[(n,['--phase','chunk','--year',str(year),'--chunk',n],root/'directional_jobs'/n/'worker') for n in numbers]
    # This function's historical parameter name is retained for callers.
    globals()['workers'](tasks,workers,finished)
    records=[];skipped=[];source_hashes={};oos=[];template=None
    for path in sorted(manifests):
        work=path.parent.parent;m=read(path);template=m
        if m['features']!=read(root/'feature_profile.json')['feature_columns'] or len(m['features'])!=173:
            raise ValueError('Directional feature vector differs from Oracle')
        for r in m['models']:
            link(work/r['file'],root/r['file']);records.append(r)
        for r in m['oos_files']:
            link(work/r['path'],root/r['path']);oos.append(r)
        source_hashes.update(m['source_hashes']);skipped.extend(m['skipped'])
        link(work/m['benchmark_file'],root/m['benchmark_file'])
    template.update(models=records,skipped=skipped,source_hashes=source_hashes,oos_files=oos)
    atomic_json(root/'directional/manifest.json',template)
    return load_manifest(root)[0]


def train_year(year,oracle_lock=None):
    import requests
    from modelFactory.config import TrainingConfig
    from modelFactory.oracle_path.train import train_oracle_path
    from modelFactory.oracle_path import directional
    item=read(ROOT/'protocol.json')['models'][str(year)];root=Path(item['root'])
    cfg=restore_config(TrainingConfig(),item['configuration'])
    if (root/'report.json').is_file() and read(root/'report.json').get('status')=='completed':return item['batch_id']
    for p,h in read(ROOT/'protocol.json')['sources'].items():
        if digest(Path(p))!=h:raise ValueError('Changed campaign source: '+p)
    oracle_lock=oracle_lock or OracleMemorySlot();held=False
    def train_hook(cfg,engine,folder,progress):
        nonlocal held
        if held:
            oracle_lock.release();held=False
        return train_directions_parallel(year,folder,progress)
    def no_http(*a,**kw):raise ValueError('No network needed: frozen training inputs only')
    state=ROOT/f'{year}-progress.json'
    atomic_json(state,dict(status='WAITING_ORACLE_MEMORY_SLOT',batch_id=item['batch_id']))
    try:
        oracle_lock.acquire();held=True
        atomic_json(state,dict(status='TRAINING',batch_id=item['batch_id']))
        with patch.object(directional,'train',train_hook),patch.object(requests.Session,'request',no_http):
            result=train_oracle_path(cfg,None,item['batch_id'],read(ROOT/'protocol.json')['universe'])
        atomic_json(state,dict(status='TRAINED',batch_id=item['batch_id'],n_features=result['n_features'],
            directional_models=result['directional_models']))
        return item['batch_id']
    except BaseException as exc:
        atomic_json(state,dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)));raise
    finally:
        if held:oracle_lock.release()


def run_training():
    plan=read(ROOT/'protocol.json');results=[]
    def finished(year):
        results.append(dict(year=year,batch_id=plan['models'][year]['batch_id']))
        atomic_json(ROOT/'progress.json',dict(status='TRAINING_ANNUAL_BATCHES',completed=len(results),total=6,results=results))
    tasks=[(y,['--phase','year','--year',y],ROOT/(y+'-worker')) for y in plan['models']]
    workers(tasks,2,finished)
    atomic_json(ROOT/'progress.json',dict(status='SIX_BATCHES_TRAINED',results=results))


if __name__=='__main__':
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    p=argparse.ArgumentParser();p.add_argument('--phase',choices=['prepare','train','year','chunk'],required=True)
    p.add_argument('--year',type=int);p.add_argument('--chunk');a=p.parse_args()
    if a.phase=='prepare':prepare()
    elif a.phase=='train':run_training()
    elif a.phase=='year':train_year(a.year)
    else:chunk_train(a.year,a.chunk)
