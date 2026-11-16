"""Recover publication only after a fully completed frozen Q051 replay.

The original driver marked completion after invoking an importer which requires
that mark first. Keep the sealed driver/protocol unchanged and retain incident
evidence; never rerun simulation or alter economic outputs for this repair.
"""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.us_q051_selection_variants_20261115 import ROOT,CASES,LABELS,WITNESS,read
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest


def finalize(name):
    folder=ROOT/'cases'/name;out=folder/'result';state=read(folder/'progress.json')
    if (state.get('status')!='FAILED' or state.get('error_type')!='ValueError'
            or state.get('error')!='Importer uniquement un replay terminé avec un bilan qualifié'):
        raise ValueError('Only the specific post-replay publication incident is eligible')
    for p,h in read(ROOT/'protocol.json')['sources'].items():
        if digest(Path(p))!=h:raise ValueError('Changed sealed input: '+p)
    r=read(out/'report.json');isolation=read(folder/'isolation.json')
    if (isolation['status']!='COMPLETED' or isolation.get('violations')
            or r['status'] not in ('INCOMPLETE_COVERAGE','COMPLETED_EXPLORATORY')
            or r['SQL_writes'] or r['provider_calls'] or r['orders']):raise ValueError('Replay not qualified')
    if read(out/'configuration.json')['portfolio']!=read(WITNESS/'result/configuration.json')['portfolio']:
        raise ValueError('Changed portfolio configuration')
    curve=pd.read_csv(out/'equity-daily.csv',index_col=0,parse_dates=True).equity
    annual=pd.read_csv(out/'annual-summary.csv');trades=pd.read_csv(out/'trades.csv')
    if (len(curve)!=1443 or str(curve.index[-1].date())!='2026-10-01'
            or not np.isclose(curve.iloc[-1],r['final_equity'],atol=1e-7)
            or len(trades)!=r['closed_lot_trades']
            or not np.isclose(4000*np.prod(1+annual.return_pct/100),r['final_equity'],atol=1e-6)):
        raise ValueError('Replay exports do not reconcile')
    files=['report.json','annual-summary.csv','trades.csv','events.csv','equity-daily.csv',
        'equity-5m.parquet','risk-5m.csv','configuration.json']
    hashes={name:digest(out/name) for name in files}
    receipt=dict(original_progress=state,reason='Completion flag must precede history import',
        replay_already_finished=True,economic_outputs_unchanged=True,source_hashes=hashes,
        finalizer_sha256=digest(Path(__file__)),observed_at_utc=datetime.now(timezone.utc).isoformat())
    with (folder/'publication-incident.json').open('x',encoding='utf-8') as f:json.dump(receipt,f,indent=2)
    atomic_json(folder/'progress.json',dict(status='COMPLETED_EXPLORATORY',publication_recovered=True))
    from ihm.services.backtesting_import import import_continuous_winner
    record=import_continuous_winner(folder,run_id='20261115_q051_vol20_'+name.lower(),
        label='Q051 vol20 + régime — '+LABELS[name]+' — annuel 2021–2026',result_subdir='result')
    atomic_json(folder/'ihm.json',dict(run_id=record['run_id']))
    if any(digest(out/n)!=h for n,h in hashes.items()):raise ValueError('Publication changed economic files')
    print(json.dumps(dict(status='COMPLETED_EXPLORATORY',run_id=record['run_id'],economic_outputs_unchanged=True)))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--case',choices=list(CASES),required=True)
    finalize(p.parse_args().case)
