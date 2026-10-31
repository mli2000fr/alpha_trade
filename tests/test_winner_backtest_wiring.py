"""Offline launch, provider precedence, archived risk and UI contracts."""
from dataclasses import replace
from datetime import UTC, date, datetime
import json

import pandas as pd
import pytest
from sqlalchemy import create_engine, event

from ihm.services.backtesting_runner import BacktestRunOptions, build_backtesting_command
from backtesting.winner_campaign_replay import build_parser


def options(**changes):
    return replace(BacktestRunOptions(start='2025-01-02', end='2025-03-31',
        winner_enabled=True, oracle_batch_id='fixture-h10', output_dir='artifacts/fixture-new',
        winner_research_assumptions=True, ml_mode='off', equity=4000.), **changes)


def test_ui_command_is_consumed_by_real_replay_parser():
    command = build_backtesting_command('run',options(winner_top_n=50, winner_max_leverage=2.,
        winner_factor_model=False, winner_cost_per_leg_bps=8., max_positions=12, margin_interest_rate=.065,
        winner_options_filter_enabled=True))
    assert command[3]=='backtesting.winner_campaign_replay'
    args = build_parser().parse_args(command[4:])
    assert (args.oracle_batch_id,args.top_n,args.initial_equity,args.max_positions)==('fixture-h10',50,4000.,12)
    assert args.max_leverage==2. and args.factor_model is False
    assert args.cost_per_leg_bps==8. and args.margin_interest_annual==.065
    assert args.options_filter is True
    assert args.research_assumptions and args.symbol_source.endswith('univers_filtred_tradable.txt')
    assert '--phase2-mode' not in command and '--no-winner-pyramiding' not in command


def test_legacy_mode_explicitly_disables_yaml_winner_without_mutating_config():
    from backtesting.cli._impl import _build_parser
    command = build_backtesting_command('run',BacktestRunOptions(start='2025-01-01'))
    assert command[3:5]==['backtesting','run'] and '--no-winner-pyramiding' in command
    assert _build_parser().parse_args(command[4:]).winner_pyramiding is False


def test_winner_requires_explicit_assumptions_and_model():
    for changes in [dict(winner_research_assumptions=False),dict(oracle_batch_id=None)]:
        with pytest.raises(ValueError):
            build_backtesting_command('run', options(**changes))


def test_daily_optout_restores_only_winner_specific_risk_fields(monkeypatch):
    from backtesting.cli._impl import _without_winner_risk_policy
    from risk_management.config import RiskConfig
    monkeypatch.setattr('common.config_loader.load_config',lambda:dict(
        winner_pyramiding=dict(enabled=True,stop_loss_pct=.05),risk_management={}))
    current=RiskConfig(account_equity=4000.,fixed_stop_pct=.05,disable_price_take_profit=True,
                       allow_fractional_shares=False,max_positions=7,max_daily_loss_pct=.02)
    standard=_without_winner_risk_policy(current,equity=4000.,preset_key=None,allow_fractional_shares=True)
    assert standard.fixed_stop_pct is None and standard.disable_price_take_profit is False
    assert standard.allow_fractional_shares is True
    assert standard.max_positions==7 and standard.max_daily_loss_pct==.02


def test_forged_past_sql_availability_cannot_serve_future_weights():
    from backtesting.winner_campaign_replay import validate_scores
    rows=pd.DataFrame([dict(trade_date='2025-01-02',symbol='AAA',proba_extreme=.9,
        fold_start='2024-01-01',lineage_fold_start='2024-01-01',model_available_date='2024-12-31',
        model_sha256='weights',feature_profile_sha256='profile',target_name='oracle_path_extreme10',target_horizon=10)])
    folds={'2024-01-01':dict(model_sha256='weights',metrics=dict(
        train_available_max='2025-02-01',val_available_max='2025-04-01'))}
    with pytest.raises(ValueError,match='non-causal'):
        validate_scores(rows,profile_hash='profile',folds=folds,expected_days=[date(2025,1,2)],top_n=1,horizon=10)
    folds['2024-01-01']['metrics']=dict(train_available_max='2024-12-30',val_available_max='2024-12-31')
    with pytest.raises(ValueError,match='Couverture Oracle insuffisante'):
        validate_scores(rows,profile_hash='profile',folds=folds,expected_days=[date(2025,1,2)],
                        top_n=1,horizon=10,universe_size=100,min_coverage=.9)


def test_daily_whole_row_priority_and_invalid_preferred_not_replaced(monkeypatch):
    from backtesting.winner_data import daily_bars
    monkeypatch.setattr('common.daily_bar_sources.load_config',lambda:dict(
        market_data=dict(daily_bars_preferred_source='eodhd')))
    engine=create_engine('sqlite://')
    rows=[]
    for day in ('2025-01-02','2025-01-03'):
        for source,price in [('alpaca_sip',100.),('eodhd_eod',110.)]:
            rows.append(dict(date=day,symbol='AAA',open=price,high=price+1,low=price-1,
                close=price,volume=1000,is_filled=int(day=='2025-01-03' and source=='eodhd_eod'),
                data_source=source,data_adjustment='split'))
    pd.DataFrame(rows).to_sql('stock_bars_daily',engine,index=False)
    statements=[]
    event.listen(engine,'before_cursor_execute',lambda conn,cursor,sql,*a:statements.append(sql))
    with engine.connect() as conn:
        result=daily_bars(conn,['AAA'],'2025-01-02','2025-01-03')
    assert result.close.tolist()==[110.] and result.data_source.tolist()==['eodhd_eod']
    assert all(s.lstrip().startswith('SELECT') for s in statements)


def test_factor_source_cannot_backdate_or_refresh_observations():
    from backtesting.winner_data import HistoricalFactorSource
    from risk_management.config import RiskConfig
    engine=create_engine('sqlite://')
    pd.DataFrame([dict(asof_date='2025-01-02',observed_at='2026-01-01',id=1)]).to_sql(
        'stock_risk_factor_inputs',engine,index=False)
    statements=[]
    event.listen(engine,'before_cursor_execute',lambda conn,cursor,sql,*a:statements.append(sql))
    with engine.connect() as conn:
        source=HistoricalFactorSource(conn,pd.DataFrame())
        with pytest.raises(ValueError,match='Aucun snapshot'):
            source(date(2025,1,2),['AAA'],datetime(2025,1,3,15,tzinfo=UTC),RiskConfig(account_equity=4000.))
    assert source.receipts[0]['qualified'] is False
    assert all(s.lstrip().startswith('SELECT') for s in statements)


def test_real_form_default_policy_and_independent_dates(monkeypatch):
    from streamlit.testing.v1 import AppTest
    from common.winner_pyramiding import WinnerPyramidingConfig
    from risk_management.config import RiskConfig
    from execution_engine.config import LeverageConfig
    monkeypatch.setattr('ihm.components.winner_backtest.load_winner_pyramiding_config',lambda:
        WinnerPyramidingConfig(enabled=True,horizon_sessions=10,stop_loss_pct=.05,trailing_stop_pct=None))
    monkeypatch.setattr('modelFactory.oracle_path.predict.load_contract',lambda *a:
        (None,{'horizon':10},None,{'2021-07-02':{'metrics':dict(fold_start='2021-07-02',
             train_available_max='2020-12-30',val_available_max='2021-07-01')}}))
    monkeypatch.setattr('risk_management.config.load_risk_config',lambda **kw:RiskConfig(
        account_equity=kw['equity'],enable_factor_model=True))
    monkeypatch.setattr('execution_engine.config.load_leverage_config_from_yaml',lambda:LeverageConfig(enabled=False))
    def app():
        from dataclasses import asdict
        import streamlit as st
        from ihm.components.winner_backtest import render_winner_backtest
        st.session_state['winner_options']=asdict(render_winner_backtest())
    at=AppTest.from_function(app).run(timeout=30)
    assert not at.exception
    assert at.session_state['winner_options']['winner_enabled'] is True
    assert at.session_state['winner_options']['winner_options_filter_enabled'] is True
    assert at.session_state['winner_options']['winner_research_assumptions'] is False
    assert at.date_input[0].min==date(2021,7,6)  # NYSE closed July 5.
    at.checkbox(key='bt_winner_assumptions').check().run(timeout=30)
    assert not at.exception and at.session_state['winner_options']['winner_research_assumptions'] is True
    assert at.session_state['winner_options']['winner_factor_model'] is True
