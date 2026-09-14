"""Bounded SEC guidance research backfill; files only, no production database writes."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
from datetime import UTC, datetime
from pathlib import Path

import requests
from sqlalchemy import bindparam, text

from database.connection import get_sqlalchemy_engine
from service.forward_pit.batch import (
    _sec_filing_index_documents, _sec_filing_index_url, _selected_sec_exhibits,
    _read_response_bytes_limited,
    _SystemTrustAdapter,
)
from service.forward_pit.guidance_audit import guidance_candidates


def submission_filings(payload, start, end, maximum):
    recent = payload.get('filings', {}).get('recent', {})
    rows=[]
    for i, accession in enumerate(recent.get('accessionNumber', [])):
        value=lambda key: recent.get(key, [])[i] if i < len(recent.get(key, [])) else None
        day=value('filingDate')
        if value('form') != '8-K' or not day or not start <= day <= end:
            continue
        items=str(value('items') or '')
        if not any(item in items.split(',') for item in ['2.02','7.01']):
            continue
        rows.append({'accession':accession, 'filing_date':day, 'form':'8-K', 'items':items,
            'acceptance_datetime':value('acceptanceDateTime'), 'primary_document':value('primaryDocument')})
    return sorted(rows, key=lambda r: ('2.02' not in r['items'], r['filing_date'],r['accession']))[:maximum]


def history_pages(payload, start, end):
    return [p for p in payload.get('filings', {}).get('files', [])
        if re.fullmatch(r'CIK[0-9]+-submissions-[0-9]+[.]json', p.get('name', ''))
        and p.get('filingFrom', '') <= end and p.get('filingTo', '') >= start]


def merge_history(payload, history):
    recent = payload.setdefault('filings', {}).setdefault('recent', {})
    old_length = len(recent.get('accessionNumber', []))
    size = len(history.get('accessionNumber', []))
    for key in set(recent) | set(history):
        recent[key] = recent.get(key, [None] * old_length) + history.get(key, [None] * size)
    return payload


def run(output, symbols, start, end, maximum, directory_index=False, max_history_pages=0):
    agent=os.getenv('SEC_EDGAR_USER_AGENT','').strip()
    if not agent:
        raise ValueError('SEC_EDGAR_USER_AGENT must be configured')
    output=Path(output)
    output.mkdir(parents=True,exist_ok=False)
    query=text('SELECT DISTINCT symbol,cik FROM sec_filing_raw WHERE symbol IN :symbols').bindparams(bindparam('symbols',expanding=True))
    with get_sqlalchemy_engine().connect() as conn:
        rows=conn.execute(query,{'symbols':symbols}).mappings().all()
    mappings={}
    for r in rows:
        if r['symbol'] in mappings and mappings[r['symbol']] != r['cik']:
            raise ValueError('Ambiguous symbol/CIK mapping')
        mappings[r['symbol']]=r['cik']
    session=requests.Session()
    session.mount('https://', _SystemTrustAdapter())
    session.headers.update({'User-Agent':agent,'Accept-Encoding':'gzip, deflate'})
    responses, documents, errors, snippets, coverage=[],[],[],[],[]

    def fetch(url, destination, max_bytes=2_000_000):
        progress = {'status': 'RUNNING', 'url': url, 'responses': len(responses),
            'downloaded_documents': sum(d['status'] == 'DOWNLOADED' for d in documents),
            'errors': len(errors), 'updated_at': datetime.now(UTC).isoformat()}
        (output/'progress.json').write_text(json.dumps(progress, indent=2), encoding='utf-8')
        print(f"FETCH {url}", flush=True)
        time.sleep(.6)  # <= 2 requests/sec, deliberately below SEC fair-access ceiling.
        received=datetime.now(UTC).isoformat()
        with session.get(url,timeout=(15,60),stream=True) as response:
            response.raise_for_status()
            body,size=_read_response_bytes_limited(response,max_bytes)
            if body is None:
                raise ValueError(f'Response exceeds {max_bytes} bytes')
            destination.parent.mkdir(parents=True,exist_ok=True)
            destination.write_bytes(body)
            responses.append({'url':url,'observed_at':received,'bytes':size,
                'sha256':hashlib.sha256(body).hexdigest(),'path':str(destination.relative_to(output))})
            return body

    try:
        for symbol in symbols:
            cik=mappings.get(symbol)
            if not cik:
                errors.append({'symbol':symbol,'stage':'mapping','error':'No local CIK mapping'})
                continue
            try:
                body=fetch(f'https://data.sec.gov/submissions/CIK{cik.zfill(10)}.json',output/symbol/'submissions.json',5_000_000)
                payload=json.loads(body)
                pages = history_pages(payload, start, end)
                loaded = 0
                for page in pages[:max_history_pages]:
                    try:
                        archived = fetch('https://data.sec.gov/submissions/' + page['name'],
                            output/symbol/page['name'], 10_000_000)
                        merge_history(payload, json.loads(archived))
                        loaded += 1
                    except Exception as exc:
                        errors.append({'symbol': symbol, 'stage': 'history', 'error': str(exc)[:500]})
                all_filings = submission_filings(payload, start, end, 100000)
                all_filings = list({f['accession']: f for f in all_filings}.values())
                filings = all_filings[:maximum]
                recent=payload.get('filings',{}).get('recent',{})
                coverage.append({'symbol':symbol,'cik':cik,'selected_filings':len(filings),
                    'recent_first_date':min(recent.get('filingDate',[]) or ['']),
                    'matching_history_pages': len(pages), 'loaded_history_pages': loaded,
                    'history_pages_not_loaded': len(pages) - loaded,
                    'eligible_filings_in_inventory': len(all_filings),
                    'filings_truncated': len(all_filings) > maximum,
                    'inventory_complete_for_requested_items': loaded == len(pages) and len(all_filings) <= maximum})
            except Exception as exc:
                errors.append({'symbol':symbol,'stage':'submissions','error':str(exc)[:500]})
                continue
            for filing in filings:
                accession=filing['accession']
                base=f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace("-", "")}'
                short_url=f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession}.txt'
                folder=output/symbol/accession
                try:
                    if directory_index:
                        index=fetch(base+'/index.json',folder/'directory-index.json')
                        items=json.loads(index).get('directory',{}).get('item',[])
                        candidates=[]
                        for item in items:
                            name=item.get('name','')
                            if (re.fullmatch(r'[A-Za-z0-9._-]+',name)
                                    and re.search(r'ex(?:hibit|h)?[_x-]*99',name,re.I)
                                    and name.lower().endswith(('.htm','.html','.txt'))):
                                candidates.append({'filename':name,'url':base+'/'+name,
                                    'document_type':'UNCONFIRMED_EX99_FILENAME_CANDIDATE'})
                        candidates=sorted(candidates,key=lambda d:d['filename'])[:2]
                    else:
                        index_url=_sec_filing_index_url(short_url,accession)
                        index=fetch(index_url,folder/'filing-index.html')
                        candidates=_selected_sec_exhibits(_sec_filing_index_documents(index.decode('utf-8',errors='replace'),base),('EX-99',),2)
                except Exception as exc:
                    errors.append({'symbol':symbol,'accession':accession,'stage':'index','error':str(exc)[:500]})
                    continue
                for doc in candidates:
                    descriptor={'symbol':symbol,'cik':cik,**filing,**doc,'historical_available_at':None}
                    if not doc['filename'].lower().endswith(('.htm','.html','.txt')):
                        documents.append({**descriptor,'status':'SKIPPED_NON_TEXT_NO_PDF_OCR'})
                        continue
                    try:
                        body=fetch(doc['url'],folder/doc['filename'])
                        decoded=body.decode('utf-8',errors='replace')
                        documents.append({**descriptor,'status':'DOWNLOADED',
                            'path':str((folder/doc['filename']).relative_to(output)),
                            'content_sha256':hashlib.sha256(body).hexdigest(),
                            'observed_at':responses[-1]['observed_at']})
                        for candidate in guidance_candidates(decoded):
                            snippets.append({**descriptor,**candidate})
                    except Exception as exc:
                        errors.append({'symbol':symbol,'accession':accession,'stage':'exhibit','error':str(exc)[:500]})
    finally:
        session.close()
        report={'experiment':'E21_GUIDANCE_HISTORICAL_SMOKE','generated_at':datetime.now(UTC).isoformat(),
            'symbols_requested':symbols,'start':start,'end':end,'max_filings_per_symbol':maximum,
            'max_exhibits_per_filing':2,'max_exhibit_bytes':2_000_000,'database_writes':False,
            'directory_index_mode':directory_index,
            'max_history_pages': max_history_pages,
            'training':False,'historical_availability_validated':False,
            'coverage':coverage,'responses':responses,'documents':documents,'errors':errors,
            'downloaded_documents':sum(d['status']=='DOWNLOADED' for d in documents),
            'unconfirmed_snippets':len(snippets),'confirmed_revision_pairs':0,
            'limitations':['Bounded history loading; inspect missing pages and truncated filing inventory',
                'Current local symbol/CIK mapping not a historical security master',
                'Directory JSON names do not certify exhibit type; filename candidates need manual review',
                'Acceptance datetime is not original press-release timestamp',
                'Collected today; no historical serving availability inferred',
                'Deterministic small sample; no performance or predictive validation']}
        report['status']='COLLECTED_REQUIRES_MANUAL_REVIEW' if report['downloaded_documents'] else 'BLOCKED_COLLECTION'
        (output/'collection_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        (output/'manual_review_candidates.json').write_text(json.dumps(snippets,indent=2),encoding='utf-8')
        (output/'progress.json').write_text(json.dumps({'status': report['status'],
            'downloaded_documents': report['downloaded_documents'], 'errors': len(errors),
            'updated_at': datetime.now(UTC).isoformat()}, indent=2), encoding='utf-8')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--symbols',default='OXM,TTC,ABM,DOCU,TSN,LULU')
    parser.add_argument('--start-date',default='2025-01-01')
    parser.add_argument('--end-date',default='2025-06-30')
    parser.add_argument('--max-filings-per-symbol',type=int,default=4)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--directory-index',action='store_true',help='Use SEC index.json; exhibit filenames require manual type confirmation')
    parser.add_argument('--max-history-pages', type=int, default=0,
        help='Maximum matching archived submissions pages per issuer (0..5)')
    args=parser.parse_args()
    if not 1<=args.max_filings_per_symbol<=24:
        parser.error('--max-filings-per-symbol must be between 1 and 24')
    if not 0 <= args.max_history_pages <= 5:
        parser.error('--max-history-pages must be between 0 and 5')
    symbols=list(dict.fromkeys(s.strip().upper() for s in args.symbols.split(',') if s.strip()))
    if not 1<=len(symbols)<=10:
        parser.error('Smoke requires 1 to 10 symbols')
    if args.start_date>args.end_date:
        parser.error('Invalid date window')
    output=args.output or Path('artifacts/research/guidance_historical_backfill')/datetime.now(UTC).strftime('e21-%Y%m%d%H%M%S')
    report=run(output,symbols,args.start_date,args.end_date,args.max_filings_per_symbol,args.directory_index,args.max_history_pages)
    print(f"Guidance backfill complete: {output}; downloaded={report['downloaded_documents']}; errors={len(report['errors'])}")
    if report['status']=='BLOCKED_COLLECTION':
        raise SystemExit(1)


if __name__=='__main__':
    main()
