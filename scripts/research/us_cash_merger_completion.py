"""Complete fixed2024Q1 tender census and bounded SEC lifecycle, no performance."""
import argparse
from datetime import datetime,timezone
import gzip
import hashlib
import io
import os
from pathlib import Path
import re
import time
from urllib.parse import urlsplit

import pandas as pd
from bs4 import BeautifulSoup

from scripts.research.us_cash_merger_feasibility import READ,parse_index,select,parse_filing
from scripts.research.us_cash_merger_review import validate_review,normalized
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest,verify_hashes

PARENT=Path('artifacts/research/us_cash_merger_feasibility/20261020-v1')
NEW_REVIEW=Path('doc/ml/sources/cash_merger_completion_review_20261020.json')
INDEX_URL=lambda q:f'https://www.sec.gov/Archives/edgar/full-index/2024/QTR{q}/master.gz'


def allowed(url):
    if url in [INDEX_URL(q) for q in [2,3,4]]:return True
    u=urlsplit(url)
    return u.scheme=='https' and u.netloc=='www.sec.gov' and not u.query and not u.fragment and bool(
        re.fullmatch(r'/Archives/edgar/data/\d+/\d{10}-\d{2}-\d{6}\.txt',u.path))


class Fetcher:
    def __init__(self,root,p):
        from common.public_data_http import verified_session
        self.root=root;self.p=p;self.client=verified_session();self.last=0.;self.start=time.monotonic()
        ua=os.getenv('SEC_EDGAR_USER_AGENT','')
        if '@' not in ua or 'example.com' in ua:raise ValueError('Identified SEC user agent required')
        self.client.headers['User-Agent']=ua
        receipts=[READ(f) for f in (root/'http').glob('*.json')]
        self.calls=len(receipts);self.total=sum(r.get('bytes',0) for r in receipts)

    def get(self,url):
        if not allowed(url):raise ValueError('SEC URL outside scoped read-only allowlist')
        key=hashlib.sha256(url.encode()).hexdigest();path=self.root/'http'/f'{key}.json'
        if path.exists():
            r=READ(path)
            if r.get('http_status') in [403,429] or r['status']=='ACCESS_CHALLENGE':raise RuntimeError('Previous refusal, no retry')
            if r['status']=='OK':
                if digest(self.root/r['file'])!=r['sha256']:raise ValueError('Archived source changed')
                return (self.root/r['file']).read_bytes(),r
            return None,r
        b=self.p['bounds']
        if self.calls>=b['requests'] or self.total>=b['total_bytes'] or time.monotonic()-self.start>b['seconds']:
            raise RuntimeError('Bounded acquisition limit')
        time.sleep(max(0,b['interval']-(time.monotonic()-self.last)))
        r=dict(url=url,retrieved_at_utc=datetime.now(timezone.utc).isoformat(),attempts=1,status='UNFINISHED')
        self.calls+=1;self.last=time.monotonic();body=None
        try:
            with self.client.get(url,timeout=(10,35),stream=True,allow_redirects=False) as response:
                r['http_status']=response.status_code
                if response.status_code==200:
                    chunks=bytearray()
                    for chunk in response.iter_content(65536):
                        chunks.extend(chunk)
                        if len(chunks)>b['document_bytes'] or self.total+len(chunks)>b['total_bytes']:raise ValueError('SIZE_LIMIT')
                    body=bytes(chunks);self.total+=len(body)
                    if b'undeclared automated tool' in body[:3000].lower() or b'access denied' in body[:2000].lower():
                        r['status']='ACCESS_CHALLENGE';body=None
                    else:
                        f=self.root/'http'/f'{key}.body';f.write_bytes(body)
                        r.update(status='OK',bytes=len(body),file=str(f.relative_to(self.root)),sha256=digest(f))
                else:r['status']='HTTP_UNAVAILABLE_NO_RETRY'
        except Exception as exc:r.update(status='TECHNICAL_FAILURE_NO_RETRY',error_type=type(exc).__name__);body=None
        atomic_json(path,r)
        if r.get('http_status') in [403,429] or r['status']=='ACCESS_CHALLENGE':raise RuntimeError('SEC refusal, no bypass')
        return body,r


def prepare(root):
    if (root/'protocol.json').exists():
        p=READ(root/'protocol.json');verify_hashes(Path('.'),p['sources']);return p
    if root.exists():raise ValueError('Fresh output required')
    validate_review(PARENT);old=READ(PARENT/'index.json')
    rows=parse_index((PARENT/old['receipt']['file']).read_bytes(),80*1024*1024)
    selected=select(rows,len(rows))
    if len(selected)!=13 or selected[:8]!=old['selected']:raise ValueError('Original census/selection changed')
    root.mkdir(parents=True);(root/'http').mkdir();(root/'initial-review').mkdir()
    paths=[Path(__file__),Path('tests/test_us_cash_merger_completion.py'),PARENT/'protocol.json',
        PARENT/'report.json',PARENT/'index.json',PARENT/'coverage-v1/report.json']
    p=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),sources={str(f):digest(f) for f in paths},
        initial_population=selected,scope='Complete13initial SC TO-T2024Q1; preserve original8and exclusions, fetch remaining5without replacement. NOT all cash M&A.',
        admission='Initial terms only: publicly listed target, fixed cash for all common shares, no variable cash/CVR/partial tender, no post-offer publicly continuing minority investment. Unknown remains reserved, not failed.',
        lifecycle='After freezing completed initial review, entire2024Q1-Q4 index, target-CIK-linked SC TO-T/A and8-K from initial filing through2024Dec31, dedup accession. All candidates up to12per case; beyond bound case incomplete, do NOT select terminal successes only. Original target identity validated again in filings.',
        cash='Legal cash consideration becoming due/agent acceptance does NOT prove broker spendable credit date; no guessedT+2 or expiry-date redemption.',
        selection='No prices, returns or final outcome used to select initial cohort. All admissible cases retain unknown/failed outcomes. No issuer eliminated for missing data.',
        bounds=dict(requests=80,document_bytes=32*1024*1024,total_bytes=350*1024*1024,
            expanded_index_bytes=80*1024*1024,seconds=1200,interval=.5,max_lifecycle_per_case=12),
        access='Official SEC only identified user agent verifiedTLS<=2rps; no retries/redirects/challenge bypass. No paid API/LLM, SQL, order, training or production changes.',
        no_performance=True,no_prices=True,no_sql=True,no_orders=True)
    atomic_json(root/'protocol.json',p);return p


def initial(root):
    p=prepare(root)
    if (root/'initials.json').exists():raise ValueError('Immutable initial capture')
    old={r['selection']['accession']:r for r in READ(PARENT/'documents.json')['documents']}
    results=[];client=Fetcher(root,p);stop=None
    try:
        for row in p['initial_population']:
            a=row['accession']
            if a in old:
                receipt=old[a]['receipt'];source=PARENT
                if digest(source/receipt['file'])!=receipt['sha256']:raise ValueError('Original initial bytes changed')
                body=(source/receipt['file']).read_bytes()
            else:
                body,receipt=client.get('https://www.sec.gov/Archives/'+row['path']);source=root
            item=dict(index=row,source_root=str(source),receipt=receipt)
            if body:
                parsed=parse_filing(body);file=root/'initial-review'/f'{a}.json';atomic_json(file,parsed)
                item.update(review_file=str(file.relative_to(root)),review_sha256=digest(file))
            results.append(item);print('Initial',len(results),'/',len(p['initial_population']),a,receipt['status'],flush=True)
    except RuntimeError as exc:stop=str(exc)
    finally:client.client.close()
    atomic_json(root/'initials.json',dict(status='COMPLETE' if len(results)==13 and stop is None else 'INCOMPLETE',
        rows=results,stop=stop,files={str(f.relative_to(root)):digest(f) for folder in ['http','initial-review'] for f in (root/folder).glob('*')}))


def freeze_cohort(root):
    p=prepare(root);initials=READ(root/'initials.json');verify_hashes(root,initials['files'])
    old=validate_review(PARENT);new=READ(NEW_REVIEW)['rows'];allrows=old+new
    if len(allrows)!=13 or len({r['accession'] for r in allrows})!=13 or {r['accession'] for r in allrows}!={r['accession'] for r in p['initial_population']}:
        raise ValueError('Completed review must retain all13original filings')
    byacc={r['index']['accession']:r for r in initials['rows']};output=[]
    for row in allrows:
        a=row['accession'];item=byacc[a];d=READ(root/item['review_file'])
        subject=re.search(r'SUBJECT COMPANY:(.*?)(?=FILED BY:|</SEC-HEADER>)',d['header'],re.S).group(1)
        name=re.search(r'COMPANY CONFORMED NAME:\s*([^\r\n]+)',subject).group(1)
        cik=re.search(r'CENTRAL INDEX KEY:\s*(\d+)',subject).group(1).zfill(10)
        if normalized(name)!=normalized(row['target']) or cik!=row['target_cik']:raise ValueError('Target identity mismatch')
        for e in row.get('evidence',[]):
            part=next((x for x in d['parts'] if x['filename']==e['filename']),None)
            if not part or normalized(e['contains']) not in normalized(part['text']):raise ValueError(f'Unproven initial clause {a} {e}')
        output.append(dict(**row,initial_filed=item['index']['filed'],initial_review_file=item['review_file'],
            initial_source_url=item['receipt']['url'],initial_sha256=item['receipt']['sha256']))
    cohort=root/'cohort.json'
    if cohort.exists():
        previous=READ(cohort);verify_hashes(Path('.'),previous['sources']);return previous
    paths=[NEW_REVIEW,root/'initials.json',Path(__file__)]
    result=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),rows=output,
        sources={str(f):digest(f) for f in paths},frozen_before_lifecycle=True,no_outcome_selection=True)
    atomic_json(cohort,result);print('Term eligible',sum(r['eligible'] for r in output),'/13',flush=True);return result


def parse_quarter(body,quarter,cap):
    with gzip.GzipFile(fileobj=io.BytesIO(body)) as stream:data=stream.read(cap+1)
    if len(data)>cap:raise ValueError('Expanded index limit')
    text=data.decode('latin-1')
    if 'CIK|Company Name|Form Type|Date Filed|Filename' not in text:raise ValueError('Index format')
    rows=[];start=pd.Timestamp(2024,quarter*3-2,1);end=start+pd.offsets.QuarterEnd()
    for line in text.splitlines():
        cells=line.split('|')
        if len(cells)!=5 or not cells[0].isdigit():continue
        cik,name,form,date,path=cells
        if not start<=pd.Timestamp(date)<=end:raise ValueError('Index quarter mismatch')
        if not re.fullmatch(r'edgar/data/\d+/\d{10}-\d{2}-\d{6}\.txt',path):raise ValueError('Unexpected index path')
        rows.append(dict(cik=cik.zfill(10),name=name,form=form,filed=date,path=path,accession=path.rsplit('/',1)[1][:-4]))
    if not rows:raise ValueError('Empty index')
    return rows


def lifecycle_candidates(rows,case,cap):
    chosen={}
    for row in rows:
        if row['cik']!=case['target_cik'] or row['form'] not in ['SC TO-T/A','8-K'] or not case['initial_filed']<=row['filed']<='2024-12-31':continue
        a=row['accession']
        if a not in chosen or row['path']<chosen[a]['path']:chosen[a]=row
    ordered=sorted(chosen.values(),key=lambda r:(r['filed'],r['accession']))
    return dict(candidates=ordered if len(ordered)<=cap else [],candidate_count=len(ordered),bound_pass=len(ordered)<=cap)


def lifecycle(root):
    p=prepare(root);cohort=freeze_cohort(root)
    if (root/'lifecycle.json').exists():raise ValueError('Immutable lifecycle capture')
    old=READ(PARENT/'index.json');rows=parse_index((PARENT/old['receipt']['file']).read_bytes(),p['bounds']['expanded_index_bytes'])
    client=Fetcher(root,p);receipts=[];cases=[];docs={};stop=None
    try:
        for q in [2,3,4]:
            body,r=client.get(INDEX_URL(q));receipts.append(r)
            if body is None:raise RuntimeError('Missing calendar index; cannot declare lifecycle complete')
            rows+=parse_quarter(body,q,p['bounds']['expanded_index_bytes'])
        for c in [c for c in cohort['rows'] if c['eligible']]:
            result=lifecycle_candidates(rows,c,p['bounds']['max_lifecycle_per_case']);cases.append(dict(case=c,**result))
            for r in result['candidates']:docs[r['accession']]=r
        for i,(acc,r) in enumerate(sorted(docs.items()),1):
            body,receipt=client.get('https://www.sec.gov/Archives/'+r['path'])
            docs[acc]=dict(index=r,receipt=receipt)
            print('Lifecycle',i,'/',len(docs),r['form'],acc,receipt['status'],flush=True)
            atomic_json(root/'progress.json',dict(status='RUNNING',phase='LIFECYCLE',completed=i,total=len(docs)))
    except RuntimeError as exc:stop=str(exc)
    finally:client.client.close()
    # Keep undownloaded metadata explicit; never count it as an empty document.
    downloaded=[v for v in docs.values() if 'receipt' in v]
    value=dict(status='COMPLETE_CAPTURE' if stop is None and len(downloaded)==len(docs) else 'INCOMPLETE',
        cases=cases,documents=downloaded,requested_documents=len(docs),stop=stop,calendar_index_receipts=receipts,
        files={str(f.relative_to(root)):digest(f) for f in (root/'http').glob('*')})
    atomic_json(root/'lifecycle.json',value)
    atomic_json(root/'progress.json',dict(status=value['status'],phase='LIFECYCLE',completed=len(downloaded),total=len(docs),stop=stop))


def extract_lifecycle(root):
    prepare(root);life=READ(root/'lifecycle.json');verify_hashes(root,life['files'])
    if (root/'lifecycle-extract.json').exists():raise ValueError('Immutable lifecycle extraction')
    folder=root/'lifecycle-review';folder.mkdir();result=[]
    for item in life['documents']:
        r=item['receipt'];row=dict(**item)
        if r['status']=='OK':
            text=(root/r['file']).read_bytes().decode('utf-8',errors='replace')
            if '</SEC-DOCUMENT>' not in text.upper():row['status']='TRUNCATED'
            else:
                parts=[]
                for block in re.findall(r'<DOCUMENT>(.*?)</DOCUMENT>',text,re.S|re.I):
                    typ=re.search(r'<TYPE>([^\r\n<]+)',block);name=re.search(r'<FILENAME>([^\r\n<]+)',block)
                    if typ and (typ.group(1).strip() in ['8-K','SC TO-T/A'] or typ.group(1).startswith('EX-')):
                        soup=BeautifulSoup(block.split('<TEXT>',1)[-1].split('</TEXT>',1)[0],'html.parser')
                        for n in soup(['script','style','ix:header','ix:hidden']):n.decompose()
                        parts.append(dict(type=typ.group(1).strip(),filename=name.group(1).strip() if name else None,text=' '.join(soup.stripped_strings)))
                file=folder/f"{item['index']['accession']}.json"
                atomic_json(file,dict(header=text.split('<DOCUMENT>',1)[0],parts=parts))
                row.update(status='READY_MANUAL_REVIEW',review_file=str(file.relative_to(root)),sha256=digest(file))
        result.append(row)
    atomic_json(root/'lifecycle-extract.json',dict(documents=result,files={str(f.relative_to(root)):digest(f) for f in folder.glob('*')}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True)
    p.add_argument('--phase',choices=['prepare','initial','freeze_cohort','lifecycle','extract_lifecycle'],required=True);a=p.parse_args()
    globals()[a.phase](a.root)
