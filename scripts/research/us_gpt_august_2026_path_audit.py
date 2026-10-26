"""Bounded retrospective GPT scores, annual Oracle TOP20, both H20 excursions.

Never publishes to live LLM/risk/order tables. Preparation/outcomes SELECT only;
analysis appends immutable claims/replies to llm_news_analysis_research_runs.
The historical context is reconstructed, NOT certified point-in-time.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime,timezone
from decimal import Decimal
import json
import logging
from pathlib import Path
import re
from threading import Lock,local

import numpy as np
import pandas as pd
from sqlalchemy import bindparam,select,text

from common.daily_bar_sources import select_daily_bars
from common.market_calendar import get_market_calendar
from modelFactory.oracle.security_continuity import load_security_discontinuities,path_crosses_known_discontinuity
from scripts.research.oracle_path_confirmation import exclusive_run
from scripts.research.us_concentrated_historical_tapes import digest,verify_hashes
from scripts.research.us_news_materiality_feasibility import META_FIELDS,raw_publication_reason
from service.llm_directional.config import load_filter_config,FilterConfig
from service.llm_directional.direction_score import score_policy
from service.llm_directional.news_cache import NewsCache,IMPORTS,atomic_json,sha,dumps
from service.llm_directional.openai_client import build_request,ResponsesClient
from service.llm_directional.prompts import TREND_EVIDENCE_VERSION

LOG=logging.getLogger(__name__)
SOURCE=Path('artifacts/research/us_news_gpt_top20_history/20261015-v1')
PREFIX='gpt-aug2026-path-v1'
CAP=Decimal('4')


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def utc():return datetime.now(timezone.utc).isoformat()
def iso(value):return pd.Timestamp(value).isoformat()


def sessions(start='2026-06-01',end='2026-10-01'):
    return [s for s in get_market_calendar('US_EQ',allow_us_weekday_fallback=False).sessions(start,end) if s.is_open]


def cfg_snapshot():
    cfg=load_filter_config()
    if cfg.model!='gpt-6-luna':raise ValueError('Reconfirm model/pricing; no silent model substitution')
    return replace(cfg,provider='openai',analysis_mode='local_data_only',scoring_mode='direction_1_10',
        separate_trend_evidence=True,oracle_top_n=20,horizon=20,timeout_seconds=300,max_output_tokens=12000)


def rows(conn,sql,params,expanding=()):
    q=text(sql)
    for name in expanding:q=q.bindparams(bindparam(name,expanding=True))
    return [dict(r) for r in conn.execute(q,params).mappings()]


def read_only(conn):
    if conn.dialect.name=='mysql':
        conn.execute(text('SET TRANSACTION READ ONLY'))
        conn.execute(text("SET SESSION time_zone='+00:00'"))
        conn.execute(text('SET SESSION MAX_EXECUTION_TIME=25000'))


def price_context(raw,trade,calendar):
    """Only <= J; whole-row provider selection, no future prices in prompt."""
    frame=raw[pd.to_datetime(raw.date).le(trade)].copy()
    if frame.empty:return [],None,'NO_J_PRICE'
    frame=select_daily_bars(frame,config={'market_data':{'daily_bars_preferred_source':'eodhd'}})
    frame=frame.sort_values('date').tail(21)
    if pd.Timestamp(frame.iloc[-1].date)!=trade:return [],None,'NO_J_PRICE'
    ohlc=frame[['open','high','low','close']].astype(float)
    good=np.isfinite(ohlc).all(axis=1)&ohlc.gt(0).all(axis=1)&frame.is_filled.eq(0)
    good &= frame.data_source.isin(['eodhd_eod','alpaca_sip'])
    good &= ohlc.low.le(ohlc[['open','close']].min(axis=1))&ohlc.high.ge(ohlc[['open','close']].max(axis=1))
    expected=[s.session_date for s in calendar if pd.Timestamp(s.session_date)<=trade][-len(frame):]
    if (not good.all() or list(pd.to_datetime(frame.date).dt.date)!=expected or
            frame.data_source.nunique()!=1 or frame.data_adjustment.nunique()!=1):
        return [],None,'INCONSISTENT_PRICE_HISTORY'
    closes=[dict(date=str(pd.Timestamp(r.date).date()),close=float(r.close)) for r in frame.itertuples()]
    last=frame.iloc[-1];close=float(last.close)
    value=dict(symbol=str(last.symbol),trade_date=str(trade.date()),source=str(last.data_source),
        adjustment=str(last.data_adjustment),open=float(last.open),high=float(last.high),low=float(last.low),close=close,
        volume=float(last.volume) if pd.notna(last.volume) else None,history_sessions=len(frame),
        returns_pct={str(n):float((close/float(frame.iloc[-n-1].close)-1)*100) if len(frame)>n else None for n in (1,5,10,20)},
        caveat='Retrospective mutable history, not certified historical availability. Descriptive context only.')
    receipt=max(pd.Timestamp(last.ingested_at),pd.Timestamp(last.last_updated))
    return closes,dict(source_id='price_volume:'+sha(value),kind='price_volume',text=dumps(value),
        available_at_utc=iso(receipt),eligible_for_direction=False,
        historical_pit_qualified=False,context_qualification='RETROSPECTIVE_CONTEXT_ONLY'),None


def make_context(candidate,news,prices,identity,cfg,calendar):
    trade=pd.Timestamp(candidate.date);cutoff=pd.Timestamp(next(s.close_at_utc for s in calendar if s.session_date==trade.date()))
    part=news[(news.symbol==candidate.symbol)&news.published_at_utc.ge(cutoff-pd.Timedelta(days=7))&news.published_at_utc.lt(cutoff)].copy()
    accepted=[];excluded=Counter()
    for r in part.sort_values(['published_at_utc','article_id'],ascending=[False,True]).to_dict('records'):
        reason=raw_publication_reason(r['provider_publication'],r['published_at_utc'])
        if reason:excluded[reason]+=1;continue
        accepted.append(r)
    # Same bounded rule as the live local context, not a claim of full corpus input.
    picked=[];seen=set()
    for r in accepted:
        content_key=r['content_sha256'] or sha([r['headline'],r['summary']])
        if content_key in seen:continue
        seen.add(content_key);picked.append(r)
    retained=picked[:cfg.local_news_max_articles]
    evidence=[]
    for r in retained:
        body=str(r['body'] or '')
        value=dict(article_id=r['article_id'],headline=str(r['headline'] or '')[:500],
            summary=str(r['summary'] or '')[:700],body=body[:cfg.local_news_max_chars],
            publication_utc=iso(r['published_at_utc']),body_truncated=bool((r['content_chars'] or 0)>cfg.local_news_max_chars),
            full_body_sha256=r['content_sha256'])
        # Never send a possible credential even if embedded in a public article.
        # Discard the source; do not weaken the outbound guard or log its text.
        if re.search(r'\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}',dumps(value)):
            excluded['POSSIBLE_SECRET_PATTERN_IN_ARCHIVED_NEWS']+=1
            continue
        evidence.append(dict(source_id='news:'+r['article_id']+':'+sha(value),kind='news',text=dumps(value),
            published_at_utc=iso(r['published_at_utc']),available_at_utc=iso(max(pd.Timestamp(r['created_at']),pd.Timestamp(r['updated_at']))),
            eligible_for_direction=False,historical_pit_qualified=False,
            context_qualification='RETROSPECTIVE_PUBLICATION_TIMED_NOT_RECEIPT_PIT'))
    closes,source,price_error=price_context(prices[prices.symbol.eq(candidate.symbol)],trade,calendar)
    if source:evidence.append(source)
    context=dict(symbol=candidate.symbol,oracle_rank=int(candidate.oracle_rank),oracle_score=float(candidate.score),
        issuer_reference=identity,trade_date=str(trade.date()),horizon_sessions=20,
        oracle_target='oracle_path_extreme20',oracle_directional=False,analysis_mode='local_data_only',
        analysis_protocol=TREND_EVIDENCE_VERSION,assessment_objective='QUALITATIVE_TREND',
        direction_score_policy=score_policy(cfg),evidence_cutoff_utc=cutoff.isoformat(),
        observed_at_utc=utc(),prices_through_decision_date=closes,local_evidence=evidence,
        local_evidence_sha256=sha(evidence),evidence_exclusions=dict(excluded),
        local_data_status=dict(news=dict(in_window=len(part),valid_publication=len(accepted),deduplicated=len(picked),
            included=sum(s['kind']=='news' for s in evidence),omitted_by_fixed_limit=max(0,len(picked)-len(retained))),
            consensus={'status':'NO_HISTORICAL_RECEIPT_BEFORE_AUGUST'},
            earnings_calendar={'status':'NOT_RECONSTRUCTED_NO_RECEIPT_PIT'},sec={'status':'NOT_RECONSTRUCTED_NO_RECEIPT_PIT'},
            fundamentals={'status':'NOT_RECONSTRUCTED_NO_RECEIPT_PIT'},price_volume={'status':price_error or 'RETROSPECTIVE_CONTEXT'}),
        freshness_policy=dict(news_publication_max_age_days=7,retrospective_reconstruction=True,
            receipt_pit_certified=False,execution_forbidden=True))
    return context


def request_for(context,cfg):
    # Stable context bytes for exact cache matching. No changes to the live prompt.
    req=build_request(json.loads(dumps(context)),cfg)
    req['reasoning']={'effort':'low'}
    req['instructions']+='''\nRESEARCH DISCLOSURE: This is a retrospective reconstruction, not a live decision.
The evidence publication window ends at evidence_cutoff_utc, but actual receipts and this
analysis happened later. Do not use any outside knowledge or information dated after cutoff.
These historical texts/prices may inform only a tentative tendency. None authorizes execution.
Do not claim historical PIT, current consensus, or sufficient execution-grade evidence.
Missing news/consensus is unknown, not bearish. Do not force any distribution of scores.
Use direction_score null if no usable basis. Quotes must be exact supplied text substrings.'''
    return req


def check_request(req):
    if req['model']!='gpt-6-luna' or req.get('tools') or req.get('tool_choice')!='none' or req.get('store') is not False:
        raise ValueError('Only stateless GPT local-data research allowed')
    from service.llm_directional.resume_failed import public_payload_check
    public_payload_check(json.loads(req['input']),req)
    if len(dumps(req).encode())>240000:raise ValueError('Oversized context; no implicit truncation')


def qualify(response,request):
    """Research parser only: never bypass a live receipt/freshness gate."""
    import jsonschema
    if response.get('status')!='completed':raise ValueError('Incomplete model response')
    if any(o.get('type','').endswith('_call') for o in response.get('output',[])):raise ValueError('Tool call forbidden')
    messages=[c['text'] for o in response.get('output',[]) if o.get('type')=='message'
        for c in o.get('content',[]) if c.get('type')=='output_text']
    if len(messages)!=1:raise ValueError('One structured answer required')
    # Reject duplicate answer keys/nonfinite constants as well as schema violations.
    def unique(pairs):
        value={}
        for k,v in pairs:
            if k in value:raise ValueError('Duplicate answer key')
            value[k]=v
        return value
    def bad_constant(value):raise ValueError('Nonfinite answer')
    result=json.loads(messages[0],object_pairs_hook=unique,parse_constant=bad_constant)
    jsonschema.validate(result,request['text']['format']['schema'])
    ctx=json.loads(request['input'])
    if result['symbol']!=ctx['symbol'] or result['sources']:raise ValueError('Identity/Web mismatch')
    if (result['trend_status']=='UNDETERMINABLE')!=(result['direction_score'] is None):raise ValueError('Null/status mismatch')
    supplied={s['source_id']:s['text'] for s in ctx['local_evidence']}
    for citation in result['local_evidence']:
        quote=citation['quote']
        if citation['source_id'] not in supplied or not quote.strip() or quote not in supplied[citation['source_id']]:
            raise ValueError('Untraceable quote')
    if result['trend_status']=='ASSESSED' and not result['local_evidence']:raise ValueError('Uncited tendency')
    # No promotion of retrospective packets to qualified live evidence.
    result['reported_evidence_quality']=result['evidence_quality']
    result['evidence_quality']='PARTIAL' if result['direction_score'] is not None else 'INSUFFICIENT'
    result['research_only']=True;result['historical_pit_certified']=False
    return result


def prepare(engine,output):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    source=SOURCE/'months/2026-08';manifest=read(source/'prepared.json')
    verify_hashes(source,manifest['files'])
    candidates=pd.read_parquet(source/'candidates.parquet')
    calendar=sessions();aug=[s for s in calendar if str(s.session_date).startswith('2026-08')]
    if len(aug)!=21 or len(candidates)!=420 or candidates.duplicated(['date','symbol']).any():raise ValueError('Incomplete month')
    if set(candidates.date.dt.date)!=set(s.session_date for s in aug):raise ValueError('Missing session')
    if any(set(g.oracle_rank)!=set(range(1,21)) for _,g in candidates.groupby('date')):raise ValueError('Incomplete TOP20')
    if not pd.to_datetime(candidates.model_available_date).lt('2026-01-01').all():raise ValueError('Future Oracle model')
    expected=manifest['model']
    for col,key in [('model_sha256','model_sha256'),('feature_profile_sha256','profile_sha256'),('fold_start','fold')]:
        if not candidates[col].map(str).eq(str(expected[key])).all():raise ValueError('Oracle lineage mismatch')
    if candidates[['future_return','oracle_extreme10']].notna().any().any():raise ValueError('Unexpected future labels')
    symbols=sorted(candidates.symbol.unique());cfg=cfg_snapshot()
    old_packets=read(source/'packets.json');identity={p['symbol']:p['issuer_reference'] for p in old_packets}
    all_news=[];all_prices=[]
    with engine.connect() as conn:
        read_only(conn)
        earliest=conn.execute(text('SELECT MIN(available_at) FROM stock_analyst_consensus_eodhd_history')).scalar_one()
        if earliest is not None and pd.Timestamp(earliest)<pd.Timestamp('2026-09-01'):
            raise ValueError('Historical consensus now exists; qualify it rather than silently omit')
        for i,symbol in enumerate(symbols):
            atomic_json(output/'progress.json',dict(status='PREPARING',symbol=symbol,completed=i,total=len(symbols),api_calls=0))
            sql=META_FIELDS.replace('n.headline,','n.headline,n.summary,LEFT(n.content,12000) body,')+'''
                FROM news_ticker_map m FORCE INDEX(idx_news_ticker_map_symbol)
                STRAIGHT_JOIN news_raw n ON n.article_id=m.article_id
                WHERE m.symbol=:symbol AND n.published_at_utc>=:start AND n.published_at_utc<:end
                AND n.ingestion_source IN ('eodhd','alpaca') LIMIT 20001'''
            part=rows(conn,sql,dict(symbol=symbol,start='2026-07-27',end='2026-09-01'))
            if len(part)>20000:raise ValueError('News query truncated')
            all_news.extend(part)
            all_prices.extend(rows(conn,'''SELECT symbol,date,open,high,low,close,volume,is_filled,
                data_source,data_adjustment,ingested_at,last_updated FROM stock_bars_daily
                WHERE symbol=:symbol AND date BETWEEN '2026-06-01' AND '2026-08-31'
                AND data_source IN ('eodhd_eod','alpaca_sip')''',dict(symbol=symbol)))
    news=pd.DataFrame(all_news);prices=pd.DataFrame(all_prices)
    if news.duplicated(['article_id','symbol']).any():raise ValueError('Duplicate article association')
    news['published_at_utc']=pd.to_datetime(news.published_at_utc,utc=True)
    contexts=[make_context(r,news,prices,identity[r.symbol],cfg,calendar) for r in candidates.itertuples()]
    requests=[request_for(c,cfg) for c in contexts]
    for req in requests:check_request(req)
    candidates.to_parquet(output/'candidates.parquet',index=False)
    news.to_parquet(output/'news-snapshot.parquet',index=False);prices.to_parquet(output/'daily-context-snapshot.parquet',index=False)
    atomic_json(output/'requests.json',requests)
    value=dict(experiment=PREFIX,created_at_utc=utc(),month='2026-08',sessions=21,candidate_days=420,
        distinct_symbols=len(symbols),oracle=expected,configuration=cfg.snapshot(),budget_usd=4,
        prompt_protocol=TREND_EVIDENCE_VERSION,research_disclosure_added=True,
        evidence='J-only price history plus max 8 latest deduplicated publication-qualified news over 7 calendar days',
        unavailable_families=['consensus','SEC receipts','earnings calendar receipts','fundamentals receipts'],
        input_sources_current_mutable_non_PIT=True,historical_pit_certified=False,
        llm_memory_contamination_not_excluded=True,current_issuer_metadata=True,static_universe_survivorship_reserved=True,
        outcome_selection_forbidden=True,entry='J+1 regular open',horizon_sessions=20,
        order_rule='First occurrence of global high vs global low. Same 5m bar remains ambiguous.',
        thresholds={'lean_bearish':'1..4','mixed':'5..6','lean_bullish':'7..10','strict_long':'>8','strict_short':'<3'},
        sql_write_allowlist=['llm_news_analysis_research_runs'],production_changed=False,orders=False,training=False,web=False,
        pricing={'input_usd_per_million':.10,'cache_write_usd_per_million':.125,'output_usd_per_million':.50,
            'verified_utc':utc(),'source':'https://developers.openai.com/api/docs/models/gpt-6-luna'},
        request_count=len(requests),with_news=sum(any(s['kind']=='news' for s in c['local_evidence']) for c in contexts),
        without_price=sum(not c['prices_through_decision_date'] for c in contexts),
        files={p.name:digest(p) for p in output.iterdir() if p.name not in ('progress.json','protocol.json')},
        source_hashes={str(Path(__file__)):digest(Path(__file__)),
            'service/llm_directional/prompts.py':digest(Path('service/llm_directional/prompts.py')),
            'service/llm_directional/openai_client.py':digest(Path('service/llm_directional/openai_client.py'))})
    atomic_json(output/'protocol.json',value);atomic_json(output/'progress.json',dict(status='PREPARED',api_calls=0,**{k:value[k] for k in ('sessions','candidate_days','with_news','distinct_symbols')}))
    return value


def upper_cost(req):
    return (Decimal(len(dumps(req).encode())+2000)*Decimal('.125')+Decimal(req['max_output_tokens'])*Decimal('.50'))/1000000


def usage_cost(raw,req):
    u=raw.get('usage') or {};details=u.get('input_tokens_details') or {}
    fields=[u.get('input_tokens'),u.get('output_tokens'),details.get('cache_write_tokens',0),details.get('cached_tokens',0)]
    if any(type(n) is not int or n<0 for n in fields):raise ValueError('Unknown billed usage')
    a,b,w,c=fields
    if w+c>a or b>req['max_output_tokens'] or raw.get('service_tier') not in (None,'default'):
        raise ValueError('Unqualified usage/tier')
    if not str(raw.get('model','')).startswith('gpt-6-luna'):raise ValueError('Unexpected returned model')
    return (Decimal(a)*Decimal('.10')+Decimal(w)*Decimal('.025')+Decimal(b)*Decimal('.50'))/1000000


def saved_import(engine,source):
    with engine.connect() as conn:
        row=conn.execute(select(IMPORTS).where(IMPORTS.c.import_id==sha(source))).mappings().first()
    if row is None:return None
    snap=json.loads(row['snapshot_json'])
    if sha(snap)!=row['snapshot_sha256']:raise ValueError('Altered archived research record')
    return snap


def analyze(engine,output,workers=3):
    root=Path(output);p=read(root/'protocol.json');verify_hashes(root,p['files']);verify_hashes(Path('.'),p['source_hashes'])
    requests=read(root/'requests.json');cfg=FilterConfig(**p['configuration']);cache=NewsCache(engine)
    ledger=root/'budget.json';budget=read(ledger) if ledger.exists() else dict(cap_usd='4',entries={})
    if Decimal(budget['cap_usd'])!=CAP:raise ValueError('Budget changed')
    lock=Lock();tls=local();done={};stop=False
    def total():return sum((Decimal(e['charge_usd']) for e in budget['entries'].values()),Decimal(0))
    def one(index,request):
        nonlocal stop
        check_request(request);key=sha(request);source=f'{PREFIX}:response:{key}';folder=root/'api'/key
        existing=saved_import(engine,source)
        if existing:
            if existing['request']!=request:raise ValueError('Cache request mismatch')
            return index,existing
        claim_source=f'{PREFIX}:claim:{key}';claim=saved_import(engine,claim_source)
        if (folder/'response.json').exists():
            if read(folder/'request.json')!=request:raise ValueError('Durable input mismatch')
            raw=read(folder/'response.json')
        else:
            if claim or (folder/'request.json').exists():raise ValueError('Unresolved paid attempt; no automatic retry')
            with lock:
                if stop:raise ValueError('New dispatch stopped')
                bound=upper_cost(request)
                if total()+bound>CAP:stop=True;raise ValueError('USD4 budget reached BEFORE call')
                if key in budget['entries']:raise ValueError('Unresolved budget reservation')
                budget['entries'][key]=dict(status='RESERVED',charge_usd=str(bound),upper_usd=str(bound))
                atomic_json(ledger,budget)
            # Immutable durable claim across processes/campaign restarts; no live tables.
            cache.save_import(claim_source,dict(request_sha256=key,request=request,claimed_at_utc=utc(),research_only=True))
            folder.mkdir(parents=True,exist_ok=False);atomic_json(folder/'request.json',request)
            if not hasattr(tls,'client'):tls.client=ResponsesClient(cfg)
            try:
                raw=tls.client(request);atomic_json(folder/'response.json',raw)
            except Exception as exc:
                with lock:stop=True
                atomic_json(folder/'error.json',dict(error_type=type(exc).__name__,no_retry=True))
                raise RuntimeError('Ambiguous API/transport result; dispatch stopped, no paid retry') from None
        charge=usage_cost(raw,request)
        with lock:
            entry=budget['entries'].get(key)
            if entry is None or charge>Decimal(entry['upper_usd']):raise ValueError('Unreserved/unbounded usage')
            entry.update(status='COMPLETE',charge_usd=str(charge),usage=raw['usage'])
            atomic_json(ledger,budget)
        try:assessment=qualify(raw,request);status='VALID'
        except Exception as exc:assessment={'error_type':type(exc).__name__,'error':str(exc)[:250]};status='INVALID'
        saved=dict(request=request,response=raw,response_sha256=sha(raw),status=status,assessment=assessment,
            saved_at_utc=utc(),usage=raw['usage'],cost_usd=str(charge),research_only=True)
        cache.save_import(source,saved)
        return index,saved
    errors=[]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        pending={};next_index=0
        while pending or (next_index<len(requests) and not stop):
            while len(pending)<workers and next_index<len(requests) and not stop:
                future=pool.submit(one,next_index,requests[next_index]);pending[future]=next_index;next_index+=1
            if not pending:break
            from concurrent.futures import wait,FIRST_COMPLETED
            finished,_=wait(pending,return_when=FIRST_COMPLETED)
            for future in finished:
                index=pending.pop(future)
                try:
                    i,value=future.result();done[i]=value
                    LOG.info('GPT %s/%s %s %s score=%s',len(done),len(requests),json.loads(requests[i]['input'])['symbol'],value['status'],value['assessment'].get('direction_score'))
                except Exception as exc:
                    stop=True;errors.append(dict(index=index,error_type=type(exc).__name__,error=str(exc)[:250]))
            atomic_json(root/'progress.json',dict(status='ANALYZING' if not stop else 'STOPPING',completed=len(done),total=len(requests),
                valid=sum(v['status']=='VALID' for v in done.values()),invalid=sum(v['status']=='INVALID' for v in done.values()),
                committed_usd=float(total()),cap_usd=4,errors=errors,updated_at_utc=utc()))
    result=[]
    for i,request in enumerate(requests):
        ctx=json.loads(request['input']);value=done.get(i)
        result.append(dict(date=ctx['trade_date'],symbol=ctx['symbol'],oracle_rank=ctx['oracle_rank'],cache_key=sha(request),
            status=value['status'] if value else 'NOT_ANALYZED',assessment=value.get('assessment') if value else None))
    atomic_json(root/'scores.json',result)
    summary=dict(status='SCORES_COMPLETED' if len(done)==len(requests) else 'PARTIAL_STOPPED',completed=len(done),total=len(requests),
        valid=sum(r['status']=='VALID' for r in result),invalid=sum(r['status']=='INVALID' for r in result),errors=errors,
        committed_usd=float(total()),cap_usd=4,score_file_sha256=digest(root/'scores.json'))
    atomic_json(root/'analysis.json',summary);atomic_json(root/'progress.json',summary)
    return summary


def measure_path(frame,window,registry,symbol,actions):
    """H20, first touch of each GLOBAL extremum; never infer same-bar order."""
    start=pd.Timestamp(window[0].open_at_utc);end=pd.Timestamp(window[-1].close_at_utc)
    raw=frame[(pd.to_datetime(frame.bar_timestamp,utc=True)>=start)&(pd.to_datetime(frame.bar_timestamp,utc=True)<end)].copy()
    if raw.empty:return dict(path_status='NO_INTRADAY',high_max_pct=None,low_min_pct=None)
    raw=raw.sort_values('bar_timestamp');raw['ts']=pd.to_datetime(raw.bar_timestamp,utc=True)
    ohlc=raw[['open','high','low','close']].astype(float)
    valid=np.isfinite(ohlc).all(axis=1)&ohlc.gt(0).all(axis=1)
    valid &= ohlc.low.le(ohlc[['open','close']].min(axis=1))&ohlc.high.ge(ohlc[['open','close']].max(axis=1))
    valid &= raw.is_filled.eq(0)&raw.volume.gt(0)&raw.data_adjustment.eq('raw')
    valid &= pd.to_datetime(raw.bar_end_timestamp,utc=True).eq(raw.ts+pd.Timedelta(minutes=5))
    expected=pd.DatetimeIndex([t for s in window for t in pd.date_range(s.open_at_utc,s.close_at_utc,freq='5min',inclusive='left')])
    quality=[]
    if raw.ts.duplicated().any():quality.append('DUPLICATE_BARS')
    if not valid.all():quality.append('INVALID_BARS')
    clean=raw[valid].drop_duplicates('ts',keep=False)
    if set(clean.ts)!=set(expected):quality.append('INCOMPLETE_5M_GRID')
    if start not in set(clean.ts):return dict(path_status='MISSING_ENTRY_OPEN',high_max_pct=None,low_min_pct=None)
    if path_crosses_known_discontinuity(symbol,pd.Timestamp(window[0].session_date),pd.Timestamp(window[-1].session_date),registry):
        quality.append('IDENTITY_DISCONTINUITY')
    split=actions[actions.symbol.eq(symbol)&actions.action_type.str.lower().isin(['split','reverse_split','stock_split'])]
    split=split[pd.to_datetime(split.effective_date).between(pd.Timestamp(window[0].session_date),pd.Timestamp(window[-1].session_date))]
    if len(split):quality.append('SPLIT_IN_WINDOW_RAW_PATH_NOT_COMPARABLE')
    ref=float(clean[clean.ts.eq(start)].iloc[0].open)
    high=float(clean.high.max());low=float(clean.low.min())
    high_ts=clean.loc[clean.high.eq(high),'ts'].min();low_ts=clean.loc[clean.low.eq(low),'ts'].min()
    # Include entry price: zero is the ceiling/floor if the path is entirely one-sided.
    positive=max(0.,(high/ref-1)*100);negative=min(0.,(low/ref-1)*100)
    if positive==0:high_ts=start
    if negative==0:low_ts=start
    order='SAME_5M_BAR_UNRESOLVED' if high_ts==low_ts else ('HIGH_FIRST' if high_ts<low_ts else 'LOW_FIRST')
    dominant='TIE' if np.isclose(positive,-negative,atol=1e-8,rtol=0) else ('LONG' if positive>-negative else 'SHORT')
    indices={s.session_date:i+1 for i,s in enumerate(window)}
    return dict(path_status='QUALIFIED_COMPLETE_5M' if not quality else 'UNQUALIFIED_OBSERVED_PATH',quality_reasons=quality,
        entry_price=ref,entry_at_utc=start.isoformat(),end_at_utc=end.isoformat(),bars_observed=len(clean),bars_expected=len(expected),
        high_max_price=max(ref,high),low_min_price=min(ref,low),high_max_pct=positive,low_min_pct=negative,
        high_first_bar_utc=high_ts.isoformat(),low_first_bar_utc=low_ts.isoformat(),
        high_session=indices[high_ts.tz_convert('America/New_York').date()],low_session=indices[low_ts.tz_convert('America/New_York').date()],
        first_extremum=order,dominant_direction=dominant,h20_close_return_pct=(float(clean.iloc[-1].close)/ref-1)*100)


def score_summary(frame):
    qualified=frame[frame.path_status.eq('QUALIFIED_COMPLETE_5M')&frame.status.eq('VALID')].copy()
    qualified['lean']=np.select([qualified.direction_score.le(4),qualified.direction_score.ge(7)],['SHORT','LONG'],default='MIXED_OR_UNKNOWN')
    qualified['correct']=qualified.lean.eq(qualified.dominant_direction)
    direction=qualified[qualified.lean.ne('MIXED_OR_UNKNOWN')&qualified.dominant_direction.ne('TIE')]
    base=dict(candidate_days=len(frame),symbols=int(frame.symbol.nunique()),valid_answers=int(frame.status.eq('VALID').sum()),
        qualified_paths=int(frame.path_status.eq('QUALIFIED_COMPLETE_5M').sum()),qualified_scored=len(qualified),
        directional_scored=len(direction),directional_accuracy_pct=float(direction.correct.mean()*100) if len(direction) else None,
        always_long_accuracy_pct=float(direction.dominant_direction.eq('LONG').mean()*100) if len(direction) else None,
        always_short_accuracy_pct=float(direction.dominant_direction.eq('SHORT').mean()*100) if len(direction) else None,
        no_independent_holdout=True,overlapping_horizons=True,historical_pit_certified=False)
    groups=[]
    for score,g in qualified.dropna(subset=['direction_score']).groupby('direction_score'):
        side='SHORT' if score<=4 else 'LONG' if score>=7 else None
        groups.append(dict(score=int(score),n=len(g),symbols=int(g.symbol.nunique()),dates=int(g.date.nunique()),
            dominant_long_pct=float(g.dominant_direction.eq('LONG').mean()*100),
            dominant_short_pct=float(g.dominant_direction.eq('SHORT').mean()*100),
            mean_positive_max_pct=float(g.high_max_pct.mean()),mean_negative_min_pct=float(g.low_min_pct.mean()),
            high_first_pct=float(g.first_extremum.eq('HIGH_FIRST').mean()*100),
            same_bar_unresolved=int(g.first_extremum.eq('SAME_5M_BAR_UNRESOLVED').sum()),
            direction_accuracy_pct=float(g.dominant_direction.eq(side).mean()*100) if side else None))
    # One non-overlapping episode per symbol; never treat 420 overlapping rows as independent.
    nonoverlap=[];used={}
    for r in direction.sort_values(['date','symbol']).to_dict('records'):
        entry=pd.Timestamp(r['entry_at_utc'])
        if r['symbol'] in used and entry<=used[r['symbol']]:continue
        used[r['symbol']]=pd.Timestamp(r['end_at_utc']);nonoverlap.append(r)
    base['nonoverlap_by_symbol']=dict(n=len(nonoverlap),correct_pct=float(np.mean([r['correct'] for r in nonoverlap])*100) if nonoverlap else None)
    base['score_groups']=groups
    return base


def evaluate(engine,output):
    root=Path(output);p=read(root/'protocol.json');analysis=read(root/'analysis.json')
    if analysis['status']!='SCORES_COMPLETED':raise ValueError('Freeze all GPT answers before loading outcomes')
    if digest(root/'scores.json')!=analysis['score_file_sha256']:raise ValueError('Scores altered')
    verify_hashes(root,p['files']);verify_hashes(Path('.'),p['source_hashes'])
    scores=read(root/'scores.json');calendar=sessions();lookup={s.session_date:i for i,s in enumerate(calendar)}
    windows={r['date']:calendar[lookup[pd.Timestamp(r['date']).date()]+1:lookup[pd.Timestamp(r['date']).date()]+21] for r in scores}
    if any(len(w)!=20 for w in windows.values()):raise ValueError('Twenty mature sessions required')
    first=min(w[0].open_at_utc for w in windows.values());last=max(w[-1].close_at_utc for w in windows.values())
    registry=load_security_discontinuities();paths=[];all_actions=[]
    with engine.connect() as conn:
        read_only(conn)
        symbols=sorted({r['symbol'] for r in scores})
        all_actions=rows(conn,'''SELECT symbol,action_type,effective_date,value_num FROM corporate_action_source_events
            WHERE symbol IN :symbols AND effective_date BETWEEN :start AND :end''',
            dict(symbols=symbols,start=first.date(),end=last.date()),('symbols',))
        actions=pd.DataFrame(all_actions,columns=['symbol','action_type','effective_date','value_num'])
        for i,symbol in enumerate(symbols):
            atomic_json(root/'progress.json',dict(status='MEASURING_PATHS_READ_ONLY',completed=i,total=len(symbols),symbol=symbol,api_calls=0))
            file=root/'outcomes'/f'{symbol}.parquet';file.parent.mkdir(exist_ok=True)
            if file.exists():raw=pd.read_parquet(file)
            else:
                found=rows(conn,'''SELECT symbol,trade_date,bar_timestamp,bar_end_timestamp,open,high,low,close,volume,
                    data_adjustment,is_filled,payload_hash FROM stock_bars_intraday FORCE INDEX(PRIMARY)
                    WHERE symbol=:symbol AND bar_timestamp>=:start AND bar_timestamp<:end
                    AND provider='alpaca' AND data_source='alpaca_sip' AND interval_code='5m' AND market_code='US_EQ'
                    AND session_tag='regular' AND data_adjustment='raw' ORDER BY bar_timestamp''',
                    dict(symbol=symbol,start=first.replace(tzinfo=None),end=last.replace(tzinfo=None)))
                raw=pd.DataFrame(found,columns=['symbol','trade_date','bar_timestamp','bar_end_timestamp','open','high','low','close','volume',
                    'data_adjustment','is_filled','payload_hash']);raw.to_parquet(file,index=False)
            for row in [r for r in scores if r['symbol']==symbol]:
                a=row.get('assessment') or {}
                path=measure_path(raw,windows[row['date']],registry,symbol,actions)
                paths.append(dict(**{k:row[k] for k in ('date','symbol','oracle_rank','status','cache_key')},
                    direction_score=a.get('direction_score'),trend_status=a.get('trend_status'),evidence_quality=a.get('evidence_quality'),**path))
    result=pd.DataFrame(paths).sort_values(['date','oracle_rank'])
    result.to_parquet(root/'results.parquet',index=False);result.to_csv(root/'results.csv',index=False)
    summary=score_summary(result);summary.update(status='COMPLETED_RETROSPECTIVE_NOT_PIT',analysis=analysis,
        outcome_source='ALPACA_SIP_RAW_5M_REGULAR',no_pnl=True,no_trading=True,
        rule='Only complete regular 5m grids, no split/identity break, enter J+1 open, 20 sessions inclusive')
    atomic_json(root/'report.json',summary);atomic_json(root/'progress.json',summary)
    NewsCache(engine).save_import(PREFIX+':evaluation:'+sha(summary),dict(report=summary,results=result.replace({np.nan:None}).to_dict('records')))
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',choices=['prepare','analyze','evaluate'],required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--workers',type=int,default=3)
    args=parser.parse_args()
    if not 1<=args.workers<=4:raise ValueError('1..4 workers')
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    from database.connection import get_sqlalchemy_engine
    engine=get_sqlalchemy_engine(db_name='alpha_trade')
    try:
        if args.phase=='prepare':result=prepare(engine,args.output)
        else:
            with exclusive_run(args.output):
                result=analyze(engine,args.output,args.workers) if args.phase=='analyze' else evaluate(engine,args.output)
        print(dumps({k:v for k,v in result.items() if k not in ('source_hashes','files','configuration','oracle')}))
    finally:engine.dispose()


if __name__=='__main__':main()
