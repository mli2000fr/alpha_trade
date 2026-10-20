"""Compact official HTML pieces after explicitly incomplete full-SGML acquisition."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import re
import time
from urllib.parse import urlsplit

from common.public_data_http import verified_session
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest,verify_hashes

PARENT=Path('artifacts/research/us_public_information_followup/20261020-v1')
READ=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))


def allowed(url):
    p=urlsplit(url)
    return p.scheme=='https' and p.netloc=='www.sec.gov' and not p.query and not p.fragment and bool(
        re.fullmatch(r'/Archives/edgar/data/\d+/\d{18}/(?:index\.json|[A-Za-z0-9_.-]+\.html?)',p.path))


def filenames(index,primary):
    files=[x['name'] for x in index.get('directory',{}).get('item',[]) if
        re.fullmatch(r'[A-Za-z0-9_.-]+\.html?',str(x.get('name',''))) and x['name']!=primary
        and not re.fullmatch(r'R\d+\.htm',x['name'])]
    # Never silently truncate a potentially incomplete exhibit list.
    return files if len(files)<=4 else None


def prepare(root):
    if (root/'protocol.json').exists():
        p=READ(root/'protocol.json');verify_hashes(Path('.'),p['sources']);return p
    if root.exists():raise ValueError('Fresh compact directory required')
    prior=READ(PARENT/'protocol.json');verify_hashes(Path('.'),prior['sources'])
    verify_hashes(PARENT,READ(PARENT/'documents.json')['files'])
    plan=READ(PARENT/'document-plan.json');done={r['accession']:r for r in READ(PARENT/'documents.json')['documents']}
    selected=[r for r in plan['requests'] if done.get(r['accession'],{}).get('receipt',{}).get('status')!='OK']
    root.mkdir(parents=True);(root/'http').mkdir()
    paths=[Path(__file__),Path('tests/test_us_public_information_compact.py'),PARENT/'protocol.json',
        PARENT/'document-plan.json',PARENT/'documents.json',PARENT/'extraction.json']
    p=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),sources={str(p):digest(p) for p in paths},
        parent=str(PARENT),requests=selected,
        rationale='Original SGML acquisition explicitly INCOMPLETE at size/volume limits; retrieve distinct smaller primary HTML and bounded official attachments, not retry full SGML or evade any access refusal.',
        limits=dict(max_requests=160,max_total_bytes=160*1024*1024,max_document_bytes=8*1024*1024,interval_seconds=.5),
        rules='Official SEC only, identified UA, verified TLS, one request per URL, stop403/429/challenge. Cumulative streamed bytes INCLUDING interrupted transfers counted. Never auto-retry a failure.',
        production_changes=False,sql=False,llm=False,training=False,price_outcomes=False,orders=False)
    atomic_json(root/'protocol.json',p);return p


class LimitStopped(RuntimeError):pass


class Client:
    def __init__(self,root,p):
        self.root=root;self.limits=p['limits'];self.last=0
        ua=os.getenv('SEC_EDGAR_USER_AGENT','').strip()
        if not ua:raise LimitStopped('NO_IDENTIFIED_SEC_CONTACT')
        self.http=verified_session();self.http.headers['User-Agent']=ua
        records=[READ(p) for p in (root/'http').glob('*.json')]
        self.calls=len(records);self.bytes=sum(r.get('streamed_bytes',0) for r in records)

    def get(self,url):
        if not allowed(url):raise ValueError('SEC compact URL outside allowlist')
        key=hashlib.sha256(url.encode()).hexdigest();path=self.root/'http'/f'{key}.json'
        if path.exists():
            m=READ(path)
            if m['status']=='OK':
                if digest(self.root/m['file'])!=m['sha256']:raise ValueError('Changed archive')
                return (self.root/m['file']).read_bytes(),m
            if m.get('http_status') in (403,429):raise LimitStopped('PREVIOUS_ACCESS_REFUSAL')
            return None,m
        if self.calls>=self.limits['max_requests'] or self.bytes>=self.limits['max_total_bytes']:
            raise LimitStopped('COMPACT_BUDGET_EXHAUSTED')
        time.sleep(max(0,self.limits['interval_seconds']-(time.monotonic()-self.last)))
        self.last=time.monotonic();self.calls+=1
        m=dict(url=url,retrieved_at_utc=datetime.now(timezone.utc).isoformat(),attempts=1,
            streamed_bytes=0,status='UNFINISHED',historical_reception_proven=False)
        body=None;stop=None
        try:
            with self.http.get(url,timeout=25,stream=True,allow_redirects=False) as response:
                m['http_status']=response.status_code
                if response.status_code in (403,429):
                    m['status']='ACCESS_REFUSED';stop='SEC_ACCESS_REFUSED_NO_BYPASS'
                elif response.status_code!=200:m['status']='HTTP_UNAVAILABLE'
                else:
                    data=bytearray()
                    for chunk in response.iter_content(65536):
                        m['streamed_bytes']+=len(chunk);self.bytes+=len(chunk);data.extend(chunk)
                        if self.bytes>self.limits['max_total_bytes']:
                            stop='COMPACT_BYTE_BUDGET';m['status']='BYTE_BUDGET';break
                        if len(data)>self.limits['max_document_bytes']:
                            m['status']='DOCUMENT_TOO_LARGE';break
                    else:
                        if any(v in bytes(data[:3000]).lower() for v in (b'access denied',b'undeclared automated tool')):
                            stop='SEC_ACCESS_CHALLENGE';m['status']='ACCESS_CHALLENGE'
                        else:
                            body=bytes(data);file=f'http/{key}.body';(self.root/file).write_bytes(body)
                            m.update(status='OK',file=file,sha256=digest(self.root/file),bytes=len(body))
        except Exception as exc:m.update(status='TECHNICAL_FAILURE_NO_RETRY',error_type=type(exc).__name__)
        atomic_json(path,m)
        if stop:raise LimitStopped(stop)
        return body,m


def acquire(root):
    p=prepare(root)
    if (root/'documents.json').exists():raise ValueError('Immutable compact acquisition')
    client=Client(root,p);result=[];stop=None
    try:
        for i,row in enumerate(p['requests'],1):
            cik,acc,meta=row['cik'],row['accession'],row['metadata']
            base=f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace("-","")}/'
            primary=meta.get('primaryDocument','')
            if not re.fullmatch(r'[A-Za-z0-9_.-]+\.html?',primary):
                result.append(dict(accession=acc,pieces=[],reason='PRIMARY_NAME_UNSUPPORTED'));continue
            body,receipt=client.get(base+primary)
            pieces=[dict(role='PRIMARY',document_type=meta['form'],receipt=receipt)]
            attachments_complete=True
            if meta['form'] in ('8-K','6-K'):
                listing,index_receipt=client.get(base+'index.json')
                extra=filenames(json.loads(listing),primary) if listing else None
                if extra is None:attachments_complete=False
                else:
                    for name in extra:
                        _,record=client.get(base+name)
                        # Only a routing label, not a fabricated native SGML type.
                        pieces.append(dict(role='HTML_ATTACHMENT_CANDIDATE',document_type='EX-99',receipt=record))
                        if record['status']!='OK':attachments_complete=False
            result.append(dict(accession=acc,cik=cik,metadata=meta,pieces=pieces,
                attachments_complete=attachments_complete,synthetic_wrapper_is_not_original_sgml=True))
            print('Compact',i,'/',len(p['requests']),acc,'calls',client.calls,'bytes',client.bytes,flush=True)
    except LimitStopped as exc:stop=str(exc)
    finally:client.http.close()
    atomic_json(root/'documents.json',dict(status='COMPLETE' if not stop and len(result)==len(p['requests']) else 'INCOMPLETE',
        stop=stop,documents=result,requests=client.calls,streamed_bytes=client.bytes,
        files={str(p.relative_to(root)):digest(p) for p in (root/'http').glob('*')}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--phase',choices=['prepare','acquire'],required=True);args=parser.parse_args()
    globals()[args.phase](args.output)
