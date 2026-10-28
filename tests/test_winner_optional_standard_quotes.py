"""Standard DAY submission without quotes remains a native-risk decision."""
from copy import deepcopy
from dataclasses import replace
from datetime import date
from unittest.mock import MagicMock

import pytest

from common.winner_pyramiding import WinnerPyramidingConfig, load_winner_pyramiding_config
from execution_engine.winner_market import NativeWinnerMarket
from execution_engine.winner_risk import reapprove_campaign
from execution_engine.winner_live_risk import NativeWinnerRisk
from execution_engine.winner_runtime import WinnerCampaignRuntime
from execution_engine.winner_standard_entry import standard_quote_check_required
from test_winner_standard_entry import setup_standard, QUEUED
from test_winner_risk import context

pytestmark = pytest.mark.usefixtures('isolated_winner_config')


def prepared(monkeypatch, *, max_entry_gap_pct=0.):
    parts = setup_standard(standard_entry_quote_check_enabled=False, max_entry_gap_pct=max_entry_gap_pct)
    cfg, store, repo, broker, plans = parts
    monkeypatch.setattr('service.market.live_quotes.fetch_latest_quotes',
        lambda *a, **kw: pytest.fail('No quote for explicitly unchecked standard entry'))
    monkeypatch.setattr('service.alpaca.intraday_bars.fetch_intraday',
        lambda *a, **kw: pytest.fail('No confirmation bars for standard entry'))
    state = store.rows()[0]['state']
    snapshot = NativeWinnerMarket(None, 'default', cfg)(state, QUEUED)
    ctx = context() | dict(captured_at=QUEUED, standard_entry_quote_check_enabled=False,
        reference_price=100., reference_price_asof=date(2026, 10, 16))
    return parts, state, snapshot, ctx


@pytest.mark.parametrize('invalid', ['false', 0, None])
def test_quote_flag_requires_boolean(invalid):
    with pytest.raises(ValueError, match='boolean'):
        WinnerPyramidingConfig(standard_entry_quote_check_enabled=invalid)


def test_yaml_default_preserved_and_explicit_opt_out():
    assert load_winner_pyramiding_config({}).standard_entry_quote_check_enabled is True
    assert load_winner_pyramiding_config({'winner_pyramiding':
        {'standard_entry_quote_check_enabled': False}}).standard_entry_quote_check_enabled is False


def test_standard_entry_native_risk_then_durable_submission_without_fake_quotes(monkeypatch):
    parts, state, snapshot, ctx = prepared(monkeypatch)
    cfg, store, repo, broker, _ = parts
    assert snapshot['ask'] is None and snapshot['bid'] is None and 'quote_time' not in snapshot
    native = NativeWinnerRisk(repo, broker, cfg, context_provider=lambda *a: ctx, clock=lambda: QUEUED)
    result = WinnerCampaignRuntime(store, repo, broker, cfg, market=lambda *a: snapshot,
        risk=native, now=QUEUED).run(store.rows())
    assert result['winner_buys_submitted'] == 1
    assert broker.calls[0].time_in_force == 'day' and broker.calls[0].order_type == 'limit'
    assert broker.calls[0].limit_price == 99.
    saved = store.rows()[0]['state']
    approval = saved['operations'][0]['approval']
    assert approval['qualified'] and approval['realtime_sip_qualified'] is False
    assert approval['standard_entry_quote_check_enabled'] is False
    assert approval['price_basis'] == 'bounded_standard_limit'
    assert approval['realtime_gap_checked'] is False
    assert not saved['lots']  # Queuing is not a fill; no invented entry price.


@pytest.mark.parametrize('changes', [dict(entries_allowed=False), dict(concentration_allowed=False),
    dict(breaker_qualified=False), dict(entry_data_qualified=False), dict(regime_qualified=False),
    dict(reference_price=float('nan')), dict(reference_price_asof=date(2026, 10, 15))])
def test_unchecked_quotes_do_not_relax_other_native_risk(monkeypatch, changes):
    _, state, snap, ctx = prepared(monkeypatch)
    with pytest.raises(ValueError):
        reapprove_campaign(state, 0, 10, snap, QUEUED, 'ENTRY', context=ctx | changes)


def test_unchecked_quotes_do_not_invent_capital(monkeypatch):
    _, state, snap, ctx = prepared(monkeypatch)
    approval = reapprove_campaign(state, 0, 10, snap, QUEUED, 'ENTRY',
        context=ctx | dict(available_buying_power=1.))
    assert approval['max_quantity'] == 0


def test_native_context_cannot_disable_confirmed_or_reinforcement_quotes(monkeypatch):
    parts, state, snap, ctx = prepared(monkeypatch)
    assert standard_quote_check_required(state, config=parts[0], kind='ADD') is True
    with pytest.raises(ValueError, match='only permits standard'):
        reapprove_campaign(state, 0, 10, snap, QUEUED, 'ADD', context=ctx)
    state['policy']['confirmation_bars'] = 2
    assert standard_quote_check_required(state, config=parts[0]) is True
    with pytest.raises(ValueError, match='only permits standard'):
        reapprove_campaign(state, 0, 10, snap, QUEUED, 'ENTRY', context=ctx)


def test_admitted_legacy_policy_and_later_tightening_remain_checked(monkeypatch):
    parts, state, _, _ = prepared(monkeypatch)
    checked = replace(parts[0], winner_pyramiding=replace(parts[0].winner_pyramiding,
        standard_entry_quote_check_enabled=True))
    assert standard_quote_check_required(state, config=checked)
    old = deepcopy(state)
    old['policy'].pop('standard_entry_quote_check_enabled')
    assert standard_quote_check_required(old, config=parts[0])


def test_no_quote_mode_cannot_claim_to_enforce_current_gap(monkeypatch):
    _, state, snap, ctx = prepared(monkeypatch)
    state['entry_policy']['max_entry_gap_pct'] = .05
    result = reapprove_campaign(state, 0, 10, snap, QUEUED, 'ENTRY', context=ctx)
    assert result['realtime_gap_checked'] is False
    assert result['order_type'] == 'limit' and result['order_limit_price'] == 105.
    assert result['limit_price'] >= 105.  # Risk reserves at least the maximum purchase price.


def test_broker_skip_is_only_for_explicit_standard_winner_entry(monkeypatch):
    from execution_engine.broker_adapter import BrokerAdapter
    from service.alpaca.trading_client import BrokerApiError
    from test_winner_standard_entry import tick
    parts = setup_standard(standard_entry_quote_check_enabled=False)
    tick(parts)
    market_intent = parts[3].calls[0]
    intent = replace(market_intent, order_type='limit', limit_price=99.)
    calls = MagicMock(side_effect=RuntimeError('SIP refused'))
    monkeypatch.setattr('execution_engine.broker_adapter.fetch_latest_quotes', calls)
    client = MagicMock()
    client.submit_order.return_value = dict(id='queued', status='accepted', qty='10')
    adapter = BrokerAdapter(client, parts[0])
    with pytest.raises(BrokerApiError, match='limite'):
        adapter.submit_intent(market_intent)
    adapter.submit_intent(intent)
    calls.assert_not_called()
    checked = BrokerAdapter(client, replace(parts[0], winner_pyramiding=replace(
        parts[0].winner_pyramiding, standard_entry_quote_check_enabled=True)))
    with pytest.raises(BrokerApiError):
        checked.submit_intent(intent)
    assert client.submit_order.call_count == 1
