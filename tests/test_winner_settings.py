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
    assert initial['winner_ignore_missing_intraday'] is True
    assert initial['winner_factor_market_cap_check'] is False
    at.checkbox(key='bt_winner_ignore_missing_intraday').uncheck().run(timeout=30)
    assert at.session_state['settings_result']['winner_ignore_missing_intraday'] is False
    at.checkbox(key='bt_winner_factor_cap').check().run(timeout=30)
    assert at.session_state['settings_result']['winner_factor_market_cap_check'] is True
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
    assert at.session_state['settings_result']['winner_ignore_missing_intraday'] is True
    assert at.session_state['settings_result']['winner_factor_market_cap_check'] is False


def test_visible_settings_block_reads_yaml_edits_replay_command_and_resets(tmp_path,monkeypatch):
    """Controls live in the named block, rather than a closed duplicate panel."""
    from pathlib import Path
    import yaml
    from streamlit.testing.v1 import AppTest
    from execution_engine.config import LeverageConfig
    from ihm.services.backtesting_runner import BacktestRunOptions,build_backtesting_command
    from backtesting.winner_campaign_replay import build_parser
    configured=WinnerPyramidingConfig(enabled=True,stop_loss_pct=.08,take_profit_pct=.16,
        trailing_stop_pct=.12,horizon_sessions=15,initial_position_fraction=.5,
        reinforcement_enabled=True,reinforcement_trigger_pct=.06,confirmation_bars=3,
        entry_valid_sessions=8,market_data_delay_seconds=930,delayed_entry_limit_buffer_pct=.02,
        cost_reserve_bps_per_leg=37,standard_entry_quote_check_enabled=False)
    config_path=tmp_path/'config.yaml'
    config_path.write_text(yaml.safe_dump(dict(winner_pyramiding=asdict(configured))),encoding='utf-8')
    original_config=config_path.read_bytes()
    monkeypatch.setenv('ALPHA_TRADE_CONFIG_PATH',str(config_path))
    model_root=tmp_path/'models';receipt=model_root/'fixture-model'/'oracle_path'/'report.json'
    receipt.parent.mkdir(parents=True)
    receipt.write_text(json.dumps(dict(status='completed',serving_ready=True,horizon=10)))
    monkeypatch.setattr('ihm.components.winner_backtest.Path',lambda p:model_root if p=='artifacts/models' else Path(p))
    monkeypatch.setattr('risk_management.config.load_risk_config',lambda **kw:RiskConfig(account_equity=kw['equity']))
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
    panel=next(e for e in at.expander if e.label=='Réglages Winner et limites du replay')
    assert panel.number_input(key='bt_wp_sl').value==8.
    assert panel.number_input(key='bt_wp_tp').value==16.
    assert panel.number_input(key='bt_wp_trailing').value==12.
    assert panel.number_input(key='bt_wp_horizon').value==15
    assert panel.number_input(key='bt_wp_confirmation').value==3
    assert panel.number_input(key='bt_wp_validity').value==8
    assert panel.number_input(key='bt_wp_delay').value==930
    assert panel.number_input(key='bt_wp_reserve').value==37.
    assert not any(e.label=='Protections et confirmation Winner' for e in at.expander)
    assert at.session_state['settings_result']['winner_policy_overrides']=={}
    for key,value in [('bt_wp_sl',6.),('bt_wp_tp',18.),('bt_wp_trailing',9.),('bt_wp_horizon',10),
                      ('bt_wp_confirmation',0),('bt_wp_validity',12),('bt_wp_delay',1200),
                      ('bt_wp_delayed_buffer',.5),('bt_wp_reserve',40.)]:
        at.number_input(key=key).set_value(value)
    at.selectbox(key='bt_wp_fraction').select(1.)
    at.checkbox(key='bt_wp_add').uncheck().run(timeout=30)
    assert not at.exception
    options=BacktestRunOptions(**at.session_state['settings_result'])
    parsed=build_parser().parse_args(build_backtesting_command('run',options)[4:])
    changes=json.loads(parsed.policy_overrides_json)
    assert changes==dict(stop_loss_pct=.06,take_profit_pct=.18,trailing_stop_pct=.09,
        horizon_sessions=10,initial_position_fraction=1.,reinforcement_enabled=False,
        confirmation_bars=0,entry_valid_sessions=12,market_data_delay_seconds=1200,
        delayed_entry_limit_buffer_pct=.005,cost_reserve_bps_per_leg=40.)
    at.button(key='bt_winner_reset_settings').click().run(timeout=30)
    assert not at.exception and at.session_state['settings_result']['winner_policy_overrides']=={}
    assert at.number_input(key='bt_wp_sl').value==8.
    assert at.number_input(key='bt_wp_horizon').value==15
    assert config_path.read_bytes()==original_config
