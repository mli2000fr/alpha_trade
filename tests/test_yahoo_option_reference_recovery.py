from contextlib import contextmanager
from copy import deepcopy
from datetime import UTC,date,datetime,timedelta
from types import SimpleNamespace
import json

import pytest
import requests

from service.forward_pit.outcomes import Outcome,BatchRunError,preserve_outcome
from service.forward_pit.yahoo_option_references import RecoveryConfig,normalize_daily_reference,recover_references

DAY=date(2026,10,28)
NOW=datetime(2026,10,29,21,tzinfo=UTC)
STAMP=int(datetime(2026,10,28,4,tzinfo=UTC).timestamp())


def payload(symbol='AAA',price=100):
    return {'chart':{'result':[{'meta':dict(symbol=symbol,currency='USD',exchangeTimezoneName='America/New_York',
        instrumentType='EQUITY'),'timestamp':[STAMP], 'indicators':{'quote':[dict(open=[price],high=[price+1],
        low=[price-1],close=[price],volume=[50])]},'events':{}}],'error':None}}


class Clock:
    value=0.
    def now(self):return NOW+timedelta(seconds=self.value)
    def mono(self):return self.value
    def sleep(self,seconds):self.value+=seconds


class Store:
    def __init__(self):self.receipts={};self.last=None;self.saved=[]
    @contextmanager
    def locked(self):yield None
    def cached(self,conn,symbol,day):return deepcopy(self.receipts.get((symbol,day)))
    def last_received(self,conn):return self.last
    def save(self,conn,envelope,status,received):
        self.receipts[envelope['symbol'],date.fromisoformat(envelope['session_date'])]=deepcopy(envelope)
        self.last=received.timestamp();self.saved.append((envelope,status))


class Session:
    def __init__(self,clock,responses):self.clock=clock;self.responses=list(responses);self.calls=[]
    def get(self,url,**kwargs):
        self.calls.append((url,kwargs));self.clock.value+=.2
        result=self.responses.pop(0)
        if isinstance(result,Exception):raise result
        status,body=result
        return SimpleNamespace(status_code=status,json=lambda:deepcopy(body),text='invalid')


def run(tmp_path,*,symbols=('AAA','BBB'),prices=None,responses=None,store=None,config=None,now=None):
    file=tmp_path/'tradable.txt';file.write_text('AAA,BBB,CCC',encoding='utf-8')
    cfg={'yahoo_reference_recovery':dict(enabled=True,symbols_file=str(file))}
    cfg['yahoo_reference_recovery'].update(config or {})
    clock=Clock();store=store or Store()
    session=Session(clock,responses or [(200,payload(s)) for s in symbols])
    outcome=Outcome()
    pauses=[]
    def uniform(low,high):pauses.append((low,high));return 3.25
    result=recover_references(None,cfg,prices=prices or {},symbols=symbols,day=DAY,
        run_id='fixture',batch_name='options_delayed_bars_sync',outcome=outcome,session=session,
        store=store,now_fn=now or clock.now,sleep_fn=clock.sleep,uniform_fn=uniform,monotonic_fn=clock.mono)
    return result,outcome.details['yahoo_reference_recovery'],outcome,session,store,pauses


def test_missing_tradable_only_keeps_alpaca_and_random_pause(tmp_path):
    result,stats,outcome,session,store,pauses=run(tmp_path,symbols=('AAA','BBB','CCC','OUT'),prices={'AAA':90},
        responses=[(200,payload('BBB',105)),(200,{'chart':{'result':[],'error':None}})])
    assert result=={'AAA':90,'BBB':105}
    assert len(session.calls)==stats['calls']==2
    assert all('OUT' not in url and '/AAA' not in url for url,_ in session.calls)
    assert pauses==[(1.,5.)] and stats['pause_seconds']==pytest.approx(3.25)
    assert stats['elapsed_seconds']==pytest.approx(3.65)
    assert stats['remaining_symbols']==['CCC'] and stats['not_found']==1
    assert stats['reference_provider']=='yahoo_finance'
    assert stats['reference_usage']=='OPTION_DISCOVERY_ONLY'
    assert store.saved[0][0]['reference']['session_date']==str(DAY)
    assert session.calls[0][1]['timeout']==20


def test_shared_success_and_empty_cache_avoid_second_batches_http(tmp_path):
    result,stats,_,_,store,_=run(tmp_path,responses=[(200,payload()),(404,{'error':'Not Found'})])
    again,second,_,session,_,_=run(tmp_path,store=store,responses=[])
    assert result==again=={'AAA':100}
    assert second['calls']==0 and second['cache_hits']==1 and session.calls==[]
    assert second['not_found']==1 and second['remaining']==1


@pytest.mark.parametrize('http,expected',[(401,'STOPPED_ACCESS_DENIED'),(403,'STOPPED_ACCESS_DENIED'),(429,'STOPPED_RATE_LIMIT')])
def test_refusal_stops_immediately_and_keeps_primary_successes(tmp_path,http,expected):
    result,stats,outcome,session,store,_=run(tmp_path,symbols=('AAA','BBB','CCC'),prices={'CCC':12},
        responses=[(http,{'error':'blocked'})])
    assert len(session.calls)==stats['calls']==1
    assert result=={'CCC':12} and stats['remaining']==2
    assert stats['status']==expected and stats['stop_http_status']==http
    assert ('🚦' if http==429 else '⛔') in outcome.warnings[0]
    assert store.saved[0][1]==http
    _,second,_,second_session,_,_=run(tmp_path,store=store)
    assert second['status']==expected and not second_session.calls


def test_disabled_and_outside_tradable_do_not_call_yahoo(tmp_path):
    for symbols,settings in [(('AAA',),{'enabled':False}),(('OUT',),{})]:
        _,stats,_,session,_,_=run(tmp_path,symbols=symbols,config=settings)
        assert stats['calls']==0 and not session.calls


def test_before_close_never_uses_a_partial_daily_bar(tmp_path):
    _,stats,outcome,session,_,_=run(tmp_path,now=lambda:datetime(2026,10,28,18,tzinfo=UTC))
    assert stats['status']=='WAITING_FOR_SESSION_CLOSE' and not session.calls and outcome.warnings


def test_three_transport_failures_bounded_no_retry(tmp_path):
    result,stats,outcome,session,store,_=run(tmp_path,symbols=('AAA','BBB','CCC'),
        responses=[requests.Timeout('not logged')]*3)
    assert not result and stats['calls']==3 and stats['status']=='STOPPED_TECHNICAL_ERRORS'
    assert len(store.saved)==3 and outcome.warnings


def test_reference_not_used_when_receipt_commit_fails(tmp_path):
    class BadCommit(Store):
        @contextmanager
        def locked(self):
            yield None
            raise RuntimeError('commit failed')
    result,stats,outcome,_,_,_=run(tmp_path,symbols=('AAA',),store=BadCommit())
    assert not result and not stats['recovered_symbols'] and stats['recovered']==0
    assert stats['status']=='STOPPED_RECEIPT_ERROR' and outcome.warnings


def test_mysql_receipt_commit_precedes_release_of_shared_request_lock():
    from service.forward_pit.yahoo_option_references import SqlReceipts
    events=[]
    class Conn:
        def execute(self,sql,params):
            events.append('release' if 'RELEASE_LOCK' in str(sql) else 'acquire')
            return SimpleNamespace(scalar=lambda:1)
        def commit(self):events.append('commit')
        def rollback(self):events.append('rollback')
    class Engine:
        dialect=SimpleNamespace(name='mysql');url=SimpleNamespace(database='alpha_trade')
        @contextmanager
        def connect(self):yield Conn()
    with SqlReceipts(Engine(),'fixture','batch').locked():events.append('receipt_written')
    assert events==['acquire','receipt_written','commit','release','commit']


@pytest.mark.parametrize('change,message',[
    (lambda d:d['chart']['result'][0]['meta'].update(currency='EUR'),'NON_USD'),
    (lambda d:d['chart']['result'][0]['meta'].update(symbol='OTHER'),'SYMBOL_MISMATCH'),
    (lambda d:d['chart']['result'][0]['meta'].update(exchangeTimezoneName='Europe/Paris'),'TIMEZONE'),
    (lambda d:d['chart']['result'][0]['indicators']['quote'][0].update(volume=[0]),'OHLCV'),
    (lambda d:d['chart']['result'][0]['indicators']['quote'][0].update(close=[float('nan')]),'NUMERIC'),
    (lambda d:d['chart']['result'][0]['indicators']['quote'][0].update(close=[True]),'NUMERIC'),
    (lambda d:d['chart']['result'][0]['indicators']['quote'][0].update(close=[]),'LENGTH'),
])
def test_reference_rejects_wrong_identity_date_scale_or_invalid_values(change,message):
    data=payload();change(data)
    with pytest.raises(ValueError,match=message):normalize_daily_reference(data,'AAA',DAY,NOW)


def test_only_exact_session_and_no_post_session_split():
    data=payload();data['chart']['result'][0]['timestamp']=[STAMP-86400]
    assert normalize_daily_reference(data,'AAA',DAY,NOW) is None
    data=payload();data['chart']['result'][0]['events']={'splits':{'x':dict(date=STAMP+86400)}}
    with pytest.raises(ValueError,match='POST_SESSION_SPLIT'):normalize_daily_reference(data,'AAA',DAY,NOW)
    data=payload('BRK-B')
    assert normalize_daily_reference(data,'BRK.B',DAY,NOW)['provider_symbol']=='BRK-B'


@pytest.mark.parametrize('settings',[dict(enabled='false'),dict(pause_min_seconds=0),dict(pause_max_seconds=6),
    dict(pause_min_seconds=4,pause_max_seconds=2),dict(timeout_seconds=True)])
def test_invalid_settings_fail_fast(settings):
    with pytest.raises(ValueError):RecoveryConfig(**settings)


def test_counters_survive_later_collector_failure():
    outcome=Outcome(details={'yahoo_reference_recovery':{'calls':4,'elapsed_seconds':12.}})
    with pytest.raises(BatchRunError) as error:
        with preserve_outcome(outcome):raise RuntimeError('later Alpaca error')
    assert error.value.outcome is outcome
    assert error.value.outcome.details['yahoo_reference_recovery']['calls']==4


def test_config_enables_only_two_option_recovery_jobs():
    from common.config_loader import load_batch_config
    config=load_batch_config()
    for name in ('oracle_options_indicative_snapshot','options_delayed_bars_sync'):
        settings=config[name]['yahoo_reference_recovery']
        assert settings['enabled'] is True
        assert settings['symbols_file']=='config/univers_batch/univers_filtred_tradable.txt'
        assert settings['pause_min_seconds']==1 and settings['pause_max_seconds']==5
    assert config['analyst_snapshot_collection']['enabled'] is False


@pytest.mark.parametrize('name',['oracle_options_indicative_snapshot','options_delayed_bars_sync'])
def test_each_collector_recovers_after_alpaca_and_preserves_counts_on_later_failure(monkeypatch,name):
    from service.forward_pit import batch,options_delayed
    class Fixed(datetime):
        @classmethod
        def now(cls,tz=None):return datetime(2026,10,28,21,tzinfo=UTC).astimezone(tz)
    monkeypatch.setattr(batch,'datetime',Fixed)
    monkeypatch.setattr(options_delayed,'datetime',Fixed)
    monkeypatch.setattr(batch,'_utcnow',lambda:datetime(2026,10,28,21))
    monkeypatch.setattr(batch,'_collection_symbols',lambda cfg:['AAA','BBB'])
    monkeypatch.setattr(batch,'get_alpaca_credentials',lambda:('fixture','fixture'))
    monkeypatch.setattr(batch,'_configure_alpaca_session',lambda *a,**k:None)
    monkeypatch.setattr(batch,'_raw',lambda *a,**k:None)
    for module in (batch,options_delayed):
        monkeypatch.setattr(module,'historical_sip_snapshots',lambda *a:({'BBB':{'minuteBar':{'c':90}}},200))
    monkeypatch.setattr(batch,'_paginated_json',lambda *a,**k:(_ for _ in ()).throw(RuntimeError('later catalogue failure')))
    captured=[]
    def recovery(engine,cfg,**kwargs):
        captured.append(kwargs)
        kwargs['outcome'].details['yahoo_reference_recovery']=dict(calls=4,elapsed_seconds=12.)
        return kwargs['prices']|{'AAA':100}
    monkeypatch.setattr('service.forward_pit.yahoo_option_references.recover_references',recovery)
    class Engine:
        @contextmanager
        def begin(self):yield SimpleNamespace()
    method=batch.options_snapshot if name=='oracle_options_indicative_snapshot' else options_delayed.options_delayed_bars_sync
    with pytest.raises(BatchRunError) as exc:
        method(Engine(),{'request_interval_seconds':0},'fixture',False)
    assert len(captured)==1 and captured[0]['prices']=={'BBB':90}
    assert captured[0]['batch_name']==name and captured[0]['day']==DAY
    assert exc.value.outcome.details['yahoo_reference_recovery']['calls']==4


def test_sql_cache_validates_hash_and_exact_scope_without_schema_changes(monkeypatch):
    from sqlalchemy import create_engine,text
    from service.forward_pit import batch
    from service.forward_pit.yahoo_option_references import SqlReceipts,PROTOCOL,ENDPOINT,PROVIDER
    engine=create_engine('sqlite://')
    now=datetime.now(UTC)
    envelope=dict(protocol=PROTOCOL,symbol='AAA',session_date=str(DAY),reference={'price':100},response=payload())
    with engine.begin() as conn:
        conn.exec_driver_sql('CREATE TABLE pit_raw_payloads (id INTEGER,provider TEXT,endpoint TEXT,entity_key TEXT,'
            'observed_at TIMESTAMP,available_at TIMESTAMP,payload_json TEXT,payload_hash TEXT)')
        params=dict(provider=PROVIDER,endpoint=ENDPOINT,entity=f'{PROTOCOL}:AAA:{DAY}',
            observed=now.replace(tzinfo=None),payload=json.dumps(envelope),hash=batch._hash(envelope))
        conn.execute(text('INSERT INTO pit_raw_payloads VALUES (1,:provider,:endpoint,:entity,:observed,:observed,:payload,:hash)'),params)
    store=SqlReceipts(engine,'run','batch')
    # SQLite textual timestamp conversion differs from MySQL; use the same
    # driver-level datetime conversion on the actual SELECT in this test.
    class Conn:
        def __init__(self,conn):self.conn=conn
        def execute(self,statement,params):
            result=self.conn.execute(statement,params).mappings().first()
            if result:
                result=dict(result);result['observed_at']=datetime.fromisoformat(result['observed_at'])
            class Result:
                def mappings(self):return self
                def first(self):return result
            return Result()
    with engine.connect() as conn:
        assert store.cached(Conn(conn),'AAA',DAY)==envelope
        assert store.cached(Conn(conn),'AAA',DAY-timedelta(days=1)) is None
    with engine.begin() as conn:conn.exec_driver_sql("UPDATE pit_raw_payloads SET payload_hash='bad'")
    with engine.connect() as conn:
        with pytest.raises(ValueError,match='hash mismatch'):store.cached(Conn(conn),'AAA',DAY)
    engine.dispose()
