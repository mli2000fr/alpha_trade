import numpy as np
import pandas as pd

from modelFactory.oracle_trajectory_e22 import (
    add_ordered_lags,
    add_path_shape_features,
    build_latest_adaptive_folds,
    compare_variant,
)
from modelFactory.oracle.dataset import GUARD_COL


def frame():
    dates = pd.bdate_range("2025-01-01", periods=7)
    rows = []
    for symbol, scale in [("A", 1.), ("B", -1.)]:
        for index, date in enumerate(dates):
            rows.append({
                "symbol": symbol, "date": date,
                "daily_return": scale * (index + 1) / 100,
                "intraday_range": .02 + index / 1000,
                "overnight_gap": scale * index / 1000,
                "volume_ratio_20": 1 + index / 10,
                "rolling_volatility_5": .01 + index / 1000,
                "relative_strength_5": scale * index / 100,
            })
    return pd.DataFrame(rows)


def test_ordered_lags_are_strictly_past_and_symbol_local():
    source = frame()
    result, columns = add_ordered_lags(
        source, ["daily_return"], lag_sessions=2)
    a = result[result["symbol"] == "A"].reset_index(drop=True)
    assert columns == ["e22_daily_return_lag1", "e22_daily_return_lag2"]
    assert np.isnan(a.loc[0, "e22_daily_return_lag1"])
    assert a.loc[2, "e22_daily_return_lag1"] == source[
        source["symbol"] == "A"].iloc[1]["daily_return"]
    assert a.loc[2, "e22_daily_return_lag2"] == source[
        source["symbol"] == "A"].iloc[0]["daily_return"]


def test_missing_symbol_session_invalidates_path():
    source = frame()
    missing_date = source[source["symbol"] == "A"].iloc[3]["date"]
    source = source[~((source["symbol"] == "A") & (source["date"] == missing_date))]
    result, _ = add_ordered_lags(source, ["daily_return"], lag_sessions=2)
    a = result[result["symbol"] == "A"].reset_index(drop=True)
    assert np.isnan(a.loc[3, "e22_daily_return_lag1"])


def test_path_shape_uses_inclusive_six_session_history():
    result, columns = add_path_shape_features(frame(), window=6)
    a = result[result["symbol"] == "A"].reset_index(drop=True)
    assert len(columns) == 14
    assert np.isnan(a.loc[4, "e22_path_return_sum_6"])
    assert np.isclose(a.loc[5, "e22_path_return_sum_6"], .21)
    assert a.loc[5, "e22_path_positive_fraction_6"] == 1
    assert a.loc[5, "e22_path_sign_changes_6"] == 0
    assert a.loc[5, "e22_path_longest_streak_6"] == 6


def test_latest_folds_cover_the_end_of_the_available_period():
    dates = pd.bdate_range("2020-01-01", periods=24)
    source = pd.DataFrame({
        "symbol": "A",
        "date": dates,
        GUARD_COL: dates,
        "oracle_extreme10": np.tile([0, 1], 12),
    })
    folds = build_latest_adaptive_folds(
        source,
        min_train_dates=6,
        val_dates=3,
        test_dates=3,
        step_dates=3,
        max_splits=2,
        forecast_horizon=1,
    )
    assert len(folds) == 2
    assert folds[-1]["t_end"] == str(dates[-1].date())
    assert folds[0]["t_start"] > str(dates[9].date())


def test_comparison_requires_every_preregistered_gate():
    baseline = {
        "overall": {
            "average_precision": .30, "auc": .60, "precision_at_20pct": .30,
            "semesters": {"2025H1": {"precision_at_20pct": .30}}},
        "folds": [{"fold_start": "x", "auc": .60}],
    }
    variant = {
        "overall": {
            "average_precision": .31, "auc": .61, "precision_at_20pct": .32,
            "semesters": {"2025H1": {"precision_at_20pct": .31}}},
        "folds": [{"fold_start": "x", "auc": .61}],
    }
    gates = {
        "average_precision_delta_min": .005, "auc_delta_min": .005,
        "precision_at_20pct_delta_min": .01, "fold_auc_win_rate_min": .6,
        "worst_semester_precision_at_20pct_delta_min": -.02,
    }
    assert compare_variant(variant, baseline, gates)["status"] == "PASS"
    variant["overall"]["auc"] = .60
    assert compare_variant(variant, baseline, gates)["status"] == "FAIL"
