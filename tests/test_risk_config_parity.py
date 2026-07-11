"""Tests pour les contraintes directionnelles et la configuration — Sprint Maître 6."""

from __future__ import annotations

import pytest

from risk_management.config import RiskConfig
from risk_management.constraints import ConstraintChecker, PortfolioState
from core.ml_selection_contract import SelectionCapacity
from core.direction import compute_initial_stop_price


# ── PortfolioState directionnel ─────────────────────────────────────────────

def test_portfolio_state_defaults() -> None:
    state = PortfolioState()
    assert state.position_count == 0
    assert state.long_count == 0
    assert state.short_count == 0
    assert state.gross_notional == 0.0
    assert state.net_notional == 0.0


def test_portfolio_state_add_long() -> None:
    state = PortfolioState()
    state.add_position(notional=5000.0, sector="Tech", side="long", symbol="AAPL")
    assert state.position_count == 1
    assert state.long_count == 1
    assert state.short_count == 0
    assert state.long_notional == 5000.0
    assert state.short_notional == 0.0
    assert state.gross_notional == 5000.0
    assert state.net_notional == 5000.0
    assert state.sector_notional["Tech"] == 5000.0


def test_portfolio_state_add_short() -> None:
    state = PortfolioState()
    state.add_position(notional=3000.0, sector="Finance", side="short", symbol="JPM")
    assert state.short_count == 1
    assert state.short_notional == 3000.0
    assert state.long_count == 0
    assert state.net_notional == -3000.0


def test_portfolio_state_mixed() -> None:
    state = PortfolioState()
    state.add_position(notional=10000.0, sector="Tech", side="long", symbol="AAPL")
    state.add_position(notional=4000.0, sector="Tech", side="short", symbol="NVDA")
    assert state.position_count == 2
    assert state.long_count == 1
    assert state.short_count == 1
    assert state.long_notional == 10000.0
    assert state.short_notional == 4000.0
    assert state.gross_notional == 14000.0
    assert state.net_notional == 6000.0
    assert state.sector_notional["Tech"] == 14000.0


# ── Contraintes directionnelles ─────────────────────────────────────────────

@pytest.fixture
def risk_cfg() -> RiskConfig:
    return RiskConfig(
        account_equity=100_000.0,
        max_positions=10,
        max_long_positions=8,
        max_short_positions=3,
        max_position_weight=0.10,
        max_sector_weight=0.30,
        max_gross_exposure=1.0,
    )


def test_constraint_max_long_positions(risk_cfg) -> None:
    checker = ConstraintChecker(risk_cfg)
    state = PortfolioState()
    # Remplir à 8 longs
    for i in range(8):
        state.add_position(notional=1000.0, sector="X", side="long", symbol=f"S{i}")
    shares, reason = checker.check("S9", "X", 10.0, 100.0, state, side="long")
    assert shares == 0.0
    assert "max_long_positions" in reason


def test_constraint_max_short_positions(risk_cfg) -> None:
    checker = ConstraintChecker(risk_cfg)
    state = PortfolioState()
    for i in range(3):
        state.add_position(notional=1000.0, sector="X", side="short", symbol=f"S{i}")
    shares, reason = checker.check("S4", "X", 10.0, 100.0, state, side="short")
    assert shares == 0.0
    assert "max_short_positions" in reason


def test_constraint_long_not_limited_by_short_cap(risk_cfg) -> None:
    """Le cap short ne limite pas les longs."""
    checker = ConstraintChecker(risk_cfg)
    state = PortfolioState()
    # Remplir 3 shorts (max atteint)
    for i in range(3):
        state.add_position(notional=1000.0, sector="X", side="short", symbol=f"S{i}")
    # Un long doit passer
    shares, reason = checker.check("L1", "X", 10.0, 100.0, state, side="long")
    assert shares > 0
    assert reason == "OK"


# ── ADV fail-closed ─────────────────────────────────────────────────────────

def test_adv_fail_closed_rejects_missing_adv() -> None:
    cfg = RiskConfig(account_equity=100_000.0, max_position_pct_of_adv=0.01)
    checker = ConstraintChecker(cfg)
    state = PortfolioState()
    shares, reason = checker.check("AAPL", "Tech", 100.0, 150.0, state, adv_usd=None)
    assert shares == 0.0
    assert reason == "adv_unavailable"


def test_adv_fail_closed_rejects_zero_adv() -> None:
    cfg = RiskConfig(account_equity=100_000.0, max_position_pct_of_adv=0.01)
    checker = ConstraintChecker(cfg)
    state = PortfolioState()
    shares, reason = checker.check("AAPL", "Tech", 100.0, 150.0, state, adv_usd=0.0)
    assert shares == 0.0
    assert reason == "adv_unavailable"


def test_adv_ok_when_not_configured() -> None:
    """Si max_position_pct_of_adv est None, ADV absent ne bloque pas."""
    cfg = RiskConfig(account_equity=100_000.0, max_position_pct_of_adv=None)
    checker = ConstraintChecker(cfg)
    state = PortfolioState()
    shares, reason = checker.check("AAPL", "Tech", 10.0, 100.0, state, adv_usd=None)
    assert shares > 0
    assert reason == "OK"


# ── Stop directionnel ───────────────────────────────────────────────────────

def test_stop_long_below_entry() -> None:
    stop = compute_initial_stop_price("buy", 100.0, risk_per_share=5.0)
    assert stop is not None
    assert stop < 100.0  # long: stop sous l'entrée


def test_stop_short_above_entry() -> None:
    stop = compute_initial_stop_price("sell", 100.0, risk_per_share=5.0)
    assert stop is not None
    assert stop > 100.0  # short: stop au-dessus de l'entrée


# ── Gross/net ───────────────────────────────────────────────────────────────

def test_gross_notional_sum_of_long_and_short() -> None:
    state = PortfolioState()
    state.add_position(notional=7000.0, sector="A", side="long")
    state.add_position(notional=3000.0, sector="A", side="short")
    assert state.gross_notional == 10000.0


def test_net_notional_long_minus_short() -> None:
    state = PortfolioState()
    state.add_position(notional=7000.0, sector="A", side="long")
    state.add_position(notional=3000.0, sector="A", side="short")
    assert state.net_notional == 4000.0


# ── RiskConfig fingerprint ──────────────────────────────────────────────────

def test_risk_config_fingerprint_is_stable() -> None:
    cfg1 = RiskConfig(account_equity=100_000.0, max_positions=10)
    cfg2 = RiskConfig(account_equity=100_000.0, max_positions=10)
    assert cfg1.fingerprint == cfg2.fingerprint


def test_risk_config_fingerprint_changes_with_param() -> None:
    cfg1 = RiskConfig(account_equity=100_000.0)
    cfg2 = RiskConfig(account_equity=200_000.0)
    assert cfg1.fingerprint != cfg2.fingerprint


def test_risk_config_to_dict_roundtrip() -> None:
    cfg = RiskConfig(
        account_equity=150_000.0,
        max_positions=15,
        max_short_positions=5,
        correlation_threshold=0.75,
    )
    d = cfg.to_dict(exclude_defaults=False)
    restored = RiskConfig.from_dict(d)
    assert restored.account_equity == 150_000.0
    assert restored.max_short_positions == 5
    assert restored.fingerprint == cfg.fingerprint


def test_risk_config_rejects_unknown_keys() -> None:
    with pytest.raises(ValueError, match="Clés inconnues"):
        RiskConfig.from_dict({"account_equity": 100000, "fantasy_key": 123})


def test_risk_config_with_overrides() -> None:
    cfg = RiskConfig(account_equity=100_000.0)
    overridden = cfg.with_overrides(max_positions=5, correlation_threshold=0.70)
    assert overridden.max_positions == 5
    assert overridden.correlation_threshold == 0.70
    assert overridden.account_equity == 100_000.0
    assert overridden.fingerprint != cfg.fingerprint


def test_risk_config_with_overrides_rejects_unknown() -> None:
    cfg = RiskConfig()
    with pytest.raises(ValueError, match="Overrides inconnus"):
        cfg.with_overrides(fake_param=42)  # type: ignore[call-arg]
