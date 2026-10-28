"""Offline zero-confirmation lifecycle; no API calls or real account writes."""
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.usefixtures('isolated_winner_config')
from sqlalchemy import create_engine

from common.winner_pyramiding import WinnerPyramidingConfig, confirmed_breakout, confirmed_winner
from execution_engine.config import ExecutionConfig
from execution_engine.models import ExecutionTarget
from execution_engine.order_intents import intent_to_alpaca_payload
from execution_engine.winner_campaign_store import WinnerCampaignStore
from execution_engine.winner_plans import stage_targets, next_plan_action, reserve_operation
from execution_engine.winner_runtime import WinnerCampaignRuntime
from execution_engine.winner_standard_entry import standard_entry_window, submit_standard_plans
from test_winner_runtime import Broker, approve, NOW


QUEUED = datetime(2026, 10, 16, 21, 0, tzinfo=UTC)


class QueuedBroker(Broker):
    def submit(self, state, intent):
        if intent.side != 'buy':
            return super().submit(state, intent)
        self.calls.append(intent)
        self.orders[intent.intent_id] = dict(id=intent.intent_id, status='accepted',
            filled_qty='0', filled_avg_price=None, type=intent.order_type,
            client_order_id=intent.submission_key)
        if self.fail_post:
            self.fail_post = False
            raise TimeoutError('Accepted DAY order; response lost')
        return SimpleNamespace(broker_order_id=intent.intent_id)

    def fill(self, quantity, price, stamp=NOW, status='filled'):
        intent = self.calls[0]
        raw = self.orders[intent.intent_id]
        self.position_quantity += quantity-int(float(raw['filled_qty']))
        raw.update(status=status, filled_qty=str(quantity), filled_avg_price=str(price),
                   filled_at=stamp.isoformat())

    def protect(self, state, lot, parent, *, tp_intent, stop_intent):
        _, stop = super().protect(state, lot, parent, tp_intent=None, stop_intent=stop_intent)
        if tp_intent:
            self.orders[tp_intent.intent_id] = dict(id=tp_intent.intent_id, type='limit',
                status='new', filled_qty='0', legs=[self.orders[stop_intent.intent_id]])
        return (SimpleNamespace(broker_order_id=tp_intent.intent_id) if tp_intent else None), stop


def setup_standard(order_type='market', **policy):
    cfg = ExecutionConfig(winner_pyramiding=WinnerPyramidingConfig(enabled=True,
        confirmation_bars=0, stop_loss_pct=.07, take_profit_pct=.20, trailing_stop_pct=.15, **policy),
        entry_order_type=order_type, limit_price_buffer_bps=-100)
    store = WinnerCampaignStore(create_engine('sqlite://'))
    target = ExecutionTarget('risk-zero', date(2026, 10, 16), 'TEST', 20, 100., .25,
        'Technology', .8, 'native', None, risk_budget_dollars=200., side='long')
    _, plans = stage_targets(store, [target], cfg, 'exec-zero', now=QUEUED)
    repo = MagicMock()
    repo.engine = store.engine
    repo.acquire_execution_lock.return_value = True
    return cfg, store, repo, QueuedBroker(), plans


def source(state, now):
    return dict(bars=[], ask=101., bid=100.9, feed='sip', quote_time=now)


def tick(parts, now=QUEUED, market=source, risk=approve):
    cfg, store, repo, broker, _ = parts
    return WinnerCampaignRuntime(store, repo, broker, cfg, market=market, risk=risk, now=now).run(store.rows())


@pytest.mark.parametrize('count', [-1, True, 1.5, 13])
def test_zero_validation_is_not_unbounded(count):
    with pytest.raises(ValueError):
        WinnerPyramidingConfig(confirmation_bars=count)


def test_zero_is_separate_from_breakout_and_needs_no_bars():
    parts = setup_standard()
    state = parts[1].rows()[0]['state']
    assert not confirmed_breakout([], None, parts[0].winner_pyramiding, now=QUEUED)
    assert next_plan_action(state, [], now=QUEUED)['action'] == 'ENTRY_SIGNAL'
    result = tick(parts)
    assert result['winner_buys_submitted'] == 1
    intent = parts[3].calls[0]
    assert intent.order_type == 'market' and intent.time_in_force == 'day'
    assert intent.qty == 10 and intent.winner_entry_mode == 'standard'
    payload = intent_to_alpaca_payload(intent, parts[0])
    assert payload['type'] == 'market' and payload['time_in_force'] == 'day'
    assert not payload.get('extended_hours')
    state = parts[1].rows()[0]['state']
    assert state['first_fill_at'] is None and state['due_open'] is None and not state['lots']


@pytest.mark.parametrize('mode', ['paper', 'live'])
def test_standard_day_payload_cannot_authorize_other_roles_or_fractional_orders(mode):
    parts = setup_standard('limit')
    tick(parts)
    intent = replace(parts[3].calls[0], broker_mode=mode)
    cfg = replace(parts[0], broker_mode=mode)
    assert intent.limit_price == 99.  # Same signal-relative -100 bps as standard entry.
    assert intent_to_alpaca_payload(intent, cfg)['limit_price'] == '99.0'
    for changes in [dict(winner_entry_mode=None), dict(winner_campaign_id=None),
                    dict(side='sell'), dict(intent_role='exit'), dict(qty=.5)]:
        with pytest.raises(ValueError):
            intent_to_alpaca_payload(replace(intent, **changes), cfg)


def test_real_fill_not_submission_starts_horizon_and_protects_without_sip():
    parts = setup_standard()
    tick(parts)
    parts[3].fill(10, 110.)  # Market gap is a real fill, never clipped to signal price.
    def offline(*_):
        raise ValueError('SIP refused')
    result = tick(parts, now=NOW, market=offline)
    state = parts[1].rows()[0]['state']
    lot = state['lots'][0]
    assert state['first_fill_at'] == NOW.isoformat()
    assert state['due_open'] == '2026-11-16T14:30:00+00:00'
    assert lot['stop'] == 102.3 and lot['tp'] == 132.
    assert lot['stop_order_id'] and lot['tp_order_id']
    assert result['winner_protections_submitted'] == 1
    assert len(parts[3].calls) == 1


def test_partial_fills_get_separate_protections_without_resetting_due_date():
    parts = setup_standard()
    tick(parts)
    parts[3].fill(4, 100., status='partially_filled')
    tick(parts, now=NOW)
    state = parts[1].rows()[0]['state']
    due = state['due_open']
    assert state['lots'][0]['remaining'] == 4 and state['lots'][0]['stop_order_id']
    parts[3].fill(10, 103., stamp=NOW+timedelta(minutes=5))
    tick(parts, now=NOW+timedelta(minutes=5))
    state = parts[1].rows()[0]['state']
    assert [l['remaining'] for l in state['lots']] == [4, 6]
    assert all(l['stop_order_id'] for l in state['lots'])
    assert state['due_open'] == due and len(parts[3].calls) == 1


def test_ambiguous_day_post_is_reconciled_not_retried():
    parts = setup_standard()
    parts[3].fail_post = True
    tick(parts)
    assert parts[1].rows()[0]['state']['operations'][0]['status'] == 'RESERVED'
    tick(parts, now=QUEUED+timedelta(seconds=5))
    assert len(parts[3].calls) == 1
    parts[3].fill(10, 100.)
    tick(parts, now=NOW)
    assert len(parts[3].calls) == 1 and parts[1].rows()[0]['state']['lots'][0]['stop_order_id']


def test_cancelled_day_order_is_not_replaced_by_a_second_buy():
    parts = setup_standard('limit')
    tick(parts)
    parts[3].orders[parts[3].calls[0].intent_id]['status'] = 'expired'
    tick(parts, now=NOW)
    assert len(parts[3].calls) == 1


def test_off_switch_cancels_queued_remainder_without_removing_partial_fill_protection():
    parts = setup_standard()
    tick(parts)
    parts[3].fill(4, 100., status='partially_filled')
    off = replace(parts[0], winner_pyramiding=replace(parts[0].winner_pyramiding, enabled=False))
    tick((off, *parts[1:]), now=NOW)
    state = parts[1].rows()[0]['state']
    assert parts[3].orders[parts[3].calls[0].intent_id]['status'] == 'canceled'
    assert state['lots'][0]['remaining'] == 4 and state['lots'][0]['stop_order_id']
    assert len(parts[3].calls) == 1


def test_risk_rejection_and_off_switch_do_not_queue_standard_orders():
    parts = setup_standard()
    tick(parts, risk=lambda *a: dict(max_quantity=0, reason='DD_BLOCKED'))
    assert not parts[3].calls
    off = replace(parts[0], winner_pyramiding=replace(parts[0].winner_pyramiding, enabled=False))
    tick((off, *parts[1:]))
    assert not parts[3].calls


def test_frozen_entry_terms_and_scoped_submission_windows():
    cfg, store, repo, broker, plans = setup_standard()
    state = store.rows()[0]['state']
    assert standard_entry_window(state, QUEUED)  # Friday after close.
    assert standard_entry_window(state, datetime(2026, 10, 19, 12, tzinfo=UTC))
    assert not standard_entry_window(state, QUEUED-timedelta(seconds=1))
    assert not standard_entry_window(state, datetime.fromisoformat(state['entry_expires_at']))
    state['entry_policy']['order_type'] = 'limit'
    with pytest.raises(ValueError, match='Frozen campaign field'):
        store.save(state, 0)
    stage_targets(store, [ExecutionTarget(**(store.rows()[0]['state']['target'] | {
        'trade_date': date(2026, 10, 16)}))], replace(cfg, entry_order_type='limit'), 'exec-later', now=QUEUED)
    assert store.rows()[0]['state']['entry_policy']['order_type'] == 'market'


@pytest.mark.parametrize('window,postclose,preopen', [('both', True, True),
    ('post_close', True, False), ('pre_open', False, True)])
def test_zero_respects_frozen_standard_submission_window(window, postclose, preopen):
    parts = setup_standard()
    state = parts[1].rows()[0]['state']
    state['entry_policy']['submission_window'] = window
    assert standard_entry_window(state, QUEUED) is postclose
    assert standard_entry_window(state, datetime(2026, 10, 19, 12, tzinfo=UTC)) is preopen


def test_native_standard_risk_keeps_sip_and_budget_checks_and_reserves_higher_limit():
    from execution_engine.winner_risk import reapprove_campaign
    from test_winner_risk import context
    parts = setup_standard('limit')
    state = parts[1].rows()[0]['state']
    state['entry_policy']['limit_price_buffer_bps'] = 1000
    snapshot = source(state, NOW)
    approved = reapprove_campaign(state, 0, 10, snapshot, NOW, 'ENTRY', context=context())
    assert approved['limit_price'] == 110. and 0 < approved['max_quantity'] <= 10
    for change in (dict(feed='iex'), dict(quote_error='403 SIP'),
                   dict(quote_time=NOW-timedelta(seconds=61))):
        with pytest.raises(ValueError):
            reapprove_campaign(state, 0, 10, snapshot | change, NOW, 'ENTRY', context=context())
    state['entry_policy']['max_entry_gap_pct'] = .005
    with pytest.raises(ValueError, match='gap'):
        reapprove_campaign(state, 0, 10, snapshot, NOW, 'ENTRY', context=context())


def test_standard_step12_submission_uses_owned_lock_and_does_not_repeat_existing_plan(monkeypatch):
    parts = setup_standard()
    cfg, store, repo, broker, plans = parts
    monkeypatch.setattr('execution_engine.winner_broker.NativeWinnerBroker', lambda *a: broker)
    monkeypatch.setattr('execution_engine.winner_market.NativeWinnerMarket', lambda *a: source)
    monkeypatch.setattr('execution_engine.winner_live_risk.NativeWinnerRisk', lambda *a: approve)
    monkeypatch.setattr('execution_engine.winner_runtime.WinnerCampaignRuntime',
        lambda *a, **kw: WinnerCampaignRuntime(*a, **kw, now=QUEUED))
    result = submit_standard_plans(store, repo, broker, cfg, plans)
    assert result['winner_buys_submitted'] == 1
    assert not result['requires_reconciliation']
    repo.acquire_execution_lock.assert_not_called()
    repo.release_execution_lock.assert_not_called()
    submit_standard_plans(store, repo, broker, cfg, plans)
    assert len(broker.calls) == 1


def test_standard_step12_unknown_post_is_not_reported_as_success(monkeypatch):
    parts = setup_standard()
    cfg, store, repo, broker, plans = parts
    broker.fail_post = True
    monkeypatch.setattr('execution_engine.winner_broker.NativeWinnerBroker', lambda *a: broker)
    monkeypatch.setattr('execution_engine.winner_market.NativeWinnerMarket', lambda *a: source)
    monkeypatch.setattr('execution_engine.winner_live_risk.NativeWinnerRisk', lambda *a: approve)
    monkeypatch.setattr('execution_engine.winner_runtime.WinnerCampaignRuntime',
        lambda *a, **kw: WinnerCampaignRuntime(*a, **kw, now=QUEUED))
    result = submit_standard_plans(store, repo, broker, cfg, plans)
    assert result['requires_reconciliation']
    assert result['standard_orders'][0]['status'] == 'RESERVED'
    assert len(broker.calls) == 1


@pytest.mark.parametrize('frozen,current', [(0, 2), (2, 0)])
def test_changing_current_confirmation_does_not_rewrite_existing_campaign(frozen, current):
    from test_winner_runtime import setup, market
    if frozen == 0:
        parts = setup_standard()
        cfg, store, repo, broker, plans = parts
        now, feed = QUEUED, source
    else:
        cfg, store, repo, broker = setup()
        now, feed = NOW, market
    cfg = replace(cfg, winner_pyramiding=replace(cfg.winner_pyramiding, confirmation_bars=current))
    WinnerCampaignRuntime(store, repo, broker, cfg, market=feed, risk=approve, now=now).run(store.rows())
    assert broker.calls[0].time_in_force == ('day' if frozen == 0 else 'ioc')
    assert store.rows()[0]['state']['policy']['confirmation_bars'] == frozen


def test_zero_does_not_turn_reinforcement_into_an_empty_confirmation():
    from common.winner_pyramiding import add_fill
    parts = setup_standard(reinforcement_enabled=True)
    state = parts[1].rows()[0]['state']
    add_fill(state, parent_id='first', quantity=10, price=100., filled_at=NOW)
    assert not confirmed_winner(state, [], now=NOW)
    assert confirmed_winner(state, [dict(timestamp=NOW, close=106., session_tag='regular')],
                            now=NOW+timedelta(minutes=5))


def test_zero_initial_market_source_does_not_download_breakout_bars(monkeypatch):
    from execution_engine.winner_market import NativeWinnerMarket
    parts = setup_standard()
    monkeypatch.setattr('service.alpaca.intraday_bars.fetch_intraday',
                        lambda *a, **kw: pytest.fail('No initial 5m confirmation required'))
    monkeypatch.setattr('service.alpaca.clientAlpaca.fetch_latest_quotes', lambda *a, **kw:
        {'TEST': dict(ap=101, bp=100.9, **{'as': 10, 'bs': 10}, t=datetime.now(UTC).isoformat())})
    snapshot = NativeWinnerMarket(None, 'default')(parts[1].rows()[0]['state'], QUEUED)
    assert snapshot['bars'] == [] and snapshot['feed'] == 'sip' and snapshot['ask'] == 101
