"""Tests sizer + constraints sur les nouveaux champs régime (Axe B, C16/C20/C21)."""
from __future__ import annotations

from risk_management.config import RiskConfig
from risk_management.constraints import ConstraintChecker, PortfolioState
from risk_management.models import PriceInfo
from risk_management.position_sizer import PositionSizer


def _pi(symbol="AAPL", price=100.0, atr=2.0):
    return PriceInfo(symbol=symbol, last_close=price, atr_20=atr)


def test_sizer_uses_risk_multiplier():
    cfg = RiskConfig(account_equity=100_000, risk_per_trade_pct=0.01,
                     atr_stop_multiple=2.0, min_position_notional=100, risk_multiplier=0.5)
    res = PositionSizer(cfg).compute(_pi(price=100, atr=2))
    # budget = 100_000*0.01*0.5 = 500 ; risk/share = 4 ; shares = 125
    assert res.proposed_shares == 125
    assert res.method == "atr"


def test_sizer_enforce_min_notional_rejects():
    cfg = RiskConfig(account_equity=2000, risk_per_trade_pct=0.01,
                     atr_stop_multiple=2.0, min_position_notional=10,
                     enforce_min_notional=155.0)
    # budget = 2000*0.01 = 20 ; risk/share = 4 ; shares = 5 ; notional = 500 OK
    res = PositionSizer(cfg).compute(_pi(price=100, atr=2))
    assert res.proposed_shares == 5
    # mais avec un prix tel que notional < 155 on rejette
    res2 = PositionSizer(cfg).compute(_pi(price=10, atr=2))
    assert res2.proposed_shares == 0
    assert res2.method == "rejected_notional_below_enforced"


def test_constraint_max_tickers_per_sector():
    cfg = RiskConfig(max_tickers_per_sector=2, min_position_notional=100, max_positions=10)
    state = PortfolioState()
    checker = ConstraintChecker(cfg)
    # Première et seconde acceptées, la troisième dans le même secteur rejetée
    state.sector_ticker_count = {"Tech": 2}
    approved, reason = checker.check("AAPL", "Tech", 1, 200.0, state)
    assert approved == 0
    assert reason == "max_tickers_per_sector atteint"


def test_constraint_uses_effective_max_positions():
    cfg = RiskConfig(max_positions=20, effective_max_positions_override=2,
                     min_position_notional=100)
    state = PortfolioState(position_count=2)
    checker = ConstraintChecker(cfg)
    approved, reason = checker.check("AAPL", "Tech", 1, 200.0, state)
    assert approved == 0
    assert reason == "max_positions atteint"

