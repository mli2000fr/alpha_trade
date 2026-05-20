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

from modelFactory import features as model_factory_features
from modelFactory import predictor
from modelFactory.features import fingerprint as compute_feature_fingerprint
from modelFactory.runtime_status import reset_runtime_status, snapshot_runtime_status


def _contract(
    feature_columns: list[str],
    *,
    include_sentiment: bool = False,
    feature_set: str = "v1",
    include_cross_sectional: bool = False,
    include_selector_context: bool = False,
) -> dict:
    """Construit un feature_contract minimal valide pour les tests.

    Génère directement le fingerprint à partir des colonnes fournies,
    sans passer par get_feature_columns (pour éviter les interférences
    avec les monkeypatches actifs dans les tests).
    """
    fp = compute_feature_fingerprint(
        include_sentiment=include_sentiment,
        feature_set=feature_set,
        include_cross_sectional=include_cross_sectional,
        include_selector_context=include_selector_context,
        feature_columns=feature_columns,
    )
    return {
        "schema_version": 1,
        "feature_columns": feature_columns,
        "feature_count": len(feature_columns),
        "feature_fingerprint": fp,
        "require_exact_order": True,
        "allow_extra_runtime_columns": True,
    }


def _feature_frame_stub(frame: pd.DataFrame):
    def _stub(
        bars,
        sentiment_df=None,
        include_sentiment=False,
        benchmark_df=None,
        feature_set="v1",
        selector_df=None,
        include_selector_context=False,
    ):
        return frame.copy()

    return _stub


def _feature_columns_stub(columns: list[str]):
    def _stub(
        include_sentiment=False,
        feature_set="v1",
        include_cross_sectional=False,
        include_selector_context=False,
    ):
        return list(columns)

    return _stub


class PickleableFakeGlobalModel:
    def predict_proba(self, X):
        return np.array([[0.2, 0.8]], dtype=float)


class PickleableFakeLocalModel:
    def __init__(self, proba: float = 0.76) -> None:
        self.proba = proba

    def predict_proba(self, X):
        return np.array([[1.0 - self.proba, self.proba]], dtype=float)


class PickleableIncompatibleTabularModel:
    def predict_proba(self, X):
        return np.array([0.7], dtype=float)


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
                "feature_contract": _contract(["feat1"]),
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
        _feature_frame_stub(features),
    )
    monkeypatch.setattr(
        predictor,
        "get_feature_columns",
        _feature_columns_stub(["feat1"]),
    )
    monkeypatch.setattr(
        model_factory_features,
        "get_feature_columns",
        _feature_columns_stub(["feat1"]),
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
                "feature_contract": _contract(["feat1"]),
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
        _feature_frame_stub(features),
    )
    monkeypatch.setattr(
        predictor,
        "get_feature_columns",
        _feature_columns_stub(["feat1"]),
    )
    monkeypatch.setattr(
        model_factory_features,
        "get_feature_columns",
        _feature_columns_stub(["feat1"]),
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
                "feature_contract": _contract(["feat1", "ret_20_rank"], include_cross_sectional=True),
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
        _feature_frame_stub(features),
    )
    monkeypatch.setattr(
        predictor,
        "get_feature_columns",
        _feature_columns_stub(["feat1", "ret_20_rank"]),
    )
    monkeypatch.setattr(
        model_factory_features,
        "get_feature_columns",
        _feature_columns_stub(["feat1", "ret_20_rank"]),
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


def test_predict_symbol_loads_selector_context_when_enabled(tmp_path: Path, monkeypatch) -> None:
    symbol = "AAPL"
    symbol_dir = tmp_path / symbol
    symbol_dir.mkdir(parents=True)
    (symbol_dir / "best.ckpt").write_text("checkpoint", encoding="utf-8")
    with open(symbol_dir / "scaler.pkl", "wb") as fh:
        pickle.dump(
            {
                "mean": [0.0, 0.0],
                "std": [1.0, 1.0],
                "features": ["feat1", "selector_trend_score"],
            },
            cast(Any, fh),
        )
    (symbol_dir / "config.json").write_text(
        json.dumps(
            {
                "data": {
                    "sequence_length": 2,
                    "forecast_horizon": 1,
                    "include_sentiment_features": False,
                    "include_selector_context_features": True,
                },
                "run_id": "run-config",
                "feature_contract": _contract(["feat1", "selector_trend_score"], include_selector_context=True),
            }
        ),
        encoding="utf-8",
    )

    bars = pd.DataFrame({"close": list(range(62))})
    features = pd.DataFrame(
        {
            "feat1": [float(i) for i in range(62)],
            "selector_trend_score": [0.82] * 62,
        }
    )
    captured: dict[str, object] = {}

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
        "load_symbol_selector_context",
        lambda engine, symbol, end_date=None, start_date=None: captured.update({"symbol": symbol, "end_date": end_date}) or pd.DataFrame(
            {
                "symbol": [symbol],
                "date": [pd.Timestamp("2026-04-21")],
                "trend_score": [0.82],
            }
        ),
    )
    monkeypatch.setattr(predictor, "compute_features", _feature_frame_stub(features))
    monkeypatch.setattr(predictor, "get_feature_columns", _feature_columns_stub(["feat1", "selector_trend_score"]))
    monkeypatch.setattr(model_factory_features, "get_feature_columns", _feature_columns_stub(["feat1", "selector_trend_score"]))
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
    assert captured == {"symbol": "AAPL", "end_date": date(2026, 4, 21)}


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
                "feature_contract": _contract(["feat1"]),
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
        _feature_frame_stub(features),
    )
    monkeypatch.setattr(
        model_factory_features,
        "get_feature_columns",
        _feature_columns_stub(["feat1"]),
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
                "feature_contract": _contract(["feat1"]),
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
                "feature_contract": _contract(["feat1"]),
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
        _feature_frame_stub(features),
    )
    monkeypatch.setattr(
        model_factory_features,
        "get_feature_columns",
        _feature_columns_stub(["feat1"]),
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
                "feature_contract": _contract(["feat1"]),
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
        _feature_frame_stub(features),
    )
    monkeypatch.setattr(
        predictor,
        "get_feature_columns",
        _feature_columns_stub(["feat1"]),
    )
    monkeypatch.setattr(
        model_factory_features,
        "get_feature_columns",
        _feature_columns_stub(["feat1"]),
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
                "feature_contract": {
                    "schema_version": 1,
                    "feature_columns": ["feat1"],
                    "feature_count": 1,
                    "feature_fingerprint": "outdated-contract",
                    "require_exact_order": True,
                    "allow_extra_runtime_columns": True,
                },
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(predictor, "load_training_run", lambda engine, symbol, run_id=None: None)
    monkeypatch.setattr(
        model_factory_features,
        "get_feature_columns",
        _feature_columns_stub(["feat1"]),
    )

    result = predictor.predict_symbol(
        symbol,
        artifacts_dir=tmp_path,
        engine=cast(Engine, object()),
        prediction_date=date(2026, 4, 21),
        persist=False,
    )

    assert result is None


def test_predict_symbol_falls_back_to_lstm_when_selected_tabular_model_is_corrupted(tmp_path: Path, monkeypatch) -> None:
    predictor.clear_model_cache()
    reset_runtime_status()
    symbol = "AAPL"
    symbol_dir = tmp_path / symbol
    symbol_dir.mkdir(parents=True)
    (symbol_dir / "best.ckpt").write_text("checkpoint", encoding="utf-8")
    with open(symbol_dir / "scaler.pkl", "wb") as fh:
        pickle.dump({"mean": [0.0], "std": [1.0], "features": ["feat1"]}, cast(Any, fh))
    (symbol_dir / "lightgbm_model.pkl").write_bytes(b"not-a-valid-pickle")
    (symbol_dir / "config.json").write_text(
        json.dumps(
            {
                "data": {
                    "sequence_length": 2,
                    "forecast_horizon": 1,
                    "include_sentiment_features": False,
                },
                "run_id": "run-config",
                "feature_contract": _contract(["feat1"]),
                "artifact_routes": {
                    "selected_model": "lightgbm",
                    "models": {
                        "lightgbm": {
                            "inference_backend": "lightgbm_tabular",
                            "config_path": str(symbol_dir / "config.json"),
                            "model_path": str(symbol_dir / "lightgbm_model.pkl"),
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
        _feature_frame_stub(features),
    )
    monkeypatch.setattr(
        model_factory_features,
        "get_feature_columns",
        _feature_columns_stub(["feat1"]),
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
    runtime_status = snapshot_runtime_status()
    assert runtime_status["prediction_artifact_issue_count"] == 1
    assert "tabular_model_corrupted:lightgbm" in str(runtime_status["last_fallback_reason"])


def test_predict_symbol_ignores_corrupted_calibrator_and_records_runtime_status(tmp_path: Path, monkeypatch) -> None:
    predictor.clear_model_cache()
    reset_runtime_status()
    symbol = "AAPL"
    symbol_dir = tmp_path / symbol
    symbol_dir.mkdir(parents=True)
    (symbol_dir / "best.ckpt").write_text("checkpoint", encoding="utf-8")
    with open(symbol_dir / "scaler.pkl", "wb") as fh:
        pickle.dump({"mean": [0.0], "std": [1.0], "features": ["feat1"]}, cast(Any, fh))
    (symbol_dir / "calibrator.pkl").write_bytes(b"not-a-valid-calibrator")
    (symbol_dir / "config.json").write_text(
        json.dumps(
            {
                "data": {
                    "sequence_length": 2,
                    "forecast_horizon": 1,
                    "include_sentiment_features": False,
                },
                "run_id": "run-config",
                "calibrator_path": str(symbol_dir / "calibrator.pkl"),
                "feature_contract": _contract(["feat1"]),
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
        _feature_frame_stub(features),
    )
    monkeypatch.setattr(
        model_factory_features,
        "get_feature_columns",
        _feature_columns_stub(["feat1"]),
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
    assert row["calibration_method"] == "none"
    runtime_status = snapshot_runtime_status()
    assert runtime_status["prediction_calibration_fallback_count"] == 1
    assert runtime_status["last_calibration_fallback_reason"] == "calibrator_corrupted:lstm_attention"


def test_predict_symbol_aborts_when_scaler_feature_contract_mismatches_config(tmp_path: Path, monkeypatch) -> None:
    predictor.clear_model_cache()
    reset_runtime_status()
    symbol = "AAPL"
    symbol_dir = tmp_path / symbol
    symbol_dir.mkdir(parents=True)
    (symbol_dir / "best.ckpt").write_text("checkpoint", encoding="utf-8")
    with open(symbol_dir / "scaler.pkl", "wb") as fh:
        pickle.dump({"mean": [0.0], "std": [1.0], "features": ["feat2"]}, cast(Any, fh))
    (symbol_dir / "config.json").write_text(
        json.dumps(
            {
                "data": {
                    "sequence_length": 2,
                    "forecast_horizon": 1,
                    "include_sentiment_features": False,
                },
                "run_id": "run-config",
                "feature_columns": ["feat1"],
                "feature_fingerprint": compute_feature_fingerprint(
                    include_sentiment=False,
                    feature_set="v1",
                    include_cross_sectional=False,
                    feature_columns=["feat1"],
                ),
                "feature_contract": {
                    "schema_version": 1,
                    "feature_columns": ["feat1"],
                    "feature_count": 1,
                    "feature_fingerprint": compute_feature_fingerprint(
                        include_sentiment=False,
                        feature_set="v1",
                        include_cross_sectional=False,
                        feature_columns=["feat1"],
                    ),
                    "require_exact_order": True,
                    "allow_extra_runtime_columns": True,
                    "scaler_feature_names": ["feat1"],
                },
            }
        ),
        encoding="utf-8",
    )

    bars = pd.DataFrame({"close": list(range(62))})
    features = pd.DataFrame({"feat1": [float(i) for i in range(62)]})

    monkeypatch.setattr(predictor, "load_training_run", lambda engine, symbol, run_id=None: None)
    monkeypatch.setattr(predictor, "load_symbol_bars", lambda engine, symbol, end_date=None: bars.copy())
    monkeypatch.setattr(
        predictor,
        "compute_features",
        _feature_frame_stub(features),
    )
    monkeypatch.setattr(
        predictor,
        "get_feature_columns",
        _feature_columns_stub(["feat1"]),
    )
    monkeypatch.setattr(
        model_factory_features,
        "get_feature_columns",
        _feature_columns_stub(["feat1"]),
    )
    monkeypatch.setattr(predictor.torch.cuda, "is_available", lambda: False)

    result = predictor.predict_symbol(
        symbol,
        artifacts_dir=tmp_path,
        engine=cast(Engine, object()),
        prediction_date=date(2026, 4, 21),
        persist=False,
    )

    assert result is None
    runtime_status = snapshot_runtime_status()
    assert runtime_status["prediction_artifact_issue_count"] == 1
    assert runtime_status["last_artifact_issue_reason"] == "feature_contract_violation:lstm_attention"


def test_resolve_artifact_paths_falls_back_when_registry_lookup_fails(tmp_path: Path, monkeypatch) -> None:
    reset_runtime_status()
    monkeypatch.setattr(
        predictor,
        "load_training_run",
        lambda engine, symbol, run_id=None: (_ for _ in ()).throw(RuntimeError("db unavailable")),
    )

    ckpt, scaler, config, selected_run_id = predictor._resolve_artifact_paths(
        "AAPL",
        tmp_path,
        cast(Engine, object()),
        run_id="run-1",
    )

    assert ckpt == tmp_path / "AAPL" / "best.ckpt"
    assert scaler == tmp_path / "AAPL" / "scaler.pkl"
    assert config == tmp_path / "AAPL" / "config.json"
    assert selected_run_id == "run-1"
    runtime_status = snapshot_runtime_status()
    assert runtime_status["prediction_db_issue_count"] == 1
    assert runtime_status["last_db_issue_operation"] == "load_training_run"


def test_predict_symbol_persistence_failure_is_best_effort(tmp_path: Path, monkeypatch) -> None:
    reset_runtime_status()
    symbol = "AAPL"
    symbol_dir = tmp_path / symbol
    symbol_dir.mkdir(parents=True)
    (symbol_dir / "best.ckpt").write_text("checkpoint", encoding="utf-8")
    with open(symbol_dir / "scaler.pkl", "wb") as fh:
        pickle.dump({"mean": [0.0], "std": [1.0], "features": ["feat1"]}, cast(Any, fh))
    (symbol_dir / "config.json").write_text(
        json.dumps({"data": {"sequence_length": 2, "forecast_horizon": 1, "include_sentiment_features": False}, "run_id": "run-config", "feature_contract": _contract(["feat1"])}),
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
        _feature_frame_stub(features),
    )
    monkeypatch.setattr(
        predictor,
        "get_feature_columns",
        _feature_columns_stub(["feat1"]),
    )
    monkeypatch.setattr(
        model_factory_features,
        "get_feature_columns",
        _feature_columns_stub(["feat1"]),
    )
    monkeypatch.setattr(predictor.torch.cuda, "is_available", lambda: False)
    monkeypatch.setattr(predictor.LSTMAttentionModule, "load_from_checkpoint", lambda path, map_location=None: FakeModel())
    monkeypatch.setattr(predictor, "insert_predictions", lambda engine, df: (_ for _ in ()).throw(RuntimeError("write failed")))

    result = predictor.predict_symbol(
        symbol,
        artifacts_dir=tmp_path,
        engine=cast(Engine, object()),
        prediction_date=date(2026, 4, 21),
        persist=True,
    )

    assert result is not None
    runtime_status = snapshot_runtime_status()
    assert runtime_status["prediction_db_issue_count"] == 1
    assert runtime_status["last_db_issue_operation"] == "insert_predictions"


def test_predict_symbol_falls_back_to_lstm_when_tabular_runtime_is_incompatible(tmp_path: Path, monkeypatch) -> None:
    reset_runtime_status()
    predictor.clear_model_cache()
    symbol = "AAPL"
    symbol_dir = tmp_path / symbol
    symbol_dir.mkdir(parents=True)
    (symbol_dir / "best.ckpt").write_text("checkpoint", encoding="utf-8")
    with open(symbol_dir / "scaler.pkl", "wb") as fh:
        pickle.dump({"mean": [0.0], "std": [1.0], "features": ["feat1"]}, cast(Any, fh))

    with open(symbol_dir / "lightgbm_model.pkl", "wb") as fh:
        pickle.dump(PickleableIncompatibleTabularModel(), cast(Any, fh))
    (symbol_dir / "config.json").write_text(
        json.dumps(
            {
                "data": {"sequence_length": 2, "forecast_horizon": 1, "include_sentiment_features": False},
                "run_id": "run-config",
                "feature_contract": _contract(["feat1"]),
                "artifact_routes": {
                    "selected_model": "lightgbm",
                    "models": {
                        "lightgbm": {
                            "inference_backend": "lightgbm_tabular",
                            "config_path": str(symbol_dir / "config.json"),
                            "model_path": str(symbol_dir / "lightgbm_model.pkl"),
                            "feature_columns": ["feat1"],
                        }
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    bars = pd.DataFrame({"close": list(range(62))})
    features = pd.DataFrame({"feat1": [float(i) for i in range(62)]})

    class FakeLstm:
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
        _feature_frame_stub(features),
    )
    monkeypatch.setattr(
        model_factory_features,
        "get_feature_columns",
        _feature_columns_stub(["feat1"]),
    )
    monkeypatch.setattr(predictor.torch.cuda, "is_available", lambda: False)
    monkeypatch.setattr(predictor.LSTMAttentionModule, "load_from_checkpoint", lambda path, map_location=None: FakeLstm())

    result = predictor.predict_symbol(
        symbol,
        artifacts_dir=tmp_path,
        engine=cast(Engine, object()),
        prediction_date=date(2026, 4, 21),
        persist=False,
    )

    assert result is not None
    assert result.to_dict(orient="records")[0]["selected_model"] == "lstm_attention"
    runtime_status = snapshot_runtime_status()
    assert runtime_status["prediction_artifact_issue_count"] == 1
    assert "tabular_model_incompatible:lightgbm" in str(runtime_status["last_fallback_reason"])


def test_predict_symbol_ignores_runtime_incompatible_calibrator(tmp_path: Path, monkeypatch) -> None:
    reset_runtime_status()
    predictor.clear_model_cache()
    symbol = "AAPL"
    symbol_dir = tmp_path / symbol
    symbol_dir.mkdir(parents=True)
    (symbol_dir / "best.ckpt").write_text("checkpoint", encoding="utf-8")
    with open(symbol_dir / "scaler.pkl", "wb") as fh:
        pickle.dump({"mean": [0.0], "std": [1.0], "features": ["feat1"]}, cast(Any, fh))

    class RuntimeBrokenCalibrator:
        def __init__(self) -> None:
            self.fitted = True
            self.method = "platt"

        def predict_proba(self, margin):
            raise ValueError("runtime mismatch")

    with open(symbol_dir / "calibrator.pkl", "wb") as fh:
        pickle.dump({"method": "platt", "slope": 1.0, "intercept": 0.0, "fitted": True, "max_iter": 100}, cast(Any, fh))
    (symbol_dir / "config.json").write_text(
        json.dumps(
            {
                "data": {"sequence_length": 2, "forecast_horizon": 1, "include_sentiment_features": False},
                "run_id": "run-config",
                "calibrator_path": str(symbol_dir / "calibrator.pkl"),
                "feature_contract": _contract(["feat1"]),
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
        _feature_frame_stub(features),
    )
    monkeypatch.setattr(
        model_factory_features,
        "get_feature_columns",
        _feature_columns_stub(["feat1"]),
    )
    monkeypatch.setattr(predictor.torch.cuda, "is_available", lambda: False)
    monkeypatch.setattr(predictor.LSTMAttentionModule, "load_from_checkpoint", lambda path, map_location=None: FakeModel())
    monkeypatch.setattr(predictor, "load_calibrator_cached", lambda path: RuntimeBrokenCalibrator())

    result = predictor.predict_symbol(
        symbol,
        artifacts_dir=tmp_path,
        engine=cast(Engine, object()),
        prediction_date=date(2026, 4, 21),
        persist=False,
    )

    assert result is not None
    row = result.to_dict(orient="records")[0]
    assert row["calibration_method"] == "none"
    runtime_status = snapshot_runtime_status()
    assert runtime_status["prediction_calibration_fallback_count"] == 1
    assert runtime_status["last_calibration_fallback_reason"] == "calibrator_incompatible:lstm_attention"


