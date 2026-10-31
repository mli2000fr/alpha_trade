from dataclasses import replace
from datetime import date

import numpy as np
import pytest

from risk_management.config import RiskConfig, load_risk_config
from risk_management.constraints import ConstraintChecker, PortfolioState
from risk_management.factor_model import FactorCovariance, check_factor_constraints_on_sized_weights
from risk_management.models import FactorExposures
from risk_management.live_factor_context import factor_violations


@pytest.mark.parametrize('enabled,quantity',[(True,10),(False,20)])
def test_sector_weight_switch_controls_sizing_and_final_validation(enabled,quantity):
    cfg=RiskConfig(account_equity=10000,max_positions=20,max_position_weight=.5,
        max_sector_weight=.1,min_position_notional=10,sector_weight_limit_enabled=enabled,
        sector_ticker_limit_enabled=False)
    state=PortfolioState();state.add_position(notional=500,sector='Tech',symbol='HELD')
    checker=ConstraintChecker(cfg)
    assert checker.check('NEW','Tech',20,50,state,adv_usd=1e7)[0]==quantity
    state.add_position(notional=1000,sector='Tech',symbol='NEW')
    assert any('sector_weight_exceeded' in v for v in checker.revalidate_portfolio(state)) is enabled
    # The count-independent exposure mode obeys the same weight switch.
    cfg=replace(cfg,sector_cap_mode='exposure',sector_exposure_cap_pct=.05)
    state=PortfolioState();state.add_position(notional=500,sector='Tech',symbol='HELD')
    assert (ConstraintChecker(cfg).check('NEW','Tech',20,50,state,adv_usd=1e7)[0]>0) is (not enabled)


def factors(beta=3.,size=.1):
    day=date(2026,10,29)
    return {'A':FactorExposures('A',day,beta,size,.1)}, FactorCovariance(
        np.eye(3),['market','size','momentum'],{'A':.01},day)


@pytest.mark.parametrize('enabled',[True,False])
def test_only_market_concentration_is_optional(enabled):
    exp,cov=factors()
    kwargs=dict(beta_exposure_basis='account_equity',factor_diversification_check_enabled=False,
        market_factor_concentration_check_enabled=enabled)
    violations=check_factor_constraints_on_sized_weights({'A':.1},exp,cov,**kwargs)
    assert any('final_factor_concentration:market:' in v for v in violations) is enabled
    beta=check_factor_constraints_on_sized_weights({'A':.1},exp,cov,max_portfolio_beta=.05,**kwargs)
    assert any('final_beta_exceeded' in v for v in beta)
    exp,cov=factors(beta=.1,size=30)
    other=check_factor_constraints_on_sized_weights({'A':.1},exp,cov,**kwargs)
    assert any('final_factor_concentration:size:' in v for v in other)


def test_live_and_watcher_context_propagates_market_switch():
    exp,cov=factors()
    context=dict(qualified=True,exposures=exp,covariance=cov)
    cfg=RiskConfig(market_factor_concentration_check_enabled=False,factor_diversification_check_enabled=False,
        beta_exposure_basis='account_equity')
    assert factor_violations(context,{'A':.1},cfg,candidate='A')==[]
    assert any('final_factor_concentration:market:' in v for v in factor_violations(
        context,{'A':.1},replace(cfg,market_factor_concentration_check_enabled=True),candidate='A'))


@pytest.mark.parametrize('key',['sector_weight_limit_enabled','market_factor_concentration_check_enabled'])
def test_switch_requires_boolean_and_yaml_defaults_to_false(key):
    with pytest.raises(ValueError,match=key):RiskConfig(**{key:'false'})
    cfg=load_risk_config(equity=1940,cli_overrides={'account_equity':1940})
    assert getattr(cfg,key) is False
