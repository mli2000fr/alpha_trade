"""Bounded SEC-only reconstruction of 93 frozen cases; no prices after decision.

Public historical evidence is NOT an original AlphaTrade receipt. Never backdate
later 10-Q facts into an earlier earnings release. No SQL/LLM/fit/orders/PnL.
"""
import argparse
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
import pandas_market_calendars as mcal

from common.public_data_http import verified_session
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest,verify_hashes
from scripts.research.us_earnings_reaction_source_audit import sections

PARENT=Path('artifacts/research/us_earnings_reaction_readiness/20261019-v1')
READ=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))


class AccessStopped(RuntimeError):pass


def allowed(url):
    p=urlsplit(url)
    if p.scheme!='https' or p.query or p.fragment or p.username or p.password:return False
    if p.netloc=='data.sec.gov':return bool(re.fullmatch(r'/submissions/CIK\d{10}(?:-submissions-\d{3})?\.json',p.path))
    if p.netloc=='www.sec.gov':return bool(re.fullmatch(r'/Archives/edgar/data/\d+/\d{18}/\d{10}-\d{2}-\d{6}\.txt',p.path))
    return False


def rows_from_metadata(data):
    block=data.get('filings',{}).get('recent',data)
    acc=block.get('accessionNumber',[])
    if any(isinstance(v,list) and len(v)!=len(acc) for v in block.values()):raise ValueError('Metadata array lengths differ')
    return [{k:v[i] for k,v in block.items() if isinstance(v,list)} for i in range(len(acc))]


def case_filings(case,rows):
    filed=pd.Timestamp(case['filed']);low=max(pd.Timestamp(case['fiscal_period_end']),filed-pd.Timedelta(days=60))
    selected=[r for r in rows if r.get('form') in ('8-K','6-K')
        and low<=pd.Timestamp(r['filingDate'])<=filed]
    return sorted(selected,key=lambda r:(r['filingDate'],r['accessionNumber']))


def acceptance(value):
    if not value:return None
    try:s=pd.Timestamp(value)
    except (ValueError,TypeError):return None
    return s.tz_convert('UTC') if s.tzinfo is not None else None


def reaction_day(value,schedule):
    """Only a fully observable session: session open strictly after receipt proxy."""
    stamp=acceptance(value)
    if stamp is None:return None
    eligible=schedule[schedule.market_open.gt(stamp)]
    return eligible.index[0] if len(eligible) else None


def quarter_mentioned(text,end):
    d=pd.Timestamp(end);month=d.strftime('%B');short=d.strftime('%b')
    # Explicit fiscal-end date near a quarter/results phrase, not mere balance-sheet mention.
    pat=rf'(?:quarter|three.months|three months).{{0,160}}?(?:ended|ending).{{0,40}}?(?:{month}|{short}\.?)[\s\u00a0]+0?{d.day},?[\s\u00a0]+{d.year}'
    return bool(re.search(pat,text[:12000],re.I|re.S))


def release_parts(body):
    parts=sections(body)
    out=[]
    for part in parts:
        t=part['text']
        if part['document_type'].startswith('EX-99') and re.search(r'(financial results|quarter.{0,40}results|results.{0,40}quarter)',t[:4000],re.I|re.S):
            out.append(part)
    return out


def prepare(root):
    if (root/'protocol.json').exists():
        p=READ(root/'protocol.json');verify_hashes(Path('.'),p['sources']);return p
    if root.exists():raise ValueError('Fresh directory required')
    old=READ(PARENT/'protocol.json');verify_hashes(Path('.'),old['sources'])
    report=READ(PARENT/'report.json');verify_hashes(PARENT,report['files'])
    inputs=[Path(__file__),Path('tests/test_us_earnings_release_reconstruction.py'),
        Path('scripts/research/us_earnings_reaction_source_audit.py'),Path('common/public_data_http.py'),
        PARENT/'protocol.json',PARENT/'report.json',PARENT/'top10-candidates.parquet',PARENT/'top10.parquet']
    root.mkdir(parents=True)
    cases=pd.read_parquet(PARENT/'top10-candidates.parquet')
    if len(cases)!=93 or cases.duplicated(['symbol','accession_number']).any():raise ValueError('Changed parent cohort')
    cases.to_parquet(root/'cases.parquet',index=False)
    p=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),sources={str(x):digest(x) for x in inputs},
        parent=str(PARENT),cases=93,ciks=sorted(set(cases.cik)),
        scope='Only93 frozen cases. Same issuer SEC submissions; relevant history shards; all original8-K/6-K between fiscal end or filed-60d and original filing date, no returns-based selection.',
        public_sources=['https://data.sec.gov/submissions/CIK##########.json','https://www.sec.gov/Archives/edgar/data/CIK/ACCESSION/ACCESSION.txt'],
        official_policy='https://www.sec.gov/about/developer-resources',
        limits=dict(max_requests=400,max_total_bytes=350*1024*1024,max_document_bytes=20*1024*1024,max_metadata_bytes=5*1024*1024,
            interval_seconds=.5,timeout_seconds=25,max_seconds=1200,max_filings_per_case=12),
        legal='Identified SEC_EDGAR_USER_AGENT; verified TLS; <=2requests/s serial, no retries or challenge bypass.403/429 stop acquisition. No alternate host to evade refusal.',
        archive='URL keyed one-attempt immutable receipts with real retrieval timestamp/hash; no secrets or contact user-agent archived. Resuming reuses failures without re-request.',
        temporal='Require offset-bearing acceptanceDateTime. Conservative first full NYSE session opening AFTER SEC acceptance. Publication may be earlier: first SEC candidate, not certified worldwide first release or original AlphaTrade receipt.',
        accounting='Never move later10-Q comparative values to earlier8-K as though already known. Exhibit text, fiscal interval, currency/scale and GAAP metric require verification before any direction promotion.',
        selection='Recompute TOP10 at corrected reaction close; do not preserve old24 agreements, do not replace missing/nonTOP10 cases or expand universe.',
        stop='Acquisition/chronology readiness only. No historical return outcome, economic test, new model, SQL write or batch change.',
        sql=False,paid_calls=0,llm_calls=0,training=False,production_changes=False,orders=False)
    atomic_json(root/'protocol.json',p);atomic_json(root/'case-ready.json',dict(files={'cases.parquet':digest(root/'cases.parquet')}))
    (root/'http').mkdir();return p


class Fetcher:
    def __init__(self,root,p):
        self.root=root;self.p=p;self.start=time.monotonic();self.last=0
        ua=os.getenv('SEC_EDGAR_USER_AGENT','').strip()
        if not ua:raise AccessStopped('SEC_CONTACT_USER_AGENT_MISSING')
        self.client=verified_session();self.client.headers['User-Agent']=ua
        existing=[READ(x) for x in (root/'http').glob('*.json')]
        self.calls=len(existing);self.total=sum(x.get('bytes',0) for x in existing)

    def close(self):self.client.close()

    def get(self,url,metadata=False):
        if not allowed(url):raise ValueError('SEC URL outside allowlist')
        key=hashlib.sha256(url.encode()).hexdigest();receipt=self.root/'http'/f'{key}.json'
        if receipt.exists():
            m=READ(receipt)
            if m['status']=='OK':
                file=self.root/m['file']
                if digest(file)!=m['sha256']:raise ValueError('Changed HTTP bytes')
                return file.read_bytes(),m
            if m.get('http_status') in (403,429):raise AccessStopped('PREVIOUS_ACCESS_REFUSAL_NO_RETRY')
            return None,m
        limits=self.p['limits']
        if self.calls>=limits['max_requests'] or self.total>=limits['max_total_bytes'] or time.monotonic()-self.start>limits['max_seconds']:
            raise AccessStopped('BOUNDED_ACQUISITION_LIMIT')
        time.sleep(max(0,limits['interval_seconds']-(time.monotonic()-self.last)))
        m=dict(url=url,retrieved_at_utc=datetime.now(timezone.utc).isoformat(),attempts=1,status='UNFINISHED',historical_reception_proven=False)
        self.calls+=1;self.last=time.monotonic();body=None
        try:
            with self.client.get(url,timeout=limits['timeout_seconds'],stream=True,allow_redirects=False) as response:
                m['http_status']=response.status_code
                if response.status_code==200:
                    data=bytearray();cap=limits['max_metadata_bytes'] if metadata else limits['max_document_bytes']
                    for chunk in response.iter_content(65536):
                        data.extend(chunk)
                        if len(data)>cap or self.total+len(data)>limits['max_total_bytes']:raise ValueError('SIZE_LIMIT')
                    body=bytes(data);self.total+=len(body)
                    if b'access denied' in body[:2000].lower() or b'undeclared automated tool' in body[:3000].lower():
                        m['status']='ACCESS_CHALLENGE';body=None
                    else:
                        file=f'http/{key}.body';(self.root/file).write_bytes(body)
                        m.update(status='OK',bytes=len(body),file=file,sha256=digest(self.root/file))
                else:m['status']='HTTP_REFUSED_OR_UNAVAILABLE'
        except Exception as exc:m.update(status='TECHNICAL_FAILURE_NO_RETRY',error_type=type(exc).__name__)
        atomic_json(receipt,m)
        if m.get('http_status') in (403,429) or m['status']=='ACCESS_CHALLENGE':raise AccessStopped('SEC_ACCESS_REFUSED_NO_BYPASS')
        return body,m


def discover(root):
    p=prepare(root)
    if (root/'discovery.json').exists():raise ValueError('Immutable discovery')
    cases=pd.read_parquet(root/'cases.parquet');result=[];stop=None
    client=Fetcher(root,p)
    try:
        for i,cik in enumerate(p['ciks'],1):
            c=cases[cases.cik.eq(cik)];low=pd.to_datetime(c.fiscal_period_end).min();high=pd.to_datetime(c.filed).max()
            body,meta=client.get(f'https://data.sec.gov/submissions/CIK{cik}.json',metadata=True)
            item=dict(cik=cik,rows=[],complete=False,receipts=[meta['url']])
            if body is None:item['reason']='SUBMISSIONS_UNAVAILABLE';result.append(item);continue
            obj=json.loads(body)
            if str(obj.get('cik')).zfill(10)!=cik:raise ValueError('Submission issuer mismatch')
            rows=rows_from_metadata(obj);complete=True
            for file in obj.get('filings',{}).get('files',[]):
                if pd.Timestamp(file['filingTo'])<low or pd.Timestamp(file['filingFrom'])>high:continue
                url='https://data.sec.gov/submissions/'+file['name'];b,m=client.get(url,metadata=True);item['receipts'].append(url)
                if b is None:complete=False;continue
                rows+=rows_from_metadata(json.loads(b))
            unique={}
            for r in rows:
                a=r['accessionNumber']
                if a in unique and unique[a]!=r:raise ValueError('Conflicting filing metadata')
                unique[a]=r
            relevant=[r for r in unique.values() if low<=pd.Timestamp(r['filingDate'])<=high
                and r.get('form') in ('8-K','6-K','10-Q','10-K')]
            item.update(rows=relevant,complete=complete,name=obj.get('name'),current_tickers=obj.get('tickers'))
            result.append(item)
            atomic_json(root/'progress.json',dict(phase='DISCOVERY',status='RUNNING',completed_ciks=i,total_ciks=len(p['ciks']),requests=client.calls,bytes=client.total))
            print('SEC metadata',i,'/',len(p['ciks']),'requests',client.calls,flush=True)
    except AccessStopped as exc:stop=str(exc)
    finally:client.close()
    atomic_json(root/'discovery.json',dict(status='COMPLETE' if not stop and len(result)==len(p['ciks']) else 'INCOMPLETE',stop=stop,issuers=result,
        files={str(x.relative_to(root)):digest(x) for x in (root/'http').glob('*')}))
    print('Discovery',len(result),'issuers; stop',stop,flush=True)


def fetch(root):
    p=prepare(root)
    if (root/'documents.json').exists():raise ValueError('Immutable document acquisition')
    d=READ(root/'discovery.json');verify_hashes(root,d['files'])
    cases=pd.read_parquet(root/'cases.parquet');issuer={x['cik']:x for x in d['issuers']};requests={};links=[]
    for c in cases.to_dict('records'):
        meta=issuer.get(c['cik'],{});rows=case_filings(c,meta.get('rows',[]))
        bounded=len(rows)<=p['limits']['max_filings_per_case']
        # Never silently truncate; cases exceeding the bound remain unqualified.
        if not bounded:rows=[]
        links.append(dict(symbol=c['symbol'],case_accession=c['accession_number'],cik=c['cik'],
            metadata_complete=meta.get('complete',False),candidate_bound_pass=bounded,candidates=[r['accessionNumber'] for r in rows]))
        for r in rows:requests[(c['cik'],r['accessionNumber'])]=r
    downloaded=[];stop=d.get('stop')
    if not stop:
        client=Fetcher(root,p)
        try:
            for i,((cik,accn),r) in enumerate(sorted(requests.items()),1):
                compact=accn.replace('-','');url=f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{compact}/{accn}.txt'
                body,receipt=client.get(url)
                downloaded.append(dict(cik=cik,accession=accn,metadata=r,receipt=receipt))
                atomic_json(root/'progress.json',dict(phase='DOCUMENTS',status='RUNNING',completed_documents=i,total_documents=len(requests),requests=client.calls,bytes=client.total))
                print('SEC documents',i,'/',len(requests),receipt['status'],flush=True)
        except AccessStopped as exc:stop=str(exc)
        finally:client.close()
    atomic_json(root/'documents.json',dict(status='COMPLETE' if stop is None and len(downloaded)==len(requests) else 'INCOMPLETE',stop=stop,
        requested_documents=len(requests),documents=downloaded,cases=links,
        files={str(x.relative_to(root)):digest(x) for x in (root/'http').glob('*')}))
    print('Documents',len(downloaded),'/',len(requests),'stop',stop,flush=True)


def build(root):
    p=prepare(root)
    if (root/'report.json').exists():raise ValueError('Immutable report')
    d=READ(root/'discovery.json');docs=READ(root/'documents.json');verify_hashes(root,docs['files'])
    metadata={x['cik']:x for x in d['issuers']};downloaded={x['accession']:x for x in docs['documents']}
    cases=pd.read_parquet(root/'cases.parquet');links={x['case_accession']:x for x in docs['cases']}
    visible=root/'visible';visible.mkdir();exhibits={};visible_files={}
    for accn,x in downloaded.items():
        receipt=x['receipt']
        if receipt['status']!='OK':continue
        body=(root/receipt['file']).read_bytes().decode('utf-8',errors='replace')
        extracted=release_parts(body);exhibits[accn]=[]
        for n,part in enumerate(extracted):
            file=f'visible/{accn}-{n}.txt';(root/file).write_text(part['text'],encoding='utf-8');visible_files[file]=digest(root/file)
            exhibits[accn].append(dict(file=file,text=part['text'],document_type=part['document_type']))
    top=pd.read_parquet(PARENT/'top10.parquet');membership={(r.symbol,r.date):(r.rank,r.score) for r in top.itertuples()}
    schedule=mcal.get_calendar('NYSE').schedule(start_date='2023-01-01',end_date='2026-10-20')
    rows=[];evidence=[]
    for c in cases.to_dict('records'):
        link=links[c['accession_number']];issues=[];matches=[]
        if not link['metadata_complete']:issues.append('METADATA_HISTORY_INCOMPLETE')
        if not link['candidate_bound_pass']:issues.append('CANDIDATE_DOCUMENT_BOUND')
        for accn in link['candidates']:
            x=downloaded.get(accn)
            if x is None or x['receipt']['status']!='OK':issues.append('CANDIDATE_DOCUMENT_UNAVAILABLE');continue
            for part in exhibits.get(accn,[]):
                if quarter_mentioned(part['text'],c['fiscal_period_end']):
                    stamp=acceptance(x['metadata'].get('acceptanceDateTime'))
                    matches.append((stamp,accn,part['file']))
                    evidence.append(dict(symbol=c['symbol'],case_accession=c['accession_number'],release_accession=accn,
                        target_period=str(c['fiscal_period_end'])[:10],exhibit_file=part['file'],acceptance_utc=str(stamp) if stamp is not None else None,
                        status='EXPLICIT_QUARTER_RELEASE_CANDIDATE_NOT_ACCOUNTING_QUALIFICATION'))
        known=sorted([x for x in matches if x[0] is not None])
        if matches and not known:issues.append('ACCEPTANCE_TIMEZONE_MISSING')
        if not matches:issues.append('NO_EXPLICIT_QUARTER_EXHIBIT_MATCH')
        chosen=known[0] if known else None
        corrected=reaction_day(chosen[0],schedule) if chosen else None
        rank,score=membership.get((c['symbol'],corrected),(None,None))
        rows.append(dict(symbol=c['symbol'],case_accession=c['accession_number'],fiscal_period_end=c['fiscal_period_end'],
            original_filed=c['filed'],original_reaction=c['reaction_date'],original_rank=c['oracle_rank'],
            metadata_complete=link['metadata_complete'],searched_filings=len(link['candidates']),
            explicit_release_candidates=len(matches),release_accession=chosen[1] if chosen else None,
            public_sec_acceptance=chosen[0] if chosen else None,corrected_reaction=corrected,
            corrected_rank=rank,corrected_score=score,retained_in_corrected_top10=rank is not None,
            temporal_candidate_without_missing_documents=chosen is not None and not issues,
            original_alpha_receipt_proven=False,first_worldwide_announcement_proven=False,
            earlier_release_accounting_values_verified=False,qualified_direction='ABSTAIN',reasons=sorted(set(issues))))
    output=pd.DataFrame(rows);output.to_parquet(root/'reconstructed-cases.parquet',index=False)
    atomic_json(root/'release-evidence.json',dict(records=evidence,files=visible_files))
    ok=output.temporal_candidate_without_missing_documents
    result=dict(status='RECONSTRUCTION_COMPLETED_PARTIAL_EVIDENCE_NO_DIRECTION_PROMOTION',finished_at_utc=datetime.now(timezone.utc).isoformat(),
        frozen_cases=len(output),metadata_issuers=len(d['issuers']),metadata_complete_issuers=sum(x['complete'] for x in d['issuers']),
        requested_documents=docs['requested_documents'],acquired_documents=sum(x['receipt']['status']=='OK' for x in docs['documents']),
        acquisition_stop=docs['stop'],explicit_quarter_candidates=int(output.explicit_release_candidates.gt(0).sum()),
        temporal_candidates_no_missing_documents=int(ok.sum()),retained_corrected_top10=int((ok & output.retained_in_corrected_top10).sum()),
        qualified_directions=0,reading='No later10-Q numbers backdated. Temporal/exhibit candidate is not certified first announcement, validated scope, historical local receipt or profitable trade.',
        next='Review exact release tables/scope and first-announcement evidence before accounting signs,price reaction or outcomes; unmet cases remain reserved.',
        api='Public SEC only; identified agent,verified TLS, bounded one attempt per URL,refusal respected.',
        sql=False,llm_calls=0,training=False,production_changes=False,price_outcomes=False,orders=False,
        files={**visible_files,**{n:digest(root/n) for n in ['protocol.json','case-ready.json','discovery.json','documents.json','reconstructed-cases.parquet','release-evidence.json']}})
    atomic_json(root/'report.json',result);atomic_json(root/'progress.json',dict(status='COMPLETED_WITH_RESERVES',**{k:result[k] for k in ['frozen_cases','acquired_documents','explicit_quarter_candidates','acquisition_stop']}))
    print(json.dumps({k:v for k,v in result.items() if k!='files'},default=str))


if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--output',type=Path,required=True)
    a.add_argument('--phase',choices=['prepare','discover','fetch','build'],required=True);args=a.parse_args()
    {'prepare':prepare,'discover':discover,'fetch':fetch,'build':build}[args.phase](args.output)
