"""Frozen price-source-only child; preserves failed parent and all feature rules."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
from pathlib import Path
import shutil

import pandas as pd
from sqlalchemy import bindparam,text

from scripts.research import us_consensus_reliability_20261022 as parent

CHILD=parent.ROOT/'sip-only-v2'
AMENDMENT=Path('doc/ml/consensus_fiabilite_sip_amendement_20261022.md')


def sip_only(prices):
    result=prices[prices.data_source.eq('alpaca_sip')].copy()
    if result.empty:raise ValueError('No SIP prices; no fallback')
    if result.duplicated(['symbol','date']).any():raise ValueError('Duplicate within SIP')
    return result


def prepare(root):
    parent.check(parent.ROOT)
    if root.exists():raise FileExistsError('Fresh child required')
    for ready in ('snapshot-ready.json','features-ready.json','prices-ready.json'):
        for name,h in parent.read(parent.ROOT/ready)['files'].items():
            if parent.digest(parent.ROOT/name)!=h:raise ValueError('Parent changed')
    root.mkdir(parents=True)
    for name in ('inventory.json','consensus.parquet','runs.parquet','price-schema.json',
                 'snapshot-ready.json','features.parquet','row-quality.parquet',
                 'proof-request.parquet','features-ready.json','raw-proof-receipts.parquet'):
        shutil.copy2(parent.ROOT/name,root/name)
    p=parent.read(parent.ROOT/'protocol.json')
    p['parent']=str(parent.ROOT)
    p['amendment']='SIP-only source selection before any returns; same original cutoff/features; no provider fallback'
    p['amendment_created_at_utc']=datetime.now(timezone.utc).isoformat()
    for path in (Path(__file__),AMENDMENT,Path('tests/test_us_consensus_reliability_sip_20261022.py')):
        p['sources'][str(path)]=parent.digest(path)
    parent.save(root/'protocol.json',p)
    original=pd.read_parquet(parent.ROOT/'prices.parquet')
    selected=sip_only(original)
    selected.to_parquet(root/'prices.parquet',index=False)
    parent.save(root/'prices-ready.json',dict(rows=len(selected),
        selection='alpaca_sip only; no returns consulted',parent_rows=len(original),
        removed_other_provider_rows=len(original)-len(selected),
        files={n:parent.digest(root/n) for n in ('prices.parquet','raw-proof-receipts.parquet')}))
    print('SIP child',len(selected),'rows; features unchanged',flush=True)


def anomaly_proofs(root):
    parent.check(root)
    folder=root/'anomaly-proof'
    if folder.exists():raise FileExistsError('Immutable anomaly proof')
    folder.mkdir()
    q=pd.read_parquet(root/'row-quality.parquet')
    rows=pd.read_parquet(root/'consensus.parquet')
    bad=rows[rows.id.isin(q.loc[~q.eps_range_ok|~q.revenue_range_ok|~q.raw_normalization_ok,'id'])].copy()
    parent.save(folder/'protocol.json',dict(created_at_utc=datetime.now(timezone.utc).isoformat(),
        cohort='All raw-quality anomalies before any new outcome-based selection',
        parent_protocol_sha256=parent.digest(root/'protocol.json'),rows=len(bad),
        source_sha256=parent.digest(Path(__file__)),sql_writes=False,api_calls=0))
    bad.to_parquet(folder/'anomaly-items.parquet',index=False)
    engine,conn=parent.connect_readonly()
    receipts=[]
    try:
        for run,g in bad.groupby('run_id'):
            stamps=[parent.utc(t).tz_localize(None).to_pydatetime() for t in g.observed_at.unique()]
            stmt=text('''SELECT id,run_id,observed_at,available_at,http_status,payload_hash,payload_json
                FROM pit_raw_payloads WHERE batch_name='eodhd_consensus_snapshot' AND provider='eodhd'
                AND endpoint='/calendar/trends' AND run_id=:run AND observed_at IN :stamps
                ORDER BY id LIMIT 1001''').bindparams(bindparam('stamps',expanding=True))
            found=[dict(r) for r in conn.execute(stmt,dict(run=run,stamps=stamps)).mappings()]
            if len(found)>1000:raise ValueError('Anomaly receipt truncation')
            receipts.extend(found)
        conn.rollback()
    finally:conn.close();engine.dispose()
    frame=pd.DataFrame(receipts)
    frame.to_parquet(folder/'receipts.parquet',index=False)
    matches=set();invalid=[]
    for row in frame.to_dict('records'):
        obj=parent.json.loads(row['payload_json'])
        if row['http_status']!=200 or parent.payload_hash(obj)!=row['payload_hash']:
            invalid.append(row['id']);continue
        for group in obj['trends']:
            for item in group:matches.add((row['run_id'],parent.utc(row['observed_at']),parent.payload_hash(item)))
    bad['found_exact_in_envelope']=[(r.run_id,parent.utc(r.observed_at),r.raw_hash) in matches for r in bad.itertuples()]
    bad.to_csv(folder/'verified-anomalies.csv',index=False)
    result=dict(status='COMPLETED_ANOMALY_SOURCE_CHECK',rows=len(bad),
        verified=int(bad.found_exact_in_envelope.sum()),symbols=sorted(bad.symbol.unique()),
        envelopes=len(frame),invalid_envelopes=invalid,sql_writes=False,api_calls=0,
        files={p.name:parent.digest(p) for p in folder.iterdir() if p.is_file()})
    parent.save(folder/'report.json',result)
    print('Anomaly source proofs',result['verified'],'/',len(bad),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',required=True,choices=('prepare','anomaly-proofs','finalize'))
    parser.add_argument('--output-dir',type=Path,default=CHILD)
    a=parser.parse_args()
    {'prepare':prepare,'anomaly-proofs':anomaly_proofs,'finalize':parent.finalize}[a.phase](a.output_dir)
