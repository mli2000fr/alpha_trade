"""Winner imposes integer admission before sizing; nominal fractions stay available."""
from dataclasses import replace
from decimal import Decimal
from unittest.mock import Mock

import numpy as np
import pytest

from common.winner_pyramiding import WinnerPyramidingConfig, initial_quantities
from execution_engine.config import ExecutionConfig
from execution_engine.models import ExecutionTarget
from execution_engine.winner_plans import stage_targets
from risk_management.config import load_risk_config
from tests.test_oracle_pure_portfolio_policy import DAY, setup, build


@pytest.mark.parametrize('enabled', [True,False])
def test_risk_quantity_policy_overrides_cli_only_when_winner_enabled(monkeypatch,enabled):
    monkeypatch.setattr('common.config_loader.load_config',lambda:dict(
        winner_pyramiding={'enabled':enabled},risk_management={'allow_fractional_shares':True}))
    cfg=load_risk_config(equity=4000,cli_overrides={
        'account_equity':4000.,'allow_fractional_shares':True,'min_position_notional':0,'min_breakout_days':1})
    assert cfg.allow_fractional_shares is (not enabled)
    if enabled:
        b=setup()
        b._cfg=cfg
        entries=build(b)
        assert entries and any(e.approved_shares>0 for e in entries)
        assert all(float(e.approved_shares).is_integer() for e in entries)


@pytest.mark.parametrize('enabled', [True,False])
def test_execution_config_defends_same_rule_for_direct_callers(enabled):
    cfg=ExecutionConfig(allow_fractional_shares=True,
        winner_pyramiding=WinnerPyramidingConfig(enabled=enabled))
    assert cfg.allow_fractional_shares is (not enabled)


@pytest.mark.parametrize('enabled', [True,False])
@pytest.mark.parametrize('step', ['risk_management','execution'])
def test_pipeline_command_never_requests_fractions_for_winner(monkeypatch,enabled,step):
    from ihm.services.pipeline_runner import PipelineLaunchOptions,build_pipeline_command
    monkeypatch.setattr('common.winner_pyramiding.load_winner_pyramiding_config',
                        lambda *a,**kw:WinnerPyramidingConfig(enabled=enabled))
    command=build_pipeline_command(step,PipelineLaunchOptions(account_id='default',execution_mode='paper',
        trade_date='2026-10-28',allow_fractional_shares=True))
    assert ('--allow-fractional-shares' in command) is (not enabled)


def test_old_fractional_targets_fail_before_any_plan_write():
    from datetime import date,datetime,UTC
    cfg=ExecutionConfig(winner_pyramiding=WinnerPyramidingConfig(enabled=True,initial_position_fraction=1.))
    target=ExecutionTarget('risk',date(2026,10,16),'TEST',1.25,100.,.1,'Tech',.9,'atr',None,
                           risk_budget_dollars=20.,side='long')
    store=Mock()
    with pytest.raises(ValueError,match='whole-share step11'):
        stage_targets(store,[replace(target,target_shares=1.),target],cfg,'exec',
                      now=datetime(2026,10,19,12,tzinfo=UTC))
    store.create.assert_not_called()


@pytest.mark.parametrize('value',[20,np.float64(20),Decimal('20')])
def test_integer_numeric_values_are_not_rejected_for_their_python_scalar_type(value):
    assert initial_quantities(value,100.,120.,WinnerPyramidingConfig(enabled=True))==(20,10)


def test_no_whole_share_is_never_rounded_up():
    policy=WinnerPyramidingConfig(enabled=True)
    assert initial_quantities(.9,100.,120.,policy)==(0,0)
    assert initial_quantities(20,100.,.1,policy)==(0,0)
