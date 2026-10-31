"""Editable replay controls must change execution, never production settings."""
from dataclasses import asdict, replace
import json

import pytest

from backtesting.winner_settings import (risk_overrides, apply_risk_settings, apply_policy_settings,
                                         production_risk_defaults)
from common.winner_pyramiding import WinnerPyramidingConfig
from risk_management.config import RiskConfig


def test_production_breaker_defaults_are_used_and_preserve_other_guards():
    base=RiskConfig(account_equity=4000.,max_portfolio_beta=3.5)
    risk=production_risk_defaults(base,{'risk_management':dict(prod_force_close_on_breaker=True,
        prod_force_close_pct=.5,backtest_force_close_pct=1.)})
    assert risk.force_close_on_breaker and risk.force_close_pct==.5
    assert not base.force_close_on_breaker and risk.max_portfolio_beta==3.5
    local=apply_risk_settings(risk,dict(force_close_pct=1.,min_position_notional=35.,risk_per_trade_pct=.02))
    assert local.force_close_pct==1. and local.min_position_notional==35.
    assert risk.force_close_pct==.5 and local.max_portfolio_beta==3.5


@pytest.mark.parametrize('value',[{'quote_spread_check_enabled':False},{'account_equity':1.},
    {'risk_per_trade_pct':0.},{'force_close_on_breaker':'false'}, {'max_position_weight':float('nan')},
    {'correlation_lookback_days':True}, {'min_position_notional':None},[]])
def test_unsupported_or_invalid_overrides_fail_before_execution(value):
    with pytest.raises(ValueError):
        risk_overrides(value)


def test_policy_edit_keeps_source_immutable_and_rejects_unsupported_mode_switches():
    base=WinnerPyramidingConfig(enabled=True,stop_loss_pct=.05,horizon_sessions=10,market_data_delay_seconds=930)
    before=asdict(base)
    local=apply_policy_settings(base,dict(stop_loss_pct=.07,horizon_sessions=15,take_profit_pct=.20))
    assert local.stop_loss_pct==.07 and local.horizon_sessions==15 and local.take_profit_pct==.20
    assert asdict(base)==before and local.market_data_delay_seconds==930
    for value in [dict(enabled=False),dict(stop_loss_pct=0),dict(market_data_delay_seconds=100)]:
        with pytest.raises(ValueError):
            apply_policy_settings(base,value)


def test_command_parser_receives_exact_risk_and_winner_edits():
    from ihm.services.backtesting_runner import BacktestRunOptions,build_backtesting_command
    from backtesting.winner_campaign_replay import build_parser
    edits=dict(risk_per_trade_pct=.02,max_portfolio_drawdown_pct=.10,sector_ticker_limit_enabled=False)
    options=BacktestRunOptions(start='2025-01-02',end='2025-03-31',winner_enabled=True,
        winner_research_assumptions=True,oracle_batch_id='model-fixture',output_dir='artifacts/new-fixture',
        winner_risk_overrides=edits,winner_policy_overrides=dict(stop_loss_pct=.07,horizon_sessions=15))
    command=build_backtesting_command('run',options)
    args=build_parser().parse_args(command[4:])
    assert json.loads(args.risk_overrides_json)==edits
    assert json.loads(args.policy_overrides_json)==dict(stop_loss_pct=.07,horizon_sessions=15)


@pytest.mark.usefixtures('isolated_winner_config')
def test_risk_budget_override_changes_real_replay_quantities():
    from tests.test_winner_intraday import fixture
    from backtesting.simulator import BacktestEngine
    cfg,args,_=fixture()
    baseline=BacktestEngine(cfg).run(**args)
    smaller,args2,_=fixture()
    smaller.risk_config=apply_risk_settings(smaller.risk_config,dict(risk_per_trade_pct=.01))
    reduced=BacktestEngine(smaller).run(**args2)
    quantity=lambda r:r.trade_events_df.loc[r.trade_events_df.event.eq('BUY_FILL'),'quantity'].sum()
    assert 0<quantity(reduced)<quantity(baseline)


@pytest.mark.parametrize('yaml_integers',[False,True])
def test_real_form_edits_and_reset_round_trip_without_changing_yaml(monkeypatch,yaml_integers):
    from streamlit.testing.v1 import AppTest
    from execution_engine.config import LeverageConfig
    base_policy=WinnerPyramidingConfig(enabled=True,horizon_sessions=10,trailing_stop_pct=None)
    base_risk=RiskConfig(account_equity=4000.)
    if yaml_integers:
        base_policy=replace(base_policy,cost_reserve_bps_per_leg=25)
        base_risk=replace(base_risk,correlation_threshold=1,max_portfolio_beta=3)
    monkeypatch.setattr('ihm.components.winner_backtest.load_winner_pyramiding_config',lambda:base_policy)
    monkeypatch.setattr('risk_management.config.load_risk_config',lambda **kw:base_risk)
    monkeypatch.setattr('execution_engine.config.load_leverage_config_from_yaml',lambda:LeverageConfig(enabled=False))
    monkeypatch.setattr('modelFactory.oracle_path.predict.load_contract',lambda *a:(None,{'horizon':10},None,
        {'2021-07-02':{'metrics':dict(fold_start='2021-07-02',train_available_max='2020-12-30',val_available_max='2021-07-01')}}))
    def app():
        from dataclasses import asdict
        import streamlit as st
        from ihm.components.winner_backtest import render_winner_backtest
        st.session_state['settings_result']=asdict(render_winner_backtest())
    at=AppTest.from_function(app).run(timeout=30)
    assert not at.exception
    initial=at.session_state['settings_result']
    assert initial['winner_research_assumptions'] is True
    assert initial['winner_risk_overrides']=={} and initial['winner_policy_overrides']=={}
    at.number_input(key='bt_wr_budget').set_value(2.)
    at.number_input(key='bt_wr_minimum').set_value(35.)
    at.number_input(key='bt_wp_sl').set_value(7.)
    at.number_input(key='bt_wp_horizon').set_value(15).run(timeout=30)
    assert not at.exception
    edited=at.session_state['settings_result']
    assert edited['winner_risk_overrides']['risk_per_trade_pct']==.02
    assert edited['winner_risk_overrides']['min_position_notional']==35.
    assert edited['winner_policy_overrides']==dict(stop_loss_pct=.07,horizon_sessions=15)
    assert base_policy.stop_loss_pct==.05 and base_risk.risk_per_trade_pct==.01
    at.button(key='bt_winner_reset_settings').click().run(timeout=30)
    assert not at.exception
    assert at.session_state['settings_result']['winner_risk_overrides']=={}
    assert at.session_state['settings_result']['winner_policy_overrides']=={}
