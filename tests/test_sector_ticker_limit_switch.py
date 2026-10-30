from dataclasses import replace

import pytest

from risk_management.config import RiskConfig, load_risk_config
from risk_management.constraints import ConstraintChecker, PortfolioState


def state():
    result=PortfolioState()
    for n in range(4):
        result.add_position(notional=100,sector='Tech',symbol=f'HELD{n}')
    return result


def config(enabled=True, **extra):
    return RiskConfig(account_equity=10000,max_positions=20,max_position_weight=.5,
        max_sector_weight=.8,min_position_notional=10,max_tickers_per_sector=4,
        sector_ticker_limit_enabled=enabled,**extra)


@pytest.mark.parametrize('enabled,expected',[(True,0),(False,10)])
def test_entry_and_final_validation_obey_same_switch(enabled,expected):
    checker=ConstraintChecker(config(enabled))
    shares,reason=checker.check('NEW','Tech',10,50,state(),adv_usd=1e7)
    assert shares==expected
    final=state();final.add_position(notional=500,sector='Tech',symbol='NEW')
    assert any('sector_ticker_count_exceeded' in v for v in checker.revalidate_portfolio(final)) is enabled


def test_disabling_count_preserves_sector_weight_and_other_limits():
    cfg=replace(config(False),max_sector_weight=.04)
    approved,reason=ConstraintChecker(cfg).check('NEW','Tech',10,50,state(),adv_usd=1e7)
    assert approved==0 and reason=='max_sector_weight atteint'
    cfg=replace(config(False),max_positions=4)
    assert ConstraintChecker(cfg).check('NEW','Tech',10,50,state(),adv_usd=1e7)[0]==0


def test_hybrid_count_can_be_disabled_but_exposure_guard_survives():
    cfg=config(False,sector_cap_mode='hybrid',sector_exposure_cap_pct=.20,
        sector_corr_map={'NEW':{f'HELD{n}':.1 for n in range(4)}})
    assert ConstraintChecker(cfg).check('NEW','Tech',10,50,state(),adv_usd=1e7)[0]==10
    cfg=replace(cfg,sector_exposure_cap_pct=.05)
    assert ConstraintChecker(cfg).check('NEW','Tech',10,50,state(),adv_usd=1e7)[1]=='sector_exposure_cap atteint'


@pytest.mark.parametrize('invalid',['false',0,None])
def test_switch_requires_a_real_boolean(invalid):
    with pytest.raises(ValueError,match='sector_ticker_limit_enabled'):
        config(invalid)


def test_yaml_false_survives_preset_and_regime_count_override():
    cfg=load_risk_config(equity=1940.7,cli_overrides=dict(account_equity=1940.7))
    assert cfg.sector_ticker_limit_enabled is False
    assert cfg.with_overrides(max_tickers_per_sector=4).sector_ticker_limit_enabled is False
