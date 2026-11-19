"""B PAPER profile: frozen toggles, broker-independent risk and no live orders."""
from dataclasses import replace
from datetime import date, datetime, UTC
from copy import deepcopy

import numpy as np
import pandas as pd
import pytest

from common.q051_paper import (PROFILE_ID, reference, profile_scope, settings,
    pipeline_options, execution_config, risk_config, validate_frozen)

B = 'q051_b_witness_v1'
ANTI = 'q051_b_anti_sl_witness_v1'


def configured(active=True):
    return {'us_pipeline': {'q051_vol20_regime': {'enabled': False},
        'b_anti_sl_reference': dict(enabled=True, apply_anti_sl=active,
            model_batch_id='model-example', artifacts_dir='artifacts/models')}}


def test_yaml_switch_selects_two_distinct_immutable_profiles_and_rejects_ambiguous_routes():
    assert settings(configured())['profile_id'] == ANTI
    assert settings(configured(False))['profile_id'] == B
    bad = configured();bad['us_pipeline']['q051_vol20_regime']['enabled'] = True
    with pytest.raises(ValueError, match='seul profil'):
        settings(bad)
    bad = configured();bad['us_pipeline']['b_anti_sl_reference']['apply_anti_sl'] = 'false'
    with pytest.raises(ValueError, match='booléen'):
        settings(bad)


def test_profile_scope_preserves_old_frozen_campaign_and_resets_after_exception():
    old = reference()
    for pid in (B, ANTI):
        with pytest.raises(RuntimeError):
            with profile_scope(pid):
                assert reference()['profile_id'] == pid
                assert validate_frozen(old) == old
                altered = deepcopy(reference());altered['selection']['long_top_n'] = 5
                with pytest.raises(ValueError, match='figé'):
                    validate_frozen(altered)
                raise RuntimeError('test scope cleanup')
        assert reference() == old


@pytest.mark.parametrize('pid', [B, ANTI])
def test_new_profile_matches_reference_risk_and_winner_but_is_paper_only(pid):
    with profile_scope(pid):
        p = reference();cfg = execution_config('test1');risk = risk_config(4000.)
        assert p['selection']['oracle_fraction'] == .10 and p['selection']['long_top_n'] == 10
        assert p['selection']['apply_anti_sl'] == (pid == ANTI)
        assert not p['portfolio_volatility']['enabled'] and not p['regime']['enabled']
        assert risk.max_gross_exposure == 1 and risk.max_position_weight == .2
        assert risk.risk_per_trade_pct == .0125 and risk.effective_min_notional == 50
        assert not risk.enable_factor_model and not risk.correlation_check_enabled
        assert cfg.winner_pyramiding.confirmation_bars == 0
        assert cfg.winner_pyramiding.stop_loss_pct == .05 and cfg.winner_pyramiding.horizon_sessions == 10
        assert cfg.winner_pyramiding.entry_valid_sessions == 1
        assert cfg.winner_pyramiding.trailing_stop_pct is None and cfg.winner_pyramiding.take_profit_pct is None
        assert not cfg.force_close_on_breaker
        with pytest.raises(ValueError, match='PAPER'):
            replace(cfg, broker_mode='live')


def test_scope_is_serialized_into_commands_for_all_stages_and_accounts(monkeypatch):
    from ihm.services.pipeline_runner import PipelineLaunchOptions, build_pipeline_command
    monkeypatch.setattr('common.q051_paper.require_paper', lambda *a: None)
    for active in [True, False]:
        opts = pipeline_options(PipelineLaunchOptions(execution_mode='paper', account_id='default', trade_date='2026-11-18'),
            configured(active)['us_pipeline'])
        assert opts.q051_profile_id == (ANTI if active else B)
        assert not opts.options_filter_enabled and not opts.llm_filter_enabled
        for account in ['default', 'test1', 'test2']:
            for stage in ['ml_predict', 'risk_management', 'execution']:
                command = build_pipeline_command(stage, replace(opts, account_id=account))
                assert command[command.index('--profile-id') + 1] == opts.q051_profile_id
                assert command[command.index('--run-id') + 1] == opts.q051_run_id
                assert command[command.index('--account') + 1] == account


def candidates():
    # TOP10 of20 Oracle candidates. High anti-SL risk on rank1, rank11 cannot refill.
    f = pd.DataFrame(dict(date=pd.Timestamp('2026-11-17'), symbol=[f'S{i:03}' for i in range(200)],
        proba_extreme=np.linspace(.99, .01, 200), long_probability=np.linspace(.95, .51, 200),
        short_probability=np.nan, long_auc=.7, long_auc_available_date=pd.Timestamp('2025-12-31'),
        long_auc_source='calibration', long_auc_model_sha256='sha', long_model_sha256='sha',
        anti_sl_probability=.02, anti_sl_threshold=.1, anti_sl_model_sha256='slsha',
        anti_sl_manifest_sha256='manifest', anti_sl_available='2025-12-31', anti_sl_status='SCORED',
        anti_sl_features_sha256='features'))
    f.loc[0, 'anti_sl_probability'] = .8
    return f


def test_toggle_changes_only_veto_after_same_top10_without_replacement(monkeypatch):
    from service.q051_paper.pipeline import rank_selection
    monkeypatch.setattr('backtesting.per_symbol_selection.attach_calibration_auc', lambda f, r: f)
    with profile_scope(ANTI):
        on, policy_on = rank_selection(candidates(), None, 200)
    with profile_scope(B):
        off, policy_off = rank_selection(candidates(), None, 200)
    assert policy_on == policy_off and policy_on.oracle_top_n == 20
    assert off[off.selected].symbol.tolist() == [f'S{i:03}' for i in range(10)]
    assert on[on.selected].symbol.tolist() == [f'S{i:03}' for i in range(1, 10)]
    assert not on[on.selected].symbol.eq('S010').any()
    assert on.anti_sl_rejected.sum() == 1 and off.anti_sl_rejected.sum() == 0
    pd.testing.assert_series_equal(on.long_probability, off.long_probability)
    corrupt = candidates();corrupt.loc[0, 'anti_sl_status'] = 'UNTRUSTED'
    with profile_scope(B), pytest.raises(ValueError, match='invalide'):
        rank_selection(corrupt, None, 200)  # Disabling a veto never blesses corrupt evidence.


def test_b_sizing_skips_spy_and_covariance_but_keeps_capital_limits(monkeypatch):
    from service.q051_paper.risk import quantity
    monkeypatch.setattr('service.q051_paper.risk.portfolio_limit', lambda *a, **k: pytest.fail('Covariance disabled'))
    c = dict(equity=4000., available_buying_power=8000., regime_allowed=False, positions=[],
        pending_entries=[], sector_map={}, returns=pd.DataFrame(), signal_day=date(2026,11,17))
    with profile_scope(ANTI):
        assert quantity(symbol='TEST', price=100., proposed=100, context=c)['quantity'] == 8
        c['positions'] = [dict(symbol='OTHER', side='long', quantity=38, mark=100.)]
        assert quantity(symbol='TEST', price=100., proposed=100, context=c)['quantity'] == 2
        c['available_buying_power'] = 0
        assert quantity(symbol='TEST', price=100., proposed=100, context=c)['quantity'] == 0


def test_incomplete_training_blocks_before_loading_or_calling_broker(tmp_path, monkeypatch):
    from service.q051_paper.pipeline import contract
    monkeypatch.setattr('modelFactory.oracle_path.predict.load_contract', lambda *a: pytest.fail('Incomplete model was loaded'))
    with profile_scope(ANTI), pytest.raises(ValueError, match='non terminé'):
        contract('training-batch', str(tmp_path), date(2026,11,18))


def test_future_training_pool_fraction_is_resolved_from_each_model_universe(monkeypatch):
    from modelFactory.oracle_path.directional import settings as direction
    raw = dict(oracle_path=dict(directional=dict(enabled=True, oracle_top_n=20,
        oracle_top_fraction=.1, selected_n=10)))
    monkeypatch.setattr('common.config_loader.load_config', lambda: raw)
    assert direction(universe_size=1790).oracle_top_n == 179
    assert direction(universe_size=200).oracle_top_n == 20
    assert direction(universe_size=1790).selected_n == 10
    assert raw['oracle_path']['directional']['oracle_top_n'] == 20
    assert direction().enabled and direction().oracle_top_n == 20  # UI preview, not a frozen training contract.


def test_capture_and_daily_context_do_not_require_spy_or_sixty_days_for_b(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    from sqlalchemy import create_engine
    from service.q051_paper.risk import capture, complete_context
    monkeypatch.setattr('common.daily_bar_sources.load_daily_close_series',
        lambda *a: pytest.fail('B witness must not load SPY'))
    monkeypatch.setattr('risk_management.db_io.RiskRepository', lambda *a: object())
    fake_repo = SimpleNamespace(engine=SimpleNamespace(dialect=SimpleNamespace(name='mysql'),
        url=SimpleNamespace(database='alpha_trade')))
    broker = MagicMock()
    broker.get_account_snapshot.return_value = dict(status='ACTIVE', equity='4000', regt_buying_power='8000')
    broker.get_all_positions.return_value = []
    broker.list_recent_orders.return_value = []
    now = datetime(2026,11,18,10,tzinfo=UTC)
    with profile_scope(ANTI):
        ctx = capture(fake_repo, broker, 'default', date(2026,11,17), now, clock=lambda: now)
        assert ctx['regime_allowed'] and ctx['available_buying_power'] == 8000
        engine = create_engine('sqlite://')
        with engine.begin() as c:
            c.exec_driver_sql('CREATE TABLE stock_bars_daily(symbol TEXT,date TEXT,close REAL,data_source TEXT)')
            c.exec_driver_sql("INSERT INTO stock_bars_daily VALUES('TEST','2026-11-17',100,'alpaca_sip')")
            c.exec_driver_sql('CREATE TABLE stock_metadata(symbol TEXT,sector TEXT)')
            c.exec_driver_sql("INSERT INTO stock_metadata VALUES('TEST','Tech')")
        result = complete_context(ctx, engine, ['TEST'])
        assert result['reference_closes'] == {'TEST': 100.} and result['returns'].empty


def test_native_watcher_reapproval_uses_frozen_b_profile_even_outside_profile_scope(tmp_path, monkeypatch):
    from unittest.mock import MagicMock
    from tests.test_q051_paper_profile import setup, risk_fixture, context, NOW
    from execution_engine.winner_live_risk import NativeWinnerRisk
    with profile_scope(ANTI):
        _, engine, repo, broker, _, _ = risk_fixture(tmp_path, monkeypatch)
        cfg, store, *_ = setup()
    state = store.rows()[0]['state']
    assert reference()['profile_id'] == PROFILE_ID and state['paper_strategy_profile']['profile_id'] == ANTI
    c = context();c.update(captured_at=NOW, raw_account={'non_marginable_buying_power': '4000'},
        base_symbols=[], regime_allowed=False, returns=pd.DataFrame())
    monkeypatch.setattr('service.q051_paper.risk.capture', lambda *a, **k: deepcopy(c))
    monkeypatch.setattr('common.q051_paper.settings', lambda: dict(enabled=True))
    monkeypatch.setattr('common.q051_paper.require_paper', lambda *a: None)
    monkeypatch.setattr('service.q051_paper.risk.portfolio_limit', lambda *a, **k: pytest.fail('B has no covariance cap'))
    forbidden = MagicMock(side_effect=AssertionError('No generic factor/B4 context for B'))
    decision = NativeWinnerRisk(repo, broker, cfg, context_provider=forbidden, clock=lambda: NOW)(
        state, store.rows()[0]['version'], 8, dict(prior_session=date(2026,10,16)), NOW, 'ENTRY')
    assert decision['max_quantity'] == 8 and decision['order_type'] == 'market'
    assert decision['q051_profile_sha256'] == reference(ANTI)['sha256']
    forbidden.assert_not_called()
    assert reference()['profile_id'] == PROFILE_ID  # No leak into another watcher campaign.


def test_new_profile_winner_runtime_queues_next_open_and_preserves_sl_and_horizon(monkeypatch):
    from tests.test_q051_paper_profile import setup, approval, NOW
    from execution_engine.winner_runtime import WinnerCampaignRuntime
    from common.winner_pyramiding import due_open
    with profile_scope(ANTI):
        cfg, store, repo, broker, _ = setup()
    monkeypatch.setattr('common.q051_paper.settings', lambda: dict(enabled=True))
    source = lambda *_: dict(bars=[], prior_session=date(2026,10,16), ask=None, bid=None)
    first = WinnerCampaignRuntime(store, repo, broker, cfg, market=source, risk=approval, now=NOW).run(store.rows())
    assert first['winner_buys_submitted'] == 1 and broker.calls[0].time_in_force == 'opg'
    stamp = datetime(2026,10,19,13,30,tzinfo=UTC)
    broker.fill(8, 100., stamp=stamp)
    WinnerCampaignRuntime(store, repo, broker, cfg, market=source, risk=approval, now=stamp).run(store.rows())
    state = store.rows()[0]['state']
    assert state['lots'][0]['stop'] == 95. and state['lots'][0]['stop_order_id']
    assert state['due_open'] == due_open(stamp, cfg.winner_pyramiding).isoformat()
    assert state['paper_strategy_profile'] == reference(ANTI)
