"""Bounded native DeepSeek Search/Fetch, with immutable raw receipts and no GPT relay.

The internal web_search_call representation is an application adapter, NOT a
claim that the chat model invoked a Responses tool or independently browsed.
"""
from datetime import datetime, timedelta, timezone
import ipaddress
import json
import re
import time
from urllib.parse import urlsplit

from .prompts import native_search_protocol, instructions, response_schema

SEARCH_URL='https://api.deepseek.com/v1/tools/search'
FETCH_URL='https://api.deepseek.com/v1/tools/fetch'
CHAT_URL='https://api.deepseek.com/chat/completions'


def public_url(value):
    if not isinstance(value,str) or len(value)>8192 or any(c.isspace() or ord(c)<32 for c in value):
        return False
    try:
        parts=urlsplit(value)
        host=(parts.hostname or '').lower().rstrip('.')
        if (parts.scheme not in ('https','http') or not host or parts.username is not None
                or parts.password is not None or parts.port not in (None,80,443)
                or host=='localhost' or host.endswith(('.localhost','.local','.internal'))):
            return False
        try:
            return ipaddress.ip_address(host).is_global
        except ValueError:
            return '.' in host
    except ValueError:
        return False


def build_request(context,config,base_schema):
    if (not native_search_protocol(context.get('analysis_protocol'))
            or context.get('analysis_mode')!='web_search' or config.provider!='deepseek'
            or config.analysis_mode!='web_search'):
        raise ValueError('Contexte incompatible avec DeepSeek Search natif')
    cutoff=datetime.fromisoformat(context['evidence_cutoff_utc'].replace('Z','+00:00'))
    if cutoff.tzinfo is None:
        raise ValueError('Cutoff DeepSeek sans fuseau')
    cutoff=cutoff.astimezone(timezone.utc)
    # Public identity only. No price path, consensus, keys, account or portfolio in queries.
    symbol=re.sub(r'[^A-Za-z0-9.\-]',' ',context['symbol']).strip()[:16]
    issuer=re.sub(r'[^\w .\-]',' ',str(context.get('issuer_reference',{}).get('company_name') or ''),flags=re.UNICODE)
    identity=f'{symbol} {issuer}'.strip()[:45]
    since=(cutoff-timedelta(days=config.max_source_age_days)).date().isoformat()
    until=(cutoff+timedelta(days=1)).date().isoformat()
    suffixes=('earnings guidance outlook','risks dilution debt SEC')
    searches=[dict(query=f'{identity} {tail} after:{since} before:{until}',
                   count=config.deepseek_search_results,need_content=True)
              for tail in suffixes[:min(config.deepseek_search_queries,config.max_tool_calls)]]
    if any(not 1<=len(r['query'])<=128 for r in searches):
        raise ValueError('Requête DeepSeek hors limite de 128 caractères')
    return dict(provider='deepseek',web_provider='deepseek',analysis_mode='web_search',
        analysis_protocol=context['analysis_protocol'],search_requests=searches,
        fetch_max_pages=min(config.deepseek_fetch_pages,max(0,config.max_tool_calls-len(searches))),
        max_web_calls=config.max_tool_calls,text_chars=config.deepseek_web_text_chars,
        analysis_model=config.deepseek_model,analysis_max_tokens=config.max_output_tokens,
        analysis_instructions=instructions('web_search',context['analysis_protocol'])+'\nAllowed decisions: '+(
            'LONG, SHORT, ABSTAIN' if config.allow_short else 'LONG, ABSTAIN (SHORT forbidden)')+
            '\nSearch and optional Fetch were performed separately through DeepSeek. '
            'Use ONLY the supplied data and Web evidence. Search summaries are not full page reads. '
            'A fetched page is marked explicitly. Do not claim you independently browsed. '
            'Copy published_at exactly from the supplied provider_date (null if unknown); '
            'retrieval time, upcoming event dates and page updates are NOT publication dates. '
            'Return json matching: '+json.dumps(response_schema(base_schema,context['analysis_protocol'])),context=context)


def _utc_now():
    return datetime.now(timezone.utc).isoformat()


def evidence(searches,fetches,text_chars):
    """Model input uses only safe returned URLs, bounded text and provider date claims."""
    pages={r['request']['url']:r['response'] for r in fetches if r.get('response')}
    values={}
    for receipt in searches:
        for item in receipt.get('response',{}).get('results',[]):
            url=item.get('url')
            if not public_url(url) or url in values:
                continue
            page=pages.get(url)
            content=(page or {}).get('content') or item.get('content') or ''
            values[url]=dict(url=url,title=item.get('title','')[:1000],provider_date=item.get('date'),
                summary=item.get('summary','')[:2000],snippet=item.get('snippet','')[:500],
                content=content[:text_chars],content_truncated=len(content)>text_chars,
                page_fetched=bool(page and page.get('content')),
                provenance='DeepSeek Search/Fetch; publication date unverified')
    return list(values.values())


def run(payload,post,key):
    """Sequential hard-capped calls. No automatic retry or other provider fallback."""
    archive=dict(provider='deepseek',web_provider='deepseek',analysis_mode='web_search',
        analysis_protocol=payload['analysis_protocol'],search_receipts=[],fetch_receipts=[],
        web_status='incomplete',status='failed')
    last_call=None

    def call(url,request,label,receipts):
        nonlocal last_call
        # Below the documented account QPS ceiling for this sequential client.
        if last_call is not None:
            time.sleep(max(0,.25-(time.monotonic()-last_call)))
        last_call=time.monotonic()
        receipt=dict(request=request,started_at_utc=_utc_now())
        receipts.append(receipt)  # An unsuccessful attempt is also archived.
        try:
            receipt['response']=post(url,request,key,label)
        except RuntimeError as exc:
            receipt.update(error=str(exc),completed_at_utc=_utc_now())
            raise
        receipt['completed_at_utc']=_utc_now()
        return receipt['response']

    try:
        if (not 1<=len(payload['search_requests'])<=payload['max_web_calls']
                or len(payload['search_requests'])+payload['fetch_max_pages']>payload['max_web_calls']):
            raise RuntimeError('Budget DeepSeek Search/Fetch invalide')
        for request in payload['search_requests']:
            raw=call(SEARCH_URL,request,'DeepSeek Search',archive['search_receipts'])
            if not isinstance(raw.get('results'),list) or any(not isinstance(i,dict) for i in raw['results']):
                raise RuntimeError('DeepSeek Search résultats invalides')
            if len(raw['results'])>request['count']:
                raise RuntimeError('DeepSeek Search nombre de résultats hors limite demandée')
            for item in raw['results']:
                if any(not isinstance(item.get(k,''),str) for k in ('url','title','content','summary','snippet')):
                    raise RuntimeError('DeepSeek Search texte invalide')
                if item.get('date') is not None and not isinstance(item['date'],str):
                    raise RuntimeError('DeepSeek Search date invalide')
        # Fetch only URLs really returned by Search, never model-supplied URLs.
        sources=evidence(archive['search_receipts'],[],payload['text_chars'])
        for item in sources[:payload['fetch_max_pages']]:
            try:
                raw=call(FETCH_URL,dict(url=item['url']),'DeepSeek Fetch',archive['fetch_receipts'])
            except RuntimeError as exc:
                if getattr(exc,'status_code',None) in (403,404):
                    continue  # Respect access policies; no bypass or retry of an unavailable page.
                raise
            if not isinstance(raw.get('content'),str) or not isinstance(raw.get('title',''),str):
                raise RuntimeError('DeepSeek Fetch contenu invalide')
        archive['web_status']='completed'
        web=evidence(archive['search_receipts'],archive['fetch_receipts'],payload['text_chars'])
        analysis=dict(model=payload['analysis_model'],max_tokens=payload['analysis_max_tokens'],
            response_format={'type':'json_object'},messages=[
                dict(role='system',content=payload['analysis_instructions']),
                dict(role='user',content=json.dumps(dict(context=payload['context'],web_evidence=web),
                    ensure_ascii=False,allow_nan=False))])
        archive['analysis_request']=analysis
        archive['analysis_started_at_utc']=_utc_now()
        archive['analysis_response']=post(CHAT_URL,analysis,key,'DeepSeek')
        archive['analysis_completed_at_utc']=_utc_now()
        archive['status']='completed'
    except RuntimeError as exc:
        archive['error']=str(exc)
    return archive


def search_traces(response):
    """Internal adapter reconstructed exclusively from actual Search receipts."""
    if (response.get('web_status')!='completed' or response.get('error')
            or not response.get('search_receipts')):
        return []
    traces=[]
    for receipt in response['search_receipts']:
        raw=receipt.get('response',{})
        if receipt.get('error') or not isinstance(raw.get('results'),list):
            return []
        sources=[dict(url=r['url'],title=r.get('title',''),provider_date=r.get('date'))
                 for r in raw['results'] if public_url(r.get('url'))]
        traces.append(dict(type='web_search_call',status='completed',
            adapter='deepseek_search_receipt',action=dict(type='search',sources=sources)))
    return traces
