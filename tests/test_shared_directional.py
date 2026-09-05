from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from modelFactory import shared_directional as shared


def test_binary_probability_to_ternary_is_normalized_and_abstains() -> None:
    result = shared.binary_probability_to_ternary([0.1, 0.5, 0.9])
    assert np.allclose(result.sum(axis=1).to_numpy(), 1.0)
    assert result.loc[0, "proba_short"] == pytest.approx(0.8)
    assert result.loc[1, "proba_flat"] == pytest.approx(1.0)
    assert result.loc[2, "proba_long"] == pytest.approx(0.8)


def test_load_profile_rejects_oracle_score_as_feature(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(
        '{"schema_version":1,"direction":"shared",'
        '"feature_columns":["directional_oracle_proba_extreme"]}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="interdites"):
        shared.load_profile(path)


def test_load_gate_recomputes_pool_and_requires_oof(tmp_path: Path) -> None:
    path = tmp_path / "gate.parquet"
    pd.DataFrame({
        "date": ["2024-01-02"] * 3,
        "symbol": ["A", "B", "C"],
        "directional_oracle_eligible": [True, False, False],
        "directional_oracle_oof_available": [True, True, True],
        "directional_oracle_extreme_pct": [0.95, 0.85, 0.75],
    }).to_parquet(path, index=False)
    gate = shared._load_gate(path, 0.20)
    assert gate.set_index("symbol")["shared_oracle_eligible"].to_dict() == {
        "A": True, "B": True, "C": False,
    }


def test_amplitude_weights_are_bounded() -> None:
    cfg = shared.SharedDirectionalConfig(amplitude_weight_min=0.5, amplitude_weight_max=3.0)
    weights = shared.amplitude_weights(pd.Series([0.01, -0.02, 0.50]), cfg)
    assert weights.min() >= 0.5
    assert weights.max() <= 3.0
    assert weights[-1] == pytest.approx(3.0)


def test_amplitude_weights_can_be_disabled() -> None:
    cfg = shared.SharedDirectionalConfig(amplitude_weighting=False)
    assert shared.amplitude_weights(pd.Series([0.01, -0.50]), cfg).tolist() == [1.0, 1.0]


def test_context_mode_is_validated() -> None:
    with pytest.raises(ValueError, match="context_mode"):
        shared.SharedDirectionalConfig(context_mode="invalid")


def test_objective_is_validated() -> None:
    with pytest.raises(ValueError, match="objective"):
        shared.SharedDirectionalConfig(objective="invalid")


def test_signed_return_requires_regressor() -> None:
    with pytest.raises(ValueError, match="regressor"):
        shared.SharedDirectionalConfig(target_mode="signed_return", objective="classifier")


def test_dual_threshold_requires_dual_classifier() -> None:
    with pytest.raises(ValueError, match="dual_classifier"):
        shared.SharedDirectionalConfig(target_mode="dual_threshold", objective="classifier")


def test_signed_target_clipping_is_learned_from_train_only() -> None:
    config = shared.SharedDirectionalConfig(
        target_mode="signed_return", objective="regressor",
        target_winsor_lower=0.25, target_winsor_upper=0.75,
    )
    train = pd.DataFrame({shared.TARGET_COL: [-100.0, 0.0, 1.0, 100.0]})
    valid = pd.DataFrame({shared.TARGET_COL: [-1000.0, 1000.0]})
    clipped_train, clipped_valid, bounds = shared.clip_signed_targets_from_train(train, valid, config)
    assert bounds == pytest.approx((-25.0, 25.75))
    assert clipped_train[shared.TARGET_COL].min() == pytest.approx(bounds[0])
    assert clipped_train[shared.TARGET_COL].max() == pytest.approx(bounds[1])
    assert clipped_valid is not None
    assert clipped_valid[shared.TARGET_COL].tolist() == pytest.approx([bounds[0], bounds[1]])


def test_build_forward_return_panel_residualizes_spy_and_sector() -> None:
    dates = pd.to_datetime(["2024-01-02", "2024-01-03"])
    bars = pd.DataFrame({
        "date": list(dates) * 3,
        "symbol": ["A", "A", "B", "B", "C", "C"],
        "adj_close": [100.0, 110.0, 100.0, 104.0, 100.0, 90.0],
    })
    benchmark = pd.DataFrame({"date": dates, "adj_close": [100.0, 102.0]})
    panel, diagnostics = shared.build_forward_return_panel(
        bars, benchmark, {"A": "TECH", "B": "TECH", "C": "OTHER"}, [1],
        sector_min_members=2,
    )
    first = panel[panel["date"].eq(dates[0])].set_index("symbol")
    assert first.loc["A", "future_return"] == pytest.approx(0.10)
    assert first.loc["A", shared.EXCESS_SPY_COL] == pytest.approx(0.08)
    assert first.loc["A", shared.SECTOR_RESIDUAL_COL] == pytest.approx(0.03)
    assert first.loc["B", shared.SECTOR_RESIDUAL_COL] == pytest.approx(-0.03)
    # Secteur C trop petit : fallback excess-SPY, pas de neutralisation fragile.
    assert first.loc["C", shared.SECTOR_RESIDUAL_COL] == pytest.approx(-0.12)
    assert diagnostics["horizons"]["1"]["rows"] == 3


def test_attach_signed_return_target_selects_requested_basis() -> None:
    pool = pd.DataFrame({
        "date": pd.to_datetime(["2024-01-02"]), "symbol": ["A"],
        "future_return": [0.20], "oracle_decile": [10],
    })
    targets = pd.DataFrame({
        "date": pd.to_datetime(["2024-01-02"]), "symbol": ["A"], "horizon": [5],
        "future_return": [0.08], shared.SPY_RETURN_COL: [0.02],
        shared.EXCESS_SPY_COL: [0.06], shared.SECTOR_RESIDUAL_COL: [0.03],
        "sector_members": [10],
    })
    result = shared.attach_signed_return_target(
        pool, targets, horizon=5, residualization="spy_sector",
    )
    assert result.loc[0, shared.TARGET_COL] == pytest.approx(0.03)
    assert result.loc[0, "future_return"] == pytest.approx(0.08)
    assert result.loc[0, "oracle_future_return_h20"] == pytest.approx(0.20)


def test_attach_dual_threshold_targets_labels_both_sides() -> None:
    dates = pd.to_datetime(["2024-01-02"] * 3)
    pool = pd.DataFrame({
        "date": dates, "symbol": ["A", "B", "C"],
        "future_return": [0.20, 0.0, -0.20], "oracle_decile": [10, 5, 1],
    })
    targets = pd.DataFrame({
        "date": dates, "symbol": ["A", "B", "C"], "horizon": [5, 5, 5],
        "future_return": [0.04, 0.01, -0.05], shared.SPY_RETURN_COL: [0.0] * 3,
        shared.EXCESS_SPY_COL: [0.04, 0.01, -0.05],
        shared.SECTOR_RESIDUAL_COL: [0.04, 0.01, -0.05], "sector_members": [10] * 3,
    })
    result = shared.attach_dual_threshold_targets(
        pool, targets, horizon=5, up_threshold=0.03, down_threshold=-0.03,
    )
    assert result[shared.LONG_TARGET_COL].tolist() == [1.0, 0.0, 0.0]
    assert result[shared.SHORT_TARGET_COL].tolist() == [0.0, 0.0, 1.0]
    assert not bool((result[shared.LONG_TARGET_COL].eq(1) & result[shared.SHORT_TARGET_COL].eq(1)).any())


def test_evaluate_signed_return_oos_measures_economic_tails() -> None:
    rows = []
    for date in pd.date_range("2024-01-01", periods=2):
        for index in range(10):
            realized = -0.10 + index * 0.022
            rows.append({
                "date": date, "symbol": f"S{index}",
                "future_return": realized,
                shared.SIGNED_TARGET_COL: realized,
                shared.SCORE_COL: realized,
            })
    metrics = shared.evaluate_signed_return_oos(pd.DataFrame(rows), top_fraction=0.10)
    assert metrics["mean_daily_ic_raw"] == pytest.approx(1.0)
    assert metrics["mean_daily_ic_target"] == pytest.approx(1.0)
    assert metrics["long_top_decile"]["mean_raw_signed_return"] > 0
    assert metrics["short_bottom_decile"]["mean_raw_signed_return"] > 0
    assert metrics["long_short_raw_spread"] > 0


def test_evaluate_dual_oos_separates_long_short_and_abstains() -> None:
    rows = []
    for date in pd.date_range("2024-01-01", periods=2):
        for index in range(10):
            realized = -0.10 + index * 0.022
            p_long = index / 9
            rows.append({
                "date": date, "symbol": f"S{index}", "future_return": realized,
                shared.LONG_TARGET_COL: int(realized >= 0.03),
                shared.SHORT_TARGET_COL: int(realized <= -0.03),
                shared.P_LONG_COL: p_long,
                shared.P_SHORT_COL: 1.0 - p_long,
            })
    metrics = shared.evaluate_dual_oos(pd.DataFrame(rows), top_fraction=0.10)
    assert metrics["auc_long"] == pytest.approx(1.0)
    assert metrics["auc_short"] == pytest.approx(1.0)
    assert metrics["mean_daily_direction_ic"] == pytest.approx(1.0)
    assert metrics["long_top_decile"]["target_precision"] == pytest.approx(1.0)
    assert metrics["short_bottom_decile"]["target_precision"] == pytest.approx(1.0)
    strict = metrics["policies"]["p0.70_m0.20"]
    assert 0.0 < strict["coverage"] < 1.0
    assert strict["long"]["mean_signed_return"] > 0
    assert strict["short"]["mean_signed_return"] > 0


def test_summarize_dual_fold_stability_keeps_folds_separate() -> None:
    folds = [
        {
            "auc_long": 0.51, "auc_short": 0.49, "mean_daily_direction_ic": 0.02,
            "long_top_decile": {"mean_signed_return": 0.01},
            "short_bottom_decile": {"mean_signed_return": -0.01},
        },
        {
            "auc_long": 0.55, "auc_short": 0.52, "mean_daily_direction_ic": -0.01,
            "long_top_decile": {"mean_signed_return": 0.02},
            "short_bottom_decile": {"mean_signed_return": 0.01},
        },
    ]
    result = shared.summarize_dual_fold_stability(folds)
    assert result["auc_long"]["mean"] == pytest.approx(0.53)
    assert result["auc_long"]["above_half_folds"] == 2
    assert result["auc_short"]["above_half_folds"] == 1
    assert result["daily_direction_ic"]["positive_folds"] == 1
    assert result["long_return_positive_folds"] == 2
    assert result["short_return_positive_folds"] == 1


def test_platt_calibration_is_validation_only_and_monotonic() -> None:
    raw = np.asarray([0.10, 0.20, 0.30, 0.70, 0.80, 0.90])
    labels = np.asarray([0, 0, 0, 1, 1, 1])
    calibrator, contract = shared.fit_non_inverting_platt(raw, labels, max_iter=50)
    calibrated = shared.apply_platt(calibrator, raw)
    assert contract["fit_scope"] == "validation_only"
    assert contract["slope"] > 0
    assert np.all(np.diff(calibrated) >= 0)
    assert np.all((calibrated >= 0) & (calibrated <= 1))


def test_platt_calibration_does_not_flip_an_inverse_validation_rank() -> None:
    raw = np.asarray([0.10, 0.20, 0.80, 0.90])
    labels = np.asarray([1, 1, 0, 0])
    calibrator, contract = shared.fit_non_inverting_platt(raw, labels, max_iter=50)
    calibrated = shared.apply_platt(calibrator, raw)
    assert contract["fallback"] == "non_positive_slope_to_validation_prevalence"
    assert calibrator.slope == 0.0
    assert np.allclose(calibrated, labels.mean())


def test_evaluate_long_confirmation_uses_fixed_daily_fractions() -> None:
    rows = []
    for date in pd.date_range("2024-01-01", periods=2):
        for index in range(20):
            realized = -0.05 + index * 0.006
            probability = 0.20 + index * 0.02
            rows.append({
                "date": date, "symbol": f"S{index}", "future_return": realized,
                shared.LONG_TARGET_COL: int(realized >= 0.03),
                shared.RAW_LONG_PROBA_COL: probability,
                shared.CAL_LONG_PROBA_COL: probability,
                shared.ORACLE_GATE_SCORE_COL: 1.0 - index / 20,
            })
    metrics = shared.evaluate_long_confirmation(pd.DataFrame(rows))
    top10 = metrics["selections"]["top_10_pct"]
    assert top10["model"]["rows"] == 4
    assert top10["model"]["precision"] == pytest.approx(1.0)
    assert top10["model"]["precision_lift_vs_matched"] > 0
    assert top10["model"]["return_lift_vs_matched"] > 0
    assert top10["oracle_amplitude"]["mean_return"] < 0
    assert metrics["auc_raw"] == pytest.approx(1.0)


def test_evaluate_oos_measures_both_directional_tails() -> None:
    rows = []
    for date in pd.date_range("2024-01-01", periods=2):
        for index in range(10):
            rows.append({
                "date": date,
                "symbol": f"S{index}",
                "future_return": -0.10 + index * 0.022,
                "oracle_decile": index + 1,
                shared.SCORE_COL: index / 9,
            })
    metrics = shared.evaluate_oos(pd.DataFrame(rows), top_fraction=0.10)
    assert metrics["auc_d10_vs_d1"] == pytest.approx(1.0)
    assert metrics["mean_daily_direction_ic"] == pytest.approx(1.0)
    assert metrics["long_top_decile"]["target_decile_precision"] == pytest.approx(1.0)
    assert metrics["short_bottom_decile"]["target_decile_precision"] == pytest.approx(1.0)
    assert metrics["long_top_decile"]["mean_signed_return"] > 0
    assert metrics["short_bottom_decile"]["mean_signed_return"] > 0
