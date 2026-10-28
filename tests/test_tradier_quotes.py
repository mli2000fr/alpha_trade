"""Production quote connector and source/freshness isolation. All HTTP is mocked."""
from datetime import datetime, timedelta, timezone
import json
from unittest.mock import MagicMock

import pytest
import requests

from service.tradier import quotes as tradier
from service.market import live_quotes

NOW = datetime.now(timezone.utc)


def raw(symbol='AAPL', **changes):
    return dict(symbol=symbol, type='stock', bid=100, ask=100.1, bidsize=100, asksize=200,
                bid_date=int((NOW-timedelta(seconds=2)).timestamp()*1000),
                ask_date=int(NOW.timestamp()*1000), **changes)


def response(payload, status=200):
    result = requests.Response()
    result.status_code = status
    result._content = json.dumps(payload).encode()
    result.url = tradier.ENDPOINT
    return result


@pytest.fixture(autouse=True)
def token(monkeypatch):
    monkeypatch.setenv('TRADIER_API_TOKEN', 'test-token-never-real')


def call(monkeypatch, rows, symbols=None, settings=None):
    http = MagicMock(return_value=response({'quotes': {'quote': rows}}))
    monkeypatch.setattr(tradier, 'request_with_retry', http)
    session = MagicMock()
    result = tradier.fetch_latest_quotes(symbols or ['AAPL'], session=session, settings=settings or {})
    return result, http, session


def test_singleton_normalized_and_timestamp_is_oldest_bid_ask_not_last_trade(monkeypatch):
    result, http, session = call(monkeypatch, raw(trade_date=1))
    quote = result['AAPL']
    assert quote['provider'] == 'tradier' and quote['feed'] == 'consolidated'
    assert quote['is_realtime'] is True
    assert quote['t'] == quote['bid_time'] and quote['t'] != quote['ask_time']
    assert quote['bp'] == 100 and quote['bs'] == 100
    live_quotes.validate_live_quote(quote, now=NOW, require_sizes=True)
    args, kwargs = http.call_args
    assert args == (session, 'GET', tradier.ENDPOINT)
    assert kwargs['headers']['Authorization'] == 'Bearer test-token-never-real'
    assert kwargs['params'] == {'symbols': 'AAPL', 'greeks': 'false'}
    assert kwargs['allow_redirects'] is False
    session.close.assert_not_called()


def test_share_classes_and_batches_do_not_change_internal_identity(monkeypatch):
    calls = []
    def get(session, method, url, **kw):
        assert method == 'GET' and url == tradier.ENDPOINT
        symbols = kw['params']['symbols'].split(',')
        calls.append(symbols)
        return response({'quotes': {'quote': [raw(s) for s in symbols]}})
    monkeypatch.setattr(tradier, 'request_with_retry', get)
    result = tradier.fetch_latest_quotes(['brk.b', 'AAPL', 'BRK.B'], session=MagicMock(), settings={'batch_size': 1})
    assert calls == [['BRK/B'], ['AAPL']]
    assert set(result) == {'BRK.B', 'AAPL'}


@pytest.mark.parametrize('rows', [[raw('OTHER')], [raw(), raw()], 'bad', [None]])
def test_unexpected_duplicate_or_malformed_response_rejected(monkeypatch, rows):
    with pytest.raises(RuntimeError):
        call(monkeypatch, rows)


@pytest.mark.parametrize('key,value', [
    ('bid_date', None), ('ask_date', 0), ('bid', 'NaN'), ('ask', 99),
    ('ask', 100), ('bidsize', 0), ('type', 'option'), ('currency', 'EUR'),
    ('delayed', True), ('realtime', False),
])
def test_bad_symbol_is_isolated_without_invented_prices_or_timestamp(monkeypatch, key, value):
    bad = raw(); bad[key] = value
    result, _, _ = call(monkeypatch, [bad, raw('MSFT')], ['AAPL', 'MSFT'])
    assert set(result) == {'MSFT'}


@pytest.mark.parametrize('delta', [timedelta(minutes=16), timedelta(seconds=-2)])
def test_delayed_or_future_side_rejected_even_when_other_side_is_current(monkeypatch, delta):
    row = raw(); row['bid_date'] = int((NOW-delta).timestamp()*1000)
    result, _, _ = call(monkeypatch, row)
    with pytest.raises(ValueError, match='future|périmée'):
        live_quotes.validate_live_quote(result['AAPL'], now=NOW)


def test_missing_token_sandbox_and_ambiguous_alias_fail_before_http(monkeypatch):
    http = MagicMock()
    monkeypatch.setattr(tradier, 'request_with_retry', http)
    monkeypatch.delenv('TRADIER_API_TOKEN')
    with pytest.raises(RuntimeError, match='TRADIER_API_TOKEN'):
        tradier.fetch_latest_quotes(['AAPL'], settings={})
    monkeypatch.setenv('TRADIER_API_TOKEN', 'test')
    with pytest.raises(ValueError, match='sandbox'):
        tradier.fetch_latest_quotes(['AAPL'], settings={'environment': 'sandbox'})
    with pytest.raises(ValueError, match='ambigu'):
        tradier.fetch_latest_quotes(['BRK.B', 'BRK/B'], settings={})
    http.assert_not_called()


@pytest.mark.parametrize('status,expected_calls', [(401, 1), (403, 1), (429, 3), (503, 3)])
def test_bounded_retry_and_no_retry_for_access_denial(monkeypatch, status, expected_calls):
    from service._http_retry import CircuitBreaker
    monkeypatch.setattr('service._http_retry.time.sleep', lambda _: None)
    original = tradier.request_with_retry
    monkeypatch.setattr(tradier, 'request_with_retry', lambda *a, **kw: original(*a, breaker=CircuitBreaker(), **kw))
    session = MagicMock(); session.request.return_value = response({}, status)
    with pytest.raises(requests.HTTPError):
        tradier.fetch_latest_quotes(['AAPL'], session=session, settings={})
    assert session.request.call_count == expected_calls


@pytest.mark.parametrize('message,calls', [('Quota Violation', 3), ('invalid symbol', 1)])
def test_only_tradier_quota_400_is_retried(monkeypatch, message, calls):
    from service._http_retry import CircuitBreaker
    monkeypatch.setattr('service._http_retry.time.sleep', lambda _: None)
    original = tradier.request_with_retry
    monkeypatch.setattr(tradier, 'request_with_retry', lambda *a, **kw: original(*a, breaker=CircuitBreaker(), **kw))
    session = MagicMock(); session.request.return_value = response({'fault': message}, 400)
    with pytest.raises(requests.HTTPError):
        tradier.fetch_latest_quotes(['AAPL'], session=session, settings={})
    assert session.request.call_count == calls


def test_configured_tradier_does_not_touch_alpaca_or_change_execution_account(monkeypatch):
    monkeypatch.setattr('common.config_loader.load_config', lambda: {'market_data': {'quotes_provider_live': 'tradier'}})
    fetch = MagicMock(return_value={'AAPL': {}})
    monkeypatch.setattr(tradier, 'fetch_latest_quotes', fetch)
    alpaca = MagicMock(side_effect=AssertionError('No fallback'))
    monkeypatch.setattr('service.alpaca.clientAlpaca.fetch_latest_quotes', alpaca)
    live_quotes.fetch_latest_quotes(['AAPL'], account_id='default')
    assert fetch.call_args.kwargs['account_id'] == 'default'
    alpaca.assert_not_called()
    fetch.side_effect = RuntimeError('403')
    with pytest.raises(RuntimeError, match='403'):
        live_quotes.fetch_latest_quotes(['AAPL'])
    alpaca.assert_not_called()


@pytest.mark.parametrize('provider', ['yahoo', 'iex', 'typo'])
def test_unknown_or_nonconsolidated_provider_cannot_silently_fallback(monkeypatch, provider):
    monkeypatch.setattr('common.config_loader.load_config', lambda: {'market_data': {'quotes_provider_live': provider}})
    with pytest.raises(ValueError):
        live_quotes.fetch_latest_quotes(['AAPL'])


def test_owned_session_closes_on_http_failure(monkeypatch):
    session = MagicMock()
    monkeypatch.setattr(tradier, 'verified_session', lambda: session)
    monkeypatch.setattr(tradier, 'request_with_retry', MagicMock(side_effect=RuntimeError('no access')))
    with pytest.raises(RuntimeError):
        tradier.fetch_latest_quotes(['AAPL'], settings={})
    session.close.assert_called_once()


def test_risk_and_pre_submission_keep_tradier_provenance(monkeypatch):
    from risk_management.cli import _load_live_spread_snapshots
    from run_execution import _load_pre_submission_spreads
    quote = tradier._normalize(raw())
    fetch = MagicMock(return_value={'AAPL': quote})
    monkeypatch.setattr(live_quotes, 'fetch_latest_quotes', fetch)
    for loader in (_load_live_spread_snapshots, _load_pre_submission_spreads):
        result = loader(['AAPL'], account_id='default')
        assert result['AAPL'].source == 'tradier_consolidated'
        assert result['AAPL'].effective_spread_bps == pytest.approx(9.9950025)
        assert result['AAPL'].quote_time.tzinfo is not None
    quote['bid_time'] = quote['t'] = (NOW-timedelta(minutes=16)).isoformat()
    assert _load_live_spread_snapshots(['AAPL'], account_id='default') == {}
    assert _load_pre_submission_spreads(['AAPL'], account_id='default') == {}


def test_tradier_can_qualify_alpaca_entry_but_stale_quote_cannot(monkeypatch):
    from execution_engine.broker_adapter import BrokerAdapter
    from execution_engine.config import ExecutionConfig
    from execution_engine.models import IntentRole
    from test_sip_project_policy import intent
    quote = tradier._normalize(raw())
    monkeypatch.setattr('execution_engine.broker_adapter.fetch_latest_quotes', lambda *a, **k: {'AAPL': quote})
    broker = MagicMock()
    broker.submit_order.return_value = dict(id='mock', symbol='AAPL', status='new')
    adapter = BrokerAdapter(broker, ExecutionConfig())
    adapter.submit_intent(intent(IntentRole.ENTRY))
    assert broker.submit_order.call_count == 1
    quote['bid_time'] = quote['t'] = (NOW-timedelta(minutes=16)).isoformat()
    with pytest.raises(Exception, match='consolidée temps réel'):
        adapter.submit_intent(intent(IntentRole.ENTRY))
    assert broker.submit_order.call_count == 1


def test_watcher_keeps_bar_feed_separate_and_checks_tradier_quote(monkeypatch):
    from execution_engine.winner_market import NativeWinnerMarket
    quote = tradier._normalize(raw())
    monkeypatch.setattr(live_quotes, 'fetch_latest_quotes', lambda *a, **k: {'AAPL': quote})
    state = dict(symbol='AAPL', policy={'max_quote_age_seconds': 60})
    snapshot = NativeWinnerMarket(None, 'default').with_quote(state, dict(feed='sip', bars=[]))
    assert snapshot['feed'] == 'sip'
    assert snapshot['quote_provider'] == 'tradier' and snapshot['quote_feed'] == 'consolidated'
    live_quotes.validate_campaign_quote(snapshot, now=NOW, max_age_seconds=60)
    snapshot['ask'] = 90
    with pytest.raises(ValueError, match='différent'):
        live_quotes.validate_campaign_quote(snapshot, now=NOW, max_age_seconds=60)
    snapshot = NativeWinnerMarket(None, 'default').with_quote(state, dict(feed='sip', bars=[]))
    quote['bid_time'] = quote['t'] = (NOW-timedelta(minutes=16)).isoformat()
    with pytest.raises(ValueError):
        live_quotes.validate_campaign_quote(snapshot, now=NOW, max_age_seconds=60)


def test_latest_collection_tradier_map_is_explicit(monkeypatch):
    from dataIntegrityEngine.sync_latest_quotes import _resolve_latest_quotes_fetcher
    monkeypatch.setattr('common.config_loader.load_config', lambda: {'market_data': {'quotes_provider_live': 'tradier'}})
    fetch, name, second = _resolve_latest_quotes_fetcher()
    assert fetch is tradier.fetch_latest_quotes and name == 'tradier' and second is None
