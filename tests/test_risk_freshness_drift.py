"""Tests unitaires — risk_management/freshness_gate.py + drift_monitor.py (Sprint Maître 13)."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from risk_management.freshness_gate import (
    DimensionFreshness,
    FreshnessConfig,
    FreshnessDimension,
    FreshnessGate,
    FreshnessResult,
    check_freshness,
)
from risk_management.drift_monitor import (
    DimensionDrift,
    DriftConfig,
    DriftDimension,
    DriftMonitor,
    DriftReport,
    DriftStatus,
    check_drift,
)


# ═══════════════════════════════════════════════════════════════════════════
# FreshnessGate tests
# ═══════════════════════════════════════════════════════════════════════════


class TestFreshnessConfig:
    def test_defaults(self) -> None:
        cfg = FreshnessConfig()
        assert cfg.max_age_price_data == 300.0
        assert cfg.max_age_ml_model == 604800.0

    def test_get_threshold(self) -> None:
        cfg = FreshnessConfig()
        assert cfg.get_threshold(FreshnessDimension.PRICE_DATA) == 300.0
        assert cfg.get_threshold(FreshnessDimension.ML_MODEL) == 604800.0

    def test_to_dict(self) -> None:
        cfg = FreshnessConfig()
        d = cfg.to_dict()
        assert d["price_data"] == 300.0


class TestDimensionFreshness:
    def test_fresh(self) -> None:
        df = DimensionFreshness(dimension=FreshnessDimension.PRICE_DATA, is_fresh=True)
        assert df.status == "fresh"

    def test_stale(self) -> None:
        df = DimensionFreshness(dimension=FreshnessDimension.PRICE_DATA, is_stale=True)
        assert df.status == "stale"

    def test_critical_stale(self) -> None:
        df = DimensionFreshness(dimension=FreshnessDimension.ML_MODEL, is_critical_stale=True)
        assert df.status == "critical_stale"


class TestFreshnessGate:
    def test_all_fresh(self) -> None:
        gate = FreshnessGate()
        now = datetime.now()
        result = gate.evaluate(
            price_data_at=now, ml_model_at=now,
            volume_adv_at=now, calibration_at=now,
            market_regime_at=now, borrow_at=now,
        )
        assert result.all_fresh is True
        assert result.must_block is False
        assert result.is_degraded is False

    def test_price_data_stale_blocks(self) -> None:
        gate = FreshnessGate()
        old = datetime.now() - timedelta(seconds=600)  # > 300s
        result = gate.evaluate(price_data_at=old, ml_model_at=datetime.now())
        assert result.must_block is True
        assert "price_data" in result.blocked_dimensions

    def test_ml_model_stale_blocks(self) -> None:
        gate = FreshnessGate()
        old = datetime.now() - timedelta(seconds=1_000_000)  # > 7 jours
        result = gate.evaluate(price_data_at=datetime.now(), ml_model_at=old)
        assert result.must_block is True
        assert "ml_model" in result.blocked_dimensions

    def test_calibration_stale_degrades(self) -> None:
        gate = FreshnessGate()
        old = datetime.now() - timedelta(seconds=1_000_000)  # > 7 jours
        result = gate.evaluate(
            price_data_at=datetime.now(), ml_model_at=datetime.now(),
            calibration_at=old, market_regime_at=datetime.now(),
        )
        assert result.must_block is False
        assert result.is_degraded is True
        assert "calibration" in result.degraded_dimensions

    def test_missing_data_stale(self) -> None:
        gate = FreshnessGate()
        result = gate.evaluate(price_data_at=None, ml_model_at=datetime.now())
        assert result.must_block is True
        assert "price_data" in result.blocked_dimensions

    def test_all_fresh_classmethod(self) -> None:
        result = FreshnessGate.all_fresh()
        assert result.all_fresh is True

    def test_to_dict(self) -> None:
        result = FreshnessGate.all_fresh()
        d = result.to_dict()
        assert d["all_fresh"] is True
        assert d["can_trade"] is True


class TestCheckFreshness:
    def test_all_fresh(self) -> None:
        result = check_freshness(
            price_data_age_seconds=60,
            ml_model_age_seconds=3600,
            market_regime_age_seconds=60,
            calibration_age_seconds=3600,
        )
        assert result.all_fresh is True

    def test_price_stale_blocks(self) -> None:
        result = check_freshness(
            price_data_age_seconds=600,  # > 300s
            ml_model_age_seconds=3600,
        )
        assert result.must_block is True

    def test_ml_model_stale_blocks(self) -> None:
        result = check_freshness(
            price_data_age_seconds=60,
            ml_model_age_seconds=1_000_000,  # > 7 jours
        )
        assert result.must_block is True


# ═══════════════════════════════════════════════════════════════════════════
# DriftMonitor tests
# ═══════════════════════════════════════════════════════════════════════════


class TestDriftConfig:
    def test_defaults(self) -> None:
        cfg = DriftConfig()
        assert cfg.features_psi_warn == 0.10
        assert cfg.features_psi_alert == 0.25


class TestDriftStatus:
    def test_is_drifting(self) -> None:
        d = DimensionDrift(dimension=DriftDimension.FEATURES, status=DriftStatus.ALERT)
        assert d.is_drifting is True
        assert d.is_critical is True

    def test_not_drifting(self) -> None:
        d = DimensionDrift(dimension=DriftDimension.FEATURES, status=DriftStatus.OK)
        assert d.is_drifting is False


class TestDriftMonitor:
    def test_all_ok(self) -> None:
        monitor = DriftMonitor()
        report = monitor.evaluate(
            features_psi=0.05,
            proba_ks_pvalue=0.10,
            pnl_drawdown_pct=0.05,
            costs_current_bps=10.0,
            costs_baseline_bps=10.0,
            exposure_current_gross=0.50,
            exposure_baseline_gross=0.50,
        )
        assert report.overall_status == DriftStatus.OK
        assert report.must_kill_switch is False

    def test_features_alert(self) -> None:
        monitor = DriftMonitor()
        report = monitor.evaluate(features_psi=0.30)  # > 0.25 alert
        assert report.overall_status == DriftStatus.ALERT
        assert report.must_kill_switch is True

    def test_features_warn(self) -> None:
        monitor = DriftMonitor()
        report = monitor.evaluate(features_psi=0.15)  # > 0.10 warn, < 0.25 alert
        assert report.overall_status == DriftStatus.WARN
        assert report.must_degrade is True

    def test_proba_drift_alert(self) -> None:
        monitor = DriftMonitor()
        report = monitor.evaluate(proba_ks_pvalue=0.005)  # <= 0.01 alert
        assert report.overall_status == DriftStatus.ALERT

    def test_proba_drift_warn(self) -> None:
        monitor = DriftMonitor()
        report = monitor.evaluate(proba_ks_pvalue=0.03)  # <= 0.05 warn, > 0.01
        assert report.overall_status == DriftStatus.WARN

    def test_sides_drift(self) -> None:
        monitor = DriftMonitor()
        report = monitor.evaluate(
            sides_long_pct=0.50, sides_baseline_long=0.33,
            sides_flat_pct=0.30, sides_baseline_flat=0.34,
            sides_short_pct=0.20, sides_baseline_short=0.33,
        )
        # max change = |0.50 - 0.33| = 0.17 → > 0.10 warn
        assert report.overall_status == DriftStatus.WARN

    def test_calibration_drift(self) -> None:
        monitor = DriftMonitor()
        report = monitor.evaluate(
            calibration_brier_current=0.15,
            calibration_brier_baseline=0.10,
        )
        # increase = 0.05 → > 0.03 alert
        assert report.overall_status == DriftStatus.ALERT

    def test_pnl_drawdown(self) -> None:
        monitor = DriftMonitor()
        report = monitor.evaluate(pnl_drawdown_pct=0.25)  # > 0.20 alert
        assert report.must_kill_switch is True

    def test_costs_drift(self) -> None:
        monitor = DriftMonitor()
        report = monitor.evaluate(
            costs_current_bps=20.0, costs_baseline_bps=10.0,
        )
        # increase = (20-10)/10 = 1.0 → > 0.50 alert
        assert report.overall_status == DriftStatus.ALERT

    def test_exposure_drift(self) -> None:
        monitor = DriftMonitor()
        report = monitor.evaluate(
            exposure_current_gross=0.80, exposure_baseline_gross=0.50,
        )
        # change = 0.30 → >= 0.30 alert
        assert report.overall_status == DriftStatus.ALERT

    def test_to_dict(self) -> None:
        monitor = DriftMonitor()
        report = monitor.evaluate(features_psi=0.05, proba_ks_pvalue=0.10)
        d = report.to_dict()
        assert d["overall_status"] == "ok"
        assert len(d["dimensions"]) == 2

    def test_summary(self) -> None:
        monitor = DriftMonitor()
        report = monitor.evaluate(features_psi=0.30, pnl_drawdown_pct=0.25)
        assert "ALERT: features" in report.summary


class TestCheckDrift:
    def test_all_ok(self) -> None:
        report = check_drift(features_psi=0.05, proba_ks_pvalue=0.10)
        assert report.overall_status == DriftStatus.OK

    def test_alert(self) -> None:
        report = check_drift(features_psi=0.30)
        assert report.overall_status == DriftStatus.ALERT
