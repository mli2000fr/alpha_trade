"""Tests unitaires — risk_management/stop_calculator.py (Sprint Maître 12)."""
from __future__ import annotations

import pytest

from risk_management.stop_calculator import (
    StopCalculator,
    StopLevels,
    compute_initial_stop_price,
    compute_stop_distance_pct,
    is_stop_valid,
)


# ── StopLevels ──────────────────────────────────────────────────────────────


class TestStopLevels:
    def test_long_stop_below_entry(self) -> None:
        levels = StopLevels(
            symbol="AAPL", side="long", entry_price=150.0,
            stop_price=145.0, stop_distance_pct=0.0333,
        )
        assert levels.is_valid is True

    def test_long_stop_above_entry_invalid(self) -> None:
        levels = StopLevels(
            symbol="AAPL", side="long", entry_price=150.0,
            stop_price=155.0, stop_distance_pct=0.03,
        )
        assert levels.is_valid is False

    def test_short_stop_above_entry(self) -> None:
        levels = StopLevels(
            symbol="TSLA", side="short", entry_price=200.0,
            stop_price=210.0, stop_distance_pct=0.05,
        )
        assert levels.is_valid is True

    def test_short_stop_below_entry_invalid(self) -> None:
        levels = StopLevels(
            symbol="TSLA", side="short", entry_price=200.0,
            stop_price=190.0, stop_distance_pct=0.05,
        )
        assert levels.is_valid is False

    def test_tp_valid_long(self) -> None:
        levels = StopLevels(
            symbol="AAPL", side="long", entry_price=150.0,
            stop_price=145.0, stop_distance_pct=0.03,
            take_profit_price=160.0,
        )
        assert levels.is_tp_valid is True

    def test_tp_invalid_long(self) -> None:
        levels = StopLevels(
            symbol="AAPL", side="long", entry_price=150.0,
            stop_price=145.0,
            take_profit_price=140.0,  # TP en-dessous pour un long = invalide
        )
        assert levels.is_tp_valid is False

    def test_recalculate_after_fill_long(self) -> None:
        levels = StopLevels(
            symbol="AAPL", side="long", entry_price=150.0,
            stop_price=145.0, stop_distance_pct=0.0333,
            atr=5.0, risk_per_share=5.0,
        )
        new_levels = levels.recalculate_after_fill(fill_price=151.0, fill_quantity=80)
        # Stop recentré sur le fill
        assert new_levels.stop_price < new_levels.entry_price  # Toujours valide
        assert new_levels.entry_price == 151.0

    def test_recalculate_after_fill_short(self) -> None:
        levels = StopLevels(
            symbol="TSLA", side="short", entry_price=200.0,
            stop_price=210.0, stop_distance_pct=0.05,
            atr=10.0, risk_per_share=10.0,
        )
        new_levels = levels.recalculate_after_fill(fill_price=198.0, fill_quantity=50)
        assert new_levels.stop_price > new_levels.entry_price  # Toujours valide (short)
        assert new_levels.entry_price == 198.0

    def test_recalculate_updates_risk_total(self) -> None:
        levels = StopLevels(
            symbol="AAPL", side="long", entry_price=150.0,
            stop_price=145.0, stop_distance_pct=0.0333,
            risk_per_share=5.0, risk_total=None,
        )
        new_levels = levels.recalculate_after_fill(fill_price=151.0, fill_quantity=100)
        assert new_levels.risk_total is not None
        assert new_levels.risk_total > 0

    def test_to_dict(self) -> None:
        levels = StopLevels(
            symbol="AAPL", side="long", entry_price=150.0,
            stop_price=145.0, stop_distance_pct=0.0333,
            take_profit_price=160.0, tp_distance_pct=0.0667,
            atr=5.0, risk_per_share=5.0, risk_total=500.0,
            time_stop_sessions=20,
        )
        d = levels.to_dict()
        assert d["symbol"] == "AAPL"
        assert d["stop_price"] == 145.0
        assert d["take_profit_price"] == 160.0

    def test_rejects_invalid_side(self) -> None:
        with pytest.raises(ValueError, match="side"):
            StopLevels(symbol="AAPL", side="both", entry_price=150.0, stop_price=145.0)


# ── StopCalculator ──────────────────────────────────────────────────────────


class TestStopCalculator:
    def test_long_stop(self) -> None:
        calc = StopCalculator(atr_stop_multiple=2.0)
        levels = calc.compute("AAPL", "long", 150.0, atr=5.0)
        # stop_distance = 5*2/150 = 0.0667
        # stop = 150 * (1-0.0667) = 140.0
        assert levels.is_valid is True
        assert levels.stop_price < 150.0
        assert levels.risk_per_share > 0

    def test_short_stop(self) -> None:
        calc = StopCalculator(atr_stop_multiple=2.0)
        levels = calc.compute("TSLA", "short", 200.0, atr=10.0)
        assert levels.is_valid is True
        assert levels.stop_price > 200.0  # Stop au-dessus pour short

    def test_defensive_regime_tighter_stops(self) -> None:
        calc = StopCalculator(atr_stop_multiple=2.0)
        normal = calc.compute("AAPL", "long", 150.0, atr=5.0, is_defensive_regime=False)
        defensive = calc.compute("AAPL", "long", 150.0, atr=5.0, is_defensive_regime=True)
        # Défensif → stop plus serré → stop_distance plus petite
        assert defensive.stop_distance_pct < normal.stop_distance_pct

    def test_defensive_calculation_does_not_mutate_future_take_profit(self) -> None:
        calc = StopCalculator(atr_stop_multiple=2.0, tp_atr_multiple=3.0)
        calc.compute("AAPL", "long", 150.0, atr=5.0, is_defensive_regime=True)

        normal = calc.compute("AAPL", "long", 150.0, atr=5.0)

        assert normal.take_profit_price == pytest.approx(165.0)

    def test_min_stop_distance(self) -> None:
        calc = StopCalculator(atr_stop_multiple=0.1, min_stop_distance_pct=0.02)
        levels = calc.compute("AAPL", "long", 150.0, atr=0.5)
        # ATR trop petit → distance clampée au min
        assert levels.stop_distance_pct >= 0.02

    def test_max_stop_distance(self) -> None:
        calc = StopCalculator(atr_stop_multiple=20.0, max_stop_distance_pct=0.10)
        levels = calc.compute("AAPL", "long", 150.0, atr=10.0)
        # ATR énorme → distance clampée au max
        assert levels.stop_distance_pct <= 0.10

    def test_no_atr_default_stop(self) -> None:
        calc = StopCalculator()
        levels = calc.compute("AAPL", "long", 150.0, atr=None)
        assert levels.is_valid is True
        # distance par défaut = 3%
        assert levels.stop_distance_pct == pytest.approx(0.03)

    def test_with_quantity(self) -> None:
        calc = StopCalculator(atr_stop_multiple=2.0)
        levels = calc.compute("AAPL", "long", 150.0, atr=5.0, quantity=100)
        assert levels.risk_total is not None
        assert levels.risk_total > 0

    def test_tp_computed(self) -> None:
        calc = StopCalculator(atr_stop_multiple=2.0, tp_atr_multiple=3.0)
        levels = calc.compute("AAPL", "long", 150.0, atr=5.0)
        assert levels.take_profit_price is not None
        assert levels.take_profit_price > 150.0

    def test_tp_none_when_disabled(self) -> None:
        calc = StopCalculator(tp_atr_multiple=None)
        levels = calc.compute("AAPL", "long", 150.0, atr=5.0)
        assert levels.take_profit_price is None


# ── compute_initial_stop_price ──────────────────────────────────────────────


class TestComputeInitialStopPrice:
    def test_long(self) -> None:
        stop = compute_initial_stop_price("long", 150.0, atr=5.0, atr_stop_multiple=2.0)
        assert stop < 150.0

    def test_short(self) -> None:
        stop = compute_initial_stop_price("short", 200.0, atr=10.0, atr_stop_multiple=2.0)
        assert stop > 200.0

    def test_no_atr_default(self) -> None:
        stop = compute_initial_stop_price("long", 150.0)
        assert stop == pytest.approx(145.5)  # 150 * (1 - 0.03) = 145.5


# ── compute_stop_distance_pct ───────────────────────────────────────────────


class TestComputeStopDistancePct:
    def test_basic(self) -> None:
        pct = compute_stop_distance_pct(atr=5.0, entry_price=100.0, atr_stop_multiple=2.0)
        assert pct == pytest.approx(0.10)

    def test_zero_entry(self) -> None:
        pct = compute_stop_distance_pct(atr=5.0, entry_price=0.0)
        assert pct == 0.03


# ── is_stop_valid ───────────────────────────────────────────────────────────


class TestIsStopValid:
    def test_long_valid(self) -> None:
        assert is_stop_valid("long", 150.0, 145.0) is True

    def test_long_invalid(self) -> None:
        assert is_stop_valid("long", 150.0, 155.0) is False

    def test_short_valid(self) -> None:
        assert is_stop_valid("short", 200.0, 210.0) is True

    def test_short_invalid(self) -> None:
        assert is_stop_valid("short", 200.0, 190.0) is False

    def test_unknown_side(self) -> None:
        assert is_stop_valid("both", 150.0, 145.0) is False
