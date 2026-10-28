from datetime import date, datetime, timezone
from dataclasses import replace
from unittest.mock import MagicMock

import pytest

from execution_engine.broker_adapter import BrokerAdapter
from execution_engine.config import ExecutionConfig
from execution_engine.models import IntentRole, OrderIntent
from service.alpaca import clientAlpaca as client
from service.alpaca.sip_reference import historical_sip_snapshots
from service.market import intraday_backfill
from scripts.operations.migrate_legacy_quotes_to_sip import fetch_last_quotes, replacement_rows, MigrationBlocked, _get_page


def intent(role):
    return OrderIntent(intent_id='id',risk_run_id='r',exec_run_id='e',symbol='AAPL',side='buy',qty=1,
                       order_type='market',limit_price=None,trail_percent=None,broker_mode='paper',
                       parent_intent_id=None,intent_role=role,idempotency_key='k',decision_price=100)


@pytest.mark.parametrize('role',[IntentRole.ENTRY,IntentRole.REBALANCE_BUY])
def test_no_new_entry_without_sip_even_with_an_old_risk_target(monkeypatch,role):
    http=MagicMock()
    monkeypatch.setattr('execution_engine.broker_adapter.fetch_latest_quotes',MagicMock(side_effect=RuntimeError('403')))
    adapter=BrokerAdapter(http,ExecutionConfig())
    with pytest.raises(Exception,match='consolidée temps réel'):
        adapter.submit_intent(intent(role))
    http.submit_order.assert_not_called()


def test_existing_exit_does_not_require_sip_permission(monkeypatch):
    http=MagicMock(); http.submit_order.return_value={"id":"test","symbol":"AAPL","status":"new"}
    quote=MagicMock(side_effect=AssertionError('No quote request for an exit'))
    monkeypatch.setattr('execution_engine.broker_adapter.fetch_latest_quotes',quote)
    BrokerAdapter(http,ExecutionConfig()).submit_intent(intent(IntentRole.EXIT))
    assert http.submit_order.call_count==1 and quote.call_count==0


@pytest.mark.parametrize('side',['buy','sell'])
def test_valid_sip_access_allows_long_or_short_entry(monkeypatch,side):
    http=MagicMock();http.submit_order.return_value={'id':'test','symbol':'AAPL','status':'new'}
    quote=MagicMock(return_value={'AAPL':{'bp':100,'ap':100.05,
        't':datetime.now(timezone.utc).isoformat(), 'provider':'alpaca', 'feed':'sip', 'is_realtime':True}})
    monkeypatch.setattr('execution_engine.broker_adapter.fetch_latest_quotes',quote)
    row=replace(intent(IntentRole.ENTRY),side=side)
    BrokerAdapter(http,ExecutionConfig()).submit_intent(row)
    assert http.submit_order.call_count==1


@pytest.mark.parametrize('quote',[{}, {'bp':float('nan'),'ap':101}, {'bp':102,'ap':101}])
def test_invalid_sip_quote_cannot_open_a_position(monkeypatch,quote):
    http=MagicMock()
    monkeypatch.setattr('execution_engine.broker_adapter.fetch_latest_quotes',lambda *a,**k:{'AAPL':quote})
    with pytest.raises(Exception,match='consolidée temps réel'):
        BrokerAdapter(http,ExecutionConfig()).submit_intent(intent(IntentRole.ENTRY))
    http.submit_order.assert_not_called()


def test_existing_position_price_remains_available_to_protections_without_sip(monkeypatch):
    http=MagicMock();http.get_position.return_value={"qty":"10","current_price":"101"}
    quote=MagicMock(side_effect=RuntimeError('403'))
    monkeypatch.setattr('execution_engine.broker_adapter.fetch_latest_quotes',quote)
    assert BrokerAdapter(http,ExecutionConfig()).get_latest_market_price('AAPL')==101
    quote.assert_not_called()


def test_default_feed_is_sip_and_latest_rejects_iex():
    assert client.DEFAULT_FEED=='sip'
    with pytest.raises(ValueError,match='SIP obligatoire'):
        client.fetch_latest_quotes(['AAPL'],feed='iex')


def test_old_intraday_plan_is_not_relabelled_or_resumed(monkeypatch):
    engine=MagicMock();monkeypatch.setattr(intraday_backfill,'get_sqlalchemy_engine',engine)
    with pytest.raises(ValueError,match='Ancien plan IEX'):
        intraday_backfill.run({'provider':'alpaca','alpaca_feed':'iex'})
    engine.assert_not_called()


def test_options_reference_uses_delayed_sip_not_the_realtime_snapshot():
    calls=[]
    def get(session,url,params,headers):
        calls.append((url,params))
        return {'bars':{'AAPL':[{'t':'2026-10-16T17:30:00Z','c':100}]}},200
    rows,status=historical_sip_snapshots(None,['AAPL'],{},get,now=datetime(2026,10,16,18,tzinfo=timezone.utc))
    assert status==200 and rows['AAPL']['stock_reference_feed']=='sip'
    assert calls[0][0].endswith('/bars') and calls[0][1]['feed']=='sip'
    assert datetime.fromisoformat(calls[0][1]['end'])<=datetime(2026,10,16,17,40,tzinfo=timezone.utc)


def test_migration_requires_complete_pagination_before_return(tmp_path,monkeypatch):
    monkeypatch.setattr('scripts.operations.migrate_legacy_quotes_to_sip.time.sleep',lambda _:None)
    http=MagicMock(); http.get.return_value.status_code=200
    http.get.return_value.json.return_value={'quotes':{'AAPL':[]},'next_page_token':'LOOP'}
    with pytest.raises(MigrationBlocked,match='pagination'):
        fetch_last_quotes(http,['AAPL'],date(2026,10,16),{},tmp_path,{'requests_this_process':0},1)


def test_migration_never_falls_back_on_403(tmp_path,monkeypatch):
    monkeypatch.setattr('scripts.operations.migrate_legacy_quotes_to_sip.time.sleep',lambda _:None)
    http=MagicMock();http.get.return_value.status_code=403
    with pytest.raises(MigrationBlocked,match='403'):
        fetch_last_quotes(http,['AAPL'],date(2026,10,16),{},tmp_path,{'requests_this_process':0},1)
    assert http.get.call_count==1 and http.get.call_args.kwargs['params']['feed']=='sip'


def test_migration_transient_network_retry_is_bounded(monkeypatch):
    import requests
    monkeypatch.setattr('scripts.operations.migrate_legacy_quotes_to_sip.time.sleep',lambda _:None)
    http=MagicMock();ok=MagicMock(status_code=200)
    http.get.side_effect=[requests.ReadTimeout(),ok]
    stats={'requests_this_process':0}
    assert _get_page(http,{'feed':'sip'},{},stats,.5) is ok
    assert stats['requests_this_process']==2
    http.get.side_effect=requests.ReadTimeout()
    with pytest.raises(MigrationBlocked,match='3 attempts'):
        _get_page(http,{'feed':'sip'},{},stats,.5)
    assert stats['requests_this_process']==5


def test_migration_quota_refusal_is_not_retried(monkeypatch):
    monkeypatch.setattr('scripts.operations.migrate_legacy_quotes_to_sip.time.sleep',lambda _:None)
    http=MagicMock();http.get.return_value.status_code=429
    with pytest.raises(MigrationBlocked,match='429'):
        _get_page(http,{'feed':'sip'},{},{'requests_this_process':0},.5)
    assert http.get.call_count==1


def test_selector_reads_only_a_real_qualified_sip_archive(tmp_path,monkeypatch):
    import pandas as pd
    from sqlalchemy import create_engine
    from common import quote_quality
    from dataIntegrityEngine.sync_latest_quotes import _build_quote_snapshot_row
    from selector.db_io import fetch_quote_snapshots
    monkeypatch.setattr(quote_quality,'ARCHIVE_ROOT',tmp_path/'artifacts'/'quotes')
    day=date(2026,10,16);now=datetime(2026,10,17,20)
    quote={'bp':100,'ap':100.05,'bs':100,'as':100,'t':'2026-10-16T19:59:59Z'}
    row=_build_quote_snapshot_row('AAPL',quote,fallback_utc_now=now)
    row.update(quote_quality.archive_quote('AAPL',day,'sip',quote,now),quality_status='VALID_RTH',
               source_timestamp=row['quote_timestamp'],instrument_id=1)
    engine=create_engine('sqlite://')
    pd.DataFrame([row]).to_sql('stock_quote_snapshots',engine,index=False)
    result=fetch_quote_snapshots(engine,set(row),['AAPL'],reference_date=day)
    assert result.symbol.tolist()==['AAPL'] and result.iloc[0]['quote_source']=='alpaca_sip'
