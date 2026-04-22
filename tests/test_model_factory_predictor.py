from __future__ import annotations

import json
import pickle
from datetime import date
from pathlib import Path
from typing import Any, cast

import pandas as pd
import pytest
import torch
from sqlalchemy.engine import Engine

from modelFactory import predictor


def test_resolve_inference_device_rejects_invalid_accelerator() -> None:
    with pytest.raises(ValueError, match="accelerator"):
        predictor._resolve_inference_device("tpu")


def test_resolve_inference_device_falls_back_to_cpu_when_gpu_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(predictor.torch.cuda, "is_available", lambda: False)

    device = predictor._resolve_inference_device("gpu")

    assert device.type == "cpu"


def test_resolve_artifact_paths_prefers_registry_when_files_exist(tmp_path: Path, monkeypatch) -> None:
    ckpt = tmp_path / "model.ckpt"
    scaler = tmp_path / "scaler.pkl"
    config = tmp_path / "config.json"
    for path in (ckpt, scaler, config):
        path.write_text("x", encoding="utf-8")

    monkeypatch.setattr(
        predictor,
        "load_training_run",
        lambda engine, symbol, run_id=None: {
            "run_id": "run-registry",
            "checkpoint_path": str(ckpt),
            "scaler_path": str(scaler),
            "config_path": str(config),
        },
    )

    resolved = predictor._resolve_artifact_paths("AAPL", tmp_path, cast(Engine, object()), run_id=None)

    assert resolved == (ckpt, scaler, config, "run-registry")


def test_predict_symbol_returns_dataframe_and_persists(tmp_path: Path, monkeypatch) -> None:
    symbol = "AAPL"
    symbol_dir = tmp_path / symbol
    symbol_dir.mkdir(parents=True)
    (symbol_dir / "best.ckpt").write_text("checkpoint", encoding="utf-8")
    with open(symbol_dir / "scaler.pkl", "wb") as fh:
        pickle.dump({"mean": [0.0], "std": [1.0], "features": ["feat1"]}, cast(Any, fh))
    (symbol_dir / "config.json").write_text(
        json.dumps(
            {
                "data": {
                    "sequence_length": 2,
                    "forecast_horizon": 1,
                    "include_sentiment_features": False,
                },
                "run_id": "run-config",
            }
        ),
        encoding="utf-8",
    )

    bars = pd.DataFrame({"close": list(range(62))})
    features = pd.DataFrame({"feat1": [float(i) for i in range(62)]})
    persisted: list[pd.DataFrame] = []

    class FakeModel:
        def to(self, device):
            return self

        def eval(self):
            return self

        def __call__(self, x):
            return torch.tensor([[0.0, 2.0]], dtype=torch.float32), torch.tensor([[1.0]])

    monkeypatch.setattr(predictor, "load_training_run", lambda engine, symbol, run_id=None: None)
    monkeypatch.setattr(predictor, "load_symbol_bars", lambda engine, symbol, end_date=None: bars.copy())
    monkeypatch.setattr(
        predictor,
        "compute_features",
        lambda bars, sentiment_df=None, include_sentiment=False, benchmark_df=None, feature_set="v1": features.copy(),
    )
    monkeypatch.setattr(predictor.torch.cuda, "is_available", lambda: False)
    monkeypatch.setattr(
        predictor.LSTMAttentionModule,
        "load_from_checkpoint",
        lambda path, map_location=None: FakeModel(),
    )
    monkeypatch.setattr(predictor, "insert_predictions", lambda engine, df: persisted.append(df.copy()))

    result = predictor.predict_symbol(
        symbol,
        artifacts_dir=tmp_path,
        engine=cast(Engine, object()),
        prediction_date=date(2026, 4, 21),
        persist=True,
    )

    assert result is not None
    row = result.to_dict(orient="records")[0]
    assert row["symbol"] == symbol
    assert row["prediction_date"] == date(2026, 4, 21)
    assert row["predicted_class"] == 1
    assert row["predicted_proba"] > 0.8
    assert row["run_id"] == "run-config"
    assert len(persisted) == 1


def test_predict_batch_skips_missing_predictions(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        predictor,
        "predict_symbol",
        lambda sym, *args, **kwargs: None if sym == "MSFT" else pd.DataFrame([
            {
                "symbol": sym,
                "prediction_date": date(2026, 4, 21),
                "predicted_proba": 0.7,
                "predicted_class": 1,
                "run_id": "run-1",
            }
        ]),
    )

    result = predictor.predict_batch(["AAPL", "MSFT"], tmp_path, cast(Engine, object()), prediction_date=date(2026, 4, 21))

    rows = result.to_dict(orient="records")
    assert len(rows) == 1
    assert rows[0]["symbol"] == "AAPL"


def test_predict_symbol_applies_saved_calibration_and_decision_threshold(tmp_path: Path, monkeypatch) -> None:
    symbol = "AAPL"
    symbol_dir = tmp_path / symbol
    symbol_dir.mkdir(parents=True)
    (symbol_dir / "best.ckpt").write_text("checkpoint", encoding="utf-8")
    with open(symbol_dir / "scaler.pkl", "wb") as fh:
        pickle.dump({"mean": [0.0], "std": [1.0], "features": ["feat1"]}, cast(Any, fh))
    with open(symbol_dir / "calibrator.pkl", "wb") as fh:
        pickle.dump({"method": "platt", "slope": 1.0, "intercept": -2.0, "fitted": True, "max_iter": 100}, cast(Any, fh))
    (symbol_dir / "config.json").write_text(
        json.dumps(
            {
                "data": {
                    "sequence_length": 2,
                    "forecast_horizon": 1,
                    "include_sentiment_features": False,
                    "decision_threshold": 0.6,
                    "target_mode": "swing_cash",
                    "target_up_threshold": 0.02,
                    "target_down_threshold": -0.01,
                },
                "run_id": "run-config",
                "calibrator_path": str(symbol_dir / "calibrator.pkl"),
            }
        ),
        encoding="utf-8",
    )

    bars = pd.DataFrame({"close": list(range(62))})
    features = pd.DataFrame({"feat1": [float(i) for i in range(62)]})

    class FakeModel:
        def to(self, device):
            return self

        def eval(self):
            return self

        def __call__(self, x):
            return torch.tensor([[0.0, 2.0]], dtype=torch.float32), torch.tensor([[1.0]])

    monkeypatch.setattr(predictor, "load_training_run", lambda engine, symbol, run_id=None: None)
    monkeypatch.setattr(predictor, "load_symbol_bars", lambda engine, symbol, end_date=None: bars.copy())
    monkeypatch.setattr(
        predictor,
        "compute_features",
        lambda bars, sentiment_df=None, include_sentiment=False, benchmark_df=None, feature_set="v1": features.copy(),
    )
    monkeypatch.setattr(predictor.torch.cuda, "is_available", lambda: False)
    monkeypatch.setattr(
        predictor.LSTMAttentionModule,
        "load_from_checkpoint",
        lambda path, map_location=None: FakeModel(),
    )

    result = predictor.predict_symbol(
        symbol,
        artifacts_dir=tmp_path,
        engine=cast(Engine, object()),
        prediction_date=date(2026, 4, 21),
        persist=False,
    )

    assert result is not None
    row = result.to_dict(orient="records")[0]
    assert row["predicted_proba"] == 0.5
    assert row["raw_proba"] > row["predicted_proba"]
    assert row["predicted_class"] == 0
    assert row["signal_label"] == "no_trade"


