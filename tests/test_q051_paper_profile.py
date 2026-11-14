"""Offline production-profile tests: no provider calls, broker orders or real SQL."""
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import create_engine

from common.q051_paper import reference, execution_config, risk_config, entry_window, validate_frozen
from execution_engine.models import ExecutionTarget
from execution_engine.winner_plans import stage_targets
from execution_engine.winner_campaign_store import WinnerCampaignStore
from execution_engine.winner_runtime import WinnerCampaignRuntime
from execution_engine.order_intents import intent_to_alpaca_payload
from service.q051_paper.risk import quantity, regime_allowed


NOW = datetime(2026,10,16,23,5,tzinfo=UTC)


def setup():
    from tests.test_winner_standard_entry import QueuedBroker
    cfg = execution_config('default')
    store = WinnerCampaignStore(create_engine('sqlite://'))
    repo = MagicMock()
    repo.engine = store.engine
    repo.acquire_execution_lock.return_value = True
    target = ExecutionTarget('q-risk', date(2026,10,16), 'TEST', 8, 100., .2, 'Technology',
        .7, 'q051_sl5_cov60_vol20', None, risk_budget_dollars=50., side='long')
    _, plans = stage_targets(store, [target], cfg, 'q-exec', now=NOW)
    return cfg, store, repo, QueuedBroker(), plans


def approval(state, version, proposed, snapshot, now, kind):
    return dict(producer='native_intraday_risk', campaign_id=state['campaign_id'],
        account_id=state['account_id'], broker_mode='paper', state_version=version, side='buy',
        qualified=True, max_quantity=proposed, limit_price=100., config_hash='cfg', portfolio_hash='observed',
        available_at=now.isoformat(), valid_until=(now+timedelta(seconds=30)).isoformat(),
        entry_data_qualified=True, realtime_sip_qualified=False, regime_qualified=True,
        standard_entry_quote_check_enabled=False, price_basis='q051_paper_moo_prior_close',
        reference_price_asof=state['signal_date'], order_type='market', order_limit_price=None,
        q051_profile_sha256=state['paper_strategy_profile']['sha256'])


def test_frozen_profile_matches_reference_and_rejects_live_and_tampering():
    cfg = execution_config('test1')
    assert cfg.winner_pyramiding.confirmation_bars == 0
    assert cfg.winner_pyramiding.initial_position_fraction == 1.
    assert cfg.winner_pyramiding.stop_loss_pct == .05
    assert cfg.winner_pyramiding.trailing_stop_pct is None and cfg.winner_pyramiding.take_profit_pct is None
    assert cfg.winner_pyramiding.horizon_sessions == 10
    risk = risk_config(8000.)
    assert risk.account_equity == 8000. and risk.max_gross_exposure == 1.
    assert risk.max_position_weight == .2 and risk.risk_per_trade_pct == .0125
    assert not risk.enable_factor_model and not risk.correlation_check_enabled and not risk.sector_weight_limit_enabled
    with pytest.raises(ValueError, match='PAPER'):
        replace(cfg, broker_mode='live')
    bad = deepcopy(reference());bad['risk']['max_gross_exposure'] = 2.
    with pytest.raises(ValueError, match='référence'):
        validate_frozen(bad)


def test_q051_risk_never_resolves_capital_presets(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('Le parcours Q051 ne doit pas résoudre un preset capital')
    monkeypatch.setattr('common.capital_presets.resolve_capital_preset_for_equity', forbidden)
    monkeypatch.setattr('risk_management.config.RiskConfig.from_preset', forbidden)
    for equity in (1870., 4000., 55000., 120000.):
        cfg = risk_config(equity)
        assert cfg.account_equity == equity
        assert cfg.risk_per_trade_pct == .0125 and cfg.max_position_weight == .2
        assert cfg.max_gross_exposure == 1. and cfg.effective_min_notional == 50.
        assert cfg.effective_max_positions == 20


@pytest.mark.parametrize('stamp,allowed', [
    ('2026-10-16T21:00Z',False), ('2026-10-16T23:05Z',True),
    ('2026-10-19T13:27Z',True), ('2026-10-19T13:28Z',False),
    ('2026-10-19T13:31Z',False), ('2026-10-20T12:00Z',False)])
def test_only_next_opening_auction_window(stamp, allowed):
    _,store,*_ = setup()
    assert entry_window(store.rows()[0]['state'], pd.Timestamp(stamp).to_pydatetime()) == allowed


def test_actual_winner_runtime_queues_moo_once_and_fill_sets_sl5_open11_without_quotes(monkeypatch):
    monkeypatch.setattr('common.q051_paper.settings',lambda:dict(enabled=True))
    cfg,store,repo,broker,_ = setup()
    source = lambda *_: dict(bars=[], prior_session=date(2026,10,16), ask=None, bid=None)
    run = lambda when: WinnerCampaignRuntime(store,repo,broker,cfg,market=source,risk=approval,now=when).run(store.rows())
    first = run(NOW)
    assert first['winner_buys_submitted'] == 1
    intent = broker.calls[0]
    assert intent.order_type == 'market' and intent.time_in_force == 'opg' and intent.winner_entry_mode == 'q051_moo'
    payload = intent_to_alpaca_payload(intent,cfg)
    assert payload['time_in_force'] == 'opg' and 'limit_price' not in payload and not payload.get('extended_hours')
    assert run(NOW+timedelta(seconds=5))['winner_buys_submitted'] == 0
    broker.fill(8, 105., stamp=datetime(2026,10,19,13,30,tzinfo=UTC))
    run(datetime(2026,10,19,13,30,5,tzinfo=UTC))
    state = store.rows()[0]['state']
    assert state['lots'][0]['entry'] == 105.
    assert state['lots'][0]['stop'] == pytest.approx(99.75)
    assert state['lots'][0]['stop_order_id']
    from common.winner_pyramiding import due_open
    assert state['due_open'] == due_open(datetime(2026,10,19,13,30,tzinfo=UTC),cfg.winner_pyramiding).isoformat()
    # A standard PAPER or LIVE campaign cannot borrow Q051's market exception.
    with pytest.raises(ValueError):
        intent_to_alpaca_payload(intent, replace(cfg,paper_strategy_profile=None))


def context(*,vol=.02,positions=None,pending=None):
    days = pd.bdate_range('2026-07-27',periods=60)
    returns = pd.DataFrame({s:np.resize([-vol,vol],60) for s in ['TEST','HELD']},index=days)
    return dict(equity=4000.,available_buying_power=8000.,regime_allowed=True,
        positions=positions or [],pending_entries=pending or [],returns=returns,
        signal_day=days[-1].date(),sector_map={'TEST':'Technology','HELD':'Technology'})


def test_covariance_and_native_caps_ignore_external_b4_but_never_exceed_1x_or_20pct():
    c = context()
    result = quantity(symbol='TEST',price=100.,proposed=1000,context=c)
    assert result['quantity'] == 8 and result['covariance']['approved_vol'] <= .20
    c = context(positions=[dict(symbol='HELD',side='long',quantity=38,mark=100.)])
    result = quantity(symbol='TEST',price=100.,proposed=1000,context=c)
    assert result['quantity'] <= 2
    c['regime_allowed'] = False
    assert quantity(symbol='TEST',price=100.,proposed=1000,context=c)['quantity'] == 0


def test_covariance_can_reduce_size_and_missing_history_is_not_zero_volatility():
    c = context(vol=.2)
    r = quantity(symbol='TEST',price=100.,proposed=1000,context=c)
    assert 0 < r['quantity'] < 8
    c['returns'].iloc[-1,0] = np.nan
    with pytest.raises(ValueError, match='complete'):
        quantity(symbol='TEST',price=100.,proposed=1000,context=c)
    c = context(positions=[dict(symbol='TEST',side='long',quantity=1,mark=100.)])
    assert quantity(symbol='TEST',price=100.,proposed=1000,context=c)['quantity'] == 0


def test_regime_uses_only_J_and_never_future_prices():
    dates = pd.bdate_range('2025-01-01',periods=210)
    close = pd.Series(100.,index=dates)
    day = dates[199]
    assert regime_allowed(close,day)
    close.loc[dates[200:]] = .01
    assert regime_allowed(close,day)
    close.loc[day] = 90.
    assert not regime_allowed(close,day)
    with pytest.raises(ValueError):
        regime_allowed(close.drop(day),day)


def test_batch_commands_share_selection_and_isolate_accounts(monkeypatch):
    from common.q051_paper import pipeline_options
    from ihm.services.pipeline_runner import PipelineLaunchOptions, build_pipeline_command
    monkeypatch.setattr('common.q051_paper.require_paper',lambda *a:None)
    options = pipeline_options(PipelineLaunchOptions(execution_mode='paper',account_id='default',trade_date='2026-11-09'),
        {'q051_vol20_regime':dict(enabled=True,model_batch_id='model-example')})
    commands = [build_pipeline_command(s,options) for s in ['ml_predict','risk_management','execution']]
    assert all('service.q051_paper.pipeline' in c for c in commands)
    assert all(c[c.index('--run-id')+1] == options.q051_run_id for c in commands)
    other = build_pipeline_command('risk_management',replace(options,account_id='test1'))
    assert other[other.index('--account')+1] == 'test1'
    assert other[other.index('--run-id')+1] == options.q051_run_id
    assert 'service.q051_paper.pipeline' not in build_pipeline_command('ml_predict',replace(options,q051_paper_enabled=False))


def test_shared_covariance_is_the_same_function_used_in_backtest():
    from backtesting.winner_portfolio_budget import portfolio_limit as replay
    from risk_management.portfolio_volatility import portfolio_limit as native
    assert replay is native


@pytest.mark.parametrize('vol',[.005,.02,.20])
def test_native_quantity_matches_replay_sizing_and_covariance_exactly(vol):
    from backtesting.winner_daily_entry import approve_daily_open
    from backtesting.winner_portfolio_budget import PortfolioRiskPolicy
    from common.q051_paper import NoDrawdownController
    cfg,store,*_ = setup()
    state = store.rows()[0]['state']
    c = context(vol=vol)
    when = datetime(2026,10,19,13,30,tzinfo=UTC)
    full_index=pd.DatetimeIndex([c['returns'].index[0]-pd.Timedelta(days=3),*c['returns'].index])
    close=pd.DataFrame({s:np.r_[100.,100.*np.cumprod(1+c['returns'][s].to_numpy())] for s in c['returns']},index=full_index)
    ctx=dict(c, risk_config=risk_config(4000),account_id='default',broker_mode='paper',captured_at=when,
        circuit_breaker=NoDrawdownController(),allocation_scale=1.,volatility_allocation_scale=1.,
        cost_reserve_pct=.0025,return_matrix=c['returns'],entry_data_qualified=True,
        regime_qualified=True,concentration_qualified=True,concentration_allowed=True,
        corporate_actions_qualified=True,breaker_qualified=True,entries_allowed=True)
    expected=PortfolioRiskPolicy(close,target=.20).wrap(approve_daily_open)(state,0,8,
        dict(price_source='CANONICAL_DAILY_OPEN',daily_open=100.,opening_at=when.isoformat()),when,context=ctx)
    actual=quantity(symbol='TEST',price=100.,proposed=8,context=c,risk_budget=50.,full_quantity=8)
    assert actual['quantity'] == expected['max_quantity']


def test_ranking_keeps_top_five_before_thresholds_and_never_refills(monkeypatch):
    from service.q051_paper.pipeline import rank_selection
    # Mirrors the frozen replay: rank inside TOP10%, take TOP5, THEN thresholds.
    frame = pd.DataFrame(dict(date=pd.Timestamp('2026-10-16'),
        symbol=[f'S{i:03}' for i in range(100)], proba_extreme=np.linspace(.99,.01,100),
        long_probability=[.95,.94,.93,.92,.91,.90,.89,.88,.87,.86]+[.99]*90,
        short_probability=np.nan, long_auc=[.49,.7,.7,.7,.7,.99,.99,.99,.99,.99]+[.99]*90,
        long_auc_available_date=pd.Timestamp('2025-12-31'),long_auc_source='calibration',
        long_auc_model_sha256='sha',long_model_sha256='sha'))
    monkeypatch.setattr('backtesting.per_symbol_selection.attach_calibration_auc',lambda f,r:f)
    result,policy = rank_selection(frame,None,100)
    assert policy.oracle_top_n == 10
    assert result.loc[result.selected,'symbol'].tolist() == ['S001','S002','S003','S004']
    assert not result[result.selected].symbol.isin(['S005','S010']).any()


def risk_fixture(tmp_path, monkeypatch, *, invalid_target=False):
    from service.q051_paper import pipeline
    engine = create_engine('sqlite://')
    with engine.begin() as c:
        for sql in [
            'CREATE TABLE risk_decisions(run_id TEXT,account_id TEXT,trade_date DATE,symbol TEXT,decision TEXT,reason TEXT,approved_shares INT)',
            'CREATE TABLE portfolio_targets(run_id TEXT,account_id TEXT,trade_date DATE,symbol TEXT,shares INT CHECK(shares<1))' if invalid_target else
            'CREATE TABLE portfolio_targets(run_id TEXT,account_id TEXT,trade_date DATE,symbol TEXT,shares INT)',
            'CREATE TABLE execution_broker_fills(symbol TEXT,request_id TEXT,filled_qty REAL,avg_fill_price REAL,fill_timestamp DATETIME,fill_id TEXT,account_id TEXT)',
            'CREATE TABLE execution_order_requests(symbol TEXT,request_id TEXT,side TEXT,intent_role TEXT,exec_run_id TEXT)',
            'CREATE TABLE execution_runs(exec_run_id TEXT,broker_mode TEXT)']:
            c.exec_driver_sql(sql)
    repo = MagicMock(engine=engine)
    repo.acquire_execution_lock.return_value = True
    broker = MagicMock()
    broker._client.get_asset.return_value = dict(tradable=True,status='active',marginable=True)
    monkeypatch.setattr(pipeline,'make_broker',lambda *a:(repo,broker,execution_config('default')))
    ctx = context(vol=.005)
    ctx.update(reference_closes={'TEST':100.},base_symbols=[],regime_allowed=True)
    monkeypatch.setattr('service.q051_paper.risk.capture',lambda *a,**k:deepcopy(ctx))
    monkeypatch.setattr('service.q051_paper.risk.complete_context',lambda c,*a:c)
    folder = tmp_path/'selection'
    folder.mkdir()
    (folder/'selection.json').write_text('{}')
    pd.DataFrame([dict(selected=True,symbol='TEST',rank=1,long_probability=.7)]).to_parquet(folder/'selection.parquet')
    selection = dict(run_id='q051-'+'a'*32)
    return pipeline, engine, repo, broker, folder, selection


def test_real_risk_stage_persists_canonical_targets_and_reuses_exact_publication(tmp_path, monkeypatch):
    p,engine,repo,_,folder,selected = risk_fixture(tmp_path,monkeypatch)
    report = p.risk(engine,folder,selected,'default',date(2026,10,16))
    assert report['targets'] == 1 and report['decisions'][0]['shares'] == 8
    assert p.risk(engine,folder,selected,'default',date(2026,10,16))['run_id'] == report['run_id']
    with engine.connect() as c:
        assert c.exec_driver_sql('SELECT COUNT(*) FROM portfolio_targets').scalar() == 1
        assert c.exec_driver_sql('SELECT COUNT(*) FROM risk_decisions').scalar() == 1
    assert repo.release_execution_lock.called
    risk_path = folder/'accounts/default/risk.json'
    bad = __import__('json').loads(risk_path.read_text());bad['targets'] = 99
    risk_path.write_text(__import__('json').dumps(bad))
    with pytest.raises(ValueError,match='incomplet'):
        p.risk(engine,folder,selected,'default',date(2026,10,16))


def test_risk_targets_and_decisions_rollback_together_on_sql_failure(tmp_path, monkeypatch):
    p,engine,_,_,folder,selected = risk_fixture(tmp_path,monkeypatch,invalid_target=True)
    with pytest.raises(Exception, match='CHECK'):
        p.risk(engine,folder,selected,'default',date(2026,10,16))
    with engine.connect() as c:
        assert c.exec_driver_sql('SELECT COUNT(*) FROM risk_decisions').scalar() == 0
    assert not (folder/'accounts/default/risk.json').exists()
    assert (folder/'accounts/default/risk.claim.json').exists()


def test_execution_uses_sealed_exact_risk_and_does_not_submit_twice(tmp_path,monkeypatch):
    p,engine,repo,_,folder,selected = risk_fixture(tmp_path,monkeypatch)
    report = p.risk(engine,folder,selected,'default',date(2026,10,16))
    record = report['decisions'][0]
    target = SimpleNamespace(symbol='TEST',side='long',target_shares=record['shares'],
        entry_price=record['entry_price'],risk_budget_dollars=record['risk_budget_dollars'])
    repo.load_portfolio_targets.return_value = [target]
    monkeypatch.setattr('execution_engine.winner_plans.require_campaign_watcher',lambda *a:None)
    monkeypatch.setattr('execution_engine.winner_plans.stage_targets',lambda *a:([],[dict(symbol='TEST',outcome='PLAN_ARMED')]))
    submit = MagicMock(return_value=dict(winner_buys_submitted=1,requires_reconciliation=False))
    monkeypatch.setattr('execution_engine.winner_standard_entry.submit_standard_plans',submit)
    first = p.execute(engine,folder,selected,'default',date(2026,10,16))
    second = p.execute(engine,folder,selected,'default',date(2026,10,16))
    assert first['exec_run_id'] == second['exec_run_id']
    assert first['submitted'] == 1 and submit.call_count == 1


def test_disabling_profile_stops_only_new_entries_and_keeps_existing_stop_lifecycle(monkeypatch):
    cfg,store,repo,broker,_ = setup()
    monkeypatch.setattr('common.q051_paper.settings',lambda:dict(enabled=False))
    market = MagicMock(side_effect=AssertionError('Disabled admission must not request a price'))
    out = WinnerCampaignRuntime(store,repo,broker,cfg,market=market,risk=approval,now=NOW).run(store.rows())
    assert out['winner_buys_submitted'] == 0
    market.assert_not_called()
    monkeypatch.setattr('common.q051_paper.settings',lambda:dict(enabled=True))
    source=lambda *_:dict(bars=[],prior_session=date(2026,10,16),ask=None,bid=None)
    WinnerCampaignRuntime(store,repo,broker,cfg,market=source,risk=approval,now=NOW).run(store.rows())
    broker.fill(8,100.,stamp=datetime(2026,10,19,13,30,tzinfo=UTC))
    monkeypatch.setattr('common.q051_paper.settings',lambda:dict(enabled=False))
    out=WinnerCampaignRuntime(store,repo,broker,cfg,market=market,risk=approval,
        now=datetime(2026,10,19,13,30,5,tzinfo=UTC)).run(store.rows())
    assert store.rows()[0]['state']['lots'][0]['stop_order_id']
    assert out['winner_buys_submitted'] == 0


def test_obsolete_watcher_refresh_requires_canonical_account_lock(tmp_path, monkeypatch):
    from service.forward_pit import watcher_startup as startup
    process = MagicMock(pid=123)
    process.cmdline.return_value = [str(startup.PROJECT_ROOT/'execution_engine/protection_watcher.py'),
        '--mode','service','--account','test1','--broker-mode','paper']
    monkeypatch.setattr(startup,'find_running_service',lambda a:process)
    def old(p):raise ValueError('processus antérieur à la mise à jour Winner')
    monkeypatch.setattr('execution_engine.winner_plans.require_current_watcher_code',old)
    release = MagicMock()
    monkeypatch.setattr('execution_engine.watcher_lease.release_dead_local_watcher_lease',release)
    repo = MagicMock()
    repo.acquire_execution_lock.return_value = False
    with pytest.raises(RuntimeError,match='opération'):
        startup.restart_outdated_q051_service(repo,'test1',tmp_path)
    process.terminate.assert_not_called()
    repo.acquire_execution_lock.return_value = True
    startup.restart_outdated_q051_service(repo,'test1',tmp_path)
    process.terminate.assert_called_once()
    process.wait.assert_called_once_with(timeout=15)
    release.assert_called_once_with(repo.engine,'test1')
    assert repo.release_execution_lock.called


def test_native_watcher_reapproval_uses_q051_without_generic_factor_or_b4_context(tmp_path,monkeypatch):
    from execution_engine.winner_live_risk import NativeWinnerRisk
    _,engine,repo,broker,_,_ = risk_fixture(tmp_path,monkeypatch)
    cfg,store,_,_,_ = setup()
    state = store.rows()[0]['state']
    ctx = context(vol=.005)
    ctx.update(captured_at=NOW, raw_account={'non_marginable_buying_power':'4000'}, base_symbols=[])
    monkeypatch.setattr('service.q051_paper.risk.capture',lambda *a,**k:deepcopy(ctx))
    monkeypatch.setattr('common.q051_paper.settings',lambda:dict(enabled=True))
    monkeypatch.setattr('common.q051_paper.require_paper',lambda *a:None)
    forbidden = MagicMock(side_effect=AssertionError('Generic B4/factor context must not run'))
    adapter = NativeWinnerRisk(repo,broker,cfg,context_provider=forbidden,clock=lambda:NOW)
    result = adapter(state,store.rows()[0]['version'],8,dict(prior_session=date(2026,10,16)),NOW,'ENTRY')
    assert result['max_quantity'] == 8 and result['order_type'] == 'market'
    assert result['q051_covariance']['approved_vol'] <= .2
    assert result['realtime_sip_qualified'] is False
    forbidden.assert_not_called()
