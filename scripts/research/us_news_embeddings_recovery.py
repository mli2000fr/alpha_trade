"""Evidence-based recovery of explicit HTTP429 rejections, same USD3 ledger.

Original paid protocol/requests/cache stay immutable. Transport amendment only:
rate pacing, error-code classification, safe headers, explicit rejection receipt.
Unknown transport outcomes and billing errors never trigger automatic retries.
"""
from collections import deque
from decimal import Decimal
import json
import os
from pathlib import Path
import time
import uuid

import pandas as pd

from scripts.research import us_news_embeddings_pilot as pilot
from scripts.research.us_news_embedding_cache import (
    CAP, RATE, MODEL, DIMENSIONS, EmbeddingCache, exclusive, sha, utc,
)
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest

FIRST_REJECTED='d9c43e4470324739b77dc8c4bcc561c5'
RATE_CODES={'rate_limit_exceeded','slow_down','tokens_per_minute','requests_per_minute'}
HEADERS=['x-request-id','retry-after','x-ratelimit-limit-tokens',
         'x-ratelimit-remaining-tokens','x-ratelimit-reset-tokens',
         'x-ratelimit-limit-project-tokens','x-ratelimit-remaining-project-tokens',
         'x-ratelimit-reset-project-tokens','x-ratelimit-limit-requests']


class RecoveryCache(EmbeddingCache):
    def summary(self,campaign):
        rows=self.db.execute('SELECT status,charged_usd,usage_tokens FROM paid_call WHERE campaign=?',
                             (campaign,)).fetchall()
        return dict(api_calls=len(rows),completed_calls=sum(r[0]=='COMPLETE' for r in rows),
            rejected_calls=sum(r[0].startswith('REJECTED_') for r in rows),
            unresolved_calls=sum(r[0]=='RESERVED' for r in rows),
            committed_usd=str(sum((Decimal(r[1]) for r in rows),Decimal(0))),
            usage_tokens=sum(r[2] or 0 for r in rows),max_budget_usd=str(CAP))

    def reserve(self,campaign,request,tokens):
        upper=(tokens*125+99)//100+32*len(request['input'])
        amount=Decimal(upper)*RATE
        request_sha=sha(request)
        self.db.execute('BEGIN IMMEDIATE')
        try:
            if self.db.execute('SELECT 1 FROM campaign WHERE campaign=?',(campaign,)).fetchone() is None:
                raise ValueError('Unregistered campaign')
            rows=self.db.execute('SELECT status,charged_usd,request_sha256 FROM paid_call WHERE campaign=?',
                                 (campaign,)).fetchall()
            if any(r[0]=='RESERVED' for r in rows):
                raise ValueError('Ambiguous call retained; no automatic paid retry')
            if any(r[0]=='COMPLETE' and r[2]==request_sha for r in rows):
                raise ValueError('Successful call cannot be paid again')
            if sum((Decimal(r[1]) for r in rows),Decimal(0))+amount>CAP:
                raise ValueError('USD3 ceiling before next call')
            call=uuid.uuid4().hex
            self.db.execute('INSERT INTO paid_call VALUES(?,?,?,?,?,?,?,?,?)',
                (call,campaign,request_sha,'RESERVED',str(amount),str(amount),utc(),None,None))
            self.db.commit()
            return call
        except BaseException:
            self.db.rollback();raise

    def rejected(self,call,receipt):
        if receipt['http_status']!=429:
            raise ValueError('Only definite HTTP429 rejection is recoverable here')
        folder=self.path.parent/'rejections';folder.mkdir(exist_ok=True)
        with (folder/f'{call}.json').open('x',encoding='utf-8') as stream:
            json.dump(receipt,stream,indent=2)
        with self.db:
            change=self.db.execute("UPDATE paid_call SET status='REJECTED_HTTP429',charged_usd='0',"
                "usage_tokens=0,response_sha256=? WHERE call_id=? AND status='RESERVED'",
                (sha(receipt),call))
            if change.rowcount!=1:
                raise ValueError('Rejection state changed')


def resume(root=pilot.ROOT):
    protocol=pilot.verify(root)
    cache=RecoveryCache(pilot.HOME/'cache.sqlite')
    session=None
    try:
        campaign=root.name
        cache.register(campaign,sha(protocol))
        first=cache.db.execute('SELECT status FROM paid_call WHERE call_id=?',(FIRST_REJECTED,)).fetchone()
        if first and first[0]=='RESERVED':
            progress=pilot.read(root/'progress.json')
            if (progress.get('status')!='STOPPED' or progress.get('message')!=
                    'OpenAI embedding HTTP 429; no automatic retry'):
                raise ValueError('Original explicit 429 evidence missing; keep reservation')
            cache.rejected(FIRST_REJECTED,dict(http_status=429,code='ORIGINAL_HTTP429_BODY_NOT_RETAINED',
                error_log_sha256=digest(root/'embedding.log'),progress_sha256=digest(root/'progress.json'),
                action='One controlled recovery after explicit rejected response; not an ambiguous POST',at=utc()))
        amendment=root/'transport-amendment.json'
        if not amendment.exists():
            atomic_json(amendment,dict(original_protocol_sha256=sha(protocol),recorded_at=utc(),
                source_sha256=digest(__file__),changes=['pace by advertised token window',
                'retry explicit temporary 429 only','retain billing errors and ambiguous outcomes'],
                cap_usd=str(CAP),new_data_or_labels=False,old_successes_unchanged=True))
        elif pilot.read(amendment)['source_sha256']!=digest(__file__):
            raise ValueError('Recovery transport source changed')
        import tiktoken
        os.environ['TIKTOKEN_CACHE_DIR']=str((pilot.HOME/'tokenizer').resolve())
        encoder=tiktoken.get_encoding('cl100k_base')
        rows=pd.read_parquet(root/'articles.parquet').to_dict('records')
        pending=[a for a in rows if cache.get(a['key']) is None]
        from common.verified_http import verified_session
        session=verified_session()
        key=os.environ.get('OPENAI_API_KEY')
        if not key:
            raise ValueError('Missing API key')
        limit=400_000
        window=deque()
        last_headers={}
        rejected_in_row=0
        completed=len(rows)-len(pending)
        for offset in range(0,len(pending),128):
            batch=pending[offset:offset+128]
            inputs=[encoder.encode(a['text'],disallowed_special=()) for a in batch]
            tokens=sum(map(len,inputs))
            if tokens!=sum(a['tokens'] for a in batch) or tokens>300000:
                raise ValueError('Input token drift')
            request=dict(model=MODEL,dimensions=DIMENSIONS,input=inputs,encoding_format='float')
            while True:
                now=time.monotonic()
                while window and now-window[0][0]>=61:
                    window.popleft()
                used=sum(t for _,t in window)
                if window and used+tokens>limit*.70:
                    delay=min(55.,max(.2,61-(now-window[0][0])))
                    atomic_json(root/'progress.json',dict(status='RATE_PACED_WAIT',completed_articles=completed,
                        total_articles=len(rows),wait_seconds=delay,rate_headers=last_headers,**cache.summary(campaign)))
                    time.sleep(delay)
                    continue
                call=cache.reserve(campaign,request,tokens)
                with (pilot.HOME/'requests'/f'{call}.json').open('x',encoding='utf-8') as stream:
                    json.dump(dict(request=request,article_keys=[a['key'] for a in batch]),stream)
                result=session.post('https://api.openai.com/v1/embeddings',json=request,
                    headers={'Authorization':'Bearer '+key},timeout=(10,60),allow_redirects=False)
                last_headers={k:result.headers[k] for k in HEADERS if k in result.headers}
                headers=pilot.HOME/'headers';headers.mkdir(exist_ok=True)
                atomic_json(headers/f'{call}.json',dict(http_status=result.status_code,headers=last_headers))
                window.append((time.monotonic(),tokens))
                if result.status_code==429:
                    error=result.json().get('error',{})
                    code=error.get('code');kind=error.get('type')
                    cache.rejected(call,dict(http_status=429,code=code,error_type=kind,
                                           headers=last_headers,at=utc()))
                    if code not in RATE_CODES:
                        raise RuntimeError('OpenAI HTTP429 '+str(code)+'; billing/unknown error: no retry')
                    rejected_in_row+=1
                    if rejected_in_row>3:
                        raise RuntimeError('Repeated temporary rate rejection; stopped after bounded recovery')
                    limit=min(limit,200_000)
                    delay=float(result.headers.get('retry-after',60))
                    atomic_json(root/'progress.json',dict(status='RATE_REJECTED_WAIT',completed_articles=completed,
                        total_articles=len(rows),error_code=code,wait_seconds=delay,**cache.summary(campaign)))
                    time.sleep(min(max(delay,5),60))
                    continue
                if result.status_code!=200:
                    raise RuntimeError('OpenAI HTTP '+str(result.status_code)+'; request retained without retry')
                cache.complete(call,batch,result.json(),tokens)
                limits=[int(result.headers[h]) for h in ['x-ratelimit-limit-tokens','x-ratelimit-limit-project-tokens']
                        if str(result.headers.get(h,'')).isdigit()]
                if limits:
                    limit=min(limits)
                rejected_in_row=0
                completed+=len(batch)
                atomic_json(root/'progress.json',dict(status='EMBEDDING_RATE_PACED',completed_articles=completed,
                    total_articles=len(rows),rate_headers=last_headers,**cache.summary(campaign)))
                print(f'Embeddings {completed}/{len(rows)} ; USD {cache.summary(campaign)["committed_usd"]}',flush=True)
                break
        summary=dict(status='EMBEDDINGS_COMPLETE',total_articles=len(rows),**cache.summary(campaign))
        atomic_json(root/'embedding-completion.json',summary)
        atomic_json(root/'progress.json',summary)
        return summary
    except Exception as exc:
        atomic_json(root/'progress.json',dict(status='STOPPED',error_type=type(exc).__name__,message=str(exc)[:250],
            automatic_ambiguous_retry=False,**cache.summary(root.name)))
        raise
    finally:
        if session:
            session.close()
        cache.close()


if __name__=='__main__':
    with exclusive(pilot.HOME/'pilot.lock'):
        print(json.dumps(resume()))
