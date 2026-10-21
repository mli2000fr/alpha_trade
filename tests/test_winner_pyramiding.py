from copy import deepcopy
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import create_engine

from common.winner_pyramiding import (WinnerPyramidingConfig, add_fill, confirmed_breakout,
    confirmed_winner, due_open, initial_quantities, known_risk, load_winner_pyramiding_config,
    new_campaign, observe_completed_bar, reinforcement_quantity, resolve_bar_exit)
from execution_engine.winner_campaign_store import WinnerCampaignStore
from execution_engine.winner_plans import (next_plan_action, plan_from_target,
    require_runtime_ready, reserve_operation, stage_targets)
from execution_engine.config import ExecutionConfig
from execution_engine.models import ExecutionTarget


def policy(**kw):
    return replace(WinnerPyramidingConfig(enabled=True), **kw)


def campaign(**kw):
    return new_campaign('wp-test', 'TEST', 20, 10, 120., policy(**kw))


def bars(closes, start='2026-10-19T14:00:00+00:00'):
    start = datetime.fromisoformat(start)
    return [dict(timestamp=start+timedelta(minutes=5*i), close=c, session_tag='regular') for i, c in enumerate(closes)]


@pytest.mark.parametrize('kw', [dict(enabled='false'), dict(reinforcement_enabled=1),
    dict(initial_position_fraction=.75), dict(stop_loss_pct=0), dict(trailing_stop_pct=float('nan')),
    dict(horizon_sessions=True), dict(entry_valid_sessions=0), dict(confirmation_bars=1.5)])
def test_strict_config(kw):
    with pytest.raises((ValueError, TypeError)):
        policy(**kw)


def test_default_off_and_fractions():
    assert not load_winner_pyramiding_config({}).enabled
    assert initial_quantities(20, 100, 120, policy()) == (20, 10)
    assert initial_quantities(20, 100, 120, policy(initial_position_fraction=1)) == (20, 20)
    assert initial_quantities(200, 100, 120, policy()) == (21, 10)


def test_breakout_requires_fresh_contiguous_cross_and_completed_bars():
    p = policy()
    b = bars([99, 101, 102])
    now = datetime(2026, 10, 19, 14, 15, tzinfo=UTC)
    assert confirmed_breakout(b, 100, p, now=now)
    assert not confirmed_breakout(b, 100, p, now=now+timedelta(seconds=61))
    assert not confirmed_breakout(b, 100, p, now=now-timedelta(seconds=1))
    assert not confirmed_breakout(bars([101, 102, 103]), 100, p, now=now)
    assert not confirmed_breakout(b[::2], 100, p, now=now)
    # A forming current bar is ignored, never used as completed confirmation.
    assert confirmed_breakout(b+bars([1], start=now.isoformat()), 100, p, now=now)
    b[0]['timestamp'] -= timedelta(days=1)
    assert not confirmed_breakout(b, 100, p, now=now)


def test_official_holding_sessions_and_add_does_not_reset():
    s = campaign(reinforcement_enabled=True)
    stamp = datetime(2026, 10, 19, 14, 0, tzinfo=UTC)
    add_fill(s, parent_id='first', quantity=10, price=100., filled_at=stamp)
    initial_due = s['due_open']
    from common.market_calendar import get_market_calendar
    cal = get_market_calendar('US_EQ', allow_us_weekday_fallback=False)
    sessions = [x for x in cal.sessions(date(2026, 10, 19), date(2026, 12, 10)) if x.is_open]
    assert due_open(stamp, policy()) == sessions[20].open_at_utc
    add_fill(s, parent_id='add', quantity=2, price=105., filled_at=stamp+timedelta(days=1), is_add=True)
    assert s['due_open'] == initial_due
    with pytest.raises(ValueError):
        add_fill(s, parent_id='add', quantity=2, price=105., filled_at=stamp, is_add=True)


def test_reinforcement_is_winner_only_one_attempt_and_residual_risk():
    s = campaign(reinforcement_enabled=True)
    stamp = datetime(2026, 10, 19, 14, 0, tzinfo=UTC)
    add_fill(s, parent_id='first', quantity=10, price=100., filled_at=stamp)
    assert reinforcement_quantity(s, 99, 10000, 100) == 0
    assert reinforcement_quantity(s, 105, 10000, 100) == 10
    assert reinforcement_quantity(s, 105, 120, 100) == 1
    assert known_risk(s, policy().fee) > 50
    assert confirmed_winner(s, bars([105, 106]), now=stamp+timedelta(minutes=10))
    s['realized_losses'] = 120
    assert reinforcement_quantity(s, 105, 10000, 100) == 0
    s['realized_losses'] = 0
    s['add_attempted'] = True
    assert reinforcement_quantity(s, 105, 10000, 100) == 0


def test_trailing_does_not_loosen_or_look_ahead_and_collision_is_adverse():
    lot = dict(entry=100., peak=100., stop=95., tp=120.)
    assert resolve_bar_exit(lot, dict(open=100, high=125, low=94)) == (95., 'STOP', 'INTRABAR')
    assert resolve_bar_exit(lot, dict(open=90, high=125, low=89), at_deadline=True)[0] == 90
    assert resolve_bar_exit(lot, dict(open=100, high=125, low=99), at_deadline=True)[1] == 'HORIZON_OPEN'
    observe_completed_bar(lot, 105, policy())
    assert lot['stop'] == 95
    observe_completed_bar(lot, 130, policy())
    assert lot['stop'] == 110.5
    observe_completed_bar(lot, 115, policy())
    assert lot['stop'] == 110.5


def test_store_account_mode_uniqueness_freeze_cas_and_history():
    store = WinnerCampaignStore(create_engine('sqlite://'))
    assert store.rows() == [] and not store.exists()
    s = campaign()
    assert store.create(s, 'default', 'paper', 'risk-1')
    other = deepcopy(s)
    other['campaign_id'] = 'wp-2'
    assert not store.create(other, 'default', 'paper', 'risk-2')
    assert store.create(other, 'default', 'live', 'risk-2')
    row = store.get('wp-test')
    s['status'] = 'EXPIRED'
    assert store.save(s, row['version']) == 1
    with pytest.raises(RuntimeError, match='concurrently'):
        store.save(s, row['version'])
    assert len(store.rows()) == 1
    assert len(store.rows(active_only=False)) == 2
    assert store.get('wp-test')['state']['policy']['horizon_sessions'] == 20


NOW = datetime(2026, 10, 19, 14, 15, tzinfo=UTC)


def target(**kw):
    values = dict(risk_run_id='risk-1', trade_date=date(2026, 10, 16), symbol='TEST',
        target_shares=20, entry_price=100., target_weight=.25, sector='Technology',
        conviction_score=.8, sizing_method='native', kelly_fraction=None,
        risk_budget_dollars=120., side='long')
    return ExecutionTarget(**(values | kw))


def config(**kw):
    return ExecutionConfig(winner_pyramiding=policy(**kw))


def admitted():
    store = WinnerCampaignStore(create_engine('sqlite://'))
    state = plan_from_target(target(), config(), 'exec-1', now=NOW)
    store.create(state, 'default', 'paper', 'risk-1')
    return store, state


def approval(state, version=0, **kw):
    return dict(producer='native_intraday_risk', campaign_id=state['campaign_id'],
        account_id='default', broker_mode='paper', state_version=version, side='buy',
        config_hash='risk-fingerprint', portfolio_hash='broker-fingerprint',
        qualified=True, max_quantity=10, available_at=NOW.isoformat(),
        valid_until=(NOW+timedelta(seconds=60)).isoformat(),
        entry_data_qualified=True, realtime_sip_qualified=True, regime_qualified=True) | kw


def test_plan_storage_freezes_target_policy_and_rerun_does_not_overwrite():
    store = WinnerCampaignStore(create_engine('sqlite://'))
    remaining, result = stage_targets(store, [target(), target(symbol='SHORT', side='short')],
        config(), 'exec-1', now=NOW)
    assert [t.symbol for t in remaining] == ['SHORT']
    assert result[0]['outcome'] == 'PLAN_ARMED'
    row = store.rows()[0]
    assert row['state']['target']['risk_run_id'] == 'risk-1'
    assert row['state']['policy']['stop_loss_pct'] == .05
    _, result2 = stage_targets(store, [target()], config(stop_loss_pct=.1), 'exec-2', now=NOW)
    assert result2[0]['outcome'] == 'EXISTING_PLAN_NOT_OVERWRITTEN'
    assert store.rows()[0]['state']['exec_run_id'] == 'exec-1'
    assert store.rows()[0]['state']['policy']['stop_loss_pct'] == .05


@pytest.mark.parametrize('kw', [dict(side='short'), dict(risk_budget_dollars=None),
    dict(risk_budget_dollars=float('nan')), dict(target_shares=.5), dict(risk_run_id=''),
    dict(trade_date=date(2026, 10, 17)), dict(trade_date=date(2025, 1, 2))])
def test_invalid_approval_never_staged(kw):
    with pytest.raises(ValueError):
        plan_from_target(target(**kw), config(), 'exec-1', now=NOW)


def test_plan_clock_signals_do_not_authorize_orders_and_off_switch_keeps_deadline():
    _, state = admitted()
    b = bars([99, 101, 102])
    assert next_plan_action(state, b, now=NOW, prior_session_high=100)['action'] == 'ENTRY_SIGNAL'
    assert next_plan_action(state, b, now=NOW, new_entries_enabled=False)['action'] == 'ENTRIES_DISABLED'
    early = datetime.fromisoformat(state['earliest_entry_open'])-timedelta(seconds=1)
    assert next_plan_action(state, [], now=early)['action'] == 'WAIT_ENTRY_SESSION'
    assert next_plan_action(state, [], now=datetime.fromisoformat(state['entry_expires_at']))['action'] == 'EXPIRE_PLAN'
    add_fill(state, parent_id='first', quantity=10, price=100., filled_at=NOW)
    assert next_plan_action(state, [], now=datetime.fromisoformat(state['due_open']),
        new_entries_enabled=False)['action'] == 'EXIT_DUE'


def test_outbox_reserved_before_any_http_and_duplicate_or_stale_is_blocked():
    store, state = admitted()
    version, key = reserve_operation(store, state, 0, action='ENTRY', quantity=10,
        approval=approval(state), now=NOW)
    assert version == 1 and key.endswith('-entry')
    assert store.get(state['campaign_id'])['state']['operations'][0]['status'] == 'RESERVED'
    assert next_plan_action(state, [], now=NOW)['action'] == 'RECONCILE_FIRST'
    with pytest.raises(ValueError, match='reconcile'):
        reserve_operation(store, state, version, action='ENTRY', quantity=10,
            approval=approval(state, version), now=NOW)


@pytest.mark.parametrize('changes', [dict(broker_mode='live'), dict(account_id='other'),
    dict(side='sell'), dict(qualified=False), dict(state_version=1), dict(max_quantity=9),
    dict(entry_data_qualified=False), dict(realtime_sip_qualified=False), dict(regime_qualified=False),
    dict(available_at=(NOW-timedelta(minutes=2)).isoformat()),
    dict(available_at=(NOW+timedelta(seconds=1)).isoformat())])
def test_risk_envelope_fail_closed(changes):
    store, state = admitted()
    with pytest.raises(ValueError, match='risk approval'):
        reserve_operation(store, state, 0, action='ENTRY', quantity=10,
            approval=approval(state, **changes), now=NOW)
    assert store.get(state['campaign_id'])['version'] == 0


def test_unfinished_runtime_cannot_fall_back_to_legacy_execution():
    from unittest.mock import patch
    require_runtime_ready()  # Connected adapters, NOT permission to place orders.
    with patch('execution_engine.winner_plans.RUNTIME_READY', False):
        with pytest.raises(RuntimeError, match='aucun ordre'):
            require_runtime_ready()


@pytest.mark.parametrize('start,now', [
    ('2026-10-19T12:00:00+00:00', '2026-10-19T12:15:00+00:00'),
    ('2026-10-19T14:01:00+00:00', '2026-10-19T14:16:00+00:00'),
    ('2026-10-19T19:45:00+00:00', '2026-10-19T20:00:00+00:00'),
    ('2026-10-17T14:00:00+00:00', '2026-10-17T14:15:00+00:00'),
])
def test_no_premarket_afterhours_weekend_or_off_grid_entry(start, now):
    assert not confirmed_breakout(bars([99, 101, 102], start=start), 100, policy(),
        now=datetime.fromisoformat(now))


@pytest.mark.parametrize('key,value', [('risk_budget', 9999), ('full_quantity', 100),
    ('account_id', 'other'), ('policy', {'enabled': False}), ('signal_date', '2026-10-01')])
def test_frozen_fields_are_enforced_by_storage_not_only_by_ui(key, value):
    store, state = admitted()
    state[key] = value
    with pytest.raises(ValueError, match='Frozen'):
        store.save(state, 0)
    assert store.get(state['campaign_id'])['version'] == 0


def test_filled_campaign_deadline_cannot_reset_and_held_lots_cannot_release_key():
    store, state = admitted()
    add_fill(state, parent_id='initial', quantity=10, price=100., filled_at=NOW)
    version = store.save(state, 0)
    original_due = state['due_open']
    state['due_open'] = '2027-01-01T14:30:00+00:00'
    with pytest.raises(ValueError, match='cannot reset'):
        store.save(state, version)
    state['due_open'] = original_due
    state['status'] = 'CLOSED'
    with pytest.raises(ValueError, match='Held lots'):
        store.save(state, version)


def test_executor_enabled_interlock_prevents_even_a_first_broker_or_target_call():
    from unittest.mock import MagicMock, patch
    from execution_engine.executor import ProductionExecutor
    repo, broker, oco = MagicMock(), MagicMock(), MagicMock()
    with patch('execution_engine.winner_plans.RUNTIME_READY', False):
        result = ProductionExecutor(config(), repo, broker, oco).execute_run('risk-1', date(2026, 10, 16))
    assert result['status'] == 'FAILED'
    broker.submit_intent.assert_not_called()
    repo.acquire_execution_lock.assert_not_called()
    repo.load_portfolio_targets.assert_not_called()


def test_daily_backtest_cannot_silently_bypass_the_intraday_contract():
    import pandas as pd
    from backtesting.simulator import BacktestConfig, BacktestEngine
    cfg = BacktestConfig(start_date=date(2026, 10, 16), end_date=date(2026, 10, 19),
        exec_config=config())
    frame = pd.DataFrame({'TEST': [100., 102.]}, index=pd.to_datetime(['2026-10-16', '2026-10-19']))
    with pytest.raises(ValueError, match='research_assumptions'):
        BacktestEngine(cfg).run(open_df=frame, close=frame, high=frame, low=frame,
            signals_df=pd.DataFrame())


def test_default_execution_configuration_reads_the_yaml_policy():
    from unittest.mock import patch
    with patch('common.config_loader.load_config', return_value={'winner_pyramiding': {'enabled': True}}):
        assert ExecutionConfig().winner_pyramiding.enabled
