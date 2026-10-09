"""No API call or broker order: directional selection, risk handoff and exits."""
import json
from dataclasses import replace
from datetime import date, datetime, UTC
from types import SimpleNamespace
from unittest.mock import MagicMock
import pytest

from service.llm_directional.config import FilterConfig, load_filter_config
from service.llm_directional.openai_client import build_request
from service.llm_directional.validation import parse_response, select_symbols
from service.llm_directional.risk_adapter import validate_short_broker
from service.llm_directional.pipeline import _validate_targets
from service.llm_directional.protections import (
    ProtectionProfile, safe_trailing_trigger, scoped_execution_config, apply_scheduled_exit,
)
from execution_engine.config import ExecutionConfig
from execution_engine.order_intents import build_initial_stop_intent, build_trailing_stop_intent, resolve_trailing_activation_price
from execution_engine.models import OrderStatus
from tests.test_llm_directional_filter import response, NOW, isolated
from tests.test_execution_db_io import engine as execution_db
from tests.test_llm_specific_protections import parent, watcher, row


def test_config_and_prompt():
    assert load_filter_config().allow_short is True
    assert FilterConfig().allow_short is False
    with pytest.raises(ValueError):
        FilterConfig(allow_short='true')
    req = build_request({}, FilterConfig(allow_short=True))
    assert req['text']['format']['schema']['properties']['decision']['enum'] == ['LONG', 'SHORT', 'ABSTAIN']
    assert 'SHORT forbidden' in build_request({}, FilterConfig())['instructions']


def test_short_gates_and_shared_total_cap():
    cfg = FilterConfig(allow_short=True, max_selected=1)
    short = parse_response(response(decision='SHORT'), 'ABC', cfg, NOW)
    assert short['eligible']
    assert not parse_response(response(decision='SHORT'), 'ABC', replace(cfg, allow_short=False), NOW)['eligible']
    assert not parse_response(response(decision='SHORT', confidence=.7), 'ABC', cfg, NOW)['eligible']
    items = [dict(short, oracle_rank=2), dict(short, symbol='XYZ', decision='LONG', oracle_rank=1)]
    assert select_symbols(items, cfg) == ['XYZ']  # One TOTAL, not one per side.


@pytest.fixture
def borrow(monkeypatch):
    from service.alpaca.accounts import AccountRegistry
    account = SimpleNamespace(account_id='default', mode='paper', long_only=False)
    monkeypatch.setattr(AccountRegistry, 'get', lambda: SimpleNamespace(resolve=lambda a: account))
    broker = MagicMock()
    broker.get_account.return_value = {'shorting_enabled': True}
    broker.get_asset.return_value = dict(symbol='ABC', status='active', tradable=True,
                                        marginable=True, shortable=True, easy_to_borrow=True)
    return broker, account


def test_etb_read_only_validation(borrow):
    broker, _ = borrow
    assert validate_short_broker(broker, ['ABC'])['ABC']['easy_to_borrow']
    broker.submit_order.assert_not_called()


@pytest.mark.parametrize('field', ['tradable', 'marginable', 'shortable', 'easy_to_borrow'])
def test_borrow_fail_closed(borrow, field):
    broker, _ = borrow
    broker.get_asset.return_value[field] = False
    with pytest.raises(ValueError):
        validate_short_broker(broker, ['ABC'])


def test_account_short_permission_and_transport_fail_closed(borrow):
    broker, account = borrow
    account.long_only = True
    with pytest.raises(ValueError):
        validate_short_broker(broker, ['ABC'])
    account.long_only = False
    broker.get_account.return_value = {}
    with pytest.raises(ValueError):
        validate_short_broker(broker, ['ABC'])
    broker.get_account.return_value = {'shorting_enabled': True}
    broker.get_asset.side_effect = TimeoutError()
    with pytest.raises(TimeoutError):
        validate_short_broker(broker, ['ABC'])


def test_target_direction_and_reductions():
    t = dict(symbol='ABC', side='short', shares=10, account_id='default', trade_date='2026-10-09')
    assert _validate_targets([t], {}, {'ABC': 'short'}, t['trade_date']) == ['ABC']
    for selected, holdings, change in [
        ({'ABC':'long'}, {}, {}), ({'ABC':'short'}, {}, {'shares':1.5}),
        ({'ABC':'short'}, {'ABC':{'side':'long','qty':'10'}}, {}),
        ({}, {}, {}), ({}, {'ABC':{'side':'short','qty':'5'}}, {}),
    ]:
        with pytest.raises(ValueError):
            _validate_targets([dict(t, **change)], holdings, selected, t['trade_date'])
    assert _validate_targets([t], {'ABC':{'side':'short','qty':'20'}}, {}, t['trade_date']) == []
    with pytest.raises(ValueError,match='dupliquées'):
        _validate_targets([t,t],{}, {'ABC':'short'}, t['trade_date'])
    with pytest.raises(ValueError,match='non qualifiée'):
        _validate_targets([t],{'ABC':{'side':'short','qty':'nan'}}, {'ABC':'short'}, t['trade_date'])


def test_short_stop_and_trailing_ceiling():
    p = ProtectionProfile()
    cfg = scoped_execution_config(ExecutionConfig(account_id='default'), p)
    entry = replace(parent(), side='sell')
    stop = build_initial_stop_intent(entry, 10, 100, cfg)
    assert stop.side == 'buy' and stop.stop_price == 107
    trail = build_trailing_stop_intent(entry, 10, 100, cfg)
    assert trail.side == 'buy' and trail.trail_percent == 20
    trigger, _ = resolve_trailing_activation_price(100, cfg, side='sell')
    assert trigger == safe_trailing_trigger(100, p, side='sell')
    assert trigger < 100 and trigger*1.2 <= 107


def test_short_deadline_is_buy_to_cover_and_caps_qty():
    w, broker = watcher()
    broker.get_position.return_value = {'side':'short','qty':'-7'}
    apply_scheduled_exit(w, dict(row(), parent_side='sell'), ProtectionProfile(), {},
                         now=datetime(2026,11,6,0,tzinfo=UTC))
    intent = broker.submit_intent.call_args.args[0]
    assert intent.side == 'buy' and intent.qty == 7 and intent.time_in_force == 'opg'


@pytest.mark.parametrize('status', [OrderStatus.FILLED, OrderStatus.SUBMITTED])
def test_short_cancel_race_no_double_cover(status):
    w, broker = watcher()
    broker.get_position.return_value = {'side':'short','qty':'-10'}
    w._repo.load_open_child_orders.return_value = [SimpleNamespace(broker_order_id='stop',intent_id='s')]
    broker.cancel_broker_order.return_value = True
    broker.poll_order_status.return_value = SimpleNamespace(status=status)
    if status == OrderStatus.FILLED:
        apply_scheduled_exit(w, dict(row(),parent_side='sell'), ProtectionProfile(), {},
                             now=datetime(2026,11,6,0,tzinfo=UTC))
    else:
        with pytest.raises(RuntimeError):
            apply_scheduled_exit(w, dict(row(),parent_side='sell'), ProtectionProfile(), {},
                                 now=datetime(2026,11,6,0,tzinfo=UTC))
    broker.submit_intent.assert_not_called()


def test_mixed_risk_without_fabricated_ml_probabilities():
    from tests.test_oracle_pure_portfolio_policy import setup, DAY
    from risk_management.models import SelectionScore, PriceInfo
    b = setup(short_selling_enabled=True, max_short_positions=2,
              fixed_stop_pct=.07, disable_price_take_profit=True)
    b._regime_snapshot = replace(b._regime_snapshot, allowed_short_entries=True)
    selections = [SelectionScore('UP','Tech',.9,snapshot_date=DAY,side='buy'),
                  SelectionScore('DOWN','Finance',.85,snapshot_date=DAY,side='sell')]
    prices = {c.symbol:PriceInfo(c.symbol,100,2,DAY,DAY) for c in selections}
    entries = b.build(selections,prices,trade_date=DAY,selection_policy='oracle_web_llm_directional')
    assert len(entries) == 2 and all(e.approved_shares > 0 for e in entries)
    assert [e.side for e in entries] == ['buy','sell']
    assert [e.stop_price_initial for e in entries] == [93,107]
    assert all(e.predicted_proba is None and e.take_profit_price is None for e in entries)
    b._regime_snapshot = replace(b._regime_snapshot, allowed_long_entries=False)
    entries = b.build(selections,prices,trade_date=DAY,selection_policy='oracle_web_llm_directional')
    assert len(entries) == 1 and entries[0].side == 'sell'


@pytest.mark.parametrize('ack_stop', [96., 109.])
def test_short_trailing_handover_never_loosens_stop(ack_stop):
    from execution_engine.protection_watcher import ProtectionTransitionWatcher
    from tests.test_protection_watcher import _item, _order
    from collections import defaultdict
    repo, broker = MagicMock(), MagicMock()
    repo.load_llm_protection_profile.return_value = ProtectionProfile()
    repo.load_entry_fill_price.return_value = 100
    repo.load_open_child_orders.return_value = []
    repo.has_open_exit_order_for_symbol.return_value = False
    broker.get_position.return_value = {'side':'short','qty':'-7'}
    broker.get_latest_market_price.return_value = 80
    broker.cancel_broker_order.return_value = True
    stop = replace(_order('s','s-id',status=OrderStatus.PARTIALLY_FILLED,
                         order_type='stop',stop_price=107), side='buy',qty=10,filled_qty=3)
    broker.poll_order_status.side_effect = [stop,replace(stop,status=OrderStatus.CANCELED),
        replace(_order('t','t-id',status=OrderStatus.CANCELED,order_type='trailing_stop',stop_price=ack_stop),side='buy')]
    broker.submit_intent.side_effect = [
        replace(_order('t','t-id',status=OrderStatus.SUBMITTED,order_type='trailing_stop',stop_price=ack_stop),side='buy'),
        replace(_order('s2','s2-id',status=OrderStatus.SUBMITTED,order_type='stop',stop_price=107),side='buy')]
    w = ProtectionTransitionWatcher(repo,broker_factory=lambda *a:broker,
        config_factory=lambda *a:ExecutionConfig(account_id='default',swing_only=False))
    metrics = defaultdict(int)
    w._process_item(replace(_item(),account_id='default',parent_side='sell',fill_price=100,fill_qty=10),metrics)
    if ack_stop <= 107:
        assert metrics['transitioned_items'] == 1
        assert broker.submit_intent.call_args.args[0].order_type == 'trailing_stop'
    else:
        assert metrics['transitioned_items'] == 0
        assert broker.submit_intent.call_args.args[0].stop_price == 107
    assert broker.submit_intent.call_args.args[0].side == 'buy'
    assert broker.submit_intent.call_args.args[0].qty == 7


def test_short_restoration_when_price_rebounds_during_cancel():
    from execution_engine.protection_watcher import ProtectionTransitionWatcher
    from tests.test_protection_watcher import _item, _order
    from collections import defaultdict
    repo, broker = MagicMock(), MagicMock()
    repo.load_llm_protection_profile.return_value = ProtectionProfile()
    repo.load_entry_fill_price.return_value = 100
    repo.load_open_child_orders.return_value = []
    repo.has_open_exit_order_for_symbol.return_value = False
    broker.get_position.return_value = {'side':'short','qty':'-10'}
    broker.get_latest_market_price.side_effect = [80,95,95]
    broker.cancel_broker_order.return_value = True
    stop = replace(_order('s','s-id',status=OrderStatus.SUBMITTED,order_type='stop',stop_price=107),side='buy')
    broker.poll_order_status.side_effect = [stop,replace(stop,status=OrderStatus.CANCELED)]
    broker.submit_intent.return_value = replace(stop,broker_order_id='s2')
    w = ProtectionTransitionWatcher(repo,broker_factory=lambda *a:broker,
        config_factory=lambda *a:ExecutionConfig(account_id='default',swing_only=False))
    metrics = defaultdict(int)
    w._process_item(replace(_item(),account_id='default',parent_side='sell',fill_price=100,fill_qty=10),metrics)
    intent = broker.submit_intent.call_args.args[0]
    assert intent.side == 'buy' and intent.stop_price == 107 and intent.order_type == 'stop'
    assert metrics['transitioned_items'] == 0


def test_sql_watch_item_preserves_parent_side():
    from execution_engine.db_io import ExecutionRepository
    value = dict(source_exec_run_id='e',risk_run_id='r',trade_date=date(2026,10,9),
        account_id='default',broker_mode='paper',symbol='ABC',parent_intent_id='p',
        initial_stop_intent_id='s',initial_stop_broker_order_id='id',fill_qty=10,
        fill_price=100,parent_side='sell')
    assert ExecutionRepository._rows_to_protection_watch_items([value])[0].parent_side == 'sell'


def test_short_persisted_selection_reloads_exact_side(isolated, monkeypatch):
    from service.llm_directional import runner, risk_adapter
    runner.analyze(engine=isolated,batch_id='b',trade_date=date(2026,10,7),
        symbol_source='test',config=FilterConfig(enabled=True,allow_short=True),
        inputs=[dict(symbol='ABC',oracle_rank=1,oracle_score=.9)],
        client=lambda request:response(decision='SHORT'),run_id='short-run',check_account=False)
    monkeypatch.setattr(risk_adapter,'validate_short_broker',lambda *a,**k:{'ABC':{'easy_to_borrow':True}})
    from service.alpaca.trading_client import AlpacaTradingClient
    monkeypatch.setattr(AlpacaTradingClient,'__init__',lambda *a,**k:None)
    candidates=risk_adapter.load_candidates(isolated,'short-run',date(2026,10,7),'default','u',['ABC'])
    assert candidates[0].side == 'short'
    assert candidates[0].p_short == candidates[0].p_side == 0
    assert candidates[0].lineage['borrow_evidence']['easy_to_borrow'] is True


def test_sql_scans_short_lot_unprotected_and_transition(execution_db):
    from sqlalchemy import text
    from execution_engine.db_io import ExecutionRepository
    with execution_db.begin() as conn:
        conn.execute(text("""INSERT INTO execution_runs(exec_run_id,risk_run_id,trade_date,account_id,broker_mode)
            VALUES ('e','r','2026-10-09','default','paper')"""))
        conn.execute(text("""INSERT INTO execution_order_requests(request_id,exec_run_id,account_id,risk_run_id,
            symbol,side,target_qty,order_type,business_key,attempt_no,intent_role,status,decision_price)
            VALUES ('p','e','default','r','ABC','sell',10,'market','p',1,'entry','FILLED',100)"""))
        conn.execute(text("""INSERT INTO execution_broker_fills(fill_id,exec_run_id,account_id,broker_order_id,
            request_id,symbol,filled_qty,avg_fill_price,fill_timestamp)
            VALUES ('f','e','default','bp','p','ABC',10,100,CURRENT_TIMESTAMP)"""))
        conn.execute(text("""INSERT INTO execution_position_lots(lot_id,account_id,symbol,opened_qty,remaining_qty,
            entry_price,opened_at,open_exec_run_id,open_request_id,lot_status)
            VALUES ('l','default','ABC',10,7,100,CURRENT_TIMESTAMP,'e','p','OPEN')"""))
        conn.execute(text("""INSERT INTO broker_account_snapshots(exec_run_id,account_id,broker_mode,snapshot_kind,
            equity,cash,settled_cash,buying_power,daytrade_count)
            VALUES ('e','default','paper','test',4000,4000,4000,4000,0)"""))
        conn.execute(text("""INSERT INTO broker_positions_snapshots(exec_run_id,account_id,symbol,qty,avg_entry_price)
            VALUES ('e','default','ABC',-7,100)"""))
    repo=ExecutionRepository(execution_db)
    lots=repo.load_time_stop_positions(account_id='default')
    assert lots[0]['parent_side']=='sell' and lots[0]['remaining_qty']==7
    parents=repo.load_unprotected_filled_parents(account_id='default')
    assert parents[0]['side']=='sell' and parents[0]['fill_qty']==7
    with execution_db.begin() as conn:
        conn.execute(text("""INSERT INTO execution_order_requests(request_id,exec_run_id,account_id,risk_run_id,
            symbol,side,target_qty,order_type,business_key,attempt_no,intent_role,status,parent_request_id)
            VALUES ('s','e','default','r','ABC','buy',7,'stop','s',1,'initial_stop','SUBMITTED','p')"""))
    assert repo.load_pending_protection_watch_items(account_id='default')[0].parent_side=='sell'


def test_short_requires_updated_watcher_even_without_specific_profile(monkeypatch):
    from service.llm_directional import pipeline
    import execution_engine.db_io as db
    repo = MagicMock()
    repo.is_watcher_healthy.return_value = True
    monkeypatch.setattr(db,'ExecutionRepository',lambda engine:repo)
    check = MagicMock(side_effect=ValueError('Watcher ancien'))
    monkeypatch.setattr(pipeline,'_check_short_watcher_code',check)
    with pytest.raises(ValueError,match='ancien'):
        pipeline._check_watcher_ready(None,{'config_json':json.dumps({'allow_short':True})})
    check.assert_called_once_with(repo)


def test_watcher_old_code_is_blocked(monkeypatch):
    from service.llm_directional.pipeline import _check_short_watcher_code
    import service.forward_pit.watcher_startup as module
    import psutil
    monkeypatch.setattr(module,'healthy_service',lambda *a:True)
    monkeypatch.setattr(psutil,'Process',lambda pid:SimpleNamespace(create_time=lambda:0))
    repo = MagicMock()
    repo.engine.connect.return_value.__enter__.return_value.execute.return_value.scalar_one.return_value = 123
    with pytest.raises(ValueError,match='redémarrer'):
        _check_short_watcher_code(repo)
