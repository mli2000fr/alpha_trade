"""Tests unitaires — RiskCheckerImpl."""
from __future__ import annotations

import pytest

from risk_management.circuit_breaker import PnLSnapshot
from risk_management.config import RiskConfig
from risk_management.constraints import PortfolioState
from risk_management.risk_checker import RiskCheckerImpl


@pytest.fixture()
def config() -> RiskConfig:
    return RiskConfig(account_equity=100_000, max_positions=5, max_position_weight=0.10)


def test_check_position_size_within_limits(config: RiskConfig) -> None:
    rc = RiskCheckerImpl(config, sector_map={"AAPL": "Tech"})
    approved = rc.check_position_size("AAPL", 50.0, 100.0)
    assert approved == 50.0
    assert rc.get_last_decision_reason() == "OK"
    assert rc.get_last_decision_reason_code() == "ok"


def test_circuit_breaker_rejects(config: RiskConfig) -> None:
    pnl = PnLSnapshot(portfolio_high_watermark=100_000, portfolio_current_value=80_000)
    rc = RiskCheckerImpl(config, pnl=pnl, sector_map={"AAPL": "Tech"})
    assert rc.is_circuit_breaker_active() is True
    approved = rc.check_position_size("AAPL", 50.0, 100.0)
    assert approved == 0.0
    assert rc.get_last_decision_reason_code() == "circuit_breaker_active"


def test_constraint_rejection_exposes_structured_reason_code(config: RiskConfig) -> None:
    rc = RiskCheckerImpl(config, state=PortfolioState(position_count=5), sector_map={"AAPL": "Tech"})

    approved = rc.check_position_size("AAPL", 50.0, 100.0)

    assert approved == 0.0
    assert rc.get_last_decision_reason() == "max_positions atteint"
    assert rc.get_last_decision_reason_code() == "constraint_max_positions"


def test_accept_updates_state(config: RiskConfig) -> None:
    state = PortfolioState()
    rc = RiskCheckerImpl(config, state=state, sector_map={"A": "Tech"})
    rc.accept("A", "Tech", 10.0, 100.0)
    assert state.position_count == 1
    assert state.total_notional == 1_000.0
    assert state.sector_notional is not None
    assert state.sector_notional["Tech"] == 1_000.0


def test_check_position_size_supports_fractional_reduction() -> None:
    cfg = RiskConfig(
        account_equity=1_000,
        max_positions=5,
        max_position_weight=0.05,
        min_position_notional=10.0,
        allow_fractional_shares=True,
    )
    rc = RiskCheckerImpl(cfg, sector_map={"AAPL": "Tech"})

    approved = rc.check_position_size("AAPL", 0.83, 100.0)

    assert approved == pytest.approx(0.5)
    assert rc.get_last_decision_reason() == "max_position_weight atteint"
    assert rc.get_last_decision_reason_code() == "constraint_max_position_weight"

