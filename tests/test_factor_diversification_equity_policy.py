"""Capital-aware diversification, shared by live risk, Winner and replay configs."""
from dataclasses import replace
from datetime import date

import numpy as np
import pytest

from risk_management.config import RiskConfig, load_risk_config
from risk_management.factor_model import FactorCovariance
from risk_management.live_factor_context import factor_violations
from risk_management.models import FactorExposures


POLICY=dict(min_factor_diversification=2,
    factor_diversification_small_account_threshold=25000.,
    factor_diversification_small_account_min=1)
DAY=date(2026,10,28)


@pytest.mark.parametrize('equity,expected',[(1960.69,1),(24999.99,1),(25000.,2),
    (25000.01,2),(59546.12,2),(62223.13,2)])
def test_strict_boundary_uses_current_equity(equity,expected):
    cfg=RiskConfig(account_equity=equity,**POLICY)
    assert cfg.effective_min_factor_diversification==expected
    assert cfg.min_factor_diversification==2


def test_live_step11_and_winner_loader_share_actual_account_rule(monkeypatch):
    from execution_engine.winner_live_risk import campaign_risk_config
    monkeypatch.setattr('common.config_loader.load_config',lambda:dict(risk_management=POLICY))
    for equity,expected in [(2000.,1),(60000.,2)]:
        step11=load_risk_config(equity=equity,cli_overrides={'account_equity':equity})
        watcher=campaign_risk_config(equity)
        assert step11.effective_min_factor_diversification==watcher.effective_min_factor_diversification==expected


def test_selected_preset_does_not_replace_actual_capital():
    cfg=RiskConfig.from_yaml_section(POLICY,preset_key='capital_2001_5000',account_equity=60000.)
    assert cfg.effective_min_factor_diversification==2


def test_replay_recomputes_threshold_as_equity_crosses_it():
    cfg=RiskConfig(account_equity=24000.,**POLICY)
    assert cfg.effective_min_factor_diversification==1
    higher=replace(cfg,account_equity=26000.)
    assert higher.effective_min_factor_diversification==2
    assert replace(higher,account_equity=24000.).effective_min_factor_diversification==1


def test_old_snapshots_keep_their_original_rule_and_new_snapshots_roundtrip():
    old=RiskConfig.from_dict({'account_equity':2000.,'min_factor_diversification':2})
    assert old.effective_min_factor_diversification==2
    cfg=RiskConfig(account_equity=2000.,**POLICY)
    restored=RiskConfig.from_dict(cfg.to_dict(exclude_defaults=False))
    assert restored.fingerprint==cfg.fingerprint
    assert restored.effective_min_factor_diversification==1
    assert old.fingerprint!=cfg.fingerprint
    assert replace(cfg,factor_diversification_small_account_threshold=None).effective_min_factor_diversification==2
    assert replace(cfg,factor_diversification_small_account_min=2).effective_min_factor_diversification==2


@pytest.mark.parametrize('values',[
    {'factor_diversification_small_account_threshold':0},
    {'factor_diversification_small_account_threshold':float('nan')},
    {'factor_diversification_small_account_threshold':float('inf')},
    {'factor_diversification_small_account_threshold':True},
    {'factor_diversification_small_account_min':0},
    {'factor_diversification_small_account_min':1.5},
    {'factor_diversification_small_account_min':True},
    {'factor_diversification_check_enabled':'false'},
    {'factor_diversification_check_enabled':0},
    {'factor_diversification_check_enabled':None},
])
def test_invalid_settings_fail_closed(values):
    with pytest.raises(ValueError):RiskConfig(**(POLICY|values))


def context(beta=1.,specific=1.):
    return dict(qualified=True,exposures={'A':FactorExposures('A',DAY,beta,.05,.05)},
        covariance=FactorCovariance(np.eye(3),['market','size','momentum'],{'A':specific},DAY))


def test_actual_factor_guard_relaxes_only_the_small_account_minimum():
    small=RiskConfig(account_equity=2000.,beta_exposure_basis='account_equity',**POLICY)
    large=replace(small,account_equity=60000.)
    assert factor_violations(context(),{'A':.1},small,candidate='A')==[]
    assert factor_violations(context(),{'A':.1},large,candidate='A')==['final_factor_diversification:1<2']
    assert any('beta_exceeded' in r for r in factor_violations(context(beta=20.),{'A':.1},small,candidate='A'))
    assert any('factor_concentration' in r for r in factor_violations(context(specific=.001),{'A':.1},small,candidate='A'))


def test_disabling_count_gate_preserves_beta_concentration_and_missing_input_guards():
    enabled=RiskConfig(account_equity=2000.,beta_exposure_basis='account_equity',**POLICY)
    disabled=replace(enabled,factor_diversification_check_enabled=False)
    assert factor_violations(context(beta=.05),{'A':.1},enabled,candidate='A')==['final_factor_diversification:0<1']
    assert factor_violations(context(beta=.05),{'A':.1},disabled,candidate='A')==[]
    assert any('beta_exceeded' in r for r in factor_violations(context(beta=40.),{'A':.1},disabled,candidate='A'))
    assert any('factor_concentration' in r for r in factor_violations(context(specific=.001),{'A':.1},disabled,candidate='A'))
    with pytest.raises(ValueError,match='Missing held/pending'):
        factor_violations(context(),{'MISSING':.1},disabled,candidate='MISSING')
    restored=RiskConfig.from_dict(disabled.to_dict(exclude_defaults=False))
    assert restored.factor_diversification_check_enabled is False
    assert restored.fingerprint==disabled.fingerprint
    assert RiskConfig.from_dict({'account_equity':2000.}).factor_diversification_check_enabled is True


def test_step11_and_watcher_load_disabled_flag_without_disabling_factor_model(monkeypatch):
    from execution_engine.winner_live_risk import campaign_risk_config
    monkeypatch.setattr('common.config_loader.load_config',lambda:dict(risk_management=POLICY|{
        'factor_diversification_check_enabled':False,'enable_factor_model':True}))
    step11=load_risk_config(equity=60000.,cli_overrides={'account_equity':60000.})
    watcher=campaign_risk_config(60000.)
    for cfg in (step11,watcher):
        assert cfg.enable_factor_model is True
        assert cfg.factor_diversification_check_enabled is False
        assert factor_violations(context(beta=.05),{'A':.1},cfg,candidate='A')==[]


def test_shared_portfolio_builder_uses_effective_rule_after_real_sizing():
    from tests.test_oracle_pure_portfolio_policy import setup,build,DAY as BUILD_DAY
    from risk_management.operational_data import BacktestOperationalDataAdapter
    from datetime import datetime,UTC
    b=setup(enable_factor_model=True,beta_exposure_basis='account_equity',**POLICY)
    b._factor_covariance=FactorCovariance(np.eye(3),['market','size','momentum'],{'NEW':1.},BUILD_DAY)
    b._factor_exposures={'NEW':FactorExposures('NEW',BUILD_DAY,1.,.05,.05)}
    assert any(e.approved_shares>0 for e in build(b))
    b._cfg=replace(b._cfg,account_equity=60000.)
    b.set_operational_snapshot(BacktestOperationalDataAdapter.build(account_id='fixture',
        account={'equity':60000.,'cash':60000.,'buying_power':60000.},
        as_of=datetime.combine(BUILD_DAY,datetime.min.time(),tzinfo=UTC)))
    rejected=build(b)
    assert rejected and all(e.approved_shares==0 for e in rejected)
    assert any('diversification' in e.decision_reason for e in rejected)
    b._cfg=replace(b._cfg,factor_diversification_check_enabled=False)
    assert any(e.approved_shares>0 for e in build(b))
