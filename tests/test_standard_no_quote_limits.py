"""Bounded DAY entries when quotes are explicitly off; no live submissions."""
from dataclasses import replace
from unittest.mock import MagicMock

import pytest

from execution_engine.winner_broker import NativeWinnerBroker
from execution_engine.winner_plans import reserve_operation
from execution_engine.winner_risk import reapprove_campaign
from execution_engine.winner_runtime import WinnerCampaignRuntime
from execution_engine.winner_live_risk import NativeWinnerRisk
from execution_engine.winner_standard_entry import standard_order_terms, standard_risk_price
from execution_engine.order_intents import intent_to_alpaca_payload
from test_winner_optional_standard_quotes import prepared
from test_winner_standard_entry import setup_standard, QUEUED

pytestmark = pytest.mark.usefixtures('isolated_winner_config')


@pytest.mark.parametrize('reference,expected', [(138.73, 142.89), (226.07, 232.85),
    (100.005, 103.), (.12345, .1271)])
def test_no_quote_limits_never_round_above_frozen_gap(reference, expected):
    parts = setup_standard(standard_entry_quote_check_enabled=False)
    state = parts[1].rows()[0]['state']
    state['target']['entry_price'] = reference
    state['entry_policy']['max_entry_gap_pct'] = .03
    assert standard_order_terms(state, quote_check_enabled=False) == ('limit', expected)
    assert standard_order_terms(state, quote_check_enabled=True) == ('market', None)


def test_original_stricter_limit_is_never_widened():
    parts = setup_standard('limit', standard_entry_quote_check_enabled=False)
    state = parts[1].rows()[0]['state']
    state['entry_policy']['max_entry_gap_pct'] = .03
    assert standard_order_terms(state, quote_check_enabled=False) == ('limit', 99.)
    state['entry_policy']['limit_price_buffer_bps'] = 500
    assert standard_order_terms(state, quote_check_enabled=False) == ('limit', 103.)


def test_zero_gap_uses_existing_frozen_limit_buffer():
    state = setup_standard(standard_entry_quote_check_enabled=False)[1].rows()[0]['state']
    state['entry_policy'].update(max_entry_gap_pct=0., limit_price_buffer_bps=10)
    assert standard_order_terms(state, quote_check_enabled=False) == ('limit', 100.10)


def test_true_quote_control_preserves_market_and_symmetric_gap_check(monkeypatch):
    _, state, snap, ctx = prepared(monkeypatch)
    state['entry_policy']['max_entry_gap_pct'] = .03
    result = reapprove_campaign(state, 0, 10, snap | dict(bid=100., ask=100.1, quote_time=QUEUED),
        QUEUED, 'ENTRY', context=ctx | dict(standard_entry_quote_check_enabled=True))
    assert result['order_type'] == 'market' and result['order_limit_price'] is None
    assert result['realtime_sip_qualified'] and result['realtime_gap_checked']
    with pytest.raises(ValueError, match='gap'):
        standard_risk_price(state, 104., quote_check_enabled=True)


@pytest.mark.parametrize('quantity_or_budget', ['no_cash', 'no_budget'])
def test_price_ceiling_does_not_bypass_sizing(monkeypatch, quantity_or_budget):
    _, state, snap, ctx = prepared(monkeypatch)
    state['entry_policy']['max_entry_gap_pct'] = .03
    if quantity_or_budget == 'no_cash':
        ctx['available_buying_power'] = 1.
    else:
        state['risk_budget'] = .01
    result = reapprove_campaign(state, 0, 10, snap, QUEUED, 'ENTRY', context=ctx)
    assert result['max_quantity'] == 0
    assert result['limit_price'] >= result['order_limit_price'] == 103.


def test_full_native_path_queues_bounded_order_and_relaunch_cannot_duplicate(monkeypatch):
    parts, state, snap, ctx = prepared(monkeypatch, max_entry_gap_pct=.03)
    cfg, store, repo, broker, _ = parts
    native = NativeWinnerRisk(repo, broker, cfg, context_provider=lambda *a: ctx, clock=lambda: QUEUED)
    def tick():
        return WinnerCampaignRuntime(store, repo, broker, cfg, market=lambda *a: snap,
            risk=native, now=QUEUED).run(store.rows())
    assert tick()['winner_buys_submitted'] == 1
    intent = broker.calls[0]
    payload = intent_to_alpaca_payload(intent, cfg)
    assert payload['type'] == 'limit' and float(payload['limit_price']) == 103.
    assert payload['time_in_force'] == 'day' and 'extended_hours' not in payload
    assert intent.qty <= state['initial_quantity']
    assert tick()['winner_buys_submitted'] == 0 and len(broker.calls) == 1


def test_lost_post_reply_is_reconciled_without_sending_limit_twice(monkeypatch):
    parts, state, snap, ctx = prepared(monkeypatch, max_entry_gap_pct=.03)
    cfg, store, repo, broker, _ = parts
    broker.fail_post = True
    native = NativeWinnerRisk(repo, broker, cfg, context_provider=lambda *a: ctx, clock=lambda: QUEUED)
    for _ in range(2):
        WinnerCampaignRuntime(store, repo, broker, cfg, market=lambda *a: snap,
            risk=native, now=QUEUED).run(store.rows())
    assert len(broker.calls) == 1
    assert broker.calls[0].order_type == 'limit' and broker.calls[0].limit_price == 103.
    assert store.rows()[0]['state']['operations'][0]['status'] == 'SUBMITTED'


def test_legacy_campaign_cannot_be_converted_without_explicit_admission():
    state = setup_standard()[1].rows()[0]['state']
    state['policy'].pop('standard_entry_quote_check_enabled')
    with pytest.raises(ValueError, match='Explicit unchecked'):
        standard_order_terms(state, quote_check_enabled=False)


@pytest.mark.parametrize('change', [dict(order_limit_price=104.), dict(order_type='market'), dict(limit_price=98.)])
def test_tampered_approval_cannot_reserve_a_buy(monkeypatch, change):
    parts, state, snap, ctx = prepared(monkeypatch)
    approval = reapprove_campaign(state, 0, 10, snap, QUEUED, 'ENTRY', context=ctx)
    with pytest.raises(ValueError, match='approval required'):
        reserve_operation(parts[1], state, 0, action='ENTRY', quantity=1,
            approval=approval | change, now=QUEUED)
    assert not state['operations']


def test_broker_bridge_rejects_over_cap_before_oms_or_http(monkeypatch):
    parts, state, snap, ctx = prepared(monkeypatch)
    cfg, store, repo, broker, _ = parts
    native = NativeWinnerRisk(repo, broker, cfg, context_provider=lambda *a: ctx, clock=lambda: QUEUED)
    WinnerCampaignRuntime(store, repo, broker, cfg, market=lambda *a: snap, risk=native, now=QUEUED).run(store.rows())
    intent = broker.calls[0]
    port = MagicMock()
    bridge = NativeWinnerBroker(repo, port, cfg)
    for wrong in (replace(intent, limit_price=101.), replace(intent, order_type='market', limit_price=None)):
        with pytest.raises(ValueError, match='bounded frozen terms'):
            bridge.submit(state, wrong)
    repo.upsert_execution_order_request_from_intent.assert_not_called()
    port.submit_intent.assert_not_called()
