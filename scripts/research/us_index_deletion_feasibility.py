"""Bounded source feasibility only; no prices, SQL, LLM, model or orders.

LSEG automation is NOT authorized by the public website terms. Never requests
that host or any mirror of its constituent lists. The separate SEC probe only
looks for issuers' own disclosures; it cannot replace an exhaustive index file.
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
from urllib.parse import parse_qs, urlencode, urlsplit

from bs4 import BeautifulSoup
from common.public_data_http import verified_session
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes

UNIVERSE=Path('config/univers_batch/univers_filtred_tradable.txt')
MAPPING=Path('artifacts/sec_cache/company_tickers.json')
QUERY='"Russell" AND ("removed" OR "removal" OR "deleted" OR "deletion" OR "excluded")'
FORMS='10-K,10-Q,8-K,20-F,6-K'
READ=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))


def allowed(url):
    u=urlsplit(url)
    if u.scheme!='https' or u.fragment or u.username or u.password:
        return False
    if u.netloc=='efts.sec.gov' and u.path=='/LATEST/search-index':
        q=parse_qs(u.query)
        return bool(q) and set(q)<=set('q dateRange startdt enddt forms from size'.split())
    return u.netloc=='www.sec.gov' and not u.query and bool(re.fullmatch(
        r'/Archives/edgar/data/\d+/(?:\d{10}-\d{2}-\d{6}\.txt|\d{18}/[A-Za-z0-9_.-]+\.html?)',u.path))


def nearby(text, radius=210):
    """Discovery candidates only: mention is not an admission/event."""
    flat=' '.join(text.split());found=[]
    for m in re.finditer(r'\bRussell\b',flat,re.I):
        snippet=flat[max(0,m.start()-radius):m.end()+radius]
        if re.search(r'\b(?:remov\w*|delet\w*|exclu\w*)\b',snippet,re.I):
            found.append(snippet)
    return list(dict.fromkeys(found))[:12]


class Stopped(RuntimeError):
    pass


class Client:
    def __init__(self, root):
        self.root=root;self.calls=0;self.bytes=0;self.last=0.;self.start=time.monotonic()
        agent=os.getenv('SEC_EDGAR_USER_AGENT','').strip()
        if '@' not in agent or 'example.com' in agent:
            raise Stopped('REAL_IDENTIFIED_SEC_CONTACT_REQUIRED')
        self.session=verified_session();self.session.headers['User-Agent']=agent

    def get(self,url):
        if not allowed(url):
            raise ValueError('SEC-only allowlist; no provider list or mirror allowed')
        if self.calls>=9 or self.bytes>=20*1024*1024 or time.monotonic()-self.start>240:
            raise Stopped('BOUNDED_SOURCE_PROBE_LIMIT')
        key=hashlib.sha256(url.encode()).hexdigest();target=self.root/'http'/f'{key}.json'
        if target.exists():
            raise ValueError('No implicit retry of immutable request')
        time.sleep(max(0,.6-(time.monotonic()-self.last)));self.last=time.monotonic();self.calls+=1
        receipt=dict(url=url,retrieved_at_utc=datetime.now(timezone.utc).isoformat(),attempts=1,status='UNFINISHED',streamed_bytes=0)
        body=None;stop=None
        try:
            with self.session.get(url,timeout=(10,30),allow_redirects=False,stream=True) as response:
                receipt['http_status']=response.status_code
                if response.status_code in [403,429]:
                    receipt['status']='ACCESS_REFUSED';stop='REFUSAL_NO_RETRY_OR_BYPASS'
                elif response.status_code!=200:
                    receipt['status']='HTTP_UNAVAILABLE_NO_RETRY'
                else:
                    data=bytearray()
                    for chunk in response.iter_content(65536):
                        data.extend(chunk);self.bytes+=len(chunk);receipt['streamed_bytes']+=len(chunk)
                        if len(data)>8*1024*1024 or self.bytes>20*1024*1024:
                            receipt['status']='BYTE_LIMIT';stop='BOUNDED_SOURCE_PROBE_LIMIT';break
                    else:
                        if any(s in bytes(data[:3500]).lower() for s in [b'access denied',b'undeclared automated tool']):
                            receipt['status']='ACCESS_CHALLENGE';stop='REFUSAL_NO_RETRY_OR_BYPASS'
                        else:
                            body=bytes(data);path=target.with_suffix('.body');path.write_bytes(body)
                            receipt.update(status='OK',file=str(path.relative_to(self.root)),sha256=digest(path))
        except Exception as exc:
            receipt.update(status='TECHNICAL_FAILURE_NO_RETRY',error_type=type(exc).__name__)
        atomic_json(target,receipt)
        if stop:
            raise Stopped(stop)
        return body,receipt


def capture(root):
    if root.exists():
        raise ValueError('Fresh immutable feasibility directory required')
    root.mkdir(parents=True);(root/'http').mkdir()
    universe={s for s in re.split(r'[,;\s]+',UNIVERSE.read_text(encoding='utf-8-sig').strip()) if s}
    mapping={}
    for row in READ(MAPPING).values():
        if row['ticker'] in universe:
            mapping.setdefault(str(row['cik_str']).zfill(10),set()).add(row['ticker'])
    inputs=[Path(__file__),Path('tests/test_us_index_deletion_feasibility.py'),UNIVERSE,MAPPING]
    protocol=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),sources={str(f):digest(f) for f in inputs},
        phase='SOURCE_FEASIBILITY_ONLY',universe_count=len(universe),years=[2024,2025,2026],event_end='2026-09-30',
        rights_gate=dict(status='LSEG_AUTOMATION_NOT_AUTHORIZED',reviewed_on='2026-10-20',
            source='https://www.lseg.com/en/policies/website-terms-of-use',sections=[9,10],
            provider_dataset_extraction=False,mirror_or_copied_index_lists_allowed=False,
            not_legal_advice=True,requires_written_permission_or_appropriately_licensed_source=True),
        probe=dict(query=QUERY,forms=FORMS,first_page_per_year=100,pagination=False,
            limit_originals=6,selection='Only one issuer CIK in current universe, sorted filed/accession/document before any price, max six',
            not_historical_census=True,no_implicit_negative_on_search_miss=True,
            rejects=['third-party index constituent tables','structured-note index descriptions','conditional risks','post-event disclosure for past entry']),
        future_test_not_executed=dict(direction='LONG_AFTER_EFFECTIVE_DELETION',entry='First full NYSE open AFTER verified effect AND known issuer disclosure',
            primary_sessions=5,secondary_sessions=[10,20],entry_session_included=True,
            no_optimization_on_observed_losses=True,no_portfolio_return_claim=True),
        no_prices=True,no_sql=True,no_llm=True,no_training=True,no_orders=True,no_batch_changes=True)
    atomic_json(root/'protocol.json',protocol)
    client=None;searches=[];originals=[];stop=None
    try:
        client=Client(root);candidates={}
        for year in [2024,2025,2026]:
            params=dict(q=QUERY,dateRange='custom',startdt=f'{year}-01-01',enddt=f'{year}-12-31' if year<2026 else '2026-09-30',forms=FORMS,**{'from':'0','size':'100'})
            body,receipt=client.get('https://efts.sec.gov/LATEST/search-index?'+urlencode(params))
            item=dict(year=year,receipt=receipt,status='UNAVAILABLE')
            if body:
                try:
                    payload=json.loads(body);hits=payload['hits']['hits'];total=payload['hits']['total']
                    item.update(status='SEARCH_RESPONSE',total_hits=total,returned=len(hits),truncated=(total.get('value',0)>len(hits) if isinstance(total,dict) else total>len(hits)))
                    for hit in hits:
                        source=hit['_source'];ciks={str(c).zfill(10) for c in source.get('ciks',[])}
                        if len(ciks)!=1 or not (ciks&mapping.keys()):
                            continue
                        accession=source.get('adsh','');filename=hit['_id'].split(':')[-1]
                        if not re.fullmatch(r'\d{10}-\d{2}-\d{6}',accession) or not re.fullmatch(r'[A-Za-z0-9_.-]+\.html?',filename):
                            continue
                        cik=next(iter(ciks));url=f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace("-","")}/{filename}'
                        candidates[url]=dict(url=url,cik=cik,symbols=sorted(mapping[cik]),filed=source.get('file_date'),accession=accession,filename=filename,search_year=year)
                except (ValueError,KeyError,TypeError) as exc:
                    item.update(status='SEARCH_SCHEMA_UNQUALIFIED',error_type=type(exc).__name__)
            searches.append(item)
        chosen=sorted(candidates.values(),key=lambda r:(r['filed'] or '',r['accession'],r['filename']))[:6]
        atomic_json(root/'selected-disclosures.json',dict(rows=chosen,chosen_before_prices=True,all_candidates=len(candidates)))
        for row in chosen:
            body,receipt=client.get(row['url']);item=dict(**row,receipt=receipt)
            if body:
                text=BeautifulSoup(body,'html.parser').get_text(' ',strip=True)
                item.update(status='DISCOVERY_ONLY_NOT_ADMITTED',nearby_mentions=nearby(text),
                    caution='Mention may be a hypothetical risk, an old event or another company; semantic and time qualification still required')
            else:
                item['status']='UNAVAILABLE'
            originals.append(item)
    except Stopped as exc:
        stop=str(exc)
    finally:
        if client:
            client.session.close()
    verify_hashes(Path('.'),protocol['sources'])
    result=dict(status='SOURCE_FEASIBILITY_BLOCKED_NO_AUTHORIZED_COMPLETE_COHORT',finished_at_utc=datetime.now(timezone.utc).isoformat(),
        searches=searches,originals=originals,stop=stop,new_requests=client.calls if client else 0,
        streamed_bytes=client.bytes if client else 0,provider_downloads_by_script=0,
        no_prices_or_economic_result=True,search_not_complete_population=True,
        files={str(f.relative_to(root)):digest(f) for f in root.rglob('*') if f.is_file()})
    atomic_json(root/'report.json',result)
    print(dict(status=result['status'],searches=[{k:v for k,v in s.items() if k!='receipt'} for s in searches],
        originals=len(originals),stop=stop,new_requests=result['new_requests']),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    capture(parser.parse_args().output)
