"""Bounded SEC tender-offer feasibility. No return, model, order or SQL write."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import time
from urllib.parse import urlsplit

from bs4 import BeautifulSoup
import pandas as pd
import pandas_market_calendars as mcal

from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes

READ=lambda path:json.loads(Path(path).read_text(encoding='utf-8'))
INDEX='https://www.sec.gov/Archives/edgar/full-index/2024/QTR1/master.gz'


def allowed(url):
    if url==INDEX:return True
    u=urlsplit(url)
    return (u.scheme=='https' and u.netloc=='www.sec.gov' and not u.query and not u.fragment
        and bool(re.fullmatch(r'/Archives/edgar/data/\d+/\d{10}-\d{2}-\d{6}\.txt',u.path)))


def prepare(root):
    if (root/'protocol.json').exists():
        p=READ(root/'protocol.json');verify_hashes(Path('.'),p['sources']);return p
    if root.exists():raise ValueError('Fresh output directory required')
    root.mkdir(parents=True);(root/'http').mkdir()
    paths=[Path(__file__),Path('tests/test_us_cash_merger_feasibility.py')]
    p=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),sources={str(x):digest(x) for x in paths},
        question='Can public initial filings supply cash acquisition terms and historical identity independently of deal outcome/current survivors?',
        quarter='2024Q1',index_url=INDEX,form='SC TO-T',sample_size=8,
        selection='Full quarter index, exclude amendments SC TO-T/A and issuer self tenders SC TO-I. Deduplicate accession across co-filers BEFORE sorting by filing date then accession; first8initial filings, no current universe/prices/outcomes filter or replacement.',
        scope='Initial third-party tender filings only, NOT census of all cash mergers. May contain unsolicited/partial/odd-lot/fund tenders; manual admission of control acquisitions needed. Filing sample is not necessarily8independent deals.',
        temporal='Only information contained in archived original initial filing. SEC header acceptance interpreted America/New_York; conservative next full NYSE session. Not worldwide first announcement, local historical receipt or vintage PIT proof.',
        outcome='Outcomes NOT used in selection. Failure/termination and final cash credit must be sought for EVERY admitted deal in a separately frozen next phase. No deal assumed completed because now delisted.',
        bounds=dict(max_requests=9,document_bytes=20*1024*1024,total_bytes=150*1024*1024,
            expanded_index_bytes=80*1024*1024,interval_seconds=.5,timeout_seconds=30,max_seconds=900),
        access='Official SEC only, identified user agent, verified TLS, serial<=2rps, no retries, redirects or access challenge bypass;403/429 stop. Exact URLs and retrieved UTC archived, no secrets.',
        no_prices_or_pnl=True,no_training=True,no_llm=True,no_orders=True,no_sql_writes=True,no_production_changes=True)
    atomic_json(root/'protocol.json',p);return p


class Fetcher:
    def __init__(self,root,p):
        from common.public_data_http import verified_session
        self.root=root;self.p=p;self.client=verified_session();self.last=0.;self.start=time.monotonic()
        agent=os.getenv('SEC_EDGAR_USER_AGENT','').strip()
        if '@' not in agent or 'example.com' in agent:raise ValueError('Identified SEC agent required')
        self.client.headers['User-Agent']=agent
        receipts=[READ(f) for f in (root/'http').glob('*.json')]
        self.calls=len(receipts);self.total=sum(r.get('bytes',0) for r in receipts)

    def get(self,url):
        if not allowed(url):raise ValueError('URL outside SEC read-only allowlist')
        key=hashlib.sha256(url.encode()).hexdigest();file=self.root/'http'/f'{key}.json'
        if file.exists():
            r=READ(file)
            if r.get('http_status') in [403,429] or r['status']=='ACCESS_CHALLENGE':raise RuntimeError('Prior SEC access refusal; no retry')
            if r['status']=='OK':
                body=self.root/r['file']
                if digest(body)!=r['sha256']:raise ValueError('Archived source changed')
                return body.read_bytes(),r
            return None,r
        b=self.p['bounds']
        if self.calls>=b['max_requests'] or self.total>=b['total_bytes'] or time.monotonic()-self.start>b['max_seconds']:
            raise RuntimeError('Bounded acquisition limit')
        time.sleep(max(0,b['interval_seconds']-(time.monotonic()-self.last)))
        r=dict(url=url,retrieved_at_utc=datetime.now(timezone.utc).isoformat(),attempts=1,status='UNFINISHED')
        self.calls+=1;self.last=time.monotonic();body=None
        try:
            with self.client.get(url,timeout=b['timeout_seconds'],stream=True,allow_redirects=False) as response:
                r['http_status']=response.status_code
                if response.status_code==200:
                    chunks=bytearray()
                    for chunk in response.iter_content(65536):
                        chunks.extend(chunk)
                        if len(chunks)>b['document_bytes'] or self.total+len(chunks)>b['total_bytes']:
                            raise ValueError('Response size limit; incomplete is not empty')
                    body=bytes(chunks);self.total+=len(body)
                    if b'undeclared automated tool' in body[:3000].lower() or b'access denied' in body[:2000].lower():
                        r['status']='ACCESS_CHALLENGE';body=None
                    else:
                        path=self.root/'http'/f'{key}.body';path.write_bytes(body)
                        r.update(status='OK',file=str(path.relative_to(self.root)),sha256=digest(path),bytes=len(body))
                else:r['status']='HTTP_UNAVAILABLE_NO_RETRY'
        except Exception as exc:r.update(status='TECHNICAL_FAILURE_NO_RETRY',error_type=type(exc).__name__);body=None
        atomic_json(file,r)
        if r.get('http_status') in [403,429] or r['status']=='ACCESS_CHALLENGE':raise RuntimeError('SEC access refused; no bypass')
        return body,r


def parse_index(body,cap):
    with gzip.GzipFile(fileobj=io.BytesIO(body)) as stream:expanded=stream.read(cap+1)
    if len(expanded)>cap:raise ValueError('Expanded index size limit')
    text=expanded.decode('latin-1')
    if 'CIK|Company Name|Form Type|Date Filed|Filename' not in text:raise ValueError('Unexpected index format')
    rows=[]
    for line in text.splitlines():
        cols=line.split('|')
        if len(cols)!=5 or not cols[0].isdigit():continue
        cik,name,form,day,path=cols
        if not re.fullmatch(r'edgar/data/\d+/\d{10}-\d{2}-\d{6}\.txt',path):raise ValueError('Unexpected SEC filing path')
        if not '2024-01-01'<=day<='2024-03-31':raise ValueError('Index outside fixed quarter')
        rows.append(dict(cik=cik.zfill(10),name=name,form=form,filed=day,path=path,
            accession=path.rsplit('/',1)[1][:-4]))
    if not rows:raise ValueError('Empty index not accepted')
    return rows


def select(rows,n):
    initial=[r for r in rows if r['form']=='SC TO-T'];unique={}
    for r in initial:
        a=r['accession']
        if a not in unique or r['path']<unique[a]['path']:unique[a]=r
        elif r['filed']!=unique[a]['filed']:raise ValueError('Conflicting accession dates')
    return sorted(unique.values(),key=lambda r:(r['filed'],r['accession']))[:n]


def index(root):
    p=prepare(root)
    if (root/'index.json').exists():raise ValueError('Immutable index selection')
    client=Fetcher(root,p)
    try:body,receipt=client.get(INDEX)
    finally:client.client.close()
    if body is None:raise RuntimeError('Quarter index unavailable; no substitute universe')
    rows=parse_index(body,p['bounds']['expanded_index_bytes']);chosen=select(rows,p['sample_size'])
    forms=Counter(r['form'] for r in rows)
    atomic_json(root/'index.json',dict(status='SELECTED_WITHOUT_OUTCOMES',receipt=receipt,
        index_rows=len(rows),form_counts={f:forms[f] for f in ['SC TO-T','SC TO-T/A','SC TO-I','DEFM14A','8-K']},
        initial_rows=forms['SC TO-T'],unique_initial_accessions=len(select(rows,len(rows))),selected=chosen,
        selection_exhausts_quarter_initials=len(chosen)==len(select(rows,len(rows))),
        files={str(f.relative_to(root)):digest(f) for f in (root/'http').glob('*')}))
    print('Initial tender filings',forms['SC TO-T'],'selected',len(chosen),flush=True)


def documents(root):
    p=prepare(root);selection=READ(root/'index.json');verify_hashes(root,selection['files'])
    if (root/'documents.json').exists():raise ValueError('Immutable original-document capture')
    results=[];stop=None;client=Fetcher(root,p)
    try:
        for row in selection['selected']:
            body,r=client.get('https://www.sec.gov/Archives/'+row['path'])
            results.append(dict(selection=row,receipt=r))
            print(row['filed'],row['accession'],r['status'],flush=True)
            atomic_json(root/'progress.json',dict(status='RUNNING',completed=len(results),total=len(selection['selected']),requests=client.calls))
    except RuntimeError as exc:stop=str(exc)
    finally:client.client.close()
    result=dict(status='COMPLETE_ATTEMPTS' if len(results)==len(selection['selected']) and stop is None else 'INCOMPLETE',
        stop=stop,documents=results,files={str(f.relative_to(root)):digest(f) for f in (root/'http').glob('*')})
    atomic_json(root/'documents.json',result)
    atomic_json(root/'progress.json',dict(status=result['status'],completed=len(results),total=len(selection['selected']),stop=stop))


def visible(html):
    s=BeautifulSoup(html,'html.parser')
    for node in s(['script','style','ix:header','ix:hidden']):node.decompose()
    return ' '.join(s.stripped_strings)


def parse_filing(body):
    text=body.decode('utf-8',errors='replace')
    if '</SEC-DOCUMENT>' not in text.upper():raise ValueError('Truncated complete submission')
    head=text.split('<DOCUMENT>',1)[0]
    acc=re.search(r'<ACCEPTANCE-DATETIME>(\d{14})',head)
    accepted=pd.to_datetime(acc.group(1),format='%Y%m%d%H%M%S').tz_localize('America/New_York').tz_convert('UTC') if acc else None
    schedule=mcal.get_calendar('NYSE').schedule(start_date='2024-01-01',end_date='2024-04-10')
    eligible=schedule[schedule.market_open.gt(accepted)] if accepted is not None else schedule.iloc[:0]
    parts=[]
    for item in re.findall(r'<DOCUMENT>(.*?)</DOCUMENT>',text,re.S|re.I):
        typ=re.search(r'<TYPE>([^\r\n<]+)',item);name=re.search(r'<FILENAME>([^\r\n<]+)',item)
        if not typ:continue
        typ=typ.group(1).strip()
        if typ!='SC TO-T' and not typ.startswith('EX-'):continue
        txt=visible(item.split('<TEXT>',1)[-1].split('</TEXT>',1)[0])
        parts.append(dict(type=typ,filename=name.group(1).strip() if name else None,text=txt))
    if sum(x['type']=='SC TO-T' for x in parts)!=1:raise ValueError('Primary tender form not unique')
    return dict(header=head,accepted_utc=str(accepted) if accepted is not None else None,
        first_full_session=str(eligible.index[0].date()) if len(eligible) else None,
        parts=parts,receipt_time_is_not_historical=True)


def build(root):
    p=prepare(root);docs=READ(root/'documents.json');verify_hashes(root,docs['files'])
    if (root/'report.json').exists():raise ValueError('Immutable feasibility extraction')
    folder=root/'review';folder.mkdir();rows=[]
    for item in docs['documents']:
        r=item['receipt'];row=dict(**item['selection'],status=r['status'],receipt=r)
        if r['status']=='OK':
            try:
                extracted=parse_filing((root/r['file']).read_bytes())
                acc=row['accession'];path=folder/f'{acc}.json';atomic_json(path,extracted)
                row.update(status='READY_MANUAL_REVIEW',review_file=str(path.relative_to(root)),
                    accepted_utc=extracted['accepted_utc'],first_full_session=extracted['first_full_session'],
                    parts=[dict(type=x['type'],filename=x['filename'],characters=len(x['text'])) for x in extracted['parts']])
            except ValueError as exc:row.update(status='UNQUALIFIED_DOCUMENT',reason=str(exc))
        rows.append(row)
    value=dict(status='EXTRACTED_NOT_A_STRATEGY_BACKTEST',selected_filings=len(READ(root/'index.json')['selected']),
        statuses=dict(Counter(r['status'] for r in rows)),rows=rows,
        entire_merger_population_covered=False,outcomes_assessed=False,prices_assessed=False,
        files={str(f.relative_to(root)):digest(f) for f in root.rglob('*') if f.is_file() and f.name not in ['progress.json']})
    atomic_json(root/'report.json',value);print(value['statuses'],flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True)
    p.add_argument('--phase',choices=['prepare','index','documents','build'],required=True);a=p.parse_args()
    globals()[a.phase](a.root)
