"""Bounded original SEC13D cohort. No price outcomes until documentary review.

Public-source capture only, with genuine identified SEC contact and TLS. Current
universe survivor bias is explicit; original issuer is SUBJECT COMPANY, not filer.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import time
from urllib.parse import urlsplit

from bs4 import BeautifulSoup
import pandas as pd

from common.public_data_http import verified_session
from scripts.research.us_cash_merger_feasibility import parse_index
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes

READ = lambda p: json.loads(Path(p).read_text(encoding='utf-8'))
INDEX_ROOT = Path('artifacts/research/us_cash_merger_feasibility/20261020-v1')
UNIVERSE = Path('config/univers_batch/univers_filtred_tradable.txt')
MAPPING = Path('artifacts/sec_cache/company_tickers.json')
INITIAL = {'SC 13D', 'SCHEDULE 13D'}


def allowed(url):
    u=urlsplit(url)
    return u.scheme=='https' and u.netloc=='www.sec.gov' and not u.query and not u.fragment and bool(
        re.fullmatch(r'/Archives/edgar/data/\d+/(?:\d{10}-\d{2}-\d{6}\.txt|\d{18}/[A-Za-z0-9_.-]+\.html?)', u.path))


class Stopped(RuntimeError): pass


class Client:
    def __init__(self,root,limits):
        ua=os.getenv('SEC_EDGAR_USER_AGENT','').strip()
        if '@' not in ua or 'example.com' in ua:raise Stopped('REAL_IDENTIFIED_SEC_CONTACT_REQUIRED')
        self.root=root;self.limits=limits;self.client=verified_session();self.client.headers['User-Agent']=ua
        receipts=[READ(f) for f in (root/'http').glob('*.json')]
        self.calls=len(receipts);self.bytes=sum(r.get('streamed_bytes',0) for r in receipts);self.last=0.;self.started=time.monotonic()

    def get(self,url):
        if not allowed(url):raise ValueError('URL outside official SEC archive allowlist')
        key=hashlib.sha256(url.encode()).hexdigest();file=self.root/'http'/f'{key}.json'
        if file.exists():
            r=READ(file)
            if r.get('http_status') in [403,429] or r['status']=='ACCESS_CHALLENGE':raise Stopped('PREVIOUS_ACCESS_REFUSAL_NO_RETRY')
            if r['status']=='OK':
                if digest(self.root/r['file'])!=r['sha256']:raise ValueError('Archived body changed')
                return (self.root/r['file']).read_bytes(),r
            return None,r
        b=self.limits
        if self.calls>=b['requests'] or self.bytes>=b['total_bytes'] or time.monotonic()-self.started>b['max_seconds']:
            raise Stopped('BOUNDED_ACQUISITION_LIMIT')
        time.sleep(max(0,b['interval_seconds']-(time.monotonic()-self.last)))
        self.last=time.monotonic();self.calls+=1;body=None;stop=None
        r=dict(url=url,retrieved_at_utc=datetime.now(timezone.utc).isoformat(),streamed_bytes=0,attempts=1,status='UNFINISHED')
        try:
            with self.client.get(url,timeout=(10,30),stream=True,allow_redirects=False) as response:
                r['http_status']=response.status_code
                if response.status_code in [403,429]:r['status']='ACCESS_REFUSED';stop='SEC_REFUSAL_NO_BYPASS'
                elif response.status_code!=200:r['status']='HTTP_UNAVAILABLE_NO_RETRY'
                else:
                    data=bytearray()
                    for chunk in response.iter_content(65536):
                        r['streamed_bytes']+=len(chunk);self.bytes+=len(chunk);data.extend(chunk)
                        if self.bytes>b['total_bytes']:r['status']='TOTAL_BYTES_LIMIT';stop='BOUNDED_ACQUISITION_LIMIT';break
                        if len(data)>b['document_bytes']:r['status']='DOCUMENT_TOO_LARGE';break
                    else:
                        if any(x in bytes(data[:3500]).lower() for x in [b'access denied',b'undeclared automated tool']):
                            r['status']='ACCESS_CHALLENGE';stop='SEC_REFUSAL_NO_BYPASS'
                        else:
                            body=bytes(data);path=self.root/'http'/f'{key}.body';path.write_bytes(body)
                            r.update(status='OK',file=str(path.relative_to(self.root)),sha256=digest(path),bytes=len(body))
        except Exception as exc:r.update(status='TECHNICAL_FAILURE_NO_RETRY',error_type=type(exc).__name__)
        atomic_json(file,r)
        if stop:raise Stopped(stop)
        return body,r


def select(rows,cik_symbols):
    unique={}
    for r in rows:
        if r['form'] not in INITIAL or r['cik'] not in cik_symbols:continue
        if r['accession'] in unique and unique[r['accession']]['filed']!=r['filed']:raise ValueError('Conflicting accession date')
        unique.setdefault(r['accession'],dict(r,index_symbols=sorted(cik_symbols[r['cik']])))
    return sorted(unique.values(),key=lambda r:(r['filed'],r['accession']))


def visible(html):
    soup=BeautifulSoup(html,'html.parser')
    for n in soup.find_all(lambda n:n.name.lower() in ['script','style','ix:header','ix:hidden']):n.decompose()
    return ' '.join(soup.stripped_strings)


def normalized(text):return ' '.join(str(text).replace('\u200b','').split())


def item4(text):
    starts=list(re.finditer(r'\bItem\s*4\s*[.:\-]?\s*Purpose\s+of\s+(?:the\s+)?Transaction',text,re.I))
    sections=[]
    for match in starts:
        stop=re.search(r'\bItem\s*5\s*[.:\-]?\s*Interest(?:s)?\s+in\s+Securities',text[match.end():],re.I)
        if stop:sections.append(text[match.start():match.end()+stop.start()])
    return max(sections,key=len) if sections else None


def parse(body):
    text=body.decode('utf-8',errors='replace')
    if '</SEC-DOCUMENT>' not in text.upper():raise ValueError('Incomplete SGML source')
    head=text.split('<DOCUMENT>',1)[0]
    subj=re.search(r'SUBJECT COMPANY:(.*?)(?=FILED BY:|</SEC-HEADER>)',head,re.S)
    if not subj:raise ValueError('No unambiguous SUBJECT COMPANY')
    cik=re.search(r'CENTRAL INDEX KEY:\s*(\d+)',subj.group(1));name=re.search(r'COMPANY CONFORMED NAME:\s*([^\r\n]+)',subj.group(1))
    if not cik or not name:raise ValueError('Missing issuer identity')
    stamp=re.search(r'<ACCEPTANCE-DATETIME>(\d{14})',head)
    acceptance=(pd.to_datetime(stamp.group(1),format='%Y%m%d%H%M%S').tz_localize('America/New_York').tz_convert('UTC').isoformat() if stamp else None)
    parts=[]
    for raw in re.findall(r'<DOCUMENT>(.*?)</DOCUMENT>',text,re.S|re.I):
        typ=re.search(r'<TYPE>([^\r\n<]+)',raw);namefile=re.search(r'<FILENAME>([^\r\n<]+)',raw)
        if not typ:continue
        typ=typ.group(1).strip()
        if typ not in INITIAL and not typ.startswith('EX-'):continue
        parts.append(dict(type=typ,filename=namefile.group(1).strip() if namefile else None,
            text=visible(raw.split('<TEXT>',1)[-1].split('</TEXT>',1)[0])))
    primary=[r for r in parts if r['type'] in INITIAL]
    if len(primary)!=1:raise ValueError('Primary initial13D not unique')
    return dict(subject_cik=cik.group(1).zfill(10),subject_name=name.group(1).strip(),accepted_utc=acceptance,
        item4=item4(primary[0]['text']),parts=parts,header=head,
        original_receipt_now_not_historical=True)


def prepare(root):
    if (root/'protocol.json').exists():
        p=READ(root/'protocol.json');verify_hashes(Path('.'),p['sources']);return p
    if root.exists():raise ValueError('Fresh immutable output required')
    old=READ(INDEX_ROOT/'index.json');file=INDEX_ROOT/old['receipt']['file']
    if digest(file)!=old['receipt']['sha256']:raise ValueError('Changed complete quarter index')
    rows=parse_index(file.read_bytes(),80*1024*1024)
    universe={s for s in re.split(r'[,;\s]+',UNIVERSE.read_text(encoding='utf-8-sig').strip()) if s}
    mapping={}
    for r in READ(MAPPING).values():
        if r['ticker'] in universe:mapping.setdefault(str(r['cik_str']).zfill(10),set()).add(r['ticker'])
    chosen=select(rows,mapping)
    inputs=[Path(__file__),Path('tests/test_us_activist_13d_pilot.py'),
        Path('scripts/research/us_cash_merger_feasibility.py'),Path('scripts/research/us_concentrated_historical_tapes.py'),
        UNIVERSE,MAPPING,INDEX_ROOT/'index.json',file]
    root.mkdir(parents=True);(root/'http').mkdir()
    p=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),sources={str(f):digest(f) for f in inputs},
        quarter='2024Q1',universe_count=len(universe),quarter_index_rows=len(rows),
        initial_all_market_rows=sum(r['form'] in INITIAL for r in rows),selected=chosen,
        selection='ALL original13D of quarter with indexedCIK in CURRENT tradable mapping; dedup accession before date/accession sorting. Header SUBJECT must confirm issuer, not investor. Current universe survivor bias remains; not all2024market campaigns.',
        classification='Manual originalItem4/exhibits. Admit explicit concrete current intervention (boardnomination, public demand for strategicreview/sale/operational/capital change); generic maydiscuss/reservesrights/undervalued alone NOT activism. Exclude compensation, IPO/merger-related ownership, passive family/control restructurings and duplicates. No outcome-based investor blacklist/whitelist.',
        novelty='Original initial filing not necessarily initial worldwide announcement. Require current explicit action, archive referenced earlier letters separately. Do not claim first-announcement alpha; next full session strictly AFTER filing date and acceptance, no trigger-date trading.',
        identity='Historical common-stock symbol must be supported in original13D or last prefiling original10K cover; undetermined classes/CIK/ticker/namechange reserved. Current mapping alone not historical proof.',
        prices='Only after dated semantic classification is frozen: existing normalized research bars and price-reserves. No missing future=loss or replacement. For unsupported identities/data retain unknown.',
        economic='Exploratory LONG only after explicit intervention, nextfullopen, fixed close after20/60sessions, noTP/SL/trailing, no leverage or portfolioPnL. Hypothetical1000USD per independent occasion,1USDentry+1USDexit,spread5bps+slippage5bps perleg;stress25bpsperleg. CompareSPY same dates/notional/costs, no claim causal activism effect or guaranteedprofit.',
        independence='Earliest qualified intervention per issuer before future price checks; block60sessions including unknown outcomes. All initial filings still disclosed; repeated issuer/investor events deduped by manual dated plan, not returns.',
        oracle='Inspect TOP10 and TOP20% frozen concurrent researchH20 scores at decision close if available. Do not substitute a later rank or require future Oracle membership.',
        gate='Bounded pilot reports effect sizes and cases even if few; no stability/model/live promotion from singlequarter or small sample. No arbitrary sample gate used to pretend efficacy was tested.',
        limits=dict(requests=80,total_bytes=150*1024*1024,document_bytes=10*1024*1024,interval_seconds=.6,max_seconds=1800),
        future_identity_capture='Only concrete activist candidates missing historicalticker proof: last original10K before13D from localfacts accession + officialindex and primaryHTML; within same bounds, no bypass403/429/challenge.',
        no_training=True,no_sql=True,no_llm=True,no_orders=True,no_production_changes=True)
    atomic_json(root/'protocol.json',p);print('Selected ALL',len(chosen),'initial13D of',p['initial_all_market_rows'],'marketwide',flush=True)
    return p


def acquire(root):
    p=prepare(root)
    if (root/'documents.json').exists():raise ValueError('Immutable source capture')
    client=Client(root,p['limits']);done=[];stop=None
    try:
        for i,row in enumerate(p['selected'],1):
            _,receipt=client.get('https://www.sec.gov/Archives/'+row['path'])
            done.append(dict(selection=row,receipt=receipt))
            print(i,'/',len(p['selected']),row['filed'],row['name'],receipt['status'],flush=True)
            atomic_json(root/'progress.json',dict(status='CAPTURING',completed=len(done),total=len(p['selected'])))
    except Stopped as exc:stop=str(exc)
    finally:client.client.close()
    atomic_json(root/'documents.json',dict(status='COMPLETE_ATTEMPTS' if not stop and len(done)==len(p['selected']) else 'INCOMPLETE',
        stop=stop,documents=done,requests=client.calls,streamed_bytes=client.bytes,
        files={str(f.relative_to(root)):digest(f) for f in (root/'http').glob('*')}))


def extract(root):
    p=prepare(root);docs=READ(root/'documents.json');verify_hashes(root,docs['files'])
    if (root/'extraction.json').exists():raise ValueError('Immutable extraction')
    folder=root/'review';folder.mkdir();rows=[]
    for d in docs['documents']:
        row=dict(**d['selection'],receipt=d['receipt'],status=d['receipt']['status'])
        if row['status']=='OK':
            try:
                obj=parse((root/row['receipt']['file']).read_bytes())
                if obj['subject_cik']!=row['cik']:raise ValueError('Index filer is not issuer SUBJECT')
                file=folder/f"{row['accession']}.json";atomic_json(file,obj)
                row.update(status='READY_REVIEW',review_file=str(file.relative_to(root)),
                    subject_name=obj['subject_name'],accepted_utc=obj['accepted_utc'],item4_chars=len(obj['item4'] or ''))
            except ValueError as exc:row.update(status='RESERVED',reason=str(exc))
        rows.append(row)
    atomic_json(root/'extraction.json',dict(status='EXTRACTED_NO_PRICE_OUTCOMES',rows=rows,
        counts=dict(Counter(r['status'] for r in rows)),files={str(f.relative_to(root)):digest(f) for f in folder.glob('*')},
        no_prices_read=True,no_training=True,no_sql=True,no_orders=True))
    print(Counter(r['status'] for r in rows),flush=True)


if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--output',type=Path,required=True)
    a.add_argument('--phase',choices=['prepare','acquire','extract'],required=True);args=a.parse_args()
    globals()[args.phase](args.output)
