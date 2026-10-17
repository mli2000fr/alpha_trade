"""Frozen annual Oracle TOP20 / stored-news campaign; SQL cache, USD 8 ceiling.

No training, Web, realized prices, orders or production configuration changes.
Only the four llm_news_analysis_* tables may be written. Prepare is read-only.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from datetime import datetime, timezone
from decimal import Decimal
import json
import logging
from pathlib import Path
from threading import Lock, Event, local
from types import SimpleNamespace

import pandas as pd
from sqlalchemy import bindparam, text

from service.llm_directional.news_cache import (NewsCache, CacheMiss, UnresolvedAttempt,
    atomic_json, request_identity, sha)
from service.llm_directional.stored_news import parse
from scripts.research import us_news_gpt_q1_2025_prepare as preparation
from scripts.research.us_news_gpt_q1_2025_run import paid_payload as legacy_paid_payload
from scripts.research.us_news_gpt_q1_2025_continue import usage_with_cache, worst_call_cost
from scripts.research.us_concentrated_historical_tapes import digest
from scripts.research.oracle_path_confirmation import exclusive_run

MODELS={2024:'model-factory-20261014113215-437ed1',
    2025:'model-factory-20261014113226-102eca',2026:'model-factory-20261014113232-bc35a7'}
START, END, TOP, MODEL='2024-01-01','2026-09-30',20,'gpt-6-luna'
CAP=Decimal('8')
SCOPE='SYMBOL_DATE_BUNDLE'
LOG=logging.getLogger(__name__)


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def utc():return datetime.now(timezone.utc).isoformat()


def paid_payload(packet,model):
    # Cache identity retains the EXACT original input string. Restore the field
    # order of the paid pilots after reading our sorted JSON snapshots; do not
    # change old cache keys or mistake unrelated/updated texts for the same input.
    original=dict(packet)
    original['issuer_reference']={k:packet['issuer_reference'][k]
        for k in ('symbol','company_name','exchange') if k in packet['issuer_reference']}
    order=('article_id','headline','summary','body','publication_utc','body_truncated','body_sha256')
    if set(packet['issuer_reference'])-set(original['issuer_reference']):raise ValueError('Unexpected issuer field')
    original['articles']=[]
    for article in packet['articles']:
        if set(article)-set(order):raise ValueError('Unexpected article field')
        original['articles'].append({k:article[k] for k in order if k in article})
    return legacy_paid_payload(original,model)


def freeze(root):
    from common.market_calendar import get_market_calendar
    from modelFactory.oracle_path.predict import load_contract
    path=root/'protocol.json'
    if path.exists():
        value=read(path)
        for name,checksum in value['sources'].items():
            if digest(Path(name))!=checksum:raise ValueError('Frozen source changed: '+name)
        return value
    annual=read(preparation.SOURCE/'protocol.json')['annual_models']
    models={};sources={}
    for year,batch in MODELS.items():
        folder,protocol,profile,folds=load_contract('artifacts/models',batch)
        declaration=annual[str(year)]
        if declaration['batch_id']!=batch:raise ValueError('Unexpected annual model')
        fold=folds[declaration['fold']]
        if fold['model_sha256']!=declaration['model_sha256']:raise ValueError('Annual weight hash mismatch')
        available=max(pd.Timestamp(fold['metrics'][key]) for key in ('train_available_max','val_available_max'))
        if available>=pd.Timestamp(f'{year}-01-01'):raise ValueError('Annual fold contains future labels')
        models[str(year)]=dict(batch_id=batch,fold=declaration['fold'],model_sha256=fold['model_sha256'],
            profile_sha256=digest(folder/'feature_profile.json'),available_date=str(available.date()),
            universe=protocol['universe'],backend=fold['backend'])
        for name in (folder/'protocol.json',folder/'feature_profile.json',Path(fold['model_file'])):
            sources[str(name)]=digest(name)
    sessions=[s for s in get_market_calendar('US_EQ',allow_us_weekday_fallback=False).sessions(START,END) if s.is_open]
    for name in (Path(__file__),Path(preparation.__file__),
            Path('scripts/research/us_news_gpt_september_pilot.py'),
            Path('scripts/research/us_news_gpt_q1_2025_run.py'),
            Path('scripts/research/us_news_gpt_q1_2025_continue.py'),
            Path('scripts/research/us_news_materiality_feasibility.py'),
            Path('service/llm_directional/news_cache.py'),Path('service/llm_directional/stored_news.py'),
            Path('service/llm_directional/openai_client.py'),Path('common/verified_http.py')):
        sources[str(name)]=digest(name)
    value=dict(experiment='US_ORACLE_PATH_TOP20_STORED_NEWS_2024_2026',created_at_utc=utc(),
        start=START,end=END,top=TOP,annual_models=models,gpt_model=MODEL,budget_usd=str(CAP),
        sessions=[str(s.session_date) for s in sessions],closes={str(s.session_date):s.close_at_utc.isoformat() for s in sessions},
        ranking='Annual frozen pre-year fold; probability descending, symbol ascending for exact ties; no future returns',
        news_window_hours=24,cutoff='STRICTLY_BEFORE_NYSE_CLOSE_J',
        prompt='unchanged Q1/September stored-news protocol; one bundle per symbol/date with qualified articles',
        excerpts=dict(headline=500,summary=700,body=2400),no_news='UNKNOWN_NO_QUALIFIED_TEXT, never neutral',
        oversize='UNKNOWN_OVERSIZE, never silently truncate the article set',
        invalid='UNKNOWN_INVALID_RESPONSE, raw answer kept, never retry for another answer',
        accounting='Standard short context; cache-write surcharge included; ignore cache-read discount conservatively',
        historical_pit_certified=False,pit_reserves=['Current issuer metadata',
            'Historical imported/revised news versions; publication is not historical local availability',
            'LLM retrospective knowledge cannot be proven absent','Static training universes / survivorship'],
        sql_write_allowlist=['llm_news_analysis_cache','llm_news_analysis_articles',
            'llm_news_analysis_uses','llm_news_analysis_research_runs'],web=False,orders=False,training=False,
        pnl=False,automatic_paid_retries=False,source_refs='original news IDs plus exact supplied text hash',sources=sources)
    value['before_paid_amendments']=[dict(previous_protocol_sha256=digest(prior),paid_calls_before_change=0)
        for prior in sorted(root.glob('protocol-preparation-v*.json'))]
    value['preparation_schema']=2
    value['entry_quality']='NOT_EVALUATED; TOP20 membership is not permission to trade'
    atomic_json(path,value);return value


def month_keys(protocol):return sorted({s[:7] for s in protocol['sessions']})


def read_scores(conn,protocol,month):
    model=protocol['annual_models'][month[:4]]
    days=[d for d in protocol['sessions'] if d.startswith(month)]
    sql='''SELECT p.prediction_date date,p.symbol,p.proba_extreme score,p.fold_start,
        p.future_return,p.oracle_extreme10,l.model_sha256,l.feature_profile_sha256,
        l.model_available_date,l.target_name,l.target_horizon,l.fold_start lineage_fold
        FROM oracle_extreme_predictions p LEFT JOIN oracle_path_prediction_lineage l
        ON p.prediction_date=l.prediction_date AND p.symbol=l.symbol AND p.batch_id=l.batch_id
        WHERE p.batch_id=:batch AND p.prediction_date BETWEEN :start AND :end'''
    rows=[dict(r) for r in conn.execute(text(sql),dict(batch=model['batch_id'],start=days[0],end=days[-1])).mappings()]
    scores=pd.DataFrame(rows)
    actual=set(pd.to_datetime(scores['date']).dt.strftime('%Y-%m-%d')) if len(scores) else set()
    if actual!=set(days):return None,dict(month=month,status='WAITING_PREDICTIONS',missing_dates=sorted(set(days)-actual))
    scores['date']=pd.to_datetime(scores.date)
    validate_scores(scores,model)
    top=preparation.fixed_top(scores,TOP)
    top['selected']=True
    coverage=dict(month=month,status='SCORES_VERIFIED',rows=len(scores),sessions=len(days),
        symbols=int(scores.symbol.nunique()),daily_observed_counts={str(d.date()):int(n) for d,n in scores.groupby('date').size().items()},
        model=model,terminal_labels_used=False)
    return top,coverage


def validate_scores(scores,model):
    if scores.duplicated(['date','symbol']).any():raise ValueError('Duplicate scores')
    if not set(scores.symbol).issubset(set(model['universe'])):raise ValueError('Symbol outside model universe')
    for column,expected in dict(fold_start=model['fold'],lineage_fold=model['fold'],
            model_sha256=model['model_sha256'],feature_profile_sha256=model['profile_sha256'],
            model_available_date=model['available_date'],target_name='oracle_path_extreme20',target_horizon=20).items():
        values=scores[column].map(str)
        if not values.eq(str(expected)).all():raise ValueError('Unqualified prediction lineage: '+column)
    if not scores.future_return.isna().all() or not scores.oracle_extreme10.isna().all():
        raise ValueError('Terminal labels unexpectedly attached to path scores')
    if not pd.to_datetime(scores.model_available_date).lt(scores.date).all():raise ValueError('Future model')


def prepare_month(root,protocol,month,engine):
    folder=root/'months'/month;folder.mkdir(parents=True,exist_ok=True)
    marker=folder/'prepared.json'
    if marker.exists():
        value=read(marker)
        for name,checksum in value['files'].items():
            if digest(folder/name)!=checksum:raise ValueError('Prepared month changed')
        if value.get('preparation_schema')!=2:
            # Before any paid analysis: remove a helper's dummy admission flag.
            # Preserve the original annotation and manifests for the audit trail.
            import shutil
            archive=folder/'initial-entry-annotation';archive.mkdir(exist_ok=True)
            for name in ('candidates.parquet','availability.json','prepared.json'):
                shutil.copy2(folder/name,archive/name)
            candidates=pd.read_parquet(folder/'candidates.parquet').drop(columns=['selected'],errors='ignore')
            candidates['entry_quality_status']='NOT_EVALUATED';candidates.to_parquet(folder/'candidates.parquet',index=False)
            panel=read(folder/'availability.json')
            for item in panel:
                item['selected_j_history']=None;item['entry_quality_status']='NOT_EVALUATED'
            atomic_json(folder/'availability.json',panel)
            value['preparation_schema']=2
            value['files']={name:digest(folder/name) for name in value['files']}
            atomic_json(marker,value)
        return value
    from scripts.research.us_news_materiality_feasibility import META_FIELDS,STAMPS
    with engine.connect().execution_options(isolation_level='REPEATABLE READ') as conn:
        # Transaction-local: never return a session-wide read-only connection
        # into the pool later used to persist the authorized analysis cache.
        conn.execute(text('SET TRANSACTION READ ONLY'))
        conn.execute(text("SET SESSION time_zone='+00:00'"))
        conn.execute(text('SET SESSION MAX_EXECUTION_TIME=15000'))
        top,coverage=read_scores(conn,protocol,month)
        if top is None:return coverage
        closes={pd.Timestamp(d):pd.Timestamp(v) for d,v in protocol['closes'].items() if d.startswith(month)}
        query=text(META_FIELDS+''' FROM news_raw n FORCE INDEX (idx_news_raw_source_published)
            STRAIGHT_JOIN news_ticker_map m ON m.article_id=n.article_id
            WHERE n.ingestion_source IN ('eodhd','alpaca')
            AND n.published_at_utc>=:start AND n.published_at_utc<:end
            AND m.symbol IN :symbols LIMIT 20001''').bindparams(bindparam('symbols',expanding=True))
        first=min(closes.values())-pd.Timedelta(hours=24);last=max(closes.values())
        bounds=list(pd.date_range(first,last,freq='3D'))
        if bounds[-1]!=last:bounds.append(last)
        columns=['article_id','symbol','ingestion_source','source','published_at_utc','created_at','updated_at',
            'map_created_at','map_updated_at','is_primary_ticker','headline','content_chars','content_sha256',
            'provider_publication','payload_json_type','url','dedupe_hash']
        rows=[]
        for start,end in zip(bounds[:-1],bounds[1:]):
            subset=top[top.date.map(closes).gt(start) & top.date.map(closes).le(end+pd.Timedelta(hours=24))]
            symbols=sorted(subset.symbol.unique())
            part=[dict(r) for r in conn.execute(query,dict(start=start.tz_localize(None).to_pydatetime(),
                end=end.tz_localize(None).to_pydatetime(),symbols=symbols)).mappings()] if symbols else []
            if len(part)>20000:raise ValueError('News metadata truncated; refuse to interpret missing rows')
            rows.extend(part)
        news=pd.DataFrame(rows,columns=columns)
        for field in STAMPS:news[field]=pd.to_datetime(news[field],utc=True,errors='coerce')
        if news.duplicated(['article_id','symbol']).any():raise ValueError('Duplicate news association')
        panel=preparation.panel_rows(top,news,closes)
        for item in panel:
            item['selected_j_history']=None;item['entry_quality_status']='NOT_EVALUATED'
        ids=sorted({a for item in panel for a in item['accepted_article_ids']})
        identity={r['symbol']:dict(r) for r in conn.execute(text(
            'SELECT symbol,company_name,exchange FROM stock_metadata WHERE symbol IN :symbols').bindparams(
                bindparam('symbols',expanding=True)),dict(symbols=sorted(top.symbol.unique()))).mappings()}
        metadata=news.drop_duplicates('article_id').set_index('article_id');bodies={}
        for i in range(0,len(ids),100):
            part=[dict(r) for r in conn.execute(text('''SELECT article_id,headline,summary,LEFT(content,12000) body,
                SHA2(content,256) body_sha256 FROM news_raw WHERE article_id IN :ids''').bindparams(
                    bindparam('ids',expanding=True)),dict(ids=ids[i:i+100])).mappings()]
            if len(part)!=len(ids[i:i+100]):raise ValueError('News disappeared during snapshot')
            for item in part:
                if item['body_sha256']!=metadata.loc[item['article_id'],'content_sha256']:raise ValueError('Text version changed')
                bodies[item['article_id']]=item
    packets=[preparation.packet_for(item,metadata,bodies,identity.get(item['symbol'])) for item in panel]
    for packet in packets:packet['batch_id']=protocol['annual_models'][month[:4]]['batch_id']
    news.to_parquet(folder/'news-metadata.parquet',index=False)
    candidates=top.drop(columns=['selected'])
    candidates['entry_quality_status']='NOT_EVALUATED';candidates.to_parquet(folder/'candidates.parquet',index=False)
    atomic_json(folder/'packets.json',packets);atomic_json(folder/'availability.json',panel)
    value=dict(coverage,preparation_schema=2,with_news=sum(bool(p['articles']) for p in packets),candidate_days=len(packets),
        article_mappings=sum(len(p['articles']) for p in packets),unique_articles=len(ids),
        strict_historical_pit_mappings=sum(p['conservative_guarded_pairs'] for p in panel),
        files={name:digest(folder/name) for name in ['candidates.parquet','packets.json','availability.json','news-metadata.parquet']})
    atomic_json(marker,value);LOG.info('Prepared %s: %d candidates, %d with news',month,len(packets),value['with_news'])
    return value


class BudgetStop(RuntimeError):pass


class Budget:
    """Durable worst-case reservations; in-flight/unknown spend is never zeroed."""
    def __init__(self,path,cap=CAP):
        self.path=Path(path);self.lock=Lock();self.cap=Decimal(str(cap))
        if self.cap>CAP or self.cap<=0:raise ValueError('Budget must be positive and at most USD 8')
        self.state=read(path) if self.path.exists() else dict(cap_usd=str(self.cap),entries={})
        if Decimal(self.state['cap_usd'])!=self.cap:raise ValueError('Do not reset or expand an existing campaign budget')
        self.save()

    def save(self):atomic_json(self.path,self.state)
    def committed(self):return sum((Decimal(r['charge_usd']) for r in self.state['entries'].values()),Decimal(0))
    def reserve(self,key,request):
        with self.lock:
            if key in self.state['entries']:raise UnresolvedAttempt('Existing budget entry; no second paid attempt')
            upper=worst_call_cost(request)
            if self.committed()+upper>self.cap:raise BudgetStop('USD budget ceiling reached before next API call')
            self.state['entries'][key]=dict(status='RESERVED',charge_usd=str(upper),upper_usd=str(upper),created_at_utc=utc())
            self.save()
    def started(self,key):
        with self.lock:
            self.state['entries'][key]['status']='STARTED';self.save()
    def finish(self,key,response):
        usage=usage_with_cache(response);cost=Decimal(str(usage['gross_cost_estimate_usd']))
        with self.lock:
            item=self.state['entries'][key]
            if cost>Decimal(item['upper_usd']):raise ValueError('Usage exceeds reserved worst-case cost')
            item.update(status='COMPLETE',charge_usd=str(cost),usage=usage,response_sha256=sha(response));self.save()
    def hit(self,key):
        with self.lock:
            self.state['entries'][key].update(status='CACHE_HIT',charge_usd='0');self.save()
    def summary(self):
        with self.lock:
            entries=list(self.state['entries'].values())
            return dict(max_budget_usd=float(self.cap),committed_including_inflight_usd=float(self.committed()),
                paid_calls=sum(e['status']=='COMPLETE' for e in entries),
                cost_usd=sum(float(e['charge_usd']) for e in entries if e['status']=='COMPLETE'),
                unresolved=sum(e['status'] in ('RESERVED','STARTED') for e in entries))


def unknown(packet,reason):
    return dict(decision_date=packet['decision_date'],symbol=packet['symbol'],oracle_rank=packet['oracle_rank'],
        batch_id=packet['batch_id'],decision=reason,confidence=None,veto_long=False,cache_key=None)


def assess(packet,cache,budget,consumer,spool,stop,transport):
    if not packet['articles']:return unknown(packet,'UNKNOWN_NO_QUALIFIED_TEXT')
    if not packet['issuer_reference'].get('company_name'):return unknown(packet,'UNKNOWN_ISSUER')
    request=paid_payload(packet,MODEL)
    if len(json.dumps(request,ensure_ascii=False).encode())>240000:return unknown(packet,'UNKNOWN_OVERSIZE')
    key,*_=request_identity(request,SCOPE)
    try:result=cache.execute(request,scope=SCOPE,consumer=consumer,qualifier=parse)
    except CacheMiss:
        if stop.is_set():raise BudgetStop('Another worker stopped paid dispatch')
        budget.reserve(key,request)
        def once(payload):
            budget.started(key)
            return transport(payload)
        try:
            result=cache.execute(request,scope=SCOPE,consumer=consumer,qualifier=parse,transport=once,
                allow_paid=True,journal_root=spool)
            if result['api_calls']:budget.finish(key,result['response'])
            else:budget.hit(key)
        except Exception:
            stop.set();raise
    value=unknown(packet,'UNKNOWN')
    value.update(result['assessment'],cache_key=result['cache_key'],technical_status=result['status'],
        cache_hit=result['cache_hit'],available_at_utc=str(result['available_at']),
        raw_response_sha256=sha(result['response']),research_only=True)
    return value


def reconcile(cache,budget,spool,consumer):
    for key,entry in list(budget.state['entries'].items()):
        if entry['status'] not in ('STARTED','RESERVED'):continue
        row=cache.get(key);folder=spool/key
        response=json.loads(row['response_json']) if row and row['response_json'] else None
        if response is None and (folder/'response.json').exists():response=read(folder/'response.json')
        if response is None:raise UnresolvedAttempt('Prior ambiguous attempt; manual investigation required, no API retry')
        request=json.loads(row['request_json']) if row else read(folder/'request.json')
        cache.import_response(request,response,scope=SCOPE,consumer=consumer,
            provenance={'recovery':'durable response only; no API'},qualifier=parse)
        budget.finish(key,response)


def analyze_month(root,protocol,month,engine,budget,workers):
    folder=root/'months'/month;packets=read(folder/'packets.json');cache=NewsCache(engine)
    consumer='us-news-top20-history-20261015-v1:'+month
    spool=root/'api';spool.mkdir(exist_ok=True);stop=Event();thread=local()
    reconcile(cache,budget,spool,consumer)
    cache.save_import(consumer+':prepared',dict(protocol=protocol,prepared=read(folder/'prepared.json'),
        packets=packets,availability=read(folder/'availability.json'),qualifier_sha256=digest(Path('service/llm_directional/stored_news.py'))))
    def transport(payload):
        if not hasattr(thread,'client'):
            from service.llm_directional.openai_client import ResponsesClient
            config=SimpleNamespace(provider='openai',api_key_env='OPENAI_API_KEY',deepseek_api_key_env='DEEPSEEK_API_KEY',timeout_seconds=90)
            thread.client=ResponsesClient(config)
        return thread.client(payload)
    outcomes={};errors=[]
    results=folder/'assessments';results.mkdir(exist_ok=True)
    def job(packet):return assess(packet,cache,budget,consumer,spool,stop,transport)
    iterator=iter(enumerate(packets));pending={}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        def fill():
            while len(pending)<workers and not stop.is_set():
                try:index,packet=next(iterator)
                except StopIteration:return
                path=results/f'{index:04d}.json'
                if path.exists():
                    value=read(path)
                    if any(value[k]!=packet[k] for k in ('decision_date','symbol','oracle_rank','batch_id')):raise ValueError('Result membership changed')
                    if value.get('cache_key'):
                        restored=cache.qualify(value['cache_key'],parse)
                        if sha(restored['response'])!=value['raw_response_sha256']:raise ValueError('SQL result changed')
                    outcomes[index]=value;continue
                pending[pool.submit(job,packet)]=(index,path)
        fill()
        while pending:
            finished,_=wait(pending,return_when=FIRST_COMPLETED)
            for future in finished:
                index,path=pending.pop(future)
                try:
                    outcomes[index]=future.result();atomic_json(path,outcomes[index])
                except Exception as exc:
                    errors.append(dict(packet=index,error_type=type(exc).__name__,error=str(exc)[:200]));stop.set()
            state=dict(status='GPT_RUNNING' if not errors else 'STOPPING',month=month,
                completed_month_candidates=len(outcomes),total_month_candidates=len(packets),errors=errors,**budget.summary())
            atomic_json(root/'progress.json',state)
            if len(outcomes)%20<workers:LOG.info('GPT %s %d/%d cost=$%.5f',month,len(outcomes),len(packets),state['cost_usd'])
            fill()
    if errors:
        atomic_json(folder/'errors.json',errors)
        raise RuntimeError('Paid campaign stopped safely: '+errors[0]['error_type'])
    if len(outcomes)!=len(packets):raise ValueError('Incomplete result set')
    ordered=[outcomes[i] for i in range(len(packets))]
    # No-text / invalid outcomes also belong in SQL, not only the paid answers.
    snapshot=dict(protocol_sha256=sha(protocol),month=month,assessments=ordered,
        prepared_import_id=sha(consumer+':prepared'),research_only=True)
    import_id=cache.save_import(consumer+':completed',snapshot)
    result=dict(month=month,candidate_days=len(ordered),decisions=dict(Counter(v['decision'] for v in ordered)),
        sql_completed_import_id=import_id,sql_prepared_import_id=sha(consumer+':prepared'),
        no_price_outcomes_loaded=True,files={str(p.relative_to(folder)):digest(p) for p in sorted(results.glob('*.json'))})
    atomic_json(folder/'completed.json',result);return result


def run(root,phase,workers):
    from database.connection import get_sqlalchemy_engine
    root.mkdir(parents=True,exist_ok=True)
    protocol=freeze(root);engine=get_sqlalchemy_engine()
    if engine.url.database!='alpha_trade':raise ValueError('US alpha_trade required')
    months=[];missing=[]
    budget=Budget(root/'budget.json') if phase=='analyze' else None
    try:
        for month in month_keys(protocol):
            prepared=prepare_month(root,protocol,month,engine);months.append(prepared)
            if prepared['status']=='WAITING_PREDICTIONS':missing.append(prepared);continue
            if phase=='analyze':
                analyze_month(root,protocol,month,engine,budget,workers)
            else:atomic_json(root/'progress.json',dict(status='PREPARING',month=month,completed_months=len(months),paid_api_calls=0))
        done=[read(root/'months'/m/'completed.json') for m in month_keys(protocol) if (root/'months'/m/'completed.json').exists()]
        result=dict(status=('WAITING_PREDICTIONS' if missing else 'COMPLETED' if phase=='analyze' else 'PREPARED'),
            start=START,end=END,top=TOP,sessions=len(protocol['sessions']),
            prepared_months=len(months)-len(missing),total_months=len(months),completed_months=len(done),missing=missing,
            candidate_days=sum(m.get('candidate_days',0) for m in months),with_news=sum(m.get('with_news',0) for m in months),
            monthly_results=done,research_only=True,historical_pit_certified=False)
        if budget:result.update(budget.summary())
        atomic_json(root/'report.json',result);atomic_json(root/'progress.json',result);return result
    except Exception as exc:
        state=dict(status='STOPPED',error_type=type(exc).__name__,error=str(exc)[:300],automatic_retry=False)
        if budget:state.update(budget.summary())
        atomic_json(root/'progress.json',state);raise
    finally:engine.dispose()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--phase',choices=['prepare','analyze'],default='prepare')
    parser.add_argument('--workers',type=int,choices=range(1,5),default=4)
    parser.add_argument('--budget-usd',type=Decimal,default=CAP)
    args=parser.parse_args()
    if args.budget_usd!=CAP:parser.error('This authorization is capped at exactly USD 8; no override')
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    with exclusive_run(args.output):print(json.dumps(run(args.output,args.phase,args.workers),default=str))


if __name__=='__main__':main()
