from __future__ import annotations

import pandas as pd
import pytest

from modelFactory import conditional_oracle_ranker as ranker
from modelFactory import shared_directional as shared


def _panel(returns: list[float], horizon: int = 3) -> pd.DataFrame:
    date = pd.Timestamp("2024-01-02")
    return pd.DataFrame({
        "date": [date] * len(returns),
        "symbol": [f"S{i}" for i in range(len(returns))],
        "horizon": [horizon] * len(returns),
        "future_return": returns,
        shared.SPY_RETURN_COL: [0.0] * len(returns),
        shared.EXCESS_SPY_COL: returns,
        shared.SECTOR_RESIDUAL_COL: returns,
        "sector_members": [len(returns)] * len(returns),
    })


def test_config_defaults_to_h3_and_h20() -> None:
    config = ranker.ConditionalRankerConfig()
    assert config.horizons == (3, 20)
    assert config.pool_pct * config.selection_fraction == pytest.approx(0.04)


def test_attach_conditional_rank_target_uses_all_oracle_rows() -> None:
    returns = [-0.10, -0.03, 0.0, 0.03, 0.10]
    pool = pd.DataFrame({
        "date": [pd.Timestamp("2024-01-02")] * 5,
        "symbol": [f"S{i}" for i in range(5)],
        "future_return": [0.0] * 5,
        "oracle_decile": [1, 3, 5, 8, 10],
    })
    result = ranker.attach_conditional_rank_target(pool, _panel(returns), horizon=3)
    assert len(result) == 5
    assert result[ranker.RANK_LABEL_COL].is_monotonic_increasing
    assert result[ranker.RANK_LABEL_COL].min() >= 0
    assert result[ranker.RANK_LABEL_COL].max() <= 9
    assert result["future_return"].tolist() == returns


def test_evaluate_ranker_separates_long_and_short() -> None:
    rows = []
    for date in pd.date_range("2024-01-01", periods=4):
        for index in range(20):
            future_return = -0.10 + index * (0.20 / 19)
            rows.append({
                "date": date,
                "symbol": f"S{index}",
                "future_return": future_return,
                ranker.RANK_LABEL_COL: min(9, index // 2),
                ranker.RANK_SCORE_COL: float(index),
                shared.ORACLE_GATE_SCORE_COL: 1.0 - index / 20,
                "momentum_20": float(index),
                "relative_strength_20": float(index),
            })
    metrics = ranker.evaluate_ranker(
        pd.DataFrame(rows), ranker.ConditionalRankerConfig(selection_fraction=0.20),
    )
    assert metrics["mean_daily_ic"] == pytest.approx(1.0)
    assert metrics["model"]["long"]["mean_signed_return"] > 0
    assert metrics["model"]["short"]["mean_signed_return"] > 0
    assert metrics["model"]["spread_raw"] > 0
    assert metrics["model"]["long"]["precision_lift_vs_matched"] > 0
    assert metrics["model"]["short"]["precision_lift_vs_matched"] > 0
    oracle = metrics["baselines"]["oracle_percentile_directionless_control"]
    assert oracle["available"] is True
    assert oracle["metrics"]["spread_raw"] < 0


def test_bottom_rank_is_not_short_when_all_returns_are_positive() -> None:
    rows = []
    for index in range(10):
        rows.append({
            "date": pd.Timestamp("2024-01-02"),
            "symbol": f"S{index}",
            "future_return": 0.01 + index * 0.005,
            ranker.RANK_LABEL_COL: index,
            ranker.RANK_SCORE_COL: float(index),
        })
    metrics = ranker.evaluate_ranker(
        pd.DataFrame(rows), ranker.ConditionalRankerConfig(),
    )
    short = metrics["model"]["short"]
    assert short["mean_raw_return"] > 0
    assert short["mean_signed_return"] < 0
    assert short["signed_hit_rate"] == 0


def test_development_gates_keep_long_and_short_independent() -> None:
    overall = {
        "mean_daily_ic": 0.03,
        "model": {
            "spread_raw": 0.01,
            "long": {
                "mean_signed_return": 0.01,
                "mean_raw_return": 0.01,
                "return_lift_vs_matched": 0.004,
                "precision_lift_vs_matched": 0.03,
            },
            "short": {
                "mean_signed_return": -0.01,
                "mean_raw_return": 0.01,
                "return_lift_vs_matched": -0.004,
                "precision_lift_vs_matched": -0.03,
            },
        },
    }
    stability = {
        "ic_positive_folds": 8,
        "spread_positive_folds": 8,
        "long_positive_lift_folds": 8,
        "short_positive_lift_folds": 1,
    }
    gates = ranker._development_gates(overall, stability, 9)
    assert gates["rank_passed"] is True
    assert gates["long_passed"] is True
    assert gates["short_passed"] is False


def test_e2b_loader_combines_oof_and_confirmation(tmp_path) -> None:
    pd.DataFrame({
        "date": ["2025-01-02"], "symbol": ["A"],
        "calibrated_proba_long": [0.4],
    }).to_parquet(tmp_path / "oof_predictions.parquet", index=False)
    confirmation_dir = tmp_path / "confirmation-20260101-20260630"
    confirmation_dir.mkdir()
    pd.DataFrame({
        "date": ["2026-01-02"], "symbol": ["A"],
        "calibrated_proba_long": [0.5],
    }).to_parquet(confirmation_dir / "predictions.parquet", index=False)
    result = ranker._load_e2b_baseline(tmp_path)
    assert len(result) == 2
    assert result[ranker.E2B_SCORE_COL].tolist() == [0.4, 0.5]
