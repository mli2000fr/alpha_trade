"""Research-only SIP price corroboration and identical-signal replay.

Uses the pre-existing flagged-symbol list, never a list chosen from trade PnL.
No SQL writes, model refits, risk changes or orders. Raw experiment preserved.
"""
import argparse
from copy import deepcopy
from datetime import datetime,timezone
import json
from pathlib import Path
import time
from unittest.mock import patch

import numpy as np
import pandas as pd

from scripts.research import us_q051_features173_replay_20261116 as base
from scripts.research.us_q051_features173_20261116 import read,shared,link
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest
from scripts.research.us_h10_price_readiness import FLAGGED

RAW=base.ROOT
ROOT=RAW.parent/'20261116-v3-sip'
CASES=['SIMPLE','VOL20_REGIME','CONTROL_SIMPLE','CONTROL_VOL20_REGIME']


def fetch(account='test1'):
    from common.verified_http import verified_session
    from service.alpaca.clientAlpaca import _build_headers
    from scripts.research.us_q051_vol20_regime_h5_20261115 import market_data
    from service._http_retry import request_with_retry,RetryPolicy
    prices,_,_=market_data();start=prices['close'].index.min().strftime('%Y-%m-%d')
    folder=ROOT/'evidence';folder.mkdir(parents=True,exist_ok=True)
    with verified_session() as session:
        for symbol in FLAGGED:
            if symbol=='TOELY':continue  # Existing evidence: unsupported ADR, no invented basis.
            path=folder/(symbol+'.json')
            if path.is_file():continue
            params=dict(symbols=symbol,timeframe='1Day',feed='sip',adjustment='split',asof='-',
                start=start+'T00:00:00Z',end='2026-10-02T00:00:00Z',limit=10000,sort='asc')
            time.sleep(.8)
            response=request_with_retry(session,'GET','https://data.alpaca.markets/v2/stocks/bars',
                headers=_build_headers(account),params=params,policy=RetryPolicy(max_attempts=3,timeout_seconds=45))
            payload=response.json()
            if payload.get('next_page_token'):raise ValueError('Unexpected truncation: bounded evidence refuses partial history')
            if set(payload.get('bars',{}))-{symbol}:raise ValueError('Unexpected evidence identity')
            atomic_json(path,dict(status='COMPLETED',symbol=symbol,params=params,body=payload,
                account_id=account,
                observed_at_utc=datetime.now(timezone.utc).isoformat(),http_status=response.status_code))
            atomic_json(ROOT/'fetch-progress.json',dict(status='FETCHING',symbol=symbol,completed=len(list(folder.glob('*.json'))),total=len(FLAGGED)-1))
    atomic_json(ROOT/'fetch-progress.json',dict(status='COMPLETED',provider_calls=len(list(folder.glob('*.json')))))


def provider_frame(path):
    data=read(path);symbol=data['symbol'];bars=data['body'].get('bars',{}).get(symbol,[])
    if not bars:return pd.DataFrame(columns=['date','symbol','open','high','low','close','volume'])
    f=pd.DataFrame(bars).rename(columns=dict(t='date',o='open',h='high',l='low',c='close',v='volume'))
    f['date']=pd.to_datetime(f.date,utc=True).dt.tz_convert('America/New_York').dt.tz_localize(None).dt.normalize()
    f['symbol']=symbol
    for c in ['open','high','low','close','volume']:f[c]=pd.to_numeric(f[c],errors='coerce')
    if f.duplicated(['date','symbol']).any():raise ValueError('Duplicate provider daily bar')
    valid=f[['open','high','low','close']].gt(0).all(axis=1)&f.volume.ge(0)
    valid &= f.high.ge(f[['open','low','close']].max(axis=1))&f.low.le(f[['open','high','close']].min(axis=1))
    if not valid.all():raise ValueError('Invalid SIP evidence OHLC')
    return f[['date','symbol','open','high','low','close','volume']].sort_values('date')


def prepare():
    from scripts.research.us_q051_vol20_regime_h5_20261115 import market_data
    from scripts.research.us_q051_classic_top10_20261115 import meaningful
    if (ROOT/'replay-protocol.json').exists():raise ValueError('Already sealed SIP replay')
    pivots,sectors,actions=market_data();inputs=ROOT/'inputs';inputs.mkdir(parents=True,exist_ok=True)
    replacements={};evidence_hashes={};ledger=[];coverage=[]
    for path in sorted((ROOT/'evidence').glob('*.json')):
        frame=provider_frame(path);symbol=read(path)['symbol'];evidence_hashes[str(path)]=digest(path)
        if symbol not in pivots['open'].columns:
            coverage.append(dict(symbol=symbol,status='OUTSIDE_REPLAY_PRICE_UNIVERSE',matched=0));continue
        if frame.empty:
            coverage.append(dict(symbol=symbol,status='NO_PROVIDER_HISTORY',matched=0));continue
        frame=frame[frame.date.isin(pivots['open'].index)]
        replacements[symbol]=frame
        old=pd.DataFrame({c:pivots[c][symbol] for c in ['open','high','low','close','volume']}).rename_axis('date').reset_index()
        joined=old.merge(frame,on='date',suffixes=('_old','_sip'),validate='one_to_one')
        values=np.column_stack([joined[c+'_sip']/joined[c+'_old']-1 for c in ['open','high','low','close']])
        changed=np.nanmax(np.abs(values),axis=1)>1e-6
        for r,delta in zip(joined.loc[changed].to_dict('records'),np.nanmax(np.abs(values[changed]),axis=1)):
            ledger.append(dict(symbol=symbol,date=str(r['date'].date()),maximum_ohlc_relative_difference=float(delta),
                old_open=r['open_old'],new_open=r['open_sip'],old_close=r['close_old'],new_close=r['close_sip']))
        for c in pivots:pivots[c].loc[frame.date,symbol]=frame.set_index('date')[c]
        coverage.append(dict(symbol=symbol,status='SIP_PRICE_LEVELS_SUBSTITUTED_ON_EXACT_DATES',matched=len(joined),changed=int(changed.sum())))
    pd.DataFrame(ledger).to_csv(inputs/'normalization-ledger.csv',index=False)
    # Keep wide pivots exactly; never fill a missing provider price or modify signals.
    for c,f in pivots.items():f.to_parquet(inputs/(c+'.parquet'))
    sectors.to_parquet(inputs/'sectors.parquet',index=False);actions.to_parquet(inputs/'actions.parquet',index=False)
    for name in ['signals.parquet','control-signals.parquet']:link(RAW/'inputs'/name,inputs/name)
    plan=read(RAW/'replay-protocol.json');plan=deepcopy(plan)
    plan.update(source_raw_campaign=str(RAW),price_requalification=dict(pre_existing_flags=FLAGGED,
        no_new_symbol_exclusion=True,no_model_refit=True,signals_unchanged=True,
        official_DD_reverse_split='2026-06-24 1-for-3',
        source='https://www.dupont.com/news/dupont-announces-reverse-stock-split-and-reaffirms-2026-financial-guidance.html',
        unresolved_spinoff=dict(symbol='DD',date='2025-11-03',policy='Audit actual held windows; never invent missing entitlement cash'),
        coverage=coverage,evidence=evidence_hashes))
    plan['sources']={str(Path(base.__file__)):digest(Path(base.__file__)),str(Path(__file__)):digest(Path(__file__)),**evidence_hashes}
    for file in inputs.glob('*.parquet'):plan['sources'][str(file)]=digest(file)
    plan['sources'][str(inputs/'normalization-ledger.csv')]=digest(inputs/'normalization-ledger.csv')
    for d,pattern in [('backtesting','*.py'),('risk_management','*.py'),('common','winner*.py')]:
        plan['sources'].update({str(p):digest(p) for p in Path(d).glob(pattern)})
    atomic_json(ROOT/'replay-protocol.json',plan)
    atomic_json(ROOT/'price-input-audit.json',dict(status='SIP_LEVELS_CORROBORATED_CORPORATE_ACTION_WINDOWS_PENDING',
        changed_rows=len(ledger),coverage=coverage,signals_unchanged=True,price_exclusions_added=False,
        raw_inputs_preserved=True,model_refits=0,SQL_writes=0))
    atomic_json(ROOT/'progress.json',dict(status='READY',cases=CASES))


def market_data():
    inputs=ROOT/'inputs'
    return ({c:pd.read_parquet(inputs/(c+'.parquet')) for c in ['open','high','low','close','volume']},
        pd.read_parquet(inputs/'sectors.parquet'),pd.read_parquet(inputs/'actions.parquet'))


def run_case(name):
    from ihm.services import backtesting_import
    from scripts.research import us_q051_vol20_regime_h5_20261115 as market_module
    original=backtesting_import.import_continuous_winner
    folder=ROOT/'cases'/name
    def deferred(source,**kw):
        kw['run_id']=kw['run_id']+'_sip';kw['label']=kw['label']+' — recoupement SIP'
        atomic_json(folder/'import-ready.json',dict(status='WAITING_PUBLICATION_RELEASE',run_id=kw['run_id']))
        while not (folder/'import-release.json').is_file():time.sleep(1)
        result=original(source,**kw)
        atomic_json(folder/'import-completed.json',dict(status='PUBLISHED',run_id=result['run_id']))
        return result
    with patch.object(base,'ROOT',ROOT),patch.object(market_module,'market_data',market_data),\
            patch.object(backtesting_import,'import_continuous_winner',deferred):
        base.run_case(name)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--phase',choices=['fetch','prepare','case'],required=True)
    p.add_argument('--account',default='test1')
    p.add_argument('--case',choices=CASES);a=p.parse_args()
    if a.phase=='fetch':fetch(a.account)
    elif a.phase=='prepare':prepare()
    else:run_case(a.case)
