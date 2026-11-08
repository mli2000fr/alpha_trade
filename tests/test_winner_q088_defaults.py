"""Q088 form defaults must reach the actual replay command and stay editable."""
from dataclasses import asdict
import json
import pytest

from streamlit.testing.v1 import AppTest


def test_q088_full_form_matches_frozen_case_and_preserves_edits(tmp_path,monkeypatch):
    from common.winner_pyramiding import WinnerPyramidingConfig
    from execution_engine.config import LeverageConfig
    from risk_management.config import RiskConfig
    from ihm.components import winner_backtest as ui
    from ihm.services.backtesting_runner import BacktestRunOptions,build_backtesting_command
    from backtesting.winner_campaign_replay import build_parser

    batch='fixture-q088'
    root=tmp_path/batch/'oracle_path';root.mkdir(parents=True)
    (root/'report.json').write_text(json.dumps(dict(status='completed',serving_ready=True,
        horizon=10,directional_models=True)))
    contract=dict(horizon=10,universe=[f'S{i}' for i in range(1790)],
        training_config=dict(oracle_path_directional_enabled=True,data=dict(training_end_date='2024-12-31')),
        directional_contract=dict(oracle_top_n=20,selected_n=5))
    folds={'2021-07-02':{'metrics':dict(fold_start='2021-07-02',
        train_available_max='2020-12-30',val_available_max='2021-07-01')}}
    policy=WinnerPyramidingConfig(enabled=True,stop_loss_pct=.07,horizon_sessions=20,
        take_profit_pct=.2,trailing_stop_pct=.15,initial_position_fraction=.5)
    risk=RiskConfig(account_equity=4000.,max_position_weight=.25,risk_per_trade_pct=.01,
        max_gross_exposure=1.,max_positions=8,target_annual_vol=.13,
        correlation_check_enabled=True,sector_weight_limit_enabled=True,
        concentration_window_calendar_days=180,sector_ticker_limit_enabled=True)
    before_policy=asdict(policy);before_risk=asdict(risk)
    monkeypatch.setattr(ui,'MODEL_ROOT',tmp_path)
    monkeypatch.setattr(ui,'load_winner_pyramiding_config',lambda:policy)
    monkeypatch.setattr('modelFactory.oracle_path.predict.load_contract',lambda *a:(root,contract,None,folds))
    monkeypatch.setattr('modelFactory.oracle_path.directional.load_manifest',lambda *a:
        (dict(models=[dict(side='long',year=2025)]),'hash'))
    monkeypatch.setattr('ihm.services.queries.get_ml_training_batch_comments',lambda:{})
    monkeypatch.setattr('risk_management.config.load_risk_config',lambda **kw:risk)
    monkeypatch.setattr('execution_engine.config.load_leverage_config_from_yaml',lambda:
        LeverageConfig(enabled=True,mode='regt_swing',max_leverage=2.))

    def app():
        import streamlit as st
        from dataclasses import asdict
        from ihm.components.winner_backtest import render_winner_backtest
        st.session_state['result']=asdict(render_winner_backtest())

    at=AppTest.from_function(app)
    # Previously opened pages receive Q088 exactly once, including batch-specific controls.
    at.session_state['bt_wp_sl']=9.
    at.session_state['bt_winner_q088_defaults_20261107']=True  # Original Q088 migrated, too.
    at.session_state['bt_wr_budget']=2.5
    at.session_state['bt_wr_controller_enabled']=False
    at.session_state[f'bt_per_symbol_min_long_probability_{batch}']=.8
    at.session_state[f'bt_per_symbol_pool_{batch}_mode']='Nombre de titres'
    at.run(timeout=30)
    assert not at.exception
    result=at.session_state['result']
    assert result['winner_top_n']==358
    assert result['winner_per_symbol_long_enabled'] and result['winner_per_symbol_allow_long']
    assert not result['winner_per_symbol_allow_short']
    assert result['winner_per_symbol_top_long']==10
    assert result['winner_per_symbol_min_long_probability']==.6
    assert result['winner_per_symbol_min_long_auc']==.6
    assert (result['equity'],result['account_type'],result['winner_max_leverage'])==(4000.,'margin',2.)
    assert result['max_positions']==20 and result['winner_cost_per_leg_bps']==8.
    assert result['margin_interest_rate']==.065
    assert result['winner_drawdown_controller_enabled'] and not result['winner_factor_model']
    assert at.checkbox(key='bt_wr_close').value
    assert at.number_input(key='bt_wr_dd').value==15.
    assert at.number_input(key='bt_wr_close_pct').value==50.
    assert at.number_input(key='bt_wr_dayloss').value==3.
    assert not result['winner_options_filter_enabled'] and result['winner_daily_entry_enabled']
    parsed=build_parser().parse_args(build_backtesting_command('run',BacktestRunOptions(**result))[4:])
    assert parsed.top_n==358 and parsed.per_symbol_top_long==10
    edits=json.loads(parsed.risk_overrides_json)
    assert edits['risk_per_trade_pct']==.0125 and edits['max_position_weight']==.2
    assert edits['max_gross_exposure']==2. and edits['min_position_notional']==50.
    assert edits['target_annual_vol'] is None and edits['correlation_check_enabled'] is False
    assert edits['concentration_window_calendar_days']==90
    assert edits['sector_weight_limit_enabled'] is False and edits['sector_ticker_limit_enabled'] is False
    p=json.loads(parsed.policy_overrides_json)
    assert p['stop_loss_pct']==.05 and p['take_profit_pct'] is None and p['trailing_stop_pct'] is None
    assert p['horizon_sessions']==10 and p['initial_position_fraction']==1.
    assert p['confirmation_bars']==0 and p['entry_valid_sessions']==1
    assert asdict(policy)==before_policy and asdict(risk)==before_risk
    assert at.selectbox(key='bt_winner_profile_choice').value=='q088'
    assert len(at.selectbox(key='bt_winner_profile_choice').options)==4
    assert any('+35,13 %' in message.value for message in at.info)
    assert not any(b.key in ('bt_winner_reset_q088','bt_winner_reset_reference','bt_winner_reset_settings')
                   for b in at.button)

    at.selectbox(key='bt_winner_profile_choice').select('q051').run(timeout=30)
    assert not at.exception
    selected=at.session_state['result']
    assert selected['winner_top_n']==179 and selected['winner_per_symbol_top_long']==5
    assert selected['winner_per_symbol_min_long_probability']==.6
    assert selected['winner_per_symbol_min_long_auc']==.6
    assert selected['winner_risk_overrides']['risk_per_trade_pct']==.0125
    assert selected['winner_risk_overrides']['max_position_weight']==.2
    assert at.number_input(key='bt_wr_gross').value==1.
    assert selected['account_type']=='margin' and selected['winner_max_leverage']==2.
    assert not selected['winner_drawdown_controller_enabled'] and not at.checkbox(key='bt_wr_close').value
    assert any('+31,67 %' in message.value and '−18,04 %' in message.value for message in at.info)
    assert (selected['oracle_batch_id'],selected['start'],selected['end'])==(result['oracle_batch_id'],result['start'],result['end'])
    q051_args=build_parser().parse_args(build_backtesting_command('run',BacktestRunOptions(**selected))[4:])
    assert q051_args.top_n==179 and q051_args.per_symbol_top_long==5
    assert not q051_args.drawdown_controller
    assert json.loads(q051_args.risk_overrides_json)['force_close_on_breaker'] is False
    at.number_input(key=f'bt_per_symbol_min_long_probability_{batch}').set_value(.7).run(timeout=30)
    assert at.session_state['result']['winner_per_symbol_min_long_probability']==.7
    assert at.session_state['result']['winner_per_symbol_top_long']==5
    at.selectbox(key='bt_winner_profile_choice').select('q088').run(timeout=30)
    assert at.session_state['result']['winner_top_n']==358
    assert at.session_state['result']['winner_per_symbol_top_long']==10
    assert at.session_state['result']['winner_drawdown_controller_enabled']
    assert at.number_input(key='bt_wr_gross').value==2.

    at.number_input(key='bt_wr_budget').set_value(1.5)
    at.number_input(key=f'bt_per_symbol_pool_{batch}_pct').set_value(10.)
    at.number_input(key=f'bt_per_symbol_min_long_probability_{batch}').set_value(.7).run(timeout=30)
    assert not at.exception
    assert at.session_state['result']['winner_top_n']==179
    assert at.session_state['result']['winner_risk_overrides']['risk_per_trade_pct']==.015
    assert at.session_state['result']['winner_per_symbol_min_long_probability']==.7
    at.button(key='bt_winner_profile_reload').click().run(timeout=30)
    assert not at.exception
    assert at.session_state['result']['winner_top_n']==358
    assert at.session_state['result']['winner_per_symbol_min_long_probability']==.6
    assert at.number_input(key='bt_wr_budget').value==1.25
    assert at.session_state['result']['winner_drawdown_controller_enabled']
    at.selectbox(key='bt_winner_profile_choice').select('production').run(timeout=30)
    assert not at.exception
    assert at.number_input(key='bt_wr_budget').value==1.
    assert at.number_input(key='bt_wp_sl').value==pytest.approx(7.)
    assert at.session_state['result']['winner_policy_overrides']=={}
    assert asdict(policy)==before_policy and asdict(risk)==before_risk
