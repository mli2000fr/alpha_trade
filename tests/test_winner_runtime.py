from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine

from common.winner_pyramiding import WinnerPyramidingConfig
from execution_engine.config import ExecutionConfig
from execution_engine.models import ExecutionTarget
from execution_engine.winner_campaign_store import WinnerCampaignStore
from execution_engine.winner_plans import stage_targets
from execution_engine.winner_runtime import WinnerCampaignRuntime


NOW = datetime(2026, 10, 19, 14, 15, tzinfo=UTC)


class Broker:
    def __init__(self):
        self.orders, self.calls = {}, []
        self.fail_post = self.no_fill_time = False
        self.position_quantity, self.price = 0, 101.

    def submit(self, state, intent):
        self.calls.append(intent)
        self.orders[intent.intent_id] = dict(id=intent.intent_id, status='filled',
            client_order_id=intent.submission_key, filled_qty=str(intent.qty),
            filled_avg_price=str(self.price), filled_at=NOW.isoformat(),
            type=intent.order_type, stop_price=intent.stop_price)
        if intent.intent_role == 'entry':
            self.position_quantity += intent.qty
        elif intent.intent_role == 'exit':
            self.position_quantity -= intent.qty
        if self.fail_post:
            self.fail_post = False
            raise TimeoutError('POST accepted, response lost')
        return SimpleNamespace(broker_order_id=intent.intent_id)

    def lookup(self, intent):
        return self.orders.get(intent.intent_id)

    def get(self, identifier):
        return self.orders[identifier]

    def persist(self, *args):
        pass

    def actual_fill_time(self, raw, state):
        if self.no_fill_time:
            raise ValueError('missing actual fill timestamp')
        return datetime.fromisoformat(raw['filled_at'])

    def protect(self, state, lot, parent, *, tp_intent, stop_intent):
        self.orders[stop_intent.intent_id] = dict(id=stop_intent.intent_id, type='stop',
            status='new', filled_qty='0', stop_price=stop_intent.stop_price)
        return None, SimpleNamespace(broker_order_id=stop_intent.intent_id)

    def tighten(self, state, lot, intent):
        assert intent.stop_price >= lot['stop']
        self.orders[intent.intent_id] = dict(id=intent.intent_id, type='stop', status='new',
            filled_qty='0', stop_price=intent.stop_price)
        self.orders[lot['stop_order_id']]['status'] = 'replaced'
        return SimpleNamespace(broker_order_id=intent.intent_id)

    def cancel(self, identifier):
        raw = self.orders[identifier]
        if raw['status'] != 'filled':
            raw['status'] = 'canceled'
        return raw

    def positions(self):
        return [dict(symbol='TEST', side='long', qty=self.position_quantity)] if self.position_quantity else []


def setup(**policy):
    cfg = ExecutionConfig(winner_pyramiding=WinnerPyramidingConfig(enabled=True, **policy))
    store = WinnerCampaignStore(create_engine('sqlite://'))
    target = ExecutionTarget('risk-1', date(2026, 10, 16), 'TEST', 20, 100., .25,
        'Technology', .8, 'native', None, risk_budget_dollars=120., side='long')
    stage_targets(store, [target], cfg, 'exec-1', now=NOW)
    repo = MagicMock()
    repo.acquire_execution_lock.return_value = True
    return cfg, store, repo, Broker()


def market(state, now):
    closes = [98, 100, 101]
    return dict(bars=[dict(timestamp=now-timedelta(minutes=5*(3-i)),
        open=price, high=price, low=price, close=price, session_tag='regular') for i, price in enumerate(closes)],
        prior_session_high=99., ask=101., bid=100.9, available_cash=4000.)


def approve(state, version, quantity, snapshot, now, kind):
    return dict(producer='native_intraday_risk', campaign_id=state['campaign_id'],
        account_id=state['account_id'], broker_mode=state['broker_mode'], state_version=version,
        side='buy', entry_data_qualified=True, realtime_sip_qualified=True, regime_qualified=True,
        config_hash='native', portfolio_hash='snapshot', qualified=True, max_quantity=quantity,
        available_at=now.isoformat(), valid_until=(now+timedelta(seconds=30)).isoformat(),
        limit_price=snapshot['ask'])


def tick(cfg, store, repo, broker, *, now=NOW, source=market, guard=approve):
    return WinnerCampaignRuntime(store, repo, broker, cfg, market=source, risk=guard, now=now).run(store.rows())


def test_watcher_lock_owners_fit_sql_and_are_unique_even_with_identical_clock():
    cfg, store, repo, broker = setup()
    records = store.rows()
    # The account is busy: no risk/order path may run, but each coordinator
    # must use a distinct SQL-compatible owner (never deterministic by time).
    repo.acquire_execution_lock.return_value = False
    for _ in range(2):
        WinnerCampaignRuntime(store, repo, broker, cfg, market=market, risk=approve, now=NOW).run(records)
    owners = [call.kwargs['exec_run_id'] for call in repo.acquire_execution_lock.call_args_list]
    assert len(set(owners)) == 2 and all(len(owner) <= 32 for owner in owners)
    repo.release_execution_lock.assert_not_called()
    assert broker.calls == []


def test_stage_watch_first_buy_protection_restart_no_duplicate():
    cfg, store, repo, broker = setup()
    result = tick(cfg, store, repo, broker)
    assert result['winner_buys_submitted'] == 1
    state = store.rows()[0]['state']
    assert state['lots'][0]['stop_order_id']
    assert state['lots'][0]['remaining'] == 10
    assert state['first_fill_at'] == NOW.isoformat()
    assert state['due_open']
    again = tick(cfg, store, repo, broker)
    assert again['winner_buys_submitted'] == 0
    assert len(broker.calls) == 1
    assert repo.acquire_execution_lock.call_count == repo.release_execution_lock.call_count == 2


def test_lost_post_response_recovered_by_client_id_never_second_buy():
    cfg, store, repo, broker = setup()
    broker.fail_post = True
    result = tick(cfg, store, repo, broker)
    assert result['winner_entries_blocked'] == 1
    assert store.rows()[0]['state']['operations'][0]['status'] == 'RESERVED'
    again = tick(cfg, store, repo, broker)
    assert again['winner_fills_reconciled'] == 1
    assert len(broker.calls) == 1
    assert store.rows()[0]['state']['lots'][0]['stop_order_id']


def test_no_order_found_after_unknown_post_does_not_authorize_retry():
    cfg, store, repo, broker = setup()
    broker.fail_post = True
    tick(cfg, store, repo, broker)
    broker.orders.clear()
    tick(cfg, store, repo, broker)
    assert len(broker.calls) == 1
    assert store.rows()[0]['state']['operations'][0]['status'] == 'UNKNOWN'


def test_disabled_entries_do_not_stop_existing_protection_or_deadline():
    cfg, store, repo, broker = setup()
    tick(cfg, store, repo, broker)
    state = store.rows()[0]['state']
    off = replace(cfg, winner_pyramiding=replace(cfg.winner_pyramiding, enabled=False))
    due = datetime.fromisoformat(state['due_open'])
    result = tick(off, store, repo, broker, now=due+timedelta(minutes=1),
        source=lambda *_: (_ for _ in ()).throw(ValueError('SIP unavailable')))
    assert result['winner_exits_submitted'] == 1
    assert broker.calls[-1].intent_role == 'exit'
    assert broker.calls[-1].qty == 10
    tick(off, store, repo, broker, now=due+timedelta(minutes=2))
    assert store.rows() == []
    assert store.rows(active_only=False)[0]['state']['status'] == 'CLOSED'
    assert len(broker.calls) == 2


def test_missing_fill_timestamp_places_stop_without_inventing_time():
    cfg, store, repo, broker = setup()
    broker.no_fill_time = True
    tick(cfg, store, repo, broker)
    state = store.rows()[0]['state']
    assert state['first_fill_at'] is None
    assert state['manual_review']
    assert len(broker.calls) == 2  # One buy and one emergency stop, not another buy.
    assert broker.calls[-1].intent_role == 'initial_stop'
    tick(cfg, store, repo, broker)
    assert len(broker.calls) == 2


def test_risk_rejection_and_market_403_never_submit():
    cfg, store, repo, broker = setup()
    tick(cfg, store, repo, broker, guard=lambda *a: dict(max_quantity=0, reason='NATIVE_REJECTION'))
    assert not broker.calls
    result = tick(cfg, store, repo, broker,
        source=lambda *_: (_ for _ in ()).throw(ValueError('403 SIP')))
    assert result['winner_entries_blocked'] == 1 and not broker.calls


def test_one_winner_reinforcement_same_deadline_and_combined_frozen_target():
    cfg, store, repo, broker = setup(reinforcement_enabled=True)
    tick(cfg, store, repo, broker)
    due = store.rows()[0]['state']['due_open']
    later = NOW+timedelta(minutes=20)
    broker.price = 107.

    def source(state, now):
        snap = market(state, now)
        for b in snap['bars']:
            b.update(open=107., high=107., low=107., close=107.)
        return snap | {'ask': 107.}

    tick(cfg, store, repo, broker, now=later, source=source)
    state = store.rows()[0]['state']
    assert len(state['lots']) == 2 and sum(l['quantity'] for l in state['lots']) <= state['full_quantity']
    assert state['due_open'] == due and state['add_attempted']
    tick(cfg, store, repo, broker, now=later+timedelta(minutes=5), source=source)
    assert len(broker.calls) == 2


def test_account_lock_blocks_all_broker_calls():
    cfg, store, repo, broker = setup()
    repo.acquire_execution_lock.return_value = False
    result = tick(cfg, store, repo, broker)
    assert result['winner_entries_blocked'] == 1 and not broker.calls
    repo.release_execution_lock.assert_not_called()


def test_rejected_deadline_sell_rearms_stop_and_freezes_without_second_sell():
    cfg, store, repo, broker = setup()
    tick(cfg, store, repo, broker)
    original_submit = broker.submit

    def submit(state, intent):
        if intent.intent_role in ('exit', 'initial_stop'):
            broker.calls.append(intent)
            broker.orders[intent.intent_id] = dict(id=intent.intent_id, type=intent.order_type,
                status='rejected' if intent.intent_role == 'exit' else 'new', filled_qty='0',
                stop_price=intent.stop_price)
            return SimpleNamespace(broker_order_id=intent.intent_id)
        return original_submit(state, intent)

    broker.submit = submit
    due = datetime.fromisoformat(store.rows()[0]['state']['due_open'])
    tick(cfg, store, repo, broker, now=due+timedelta(minutes=1))
    result = tick(cfg, store, repo, broker, now=due+timedelta(minutes=2))
    state = store.rows()[0]['state']
    assert result['winner_failures'] == 1  # visible operator action, not silent success
    assert state['manual_review'] and broker.orders[state['lots'][0]['stop_order_id']]['status'] == 'new'
    assert sum(c.intent_role == 'exit' for c in broker.calls) == 1
    tick(cfg, store, repo, broker, now=due+timedelta(minutes=3))
    assert sum(c.intent_role == 'initial_stop' for c in broker.calls) == 1


def test_guard_state_is_persistent_and_account_mode_scoped():
    cfg, store, _, _ = setup()
    value, version = store.get_guard('default', 'paper')
    assert value is None
    version = store.save_guard('default', 'paper', {'peak': 5000}, version)
    assert store.get_guard('default', 'paper') == ({'peak': 5000}, version)
    assert store.get_guard('default', 'live')[0] is None
    assert store.get_guard('test1', 'paper')[0] is None
    with pytest.raises(RuntimeError):
        store.save_guard('default', 'paper', {'peak': 1000}, version-1)


def test_real_watcher_scan_reaches_native_risk_then_buy_and_stop(monkeypatch):
    from collections import defaultdict
    from execution_engine.protection_watcher import ProtectionTransitionWatcher
    from execution_engine.winner_live_risk import NativeWinnerRisk
    from test_winner_risk import context
    cfg, store, repo, broker = setup()
    repo.engine = store.engine
    watcher = ProtectionTransitionWatcher(repo, lambda *a: broker, lambda *a: cfg)
    monkeypatch.setattr('common.winner_pyramiding.load_winner_pyramiding_config', lambda: cfg.winner_pyramiding)
    monkeypatch.setattr('execution_engine.winner_broker.NativeWinnerBroker', lambda *a: broker)
    monkeypatch.setattr('execution_engine.winner_market.NativeWinnerMarket', lambda *a:
        lambda state, now: market(state, now) | dict(feed='sip', quote_time=now))
    native = NativeWinnerRisk(repo, broker, cfg, context_provider=lambda *a: context(), clock=lambda: NOW)
    monkeypatch.setattr('execution_engine.winner_market.NativeWinnerRisk', lambda *a: native)
    monkeypatch.setattr('execution_engine.winner_runtime.WinnerCampaignRuntime',
        lambda *a, **kw: WinnerCampaignRuntime(*a, **kw, now=NOW))
    results = defaultdict(lambda: dict(watched_items=0, status='COMPLETED'))
    managed = watcher._run_winner_campaigns(results, account_id='default', exec_run_id=None, limit=100)
    assert ('default', 'paper', 'TEST') in managed
    assert results['exec-1']['winner_buys_submitted'] == 1
    assert results['exec-1']['winner_protections_submitted'] == 1
    assert store.rows()[0]['state']['operations'][0]['approval']['producer'] == 'native_intraday_risk'
