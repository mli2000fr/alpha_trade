"""Tests unitaires — risk_management/capacity.py (Sprint Maître 10).

Vérifie : CapacityEstimate, CapacityEstimator (symbol, sector, strategy).
"""

from __future__ import annotations

import pytest

from risk_management.capacity import (
    CapacityEstimate,
    CapacityEstimator,
    estimate_symbol_capacity,
)


# ── CapacityEstimate ────────────────────────────────────────────────────────


class TestCapacityEstimate:
    def test_basic_estimate(self) -> None:
        cap = CapacityEstimate(
            scope="symbol", scope_key="AAPL",
            max_notional=100_000, adv_usd=10_000_000,
        )
        assert cap.scope == "symbol"
        assert cap.scope_key == "AAPL"
        assert cap.max_notional == 100_000

    def test_max_shares_at_price(self) -> None:
        cap = CapacityEstimate(
            scope="symbol", scope_key="AAPL",
            max_notional=100_000, adv_usd=10_000_000,
        )
        assert cap.max_shares_at_price(150.0) == 666  # 100000/150 = 666.66 → 666

    def test_max_shares_zero_price(self) -> None:
        cap = CapacityEstimate(scope="symbol", scope_key="AAPL", max_notional=100_000)
        assert cap.max_shares_at_price(0) == 0
        assert cap.max_shares_at_price(-10) == 0

    def test_to_dict(self) -> None:
        cap = CapacityEstimate(
            scope="symbol", scope_key="AAPL",
            max_notional=100_000, max_shares=666,
            turnover_days=0.5, adv_usd=10_000_000,
            is_constrained_by_adv=False,
        )
        d = cap.to_dict()
        assert d["scope"] == "symbol"
        assert d["max_notional"] == 100_000.0
        assert d["max_shares"] == 666


# ── CapacityEstimator — estimate_symbol ─────────────────────────────────────


class TestCapacityEstimatorSymbol:
    def test_basic_estimate(self) -> None:
        estimator = CapacityEstimator()
        cap = estimator.estimate_symbol("AAPL", adv_usd=10_000_000)
        # Capacity is constrained by slippage limit (50 bps default)
        # For $10M ADV with default 5 bps spread: capacity ≈ $22.5K
        assert cap.max_notional > 0
        assert cap.scope == "symbol"
        assert cap.scope_key == "AAPL"
        assert cap.is_constrained_by_adv is False

    def test_low_adv_zero_capacity(self) -> None:
        estimator = CapacityEstimator(min_adv_for_capacity=1_000_000)
        cap = estimator.estimate_symbol("PENNY", adv_usd=100_000)
        assert cap.max_notional == 0.0
        assert cap.is_constrained_by_adv is True

    def test_high_spread_reduces_capacity(self) -> None:
        estimator = CapacityEstimator(max_spread_bps=20.0)
        cap_normal = estimator.estimate_symbol("AAPL", adv_usd=10_000_000, spread_bps=5.0)
        cap_wide = estimator.estimate_symbol("AAPL", adv_usd=10_000_000, spread_bps=50.0)
        assert cap_wide.max_notional < cap_normal.max_notional
        assert cap_wide.is_constrained_by_spread is True

    def test_with_price(self) -> None:
        estimator = CapacityEstimator()
        cap = estimator.estimate_symbol("AAPL", adv_usd=10_000_000, price=150.0)
        # Capacity ≈ $22.5K → shares ≈ 150
        assert cap.max_shares is not None
        assert cap.max_shares > 0

    def test_zero_adv(self) -> None:
        estimator = CapacityEstimator()
        cap = estimator.estimate_symbol("DEAD", adv_usd=0)
        assert cap.max_notional == 0.0
        assert cap.is_constrained_by_adv is True

    def test_turnover_days_computed(self) -> None:
        estimator = CapacityEstimator()
        cap = estimator.estimate_symbol("AAPL", adv_usd=10_000_000)
        # Turnover days = max_notional / daily_capacity
        # With slippage-constrained max_notional ≈ $22.5K
        # daily_capacity = 10M * 1% = 100K
        # turnover_days = 22.5K / 100K ≈ 0.225
        assert cap.turnover_days > 0
        assert cap.turnover_days_stressed > cap.turnover_days

    def test_slippage_constrained_capacity(self) -> None:
        """Quand le slippage estimé dépasse max_slippage_bps, la capacité est réduite."""
        estimator = CapacityEstimator(max_slippage_bps=10.0)
        # Avec ADV petit, même un petit notional cause un slippage élevé
        cap = estimator.estimate_symbol("ILLIQUID", adv_usd=500_000, spread_bps=20.0)
        # half_spread = 10 bps → déjà au max → capacité quasi nulle
        assert cap.max_notional < 50_000  # Très limité


# ── CapacityEstimator — estimate_sector ─────────────────────────────────────


class TestCapacityEstimatorSector:
    def test_sector_aggregation(self) -> None:
        estimator = CapacityEstimator()
        symbols = ["AAPL", "MSFT", "GOOGL"]
        adv_map = {"AAPL": 10_000_000, "MSFT": 8_000_000, "GOOGL": 6_000_000}
        cap = estimator.estimate_sector("Tech", symbols, adv_map)
        # Each symbol is slippage-constrained, sum × 0.70 discount
        assert cap.max_notional > 0
        assert cap.scope == "sector"
        assert cap.scope_key == "Tech"
        assert cap.adv_usd == 24_000_000

    def test_empty_sector(self) -> None:
        estimator = CapacityEstimator()
        cap = estimator.estimate_sector("Empty", [], {})
        assert cap.max_notional == 0.0

    def test_sector_with_spreads(self) -> None:
        estimator = CapacityEstimator(max_spread_bps=20.0)
        symbols = ["AAPL", "ILLIQUID"]
        adv_map = {"AAPL": 10_000_000, "ILLIQUID": 1_000_000}
        spread_map = {"AAPL": 5.0, "ILLIQUID": 100.0}
        cap = estimator.estimate_sector("Mixed", symbols, adv_map, spread_map)
        # ILLIQUID a un spread > max → capacité réduite
        assert cap.is_constrained_by_spread is True


# ── CapacityEstimator — estimate_strategy ───────────────────────────────────


class TestCapacityEstimatorStrategy:
    def test_strategy_capacity(self) -> None:
        estimator = CapacityEstimator()
        caps = [
            CapacityEstimate("symbol", "AAPL", max_notional=100_000, adv_usd=10_000_000),
            CapacityEstimate("symbol", "MSFT", max_notional=80_000, adv_usd=8_000_000),
            CapacityEstimate("symbol", "GOOGL", max_notional=60_000, adv_usd=6_000_000),
            CapacityEstimate("symbol", "PENNY", max_notional=5_000, adv_usd=500_000),
        ]
        cap = estimator.estimate_strategy("momentum", caps, max_positions=3)
        # Top 3: AAPL(100K) + MSFT(80K) + GOOGL(60K) = 240K
        # diversification: sqrt(3) * 0.60 = 1.039 > 1.0 → min(1.039, 1.0) = 1.0
        assert cap.scope == "strategy"
        assert cap.scope_key == "momentum"
        assert cap.max_notional == pytest.approx(240_000.0)

    def test_correlation_reduces_capacity(self) -> None:
        estimator = CapacityEstimator()
        caps = [CapacityEstimate("symbol", f"STOCK_{i}", max_notional=100_000) for i in range(20)]
        # sqrt(20) * 0.6 = 2.68 > 1 → diversification capped at 1.0
        cap_low_corr = estimator.estimate_strategy("strat", caps, correlation_factor=0.60)
        # sqrt(20) * 0.1 = 0.447 < 1 → capacity reduced
        cap_high_corr = estimator.estimate_strategy("strat", caps, correlation_factor=0.10)
        assert cap_high_corr.max_notional < cap_low_corr.max_notional

    def test_max_positions_limits(self) -> None:
        estimator = CapacityEstimator()
        caps = [CapacityEstimate("symbol", f"STOCK_{i}", max_notional=100_000) for i in range(100)]
        cap = estimator.estimate_strategy("strat", caps, max_positions=10)
        # Only top 10 counted
        assert cap.max_notional == pytest.approx(10 * 100_000)


# ── estimate_symbol_capacity (helper) ───────────────────────────────────────


class TestEstimateSymbolCapacity:
    def test_helper(self) -> None:
        cap = estimate_symbol_capacity("AAPL", 10_000_000)
        # Slippage-constrained, but positive
        assert cap.max_notional > 0

    def test_helper_with_custom_participation(self) -> None:
        cap = estimate_symbol_capacity("AAPL", 10_000_000, max_participation_pct=0.02)
        # Higher participation allows more capacity, but still slippage-constrained
        assert cap.max_notional > 0

    def test_helper_with_spread_and_price(self) -> None:
        cap = estimate_symbol_capacity("AAPL", 10_000_000, spread_bps=5.0, price=150.0)
        assert cap.max_shares is not None
        assert cap.max_shares > 0
