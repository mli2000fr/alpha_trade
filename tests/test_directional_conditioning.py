from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from modelFactory.dataset import FeatureScaler, build_sequence_dataset
from modelFactory.directional_conditioning import (
    ORACLE_AVAILABLE_COLUMN,
    ORACLE_ELIGIBLE_COLUMN,
    ORACLE_FOLD_COLUMN,
    ORACLE_PERCENTILE_COLUMN,
    ORACLE_PROBA_COLUMN,
    attach_directional_oof_gate,
    build_directional_oof_gate,
    eligible_target_mask,
)
from modelFactory.evaluation import align_sequence_rows
from modelFactory.tabular_baseline import tabular_split


def _oracle_oof() -> pd.DataFrame:
    rows = []
    for day in ("2024-01-02", "2024-01-03"):
        for index in range(10):
            rows.append({
                "date": day,
                "symbol": f"S{index:02d}",
                "proba_extreme": (index + 1) / 10,
                "fold_start": "2024-01-02",
            })
    return pd.DataFrame(rows)


def test_build_directional_oof_gate_uses_daily_oracle_percentiles() -> None:
    gate, diagnostics = build_directional_oof_gate(_oracle_oof(), pool_pct=0.20)

    assert len(gate) == 20
    assert set(gate.columns) >= {
        "date", "symbol", ORACLE_PROBA_COLUMN, ORACLE_PERCENTILE_COLUMN,
        ORACLE_AVAILABLE_COLUMN, ORACLE_ELIGIBLE_COLUMN, ORACLE_FOLD_COLUMN,
    }
    # Même convention inclusive que le serving : rang percentile >= 0.80.
    assert gate.groupby("date")[ORACLE_ELIGIBLE_COLUMN].sum().tolist() == [3, 3]
    assert diagnostics["source"] == "oracle_walk_forward_oof_test"
    assert diagnostics["oof_only"] is True
    assert diagnostics["eligible_rows"] == 6


def test_build_directional_oof_gate_rejects_untraceable_scores() -> None:
    frame = _oracle_oof().drop(columns=["fold_start"])

    with pytest.raises(ValueError, match="fold_start"):
        build_directional_oof_gate(frame)


def test_attach_gate_preserves_daily_history_and_only_marks_endpoints() -> None:
    dates = pd.date_range("2024-01-01", periods=6, freq="D")
    prepared = pd.DataFrame({
        "date": dates,
        "feature": np.arange(6, dtype=float),
        "target": [-1, 0, 1, -1, 0, 1],
    })
    gate = pd.DataFrame({
        "date": [dates[2], dates[4]],
        ORACLE_PROBA_COLUMN: [0.8, 0.9],
        ORACLE_PERCENTILE_COLUMN: [0.8, 1.0],
        ORACLE_AVAILABLE_COLUMN: [True, True],
        ORACLE_ELIGIBLE_COLUMN: [True, False],
        ORACLE_FOLD_COLUMN: [dates[2], dates[2]],
    })

    conditioned = attach_directional_oof_gate(prepared, gate)

    assert len(conditioned) == len(prepared)
    assert eligible_target_mask(conditioned).tolist() == [False, False, True, False, False, False]
    assert conditioned.attrs["directional_conditioning"]["oof_available_rows"] == 2
    assert conditioned.attrs["directional_conditioning"]["eligible_rows"] == 1


def test_lstm_sequences_keep_non_gate_rows_as_lookback_but_not_endpoints() -> None:
    frame = pd.DataFrame({
        "feature": np.arange(6, dtype=float),
        "target": [-1, 0, 1, -1, 0, 1],
        ORACLE_ELIGIBLE_COLUMN: [False, False, True, False, True, False],
    })
    scaler = FeatureScaler(["feature"]).fit(frame)

    dataset = build_sequence_dataset(frame, scaler, seq_len=3)

    assert dataset is not None
    assert len(dataset) == 2
    # Endpoints 2 et 4 ; la fenêtre de l'endpoint 4 contient aussi le jour 3,
    # pourtant non éligible, ce qui préserve la continuité du signal temporel.
    assert dataset.y.tolist() == [1, 0]


def test_alignment_and_tabular_splits_apply_same_oracle_endpoint_gate() -> None:
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    frame = pd.DataFrame({
        "date": dates,
        "feature": np.arange(10, dtype=float),
        "target": [-1, 0, 1, -1, 0, 1, -1, 0, 1, -1],
        ORACLE_ELIGIBLE_COLUMN: [False, False, True, False, False, True, False, True, True, False],
    })

    aligned = align_sequence_rows(frame, seq_len=3)
    train, val, test = tabular_split(
        frame, train_ratio=0.6, val_ratio=0.2, forecast_horizon=0,
    )

    assert aligned["date"].tolist() == [dates[2], dates[5], dates[7], dates[8]]
    assert train["date"].tolist() == [dates[2], dates[5]]
    assert val["date"].tolist() == [dates[7]]
    assert test["date"].tolist() == [dates[8]]
