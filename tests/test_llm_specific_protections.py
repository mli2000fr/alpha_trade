"""No provider calls, paid searches, live broker or production database."""
from dataclasses import asdict, replace
from datetime import UTC, date, datetime, timedelta
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine

from service.llm_directional.config import FilterConfig, load_filter_config
from service.llm_directional.protections import (
    ProtectionProfile, archived_profile, profile_for_risk, scoped_execution_config,
    safe_trailing_trigger, exit_open, exit_action, apply_scheduled_exit,
    submit_order,
)
from execution_engine.config import ExecutionConfig
from execution_engine.models import OrderIntent, IntentRole, OrderStatus
from execution_engine.order_intents import (
    build_initial_stop_intent, build_take_profit_intent, build_trailing_stop_intent,
    resolve_trailing_activation_price, intent_to_alpaca_payload,
)


def parent():
    return OrderIntent(intent_id='parent', exec_run_id='exec', risk_run_id='risk',
        symbol='ABC', side='buy', qty=10, order_type='market', limit_price=None,
        trail_percent=None, broker_mode='paper', parent_intent_id=None,
        intent_role=IntentRole.ENTRY, idempotency_key='parent', decision_price=100)


@pytest.mark.parametrize('values', [
    {'enabled': 'true'}, {'stop_loss_pct': 0}, {'stop_loss_pct': float('nan')},
    {'stop_loss_pct': True}, {'trailing_stop_pct': 1}, {'trailing_stop_pct': -.1},
    {'exit_session': 1}, {'exit_session': True}, {'exit_session': 21.5},
])
def test_invalid_profile(values):
    with pytest.raises(ValueError):
        ProtectionProfile(**values)


def test_yaml_and_archive_are_frozen():
    cfg = load_filter_config()
    # The deployed values are deliberately editable (e.g. a 15% trailing).
    assert isinstance(cfg.protections, ProtectionProfile)
    assert ProtectionProfile().trailing_stop_pct == .20
    snapshot = cfg.snapshot()
    assert snapshot['protections']['exit_session'] == cfg.protections.exit_session
    restored = FilterConfig(**snapshot)
    assert restored.protections == cfg.protections
    assert archived_profile(json.dumps(snapshot)) == cfg.protections
    assert archived_profile('{}') is None
    snapshot['protections']['enabled'] = False
    assert archived_profile(json.dumps(snapshot)) is None


def test_fill_anchored_sl_and_no_price_tp_even_with_legacy_target():
    cfg = scoped_execution_config(ExecutionConfig(account_id='default'), ProtectionProfile())
    target = SimpleNamespace(stop_price_initial=95, risk_per_share=5, take_profit_price=107)
    stop = build_initial_stop_intent(parent(), 10, 110, cfg, target)
    assert stop.stop_price == 102.3  # Actual fill, not previous close 100.
    assert build_take_profit_intent(parent(), 10, 110, cfg, target) is None
    trail = build_trailing_stop_intent(parent(), 10, 110, cfg, target)
    assert trail.trail_percent == 20
    trigger, mode = resolve_trailing_activation_price(110, cfg, target)
    assert mode == 'gpt_sl_floor'
    assert trigger*.8 >= stop.stop_price-1e-6
    target.trailing_risk_based = True
    target.trailing_stop_pct = .03
    assert build_trailing_stop_intent(parent(), 10, 110, cfg, target).trail_percent == 20


def test_default_unchanged_and_never_loosen_sl():
    cfg = ExecutionConfig()
    assert scoped_execution_config(cfg, None) is cfg
    target = SimpleNamespace(stop_price_initial=95, risk_per_share=5, take_profit_price=106)
    assert build_initial_stop_intent(parent(), 10, 100, cfg, target).stop_price == 95
    assert build_take_profit_intent(parent(), 10, 100, cfg, target).limit_price == 106
    for sl, trail in ((.07,.20),(.20,.07),(.07,.07)):
        p = ProtectionProfile(stop_loss_pct=sl, trailing_stop_pct=trail)
        assert safe_trailing_trigger(100,p)*(1-trail) >= 100*(1-sl)-1e-9


@pytest.mark.parametrize('config', [
    ExecutionConfig(broker_mode='live'), ExecutionConfig(account_id='test1'),
])
def test_profile_never_reaches_other_accounts_or_live(config):
    with pytest.raises(ValueError):
        scoped_execution_config(config, ProtectionProfile())


def test_risk_sizing_uses_seven_percent_not_atr():
    from risk_management.config import RiskConfig
    from risk_management.position_sizer import PositionSizer
    from risk_management.models import PriceInfo
    cfg = RiskConfig(account_equity=7000, risk_per_trade_pct=.01,
        min_position_notional=0, fixed_stop_pct=.07, allow_fractional_shares=False)
    for atr in (.5, 2, 10):
        assert cfg.stop_distance(100, atr) == 7
        assert PositionSizer(cfg).compute(PriceInfo('ABC',100,atr)).proposed_shares == 10
    assert RiskConfig().stop_distance(100,2) == 4


def test_step_commands_ignore_checkbox_without_gpt_and_restore_defaults():
    from ihm.services.pipeline_runner import PipelineLaunchOptions, build_pipeline_command
    base = PipelineLaunchOptions(trade_date='2026-10-09')
    assert build_pipeline_command('execution',replace(base,llm_specific_protections=True)) == build_pipeline_command('execution',base)
    for enabled in (True, False):
        opts = replace(base, llm_filter_enabled=True,llm_specific_protections=enabled,
            llm_filter_run_id='run',ml_predict_batch_id='batch')
        command = build_pipeline_command('execution',opts)
        assert ('--specific-protections' if enabled else '--no-specific-protections') in command
        inner=json.loads(command[command.index('--command-json')+1])
        assert ('--allow-fractional-shares' in inner) is not enabled


def test_changing_checkbox_after_analysis_fails_before_orders():
    from service.llm_directional.pipeline import _check_protection_choice
    run = {'config_json':json.dumps({'protections':asdict(ProtectionProfile())})}
    _check_protection_choice(run,True)
    with pytest.raises(ValueError):
        _check_protection_choice(run,False)


def test_deadline_counts_sessions_not_days_includes_entry_and_holidays():
    # Thanksgiving and Friday half-day; no weekends/holiday in holding count.
    entry=datetime(2026,11,25,15,tzinfo=UTC)
    due=exit_open(entry,ProtectionProfile(exit_session=3))
    assert due == datetime(2026,11,30,14,30,tzinfo=UTC)
    due21=exit_open(datetime(2026,10,9,14,tzinfo=UTC),ProtectionProfile())
    assert due21 == datetime(2026,11,6,14,30,tzinfo=UTC)  # NY DST shift.


def test_moo_window_and_late_recovery():
    due=datetime(2026,11,30,14,30,tzinfo=UTC)
    assert exit_action(due,now=datetime(2026,11,27,23,tzinfo=UTC)) is None
    assert exit_action(due,now=datetime(2026,11,28,0,tzinfo=UTC)) == 'MOO'
    assert exit_action(due,now=due-timedelta(minutes=3)) == 'MOO'
    assert exit_action(due,now=due-timedelta(minutes=1)) is None
    assert exit_action(due,now=due) == 'LATE_MARKET'
    assert exit_action(due,now=datetime(2026,11,30,22,tzinfo=UTC)) is None


def row():
    return dict(opened_at=datetime(2026,10,9,14,tzinfo=UTC),account_id='default',
        broker_mode='paper',symbol='ABC',parent_intent_id='parent',
        parent_exec_run_id='exec',parent_risk_run_id='risk',remaining_qty=10,avg_entry_price=100)


def watcher():
    w=MagicMock()
    w._repo.has_open_exit_order_for_symbol.return_value=False
    w._repo.load_open_child_orders.return_value=[]
    b=w._broker_for.return_value
    b.get_position.return_value={'side':'long','qty':'10'}
    b.submit_intent.return_value=SimpleNamespace(status=OrderStatus.SUBMITTED,broker_order_id='exit')
    return w,b


def test_moo_payload_stable_id_and_existing_exit_is_skipped():
    w,b=watcher()
    p=ProtectionProfile()
    now=datetime(2026,11,6,0,tzinfo=UTC)
    apply_scheduled_exit(w,row(),p,{},now=now)
    intent=b.submit_intent.call_args.args[0]
    payload=intent_to_alpaca_payload(intent,ExecutionConfig())
    assert payload['time_in_force']=='opg'
    assert payload['type']=='market' and payload['side']=='sell'
    apply_scheduled_exit(w,row(),p,{},now=now)
    assert b.submit_intent.call_args.args[0].submission_key==intent.submission_key
    b.submit_intent.reset_mock()
    w._repo.has_open_exit_order_for_symbol.return_value=True
    apply_scheduled_exit(w,row(),p,{},now=now)
    b.submit_intent.assert_not_called()


@pytest.mark.parametrize('status',[OrderStatus.FILLED,OrderStatus.SUBMITTED])
def test_cancel_race_cannot_send_second_sale(status):
    w,b=watcher()
    w._repo.load_open_child_orders.return_value=[SimpleNamespace(broker_order_id='stop',intent_id='s')]
    b.cancel_broker_order.return_value=True
    b.poll_order_status.return_value=SimpleNamespace(status=status)
    if status==OrderStatus.FILLED:
        apply_scheduled_exit(w,row(),ProtectionProfile(),{},now=datetime(2026,11,6,0,tzinfo=UTC))
    else:
        with pytest.raises(RuntimeError):
            apply_scheduled_exit(w,row(),ProtectionProfile(),{},now=datetime(2026,11,6,0,tzinfo=UTC))
    b.submit_intent.assert_not_called()


def test_profile_loaded_by_exact_risk_and_symbol_after_restart():
    from service.llm_directional.repository import metadata, runs
    engine=create_engine('sqlite://')
    metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(runs.insert().values(run_id='llm',trade_date=date(2026,10,7),batch_id='b',
            account_id='default',status='COMPLETED',started_at=datetime(2026,10,7),
            config_json=json.dumps({'protections':asdict(ProtectionProfile())}),input_json='{}',
            input_sha256='h',protocol_version='v',risk_run_id='risk',selected_json='["ABC"]'))
    def load(risk='risk',symbol='ABC',account='default',mode='paper'):
        return profile_for_risk(engine,risk,symbol,account_id=account,broker_mode=mode)
    assert load()==ProtectionProfile()
    assert load(risk='other') is None and load(symbol='DEF') is None
    assert load(account='test1') is None and load(mode='live') is None


def test_unknown_transport_keeps_intent_durable_and_no_looser_fallback():
    from execution_engine.children_submission import submit_children
    from tests.test_protection_watcher import _order
    executor=MagicMock()
    executor._cfg=ExecutionConfig(account_id='default')
    executor._repo.load_llm_protection_profile.return_value=ProtectionProfile()
    executor._repo.has_open_exit_order_for_symbol.return_value=False
    executor._repo.load_open_child_orders.return_value=[]
    executor._broker.submit_intent.side_effect=TimeoutError('unknown broker state')
    fill=replace(_order('parent','entry',status=OrderStatus.FILLED,order_type='market'),
        filled_qty=10,avg_fill_price=100)
    with pytest.raises(RuntimeError,match='SL GPT non armé'):
        submit_children(executor,parent(),fill,'exec',account_state=SimpleNamespace(
            account_type='margin',swing_only=False,daytrade_count=0),metrics={})
    executor._broker.submit_intent.assert_called_once()
    assert executor._broker.submit_intent.call_args.args[0].stop_price==93
    assert executor._repo.upsert_execution_order_request_from_intent.call_args.kwargs['status']==OrderStatus.NEW


def test_children_only_one_fixed_stop_and_duplicate_scan_is_skipped():
    from execution_engine.children_submission import submit_children
    from tests.test_protection_watcher import _order
    executor=MagicMock()
    executor._cfg=ExecutionConfig(account_id='default')
    executor._repo.load_llm_protection_profile.return_value=ProtectionProfile()
    executor._repo.has_open_exit_order_for_symbol.return_value=False
    executor._repo.load_open_child_orders.return_value=[]
    executor._broker.submit_intent.return_value=_order('sl','sl-id',status=OrderStatus.SUBMITTED,order_type='stop')
    fill=replace(_order('parent','entry',status=OrderStatus.FILLED,order_type='market'),
        filled_qty=10,avg_fill_price=110)
    state=SimpleNamespace(account_type='margin',swing_only=True,daytrade_count=0)
    submit_children(executor,parent(),fill,'exec',account_state=state,metrics={})
    intent=executor._broker.submit_intent.call_args.args[0]
    assert intent.intent_role==IntentRole.INITIAL_STOP and intent.stop_price==102.3
    executor._broker.submit_intent.assert_called_once()
    executor._repo.load_open_child_orders.return_value=[SimpleNamespace(order_type='stop')]
    submit_children(executor,parent(),fill,'exec',account_state=state,metrics={})
    executor._broker.submit_intent.assert_called_once()


def test_deadline_survives_disabled_legacy_time_stop_and_profitable_position(monkeypatch):
    from execution_engine.protection_watcher import ProtectionTransitionWatcher
    from execution_engine.config import TimeStopConfig
    import service.llm_directional.protections as module
    repo=MagicMock()
    repo.load_llm_protection_profile.return_value=ProtectionProfile()
    repo.load_time_stop_positions.return_value=[row()]
    repo.has_open_exit_order_for_symbol.return_value=False
    repo.load_open_child_orders.return_value=[]
    broker=MagicMock()
    broker.get_latest_market_price.return_value=150  # Gains do not veto the exit.
    broker.get_position.return_value={'side':'long','qty':'10'}
    broker.submit_intent.return_value=SimpleNamespace(status=OrderStatus.SUBMITTED,broker_order_id='exit')
    w=ProtectionTransitionWatcher(repo,broker_factory=lambda *a:broker,
        config_factory=lambda *a:ExecutionConfig(account_id='default',time_stop=TimeStopConfig(enabled=False)))
    action=module.apply_scheduled_exit
    monkeypatch.setattr(module,'apply_scheduled_exit',lambda w,r,p,m:action(w,r,p,m,
        now=datetime(2026,11,6,0,tzinfo=UTC)))
    metrics={'account_id':'default','broker_mode':'paper'}
    w._apply_time_stop_exits(metrics)
    assert metrics['time_stop_submitted']==1
    assert broker.submit_intent.call_args.args[0].time_in_force=='opg'


def test_handover_rechecks_price_and_restores_original_stop_not_twenty_percent():
    from execution_engine.protection_watcher import ProtectionTransitionWatcher
    from tests.test_protection_watcher import _item, _order
    repo=MagicMock()
    repo.load_llm_protection_profile.return_value=ProtectionProfile()
    repo.load_entry_fill_price.return_value=100
    repo.has_open_exit_order_for_symbol.return_value=False
    repo.load_open_child_orders.return_value=[]
    broker=MagicMock()
    broker.get_position.return_value={'side':'long','qty':'10'}
    broker.poll_order_status.side_effect=[
        _order('sl','sl-id',status=OrderStatus.SUBMITTED,order_type='stop',stop_price=93),
        _order('sl','sl-id',status=OrderStatus.CANCELED,order_type='stop',stop_price=93)]
    broker.cancel_broker_order.return_value=True
    broker.get_latest_market_price.side_effect=[120,110,110]
    broker.submit_intent.return_value=_order('sl-new','sl-new-id',status=OrderStatus.SUBMITTED,order_type='stop',stop_price=93)
    w=ProtectionTransitionWatcher(repo,broker_factory=lambda *a:broker,
        config_factory=lambda *a:ExecutionConfig(account_id='default',swing_only=False))
    item=replace(_item(),account_id='default',fill_price=100,fill_qty=10)
    from collections import defaultdict
    metrics=defaultdict(int)
    w._process_item(item,metrics)
    submitted=broker.submit_intent.call_args.args[0]
    assert submitted.order_type=='stop' and submitted.stop_price==93
    assert metrics['transitioned_items']==0


def test_persistence_failure_prevents_submission():
    repo, broker=MagicMock(),MagicMock()
    repo.upsert_execution_order_request_from_intent.side_effect=RuntimeError('DB unavailable')
    with pytest.raises(RuntimeError):
        submit_order(repo,broker,parent(),account_id='default')
    broker.submit_intent.assert_not_called()


def test_new_profile_blocks_execution_without_running_watcher(monkeypatch):
    from service.llm_directional.pipeline import _check_watcher_ready
    import execution_engine.db_io as module
    repo=MagicMock()
    monkeypatch.setattr(module,'ExecutionRepository',lambda e:repo)
    run={'config_json':json.dumps({'protections':asdict(ProtectionProfile())})}
    repo.is_watcher_healthy.return_value=False
    with pytest.raises(ValueError,match='watcher continu'):
        _check_watcher_ready(None,run)
    repo.is_watcher_healthy.return_value=True
    _check_watcher_ready(None,run)
    repo.is_watcher_healthy.reset_mock()
    _check_watcher_ready(None,{'config_json':'{}'})
    repo.is_watcher_healthy.assert_not_called()


@pytest.mark.parametrize('confirmed_floor',[96,91])
def test_native_trailing_confirmed_floor_never_replaces_sl_with_looser_protection(confirmed_floor):
    from execution_engine.protection_watcher import ProtectionTransitionWatcher
    from tests.test_protection_watcher import _item, _order
    from collections import defaultdict
    repo=MagicMock()
    repo.load_llm_protection_profile.return_value=ProtectionProfile()
    repo.load_entry_fill_price.return_value=100
    repo.has_open_exit_order_for_symbol.return_value=False
    repo.load_open_child_orders.return_value=[]
    broker=MagicMock()
    broker.get_position.return_value={'side':'long','qty':'10'}
    broker.get_latest_market_price.return_value=120
    broker.cancel_broker_order.return_value=True
    broker.poll_order_status.side_effect=[
        _order('sl','sl-id',status=OrderStatus.SUBMITTED,order_type='stop',stop_price=93),
        _order('sl','sl-id',status=OrderStatus.CANCELED,order_type='stop',stop_price=93),
        _order('trail','trail-id',status=OrderStatus.CANCELED,order_type='trailing_stop',stop_price=confirmed_floor)]
    broker.submit_intent.side_effect=[
        _order('trail','trail-id',status=OrderStatus.SUBMITTED,order_type='trailing_stop',stop_price=confirmed_floor,trail_percent=20),
        _order('sl-new','sl-new-id',status=OrderStatus.SUBMITTED,order_type='stop',stop_price=93)]
    w=ProtectionTransitionWatcher(repo,broker_factory=lambda *a:broker,
        config_factory=lambda *a:ExecutionConfig(account_id='default',swing_only=False))
    metrics=defaultdict(int)
    w._process_item(replace(_item(),account_id='default',fill_price=100,fill_qty=10),metrics)
    if confirmed_floor>=93:
        assert metrics['transitioned_items']==1
        broker.submit_intent.assert_called_once()
        assert broker.submit_intent.call_args.args[0].trail_percent==20
    else:
        assert metrics['transitioned_items']==0
        assert broker.submit_intent.call_args.args[0].stop_price==93
        assert broker.cancel_broker_order.call_count==2


def test_risk_targets_have_fixed_sl_and_no_price_tp():
    from tests.test_portfolio_builder import _cfg, _candidates, _prices, _long_predictions
    from risk_management.portfolio_builder import PortfolioBuilder
    cfg=replace(_cfg(),fixed_stop_pct=.07,disable_price_take_profit=True,allow_fractional_shares=False)
    entries=PortfolioBuilder(cfg).build(_candidates(),_prices(),
        predictions=_long_predictions([c.symbol for c in _candidates()]))
    accepted=[e for e in entries if e.approved_shares>0]
    assert accepted
    for entry in accepted:
        assert entry.risk_per_share==pytest.approx(_prices()[entry.symbol].last_close*.07)
        assert entry.take_profit_price is None


def test_partial_stop_fill_caps_trailing_to_remaining_real_position():
    from execution_engine.protection_watcher import ProtectionTransitionWatcher
    from tests.test_protection_watcher import _item, _order
    from collections import defaultdict
    repo,broker=MagicMock(),MagicMock()
    repo.load_llm_protection_profile.return_value=ProtectionProfile()
    repo.load_entry_fill_price.return_value=100
    repo.load_open_child_orders.return_value=[]
    broker.get_position.return_value={'side':'long','qty':'7'}
    broker.get_latest_market_price.return_value=120
    broker.cancel_broker_order.return_value=True
    original=replace(_order('sl','sl-id',status=OrderStatus.PARTIALLY_FILLED,order_type='stop',stop_price=93),qty=10,filled_qty=3)
    broker.poll_order_status.side_effect=[original,replace(original,status=OrderStatus.CANCELED)]
    broker.submit_intent.return_value=replace(_order('trail','trail-id',status=OrderStatus.SUBMITTED,
        order_type='trailing_stop',stop_price=96,trail_percent=20),qty=7)
    w=ProtectionTransitionWatcher(repo,broker_factory=lambda *a:broker,
        config_factory=lambda *a:ExecutionConfig(account_id='default',swing_only=False))
    w._process_item(replace(_item(),account_id='default',fill_price=100,fill_qty=10),defaultdict(int))
    assert broker.submit_intent.call_args.args[0].qty==7
