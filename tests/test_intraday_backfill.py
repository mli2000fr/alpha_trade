from datetime import date,datetime,timezone
from pathlib import Path
from unittest.mock import MagicMock
import json
import pytest
from service.eodhd import intraday_backfill as backfill
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
    assert any('service.eodhd.intraday_backfill' in x.value for x in at.code)


def test_plan_json_roundtrip_is_identical(tmp_path,monkeypatch):
    import json
    universe=tmp_path/'universe.txt'
    universe.write_text('ABC\n',encoding='utf-8')
    monkeypatch.setattr(backfill,'load_universe_file_symbols',lambda *a,**k:['ABC'])
    monkeypatch.setattr(backfill,'resolve_universe_file_path',lambda *a,**k:universe)
    plan=backfill.build_plan(date(2025,1,2),date(2025,1,3),'universe-file:universe.txt','5m',30)
    assert json.loads(json.dumps(plan))==plan
