"""Bounded EODHD reread and local metadata; research archives, no SQL writes."""
import argparse
from datetime import datetime,timezone
from pathlib import Path
import ssl

import pandas as pd
import requests
from sqlalchemy import text,bindparam

from database.connection import get_sqlalchemy_engine
from service.eodhd.clientEodhd import fetch_eod,fetch_splits
from service.eodhd.quota import EodhdQuotaTracker
from modelFactory.features import compute_features
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest


def run(source,output):
    output.mkdir(parents=True,exist_ok=False)
    bars=pd.read_parquet(source/'suspect-bars.parquet')
    engine=get_sqlalchemy_engine(db_name='alpha_trade')
    if engine.url.database!='alpha_trade':
        raise ValueError('US database required')
    symbols=sorted(bars.symbol.unique())
    queries={
        'instruments':'SELECT instrument_id,market_code,exchange_mic,local_symbol,display_name,listing_date,delisting_date,mapping_status FROM instruments WHERE local_symbol IN :symbols',
        'actions':'SELECT provider,symbol,ca_type,ex_date,split_from,split_to,amount_per_share FROM corporate_actions_events WHERE symbol IN :symbols AND ex_date BETWEEN :start AND :end'}
    for name,query in queries.items():
        with engine.connect() as conn:
            conn.exec_driver_sql('SET TRANSACTION READ ONLY')
            frame=pd.read_sql(text(query).bindparams(bindparam('symbols',expanding=True)),conn,
                params=dict(symbols=symbols,start='2018-01-01',end='2019-12-31'))
        frame.to_parquet(output/(name+'.parquet'),index=False)
    # Replicate the shared feature generator, not just the three diagnostic formulas.
    parts=[]
    for symbol,group in bars.groupby('symbol'):
        feats=compute_features(group,feature_set='expert',include_factors=True)
        feats['symbol']=symbol
        parts.append(feats)
    pd.concat(parts,ignore_index=True).to_parquet(output/'shared-generator-features.parquet',index=False)
    session=requests.Session()
    trust=output/'windows-trust.pem'
    trust.write_text(''.join(ssl.DER_cert_to_PEM_cert(c) for c in ssl.create_default_context().get_ca_certs(binary_form=True)),encoding='ascii')
    session.verify=str(trust.resolve())
    tracker=EodhdQuotaTracker(cache_dir=output/'provider-quota')
    windows={'KNTK':('2018-11-01','2018-12-03'),'AMTB':('2018-10-01','2018-11-15')}
    results=[]
    try:
        for symbol,(start,end) in windows.items():
            row=dict(symbol=symbol,start=start,end=end)
            for name,fetcher in [('bars',fetch_eod),('splits',fetch_splits)]:
                try:
                    payload=fetcher(symbol,start=start,end=end,session=session,tracker=tracker,feature='oracle_outlier_audit')
                    path=output/f'{symbol}-{name}.json'
                    atomic_json(path,payload)
                    row[name]=dict(status='RECEIVED',count=len(payload),sha256=digest(path))
                except Exception as exc:
                    # Never archive request URLs containing API keys.
                    row[name]=dict(status='FAILED',error_type=type(exc).__name__)
            results.append(row)
    finally:
        session.close()
    atomic_json(output/'report.json',dict(status='COMPLETED_EVIDENCE_RECHECK',provider_results=results,
        observed_at=datetime.now(timezone.utc).isoformat(),sql_writes=False,training=False,
        caveats=['Vendor reread is same-source, not independent or historical vintage proof',
                 'Generator recheck omits selector context and benchmark; three suspect price formulas unchanged',
                 'Current instrument listing dates are not full historical identity certification']))
    print(results)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    run(args.source,args.output)
