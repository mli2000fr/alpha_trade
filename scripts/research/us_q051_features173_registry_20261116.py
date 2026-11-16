"""Publish only this campaign's completed new model metadata; no model activation."""
import argparse
from datetime import date,datetime,timezone
import json
from pathlib import Path
import time

from scripts.research.us_q051_features173_20261116 import ROOT,read
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest


def register(year=None):
    from sqlalchemy import text
    from database.connection import get_sqlalchemy_engine
    from modelFactory.db_registry import insert_training_batch,update_training_batch
    from modelFactory.oracle_path.predict import load_contract
    from modelFactory.oracle_path.directional import load_manifest
    from common.run_market_scope import resolve_run_market_scope,compute_scope_universe_fingerprint
    plan=read(ROOT/'protocol.json');engine=get_sqlalchemy_engine();receipts=[]
    for y,item in plan['models'].items():
        if year is not None and int(y)!=year:continue
        root,p,profile,folds=load_contract('artifacts/models',item['batch_id'])
        manifest,mhash=load_manifest(root)
        if len(profile['feature_columns'])!=173 or manifest['features']!=profile['feature_columns']:
            raise ValueError('Completed 173-input contract required')
        cfg=p['training_config'];data=cfg['data'];batch=item['batch_id']
        command=['python','-X','utf8','-m','scripts.research.us_q051_features173_20261116','--phase','year','--year',y]
        symbol_source='universe-file:univers_filtred_tradable.txt'
        meta=dict(market_context=resolve_run_market_scope('US_EQ').as_manifest(),
            cli_options=dict(mode='train',oracle_path_model_only=True,oracle_path_directional=True,
                oracle_path_directional_features='oracle',oracle_horizon=10,market_code='US_EQ',symbol_source=symbol_source),
            training_config=cfg,feature_columns=profile['feature_columns'],
            research_campaign=str(ROOT),directional_manifest_sha256=mhash,
            oracle_protocol_sha256=digest(root/'protocol.json'),test_year=int(y),
            fresh_oracle_fits=True,fresh_directional_fits=True,dataset_reused_from=item['source_batch'],
            directional_models=len(manifest['models']),directional_skipped=len(manifest['skipped']),
            per_symbol_features=173,production_activation=False)
        with engine.connect() as conn:
            prior=conn.execute(text('SELECT status,metadata_json FROM model_training_batch WHERE batch_id=:bid'),{'bid':batch}).mappings().first()
        if prior:
            previous=json.loads(prior['metadata_json']) if isinstance(prior['metadata_json'],str) else prior['metadata_json']
            if previous!=meta:raise ValueError('Existing batch metadata differs; refuse overwrite: '+batch)
        else:
            insert_training_batch(engine,batch_id=batch,command_line=' '.join(command),command_argv_json=json.dumps(command),
                metadata_json=json.dumps(meta,default=str,ensure_ascii=False),symbol_source=symbol_source,
                universe_date=None,requested_symbol_count=len(p['universe']),
                training_start_date=date.fromisoformat(data['training_start_date']),training_end_date=date.fromisoformat(data['training_end_date']),
                started_at=datetime.fromisoformat(plan['created_at_utc']).replace(tzinfo=None),comment=item['comment'],
                market_code='US_EQ',universe_id=symbol_source,
                universe_fingerprint=compute_scope_universe_fingerprint(market_code='US_EQ',symbol_source=symbol_source,
                    universe_date=None,symbols=p['universe']),symbols=','.join(p['universe'])[:5000])
        update_training_batch(engine,batch,status='completed',finished_at=datetime.fromtimestamp((root/'report.json').stat().st_mtime,timezone.utc).replace(tzinfo=None),
            symbols_completed=1,symbols_skipped=0,symbols_failed=0)
        receipts.append(dict(year=int(y),batch_id=batch,status='completed',directional_models=len(manifest['models']),
            feature_count=173,production_activation=False))
    atomic_json(ROOT/('registry-'+str(year)+'.json' if year else 'registry.json'),dict(status='REGISTERED',batches=receipts))
    return receipts


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--year',type=int);p.add_argument('--wait',action='store_true');a=p.parse_args()
    if not a.wait:print(json.dumps(register(a.year)))
    else:
        receipts=[]
        for y,item in read(ROOT/'protocol.json')['models'].items():
            while True:
                file=ROOT/(y+'-progress.json');state=read(file) if file.exists() else {}
                if state.get('status')=='FAILED':raise RuntimeError('Annual training failed: '+y)
                if state.get('status')=='TRAINED':break
                time.sleep(10)
            receipts.extend(register(int(y)))
            print('Registered',y,item['batch_id'],flush=True)
        atomic_json(ROOT/'registry.json',dict(status='REGISTERED',batches=receipts))
