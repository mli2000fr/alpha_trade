from __future__ import annotations

import json
import pickle
from datetime import date
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd
import pytest
import torch
from sqlalchemy.engine import Engine

from modelFactory import predictor


class PickleableFakeGlobalModel:
    def predict_proba(self, X):
        return np.array([[0.2, 0.8]], dtype=float)


class PickleableFakeLocalModel:
    def __init__(self, proba: float = 0.76) -> None:
        self.proba = proba

    def predict_proba(self, X):
        return np.array([[1.0 - self.proba, self.proba]], dtype=float)


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


def test_resolve_selected_model_route_uses_routing_block(tmp_path: Path) -> None:
    routed_ckpt = tmp_path / "routed.ckpt"
    routed_scaler = tmp_path / "routed.pkl"
    routed_config = tmp_path / "routed.json"
    cfg_data = {
        "architecture_selected": "catboost",
        "artifact_routes": {
            "selected_model": "catboost",
            "models": {
                "lstm_attention": {
                    "checkpoint_path": str(routed_ckpt),
                    "scaler_path": str(routed_scaler),
                    "config_path": str(routed_config),
                }
            },
        },
    }

    route = predictor._resolve_selected_model_route(
        cfg_data,
        tmp_path / "default.ckpt",
        tmp_path / "default.pkl",
        tmp_path / "default.json",
    )

    assert route["selected_model"] == "lstm_attention"
    assert route["checkpoint_path"] == routed_ckpt
    assert route["scaler_path"] == routed_scaler


def test_resolve_selected_model_route_can_return_global_model_route(tmp_path: Path) -> None:
    global_model_path = tmp_path / "global.pkl"
    global_config_path = tmp_path / "global.json"
    cfg_data = {
        "architecture_selected": "global_model",
        "artifact_routes": {
            "selected_model": "global_model",
            "models": {
                "global_model": {
                    "inference_backend": "global_tabular",
                    "config_path": str(global_config_path),
                    "model_path": str(global_model_path),
                }
            },
        },
    }

    route = predictor._resolve_selected_model_route(
        cfg_data,
        tmp_path / "default.ckpt",
        tmp_path / "default.pkl",
        tmp_path / "default.json",
    )

    assert route["selected_model"] == "global_model"
    assert route["inference_backend"] == "global_tabular"
    assert route["model_path"] == global_model_path


def test_resolve_selected_model_route_can_return_local_tabular_route(tmp_path: Path) -> None:
    model_path = tmp_path / "lightgbm_model.pkl"
    cfg_data = {
        "architecture_selected": "lightgbm",
        "artifact_routes": {
            "selected_model": "lightgbm",
            "models": {
                "lightgbm": {
                    "inference_backend": "lightgbm_tabular",
                    "config_path": str(tmp_path / "config.json"),
                    "model_path": str(model_path),
                    "feature_columns": ["feat1"],
                    "selected_decision_threshold": 0.61,
                }
            },
        },
    }

    route = predictor._resolve_selected_model_route(
        cfg_data,
        tmp_path / "default.ckpt",
        tmp_path / "default.pkl",
        tmp_path / "default.json",
    )

    assert route["selected_model"] == "lightgbm"
    assert route["inference_backend"] == "lightgbm_tabular"
    assert route["model_path"] == model_path
    assert route["feature_columns"] == ["feat1"]


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
    assert row["selected_model"] == "lstm_attention"
    assert len(persisted) == 1
    persisted_row = persisted[0].to_dict(orient="records")[0]
    assert persisted_row["selected_model"] == "lstm_attention"
    assert persisted_row["decision_threshold"] == 0.5
    assert persisted_row["signal_label"] == "long"
    assert persisted_row["calibration_method"] == "none"


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
    assert row["selected_model"] == "lstm_attention"


def test_predict_symbol_supports_cross_sectional_features(tmp_path: Path, monkeypatch) -> None:
    symbol = "AAPL"
    symbol_dir = tmp_path / symbol
    symbol_dir.mkdir(parents=True)
    (symbol_dir / "best.ckpt").write_text("checkpoint", encoding="utf-8")
    with open(symbol_dir / "scaler.pkl", "wb") as fh:
        pickle.dump({"mean": [0.0, 0.0], "std": [1.0, 1.0], "features": ["feat1", "ret_20_rank"]}, cast(Any, fh))
    (symbol_dir / "config.json").write_text(
        json.dumps(
            {
                "data": {
                    "sequence_length": 2,
                    "forecast_horizon": 1,
                    "include_sentiment_features": False,
                    "enable_cross_sectional_features": True,
                    "cross_sectional_min_universe": 2,
                },
                "run_id": "run-config",
            }
        ),
        encoding="utf-8",
    )

    bars = pd.DataFrame({"symbol": [symbol] * 62, "date": pd.date_range("2024-01-01", periods=62, freq="D"), "close": list(range(62))})
    features = pd.DataFrame({"symbol": [symbol] * 62, "date": pd.date_range("2024-01-01", periods=62, freq="D"), "feat1": [float(i) for i in range(62)]})
    cross_sectional = pd.DataFrame({"symbol": [symbol] * 62, "date": pd.date_range("2024-01-01", periods=62, freq="D"), "ret_20_rank": [0.8] * 62})

    class FakeModel:
        def to(self, device):
            return self

        def eval(self):
            return self

        def __call__(self, x):
            return torch.tensor([[0.0, 2.0]], dtype=torch.float32), torch.tensor([[1.0]])

    monkeypatch.setattr(predictor, "load_training_run", lambda engine, symbol, run_id=None: None)
    monkeypatch.setattr(predictor, "load_symbol_bars", lambda engine, symbol, end_date=None: bars.copy())
    monkeypatch.setattr(predictor, "load_benchmark_bars", lambda engine, benchmark_symbol, end_date=None: bars.assign(symbol="SPY"))
    monkeypatch.setattr(predictor, "load_candidate_symbols", lambda engine: ["AAPL", "MSFT"])
    monkeypatch.setattr(predictor, "load_universe_bars", lambda engine, symbols, end_date=None: bars.assign(symbol="AAPL"))
    monkeypatch.setattr(
        predictor,
        "compute_features",
        lambda bars, sentiment_df=None, include_sentiment=False, benchmark_df=None, feature_set="v1": features.copy(),
    )
    monkeypatch.setattr(
        predictor,
        "get_feature_columns",
        lambda include_sentiment=False, feature_set="v1", include_cross_sectional=False: ["feat1", "ret_20_rank"],
    )
    monkeypatch.setattr(
        predictor,
        "build_cross_sectional_features",
        lambda universe_df, benchmark_df=None, min_universe_size=20: (cross_sectional.copy(), {"enabled": True}),
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
    assert row["selected_model"] == "lstm_attention"
    assert row["predicted_class"] == 1


@pytest.mark.parametrize(
    ("model_name", "backend", "file_name", "decision_threshold", "expected_class"),
    [
        ("lightgbm", "lightgbm_tabular", "lightgbm_model.pkl", 0.60, 1),
        ("catboost", "catboost_tabular", "catboost_model.pkl", 0.80, 0),
    ],
)
def test_predict_symbol_can_route_to_local_tabular_model(
    tmp_path: Path,
    monkeypatch,
    model_name: str,
    backend: str,
    file_name: str,
    decision_threshold: float,
    expected_class: int,
) -> None:
    symbol = "AAPL"
    symbol_dir = tmp_path / symbol
    symbol_dir.mkdir(parents=True)
    model_path = symbol_dir / file_name
    with open(model_path, "wb") as fh:
        pickle.dump(PickleableFakeLocalModel(), cast(Any, fh))
    (symbol_dir / "config.json").write_text(
        json.dumps(
            {
                "data": {
                    "sequence_length": 2,
                    "forecast_horizon": 1,
                    "include_sentiment_features": False,
                    "decision_threshold": 0.5,
                },
                "run_id": "run-config",
                "artifact_routes": {
                    "selected_model": model_name,
                    "models": {
                        model_name: {
                            "inference_backend": backend,
                            "config_path": str(symbol_dir / "config.json"),
                            "model_path": str(model_path),
                            "feature_columns": ["feat1"],
                            "selected_decision_threshold": decision_threshold,
                        }
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    bars = pd.DataFrame({"symbol": [symbol] * 62, "date": pd.date_range("2024-01-01", periods=62, freq="D"), "close": list(range(62))})
    features = pd.DataFrame({"symbol": [symbol] * 62, "date": pd.date_range("2024-01-01", periods=62, freq="D"), "feat1": [float(i) for i in range(62)]})

    monkeypatch.setattr(predictor, "load_training_run", lambda engine, symbol, run_id=None: None)
    monkeypatch.setattr(predictor, "load_symbol_bars", lambda engine, symbol, end_date=None: bars.copy())
    monkeypatch.setattr(
        predictor,
        "compute_features",
        lambda bars, sentiment_df=None, include_sentiment=False, benchmark_df=None, feature_set="v1": features.copy(),
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
    assert row["selected_model"] == model_name
    assert row["decision_threshold"] == decision_threshold
    assert row["predicted_class"] == expected_class


def test_predict_symbol_can_route_to_global_model(tmp_path: Path, monkeypatch) -> None:
    symbol = "AAPL"
    symbol_dir = tmp_path / symbol
    global_dir = tmp_path / "__GLOBAL__"
    symbol_dir.mkdir(parents=True)
    global_dir.mkdir(parents=True)
    (symbol_dir / "best.ckpt").write_text("checkpoint", encoding="utf-8")
    with open(symbol_dir / "scaler.pkl", "wb") as fh:
        pickle.dump({"mean": [0.0], "std": [1.0], "features": ["feat1"]}, cast(Any, fh))
    with open(global_dir / "global_model.pkl", "wb") as fh:
        pickle.dump(PickleableFakeGlobalModel(), cast(Any, fh))
    (global_dir / "config.json").write_text(
        json.dumps(
            {
                "data": {
                    "sequence_length": 2,
                    "forecast_horizon": 1,
                    "include_sentiment_features": False,
                    "decision_threshold": 0.6,
                },
                "feature_columns": ["feat1"],
                "artifact_symbol": "__GLOBAL__",
                "architecture_selected": "global_model",
            }
        ),
        encoding="utf-8",
    )
    (symbol_dir / "config.json").write_text(
        json.dumps(
            {
                "data": {
                    "sequence_length": 2,
                    "forecast_horizon": 1,
                    "include_sentiment_features": False,
                },
                "artifact_routes": {
                    "selected_model": "global_model",
                    "models": {
                        "global_model": {
                            "inference_backend": "global_tabular",
                            "config_path": str(global_dir / "config.json"),
                            "model_path": str(global_dir / "global_model.pkl"),
                        }
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    bars = pd.DataFrame({"symbol": [symbol] * 62, "date": pd.date_range("2024-01-01", periods=62, freq="D"), "close": list(range(62))})
    features = pd.DataFrame({"symbol": [symbol] * 62, "date": pd.date_range("2024-01-01", periods=62, freq="D"), "feat1": [float(i) for i in range(62)]})

    monkeypatch.setattr(predictor, "load_training_run", lambda engine, symbol, run_id=None: None)
    monkeypatch.setattr(predictor, "load_symbol_bars", lambda engine, symbol, end_date=None: bars.copy())
    monkeypatch.setattr(
        predictor,
        "compute_features",
        lambda bars, sentiment_df=None, include_sentiment=False, benchmark_df=None, feature_set="v1": features.copy(),
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
    assert row["selected_model"] == "global_model"
    assert row["predicted_class"] == 1


def test_predict_symbol_falls_back_to_lstm_when_selected_tabular_route_is_unservable(tmp_path: Path, monkeypatch) -> None:
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
                "artifact_routes": {
                    "selected_model": "lightgbm",
                    "models": {
                        "lightgbm": {
                            "inference_backend": "lightgbm_tabular",
                            "config_path": str(symbol_dir / "config.json"),
                            "model_path": str(symbol_dir / "missing_lightgbm_model.pkl"),
                            "feature_columns": ["feat1"],
                            "selected_decision_threshold": 0.61,
                        }
                    },
                },
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
    assert row["selected_model"] == "lstm_attention"
    assert row["predicted_class"] == 1


def test_predict_symbol_aborts_on_feature_fingerprint_drift(tmp_path: Path, monkeypatch) -> None:
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
                "feature_fingerprint": "outdated-contract",
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(predictor, "load_training_run", lambda engine, symbol, run_id=None: None)

    result = predictor.predict_symbol(
        symbol,
        artifacts_dir=tmp_path,
        engine=cast(Engine, object()),
        prediction_date=date(2026, 4, 21),
        persist=False,
    )

    assert result is None


