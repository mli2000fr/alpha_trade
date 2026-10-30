from dataclasses import replace
from datetime import date

import numpy as np
import pandas as pd
import pytest

from risk_management.config import RiskConfig, load_risk_config
from risk_management.constraints import ConstraintChecker, PortfolioState
from execution_engine.winner_risk import reapprove_campaign


@pytest.mark.parametrize('enabled',[True,False])
def test_portfolio_correlation_switch(enabled):
    from test_portfolio_builder import _cfg, _candidates, _prices, _long_predictions
    from risk_management.portfolio_builder import PortfolioBuilder
    base=np.sin(np.arange(60))
    builder=PortfolioBuilder(_cfg(correlation_check_enabled=enabled))
    entries=builder.build(_candidates(),_prices(),predictions=_long_predictions([c.symbol for c in _candidates()]),
        return_matrix=pd.DataFrame({'AAPL':base,'MSFT':base}))
    assert any(e.correlation_blocker for e in entries) is enabled


@pytest.mark.parametrize('empty',[False,True])
def test_native_winner_switch_preserves_all_other_admission_checks(empty):
    from test_winner_risk import context, data, NOW
    state,snapshot=data()
    ctx=context()
    ctx.update(positions=[dict(symbol='HELD',side='long',quantity=1,mark=100)],
        sector_map={'TEST':'Technology','HELD':'Other'},
        return_matrix=pd.DataFrame() if empty else pd.DataFrame({'TEST':np.arange(60),'HELD':np.arange(60)}))
    with pytest.raises(ValueError,match='correlation'):
        reapprove_campaign(state,0,10,snapshot,NOW,'ENTRY',context=ctx)
    ctx['risk_config']=replace(ctx['risk_config'],correlation_check_enabled=False)
    result=reapprove_campaign(state,0,10,snapshot,NOW,'ENTRY',context=ctx)
    assert result['max_quantity']>0
    ctx['entries_allowed']=False
    with pytest.raises(ValueError,match='regime'):
        reapprove_campaign(state,0,10,snapshot,NOW,'ENTRY',context=ctx)


def test_hybrid_guard_uses_same_switch():
    cfg=RiskConfig(account_equity=10000,max_positions=20,max_position_weight=.5,min_position_notional=10,
        sector_weight_limit_enabled=False,sector_ticker_limit_enabled=False,sector_cap_mode='hybrid')
    state=PortfolioState()
    for n in range(4):state.add_position(notional=100,sector='Tech',symbol=f'H{n}')
    assert ConstraintChecker(cfg).check('NEW','Tech',10,50,state,adv_usd=1e7)[1]=='sector_corr_threshold atteint'
    assert ConstraintChecker(replace(cfg,correlation_check_enabled=False)).check('NEW','Tech',10,50,state,adv_usd=1e7)[0]==10


def test_factor_correlation_uses_same_switch_but_beta_remains_checked():
    from risk_management.live_factor_context import factor_violations
    from risk_management.factor_model import FactorCovariance
    from risk_management.models import FactorExposures
    day=date(2026,10,29)
    ctx=dict(qualified=True,exposures={s:FactorExposures(s,day,3,.1,.1) for s in ['A','B']},
        covariance=FactorCovariance(np.eye(3),['market','size','momentum'],{'A':.01,'B':.01},day))
    cfg=RiskConfig(use_factor_correlation_filter=True,beta_exposure_basis='account_equity',
        factor_diversification_check_enabled=False,market_factor_concentration_check_enabled=False)
    assert any('factor_correlation' in v for v in factor_violations(ctx,{'A':.1,'B':.1},cfg,candidate='A',other_sides={'B':'long'}))
    cfg=replace(cfg,correlation_check_enabled=False)
    assert factor_violations(ctx,{'A':.1,'B':.1},cfg,candidate='A',other_sides={'B':'long'})==[]
    assert any('final_beta_exceeded' in v for v in factor_violations(ctx,{'A':.1,'B':.1},
        replace(cfg,max_portfolio_beta=.1),candidate='A',other_sides={'B':'long'}))


def test_configuration_is_boolean_and_operational_default_is_off():
    with pytest.raises(ValueError,match='correlation_check_enabled'):
        RiskConfig(correlation_check_enabled='false')
    assert load_risk_config(equity=1940,cli_overrides={'account_equity':1940}).correlation_check_enabled is False
