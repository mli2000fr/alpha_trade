from datetime import date,datetime,timezone
from pathlib import Path
from unittest.mock import MagicMock
import json
import pytest
from service.market import intraday_backfill as backfill
from service.eodhd import clientEodhd as client
from service.eodhd.quota import EodhdQuotaTracker
from database import intraday_bars as store


def sample(stamp='2025-01-02T14:30:00+00:00',**overrides):
    result=dict(timestamp=int(datetime.fromisoformat(stamp).timestamp()),open=100,high=102,low=99,close=101,volume=100)
    result.update(overrides)
    return result


def normalize(payload,interval='5m'):
    return backfill.normalize_bars(payload,symbol='ABC',interval=interval,start=date(2025,1,2),
        end_exclusive=date(2025,1,3),observed=datetime(2026,10,11),run_id='test',
        sessions={date(2025,1,2):(datetime(2025,1,2,14,30,tzinfo=timezone.utc),datetime(2025,1,2,21,tzinfo=timezone.utc))})


def test_utc_dst_and_slices():
    a,b=backfill.utc_bounds(date(2025,3,9),date(2025,3,10))
    assert (b-a).total_seconds()==23*3600
    assert list(backfill.date_slices(date(2025,1,1),date(2025,1,3),2))==[
        (date(2025,1,1),date(2025,1,3)),(date(2025,1,3),date(2025,1,4))]


def test_normalization_raw_and_no_fabricated_fields():
    rows,errors,outside=normalize([sample(),sample()])
    assert len(rows)==1 and errors==[] and outside==0
    assert rows[0]['bar_timestamp']==datetime(2025,1,2,14,30)
    assert rows[0]['bar_end_timestamp']==datetime(2025,1,2,14,35)
    assert rows[0]['session_tag']=='regular' and rows[0]['data_adjustment']=='raw'
    assert 'adj_close' not in rows[0] and 'vwap' not in rows[0]


@pytest.mark.parametrize('overrides',[dict(high=50),dict(volume=-1),dict(volume=.5),dict(close=float('nan')),dict(open=1e-12)])
def test_invalid_rows_rejected(overrides):
    rows,errors,_=normalize([sample(**overrides)])
    assert not rows and len(errors)==1


def test_conflicting_duplicate_response_not_arbitrarily_selected():
    rows,errors,_=normalize([sample(),sample(close=102)])
    assert not rows and errors


def test_half_open_date_boundary_and_session_tags():
    rows,errors,outside=normalize([sample('2025-01-03T05:00:00+00:00'),sample('2025-01-02T21:00:00+00:00')])
    assert outside==1 and not errors
    assert rows[0]['session_tag']=='post_market'


def test_quota_and_client_params(monkeypatch):
    calls={}
    def request(**kwargs):calls.update(kwargs);return [sample()]
    monkeypatch.setattr(client,'_do_request',request)
    monkeypatch.setattr(client,'_get_token',lambda:'secret-test')
    monkeypatch.setattr(client,'_get_base_url',lambda:'https://eodhd.com/api')
    client.fetch_intraday('BF.B',start_epoch=100,end_epoch=400,interval='5m')
    assert calls['url'].endswith('/intraday/BF-B.US')
    assert calls['endpoint']=='intraday' and calls['params']['interval']=='5m'
    assert EodhdQuotaTracker().cost_for('intraday')==5
    with pytest.raises(ValueError):client.fetch_intraday('ABC',start_epoch=0,end_epoch=601*86400)


def test_sql_short_tranches_and_us_guard():
    engine=MagicMock();conn=engine.begin.return_value.__enter__.return_value
    conn.execute.return_value.scalar.return_value='alpha_trade'
    rows=[{'x':x} for x in range(1001)]
    assert store.persist_rows(engine,rows)==1001
    batches=[c.args[1] for c in conn.execute.call_args_list if len(c.args)>1]
    assert [len(x) for x in batches]==[500,500,1]
    assert 'ON DUPLICATE KEY UPDATE' in str(store.UPSERT)
    conn.execute.return_value.scalar.return_value='alpha_trade_fr'
    with pytest.raises(RuntimeError):store.persist_rows(engine,[{}])


def test_run_resume_no_second_api_request(tmp_path,monkeypatch):
    plan=dict(plan_id='intraday-test',tasks=1,symbols=['ABC'],ranges=[['2025-01-02','2025-01-03']],interval='5m')
    monkeypatch.setattr(backfill,'ROOT',tmp_path)
    monkeypatch.setattr(backfill,'get_sqlalchemy_engine',lambda:MagicMock())
    monkeypatch.setattr(backfill,'ensure_table',lambda engine:None)
    monkeypatch.setattr(backfill,'persist_rows',lambda engine,rows:len(rows))
    monkeypatch.setattr(backfill.time,'sleep',lambda _:None)
    calendar=MagicMock();calendar.sessions.return_value=[]
    monkeypatch.setattr(backfill,'get_market_calendar',lambda *a,**k:calendar)
    fetch=MagicMock(return_value=[sample()]);monkeypatch.setattr(backfill,'fetch_intraday',fetch)
    first=backfill.run(plan);second=backfill.run(plan)
    assert first['status']==second['status']=='COMPLETED'
    assert first['persisted']==second['persisted']==1
    assert second['skipped']==1 and fetch.call_count==1


def test_permission_error_stops_all_following_requests(tmp_path,monkeypatch):
    plan=dict(plan_id='intraday-test',tasks=2,symbols=['ABC','DEF'],ranges=[['2025-01-02','2025-01-03']],interval='5m')
    monkeypatch.setattr(backfill,'ROOT',tmp_path)
    monkeypatch.setattr(backfill,'get_sqlalchemy_engine',lambda:MagicMock())
    monkeypatch.setattr(backfill,'ensure_table',lambda engine:None)
    calendar=MagicMock();calendar.sessions.return_value=[]
    monkeypatch.setattr(backfill,'get_market_calendar',lambda *a,**k:calendar)
    fetch=MagicMock(side_effect=client.EodhdPermissionError('HTTP 403 intraday'))
    monkeypatch.setattr(backfill,'fetch_intraday',fetch)
    result=backfill.run(plan)
    assert result['status']=='BLOCKED' and fetch.call_count==1


def test_navigation_and_page_default(monkeypatch):
    from ihm.services.navigation import get_navigation_sections
    assert any(p.key=='intraday_bars' for s in get_navigation_sections() for p in s.pages)
    from ihm.pages import intraday_bars as page
    monkeypatch.setattr(page,'load_pipeline_history',lambda:[])
    from streamlit.testing.v1 import AppTest
    at=AppTest.from_string('from ihm.pages.intraday_bars import render\nrender()').run(timeout=20)
    assert not at.exception
    assert any(x.value=='5m' for x in at.selectbox)
    assert any(x.value==backfill.DEFAULT_SOURCE for x in at.selectbox)
    assert any('service.market.intraday_backfill' in x.value for x in at.code)
    assert any(x.value=='alpaca' for x in at.selectbox)
    assert at.selectbox(key='intraday_feed').value=='sip'


def test_missing_configuration_defaults_to_sip(monkeypatch):
    monkeypatch.setattr(backfill,'load_config',lambda:{})
    assert backfill.intraday_defaults()['alpaca_feed']=='sip'


@pytest.mark.parametrize('status',['completed','running'])
def test_page_run_controls(tmp_path,monkeypatch,status):
    from ihm.pages import intraday_bars as page
    from streamlit.testing.v1 import AppTest
    record=dict(run_id='test-run',step_key='intraday_backfill',status=status,
                command=['--expected-plan-id','test-plan'])
    history=[record]
    monkeypatch.setattr(page,'PROJECT_ROOT',tmp_path)
    monkeypatch.setattr(page,'load_pipeline_history',lambda:list(history))
    monkeypatch.setattr(page,'poll_pipeline_run',lambda _:record)
    monkeypatch.setattr(page,'read_pipeline_logs',lambda _:'INFO test')
    stop=MagicMock(return_value=True)
    monkeypatch.setattr(page,'stop_pipeline_run',stop)
    delete=MagicMock(side_effect=lambda *a,**k:history.clear() or True)
    monkeypatch.setattr(page,'delete_pipeline_history_run',delete)
    at=AppTest.from_string('from ihm.pages.intraday_bars import render\nrender()').run(timeout=20)
    assert not at.exception
    assert at.button(key='intraday_stop_test-run').disabled==(status=='completed')
    assert at.button(key='intraday_delete_test-run').disabled==(status=='running')
    if status=='completed':
        at.button(key='intraday_delete_test-run').click().run(timeout=20)
        assert not at.exception
        delete.assert_called_once_with('test-run',expected_step_key='intraday_backfill')
        assert not any(x.label=='Exécution à suivre' for x in at.selectbox)
    else:
        at.button(key='intraday_stop_test-run').click().run(timeout=20)
        assert not at.exception
        stop.assert_called_once_with('test-run')


def test_run_history_deletion_is_scoped_and_persistent(tmp_path,monkeypatch):
    from ihm.services import process_registry as registry
    monkeypatch.setattr(registry,'RUNS_DIR',tmp_path)
    monkeypatch.setattr(registry,'HISTORY_INDEX_PATH',tmp_path/'history_index.json')
    monkeypatch.setattr(registry,'_ACTIVE_RUNS',{})
    monkeypatch.setattr(registry,'_ACTIVE_WORKFLOWS',{})
    monkeypatch.setattr(registry,'_RECOVERY_DONE',False)
    monkeypatch.setattr(registry,'_recover_history_index_entries',lambda index:{})
    records={status:dict(run_id=status,step_key='intraday_backfill',status=status)
             for status in ['completed','failed','running','starting','scheduled']}
    registry._write_history_index(records)
    for status in ['running','starting','scheduled']:
        with pytest.raises(ValueError):
            registry.delete_pipeline_history_run(status,expected_step_key='intraday_backfill')
    with pytest.raises(ValueError):
        registry.delete_pipeline_history_run('completed',expected_step_key='other')
    assert registry.delete_pipeline_history_run('completed',expected_step_key='intraday_backfill')
    assert registry._read_history_index()['completed']['history_deleted']
    assert 'completed' not in {r['run_id'] for r in registry.load_pipeline_history()}
    monkeypatch.setattr(registry,'_RECOVERY_DONE',False)
    assert 'completed' not in {r['run_id'] for r in registry.load_pipeline_history()}


def test_plan_json_roundtrip_is_identical(tmp_path,monkeypatch):
    import json
    universe=tmp_path/'universe.txt'
    universe.write_text('ABC\n',encoding='utf-8')
    monkeypatch.setattr(backfill,'load_universe_file_symbols',lambda *a,**k:['ABC'])
    monkeypatch.setattr(backfill,'resolve_universe_file_path',lambda *a,**k:universe)
    plan=backfill.build_plan(date(2025,1,2),date(2025,1,3),'universe-file:universe.txt','5m',30)
    assert json.loads(json.dumps(plan))==plan


def test_provider_feed_in_plan_identity(tmp_path,monkeypatch):
    universe=tmp_path/'universe.txt';universe.write_text('ABC\n',encoding='utf-8')
    monkeypatch.setattr(backfill,'load_universe_file_symbols',lambda *a,**k:['ABC'])
    monkeypatch.setattr(backfill,'resolve_universe_file_path',lambda *a,**k:universe)
    args=(date(2025,1,2),date(2025,1,3),'universe-file:universe.txt','5m',30)
    plans=[backfill.build_plan(*args,provider=p,alpaca_feed=f) for p,f in [('alpaca','iex'),('alpaca','sip'),('eodhd','iex')]]
    assert len({p['plan_id'] for p in plans})==3
    assert plans[0]['estimated_api_credits'] is None and plans[2]['estimated_api_credits']==5


def test_configuration_defaults_and_cli_options(monkeypatch):
    monkeypatch.setattr(backfill,'load_config',lambda:{'intraday_backfill':dict(provider='eodhd',alpaca_feed='sip',account_id='test1')})
    assert backfill.intraday_defaults()==dict(provider='eodhd',alpaca_feed='sip',account_id='test1')
    from ihm.services import intraday_backfill as ui
    command=ui.build_command(date(2025,1,2),date(2025,1,3),backfill.DEFAULT_SOURCE)
    assert command[command.index('--provider')+1]=='eodhd'
    command=ui.build_command(date(2025,1,2),date(2025,1,3),backfill.DEFAULT_SOURCE,provider='alpaca')
    assert command[command.index('--alpaca-feed')+1]=='sip'
    assert command[command.index('--account-id')+1]=='test1'


def test_alpaca_pagination_raw_and_feed(monkeypatch):
    from service.alpaca import intraday_bars as alpaca
    monkeypatch.setattr(alpaca,'_build_headers',lambda _:dict(fake='test'))
    monkeypatch.setattr(alpaca.time,'sleep',lambda _:None)
    calls=[]
    def request(session,method,url,**kwargs):
        assert method=='GET' and url.endswith('/v2/stocks/bars')
        calls.append(dict(kwargs['params']))
        response=MagicMock(status_code=200)
        response.json.return_value=dict(bars={'ABC':[dict(t='2025-01-02T14:30:00Z',o=10,h=12,l=9,c=11,v=100,n=5,vw=10.5)]},
            next_page_token='page2' if len(calls)==1 else None)
        return response
    monkeypatch.setattr(alpaca,'request_with_retry',request)
    rows=alpaca.fetch_intraday('ABC',start_epoch=100,end_epoch=200,feed='sip',session=MagicMock())
    assert len(rows)==2 and rows[0]['vw']==10.5
    assert calls[0]['feed']=='sip' and calls[0]['timeframe']=='5Min'
    assert calls[0]['asof']=='-' and calls[0]['adjustment']=='raw'
    assert calls[1]['page_token']=='page2'


@pytest.mark.parametrize('code',[401,403,429])
def test_alpaca_http_exception_stops_no_feed_fallback(monkeypatch,code):
    from service.alpaca import intraday_bars as alpaca
    import requests
    monkeypatch.setattr(alpaca,'_build_headers',lambda _:dict(fake='test'))
    response=requests.Response();response.status_code=code
    request=MagicMock(side_effect=requests.HTTPError('failed',response=response))
    monkeypatch.setattr(alpaca,'request_with_retry',request)
    with pytest.raises(alpaca.AlpacaIntradayBlocked):
        alpaca.fetch_intraday('ABC',start_epoch=100,end_epoch=200,feed='sip',session=MagicMock())
    assert request.call_count==1


def test_alpaca_run_persists_explicit_provider_and_resumes(tmp_path,monkeypatch):
    plan=dict(version=2,provider='alpaca',alpaca_feed='iex',account_id='default',plan_id='alpaca-test',
        tasks=1,symbols=['ABC'],ranges=[['2025-01-02','2025-01-03']],interval='5m')
    monkeypatch.setattr(backfill,'ROOT',tmp_path)
    monkeypatch.setattr(backfill,'get_sqlalchemy_engine',lambda:MagicMock())
    monkeypatch.setattr(backfill,'ensure_table',lambda _:None)
    saved=[]
    def persist(engine,rows):saved.extend(rows);return len(rows)
    monkeypatch.setattr(backfill,'persist_rows',persist)
    monkeypatch.setattr(backfill.time,'sleep',lambda _:None)
    calendar=MagicMock();calendar.sessions.return_value=[]
    monkeypatch.setattr(backfill,'get_market_calendar',lambda *a,**k:calendar)
    fetch=MagicMock(return_value=[sample()]);monkeypatch.setattr(backfill,'fetch_alpaca_intraday',fetch)
    assert backfill.run(plan)['status']=='COMPLETED'
    assert backfill.run(plan)['skipped']==1 and fetch.call_count==1
    assert saved[0]['provider']=='alpaca' and saved[0]['data_source']=='alpaca_iex'
    assert saved[0]['provider_symbol']=='ABC'


def test_log_panel_explains_stream_and_renders(monkeypatch):
    from ihm.pages import intraday_bars as page
    record=dict(run_id='intraday-log-test',step_key='intraday_backfill',status='completed',
                command=['--expected-plan-id','no-test-artifact'])
    monkeypatch.setattr(page,'load_pipeline_history',lambda:[record])
    monkeypatch.setattr(page,'poll_pipeline_run',lambda _:record)
    monkeypatch.setattr(page,'read_pipeline_logs',lambda _:'[stderr] INFO SKM 2025-01-01 -> 2025-01-31 (5m)')
    from streamlit.testing.v1 import AppTest
    at=AppTest.from_string('from ihm.pages.intraday_bars import render\nrender()').run(timeout=20)
    assert not at.exception
    assert any('INFO SKM' in x.value for x in at.code)
    assert any('pas une erreur' in x.value for x in at.caption)
