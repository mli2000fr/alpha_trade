"""Read only the official primary HTML of oversized KIM initial filing.

Technical per-document cap alternative; no retry of a refusal, no prices.
"""
import argparse
from datetime import datetime,timezone
from pathlib import Path

from scripts.research.us_activist_13d_confirmation import Client
from scripts.research.us_activist_13d_confirmation_replay import primary_name
from scripts.research.us_activist_13d_pilot import READ
from scripts.research.us_cash_merger_feasibility import visible
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest,verify_hashes


def run(root):
    parent=READ(root/'protocol.json');verify_hashes(Path('.'),parent['sources'])
    record=next(r for r in READ(root/'extraction.json')['rows'] if r['accession']=='0001140361-24-045053')
    if record['status']!='DOCUMENT_TOO_LARGE' or record['receipt'].get('http_status')!=200:
        raise ValueError('Only a technical size cap may use this supplement')
    out=root/'kim-primary-v1'
    if out.exists():
        raise ValueError('Fresh immutable source supplement required')
    out.mkdir();(out/'http').mkdir()
    files=[Path(__file__),root/'protocol.json',root/'extraction.json',Path('scripts/research/us_activist_13d_confirmation_replay.py')]
    atomic_json(out/'protocol.json',dict(created_at_utc=datetime.now(timezone.utc).isoformat(),reason='Original full submission hit20MiB, request primary official HTML only before price review, preserve first receipt',
        sources={str(f):digest(f) for f in files},accession=record['accession'],no_prices=True,not_a_refusal_bypass=True))
    client=Client(out,dict(parent['limits'],requests=2,document_bytes=8*1024*1024,total_bytes=10*1024*1024,max_seconds=120))
    cik=record['indexed_ciks'][0];acc=record['accession'];base=f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace("-","")}/'
    result=dict(accession=acc,status='UNKNOWN')
    try:
        body,receipt=client.get(base+acc+'-index.html');result['index_receipt']=receipt
        if body:
            name=primary_name(body,'SC TO-I');body,receipt=client.get(base+name);result['receipt']=receipt
            if body:
                result.update(status='PRIMARY_HTML_CAPTURED_NOT_ECONOMICALLY_TESTED',filename=name,text=visible(body.decode('utf-8',errors='replace')))
    finally:
        client.session.close()
    result.update(files={str(f.relative_to(out)):digest(f) for f in (out/'http').glob('*')})
    atomic_json(out/'report.json',result);print(result['status'],result.get('text','')[:1800],flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);run(p.parse_args().output)
