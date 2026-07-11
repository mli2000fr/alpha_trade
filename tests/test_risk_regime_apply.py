"""Tests pour ``risk_management/regime_apply.py`` (Axe B)."""
from __future__ import annotations

from datetime import date

from risk_management.config import RiskConfig
from risk_management.regime_apply import apply_snapshot, apply_structural_market_guards, apply_transition
from risk_management.regime_state_machine import RegimeState, RegimeTransition, TransitionAction
from service.market.config import MarketRegimesConfig
from service.market.models import MarketRegimeSnapshot


def _make_snap(**kwargs) -> MarketRegimeSnapshot:
    base = {"trade_date": date(2025, 5, 1)}
    base.update(kwargs)
    return MarketRegimeSnapshot(**base)  # type: ignore[arg-type]


def test_apply_snapshot_none_returns_same_cfg():
    cfg = RiskConfig()
    assert apply_snapshot(cfg, None) is cfg


def test_apply_structural_market_guards_none_returns_same_cfg():
    cfg = RiskConfig()
    assert apply_structural_market_guards(cfg, market_regimes_config=None, equity=2_000.0) is cfg


def test_apply_structural_market_guards_applies_min_notional_even_when_regime_disabled():
    cfg = RiskConfig(max_positions=20)
    market_cfg = MarketRegimesConfig(enabled=False, enforce_min_notional=155.0)

    new = apply_structural_market_guards(cfg, market_regimes_config=market_cfg, equity=2_000.0)

    assert new is not cfg
    assert new.enforce_min_notional == 155.0
    assert new.effective_min_notional == 155.0
    assert new.effective_max_positions_override == 12
    assert new.effective_max_positions == 12


def test_apply_structural_market_guards_blocks_slots_when_equity_below_min_notional():
    cfg = RiskConfig(max_positions=20)
    market_cfg = MarketRegimesConfig(enabled=False, enforce_min_notional=155.0)

    new = apply_structural_market_guards(cfg, market_regimes_config=market_cfg, equity=100.0)

    assert new.enforce_min_notional == 155.0
    assert new.effective_max_positions_override == 0
    assert new.effective_max_positions == 0


def test_apply_snapshot_risk_multiplier():
    cfg = RiskConfig()
    snap = _make_snap(risk_multiplier=0.4)
    new = apply_snapshot(cfg, snap)
    assert new.risk_multiplier == 0.4
    assert new is not cfg


def test_apply_snapshot_min_notional_override():
    cfg = RiskConfig()
    snap = _make_snap(enforced_min_notional=155.0)
    new = apply_snapshot(cfg, snap)
    assert new.enforce_min_notional == 155.0
    assert new.effective_min_notional == 155.0


def test_apply_snapshot_max_positions_override():
    cfg = RiskConfig(max_positions=20)
    snap = _make_snap(effective_max_positions=2)
    new = apply_snapshot(cfg, snap)
    assert new.effective_max_positions_override == 2
    assert new.effective_max_positions == 2


def test_apply_snapshot_max_tickers_per_sector():
    cfg = RiskConfig()
    snap = _make_snap(max_tickers_per_sector=2)
    new = apply_snapshot(cfg, snap)
    assert new.max_tickers_per_sector == 2


def test_apply_snapshot_combined():
    cfg = RiskConfig()
    snap = _make_snap(
        risk_multiplier=0.5,
        enforced_min_notional=155.0,
        effective_max_positions=3,
        max_tickers_per_sector=2,
    )
    new = apply_snapshot(cfg, snap)
    assert new.risk_multiplier == 0.5
    assert new.enforce_min_notional == 155.0
    assert new.effective_max_positions_override == 3
    assert new.max_tickers_per_sector == 2


def test_apply_snapshot_exposure_caps():
    cfg = RiskConfig(
        max_position_weight=0.30,
        max_sector_weight=0.55,
        max_gross_exposure=1.0,
    )
    snap = _make_snap(
        max_position_weight=0.15,
        max_sector_weight=0.20,
        max_gross_exposure=0.35,
    )
    new = apply_snapshot(cfg, snap)
    assert new.max_position_weight == 0.15
    assert new.max_sector_weight == 0.20
    assert new.max_gross_exposure == 0.35


def test_apply_transition_only_tightens_permissions_and_exposure() -> None:
    cfg = RiskConfig(max_long_positions=4, max_short_positions=3, max_gross_exposure=0.8)
    transition = RegimeTransition(
        from_state=RegimeState.NORMAL,
        to_state=RegimeState.CAPITAL_PRESERVATION,
        action=TransitionAction.LIQUIDATE_LONGS,
        risk_multiplier=0.3,
        max_gross_exposure=0.3,
        allow_new_entries=True,
        allow_long=False,
        allow_short=True,
    )

    adjusted = apply_transition(cfg, transition)

    assert adjusted.risk_multiplier == 0.3
    assert adjusted.max_gross_exposure == 0.3
    assert adjusted.max_long_positions == 0
    assert adjusted.max_short_positions == 3


