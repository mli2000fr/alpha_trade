"""Tests Phase 7.2 — calibration empirique poids (audit_global §7.2).

Sprint S3 / A-027 : bornes business [0.05, 0.40] sur poids walk-forward calibrés.
Sprint S4 / A-022 : walk_forward_risk_params — grid-search sur paramètres risk.
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pytest

from backtesting.weights_calibration import (
    MARKET_REGIME_ALL,
    CalibrationResult,
    CalibrationSegmentDrift,
    EmpiricalRiskCalibrationRun,
    EmpiricalRiskCalibrator,
    calibrate_conviction,
    calibrate_conviction_kelly,
    calibrate_sentiment,
    compute_segment_drifts,
    metric_hit_rate,
    metric_information_coefficient,
)


def _make_synth_data(n: int = 100, *, leak: float = 0.7, seed: int = 7):
    rng = np.random.default_rng(seed)
    quant = rng.uniform(0, 1, n)
    proba = rng.uniform(0, 1, n)
    # Forward return corrélé à la prédiction si leak proche de 1.
    fwd = leak * (proba - 0.5) + (1 - leak) * rng.normal(0, 0.05, n)
    return quant, proba, fwd


def test_metric_ic_perfect_correlation() -> None:
    x = np.linspace(0, 1, 50)
    assert metric_information_coefficient(x, x) == pytest.approx(1.0, abs=1e-6)
    assert metric_information_coefficient(x, -x) == pytest.approx(-1.0, abs=1e-6)


def test_metric_hit_rate_basic() -> None:
    preds = np.array([0.6, 0.7, 0.4, 0.8])
    fwd = np.array([0.01, -0.02, 0.03, 0.05])
    # 3 longs (0.6, 0.7, 0.8), 2 winners → 2/3
    assert metric_hit_rate(preds, fwd) == pytest.approx(2 / 3, abs=1e-6)


def test_calibrate_conviction_returns_valid_result() -> None:
    quant, proba, fwd = _make_synth_data(leak=0.9)
    result = calibrate_conviction(
        quant_scores=quant,
        predicted_proba=proba,
        forward_returns=fwd,
        metric_name="ic",
        grid_step=0.1,
        window=(date(2024, 1, 1), date(2024, 6, 30)),
    )
    assert isinstance(result, CalibrationResult)
    assert result.scope == "conviction"
    assert "score_weight" in result.best_weights and "prediction_weight" in result.best_weights
    # Avec leak=0.9 sur la prédiction, le best devrait privilégier la prédiction.
    assert result.best_weights["prediction_weight"] >= result.best_weights["score_weight"]
    assert len(result.candidates) > 0
    payload = result.to_payload()
    assert payload["schema_version"] == 2
    assert payload["window_start"] == "2024-01-01"


def test_calibrate_conviction_validates_inputs() -> None:
    with pytest.raises(ValueError):
        calibrate_conviction(quant_scores=[0.1], predicted_proba=[0.2, 0.3], forward_returns=[0.0])
    with pytest.raises(ValueError):
        calibrate_conviction(
            quant_scores=[0.1, 0.2],
            predicted_proba=[0.1, 0.2],
            forward_returns=[0.0, 0.0],
            metric_name="unknown",
        )
    with pytest.raises(ValueError):
        # < 5 observations valides
        calibrate_conviction(
            quant_scores=[0.1, 0.2],
            predicted_proba=[0.1, 0.2],
            forward_returns=[0.0, 0.0],
        )


def test_calibrate_conviction_kelly_returns_valid_result() -> None:
    rng = np.random.default_rng(11)
    n_days = 20
    names_per_day = 6
    dates = [date(2025, 1, 1 + idx // names_per_day) for idx in range(n_days * names_per_day)]
    quant = rng.uniform(0.2, 0.9, n_days * names_per_day)
    proba = rng.uniform(0.45, 0.8, n_days * names_per_day)
    hist_wr = rng.uniform(0.48, 0.75, n_days * names_per_day)
    forward_returns = ((proba - 0.5) * 0.08) + rng.normal(0.0, 0.01, n_days * names_per_day)

    result = calibrate_conviction_kelly(
        snapshot_dates=dates,
        quant_scores=quant,
        predicted_proba=proba,
        historical_win_rate=hist_wr,
        forward_returns=forward_returns,
        metric_name="sharpe",
        conviction_grid_step=0.2,
        kelly_fraction_multipliers=(0.10, 0.25),
        min_effective_probabilities=(0.50, 0.55),
        assumed_payoff_ratios=(1.0, 1.5),
        top_n=3,
        window=(date(2025, 1, 1), date(2025, 1, 20)),
    )

    assert isinstance(result, CalibrationResult)
    assert result.scope == "risk"
    assert result.metric_name == "sharpe"
    assert result.best_weights["score_weight"] + result.best_weights["prediction_weight"] == pytest.approx(1.0)
    assert result.best_weights["kelly_fraction_multiplier"] in {0.10, 0.25}
    assert result.best_weights["min_effective_probability"] in {0.50, 0.55}
    assert result.best_weights["assumed_payoff_ratio"] in {1.0, 1.5}
    assert len(result.candidates) > 0


def test_walk_forward_backtests_by_regime_returns_all_and_regime_segments(monkeypatch, tmp_path) -> None:
    calibrator = EmpiricalRiskCalibrator(engine=object())
    work_df = __import__("pandas").DataFrame(
        [
            {
                "snapshot_date": date(2025, 1, 2),
                "symbol": "AAPL",
                "quant_score": 0.8,
                "predicted_proba": 0.7,
                "historical_win_rate": 0.6,
                "forward_return": 0.02,
                "market_regime_mode": "normal",
            },
            {
                "snapshot_date": date(2025, 1, 3),
                "symbol": "MSFT",
                "quant_score": 0.7,
                "predicted_proba": 0.68,
                "historical_win_rate": 0.58,
                "forward_return": 0.01,
                "market_regime_mode": "capital_preservation",
            },
        ]
    )

    monkeypatch.setattr(calibrator, "load_dataset", lambda **kwargs: work_df)
    monkeypatch.setattr(
        calibrator,
        "walk_forward_backtest",
        lambda **kwargs: (
            type(
                "_RunSummary",
                (),
                {
                    "start_date": kwargs["start_date"],
                    "end_date": kwargs["end_date"],
                    "observations_evaluated": 1,
                    "scenarios_evaluated": 1,
                    "latest_best_scenario_name": f"scenario-{kwargs['market_regime_mode']}",
                    "metric_name": "sharpe",
                    "metric_value": 1.0,
                    "final_value": 101000.0,
                    "total_return_pct": 1.0,
                    "sharpe_ratio": 1.0,
                    "max_drawdown_pct": -1.0,
                    "calibration_run_id": f"run-{kwargs['market_regime_mode']}",
                    "best_weights": {"score_weight": 0.4, "prediction_weight": 0.6},
                    "artifact_dir": str(tmp_path / kwargs["market_regime_mode"]),
                    "market_regime_mode": kwargs["market_regime_mode"],
                },
            )(),
            __import__("pandas").DataFrame(),
            __import__("pandas").DataFrame(),
            kwargs["dataset"],
            {},
        ),
    )

    results = calibrator.walk_forward_backtests_by_regime(
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 31),
        output_dir=tmp_path,
    )

    assert MARKET_REGIME_ALL in results
    assert "normal" in results
    assert "capital_preservation" in results


def test_compute_segment_drifts_compares_non_all_segment_to_baseline_and_reference() -> None:
    baseline = EmpiricalRiskCalibrationRun(
        start_date=date(2025, 1, 1),
        end_date=date(2025, 3, 31),
        observations_evaluated=300,
        scenarios_evaluated=10,
        latest_best_scenario_name="baseline",
        metric_name="sharpe",
        metric_value=1.20,
        final_value=120_000.0,
        total_return_pct=20.0,
        sharpe_ratio=1.10,
        max_drawdown_pct=-4.0,
        calibration_run_id="wcr-all",
        calibration_batch_id="batch-001",
        segment_key="regime=all|horizon=5d|window=12m",
        horizon_days=5,
        lookback_months=12,
        market_regime_mode="all",
        eligible_for_live=True,
    )
    defensive = EmpiricalRiskCalibrationRun(
        start_date=date(2025, 1, 1),
        end_date=date(2025, 3, 31),
        observations_evaluated=220,
        scenarios_evaluated=10,
        latest_best_scenario_name="defensive",
        metric_name="sharpe",
        metric_value=0.90,
        final_value=114_000.0,
        total_return_pct=14.0,
        sharpe_ratio=0.95,
        max_drawdown_pct=-3.5,
        calibration_run_id="wcr-cap",
        calibration_batch_id="batch-001",
        segment_key="regime=capital_preservation|horizon=5d|window=12m",
        horizon_days=5,
        lookback_months=12,
        market_regime_mode="capital_preservation",
        eligible_for_live=False,
    )

    drifts = compute_segment_drifts(
        [baseline, defensive],
        reference_horizon_days=5,
        reference_lookback_months=12,
    )

    assert drifts
    assert all(isinstance(item, CalibrationSegmentDrift) for item in drifts)
    assert any(item.comparison_kind == "vs_all_same_horizon_window" for item in drifts)
    assert any(item.comparison_kind == "vs_reference_live_segment" for item in drifts)


def test_calibrate_conviction_kelly_validates_inputs() -> None:
    with pytest.raises(ValueError, match="longueurs incohérentes"):
        calibrate_conviction_kelly(
            snapshot_dates=[date(2025, 1, 1)],
            quant_scores=[0.1],
            predicted_proba=[0.6, 0.7],
            historical_win_rate=[0.55],
            forward_returns=[0.01],
        )
    with pytest.raises(ValueError, match="Métrique risque inconnue"):
        calibrate_conviction_kelly(
            snapshot_dates=[date(2025, 1, 1)] * 12,
            quant_scores=[0.5] * 12,
            predicted_proba=[0.6] * 12,
            historical_win_rate=[0.55] * 12,
            forward_returns=[0.01] * 12,
            metric_name="unknown",
        )


def test_calibrate_sentiment_grid_normalisation() -> None:
    rng = np.random.default_rng(3)
    quant = rng.uniform(0, 1, 80)
    sent = rng.uniform(0, 1, 80)
    macro = rng.uniform(0, 1, 80)
    fwd = 0.3 * (sent - 0.5) + 0.1 * rng.normal(0, 0.05, 80)
    result = calibrate_sentiment(
        quant_scores=quant,
        sentiment_signal=sent,
        macro_signal=macro,
        forward_returns=fwd,
        metric_name="ic",
        grid_step=0.2,
    )
    w = result.best_weights
    s = w["quant_weight"] + w["sentiment_weight"] + w["macro_weight"]
    assert abs(s - 1.0) < 1e-3
    assert all(v >= 0.0 for v in w.values())


# ---------------------------------------------------------------------------
# Sprint S3 / A-027 — bornes business sur les poids walk-forward
# ---------------------------------------------------------------------------

def test_validate_walk_forward_weights_clips_above_max() -> None:
    """Poids au-dessus de WEIGHT_MAX doit être clippé avec warning."""
    from backtesting.walk_forward import WEIGHT_MAX, WalkForwardWeights, validate_walk_forward_weights
    w = WalkForwardWeights(sentiment_weight=0.20, macro_weight=0.10, quant_weight=0.80)
    validated = validate_walk_forward_weights(w, strict=False)
    assert validated.quant_weight == pytest.approx(WEIGHT_MAX)
    assert validated.sentiment_weight == pytest.approx(0.20)


def test_validate_walk_forward_weights_clips_below_min() -> None:
    """Poids en dessous de WEIGHT_MIN doit être clippé."""
    from backtesting.walk_forward import WEIGHT_MIN, WalkForwardWeights, validate_walk_forward_weights
    w = WalkForwardWeights(sentiment_weight=0.01, macro_weight=0.10, quant_weight=0.40)
    validated = validate_walk_forward_weights(w, strict=False)
    assert validated.sentiment_weight == pytest.approx(WEIGHT_MIN)


def test_validate_walk_forward_weights_strict_raises() -> None:
    """strict=True doit lever ValueError sur tout dépassement."""
    from backtesting.walk_forward import WalkForwardWeights, validate_walk_forward_weights
    w = WalkForwardWeights(sentiment_weight=0.20, macro_weight=0.10, quant_weight=0.80)
    with pytest.raises(ValueError, match="hors bornes"):
        validate_walk_forward_weights(w, strict=True)


def test_validate_walk_forward_weights_valid_unchanged() -> None:
    """Poids dans les bornes doivent être retournés inchangés."""
    from backtesting.walk_forward import WalkForwardWeights, validate_walk_forward_weights
    w = WalkForwardWeights(sentiment_weight=0.20, macro_weight=0.10, quant_weight=0.35)
    validated = validate_walk_forward_weights(w, strict=True)
    assert validated is w  # Même objet renvoyé si pas de violation


def test_validate_walk_forward_weights_preserves_metadata() -> None:
    """Les métadonnées calibration_run_id etc. sont conservées après clippage."""
    from backtesting.walk_forward import WalkForwardWeights, validate_walk_forward_weights
    w = WalkForwardWeights(
        sentiment_weight=0.20, macro_weight=0.10, quant_weight=0.80,
        calibration_run_id="wf-99", calibration_source="test"
    )
    validated = validate_walk_forward_weights(w, strict=False)
    assert validated.calibration_run_id == "wf-99"
    assert validated.calibration_source == "test"


# ---------------------------------------------------------------------------
# Sprint S4 / A-022 — walk_forward_risk_params
# ---------------------------------------------------------------------------


def test_walk_forward_risk_params_returns_best_combo_sharpe() -> None:
    """walk_forward_risk_params doit retourner le meilleur combo sur un dataset test."""
    from backtesting.walk_forward import RiskParamResult, walk_forward_risk_params

    rng = np.random.default_rng(42)
    returns = rng.normal(0.001, 0.02, 60)
    param_grid = {
        "atr_period": [14, 20],
        "correlation_threshold": [0.75, 0.80, 0.85],
    }
    result = walk_forward_risk_params(returns, param_grid, metric_name="sharpe")

    assert isinstance(result, RiskParamResult)
    assert result.metric_name == "sharpe"
    assert "atr_period" in result.best_params
    assert "correlation_threshold" in result.best_params
    assert result.best_params["atr_period"] in [14, 20]
    assert result.best_params["correlation_threshold"] in [0.75, 0.80, 0.85]
    assert result.n_evaluated == 6  # 2 × 3
    assert result.best_score > float("-inf")


def test_walk_forward_risk_params_sortino_metric() -> None:
    """Fonctionne avec metric_name='sortino'."""
    from backtesting.walk_forward import walk_forward_risk_params

    rng = np.random.default_rng(7)
    returns = rng.normal(0.0005, 0.015, 50)
    result = walk_forward_risk_params(
        returns,
        {"atr_period": [10, 14], "kelly_fraction": [0.20, 0.25]},
        metric_name="sortino",
    )
    assert result.metric_name == "sortino"
    assert result.n_evaluated == 4


def test_walk_forward_risk_params_hit_rate_metric() -> None:
    """Fonctionne avec metric_name='hit_rate'."""
    from backtesting.walk_forward import walk_forward_risk_params

    rng = np.random.default_rng(3)
    returns = rng.normal(0.001, 0.02, 40)
    result = walk_forward_risk_params(
        returns,
        {"correlation_threshold": [0.70, 0.80]},
        metric_name="hit_rate",
    )
    assert 0.0 <= result.best_score <= 1.0


def test_walk_forward_risk_params_raises_on_unknown_metric() -> None:
    """Doit lever ValueError sur metric_name inconnu."""
    from backtesting.walk_forward import walk_forward_risk_params

    rng = np.random.default_rng(0)
    returns = rng.normal(0.001, 0.02, 30)
    with pytest.raises(ValueError, match="metric_name"):
        walk_forward_risk_params(returns, {"atr_period": [14]}, metric_name="unknown")


def test_walk_forward_risk_params_raises_on_too_few_observations() -> None:
    """Doit lever ValueError si moins de min_observations rendements valides."""
    from backtesting.walk_forward import walk_forward_risk_params

    with pytest.raises(ValueError, match="observations"):
        walk_forward_risk_params(
            [0.01, 0.02, 0.03],
            {"atr_period": [14]},
            min_observations=20,
        )


def test_empirical_calibration_fallback_levels_preserve_configured_order(monkeypatch) -> None:
    from risk_management import db_io as risk_db_io

    monkeypatch.setattr(
        risk_db_io,
        "load_config",
        lambda: {
            "risk_management": {
                "empirical_calibration": {
                    "fallback_levels": [
                        "exact_segment",
                        "regime_all",
                        "regime_all_nearest_segment",
                    ]
                }
            }
        },
    )

    levels, source = risk_db_io._load_empirical_calibration_fallback_levels()

    assert levels == [
        "exact_segment",
        "regime_all",
        "regime_all_nearest_segment",
    ]
    assert source == "config_yaml"


