"""Independent year precomputation for the authorized same-batch research replay."""
import argparse
from datetime import date
import json
import logging
from pathlib import Path
import shutil
from unittest.mock import patch

import requests
from threadpoolctl import threadpool_limits

from backtesting.isolation import ReadOnlyReplay
from backtesting.winner_campaign_replay import atomic_json
from modelFactory.oracle_path.predict import load_contract
from modelFactory.oracle_path.directional import load_manifest
from modelFactory.oracle_path.train import digest
from scripts.research.us_q051_same_batch_retrospective_20261114 import infer_year,latest_heads,MODE


def run(target,year):
    target=Path(target).resolve()
    base=json.loads((target/'protocol.json').read_text(encoding='utf-8'))
    if base.get('lookahead_authorized') is not True or base.get('evaluation_mode')!=MODE:
        raise ValueError('Contrat rétrospectif autorisé requis')
    current=Path('scripts/research/us_q051_same_batch_retrospective_20261114.py')
    if digest(current)!=base['source_script_sha256']:
        raise ValueError('Script de recherche changé depuis le lancement')
    start=max(date(year,1,1),date.fromisoformat(base['start']))
    end=min(date(year,12,31),date.fromisoformat(base['end']))
    from modelFactory.oracle.build_labels import nyse_sessions
    sessions=nyse_sessions(date.fromisoformat(base['start']),date.fromisoformat(base['end']))
    last=sessions[-2].date()
    end=min(end,last)
    folder=target/'workers'/str(year);folder.mkdir(parents=True,exist_ok=False)
    def progress(phase,n,total,day):
        atomic_json(folder/'progress.json',dict(status='RUNNING',phase=phase,completed=n,total=total,last_date=day))
    def no_http(*a,**kw):raise ValueError('Aucun appel fournisseur/broker')
    with ReadOnlyReplay(folder).install(),patch.object(requests.Session,'request',no_http),threadpool_limits(limits=1):
        model_root,protocol,profile,_=load_contract('artifacts/models',base['batch_id'])
        manifest,_=load_manifest(model_root)
        from database.connection import get_sqlalchemy_engine
        engine=get_sqlalchemy_engine(db_name='alpha_trade')
        progress('ORACLE_INFERENCE',0,0,str(end))
        output=folder/f'scores-{year}.parquet'
        infer_year(engine,model_root,protocol,profile,base['oracle_model'],latest_heads(manifest),start,end,output,progress)
        engine.dispose()
        atomic_json(folder/'progress.json',dict(status='COMPLETED',year=year))
    audit=json.loads((folder/'isolation.json').read_text())
    if audit['status']!='COMPLETED' or audit['violations']:
        raise ValueError('Isolation du worker non qualifiée')
    destination=target/output.name
    if destination.exists():
        # The main process may have reached the same year. Never overwrite it.
        atomic_json(folder/'publication.json',dict(status='NOT_PUBLISHED_MAIN_ALREADY_OWNS_YEAR',year=year))
        return
    temporary=target/(output.name+'.worker-tmp')
    shutil.copyfile(output,temporary)
    temporary.rename(destination)
    atomic_json(target/f'scores-{year}.seal.json',dict(sha256=digest(destination),evaluation_mode=MODE,
        worker=str(folder),worker_isolation_sha256=digest(folder/'isolation.json')))
    atomic_json(folder/'publication.json',dict(status='PUBLISHED',sha256=digest(destination)))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target-root',required=True)
    parser.add_argument('--year',required=True,type=int)
    args=parser.parse_args()
    logging.basicConfig(level=logging.WARNING)
    run(args.target_root,args.year)
