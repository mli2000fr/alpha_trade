"""Daily US EODHD ingestion: bounded HTTP, atomic news archive, no scoring/LLM.

Own checkpoint namespace and scheduled Paris cycles, never moves weekly watermarks.
Incomplete symbols restart at offset zero; archived versions deduplicate.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import logging
from pathlib import Path
import time
from urllib.parse import urlsplit
from uuid import uuid4
from zoneinfo import ZoneInfo

import requests
from sqlalchemy import inspect, text

from common.config_loader import load_batch_config
from common.universe_files import load_universe_file_symbols
from event_sentiment.config import EventSentimentConfig
from event_sentiment.db_io import EventSentimentRepository
from event_sentiment.ingestion import NewsIngestionService
from service._http_retry import _redact_sensitive_text, RetryPolicy, CircuitBreaker, CircuitOpenError
from service.eodhd import news_client
from service.eodhd.quota import get_default_tracker, EodhdCircuitOpen, EodhdQuotaExceeded
from service.forward_pit.outcomes import Outcome, BatchRunError
from service.market.intraday_backfill import atomic_json, run_lock

ROOT=Path(__file__).resolve().parents[2]
BATCH='eodhd_news_ingestion_sync'
SOURCE='eodhd_news_daily'
LOG=logging.getLogger(__name__)
PARIS=ZoneInfo('Europe/Paris')


class GlobalCollectionStop(RuntimeError):
    pass


class SymbolAttemptLimit(RuntimeError):
    pass


class CollectionDeferred(GlobalCollectionStop):
    """Global refusal before HTTP: do not falsely fail unqueried symbols."""


def collection_cycle(end,cfg):
    """Latest scheduled Paris slot: a midnight smoke must not suppress tonight."""
    local=end.astimezone(PARIS)
    slot=local.replace(hour=int(cfg.get('run_hours',20)),minute=int(cfg.get('run_minutes',30)),
        second=0,microsecond=0)
    if local<slot:
        slot-=timedelta(days=1)
    return slot


class HttpBudget:
    """Counts actual attempts including retries, before network; redirects forbidden."""
    def __init__(self,cfg,root,*,tracker=None,clock=time.monotonic,sleep=time.sleep,now=None):
        self.cfg,self.root=cfg,root
        self.tracker=tracker or get_default_tracker()
        self.clock,self.sleep=clock,sleep
        self.now=now or (lambda:datetime.now(timezone.utc))
        self.started=clock()
        self.last_request=None
        self.attempts=self.symbol_attempts=0
        self.new_symbol()

    def new_symbol(self):
        self.symbol_attempts=0
        # One slow symbol must not exhaust the shared host breaker for all others.
        # Retries remain bounded; repeated incomplete symbols stop the whole run.
        self.breaker=CircuitBreaker(failure_threshold=self.cfg['http_max_attempts']+1)

    def check_cooldown(self):
        path=self.root/'cooldown.json'
        if path.exists():
            state=json.loads(path.read_text(encoding='utf-8'))
            until=datetime.fromisoformat(state['retry_after_utc'])
            if until.tzinfo is None:
                raise GlobalCollectionStop('Invalid news cooldown timestamp')
            if self.now()<until:
                raise CollectionDeferred('News cooldown until '+until.isoformat()+'; no HTTP attempted')

    def pause_after_failures(self,until=None):
        until=until or self.now()+timedelta(seconds=self.cfg['failure_cooldown_seconds'])
        atomic_json(self.root/'cooldown.json',{'retry_after_utc':until.isoformat(),
            'reason':'consecutive_incomplete_symbols'})
        return until.isoformat()

    def proxy(self,session):
        budget=self
        class Proxy:
            def request(self,method,url,**kwargs):
                budget.check_cooldown()
                parsed=urlsplit(url)
                if method.upper()!='GET' or parsed.scheme!='https' or parsed.hostname!='eodhd.com' or parsed.path!='/api/news':
                    raise GlobalCollectionStop('Only official EODHD news GET allowed')
                if kwargs.get('verify') is False:
                    raise GlobalCollectionStop('Disabling TLS verification is forbidden')
                if budget.last_request is not None:
                    pause=float(budget.cfg['request_interval_seconds'])
                    budget.sleep(max(0,pause-(budget.clock()-budget.last_request)))
                if budget.clock()-budget.started>=60*float(budget.cfg['max_duration_minutes']):
                    raise CollectionDeferred('News duration limit reached; remaining symbols pending')
                if budget.attempts>=budget.cfg['max_http_attempts_per_run']:
                    raise CollectionDeferred('News HTTP run budget exhausted')
                if budget.symbol_attempts>=budget.cfg['max_http_attempts_per_symbol']:
                    raise SymbolAttemptLimit('News symbol HTTP budget exhausted; symbol incomplete')
                day=budget.now().astimezone(timezone.utc).date().isoformat()
                path=budget.root/('attempts-'+day+'.json')
                state=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'attempts':0}
                used=state['attempts']
                if type(used) is not int or used<0:
                    raise GlobalCollectionStop('Invalid news daily budget state')
                if used>=budget.cfg['max_http_attempts_per_day']:
                    raise CollectionDeferred('News daily HTTP budget exhausted')
                try:
                    budget.tracker.reserve('news')
                except (EodhdCircuitOpen,EodhdQuotaExceeded) as exc:
                    if isinstance(exc,EodhdCircuitOpen):
                        until=datetime.fromtimestamp(budget.tracker.state.circuit_open_until_epoch,timezone.utc)
                        budget.pause_after_failures(until)
                    raise CollectionDeferred(_redact_sensitive_text(str(exc))) from None
                atomic_json(path,{'attempts':used+1,'cost_units_reserved':5*(used+1)})
                budget.attempts+=1; budget.symbol_attempts+=1
                budget.last_request=budget.clock()
                kwargs['allow_redirects']=False
                try:
                    response=session.request(method,url,**kwargs)
                except Exception as exc:
                    # Still charge every actual attempt conservatively. A retry
                    # timeout is not evidence of failures on five distinct titles.
                    budget.tracker.record_failure('news',feature=BATCH,count_call=True,
                        count_towards_circuit=not isinstance(exc,(requests.exceptions.Timeout,
                            requests.exceptions.ConnectionError)))
                    if isinstance(exc,requests.exceptions.SSLError):
                        raise GlobalCollectionStop('TLS certificate verification failed; stopped') from None
                    raise
                if response.status_code>=400:
                    budget.tracker.record_failure('news',feature=BATCH,count_call=True)
                else:
                    budget.tracker.record_success('news',feature=BATCH)
                if response.status_code in (401,403,429) or 300<=response.status_code<400:
                    response.close()
                    raise GlobalCollectionStop(f'News HTTP {response.status_code}; stopped')
                return response
        return Proxy()


class CountingRepository(EventSentimentRepository):
    def __init__(self,engine,outcome):
        super().__init__()
        self.engine=engine
        self.outcome=outcome

    def persist_news_page(self,*args,**kwargs):
        stats=super().persist_news_page(*args,**kwargs)
        # Update immediately after sealed durable archive commit, even if a
        # later page of this symbol fails. Submitted upserts aren't new versions.
        self.outcome.persisted+=stats['raw_versions']
        for key in ('landed','ticker_maps','raw_versions','map_versions','observations'):
            self.outcome.details['archive'][key]+=stats[key]
        return stats


def settings(cfg):
    defaults=dict(lookback_days=7,page_limit=100,request_interval_seconds=.25,
        max_http_attempts_per_run=4000,max_http_attempts_per_day=4000,
        max_http_attempts_per_symbol=25,max_duration_minutes=120,max_consecutive_failures=3,
        http_timeout_seconds=30,http_max_attempts=3,failure_cooldown_seconds=1800)
    values={key:cfg.get(key,value) for key,value in defaults.items()}
    for key in ('lookback_days','page_limit','max_http_attempts_per_run','max_http_attempts_per_day',
                'max_http_attempts_per_symbol','max_consecutive_failures','http_max_attempts','failure_cooldown_seconds'):
        if type(values[key]) is not int or values[key]<1:
            raise ValueError('Invalid positive integer setting: '+key)
    if not values['lookback_days']<=31 or not values['page_limit']<=1000:
        raise ValueError('News window/page bounds exceeded')
    if not .1<=float(values['request_interval_seconds'])<=10 or not 1<=float(values['max_duration_minutes'])<=120:
        raise ValueError('News rate/duration bounds exceeded')
    if not 5<=float(values['http_timeout_seconds'])<=60 or not 1<=values['http_max_attempts']<=5:
        raise ValueError('News HTTP timeout/retry bounds exceeded')
    if not 60<=values['failure_cooldown_seconds']<=7200:
        raise ValueError('News cooldown bounds exceeded')
    return values


def collect(engine,cfg,run_id,dry_run=False,*,now=None,repository=None,budget_factory=HttpBudget,
            service_factory=NewsIngestionService):
    if engine.url.database!='alpha_trade' or cfg.get('market_code')!='US_EQ' or cfg.get('provider')!='eodhd':
        raise ValueError('Daily news requires EODHD / US_EQ / alpha_trade')
    policy=settings(cfg)
    end=now or datetime.now(timezone.utc)
    if end.tzinfo is None:
        raise ValueError('Aware collection time required')
    cycle=collection_cycle(end,cfg)
    symbols=load_universe_file_symbols('universe-file:'+str(cfg['symbols_file']))
    selected=cfg.get('selected_symbols')
    if selected is not None:
        if not isinstance(selected,list) or not selected or not set(selected)<=set(symbols):
            raise ValueError('Smoke symbols must belong to the configured universe')
        symbols=sorted(set(selected))
    if not symbols:
        raise ValueError('Empty news universe')
    root=ROOT/'artifacts/operations'/BATCH
    outcome=Outcome(requested=len(symbols),details=dict(provider='eodhd',market_code='US_EQ',
        checkpoint_source=SOURCE,collection_day=cycle.date().isoformat(),
        collection_cycle_started_at=cycle.isoformat(),status='RUNNING',
        window_start=(end-timedelta(days=policy['lookback_days'])).isoformat(),window_end=end.isoformat(),
        counter_units={'requested':'symbols','received':'article occurrences','persisted':'new raw text/payload versions',
                       'empty':'symbols without kept articles','failed':'incomplete symbols'},
        archive={k:0 for k in ('landed','ticker_maps','raw_versions','map_versions','observations')},
        completed_symbols=0,skipped_completed=0,pending_symbols=len(symbols),http_attempts=0,
        errors=[],training=False,sentiment_scoring=False,llm_calls=0,orders=False,policy=policy))
    if dry_run:
        outcome.details['status']='PREPARED_DRY_RUN'
        return outcome
    with engine.connect() as conn:
        if conn.execute(text('SELECT DATABASE()')).scalar_one()!='alpha_trade':
            raise ValueError('Actual US schema alpha_trade required')
        needed={'news_raw','news_ticker_map','news_raw_versions','news_ticker_map_versions',
            'news_archive_observations','news_ingestion_checkpoint'}
        if not needed<=set(inspect(conn).get_table_names()):
            raise ValueError('News/archive schema required; no automatic DDL')
    root.mkdir(parents=True,exist_ok=True)
    report_dir=root/run_id
    report_dir.mkdir(exist_ok=False)
    def progress():
        atomic_json(report_dir/'progress.json',outcome.__dict__)
    try:
        with run_lock(root):
            repo=repository or CountingRepository(engine,outcome)
            config=EventSentimentConfig.for_provider('eodhd',source_name=SOURCE,page_limit=policy['page_limit'],
                initial_backfill_days=policy['lookback_days'],allow_sector_fallback=False)
            service=service_factory(repo,config)
            budget=budget_factory(policy,root)
            if hasattr(budget,'check_cooldown'):
                budget.check_cooldown()
            def pages(**kwargs):
                retry=RetryPolicy(max_attempts=policy['http_max_attempts'],
                    timeout_seconds=policy['http_timeout_seconds'],base_delay_seconds=1,max_delay_seconds=30)
                extra={'breaker':budget.breaker} if hasattr(budget,'breaker') else {}
                for articles,token in news_client.iter_news_pages(**{**kwargs,
                        'session':budget.proxy(kwargs['session']),'retry_policy':retry,**extra}):
                    outcome.received+=len(articles)
                    yield articles,token
            service._iter_news_pages=pages
            consecutive=0
            for symbol in symbols:
                cp=repo.get_checkpoint(SOURCE,symbol)
                last=cp.get('news_ingested_at') if cp else None
                if last is not None:
                    if last.tzinfo is None:
                        last=last.replace(tzinfo=timezone.utc)
                    if cp.get('status')=='success' and last>=cycle:
                        outcome.details['skipped_completed']+=1
                        outcome.details['pending_symbols']-=1
                        progress()
                        continue
                budget.new_symbol()
                attempts_before=budget.attempts
                try:
                    stats=service.run(start_utc=end-timedelta(days=policy['lookback_days']),end_utc=end,
                        symbols=[symbol],resume_checkpoints=False)
                    repo.touch_checkpoint_stage(SOURCE,[symbol],stage='news_ingested')
                    outcome.empty+=int(stats['fetched']==0)
                    outcome.details['completed_symbols']+=1
                    consecutive=0
                except Exception as exc:
                    if isinstance(exc,(CollectionDeferred,EodhdCircuitOpen,EodhdQuotaExceeded,CircuitOpenError)):
                        # If this title already had HTTP attempts, it is incomplete;
                        # otherwise it and all following titles remain pending.
                        outcome.details['stop_reason']=_redact_sensitive_text(str(exc))[:500]
                        if budget.attempts>attempts_before:
                            outcome.failed+=1
                            outcome.details['errors'].append(dict(symbol=symbol,error_type=type(exc).__name__,
                                message=outcome.details['stop_reason']))
                        raise BatchRunError('Daily news deferred: '+outcome.details['stop_reason'],outcome) from None
                    consecutive+=1; outcome.failed+=1
                    outcome.details['errors'].append(dict(symbol=symbol,error_type=type(exc).__name__,
                        message=_redact_sensitive_text(str(exc))[:500]))
                    if consecutive>=policy['max_consecutive_failures'] and not isinstance(exc,GlobalCollectionStop):
                        outcome.details['retry_after_utc']=budget.pause_after_failures()
                    if isinstance(exc,GlobalCollectionStop) or consecutive>=policy['max_consecutive_failures']:
                        raise BatchRunError('Daily news interrupted: '+_redact_sensitive_text(str(exc))[:500],outcome) from None
                finally:
                    outcome.details['http_attempts']=budget.attempts
                    outcome.details['pending_symbols']=len(symbols)-outcome.details['completed_symbols']-outcome.details['skipped_completed']-outcome.failed
                    progress()
                LOG.info('Daily news completed=%d skipped=%d failed=%d pending=%d articles=%d new_versions=%d',
                    outcome.details['completed_symbols'],outcome.details['skipped_completed'],outcome.failed,
                    outcome.details['pending_symbols'],outcome.received,outcome.persisted)
            if outcome.failed:
                raise BatchRunError(f'Daily news: {outcome.failed} incomplete symbols',outcome)
            outcome.details['status']='COMPLETED'
    except BatchRunError:
        outcome.details['status']='FAILED'
        raise
    except CollectionDeferred as exc:
        outcome.details['status']='FAILED'
        outcome.details['stop_reason']=_redact_sensitive_text(str(exc))[:500]
        raise BatchRunError('Daily news deferred: '+outcome.details['stop_reason'],outcome) from None
    except Exception as exc:
        outcome.details['status']='FAILED'
        outcome.failed=max(1,outcome.failed)
        raise BatchRunError('Daily news technical failure: '+_redact_sensitive_text(str(exc))[:500],outcome) from None
    finally:
        progress()
        atomic_json(report_dir/'report.json',outcome.__dict__)
    return outcome


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--smoke',action='store_true',required=True)
    parser.add_argument('--symbols',required=True)
    args=parser.parse_args()
    selected=sorted(set(args.symbols.split(',')))
    if not 1<=len(selected)<=3:
        parser.error('Smoke: at most three explicit universe symbols')
    from database.connection import get_sqlalchemy_engine
    cfg=dict(load_batch_config()[BATCH],selected_symbols=selected,max_http_attempts_per_run=12,
        max_http_attempts_per_symbol=4,max_duration_minutes=5)
    run_id='smoke-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid4().hex[:8]
    try:
        result=collect(get_sqlalchemy_engine(),cfg,run_id)
        print(json.dumps({'status':'COMPLETED_SMOKE_NOT_FULL_BATCH','run_id':run_id,**result.__dict__},default=str))
    except BatchRunError as exc:
        print(json.dumps({'status':'FAILED','run_id':run_id,'error':str(exc),**exc.outcome.__dict__},default=str))
        raise SystemExit(1)
