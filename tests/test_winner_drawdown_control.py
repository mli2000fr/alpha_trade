"""Replay opt-out is explicit and does not change production risk objects."""
from dataclasses import asdict
from datetime import date

import pytest

from backtesting.winner_drawdown_control import effective_drawdown_settings,create_drawdown_state
from execution_engine.config import ExecutionConfig
from risk_management.config import RiskConfig


def test_inactive_controller_never_blocks_or_degrades_but_keeps_observed_peak():
    cfg=RiskConfig(policy='b4',max_portfolio_drawdown_pct=.15,max_daily_loss_pct=.03)
    guard=create_drawdown_state(cfg,date(2025,1,2),4000.,{},False)
    observation=guard.evaluate(date(2025,1,3),2000.,None,daily_pnl=-2000.)
    assert observation['reference_peak']==4000 and observation['allocation_scale']==1.
    assert not observation['active'] and not observation['circuit_breaker'].is_active()
    assert not observation['circuit_breaker'].just_tripped()
    with pytest.raises(ValueError):guard.evaluate(date(2025,1,2),2000.,None,daily_pnl=0.)


def test_switch_disables_only_liquidation_flags_in_local_copies():
    risk=RiskConfig(policy='b4',force_close_on_breaker=True,max_position_weight=.2)
    execution=ExecutionConfig(force_close_on_breaker=True)
    before=asdict(risk),asdict(execution)
    local_risk,local_execution=effective_drawdown_settings(risk,execution,False)
    assert not local_risk.force_close_on_breaker and not local_execution.force_close_on_breaker
    assert local_risk.max_position_weight==risk.max_position_weight
    assert (asdict(risk),asdict(execution))==before
    assert effective_drawdown_settings(risk,execution,True)==(risk,execution)
    with pytest.raises(ValueError):effective_drawdown_settings(risk,execution,0)


def test_enabled_switch_reuses_native_controller_without_substitution():
    from common.winner_risk_state import CampaignRiskState
    cfg=RiskConfig(policy='b0')
    assert isinstance(create_drawdown_state(cfg,date(2025,1,2),4000.,{},True),CampaignRiskState)


@pytest.mark.usefixtures('isolated_winner_config')
def test_off_really_allows_later_entry_after_drawdown_without_disabling_position_stop():
    from dataclasses import replace
    from backtesting.simulator import BacktestEngine
    from tests.test_winner_intraday import fixture
    results=[]
    for active in (True,False):
        cfg,args,raw=fixture(symbols=('AAA','BBB'))
        cfg.risk_config=replace(cfg.risk_config,max_portfolio_drawdown_pct=.04,force_close_on_breaker=True)
        cfg.winner_drawdown_controller_enabled=active
        raw[(cfg.start_date,'AAA')].loc[4:,['open','close','high','low']]=[90.,90.,90.1,89.9]
        raw[(cfg.start_date,'BBB')].loc[:9,['open','close','high','low']]=[100.,100.,100.1,99.9]
        results.append(BacktestEngine(cfg).run(**args))
    filled=lambda r:r.trade_events_df.loc[r.trade_events_df.event.eq('BUY_FILL'),'symbol'].tolist()
    assert filled(results[0])==['AAA']
    assert filled(results[1])==['AAA','BBB']
    off=results[1]
    assert off.closed_trades_df.iloc[0].pnl<0 and off.closed_trades_df.iloc[0].exit_reason=='STOP_GAP'
    assert not off.drawdown_breaker_df.active.any() and off.drawdown_breaker_df.allocation.eq(1.).all()
    meta=off.tracker_snapshot['winner_replay']
    assert not meta['global_liquidation']['enabled'] and not meta['drawdown_controller']['enabled']
    curve=off.intraday_equity_curve.equity
    assert (curve/curve.cummax()-1).min() < -.04  # Measurement is retained.


@pytest.mark.usefixtures('isolated_winner_config')
def test_off_skips_b4_regime_requirement_but_keeps_native_position_caps():
    from dataclasses import replace
    from backtesting.simulator import BacktestEngine
    from tests.test_winner_intraday import fixture
    cfg,args,_=fixture(symbols=('AAA','BBB'))
    cfg.risk_config=replace(cfg.risk_config,policy='b4',max_positions=1,max_long_positions=1)
    with pytest.raises(ValueError,match='SPY SMA50/200'):BacktestEngine(cfg).run(**args)
    cfg.winner_drawdown_controller_enabled=False
    result=BacktestEngine(cfg).run(**args)
    assert result.trade_events_df.loc[result.trade_events_df.event.eq('BUY_FILL'),'symbol'].tolist()==['AAA']
    cfg.winner_hard_drawdown_pct=.25
    with pytest.raises(ValueError,match='conflicts'):BacktestEngine(cfg).run(**args)


@pytest.mark.parametrize('enabled',[False,True])
def test_command_and_parser_transmit_switch_explicitly(enabled):
    from ihm.services.backtesting_runner import BacktestRunOptions,build_backtesting_command
    from backtesting.winner_campaign_replay import build_parser
    opts=BacktestRunOptions(start='2025-01-02',end='2025-12-31',winner_enabled=True,
        winner_research_assumptions=True,oracle_batch_id='fixture',output_dir='artifacts/new',
        winner_drawdown_controller_enabled=enabled)
    args=build_parser().parse_args(build_backtesting_command('run',opts)[4:])
    assert args.drawdown_controller is enabled
