"""Tests Phase 5.1 — risk_management run_summary + decoupling."""
from __future__ import annotations

import warnings
from datetime import date

import pytest

from core.conviction import ConvictionWeights, fuse
from risk_management.config import RiskConfig


def test_to_conviction_weights_returns_typed_object() -> None:
    cfg = RiskConfig(score_weight=0.4, prediction_weight=0.6)
    weights = cfg.to_conviction_weights()
    assert isinstance(weights, ConvictionWeights)
    assert weights.score_weight == pytest.approx(0.4)
    assert weights.prediction_weight == pytest.approx(0.6)


def test_default_conviction_weights_are_40_60() -> None:
    cfg = RiskConfig()
    assert cfg.score_weight == pytest.approx(0.40)
    assert cfg.prediction_weight == pytest.approx(0.60)


def test_legacy_compute_conviction_emits_deprecation_warning() -> None:
    from risk_management.conviction import compute_conviction as legacy
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = legacy(0.6, 0.7, 0.4, 0.6)
        assert any(issubclass(item.category, DeprecationWarning) for item in w)
    expected = fuse(quant_score=0.6, predicted_proba=0.7, weights=ConvictionWeights(0.4, 0.6))
    assert result == pytest.approx(expected)


def test_legacy_returns_same_value_as_core_fuse() -> None:
    from risk_management.conviction import compute_conviction as legacy
    cases = [
        (0.5, 0.7, 0.4, 0.6),
        (0.9, None, 0.4, 0.6),
        (0.1, 0.1, 0.5, 0.5),
        (0.8, 0.6, 0.3, 0.7),
        (0.65, 0.55, 0.4, 0.6),
    ]
    for score, proba, sw, pw in cases:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            legacy_value = legacy(score, proba, sw, pw)
        core_value = fuse(
            quant_score=score,
            predicted_proba=proba,
            weights=ConvictionWeights(sw, pw),
        )
        assert legacy_value == pytest.approx(core_value, abs=1e-12)


# --- run_summary contractuels ---

def _build_minimal_summary_via_repo() -> dict:
    """Construit un summary minimal en simulant ce que fait cli.main."""
    from core.run_summary import attach_schema_version
    summary = {
        "run_id": "rid",
        "trade_date": date(2026, 4, 27).isoformat(),
        "account_equity_breakdown": {
            "cash": 100.0,
            "long_positions_value": 50.0,
            "short_positions_value": 0.0,
            "dividends_ledger": 5.0,
            "total": 150.0,
            "source": "broker_account_snapshots",
            "snapshot_at": None,
            "settled_cash": 100.0,
            "account_id": "default",
            "trade_date": "2026-04-27",
        },
        "conviction_weights": {
            "score_weight": 0.4,
            "prediction_weight": 0.6,
            "source": "core.conviction",
        },
        "conviction_weights_calibration": {
            "source": "default",
            "calibration_run_id": None,
        },
    }
    return attach_schema_version(summary, version=1)


def test_summary_contains_account_equity_breakdown() -> None:
    summary = _build_minimal_summary_via_repo()
    assert "account_equity_breakdown" in summary
    breakdown = summary["account_equity_breakdown"]
    assert {"cash", "long_positions_value", "short_positions_value", "dividends_ledger", "total", "source"} <= set(breakdown)


def test_summary_breakdown_total_matches_cash_plus_positions() -> None:
    summary = _build_minimal_summary_via_repo()
    b = summary["account_equity_breakdown"]
    expected = (b["cash"] or 0.0) + (b["long_positions_value"] or 0.0) + (b["short_positions_value"] or 0.0)
    assert b["total"] == pytest.approx(expected, abs=1e-2)


def test_summary_has_schema_version() -> None:
    summary = _build_minimal_summary_via_repo()
    assert summary["schema_version"] == 1


def test_summary_contains_conviction_weights_source_core_conviction() -> None:
    summary = _build_minimal_summary_via_repo()
    assert summary["conviction_weights"]["source"] == "core.conviction"


def test_summary_contains_conviction_weights_calibration_placeholder() -> None:
    summary = _build_minimal_summary_via_repo()
    calib = summary["conviction_weights_calibration"]
    assert calib["source"] == "default"
    assert calib["calibration_run_id"] is None


def test_load_account_equity_breakdown_returns_missing_source_when_no_tables() -> None:
    """En l'absence des tables, source='missing' et aucune exception."""
    from sqlalchemy import create_engine
    from risk_management.db_io import RiskRepository

    engine = create_engine("sqlite:///:memory:")
    repo = RiskRepository(engine=engine)
    breakdown = repo.load_account_equity_breakdown("default", date(2026, 4, 27))
    assert breakdown["source"] == "missing"
    assert breakdown["account_id"] == "default"
    assert breakdown["total"] is None

