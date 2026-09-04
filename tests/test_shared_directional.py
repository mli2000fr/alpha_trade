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
