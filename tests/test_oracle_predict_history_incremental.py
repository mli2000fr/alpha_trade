from __future__ import annotations

import json
import numpy as np
import pandas as pd

from modelFactory.oracle import predict_history


def test_prediction_infers_oracle_horizon_from_feature_profile(monkeypatch, tmp_path) -> None:
    import modelFactory.oracle.dataset as dataset_module
    import modelFactory.oracle.train as train_module

    root = tmp_path / "champions"
    batch_root = root / "batch-h10"
    batch_root.mkdir(parents=True)
    (batch_root / "oracle_champions.json").write_text(
        '[{"t_start":"2024-01-01","model_file":"fold.txt","feature_columns":["signal"]}]',
        encoding="utf-8",
    )
    (batch_root / "feature_profile.json").write_text(
        '{"oracle_horizon":10,"oracle_universe_mode":"static_bars","serving_ready":true}',
        encoding="utf-8",
    )
    monkeypatch.setattr(predict_history, "_CHAMPIONS_ROOT", root)
    observed: dict[str, int] = {}
    def fake_universe(engine, batch_id, horizon):
        observed["horizon"] = horizon
        return ["AAPL"]

    monkeypatch.setattr(train_module, "get_universe_symbols", fake_universe)
    monkeypatch.setattr(dataset_module, "build_dataset", lambda *a, **k: (pd.DataFrame(), []))

    result = predict_history.predict_oracle_extreme_history(
        object(), "batch-h10", "2025-01-01", "2025-01-31",
    )

    assert result["reason"] == "empty_dataset"
    assert observed["horizon"] == 10


def test_prediction_rejects_oracle_horizon_mismatch(monkeypatch, tmp_path) -> None:
    root = tmp_path / "champions"
    batch_root = root / "batch-h5"
    batch_root.mkdir(parents=True)
    (batch_root / "oracle_champions.json").write_text(
        '[{"t_start":"2024-01-01","model_file":"fold.txt","feature_columns":["signal"]}]',
        encoding="utf-8",
    )
    (batch_root / "feature_profile.json").write_text(
        '{"oracle_horizon":5,"oracle_universe_mode":"static_bars","serving_ready":true}',
        encoding="utf-8",
    )
    monkeypatch.setattr(predict_history, "_CHAMPIONS_ROOT", root)

    result = predict_history.predict_oracle_extreme_history(
        object(), "batch-h5", "2025-01-01", "2025-01-31", horizon=20,
    )

    assert result["reason"] == "oracle_horizon_mismatch"
    assert result["trained_horizon"] == 5


def test_dynamic_p0f_batch_is_rejected_by_serving(monkeypatch, tmp_path) -> None:
    root = tmp_path / "champions"
    batch_root = root / "batch-p0f"
    batch_root.mkdir(parents=True)
    (batch_root / "feature_profile.json").write_text(json.dumps({
        "oracle_universe_mode": "pit_dynamic_bars",
        "serving_ready": False,
    }), encoding="utf-8")
    monkeypatch.setattr(predict_history, "_CHAMPIONS_ROOT", root)
    monkeypatch.setattr(predict_history, "_load_champions_meta", lambda batch_id: [{
        "t_start": "2020-01-01", "model_file": "fold.txt", "feature_columns": ["signal"],
    }])
    result = predict_history.predict_oracle_extreme_history(
        object(), "batch-p0f", "2024-01-01", "2024-12-31")
    assert result["status"] == "error"
    assert result["reason"] == "dynamic_oracle_universe_not_serving_ready"


def test_dynamic_oracle_shadow_uses_pit_membership_and_never_writes_tables(
    monkeypatch, tmp_path,
) -> None:
    root = tmp_path / "champions"
    batch_root = root / "batch-p0h"
    batch_root.mkdir(parents=True)
    (batch_root / "feature_profile.json").write_text(json.dumps({
        "oracle_universe_mode": "pit_dynamic_bars",
        "serving_ready": False,
        "feature_set": "expert",
        "generator_options": {},
    }), encoding="utf-8")
    monkeypatch.setattr(predict_history, "_CHAMPIONS_ROOT", root)
    monkeypatch.setattr(predict_history, "_load_champions_meta", lambda batch_id: [{
        "t_start": "2025-01-08", "model_file": "fold.txt", "feature_columns": ["signal"],
    }])

    dates = pd.to_datetime(["2026-01-02", "2026-01-02", "2026-01-05", "2026-01-05"])
    membership = pd.DataFrame({"date": dates, "symbol": ["A", "B", "A", "B"]})
    membership_diagnostics = {
        "rows": 4, "dates": 2, "symbols": 2,
        "daily_min": 2, "daily_median": 2, "daily_max": 2,
    }
    import modelFactory.oracle.dynamic_universe as dynamic_module
    import modelFactory.oracle.dataset as dataset_module
    import modelFactory.oracle.predictions_store as store_module
    import lightgbm

    monkeypatch.setattr(
        dynamic_module,
        "load_dynamic_universe_from_bars",
        lambda *args, **kwargs: (membership.copy(), membership_diagnostics.copy()),
    )
    captured: dict[str, object] = {}

    def _build_dataset(*args, **kwargs):
        captured["membership"] = kwargs.get("feature_membership")
        return pd.DataFrame({
            "date": dates,
            "symbol": ["A", "B", "A", "B"],
            "signal": [0.1, 0.9, 0.2, 0.8],
            "future_return": [np.nan] * 4,
            "oracle_extreme10": [np.nan] * 4,
        }), ["signal"]

    monkeypatch.setattr(dataset_module, "build_dataset", _build_dataset)

    class Booster:
        def __init__(self, *, model_file: str) -> None:
            self.model_file = model_file

        def predict(self, frame: pd.DataFrame) -> np.ndarray:
            return frame["signal"].to_numpy(dtype=float)

    monkeypatch.setattr(lightgbm, "Booster", Booster)
    monkeypatch.setattr(
        store_module,
        "write_oracle_predictions",
        lambda *_args, **_kwargs: pytest.fail("shadow must not write Oracle table"),
    )

    result = predict_history.predict_oracle_extreme_history(
        object(),
        "batch-p0h",
        "2026-01-02",
        "2026-01-05",
        symbols=["A", "B"],
        persist_chunk_dates=1,
        shadow_mode=True,
        shadow_artifacts_root=tmp_path / "shadow",
    )

    assert result["status"] == "completed"
    assert result["prediction_mode"] == "shadow"
    assert result["trading_eligible"] is False
    assert result["serving_ready"] is False
    assert result["n_rows"] == 4
    assert len(result["parts"]) == 2
    assert isinstance(captured["membership"], pd.DataFrame)
    artifact = tmp_path / "shadow" / "batch-p0h"
    run_root = next(artifact.iterdir())
    saved = pd.concat(
        [pd.read_parquet(path) for path in sorted((run_root / "parts").glob("*.parquet"))],
        ignore_index=True,
    )
    assert "champion_t_start" in saved.columns
    assert "fold_start" not in saved.columns
    assert saved["prediction_mode"].eq("shadow").all()
    assert saved.groupby("date")["extreme_gate_top20"].sum().tolist() == [1, 1]
    assert (run_root / "report.json").is_file()


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
        "prediction_mode": "serving",
        "trading_eligible": True,
        "dynamic_universe": None,
    }
