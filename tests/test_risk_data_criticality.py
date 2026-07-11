"""Tests unitaires — risk_management/data_criticality.py (Sprint Maître 9).

Vérifie : classification, fail-closed, fail-degraded, best-effort.
"""

from __future__ import annotations

import pytest

from risk_management.data_criticality import (
    CANONICAL_CRITICALITY,
    AvailabilityStatus,
    DataAvailabilityGate,
    DataCriticality,
    GateResult,
    classify_data_source,
    check_data_availability,
)


# ── DataCriticality ─────────────────────────────────────────────────────────


class TestDataCriticality:
    def test_critical_is_blocking(self) -> None:
        status = AvailabilityStatus(
            source_name="price_data",
            criticality=DataCriticality.CRITICAL,
            available=False,
        )
        assert status.is_blocking is True
        assert status.is_degrading is False

    def test_required_is_degrading(self) -> None:
        status = AvailabilityStatus(
            source_name="ml_predictions",
            criticality=DataCriticality.REQUIRED,
            available=False,
        )
        assert status.is_blocking is False
        assert status.is_degrading is True

    def test_optional_is_neither(self) -> None:
        status = AvailabilityStatus(
            source_name="sentiment_overlay",
            criticality=DataCriticality.OPTIONAL_OVERLAY,
            available=False,
        )
        assert status.is_blocking is False
        assert status.is_degrading is False

    def test_available_source_is_neither(self) -> None:
        status = AvailabilityStatus(
            source_name="price_data",
            criticality=DataCriticality.CRITICAL,
            available=True,
        )
        assert status.is_blocking is False
        assert status.is_degrading is False


# ── classify_data_source ────────────────────────────────────────────────────


class TestClassifyDataSource:
    def test_known_critical(self) -> None:
        assert classify_data_source("price_data") == DataCriticality.CRITICAL
        assert classify_data_source("earnings_calendar") == DataCriticality.CRITICAL
        assert classify_data_source("tradability_check") == DataCriticality.CRITICAL

    def test_known_required(self) -> None:
        assert classify_data_source("ml_predictions") == DataCriticality.REQUIRED
        assert classify_data_source("market_regime") == DataCriticality.REQUIRED
        assert classify_data_source("atr_data") == DataCriticality.REQUIRED

    def test_known_optional(self) -> None:
        assert classify_data_source("sentiment_overlay") == DataCriticality.OPTIONAL_OVERLAY
        assert classify_data_source("macro_overlay") == DataCriticality.OPTIONAL_OVERLAY

    def test_unknown_defaults_to_critical(self) -> None:
        """Principe de précaution : source inconnue → CRITICAL (fail-closed)."""
        assert classify_data_source("new_unknown_source") == DataCriticality.CRITICAL

    def test_all_canonical_entries_have_valid_enum(self) -> None:
        """Toutes les entrées du mapping canonique utilisent des valeurs valides."""
        for name, crit in CANONICAL_CRITICALITY.items():
            assert isinstance(crit, DataCriticality), f"{name}: {crit}"


# ── DataAvailabilityGate — all available ────────────────────────────────────


class TestDataAvailabilityGateAllAvailable:
    def test_all_available_no_block(self) -> None:
        result = DataAvailabilityGate().evaluate()
        assert result.must_block is False
        assert result.is_degraded is False
        assert result.can_trade is True
        assert result.degraded_multiplier == 1.0

    def test_all_available_classmethod(self) -> None:
        result = DataAvailabilityGate.all_available()
        assert result.must_block is False
        assert result.is_degraded is False


# ── DataAvailabilityGate — fail-closed ──────────────────────────────────────


class TestDataAvailabilityGateFailClosed:
    def test_price_data_missing_blocks(self) -> None:
        result = DataAvailabilityGate().evaluate(price_data_available=False)
        assert result.must_block is True
        assert result.can_trade is False
        assert "price_data" in result.block_reasons

    def test_earnings_data_missing_blocks(self) -> None:
        result = DataAvailabilityGate().evaluate(earnings_data_available=False)
        assert result.must_block is True
        assert "earnings_calendar" in result.block_reasons

    def test_tradability_check_missing_blocks(self) -> None:
        result = DataAvailabilityGate().evaluate(tradability_check_available=False)
        assert result.must_block is True

    def test_broker_connection_missing_blocks(self) -> None:
        result = DataAvailabilityGate().evaluate(broker_connection_available=False)
        assert result.must_block is True

    def test_circuit_breaker_tripped_blocks(self) -> None:
        result = DataAvailabilityGate().evaluate(circuit_breaker_ok=False)
        assert result.must_block is True

    def test_critical_missing_shortcut(self) -> None:
        result = DataAvailabilityGate.critical_missing("price_data", "earnings_calendar")
        assert result.must_block is True
        assert len(result.block_reasons) == 2


# ── DataAvailabilityGate — fail-degraded ────────────────────────────────────


class TestDataAvailabilityGateFailDegraded:
    def test_ml_predictions_missing_degraded(self) -> None:
        result = DataAvailabilityGate().evaluate(ml_predictions_available=False)
        assert result.must_block is False
        assert result.is_degraded is True
        assert result.can_trade is True  # On peut trader en dégradé
        assert result.degraded_multiplier < 1.0

    def test_market_regime_missing_degraded(self) -> None:
        result = DataAvailabilityGate().evaluate(market_regime_available=False)
        assert result.is_degraded is True
        assert "market_regime" in result.degraded_reasons

    def test_atr_missing_degraded(self) -> None:
        result = DataAvailabilityGate().evaluate(atr_data_available=False)
        assert result.is_degraded is True

    def test_multiple_required_missing_increases_degradation(self) -> None:
        result1 = DataAvailabilityGate().evaluate(ml_predictions_available=False)
        result3 = DataAvailabilityGate().evaluate(
            ml_predictions_available=False,
            market_regime_available=False,
            atr_data_available=False,
        )
        # Plus de REQUIRED manquantes → multiplicateur plus faible
        assert result3.degraded_multiplier < result1.degraded_multiplier

    def test_required_and_critical_missing(self) -> None:
        """Une CRITICAL manquante + une REQUIRED → must_block prime."""
        result = DataAvailabilityGate().evaluate(
            price_data_available=False,
            ml_predictions_available=False,
        )
        assert result.must_block is True
        assert result.is_degraded is True  # Aussi dégradé, mais bloqué d'abord


# ── DataAvailabilityGate — best-effort ──────────────────────────────────────


class TestDataAvailabilityGateBestEffort:
    def test_sentiment_missing_ignored(self) -> None:
        result = DataAvailabilityGate().evaluate(sentiment_overlay_available=False)
        assert result.must_block is False
        assert result.is_degraded is False
        # Vérifie que le status est bien "missing_ignored"
        for s in result.statuses:
            if s.source_name == "sentiment_overlay":
                assert s.quality == "missing_ignored"

    def test_macro_overlay_missing_ignored(self) -> None:
        result = DataAvailabilityGate().evaluate(macro_overlay_available=False)
        assert result.must_block is False
        assert result.is_degraded is False


# ── check_data_availability (helper) ────────────────────────────────────────


class TestCheckDataAvailability:
    def test_all_ok(self) -> None:
        result = check_data_availability()
        assert result.must_block is False

    def test_price_missing(self) -> None:
        result = check_data_availability(price_ok=False)
        assert result.must_block is True

    def test_earnings_missing(self) -> None:
        result = check_data_availability(earnings_ok=False)
        assert result.must_block is True

    def test_ml_missing_degraded(self) -> None:
        result = check_data_availability(ml_ok=False)
        assert result.is_degraded is True
        assert result.must_block is False


# ── GateResult ──────────────────────────────────────────────────────────────


class TestGateResult:
    def test_empty_result(self) -> None:
        r = GateResult()
        assert r.must_block is False
        assert r.can_trade is True

    def test_blocked_result(self) -> None:
        r = GateResult(must_block=True, block_reasons=("price_data",))
        assert r.can_trade is False

    def test_degraded_result(self) -> None:
        r = GateResult(is_degraded=True, degraded_multiplier=0.5)
        assert r.can_trade is True  # On peut trader en dégradé
        assert r.degraded_multiplier == 0.5
