from __future__ import annotations

import numpy as np
import pandas as pd

from modelFactory.oracle import predict_history


def test_oracle_history_persists_incrementally_by_date_chunks(monkeypatch) -> None:
    dates = pd.date_range("2024-01-02", periods=5, freq="D")
    dataset = pd.DataFrame({
        "date": dates,
        "symbol": ["AAPL"] * len(dates),
        "signal": np.arange(len(dates), dtype=float),
        "future_return": [np.nan] * len(dates),
        "oracle_extreme10": [np.nan] * len(dates),
    })

    monkeypatch.setattr(
        predict_history,
        "_load_champions_meta",
        lambda batch_id: [{
            "t_start": "2020-01-01",
            "model_file": "fold.txt",
            "feature_columns": ["signal"],
        }],
    )

    import modelFactory.oracle.dataset as dataset_module
    import modelFactory.oracle.predictions_store as store_module
    import modelFactory.oracle.train as train_module
    import lightgbm

    monkeypatch.setattr(
        dataset_module,
        "build_dataset",
        lambda *args, **kwargs: (dataset.copy(), ["signal"]),
    )
    monkeypatch.setattr(train_module, "get_universe_symbols", lambda *args, **kwargs: ["AAPL"])

    class Booster:
        def __init__(self, *, model_file: str) -> None:
            self.model_file = model_file

        def predict(self, frame: pd.DataFrame) -> np.ndarray:
            return np.full(len(frame), 0.75)

    monkeypatch.setattr(lightgbm, "Booster", Booster)

    persisted_chunks: list[pd.DataFrame] = []

    def fake_write(engine, frame: pd.DataFrame, *, batch_id: str) -> int:
        assert batch_id == "batch-test"
        persisted_chunks.append(frame.copy())
        return len(frame)

    monkeypatch.setattr(store_module, "write_oracle_predictions", fake_write)

    result = predict_history.predict_oracle_extreme_history(
        object(),
        "batch-test",
        "2024-01-02",
        "2024-01-06",
        persist_chunk_dates=2,
    )

    assert [len(chunk) for chunk in persisted_chunks] == [2, 2, 1]
    assert [chunk["date"].tolist() for chunk in persisted_chunks] == [
        ["2024-01-02", "2024-01-03"],
        ["2024-01-04", "2024-01-05"],
        ["2024-01-06"],
    ]
    assert result == {
        "status": "completed",
        "batch_id": "batch-test",
        "n_rows": 5,
        "range": ["2024-01-02", "2024-01-06"],
        "n_dates": 5,
        "n_symbols": 1,
        "n_folds_used": 1,
        "persist_chunk_dates": 2,
    }
