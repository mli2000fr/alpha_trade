"""Tests unitaires — risk_management/portfolio_optimizer.py (Sprint Maître 11).

Vérifie : HoldingSnapshot, NoTradeBand, TurnoverCosts,
MarginalRiskDecomposition, PortfolioOptimizer, compute_mctr.
"""

from __future__ import annotations

import numpy as np
import pytest

from risk_management.portfolio_optimizer import (
    HoldingSnapshot,
    MarginalRiskDecomposition,
    NoTradeBand,
    OptimizationResult,
    PortfolioOptimizer,
    TurnoverCosts,
    compute_mctr,
    optimize_portfolio,
)


# ── HoldingSnapshot ─────────────────────────────────────────────────────────


class TestHoldingSnapshot:
    def test_long_holding(self) -> None:
        h = HoldingSnapshot("AAPL", side="long", quantity=100, current_price=150.0)
        assert h.notional == 15000.0
        assert h.signed_notional == 15000.0

    def test_short_holding(self) -> None:
        h = HoldingSnapshot("TSLA", side="short", quantity=50, current_price=200.0)
        assert h.notional == 10000.0
        assert h.signed_notional == -10000.0

    def test_rejects_invalid_side(self) -> None:
        with pytest.raises(ValueError, match="side"):
            HoldingSnapshot("AAPL", side="both")

    def test_with_open_order(self) -> None:
        h = HoldingSnapshot("AAPL", has_open_order=True, open_order_side="sell", open_order_quantity=50)
        assert h.has_open_order is True

    def test_metadata_fields(self) -> None:
        h = HoldingSnapshot(
            "AAPL", sector="Tech", industry="Software",
            country="US", currency="USD", theme="AI",
        )
        assert h.sector == "Tech"
        assert h.industry == "Software"
        assert h.country == "US"
        assert h.theme == "AI"


# ── NoTradeBand ─────────────────────────────────────────────────────────────


class TestNoTradeBand:
    def test_within_band_skips(self) -> None:
        band = NoTradeBand(lower_pct=0.20, upper_pct=0.20)
        skip, reason = band.should_skip_trade(100, 110, 150.0)  # +10% dans bande
        assert skip is True

    def test_outside_band_trades(self) -> None:
        band = NoTradeBand(lower_pct=0.20, upper_pct=0.20)
        skip, reason = band.should_skip_trade(100, 130, 150.0)  # +30% hors bande
        assert skip is False

    def test_no_existing_position_trades(self) -> None:
        band = NoTradeBand()
        skip, reason = band.should_skip_trade(0, 100, 150.0)
        assert skip is False

    def test_below_min_notional_skips(self) -> None:
        band = NoTradeBand(min_notional_to_trade=500.0)
        skip, reason = band.should_skip_trade(100, 130, 10.0)  # delta=30*10=300 < 500
        assert skip is True

    def test_above_min_notional_trades(self) -> None:
        band = NoTradeBand(min_notional_to_trade=500.0)
        skip, reason = band.should_skip_trade(100, 130, 20.0)  # delta=30*20=600 > 500
        assert skip is False

    def test_reduce_below_lower_band_trades(self) -> None:
        band = NoTradeBand(lower_pct=0.20)
        skip, reason = band.should_skip_trade(100, 70, 150.0)  # -30% hors bande
        assert skip is False


# ── TurnoverCosts ───────────────────────────────────────────────────────────


class TestTurnoverCosts:
    def test_cost_of_trade(self) -> None:
        tc = TurnoverCosts(total_one_way_bps=5.5)
        cost = tc.cost_of_trade(100_000)
        assert cost == pytest.approx(55.0)  # 100000 * 5.5/10000 = 55

    def test_cost_with_adv(self) -> None:
        tc = TurnoverCosts(total_one_way_bps=5.0, market_impact_bps_per_pct_adv=2.0)
        cost_no_adv = tc.cost_of_trade(100_000)
        cost_with_adv = tc.cost_of_trade(100_000, adv_usd=10_000_000)
        # Avec ADV, l'impact de marché est ajouté
        assert cost_with_adv > cost_no_adv

    def test_cost_of_rebalance_zero(self) -> None:
        tc = TurnoverCosts()
        cost = tc.cost_of_rebalance(50_000, 50_000)
        assert cost == 0.0

    def test_cost_of_rebalance_delta(self) -> None:
        tc = TurnoverCosts(total_one_way_bps=10.0)
        cost = tc.cost_of_rebalance(0, 100_000)
        assert cost == pytest.approx(100.0)  # 100000 * 10/10000 = 100

    def test_annualized_turnover_impact(self) -> None:
        tc = TurnoverCosts(total_one_way_bps=5.0)
        impact = tc.annualized_turnover_impact(0.10, 252)  # 10% daily turnover
        assert impact > 0


# ── MarginalRiskDecomposition ───────────────────────────────────────────────


class TestMarginalRiskDecomposition:
    def test_empty(self) -> None:
        m = MarginalRiskDecomposition()
        assert m.total_risk == 0.0
        assert len(m.symbols) == 0

    def test_to_dict(self) -> None:
        m = MarginalRiskDecomposition(
            weights=np.array([0.5, 0.5]),
            total_risk=0.15,
            symbols=["A", "B"],
        )
        d = m.to_dict()
        assert d["total_risk"] == 0.15
        assert d["n_positions"] == 2


# ── compute_mctr ────────────────────────────────────────────────────────────


class TestComputeMCTR:
    def test_two_assets(self) -> None:
        weights = np.array([0.6, 0.4])
        cov = np.array([[0.04, 0.01], [0.01, 0.09]])
        decomp = compute_mctr(weights, cov, ["A", "B"])
        assert decomp.total_risk > 0
        assert len(decomp.mctr) == 2
        # Risk contributions sum to total variance
        assert sum(decomp.risk_contributions) == pytest.approx(decomp.total_risk ** 2, rel=0.01)
        assert decomp.worst_contributor_symbol is not None

    def test_single_asset(self) -> None:
        weights = np.array([1.0])
        cov = np.array([[0.04]])
        decomp = compute_mctr(weights, cov, ["A"])
        assert decomp.total_risk == pytest.approx(0.2)  # sqrt(0.04)

    def test_empty(self) -> None:
        decomp = compute_mctr(np.array([]), np.array([]), [])
        assert decomp.total_risk == 0.0

    def test_zero_variance(self) -> None:
        weights = np.array([0.5, 0.5])
        cov = np.zeros((2, 2))
        decomp = compute_mctr(weights, cov, ["A", "B"])
        assert decomp.total_risk == 0.0


# ── PortfolioOptimizer ──────────────────────────────────────────────────────


class TestPortfolioOptimizer:
    def _make_candidate(self, symbol, side="long", edge=0.05, qty=100, price=100.0, sector=None):
        return {
            "symbol": symbol, "side": side, "edge": edge,
            "proposed_quantity": qty, "price": price, "sector": sector,
        }

    def test_empty_candidates(self) -> None:
        opt = PortfolioOptimizer()
        result = opt.optimize([], account_equity=100_000)
        assert len(result.target_weights) == 0
        assert result.turnover_pct == 0.0

    def test_single_candidate_accepted(self) -> None:
        opt = PortfolioOptimizer(max_position_weight=0.20)  # Raise cap to fit 15K
        result = opt.optimize(
            [self._make_candidate("AAPL", edge=0.08, qty=100, price=150.0)],
            account_equity=100_000,
        )
        assert "AAPL" in result.target_weights
        assert result.target_quantities["AAPL"] > 0

    def test_max_positions_non_greedy(self) -> None:
        """Avec max_positions=2, on a exactement 2 positions retenues."""
        opt = PortfolioOptimizer(max_positions=2, max_position_weight=0.10)
        candidates = [
            self._make_candidate("A", edge=0.10, qty=50, price=100.0),
            self._make_candidate("B", edge=0.07, qty=50, price=100.0),
            self._make_candidate("C", edge=0.09, qty=50, price=100.0),
        ]
        result = opt.optimize(candidates, account_equity=100_000)
        # Exactement 2 positions dans le portefeuille final
        assert len(result.target_weights) == 2

    def test_gross_exposure_limit(self) -> None:
        opt = PortfolioOptimizer(max_gross_exposure=0.15)
        candidates = [
            self._make_candidate("A", edge=0.10, qty=100, price=100.0),  # 10K = 10%
            self._make_candidate("B", edge=0.08, qty=100, price=100.0),  # 10K → réduit
        ]
        result = opt.optimize(candidates, account_equity=100_000)
        # B est réduit pour fitter dans 15% gross
        assert "B" in result.reduced_symbols or result.target_quantities.get("B", 0) < 100

    def test_position_weight_cap(self) -> None:
        opt = PortfolioOptimizer(max_position_weight=0.05)
        candidates = [
            self._make_candidate("BIG", edge=0.15, qty=1000, price=100.0),  # 100K = 100% → réduit
        ]
        result = opt.optimize(candidates, account_equity=100_000)
        if "BIG" in result.target_quantities:
            assert result.target_quantities["BIG"] <= 500  # max 50K / 100 = 500

    def test_existing_holdings_included(self) -> None:
        opt = PortfolioOptimizer()
        holdings = [
            HoldingSnapshot("AAPL", side="long", quantity=100, current_price=150.0),
        ]
        result = opt.optimize([], holdings, account_equity=100_000)
        assert "AAPL" in result.target_weights
        # Pas de trade si pas de changement
        assert "AAPL" not in result.trades

    def test_existing_holdings_generate_trades(self) -> None:
        opt = PortfolioOptimizer(max_position_weight=0.20)
        opt.no_trade_band = NoTradeBand(lower_pct=0.0, upper_pct=0.0)  # Désactive no-trade
        holdings = [
            HoldingSnapshot("AAPL", side="long", quantity=50, current_price=150.0),
        ]
        candidates = [
            self._make_candidate("AAPL", edge=0.08, qty=100, price=150.0),
        ]
        result = opt.optimize(candidates, holdings, account_equity=100_000)
        # Trade = 100 - 50 = +50
        assert result.trades.get("AAPL") == 50.0

    def test_replacing_holding_does_not_double_count_gross_exposure(self) -> None:
        opt = PortfolioOptimizer(max_gross_exposure=0.20, max_position_weight=0.20)
        holdings = [HoldingSnapshot("AAPL", side="long", quantity=100, current_price=100.0)]

        result = opt.optimize(
            [self._make_candidate("AAPL", edge=0.08, qty=150, price=100.0)],
            holdings,
            account_equity=100_000,
        )

        assert result.target_quantities["AAPL"] == 150.0
        assert "AAPL" not in result.rejected_symbols

    def test_signed_net_exposure_limit_reduces_same_side_candidate(self) -> None:
        opt = PortfolioOptimizer(
            max_gross_exposure=1.0,
            max_net_exposure=0.10,
            max_position_weight=0.50,
        )

        result = opt.optimize(
            [self._make_candidate("AAPL", edge=0.08, qty=200, price=100.0)],
            account_equity=100_000,
        )

        assert result.target_quantities["AAPL"] == 100.0
        assert result.reduced_symbols["AAPL"][1] == "max_net_exposure"

    def test_no_trade_band_skips(self) -> None:
        opt = PortfolioOptimizer(max_position_weight=0.20)
        opt.no_trade_band = NoTradeBand(lower_pct=0.20, upper_pct=0.20)
        holdings = [
            HoldingSnapshot("AAPL", side="long", quantity=100, current_price=150.0),
        ]
        candidates = [
            self._make_candidate("AAPL", edge=0.08, qty=110, price=150.0),  # +10% → dans bande
        ]
        result = opt.optimize(candidates, holdings, account_equity=100_000)
        # Pas de trade, la position existante est conservée
        assert "AAPL" not in result.trades

    def test_blocked_by_open_order(self) -> None:
        opt = PortfolioOptimizer(max_position_weight=0.20)
        holdings = [
            HoldingSnapshot("AAPL", has_open_order=True, open_order_side="sell"),
        ]
        candidates = [
            self._make_candidate("AAPL", edge=0.08, qty=100, price=150.0),
        ]
        result = opt.optimize(candidates, holdings, account_equity=100_000)
        assert "AAPL" in result.rejected_symbols

    def test_deterministic_output(self) -> None:
        opt = PortfolioOptimizer()
        candidates = [
            self._make_candidate("A", edge=0.10, qty=50, price=100.0),
            self._make_candidate("B", edge=0.08, qty=50, price=100.0),
        ]
        r1 = opt.optimize(candidates, account_equity=100_000)
        r2 = opt.optimize(candidates, account_equity=100_000)
        assert r1.target_weights == r2.target_weights

    def test_audit_trail(self) -> None:
        opt = PortfolioOptimizer()
        result = opt.optimize(
            [self._make_candidate("AAPL", edge=0.08, qty=100, price=150.0)],
            account_equity=100_000,
        )
        assert len(result.audit_trail) > 0
        assert any("accept:AAPL" in t for t in result.audit_trail)

    def test_rejected_candidate(self) -> None:
        opt = PortfolioOptimizer(max_position_weight=0.01)
        candidates = [
            self._make_candidate("HUGE", edge=0.10, qty=10000, price=100.0),  # 1M > 1K max
        ]
        result = opt.optimize(candidates, account_equity=100_000)
        assert "HUGE" in result.rejected_symbols or "HUGE" in result.reduced_symbols

    def test_to_dict(self) -> None:
        result = OptimizationResult(
            target_weights={"A": 0.05},
            target_quantities={"A": 50},
            total_edge=0.05,
            rejected_symbols={"B": "max_positions"},
            reduced_symbols={"C": (30.0, "max_gross_exposure")},
        )
        d = result.to_dict()
        assert d["n_targets"] == 1
        assert d["n_rejected"] == 1
        assert d["n_reduced"] == 1


# ── optimize_portfolio (helper) ─────────────────────────────────────────────


class TestOptimizePortfolio:
    def test_helper(self) -> None:
        candidates = [{"symbol": "AAPL", "side": "long", "edge": 0.08, "proposed_quantity": 50, "price": 150.0}]
        result = optimize_portfolio(candidates, account_equity=100_000)
        assert "AAPL" in result.target_weights

    def test_helper_with_holdings(self) -> None:
        holdings = [HoldingSnapshot("AAPL", quantity=100, current_price=150.0)]
        result = optimize_portfolio([], holdings, account_equity=100_000)
        assert "AAPL" in result.target_weights
