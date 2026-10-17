"""No live HTTP or MySQL: bounded transport, checkpoints and preserved counters."""
from datetime import datetime, timezone
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests
import yaml

from service.eodhd import news_ingestion_daily as daily
from service.forward_pit.outcomes import Outcome, BatchRunError

NOW=datetime(2026,10,16,19,tzinfo=timezone.utc)


class Tracker:
    def __init__(self): self.success=self.failure=self.reserved=0
    def reserve(self,*a,**k): self.reserved+=1
    def record_success(self,*a,**k): self.success+=1
    def record_failure(self,*a,**k): self.failure+=1


class Session:
    def __init__(self,status=200,error=None): self.status,self.error=status,error; self.calls=0
    def request(self,*a,**k):
        self.calls+=1
        assert k['allow_redirects'] is False
        if self.error: raise self.error
        return SimpleNamespace(status_code=self.status,close=lambda:None)


def budget(tmp_path,**changes):
    cfg=daily.settings({**dict(max_http_attempts_per_run=2,max_http_attempts_per_day=3,
        max_http_attempts_per_symbol=2),**changes})
    return daily.HttpBudget(cfg,tmp_path,tracker=Tracker(),sleep=lambda _:None,now=lambda:NOW)


def request(b,session=None,**kw):
    return b.proxy(session or Session()).request('GET','https://eodhd.com/api/news',**kw)


def test_budget_reserved_before_attempt_and_persisted_across_runs(tmp_path):
    b=budget(tmp_path)
    assert request(b).status_code==200
    assert request(b).status_code==200
    with pytest.raises(daily.GlobalCollectionStop): request(b)
    other=budget(tmp_path)
    request(other)
    with pytest.raises(daily.GlobalCollectionStop): request(other)
    assert json.loads((tmp_path/'attempts-2026-10-16.json').read_text())['attempts']==3


def test_failed_attempts_and_retries_cost_budget_too(tmp_path):
    b=budget(tmp_path)
    for _ in range(2):
        with pytest.raises(requests.exceptions.Timeout):
            request(b,Session(error=requests.exceptions.Timeout()))
    assert b.attempts==2 and b.tracker.failure==2
    with pytest.raises(daily.GlobalCollectionStop): request(b)


@pytest.mark.parametrize('status',[301,302,401,403,429])
def test_access_and_redirect_failures_abort_immediately(tmp_path,status):
    b=budget(tmp_path)
    with pytest.raises(daily.GlobalCollectionStop): request(b,Session(status=status))
    assert b.attempts==1


def test_ssl_failure_is_global_no_bypass(tmp_path):
    b=budget(tmp_path)
    with pytest.raises(daily.GlobalCollectionStop,match='TLS'):
        request(b,Session(error=requests.exceptions.SSLError()))
    assert b.attempts==1
    with pytest.raises(daily.GlobalCollectionStop,match='forbidden'):
        request(b,verify=False)
    assert b.attempts==1


def test_duration_and_symbol_limit_no_network(tmp_path):
    b=budget(tmp_path,max_http_attempts_per_run=4,max_http_attempts_per_symbol=1)
    request(b)
    with pytest.raises(daily.SymbolAttemptLimit): request(b)
    b.new_symbol(); request(b)
    b.clock=lambda:b.started+7201
    with pytest.raises(daily.GlobalCollectionStop,match='duration'): request(b)


def test_cycle_keeps_midnight_catchup_separate_from_next_evening():
    midnight=datetime(2026,10,16,0,30,tzinfo=daily.PARIS)
    evening=datetime(2026,10,16,20,30,tzinfo=daily.PARIS)
    assert daily.collection_cycle(midnight,{}).isoformat()=='2026-10-15T20:30:00+02:00'
    assert daily.collection_cycle(evening,{}).isoformat()=='2026-10-16T20:30:00+02:00'


def test_cycle_dst_uses_paris_not_fixed_utc_offset():
    assert daily.collection_cycle(datetime(2026,10,25,20,30,tzinfo=daily.PARIS),{}).utcoffset()==daily.timedelta(hours=1)
    assert daily.collection_cycle(datetime(2026,10,24,20,30,tzinfo=daily.PARIS),{}).utcoffset()==daily.timedelta(hours=2)


def test_other_endpoint_host_method_denied(tmp_path):
    b=budget(tmp_path)
    for method,url in [('POST','https://eodhd.com/api/news'),('GET','https://other.test/api/news'),
                       ('GET','https://eodhd.com/api/fundamentals/AAPL.US')]:
        with pytest.raises(daily.GlobalCollectionStop): b.proxy(Session()).request(method,url)
    assert b.attempts==0


def test_real_tls_factory_checks_cert_and_hostname_and_rejects_false():
    import ssl
    from common.verified_http import VerifiedTLSAdapter
    from event_sentiment.ingestion import verified_session
    with verified_session() as session:
        adapter=session.get_adapter('https://eodhd.com/api/news')
        assert isinstance(adapter,VerifiedTLSAdapter)
        assert adapter.context.verify_mode==ssl.CERT_REQUIRED and adapter.context.check_hostname
        req=requests.Request('GET','https://eodhd.com/api/news').prepare()
        _,pool=adapter.build_connection_pool_key_attributes(req,True)
        assert pool['ssl_context'] is adapter.context
        with pytest.raises(ValueError): adapter.build_connection_pool_key_attributes(req,False)


class Conn:
    def __enter__(self): return self
    def __exit__(self,*a): pass
    def execute(self,stmt):
        assert str(stmt)=='SELECT DATABASE()'
        return SimpleNamespace(scalar_one=lambda:'alpha_trade')


class Engine:
    url=SimpleNamespace(database='alpha_trade')
    def connect(self): return Conn()


class Repo:
    def __init__(self): self.checkpoints={}; self.marked=[]
    def get_checkpoint(self,source,symbol):
        assert source==daily.SOURCE
        return self.checkpoints.get(symbol)
    def touch_checkpoint_stage(self,source,symbols,stage):
        assert source==daily.SOURCE and stage=='news_ingested'
        self.marked+=symbols
        self.checkpoints[symbols[0]]=dict(status='success',news_ingested_at=NOW)


class Budget:
    attempts=0
    def __init__(self,*a): pass
    def new_symbol(self): pass
    def proxy(self,session): return session
    def pause_after_failures(self): return '2026-10-16T19:30:00+00:00'


class Service:
    failures={}
    def __init__(self,repo,config): self.repo,self.config=repo,config
    def run(self,**kw):
        assert kw['resume_checkpoints'] is False
        assert kw['start_utc']==NOW-daily.timedelta(days=7)
        symbol=kw['symbols'][0]
        fetched=0
        for rows,_ in self._iter_news_pages(**kw,session=object()): fetched+=len(rows)
        if symbol in self.failures: raise self.failures[symbol]
        return {'fetched':fetched}


@pytest.fixture
def setup(monkeypatch,tmp_path):
    monkeypatch.setattr(daily,'ROOT',tmp_path)
    monkeypatch.setattr(daily,'load_universe_file_symbols',lambda _:['AAA','BBB','CCC'])
    monkeypatch.setattr(daily,'inspect',lambda _:SimpleNamespace(get_table_names=lambda:[
        'news_raw','news_ticker_map','news_raw_versions','news_ticker_map_versions',
        'news_archive_observations','news_ingestion_checkpoint']))
    monkeypatch.setattr(daily.news_client,'iter_news_pages',lambda **kw:iter([([{'id':kw['symbols'][0]}],None)]))
    Service.failures={}
    return dict(market_code='US_EQ',provider='eodhd',symbols_file='fixture.txt')


def collect(cfg,repo,run,**kw):
    return daily.collect(Engine(),cfg,run,now=NOW,repository=repo,budget_factory=Budget,service_factory=Service,**kw)


def test_success_daily_resume_zero_new_requests_not_weekly_checkpoint(setup):
    repo=Repo()
    result=collect(setup,repo,'first')
    assert result.requested==3 and result.received==3 and result.failed==0
    assert repo.marked==['AAA','BBB','CCC']
    resumed=collect(setup,repo,'resume')
    assert resumed.details['skipped_completed']==3 and resumed.received==0
    assert resumed.details['pending_symbols']==0


def test_empty_news_normal_not_warning(setup,monkeypatch):
    monkeypatch.setattr(daily.news_client,'iter_news_pages',lambda **kw:iter([([],None)]))
    result=collect(setup,Repo(),'empty')
    assert result.empty==3 and result.failed==0 and not result.warnings


def test_failure_preserves_partial_received_and_pending(setup):
    Service.failures={'BBB':daily.GlobalCollectionStop('HTTP 403')}
    repo=Repo()
    with pytest.raises(BatchRunError) as err: collect(setup,repo,'failure')
    result=err.value.outcome
    assert result.received==2 and result.failed==1 and result.details['completed_symbols']==1
    assert result.details['pending_symbols']==1 and repo.marked==['AAA']


def test_symbol_failure_isolated_and_run_not_silently_successful(setup):
    Service.failures={'BBB':daily.SymbolAttemptLimit('incomplete')}
    repo=Repo()
    with pytest.raises(BatchRunError) as err: collect(setup,repo,'failure')
    assert repo.marked==['AAA','CCC']
    assert err.value.outcome.details['pending_symbols']==0 and err.value.outcome.failed==1


def test_dry_run_no_files_no_connection(setup,tmp_path):
    engine=SimpleNamespace(url=SimpleNamespace(database='alpha_trade'))
    result=daily.collect(engine,setup,'dry',True,now=NOW)
    assert result.requested==3 and not (tmp_path/'artifacts').exists()


def test_wrong_market_and_symbols_rejected_before_connect(setup):
    for change in ({'market_code':'FR_EQ'},{'provider':'yahoo'},{'selected_symbols':['BAD']}):
        with pytest.raises(ValueError): collect({**setup,**change},Repo(),'invalid')


def test_counters_count_archive_versions_not_upsert_rows(monkeypatch):
    stats=dict(landed=12,ticker_maps=20,raw_versions=2,map_versions=4,observations=6)
    monkeypatch.setattr(daily.EventSentimentRepository,'persist_news_page',lambda *a,**k:stats)
    repo=object.__new__(daily.CountingRepository)
    repo.outcome=Outcome(details={'archive':dict.fromkeys(stats,0)})
    repo.persist_news_page([])
    assert repo.outcome.persisted==2 and repo.outcome.details['archive']==stats


def test_catalog_is_daily_at_night_same_universe_no_changes_to_pipeline_lists():
    cfg=yaml.safe_load(Path('batch.yaml').read_text(encoding='utf-8'))
    application=yaml.safe_load(Path('config.yaml').read_text(encoding='utf-8'))
    section=cfg[daily.BATCH]
    assert section['enabled'] and section['run_hours']=='20' and section['run_minutes']=='30'
    assert section['timezone']=='Europe/Paris' and section['run_days']=='0,1,2,3,4,5,6'
    assert section['symbols_file']==cfg['us_pipeline']['symbols_file']
    assert section['max_duration_minutes']<=120
    # User-controlled daily steps can include 10/11/12; this collector does
    # not impose the historical factory list on the scheduled workflow.
    assert application['us_pipeline']['steps']
    assert all(type(n) is int and 1<=n<=14 for n in application['us_pipeline']['steps'])
    assert application['us_pipeline']['steps_friday']
    assert all(type(n) is int and 1<=n<=14 for n in application['us_pipeline']['steps_friday'])
    from ihm.services.batch_management import load_batch_specs
    spec=next(s for s in load_batch_specs() if s.name==daily.BATCH)
    assert spec.runnable and spec.task_name=='AlphaTrade-EodhdNewsIngestionSync'


def test_retries_on_one_slow_symbol_do_not_open_global_quota_circuit(tmp_path):
    from service.eodhd.quota import EodhdQuotaTracker
    cfg=daily.settings({'max_http_attempts_per_run':20,'max_http_attempts_per_day':20})
    tracker=EodhdQuotaTracker(failure_threshold=5)
    b=daily.HttpBudget(cfg,tmp_path,tracker=tracker,sleep=lambda _:None,now=lambda:NOW)
    for _ in range(5):
        with pytest.raises(requests.exceptions.ReadTimeout):
            request(b,Session(error=requests.exceptions.ReadTimeout()))
    assert not tracker.is_circuit_open()
    assert tracker.state.calls_failed==5 and b.attempts==5
    b.new_symbol()
    assert request(b).status_code==200


def test_global_circuit_stops_before_http_and_pause_survives_new_process(tmp_path):
    from service.eodhd.quota import EodhdQuotaTracker
    tracker=EodhdQuotaTracker(failure_threshold=1)
    tracker.record_failure('news')
    cfg=daily.settings({})
    b=daily.HttpBudget(cfg,tmp_path,tracker=tracker,sleep=lambda _:None)
    session=Session()
    with pytest.raises(daily.CollectionDeferred): request(b,session)
    assert b.attempts==0 and session.calls==0
    fresh=daily.HttpBudget(cfg,tmp_path,tracker=Tracker(),sleep=lambda _:None)
    with pytest.raises(daily.CollectionDeferred,match='cooldown'): request(fresh,session)
    assert fresh.attempts==0 and session.calls==0


def test_cooldown_expires_without_deleting_prior_proof(tmp_path):
    b=budget(tmp_path)
    until=b.pause_after_failures()
    with pytest.raises(daily.CollectionDeferred): request(b)
    b.now=lambda:NOW+daily.timedelta(minutes=31)
    assert request(b).status_code==200
    assert json.loads((tmp_path/'cooldown.json').read_text())['retry_after_utc']==until


def test_startup_pause_keeps_all_symbols_pending_and_archives_final_report(setup,tmp_path):
    root=tmp_path/'artifacts/operations'/daily.BATCH
    root.mkdir(parents=True)
    b=daily.HttpBudget(daily.settings(setup),root,tracker=Tracker(),now=lambda:NOW)
    b.pause_after_failures()
    class PausedBudget(daily.HttpBudget):
        def __init__(self,cfg,folder):
            super().__init__(cfg,folder,tracker=Tracker(),now=lambda:NOW)
    repo=Repo()
    with pytest.raises(BatchRunError) as err:
        daily.collect(Engine(),setup,'paused',now=NOW,repository=repo,
                      budget_factory=PausedBudget,service_factory=Service)
    report=json.loads((root/'paused/report.json').read_text())
    assert err.value.outcome.failed==report['failed']==0
    assert report['details']['pending_symbols']==3 and report['details']['http_attempts']==0
    assert report['details']['status']=='FAILED' and repo.marked==[]


def test_unqueried_symbols_are_pending_not_failed_on_circuit(setup):
    Service.failures={'AAA':daily.CollectionDeferred('circuit open')}
    repo=Repo()
    with pytest.raises(BatchRunError) as err: collect(setup,repo,'deferred')
    result=err.value.outcome
    assert result.failed==0 and result.details['pending_symbols']==3
    assert result.details['errors']==[] and repo.marked==[]
    assert result.details['status']=='FAILED' and 'circuit' in result.details['stop_reason']


def test_three_incomplete_symbols_persist_pause_and_preserve_failure_counts(setup):
    Service.failures={symbol:requests.exceptions.Timeout('timeout') for symbol in ['AAA','BBB','CCC']}
    with pytest.raises(BatchRunError) as err: collect(setup,Repo(),'outage')
    result=err.value.outcome
    assert result.failed==3 and result.details['pending_symbols']==0
    assert result.details['retry_after_utc']=='2026-10-16T19:30:00+00:00'


def test_real_client_retry_path_isolated_and_resumes_remaining_titles(setup,monkeypatch,tmp_path):
    # Use the actual retry loop and quota tracker, not a simulated final error.
    from service.eodhd.quota import EodhdQuotaTracker
    monkeypatch.setattr(daily.news_client,'iter_news_pages',REAL_ITER_NEWS_PAGES)
    monkeypatch.setattr(daily.news_client,'_get_token',lambda:'test-only')
    monkeypatch.setattr(daily.news_client,'_get_base_url',lambda:'https://eodhd.com/api')
    monkeypatch.setattr('service._http_retry.time.sleep',lambda _:None)
    tracker=EodhdQuotaTracker()
    attempts=[]
    class Transport:
        def request(self,method,url,**kwargs):
            symbol=kwargs['params']['s']
            attempts.append((symbol,kwargs['timeout']))
            if symbol=='AAA.US': raise requests.exceptions.ReadTimeout('slow title')
            return SimpleNamespace(status_code=200,json=lambda:[],raise_for_status=lambda:None)
    class RealService(Service):
        def run(self,**kw):
            pages=list(self._iter_news_pages(start_utc=kw['start_utc'],end_utc=kw['end_utc'],
                symbols=kw['symbols'],session=Transport()))
            return {'fetched':sum(len(rows) for rows,_ in pages)}
    class RealBudget(daily.HttpBudget):
        def __init__(self,cfg,root):
            super().__init__(cfg,root,tracker=tracker,sleep=lambda _:None,now=lambda:NOW)
    repo=Repo()
    with pytest.raises(BatchRunError) as err:
        daily.collect(Engine(),setup,'real-retry',now=NOW,repository=repo,
                      budget_factory=RealBudget,service_factory=RealService)
    result=err.value.outcome
    assert result.failed==1 and result.details['completed_symbols']==2
    assert repo.marked==['BBB','CCC'] and result.details['http_attempts']==5
    assert attempts==[('AAA.US',30)]*3+[('BBB.US',30),('CCC.US',30)]
    assert not tracker.is_circuit_open()
    # On restart only the genuinely incomplete title is requested again.
    monkeypatch.setattr(daily.news_client,'iter_news_pages',lambda **kw:iter([([],None)]))
    resumed=collect(setup,repo,'retry-checkpoints')
    assert resumed.details['skipped_completed']==2 and repo.marked[-1]=='AAA'


@pytest.mark.parametrize('change',[{'http_timeout_seconds':0},{'http_max_attempts':10},
                                 {'failure_cooldown_seconds':0}])
def test_retry_settings_reject_unbounded_or_disabled_protections(change):
    with pytest.raises(ValueError): daily.settings(change)


REAL_ITER_NEWS_PAGES=daily.news_client.iter_news_pages
