from dataclasses import asdict,replace

import pytest

from scripts.research.us_winner_min70_4000_20261025 import minimum_only


def fixture():
    from scripts.research import us_winner_monthly_scope_repair_20261024 as repair
    study=repair.study
    parent=study.capacity.grid.base.read(study.ROOT/'protocol.json')
    return study.configuration(parent,study.inputs.START)


def test_only_minimum_changes_and_deposit_policy_are_preserved():
    cfg=fixture();changed=minimum_only(cfg)
    a,b=asdict(cfg),asdict(changed)
    assert changed.initial_equity==4000.
    assert changed.exec_config==cfg.exec_config
    assert changed.risk_config.effective_min_notional==70.
    assert cfg.risk_config.effective_min_notional==155.
    b['risk_config']['min_position_notional']=155.
    assert a==b


def test_refuses_hidden_override_other_capital_and_other_treatment():
    cfg=fixture()
    for wrong in [replace(cfg,initial_equity=7980.),
                  replace(cfg,risk_config=replace(cfg.risk_config,enforce_min_notional=155.)),
                  replace(cfg,risk_config=replace(cfg.risk_config,min_position_notional=70.))]:
        with pytest.raises(ValueError):minimum_only(wrong)
    with pytest.raises(ValueError):minimum_only(cfg,77.69)


def test_native_size_constraint_accepts_lower_ticket_without_raising_risk_budget():
    from risk_management.constraints import ConstraintChecker,PortfolioState
    cfg=fixture();changed=minimum_only(cfg)
    assert cfg.risk_config.risk_per_trade_pct==changed.risk_config.risk_per_trade_pct==.0125
    assert cfg.risk_config.max_portfolio_drawdown_pct==changed.risk_config.max_portfolio_drawdown_pct==.15
    assert cfg.risk_config.effective_min_notional>100.>changed.risk_config.effective_min_notional
    rejected,reason=ConstraintChecker(cfg.risk_config).check('AAA','S',10,10.,PortfolioState(),adv_usd=1e8)
    accepted,accepted_reason=ConstraintChecker(changed.risk_config).check('AAA','S',10,10.,PortfolioState(),adv_usd=1e8)
    assert rejected==0 and reason=='min_position_notional non atteint'
    assert accepted==10 and accepted_reason=='OK'
