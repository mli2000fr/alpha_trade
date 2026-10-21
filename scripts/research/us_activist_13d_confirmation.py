"""Outcome-blind initial13D confirmation, 2025 and 2026Q1-Q3.

New sealed research outputs only. Never writes SQL, trains, calls LLMs or orders.
Existing 2024 artifacts/scripts are preserved. Local current-universe survivor
bias and a deterministic outside-route probe are disclosed, not hidden.
"""
import argparse
from collections import Counter
from datetime import datetime,timezone
import hashlib
import os
from pathlib import Path
import re
import time
from urllib.parse import urlsplit

from common.public_data_http import verified_session
from scripts.research.us_activist_13d_pilot import READ,UNIVERSE,MAPPING,Stopped,parse
from scripts.research.us_activist_13d_extension import parse_quarter,distinct,choose,reuse
from scripts.research.us_activist_13d_extension_review import section4
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest,verify_hashes

PRIOR=Path('artifacts/research/us_activist_13d/extension-2024-20261020-v1')


def allowed(url):
    u=urlsplit(url)
    return u.scheme=='https' and u.netloc=='www.sec.gov' and not u.query and not u.fragment and bool(re.fullmatch(
        r'/Archives/edgar/(?:full-index/202[56]/QTR[1-4]/master.gz|data/\d+/(?:\d{10}-\d{2}-\d{6}\.txt|\d{18}/[A-Za-z0-9_.-]+\.html?))',u.path))


class Client:
    def __init__(self,root,limits):
        agent=os.getenv('SEC_EDGAR_USER_AGENT','').strip()
        if '@' not in agent or 'example.com' in agent:
            raise Stopped('REAL_IDENTIFIED_SEC_CONTACT_REQUIRED')
        self.root,self.limits=root,limits
        self.session=verified_session();self.session.headers['User-Agent']=agent
        receipts=[READ(f) for f in (root/'http').glob('*.json')]
        self.calls=sum(not r.get('reused_from') for r in receipts)
        self.bytes=sum(r.get('streamed_bytes',0) for r in receipts if not r.get('reused_from'))
        self.last,self.started=0.,time.monotonic()

    def get(self,url):
        if not allowed(url):
            raise ValueError('Outside bounded SEC allowlist')
        key=hashlib.sha256(url.encode()).hexdigest();file=self.root/'http'/f'{key}.json'
        if file.exists():
            r=READ(file)
            if r.get('http_status') in [403,429] or r['status']=='ACCESS_CHALLENGE':
                raise Stopped('PREVIOUS_REFUSAL_NO_RETRY')
            if r['status']=='OK':
                target=self.root/r['file']
                if digest(target)!=r['sha256']:
                    raise ValueError('Archived source changed')
                return target.read_bytes(),r
            return None,r
        b=self.limits
        if self.calls>=b['requests'] or self.bytes>=b['total_bytes'] or time.monotonic()-self.started>b['max_seconds']:
            raise Stopped('BOUNDED_ACQUISITION_LIMIT')
        time.sleep(max(0,b['interval_seconds']-(time.monotonic()-self.last)))
        self.last=time.monotonic();self.calls+=1
        r=dict(url=url,retrieved_at_utc=datetime.now(timezone.utc).isoformat(),attempts=1,streamed_bytes=0,status='UNFINISHED')
        body,stop=None,None
        try:
            with self.session.get(url,timeout=(10,30),stream=True,allow_redirects=False) as response:
                r['http_status']=response.status_code
                if response.status_code in [403,429]:
                    r['status'],stop='ACCESS_REFUSED','SEC_REFUSAL_NO_BYPASS'
                elif response.status_code!=200:
                    r['status']='HTTP_UNAVAILABLE_NO_RETRY'
                else:
                    data=bytearray()
                    for chunk in response.iter_content(65536):
                        data.extend(chunk);r['streamed_bytes']+=len(chunk);self.bytes+=len(chunk)
                        if self.bytes>b['total_bytes']:
                            r['status'],stop='TOTAL_BYTES_LIMIT','BOUNDED_ACQUISITION_LIMIT';break
                        if len(data)>b['document_bytes']:
                            r['status']='DOCUMENT_TOO_LARGE';break
                    else:
                        if any(t in bytes(data[:3500]).lower() for t in [b'access denied',b'undeclared automated tool']):
                            r['status'],stop='ACCESS_CHALLENGE','SEC_REFUSAL_NO_BYPASS'
                        else:
                            body=bytes(data);target=self.root/'http'/f'{key}.body';target.write_bytes(body)
                            r.update(status='OK',file=str(target.relative_to(self.root)),sha256=digest(target),bytes=len(body))
        except Exception as exc:
            r.update(status='TECHNICAL_FAILURE_NO_RETRY',error_type=type(exc).__name__)
        atomic_json(file,r)
        if stop:
            raise Stopped(stop)
        return body,r


def mapping():
    universe={s for s in re.split(r'[,;\s]+',UNIVERSE.read_text(encoding='utf-8-sig').strip()) if s}
    mapped,allmapped={},{}
    for r in READ(MAPPING).values():
        cik=str(r['cik_str']).zfill(10)
        allmapped.setdefault(cik,set()).add(r['ticker'])
        if r['ticker'] in universe:
            mapped.setdefault(cik,set()).add(r['ticker'])
    return universe,mapped,allmapped


def prepare(root):
    if (root/'protocol.json').exists():
        p=READ(root/'protocol.json');verify_hashes(Path('.'),p['sources']);return p
    if root.exists():
        raise ValueError('Fresh confirmation directory required')
    files=[Path(__file__),Path('tests/test_us_activist_13d_confirmation.py'),UNIVERSE,MAPPING,
           Path('scripts/research/us_activist_13d_pilot.py'),Path('scripts/research/us_activist_13d_extension.py'),
           Path('scripts/research/us_activist_13d_extension_review.py'),PRIOR/'protocol.json',PRIOR/'selection.json']
    p=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),sources={str(f):digest(f) for f in files},
           years={2025:[1,2,3,4],2026:[1,2,3]},event_end='2026-09-30',price_end='2026-09-30',
           selection='All distinct initial13D with ANY indexedCIK in CURRENT1790mapping in complete prescribed quarters. '
                     'Plus10outside-route perquarter smallestSHA256(accession), dedupcofilers BEFORE selection, no return/prices filter. '
                     'Currentmapping survivor bias not corrected; outsideprobe NOT a historical delisted census. Do not complete an incomplete year with assumedzeroevents.',
           semantics=READ(PRIOR/'protocol.json')['semantics'],
           timing='Next fullNYSEopen strictly after filingdate and afteracceptance. BlocksameCIK60sessions BEFORE outcomequality across2025/2026. '
                  'No worldwide firstannouncement/localhistoricalreceipt claim.2024observed cannot be advertised as unseenvalidation.',
           economic=READ(PRIOR/'protocol.json')['economic'],
           outcome='Existing frozen normalizedresearchbars only, availablethroughSep30. H20/H60includeentry. Immature, missingprice or unsupportedhistoricalclass '
                   'UNKNOWN notzero/loss, no replacement or exclusionfromadmitteddenominator.2026partialyear notannualreturn. No newpriceAPI.',
           oracle='Exact frozen PATH_H20 researchscores on lastNYSEclose beforeentry; contextonly. Missingrank isUNKNOWN, notnonTOP10. No futurelabels read for selection.',
           limits=dict(requests=420,total_bytes=420*1024*1024,document_bytes=40*1024*1024,interval_seconds=.6,max_seconds=2400),
           noncurrent_probe_per_quarter=10,no_sql=True,no_llm=True,no_training=True,no_orders=True,no_production_changes=True)
    root.mkdir(parents=True);(root/'http').mkdir();atomic_json(root/'protocol.json',p)
    for index in READ(PRIOR/'selection.json')['indexes']:
        if index['year']==2025:
            reuse(root,index['receipt'],PRIOR)
    return p


def indexes(root):
    p=prepare(root)
    if (root/'selection.json').exists():
        raise ValueError('Immutable selection')
    universe,mapped,_=mapping();client=Client(root,p['limits'])
    allrows={};summaries=[];stop=None;year_status={}
    try:
        for year,quarters in p['years'].items():
            year=int(year);allrows[year]=[];complete=True
            for q in quarters:
                body,receipt=client.get(f'https://www.sec.gov/Archives/edgar/full-index/{year}/QTR{q}/master.gz')
                if body is None:
                    complete=False;summaries.append(dict(year=year,quarter=q,status='INDEX_UNAVAILABLE',receipt=receipt));break
                rows=parse_quarter(body,year,q);unique=distinct(rows,mapped);allrows[year].extend(rows)
                summaries.append(dict(year=year,quarter=q,status='OK',index_rows=len(rows),initial_rows=sum(r['form'] in ['SC 13D','SCHEDULE 13D'] for r in rows),
                                      initial_accessions=len(unique),current_route_accessions=sum(bool(r['mapped_symbols']) for r in unique),receipt=receipt))
                print(year,q,len(unique),'initials',summaries[-1]['current_route_accessions'],'current route',flush=True)
            year_status[str(year)]='COMPLETE_INDEXES' if complete else 'INCOMPLETE_INDEXES'
    except Stopped as exc:
        stop=str(exc)
    finally:
        client.session.close()
    selected=[]
    for year,rows in allrows.items():
        if year_status.get(str(year))=='COMPLETE_INDEXES':
            selected.extend(dict(r,event_year=year) for r in choose(distinct(rows,mapped),p['noncurrent_probe_per_quarter']))
    selected.sort(key=lambda r:(r['filed'],r['accession']))
    atomic_json(root/'selection.json',dict(status='FROZEN_WITHOUT_PRICE_OUTCOMES' if selected else 'NO_COMPLETE_INDEX_YEAR',
                created_at_utc=datetime.now(timezone.utc).isoformat(),indexes=summaries,year_status=year_status,stop=stop,
                universe_count=len(universe),selected=selected,selected_counts=dict(Counter(str(r['event_year'])+':'+r['cohort'] for r in selected)),
                files={str(f.relative_to(root)):digest(f) for f in (root/'http').glob('*')}))
    print('Selected',len(selected),year_status,flush=True)


def acquire(root):
    p=prepare(root);selection=READ(root/'selection.json');verify_hashes(root,selection['files'])
    if selection['stop'] or (root/'documents.json').exists():
        raise ValueError('Stopped collection or immutable results; do not bypass/retry')
    client=Client(root,p['limits']);rows=[];stop=None
    try:
        for i,r in enumerate(selection['selected'],1):
            body,receipt=client.get('https://www.sec.gov/Archives/'+r['paths'][0])
            rows.append(dict(selection=r,receipt=receipt))
            atomic_json(root/'progress.json',dict(status='CAPTURING',completed=len(rows),total=len(selection['selected']),last_filed=r['filed']))
            print(i,'/',len(selection['selected']),r['filed'],r['mapped_symbols'],receipt['status'],flush=True)
    except Stopped as exc:
        stop=str(exc)
    finally:
        client.session.close()
    atomic_json(root/'documents.json',dict(status='COMPLETE_ATTEMPTS' if not stop and len(rows)==len(selection['selected']) else 'INCOMPLETE',
                documents=rows,stop=stop,requests=client.calls,streamed_bytes=client.bytes,
                files={str(f.relative_to(root)):digest(f) for f in (root/'http').glob('*')}))


def extract(root):
    prepare(root);docs=READ(root/'documents.json');verify_hashes(root,docs['files'])
    if (root/'extraction.json').exists():
        raise ValueError('Immutable extraction')
    universe,_,allmapped=mapping();out=root/'review';out.mkdir();rows=[]
    for doc in docs['documents']:
        row=dict(**doc['selection'],receipt=doc['receipt'],status=doc['receipt']['status'])
        if row['status']=='OK':
            try:
                raw=(root/row['receipt']['file']).read_bytes();obj=parse(raw);text,method=section4(obj,raw)
                f=out/f"{row['accession']}.json";atomic_json(f,obj)
                symbols=sorted(allmapped.get(obj['subject_cik'],set()))
                row.update(status='READY_REVIEW',review_file=str(f.relative_to(root)),subject_cik=obj['subject_cik'],subject_name=obj['subject_name'],
                           current_mapping_symbols=symbols,current_tradable_symbols=sorted(set(symbols)&universe),section4=text,section_method=method)
            except ValueError as exc:
                row.update(status='RESERVED',reason=str(exc))
        rows.append(row)
    atomic_json(root/'extraction.json',dict(status='EXTRACTED_NO_PRICE_OUTCOMES',rows=rows,counts=dict(Counter(r['status'] for r in rows)),
                files={str(f.relative_to(root)):digest(f) for f in out.glob('*')},no_prices_read=True))
    print(Counter(r['status'] for r in rows),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--phase',choices=['indexes','acquire','extract'],required=True)
    args=parser.parse_args();globals()[args.phase](args.output)
