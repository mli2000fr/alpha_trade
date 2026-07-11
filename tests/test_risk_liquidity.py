"""Tests unitaires — risk_management/liquidity.py (Sprint Maître 10).

Vérifie : SpreadSnapshot, BorrowSnapshot, BorrowStatus,
ParticipationLimit, SlippageEstimator, LiquidityGate.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from risk_management.liquidity import (
    BorrowSnapshot,
    BorrowStatus,
    LiquidityGate,
    LiquidityGateResult,
    ParticipationLimit,
    SlippageEstimate,
    SlippageEstimator,
    SpreadSnapshot,
    check_liquidity_pre_entry,
)


# ── BorrowStatus ────────────────────────────────────────────────────────────


class TestBorrowStatus:
    def test_etb_is_shortable(self) -> None:
        assert BorrowStatus.EASY_TO_BORROW.is_shortable is True

    def test_htb_is_shortable(self) -> None:
        assert BorrowStatus.HARD_TO_BORROW.is_shortable is True

    def test_not_shortable(self) -> None:
        assert BorrowStatus.NOT_SHORTABLE.is_shortable is False

    def test_htb_requires_locate(self) -> None:
        assert BorrowStatus.HARD_TO_BORROW.requires_locate is True
        assert BorrowStatus.EASY_TO_BORROW.requires_locate is False

    def test_fee_multiplier(self) -> None:
        assert BorrowStatus.EASY_TO_BORROW.fee_multiplier == 1.0
        assert BorrowStatus.HARD_TO_BORROW.fee_multiplier == 5.0
        assert BorrowStatus.NOT_SHORTABLE.fee_multiplier == float("inf")


# ── SpreadSnapshot ──────────────────────────────────────────────────────────


class TestSpreadSnapshot:
    def test_valid_spread(self) -> None:
        s = SpreadSnapshot("AAPL", bid=149.95, ask=150.05, quote_time=datetime.now())
        assert s.is_available is True
        assert s.mid_price == pytest.approx(150.0)

    def test_invalid_bid_ge_ask(self) -> None:
        with pytest.raises(ValueError, match="bid"):
            SpreadSnapshot("AAPL", bid=150.0, ask=149.0)

    def test_missing_data_not_available(self) -> None:
        s = SpreadSnapshot("AAPL")
        assert s.is_available is False
        assert s.mid_price is None

    def test_stale_quote(self) -> None:
        old = datetime.now() - timedelta(seconds=400)
        s = SpreadSnapshot("AAPL", bid=149.0, ask=151.0, quote_time=old, max_age_seconds=300)
        assert s.is_stale is True

    def test_fresh_quote(self) -> None:
        recent = datetime.now()
        s = SpreadSnapshot("AAPL", bid=149.0, ask=151.0, quote_time=recent, max_age_seconds=300)
        assert s.is_stale is False

    def test_effective_spread_bps_computed(self) -> None:
        s = SpreadSnapshot("AAPL", bid=149.50, ask=150.50)
        # spread_bps = (150.50 - 149.50) / 150.0 * 10000 = 1.0/150.0*10000 = 66.67
        expected = (1.0 / 150.0) * 10000.0
        assert s.effective_spread_bps == pytest.approx(expected, rel=0.01)

    def test_effective_spread_bps_explicit(self) -> None:
        s = SpreadSnapshot("AAPL", spread_bps=10.0)
        assert s.effective_spread_bps == 10.0

    def test_zero_bid_not_available(self) -> None:
        s = SpreadSnapshot("AAPL", bid=0.0, ask=150.0)
        assert s.is_available is False


# ── BorrowSnapshot ──────────────────────────────────────────────────────────


class TestBorrowSnapshot:
    def test_etb_default(self) -> None:
        b = BorrowSnapshot("AAPL")
        assert b.status == BorrowStatus.EASY_TO_BORROW
        assert b.is_shortable is True
        assert b.is_htb_blocked is False

    def test_htb_without_locate_blocked(self) -> None:
        b = BorrowSnapshot(
            "GME", status=BorrowStatus.HARD_TO_BORROW,
            locate_required=True, locate_confirmed=False,
        )
        assert b.is_shortable is True
        assert b.is_htb_blocked is True

    def test_htb_with_locate_not_blocked(self) -> None:
        b = BorrowSnapshot(
            "GME", status=BorrowStatus.HARD_TO_BORROW,
            locate_required=True, locate_confirmed=True,
        )
        assert b.is_htb_blocked is False

    def test_not_shortable(self) -> None:
        b = BorrowSnapshot("BANKRUPT", status=BorrowStatus.NOT_SHORTABLE)
        assert b.is_shortable is False
        assert b.quantity_available == 0

    def test_effective_fee_etb(self) -> None:
        b = BorrowSnapshot("AAPL", fee_annual=0.003)
        assert b.effective_fee_annual == 0.003

    def test_effective_fee_not_shortable(self) -> None:
        b = BorrowSnapshot("BANKRUPT", status=BorrowStatus.NOT_SHORTABLE)
        assert b.effective_fee_annual == float("inf")

    def test_edge_cost_for_holding(self) -> None:
        b = BorrowSnapshot("AAPL", fee_annual=0.003)
        cost = b.edge_cost_for_holding(holding_days=10)
        assert cost == pytest.approx(0.003 * 10 / 252.0)

    def test_edge_cost_not_shortable_is_infinite(self) -> None:
        b = BorrowSnapshot("BANKRUPT", status=BorrowStatus.NOT_SHORTABLE)
        assert b.edge_cost_for_holding(10) == float("inf")

    def test_recall_risk_bounds(self) -> None:
        with pytest.raises(ValueError, match="recall_risk"):
            BorrowSnapshot("AAPL", recall_risk=1.5)

    def test_htb_auto_sets_locate_required(self) -> None:
        b = BorrowSnapshot("GME", status=BorrowStatus.HARD_TO_BORROW)
        assert b.locate_required is True


# ── ParticipationLimit ──────────────────────────────────────────────────────


class TestParticipationLimit:
    def test_default_entry_limit(self) -> None:
        limit = ParticipationLimit()
        max_notional = limit.max_notional_entry(10_000_000)
        assert max_notional == 100_000  # 1% de 10M

    def test_default_liquidation_limit(self) -> None:
        limit = ParticipationLimit()
        max_notional = limit.max_notional_liquidation(10_000_000)
        assert max_notional == 50_000  # 0.5% de 10M

    def test_entry_ok(self) -> None:
        limit = ParticipationLimit()
        ok, reason = limit.check_entry(50_000, 10_000_000)
        assert ok is True
        assert reason is None

    def test_entry_exceeds_adv(self) -> None:
        limit = ParticipationLimit()
        ok, reason = limit.check_entry(200_000, 10_000_000)
        assert ok is False
        assert reason is not None

    def test_entry_below_min_adv(self) -> None:
        limit = ParticipationLimit(min_adv_for_entry=1_000_000)
        ok, reason = limit.check_entry(5_000, 500_000)
        assert ok is False
        assert "min_adv" in (reason or "")

    def test_entry_adv_zero(self) -> None:
        limit = ParticipationLimit()
        ok, reason = limit.check_entry(10_000, 0)
        assert ok is False

    def test_absolute_cap(self) -> None:
        limit = ParticipationLimit(max_notional_absolute=25_000)
        ok, reason = limit.check_entry(30_000, 100_000_000)
        assert ok is False
        assert "max_absolute" in (reason or "")

    def test_liquidation_ok(self) -> None:
        limit = ParticipationLimit()
        ok, reason = limit.check_liquidation(25_000, 10_000_000)
        assert ok is True

    def test_liquidation_exceeds(self) -> None:
        limit = ParticipationLimit()
        ok, reason = limit.check_liquidation(100_000, 10_000_000)
        assert ok is False

    def test_invalid_pct(self) -> None:
        with pytest.raises(ValueError):
            ParticipationLimit(max_pct_of_adv_entry=0)
        with pytest.raises(ValueError):
            ParticipationLimit(max_pct_of_adv_entry=1.5)


# ── SlippageEstimator ───────────────────────────────────────────────────────


class TestSlippageEstimator:
    def test_zero_notional_zero_slippage(self) -> None:
        est = SlippageEstimator()
        result = est.estimate("AAPL", notional=0, adv_usd=10_000_000)
        assert result.total_slippage_bps == 0.0

    def test_basic_estimate(self) -> None:
        est = SlippageEstimator()
        result = est.estimate(
            "AAPL", notional=100_000, adv_usd=10_000_000,
            spread_bps=5.0, daily_vol_pct=2.0,
        )
        # spread component = 2.5 bps (half spread)
        # participation = 100k/10M = 0.01
        # impact = 0.1 * sqrt(0.01) * 10000 = 0.1 * 0.1 * 10000 = 100 bps
        # vol = 0.5 * 2.0 * sqrt(0.01) * 100 = 0.5 * 2 * 0.1 * 100 = 10 bps
        # total ≈ 2.5 + 100 + 10 = 112.5 bps
        assert result.spread_component_bps == pytest.approx(2.5)
        assert result.impact_component_bps == pytest.approx(100.0)
        assert result.volatility_component_bps == pytest.approx(10.0)
        assert result.total_slippage_bps > 0

    def test_stressed_multiplier(self) -> None:
        est = SlippageEstimator(stress_multiplier=3.0)
        normal = est.estimate("AAPL", notional=100_000, adv_usd=10_000_000, is_stressed=False)
        stressed = est.estimate("AAPL", notional=100_000, adv_usd=10_000_000, is_stressed=True)
        assert stressed.total_slippage_bps == pytest.approx(normal.total_slippage_bps * 3.0)

    def test_estimate_stressed_shortcut(self) -> None:
        est = SlippageEstimator()
        result = est.estimate_stressed("AAPL", notional=100_000, adv_usd=10_000_000)
        assert result.is_stressed is True

    def test_larger_notional_higher_slippage(self) -> None:
        est = SlippageEstimator()
        small = est.estimate("AAPL", notional=10_000, adv_usd=10_000_000)
        large = est.estimate("AAPL", notional=500_000, adv_usd=10_000_000)
        assert large.total_slippage_bps > small.total_slippage_bps

    def test_slippage_estimate_properties(self) -> None:
        est = SlippageEstimator()
        result = est.estimate("AAPL", notional=50_000, adv_usd=10_000_000)
        assert result.total_slippage_pct == result.total_slippage_bps / 10000.0
        assert result.symbol == "AAPL"


# ── LiquidityGate ───────────────────────────────────────────────────────────


class TestLiquidityGateBasic:
    def test_all_ok_long(self) -> None:
        gate = LiquidityGate()
        result = gate.evaluate(
            "AAPL", "long", 50_000,
            adv_usd=10_000_000,
            spread=SpreadSnapshot("AAPL", bid=149.9, ask=150.1, quote_time=datetime.now()),
        )
        assert result.go is True

    def test_spread_too_wide(self) -> None:
        gate = LiquidityGate(max_spread_bps=10.0)
        result = gate.evaluate(
            "AAPL", "long", 50_000,
            adv_usd=10_000_000,
            spread=SpreadSnapshot("AAPL", bid=148.0, ask=152.0, quote_time=datetime.now()),
        )
        # spread = (152-148)/150 * 10000 ≈ 266 bps > 10 → NO-GO
        assert result.go is False
        assert result.spread_ok is False

    def test_stale_quote_blocks(self) -> None:
        gate = LiquidityGate(require_fresh_quote=True)
        old = datetime.now() - timedelta(seconds=400)
        result = gate.evaluate(
            "AAPL", "long", 50_000,
            adv_usd=10_000_000,
            spread=SpreadSnapshot("AAPL", bid=149.9, ask=150.1, quote_time=old, max_age_seconds=300),
        )
        assert result.go is False
        assert "stale" in result.reason

    def test_short_without_borrow_blocked(self) -> None:
        gate = LiquidityGate()
        result = gate.evaluate("AAPL", "short", 50_000, adv_usd=10_000_000)
        assert result.go is False
        assert "borrow" in result.reason.lower()

    def test_short_etb_ok(self) -> None:
        gate = LiquidityGate()
        result = gate.evaluate(
            "AAPL", "short", 50_000,
            adv_usd=10_000_000,
            borrow=BorrowSnapshot("AAPL", status=BorrowStatus.EASY_TO_BORROW),
        )
        assert result.go is True

    def test_short_htb_without_locate_blocked(self) -> None:
        gate = LiquidityGate(block_htb_without_locate=True)
        result = gate.evaluate(
            "GME", "short", 50_000,
            adv_usd=10_000_000,
            borrow=BorrowSnapshot(
                "GME", status=BorrowStatus.HARD_TO_BORROW,
                locate_required=True, locate_confirmed=False,
            ),
        )
        assert result.go is False
        assert "HTB" in result.reason

    def test_short_not_shortable_blocked(self) -> None:
        gate = LiquidityGate()
        result = gate.evaluate(
            "BANKRUPT", "short", 50_000,
            adv_usd=10_000_000,
            borrow=BorrowSnapshot("BANKRUPT", status=BorrowStatus.NOT_SHORTABLE),
        )
        assert result.go is False
        assert "not_shortable" in result.reason

    def test_adv_missing_blocks(self) -> None:
        gate = LiquidityGate()
        result = gate.evaluate("AAPL", "long", 50_000)
        assert result.go is False
        assert "adv" in result.reason.lower()

    def test_adv_zero_blocks(self) -> None:
        gate = LiquidityGate()
        result = gate.evaluate("AAPL", "long", 50_000, adv_usd=0)
        assert result.go is False

    def test_participation_exceeds_limit(self) -> None:
        gate = LiquidityGate(
            participation_limit=ParticipationLimit(max_pct_of_adv_entry=0.005),
        )
        result = gate.evaluate(
            "AAPL", "long", 100_000,  # 2% de 5M > 0.5%
            adv_usd=5_000_000,
        )
        assert result.go is False

    def test_slippage_too_high(self) -> None:
        gate = LiquidityGate(max_slippage_bps=20.0)
        result = gate.evaluate(
            "AAPL", "long", 500_000,
            adv_usd=2_000_000,  # 25% participation → slippage énorme
        )
        assert result.go is False
        assert "slippage" in result.reason.lower()


# ── LiquidityGateResult ─────────────────────────────────────────────────────


class TestLiquidityGateResult:
    def test_to_dict_go(self) -> None:
        r = LiquidityGateResult(go=True, reason="liquidite_ok", participation_pct=0.005)
        d = r.to_dict()
        assert d["go"] is True
        assert d["participation_pct"] == 0.005

    def test_to_dict_no_go(self) -> None:
        r = LiquidityGateResult(go=False, reason="spread trop large", spread_ok=False)
        d = r.to_dict()
        assert d["go"] is False
        assert d["spread_ok"] is False


# ── check_liquidity_pre_entry (helper) ──────────────────────────────────────


class TestCheckLiquidityPreEntry:
    def test_long_ok(self) -> None:
        result = check_liquidity_pre_entry("AAPL", "long", 50_000, adv_usd=10_000_000, spread_bps=5.0)
        assert result.go is True

    def test_short_etb_ok(self) -> None:
        result = check_liquidity_pre_entry(
            "AAPL", "short", 50_000, adv_usd=10_000_000, spread_bps=5.0,
            borrow_status="easy_to_borrow",
        )
        assert result.go is True

    def test_short_not_shortable_blocked(self) -> None:
        result = check_liquidity_pre_entry(
            "AAPL", "short", 50_000, adv_usd=10_000_000,
            borrow_status="not_shortable",
        )
        assert result.go is False

    def test_no_adv_blocks(self) -> None:
        result = check_liquidity_pre_entry("AAPL", "long", 50_000)
        assert result.go is False
