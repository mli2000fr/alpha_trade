from copy import deepcopy
from dataclasses import asdict

import pytest

from scripts.research.us_winner_risk_tradeoff_20261107 import build_cases,check_reproduction
from scripts.research.us_winner_ui_grid_20261107 import cases,configuration


def reference():
    from risk_management.config import RiskConfig
    from common.winner_pyramiding import WinnerPyramidingConfig
    from execution_engine.config import LeverageConfig
    return dict(arguments=dict(margin_interest_annual=.065),
        risk=asdict(RiskConfig(account_equity=4000.,force_close_on_breaker=False,
                              enable_factor_model=False,max_gross_exposure=2.)),
        winner_policy=asdict(WinnerPyramidingConfig(enabled=True,initial_position_fraction=1.,
            confirmation_bars=0,stop_loss_pct=.05,take_profit_pct=None,horizon_sessions=10,trailing_stop_pct=None)),
        leverage=asdict(LeverageConfig(enabled=True,mode='regt_swing',max_leverage=2.)))


def test_sixteen_cases_change_no_selection_or_exit_and_preserve_anchors():
    anchors=[c for c in cases() if c['name'] in ('Q051','Q088')]
    original=deepcopy(anchors)
    variants=build_cases(anchors)
    assert len(variants)==16 and len({v['name'] for v in variants})==16
    for anchor in anchors:
        group=[v for v in variants if v['anchor']==anchor['name']]
        assert len(group)==8
        assert len({tuple(v['risk_axes'].values()) for v in group})==8
        assert all(v['selection']==anchor['selection'] and v['policy']==anchor['policy'] and v['daily']==anchor['daily'] for v in group)
    assert anchors==original


def test_native_configuration_uses_dd15_liquidation_only_when_requested_and_applies_entry_caps():
    anchors=[c for c in cases() if c['name'] in ('Q051','Q088')]
    ref=reference();frozen=deepcopy(ref)
    for variant in build_cases(anchors):
        cfg=configuration(ref,variant)
        axes=variant['risk_axes']
        assert cfg.risk_config.risk_per_trade_pct==(.0125 if axes['reduce_entry_size'] else .025)
        assert cfg.risk_config.max_position_weight==(.2 if axes['reduce_entry_size'] else .4)
        assert cfg.risk_config.max_gross_exposure==(1. if axes['gross_entry_cap_1x'] else 2.)
        assert cfg.exec_config.leverage.max_leverage==2.  # unchanged account capacity
        assert cfg.winner_drawdown_controller_enabled is axes['b4_dd15']
        assert cfg.risk_config.force_close_on_breaker is axes['b4_dd15']
        if axes['b4_dd15']:
            assert cfg.risk_config.max_portfolio_drawdown_pct==.15
            assert cfg.risk_config.force_close_pct==.5
        assert cfg.exec_config.winner_pyramiding.stop_loss_pct==.05
        assert cfg.exec_config.winner_pyramiding.horizon_sessions==10
        assert cfg.exec_config.winner_pyramiding.initial_position_fraction==1.
        assert cfg.exec_config.winner_pyramiding.confirmation_bars==0
    assert ref==frozen


def test_a_financial_difference_blocks_anchor_reproduction():
    original={k:1. for k in ('final_equity','return_pct','max_drawdown_pct','average_gross_capital',
        'maximum_gross_capital','costs','margin_interest','closed_lot_trades','winners','losers')}
    check_reproduction(dict(original),original)
    altered=dict(original,maximum_gross_capital=1.01)
    with pytest.raises(ValueError,match='maximum_gross_capital'):
        check_reproduction(altered,original)
