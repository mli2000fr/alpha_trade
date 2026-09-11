from __future__ import annotations

import pandas as pd
import pytest

from modelFactory.oracle_pre_entry_utility import (
    E14Config,
    add_priority_scores,
    economic_model_diagnostics,
    fit_oof_economic_heads,
    schedule_economic_capacity,
)
from modelFactory.oracle_pre_entry_veto import MODEL_FEATURES


def _training_panel() -> pd.DataFrame:
    rows = []
    for index in range(120):
        row = {feature: float(index % 11) for feature in MODEL_FEATURES}
        row.update({
            "fold": "2024-01-01", "exit_date": pd.Timestamp("2024-03-01"),
            "date": pd.Timestamp("2024-02-01"),
            "net_return_lifecycle": (index % 9 - 4) / 100,
            "loss": int(index % 9 < 4), "bad_trailing": int(index % 4 == 0),
        })
        rows.append(row)
    for index in range(12):
        row = {feature: float(index % 7) for feature in MODEL_FEATURES}
        row.update({
            "fold": "2024-07-01", "exit_date": pd.Timestamp("2024-08-01"),
            "date": pd.Timestamp("2024-07-02"),
            "net_return_lifecycle": (index % 7 - 3) / 100,
            "loss": int(index % 7 < 3), "bad_trailing": int(index % 3 == 0),
        })
        rows.append(row)
    return pd.DataFrame(rows)


def test_oof_heads_use_purged_history_and_create_train_thresholds() -> None:
    scored, diagnostics = fit_oof_economic_heads(
        _training_panel(), E14Config(min_train_rows=100, iterations=1)
    )
    assert diagnostics[0]["status"] == "skipped"
    assert diagnostics[1]["status"] == "scored"
    assert len(scored) == 12
    assert scored["predicted_loss_probability"].between(0, 1).all()
    assert "keep_utility_0.20" in scored
    assert "keep_loss_0.20" in scored
    assert "0.20" in diagnostics[1]["utility_thresholds"]


def test_priority_scores_are_daily_and_bounded() -> None:
    frame = pd.DataFrame({
        "date": [pd.Timestamp("2024-01-02")] * 3,
        "directional_oracle_proba_extreme": [0.9, 0.8, 0.7],
        "predicted_net_utility": [-0.1, 0.2, 0.1],
        "predicted_loss_probability": [0.8, 0.2, 0.5],
    })
    result = add_priority_scores(frame)
    for column in (
        "oracle_priority", "utility_priority", "hybrid_priority", "low_loss_priority"
    ):
        assert result[column].between(0, 1).all()
    assert result.loc[1, "utility_priority"] == 1.0


def test_scheduler_can_rerank_by_predicted_utility() -> None:
    date = pd.Timestamp("2024-01-02")
    frame = pd.DataFrame([
        {
            "date": date, "entry_date": date + pd.offsets.BDay(1),
            "exit_date": date + pd.offsets.BDay(2), "symbol": symbol,
            "directional_oracle_proba_extreme": oracle, "oracle_priority": oracle,
            "utility_priority": utility,
        }
        for symbol, oracle, utility in (
            ("AAA", 0.9, 0.1), ("BBB", 0.8, 0.9)
        )
    ])
    result = schedule_economic_capacity(
        frame, max_positions=1, priority_column="utility_priority"
    )
    assert result["symbol"].tolist() == ["BBB"]


def test_scheduler_applies_economic_veto_without_refill_from_rejected() -> None:
    date = pd.Timestamp("2024-01-02")
    frame = pd.DataFrame([
        {
            "date": date, "entry_date": date + pd.offsets.BDay(1),
            "exit_date": date + pd.offsets.BDay(2), "symbol": symbol,
            "directional_oracle_proba_extreme": score,
            "oracle_priority": score, "keep": keep,
        }
        for symbol, score, keep in (
            ("AAA", 0.9, False), ("BBB", 0.8, True)
        )
    ])
    result = schedule_economic_capacity(
        frame, max_positions=1, keep_column="keep"
    )
    assert result["symbol"].tolist() == ["BBB"]


def test_model_diagnostics_recognize_ordered_utility() -> None:
    values = list(range(100))
    frame = pd.DataFrame({
        "predicted_net_utility": values,
        "predicted_loss_probability": list(reversed(values)),
        "net_return_lifecycle": values,
        "loss": [int(value < 50) for value in values],
        "bad_trailing": [int(value < 30) for value in values],
        "date": [pd.Timestamp("2024-01-02")] * 100,
        "fold": ["2024-01-01"] * 100,
    })
    diagnostics = economic_model_diagnostics(frame)
    assert diagnostics["utility_ic_oof"] == pytest.approx(1.0)
    assert diagnostics["loss_score_ic_oof"] == pytest.approx(1.0)


def test_config_rejects_invalid_primary_fraction() -> None:
    with pytest.raises(ValueError, match="primary_veto_fraction"):
        E14Config(primary_veto_fraction=0.0)
