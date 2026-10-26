from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import requests

pytestmark = pytest.mark.usefixtures('isolated_winner_config')

from execution_engine.config import ExecutionConfig
from execution_engine.models import IntentRole
from execution_engine.order_intents import build_oco_protection_payload, intent_to_alpaca_payload
from execution_engine.winner_broker import NativeWinnerBroker, make_intent
from service.alpaca.trading_client import AlpacaTradingClient, BrokerApiError


STATE = dict(campaign_id='wp-campaign', risk_run_id='risk-1', exec_run_id='exec-1', symbol='TEST',
    broker_mode='paper', account_id='default', created_at='2026-10-19T14:00:00+00:00')


def bridge():
    repo, broker = MagicMock(), MagicMock()
    repo.load_cumulative_filled_qty.return_value = 0.
    cfg = ExecutionConfig()
    return NativeWinnerBroker(repo, broker, cfg), repo, broker


def test_terminal_protection_cancel_is_observation_not_second_delete():
    adapter, _, broker = bridge()
    adapter.client._request.return_value = dict(id='sl', status='canceled', filled_qty='0')
    assert adapter.cancel('sl')['status'] == 'canceled'
    broker.cancel_broker_order.assert_not_called()


def test_fill_wins_cancel_race_but_unconfirmed_live_leg_is_not_canceled():
    adapter, _, broker = bridge()
    adapter.client._request.side_effect = [dict(id='sl', status='new'), dict(id='sl', status='filled')]
    broker.cancel_broker_order.side_effect = BrokerApiError(422, 'already filled')
    assert adapter.cancel('sl')['status'] == 'filled'
    adapter.client._request.side_effect = [dict(id='sl', status='new'), dict(id='sl', status='new')]
    with pytest.raises(BrokerApiError):
        adapter.cancel('sl')


@pytest.mark.parametrize('mode', ['paper', 'live'])
def test_scoped_ioc_and_moo_allowed_without_relaxing_legacy_orders(mode):
    state = STATE | {'broker_mode': mode}
    cfg = ExecutionConfig(broker_mode=mode)
    buy = make_intent(state, 'entry', quantity=10, price=101, tif='ioc')
    assert intent_to_alpaca_payload(buy, cfg)['time_in_force'] == 'ioc'
    sell = make_intent(state, 'exit', quantity=10, price=101, side='sell', role=IntentRole.EXIT,
        order_type='market', tif='opg')
    assert intent_to_alpaca_payload(sell, cfg)['time_in_force'] == 'opg'
    with pytest.raises(ValueError):
        intent_to_alpaca_payload(replace(buy, winner_campaign_id=None), cfg)
    with pytest.raises(ValueError):
        intent_to_alpaca_payload(replace(buy, side='sell'), cfg)
    with pytest.raises(ValueError):
        intent_to_alpaca_payload(replace(buy, qty=1.5), cfg)


def test_oco_client_id_is_durable_and_matches_take_profit_request():
    parent = make_intent(STATE, 'entry', quantity=10, price=101, tif='ioc')
    tp = make_intent(STATE, 'tp', quantity=10, price=120, role=IntentRole.TAKE_PROFIT, side='sell')
    sl = make_intent(STATE, 'sl', quantity=10, stop=95, role=IntentRole.INITIAL_STOP,
        side='sell', order_type='stop')
    first = build_oco_protection_payload(parent, tp, sl, config=ExecutionConfig())
    second = build_oco_protection_payload(parent, tp, sl, config=ExecutionConfig())
    assert first == second and first['client_order_id'] == tp.submission_key


@pytest.mark.parametrize('method,error', [('POST', requests.Timeout()), ('PATCH', requests.ConnectionError())])
def test_durable_mutation_transport_failure_never_retried(method, error):
    client = object.__new__(AlpacaTradingClient)
    client.base_url, client._session = 'https://offline.invalid', MagicMock()
    client._session.request.side_effect = error
    with pytest.raises(type(error)):
        client._request(method, '/v2/orders', json={'client_order_id': 'wp-stable'})
    assert client._session.request.call_count == 1


@pytest.mark.parametrize('status', [429, 500, 503])
def test_durable_mutation_http_failure_never_retried(status):
    client = object.__new__(AlpacaTradingClient)
    client.base_url, client._session = 'https://offline.invalid', MagicMock()
    client._session.request.return_value.status_code = status
    client._session.request.return_value.text = 'uncertain'
    with pytest.raises(BrokerApiError):
        client._request('POST', '/v2/orders', json={'client_order_id': 'wp-stable'})
    assert client._session.request.call_count == 1


def test_stop_amend_is_patch_not_cancel_submit_and_cannot_loosen():
    adapter, repo, broker = bridge()
    adapter.client._request.return_value = dict(id='old', status='new', stop_price='95')
    adapter.client.replace_order.return_value = dict(id='new', status='new', stop_price='98')
    broker.broker_order_from_api.return_value = SimpleNamespace(status='NEW', stop_price=98.)
    lot = dict(stop_order_id='old')
    intent = make_intent(STATE, 'ratchet', quantity=10, side='sell', role=IntentRole.INITIAL_STOP,
        order_type='stop', stop=98.)
    adapter.tighten(STATE, lot, intent)
    adapter.client.replace_order.assert_called_once()
    adapter.client.cancel_order.assert_not_called()
    broker.submit_intent.assert_not_called()
    with pytest.raises(ValueError, match='cannot loosen'):
        adapter.tighten(STATE, lot, replace(intent, stop_price=94.))


def test_lookup_404_is_absence_but_transport_errors_are_not():
    adapter, _, _ = bridge()
    intent = make_intent(STATE, 'entry', quantity=10, price=101, tif='ioc')
    adapter.client._request.side_effect = BrokerApiError(404, 'absent')
    assert adapter.lookup(intent) is None
    adapter.client._request.side_effect = BrokerApiError(403, 'forbidden')
    with pytest.raises(BrokerApiError):
        adapter.lookup(intent)


def test_canonical_fill_idempotency_and_actual_receipt_time():
    adapter, repo, _ = bridge()
    intent = make_intent(STATE, 'entry', quantity=10, price=101, tif='ioc')
    raw = dict(id='order', filled_qty='10', filled_avg_price='101', filled_at='2026-10-19T14:15:01Z')
    adapter.journal_fill(STATE, intent, raw)
    fill = repo.insert_execution_broker_fill.call_args.args[0]
    assert fill.filled_qty == 10 and fill.fill_timestamp == datetime(2026, 10, 19, 14, 15, 1, tzinfo=UTC)
    repo.load_cumulative_filled_qty.return_value = 10
    adapter.journal_fill(STATE, intent, raw)
    assert repo.insert_execution_broker_fill.call_count == 1


def test_missing_fill_time_never_substitutes_now_or_order_updated_at():
    adapter, _, _ = bridge()
    adapter.client._request.return_value = []
    with pytest.raises(ValueError, match='timestamp unavailable'):
        adapter.actual_fill_time(dict(id='order', updated_at='2026-10-19T14:15:01Z'), STATE)
