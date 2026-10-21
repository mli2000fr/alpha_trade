"""Offline source audit only, not an event or economic validation."""
import argparse
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
import json

from bs4 import BeautifulSoup
from scripts.research.us_index_deletion_feasibility import allowed,nearby
from scripts.research.us_index_deletion_source_check import echoed_terms
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest,verify_hashes

READ=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))


def audit(prior,control):
    target=control/'audit.json'
    if target.exists():
        raise ValueError('Immutable source audit')
    receipts=[];reports=[]
    for root in [prior,control]:
        p=READ(root/'protocol.json');verify_hashes(Path('.'),p['sources'])
        report=READ(root/'report.json');verify_hashes(root,report['files']);reports.append(report)
        local=[READ(f) for f in (root/'http').glob('*.json')]
        if len(local)!=report['new_requests'] or sum(x['streamed_bytes'] for x in local)!=report['streamed_bytes']:
            raise ValueError('Request counters mismatch')
        for receipt in local:
            if not allowed(receipt['url']):
                raise ValueError('Non-SEC source request')
            if receipt['status']=='OK' and digest(root/receipt['file'])!=receipt['sha256']:
                raise ValueError('Original changed')
        receipts.extend(local)
    initial=reports[0];final=reports[1]
    for s in initial['searches']:
        terms=echoed_terms(READ(prior/s['receipt']['file']))
        if 'AND' not in terms or '(' not in terms:
            raise ValueError('Initial query issue not reproduced')
    positives=[]
    for s in final['searches']:
        payload=READ(control/s['receipt']['file']);hits=payload['hits']['hits'];total=payload['hits']['total']
        if len(hits)!=s['returned'] or total!=s['total_hits'] or echoed_terms(payload)!=s['echoed_terms']:
            raise ValueError('Search controls mismatch')
        if s['status']!='VALIDATED_SIMPLE_QUERY':
            raise ValueError('Unqualified search semantics')
        if s['query']=='"Russell"':
            positives.append(total['value']>0)
        if not s['truncated']:
            raise ValueError('Expected limited pages explicitly disclosed')
    if positives!=[True]:
        raise ValueError('No positive search control')
    selection=READ(control/'selected-disclosures.json')['rows']
    if [r['url'] for r in selection]!=[r['url'] for r in final['originals']]:
        raise ValueError('Silent source replacement')
    for original in final['originals']:
        receipt=original['receipt'];body=(control/receipt['file']).read_bytes()
        text=BeautifulSoup(body,'html.parser').get_text(' ',strip=True)
        if nearby(text)!=original['nearby_mentions'] or original['status']!='DISCOVERY_ONLY_NOT_ADMITTED':
            raise ValueError('Discovery promoted or extraction changed')
    result=dict(status='PASS_SOURCE_CHECK_ONLY_NO_BACKTEST_AUTHORIZED',finished_at_utc=datetime.now(timezone.utc).isoformat(),
        total_sec_requests=len(receipts),total_streamed_bytes=sum(r['streamed_bytes'] for r in receipts),
        http_status_counts=dict(Counter(str(r.get('http_status')) for r in receipts)),
        raw_originals_checked=len(selection),initial_query_zero_not_valid_event_count=True,
        issuer_probe_truncated_and_not_census=True,qualified_event_count_not_estimated=True,
        provider_dataset_downloads_by_scripts=0,performance_computed=False,
        same_assistant_not_independent_human=True,
        sources={str(Path(__file__)):digest(Path(__file__)),str(prior/'report.json'):digest(prior/'report.json'),str(control/'report.json'):digest(control/'report.json')})
    atomic_json(target,result);print(result,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prior',type=Path,required=True);p.add_argument('--control',type=Path,required=True)
    args=p.parse_args();audit(args.prior,args.control)
