from dataclasses import replace
import pytest

from scripts.research.us_gpt_winner_boost_favorable import entry_sizing,scaled_risk


@pytest.mark.usefixtures('isolated_winner_config')
def test_per_candidate_multiplier_reaches_native_daily_entry_and_recheck():
    from tests.test_winner_intraday import fixture
    from backtesting.simulator import BacktestEngine
    from backtesting import winner_daily_entry as module
    cfg,args,_=fixture(symbols=('AAA','BBB'),leverage=2.,confirmation_bars=0,initial_position_fraction=1.)
    cfg.winner_daily_entry_enabled=True;cfg.winner_drawdown_controller_enabled=False
    cfg.risk_config=replace(cfg.risk_config,risk_per_trade_pct=.0125,max_position_weight=.2,
        target_annual_vol=None,correlation_check_enabled=False,sector_weight_limit_enabled=False)
    for field in ('open_df','close','high','low'):args[field]=args[field]*0+100.
    args['high']+=1.;args['low']-=1.
    day=str(args['signals_df'].trade_date.iloc[0])[:10]
    old_enter,old_approve=module.enter_daily_candidates,module.approve_daily_open
    with entry_sizing({(day,'AAA'):5,(day,'BBB'):1}):result=BacktestEngine(cfg).run(**args)
    buys=result.trade_events_df.query('event=="BUY_FILL"').set_index('symbol')
    # The first fill's fees reduce current equity before sizing BBB: floor(799.36/100)=7.
    assert buys.loc['AAA','quantity']==40 and buys.loc['BBB','quantity']==7
    assert module.enter_daily_candidates is old_enter and module.approve_daily_open is old_approve
    assert cfg.risk_config.risk_per_trade_pct==.0125 and cfg.risk_config.max_position_weight==.2
    scaled=scaled_risk(cfg.risk_config,5)
    assert scaled.risk_per_trade_pct==.0625 and scaled.max_position_weight==1.
    assert scaled.max_gross_exposure==2. and cfg.exec_config.leverage.max_leverage==2.
