from __future__ import annotations

import numpy as np
import pandas as pd

from modelFactory.oracle_opening_volume_ablation import (
    E20CConfig,
    build_folds,
    evaluate,
    feature_columns,
    prepare_dataset,
    summarize,
)


def test_feature_contract_is_strictly_incremental() -> None:
    price, volume = feature_columns(30)
    assert "return_30m" in price
    assert "volume_rank_30m" in volume
    assert "vwap_return_30m" in volume
    assert not set(price) & set(volume)
    assert all("60m" not in column for column in price + volume)


def test_prepare_dataset_uses_next_session_and_current_cross_section() -> None:
    events = pd.DataFrame({
        "date": pd.to_datetime(["2026-09-11", "2026-09-11", "2026-09-14"]),
        "symbol": ["AAA", "BBB", "ZZZ"], "future_return": [0.1, -0.1, 0.0],
        "oracle_decile": [10, 1, 5],
        "directional_oracle_proba_extreme": [0.8, 0.7, 0.5],
        "directional_oracle_extreme_pct": [0.1, 0.2, 0.5],
    })
    base = {
        "session_date": pd.to_datetime(["2026-09-14", "2026-09-14"]),
        "symbol": ["AAA", "BBB"], "opening_price": [100.0, 50.0],
        "eligible_30m": [True, True],
    }
    for minute in (5, 15, 30):
        base.update({
            f"return_{minute}m": [0.01, -0.01], f"range_{minute}m": [0.02, 0.02],
            f"max_up_{minute}m": [0.02, 0.01], f"max_down_{minute}m": [-0.01, -0.02],
            f"close_location_{minute}m": [0.8, 0.2],
            f"volume_{minute}m": [1000.0 * minute, 100.0 * minute],
            f"trade_count_{minute}m": [100.0 * minute, 10.0 * minute],
            f"average_trade_size_{minute}m": [10.0, 10.0],
            f"vwap_{minute}m": [101.0, 49.0],
        })
    result = prepare_dataset(events, pd.DataFrame(base), E20CConfig())
    assert result["target_session"].eq(pd.Timestamp("2026-09-14")).all()
    assert result.loc[result.symbol.eq("AAA"), "volume_rank_30m"].iloc[0] == 1.0
    assert np.isclose(result.loc[result.symbol.eq("AAA"), "volume_share_15_30"].iloc[0], 0.5)


def test_folds_apply_horizon_embargo() -> None:
    dates = pd.Series(pd.bdate_range("2020-01-01", periods=50))
    config = E20CConfig(minimum_train_sessions=20, test_sessions=5, step_sessions=5,
                        embargo_sessions=3, maximum_folds=10, minimum_folds=1)
    folds = build_folds(dates, config)
    first = folds[0]
    assert len(first["train_dates"]) == 20
    assert len(first["test_dates"]) == 5
    assert dates.iloc[23] == first["test_start"]


def test_summary_rejects_unstable_increment() -> None:
    config = E20CConfig(minimum_folds=1)
    folds = pd.DataFrame([
        {"fold": 0, "variant": "price_only", "auc": 0.55, "brier": 0.24,
         "tail_accuracy": 0.56, "mean_signed_target_return": 0.01},
        {"fold": 0, "variant": "price_plus_volume", "auc": 0.54, "brier": 0.25,
         "tail_accuracy": 0.55, "mean_signed_target_return": 0.0},
    ])
    predictions = pd.DataFrame({
        "target": [1, 0, 1, 0], "future_return": [0.1, -0.1, 0.1, -0.1],
        "oracle_decile": [10, 1, 10, 1], "semester": "2025H1",
        "proba_price_only": [0.8, 0.2, 0.8, 0.2],
        "proba_price_plus_volume": [0.6, 0.4, 0.4, 0.6],
    })
    result = summarize(folds, predictions, config)
    assert result["verdict"] == "NO_GO_INCREMENTAL_VOLUME"
    assert result["promotion_authorized"] is False


def test_oof_predictions_preserve_target(monkeypatch) -> None:
    class FakeModel:
        def fit(self, features, target):
            return self

        def predict_proba(self, features):
            probability = np.full(len(features), 0.6)
            return np.column_stack([1 - probability, probability])

    monkeypatch.setattr(
        "modelFactory.oracle_opening_volume_ablation._model",
        lambda config: FakeModel(),
    )
    config = E20CConfig(
        minimum_train_sessions=2, test_sessions=1, step_sessions=1,
        embargo_sessions=1, maximum_folds=2, minimum_folds=1,
    )
    price, volume = feature_columns(30)
    rows = []
    for index, date in enumerate(pd.bdate_range("2026-01-01", periods=6)):
        for symbol, target in (("AAA", 1), ("BBB", 0)):
            row = {
                "date": date, "target_session": date, "symbol": symbol,
                "target": target, "future_return": 0.1 if target else -0.1,
                "oracle_decile": 10 if target else 1, "semester": "2026H1",
            }
            row.update({column: float(index + 1) for column in price + volume})
            rows.append(row)
    _, predictions = evaluate(pd.DataFrame(rows), config)
    assert "target" in predictions.columns
    assert set(predictions["target"]) == {0, 1}