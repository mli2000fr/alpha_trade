"""Tests pour ``risk_management/regime_apply.py`` (Axe B)."""
from __future__ import annotations

from datetime import date

from risk_management.config import RiskConfig
from risk_management.regime_apply import apply_snapshot
from service.market.models import MarketRegimeSnapshot


def _make_snap(**kwargs) -> MarketRegimeSnapshot:
    base = {"trade_date": date(2025, 5, 1)}
    base.update(kwargs)
    return MarketRegimeSnapshot(**base)  # type: ignore[arg-type]


def test_apply_snapshot_none_returns_same_cfg():
    cfg = RiskConfig()
    assert apply_snapshot(cfg, None) is cfg


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


