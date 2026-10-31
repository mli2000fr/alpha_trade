"""Disabling size risk in replay must remove the dependency, not fake cap values."""
from dataclasses import replace
from datetime import date

import pandas as pd
import pytest
from sqlalchemy import event

from tests.test_winner_factor_reconstruction import database,SYMBOLS,DAY,NOW
from backtesting.winner_data import HistoricalFactorSource
from risk_management.config import RiskConfig

pytestmark=pytest.mark.usefixtures('isolated_winner_config')


def test_disabled_cap_never_reads_cap_sec_or_iwm_and_qualifies_two_real_factors():
    engine,close,_,_=database()
    close=close.drop(columns='IWM')
    statements=[]
    event.listen(engine,'before_cursor_execute',lambda c,cursor,sql,*a:statements.append(sql))
    with engine.connect() as conn:
        source=HistoricalFactorSource(conn,close,universe=SYMBOLS,start=close.index.min().date(),
            end=DAY,market_cap_check=False)
        context=source(DAY,['S0'],NOW,RiskConfig())
    assert context['factor_names']==['market','momentum']
    assert context['disabled_factors']==['size']
    assert context['covariance'].factor_cov.shape==(2,2)
    assert source.reconstruction.frame.market_cap.isna().all()
    assert source.reconstruction.sec is None
    assert not any('stock_market_cap_daily' in s or 'stock_risk_factor_inputs' in s for s in statements)


def test_form_command_carries_explicit_cap_toggle_to_real_parser():
    from tests.test_winner_backtest_wiring import options
    from ihm.services.backtesting_runner import build_backtesting_command
    from backtesting.winner_campaign_replay import build_parser
    command=build_backtesting_command('run',options(winner_factor_model=True,winner_factor_market_cap_check=False))
    assert '--no-factor-market-cap-check' in command
    parsed=build_parser().parse_args(command[4:])
    assert parsed.factor_model is True and parsed.factor_market_cap_check is False


def test_reduced_factor_context_remains_replay_only_and_keeps_beta_guard():
    from tests.test_winner_risk import data,context
    from tests.test_winner_runtime import NOW as now
    from risk_management.factor_model import FactorCovariance
    from risk_management.models import FactorExposures
    from execution_engine.winner_risk import reapprove_campaign
    import numpy as np
    state,snap=data();cfg=replace(context()['risk_config'],enable_factor_model=True)
    factor=dict(qualified=True,asof_date=now.date(),captured_at=now,observed_at=now,
        market_cap_check_enabled=False,disabled_factors=['size'],snapshot_hash='without-size',
        exposures={'TEST':FactorExposures('TEST',now.date(),2.,0.,1.)},
        covariance=FactorCovariance(np.eye(2),['market','momentum'],{'TEST':.05},now.date()))
    ctx=context(cfg)|dict(factor_qualified=True,factor_asof_date=now.date(),factor_context=factor)
    with pytest.raises(ValueError,match='restricted'):
        reapprove_campaign(state,0,10,snap,now,'ENTRY',context=ctx)
    result=reapprove_campaign(state,0,10,snap,now,'ENTRY',context=ctx,replay_factor_market_cap_disabled=True)
    assert result['max_quantity']==0 and any('beta' in r for r in result['factor_rejections'])
