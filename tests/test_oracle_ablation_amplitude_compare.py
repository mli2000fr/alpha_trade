from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from modelFactory.oracle_ablation_amplitude_compare import evaluate_batch, prepare_labels


def _frames(aligned: bool = True) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows, labels = [], []
    for date in pd.to_datetime(["2024-01-02", "2024-01-03"]):
        returns = [-0.10, -0.02, 0.01, 0.12]
        scores = [0.9, 0.2, 0.1, 0.8] if aligned else [0.1, 0.8, 0.9, 0.2]
        for idx, (ret, score) in enumerate(zip(returns, scores, strict=True)):
            symbol = f"S{idx}"
            rows.append({"date": date, "symbol": symbol, "proba_extreme": score})
            labels.append({
                "date": date, "symbol": symbol, "future_return": ret,
                "abs_future_return": abs(ret), "oracle_extreme10": int(idx in {0, 3}),
            })
    return pd.DataFrame(rows), pd.DataFrame(labels)


def test_evaluate_batch_rewards_extreme_amplitude_ranking() -> None:
    scores, labels = _frames(aligned=True)
    report, daily = evaluate_batch(scores, labels)
    assert report["auc_extreme10"] == pytest.approx(1.0)
    assert report["mean_amplitude_lift"] > 0
    assert report["positive_day_ratio"] == pytest.approx(1.0)
    assert len(daily) == 2


def test_evaluate_batch_rejects_empty_intersection() -> None:
    scores, labels = _frames()
    labels["symbol"] = "OTHER_" + labels["symbol"]
    with pytest.raises(ValueError, match="Aucune ligne commune"):
        evaluate_batch(scores, labels)


def test_prepare_labels_keeps_only_valid_rows(tmp_path: Path) -> None:
    path = tmp_path / "labels.parquet"
    pd.DataFrame({
        "prediction_date": ["2024-01-02", "2024-01-03"],
        "symbol": ["aa", "bb"], "future_return": [0.1, 0.2],
        "oracle_extreme10": [1, 0], "target_quality_valid": [1, 0],
    }).to_parquet(path, index=False)
    result = prepare_labels(path, "2024-01-01", "2024-12-31")
    assert result["symbol"].tolist() == ["AA"]
    assert result["abs_future_return"].tolist() == pytest.approx([0.1])
