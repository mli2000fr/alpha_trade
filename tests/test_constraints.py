"""Tests unitaires — ConstraintChecker."""
from __future__ import annotations

import pytest

from risk_management.config import RiskConfig
from risk_management.constraints import ConstraintChecker, PortfolioState


@pytest.fixture()
def config() -> RiskConfig:
    return RiskConfig(
        account_equity=100_000,
        max_positions=2,
        max_position_weight=0.10,
        max_sector_weight=0.20,
        max_gross_exposure=1.0,
        min_position_notional=500.0,
    )


@pytest.fixture()
def checker(config: RiskConfig) -> ConstraintChecker:
    return ConstraintChecker(config)


def test_max_positions(checker: ConstraintChecker) -> None:
    state = PortfolioState(position_count=2)
    shares, reason = checker.check("A", "Tech", 10, 50.0, state)
    assert shares == 0
    assert "max_positions" in reason


def test_max_position_weight(checker: ConstraintChecker) -> None:
    state = PortfolioState()
    # 200 shares * 100$ = 20000 => 20% > max 10%
    shares, reason = checker.check("A", "Tech", 200, 100.0, state)
    assert shares == 100  # réduit à 10000$


def test_max_sector_weight(checker: ConstraintChecker) -> None:
    state = PortfolioState(sector_notional={"Tech": 18_000})
    # 18000 + 50*100=5000 > 20000 => limité à 2000/100=20
    shares, reason = checker.check("B", "Tech", 50, 100.0, state)
    assert shares == 20


def test_min_notional_rejection(checker: ConstraintChecker) -> None:
    state = PortfolioState()
    shares, reason = checker.check("C", "Health", 1, 100.0, state)
    assert shares == 0
    assert "min_position_notional" in reason


def test_ok_pass(checker: ConstraintChecker) -> None:
    state = PortfolioState()
    shares, reason = checker.check("D", "Energy", 10, 100.0, state)
    assert shares == 10
    assert reason == "OK"
