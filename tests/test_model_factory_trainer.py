from __future__ import annotations

from pathlib import Path
from typing import cast
import json

import numpy as np
import pandas as pd
import pytest
import torch
from sqlalchemy.engine import Engine

from modelFactory.config import BaselineConfig, ChampionSelectionConfig, DataConfig, ModelConfig, TargetOptimizationConfig, TrainingConfig
from modelFactory import trainer


def _training_config(tmp_path: Path, *, min_history_days: int = 10) -> TrainingConfig:
    return TrainingConfig(
        data=DataConfig(sequence_length=2, forecast_horizon=1, min_history_days=min_history_days, train_ratio=0.6, val_ratio=0.2),
        model=ModelConfig(batch_size=4, max_epochs=1, patience=1),
        artifacts_dir=tmp_path,
        accelerator="cpu",
    )


def test_evaluate_best_checkpoint_accepts_empty_conditional_test_split(
    monkeypatch, tmp_path: Path,
) -> None:
    class FakeModel:
        pass

    val_outputs = {
        "logits": np.asarray([[0.0, 1.0], [1.0, 0.0]], dtype=np.float32),
        "labels": np.asarray([1, 0], dtype=np.int64),
        "raw_proba": np.asarray([0.7, 0.3], dtype=np.float64),
        "margins": np.asarray([1.0, -1.0], dtype=np.float64),
        "num_classes": 2,
    }
    monkeypatch.setattr(
        trainer.LSTMAttentionModule,
        "load_from_checkpoint",
        lambda *args, **kwargs: FakeModel(),
    )
    monkeypatch.setattr(trainer, "_build_loader", lambda *args, **kwargs: object())
    monkeypatch.setattr(trainer, "_collect_outputs", lambda model, loader, device: (
        val_outputs if loader is not None else {
            "logits": np.empty((0, 2), dtype=np.float32),
            "labels": np.empty(0, dtype=np.int64),
            "raw_proba": np.empty(0, dtype=np.float64),
            "margins": np.empty(0, dtype=np.float64),
            "num_classes": 2,
        }
    ))
    monkeypatch.setattr(trainer, "_fit_calibrator", lambda outputs, cfg: None)
    monkeypatch.setattr(trainer, "_compute_metrics", lambda *args, **kwargs: {"n_samples": 2})

    result = trainer._evaluate_best_checkpoint(
        tmp_path / "best.ckpt",
        batch_size=4,
        val_ds=object(),
        test_ds=None,
        val_frame=None,
        test_frame=None,
        cfg=_training_config(tmp_path),
    )

    assert result[0] == {"n_samples": 2}
    assert result[1] == {}
    assert result[5]["labels"].size == 0


def test_run_training_registry_writes_lstm_multi_horizon(monkeypatch, tmp_path: Path) -> None:
    """Option B (2026-08-15) : en multi-horizon, les métriques LSTM sont
    persistées avec horizon=h (comme les tabulaires) ; les horizons en échec
    sont ignorés et aucune ligne legacy sans horizon n'est écrite."""
    inserts: list[tuple[str, str, object]] = []
    monkeypatch.setattr(trainer, "update_training_run", lambda engine, run_id, **kwargs: None)
    monkeypatch.setattr(
        trainer, "insert_metrics",
        lambda engine, run_id, symbol, split_name, metrics,
        model_name="lstm_attention", horizon=None:
        inserts.append((model_name, split_name, horizon)),
    )
    monkeypatch.setattr(trainer, "upsert_metrics_full", lambda *args, **kwargs: None)
    monkeypatch.setattr(trainer, "replace_model_governance", lambda *args, **kwargs: None)
    monkeypatch.setattr(trainer, "upsert_directional_oos_metrics", lambda *args, **kwargs: None)

    lstm_horizons = {
        "h3": {"status": "completed", "horizon": 3,
               "val": {"f1_macro": 0.30}, "wf": {"f1_macro": 0.31}},
        "h20": {"status": "completed", "horizon": 20,
                "val": {"f1_macro": 0.33}, "test": {}, "wf": {"f1_macro": 0.34}},
        "h10": {"status": "failed", "reason": "boom"},
    }

    trainer._run_training_registry_writes(
        engine=cast(Engine, object()),
        run_id="r1",
        symbol="AAPL",
        trainer=cast(object, type("T", (), {"current_epoch": 1})()),
        best_ckpt=tmp_path / "missing.ckpt",
        scaler_path=tmp_path / "scaler.pkl",
        config_path=tmp_path / "config.json",
        val_metrics={"f1_macro": 0.33},
        test_metrics={"f1_macro": 0.32},
        walk_forward_metrics={"mean": {"f1_macro": 0.34}},
        all_metrics={},
        challengers={},
        artifact_routes_models={},
        selected_architecture="lstm_attention",
        selection_mode="auto",
        selection_metric="f1_macro",
        challenger_ranking=[],
        lstm_horizons=lstm_horizons,
    )

    lstm_rows = [(m, s, h) for m, s, h in inserts if m == "lstm_attention"]
    assert ("lstm_attention", "val", 3) in lstm_rows
    assert ("lstm_attention", "wf", 3) in lstm_rows
    assert ("lstm_attention", "val", 20) in lstm_rows
    assert ("lstm_attention", "wf", 20) in lstm_rows
    # L'horizon en échec n'est pas persisté
    assert not any(h == 10 for _, _, h in lstm_rows)
    # Pas de ligne legacy sans horizon en multi-horizon
    assert not any(h is None for _, _, h in lstm_rows)


def test_compute_metrics_persists_ternary_directional_oos_statistics() -> None:
    outputs = {
        "labels": np.array([-1, 1, -1]),
        "logits": np.array([[3.0, 0.0, -1.0], [-1.0, 0.0, 3.0], [3.0, 0.0, -1.0]]),
        "raw_proba": np.array([[0.8, 0.1, 0.1], [0.1, 0.1, 0.8], [0.8, 0.1, 0.1]]),
        "margins": np.zeros(3),
        "num_classes": 3,
    }

    metrics = trainer._compute_metrics(
        outputs,
        decision_threshold=0.5,
        future_returns=np.array([-0.03, 0.04, 0.02]),
    )

    directional = metrics["directional_oos_metrics"]
    assert directional["long"]["trade_count"] == 1
    assert directional["short"]["trade_count"] == 2
    assert directional["short"]["payoff"] == pytest.approx(1.5)


def test_compute_metrics_uses_ternary_policy_for_served_predictions() -> None:
    outputs = {
        "labels": np.array([0]),
        "logits": np.array([[0.0, 0.0, 0.0]]),
        # Argmax alone would select long. The canonical policy abstains because
        # the top-two margin is below its required threshold.
        "raw_proba": np.array([[0.20, 0.36, 0.44]]),
        "margins": np.zeros(1),
        "num_classes": 3,
    }

    metrics = trainer._compute_metrics(outputs, decision_threshold=0.5)

    assert metrics["pred_flat_pct"] == 100.0
    assert metrics["pred_long_pct"] == 0.0


def test_train_symbol_skips_when_history_too_short(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, dict]] = []
    monkeypatch.setattr(trainer, "ensure_registry_entry", lambda engine, symbol: 1)
    monkeypatch.setattr(trainer, "insert_training_run", lambda engine, run_id, registry_id, symbol, status="pending", **kwargs: None)
    monkeypatch.setattr(trainer, "update_training_run", lambda engine, run_id, **kwargs: calls.append((run_id, kwargs)))

    result = trainer.train_symbol(
        "AAPL",
        pd.DataFrame({"close": [1.0, 2.0, 3.0]}),
        _training_config(tmp_path, min_history_days=5),
        engine=cast(Engine, object()),
    )

    assert result.status == "skipped"
    assert result.skip_reason is not None and "history_too_short" in result.skip_reason
    assert calls and calls[-1][1]["status"] == "skipped"


def test_train_symbol_skips_when_sequences_are_empty(monkeypatch, tmp_path: Path) -> None:
    class FakeDataModule:
        def __init__(self, bars_df, data_cfg, model_cfg, sentiment_df=None) -> None:
            self.train_ds = []
            self.val_ds = []
            self.test_ds = []

        def setup(self) -> None:
            return None

    updates: list[dict] = []
    monkeypatch.setattr(trainer, "SymbolDataModule", FakeDataModule)
    monkeypatch.setattr(trainer, "ensure_registry_entry", lambda engine, symbol: 1)
    monkeypatch.setattr(trainer, "insert_training_run", lambda engine, run_id, registry_id, symbol, status="pending", **kwargs: None)
    monkeypatch.setattr(trainer, "update_training_run", lambda engine, run_id, **kwargs: updates.append(kwargs))

    bars_df = pd.DataFrame({"close": list(range(12))})
    result = trainer.train_symbol("AAPL", bars_df, _training_config(tmp_path, min_history_days=10), engine=cast(Engine, object()))

    assert result.status == "skipped"
    assert result.skip_reason == "insufficient_sequences_after_split"
    assert updates and updates[-1]["status"] == "skipped"


def test_conditional_train_symbol_skips_without_test_endpoints(monkeypatch, tmp_path: Path) -> None:
    class FakeDataModule:
        def __init__(self, bars_df, data_cfg, model_cfg, **kwargs) -> None:
            self.train_ds = [1]
            self.val_ds = [1]
            self.test_ds = []

        def setup(self) -> None:
            return None

    monkeypatch.setattr(trainer, "SymbolDataModule", FakeDataModule)
    monkeypatch.setattr(trainer, "ensure_registry_entry", lambda engine, symbol: 1)
    monkeypatch.setattr(trainer, "insert_training_run", lambda *args, **kwargs: None)
    monkeypatch.setattr(trainer, "update_training_run", lambda *args, **kwargs: None)
    cfg = TrainingConfig(
        data=DataConfig(sequence_length=2, forecast_horizon=1, min_history_days=10),
        model=ModelConfig(batch_size=4, max_epochs=1, patience=1),
        artifacts_dir=tmp_path,
        accelerator="cpu",
        directional_conditioning_enabled=True,
        directional_oracle_gate_path=tmp_path / "gate.parquet",
    )

    result = trainer.train_symbol(
        "AAPL",
        pd.DataFrame({"close": list(range(12))}),
        cfg,
        engine=cast(Engine, object()),
    )

    assert result.status == "skipped"
    assert result.skip_reason == "insufficient_conditional_test_sequences"


def test_train_symbol_returns_failed_when_datamodule_setup_raises(monkeypatch, tmp_path: Path) -> None:
    class ExplodingDataModule:
        def __init__(self, bars_df, data_cfg, model_cfg, sentiment_df=None) -> None:
            pass

        def setup(self) -> None:
            raise RuntimeError("dataset boom")

    updates: list[dict] = []
    monkeypatch.setattr(trainer, "SymbolDataModule", ExplodingDataModule)
    monkeypatch.setattr(trainer, "ensure_registry_entry", lambda engine, symbol: 1)
    monkeypatch.setattr(trainer, "insert_training_run", lambda engine, run_id, registry_id, symbol, status="pending", **kwargs: None)
    monkeypatch.setattr(trainer, "update_training_run", lambda engine, run_id, **kwargs: updates.append(kwargs))

    bars_df = pd.DataFrame({"close": list(range(12))})
    result = trainer.train_symbol("AAPL", bars_df, _training_config(tmp_path, min_history_days=10), engine=cast(Engine, object()))

    assert result.status == "failed"
    assert result.skip_reason is not None and "dataset boom" in result.skip_reason
    assert updates and updates[-1]["status"] == "failed"


def test_extract_best_epoch_reads_lightning_checkpoint(tmp_path: Path) -> None:
    ckpt_path = tmp_path / "best.ckpt"
    torch.save({"epoch": 7}, ckpt_path)

    assert trainer._extract_best_epoch(ckpt_path) == 7


def test_train_symbol_persists_challenger_ranking_and_routing(monkeypatch, tmp_path: Path) -> None:
    class FakeScaler:
        feature_names = ["feat1"]

        @staticmethod
        def state_dict() -> dict:
            return {"mean": [0.0], "std": [1.0], "features": ["feat1"]}

    class FakeLoader:
        num_workers = 0

    class FakeDataModule:
        def __init__(self, bars_df, data_cfg, model_cfg, **kwargs) -> None:
            frame = pd.DataFrame(
                {
                    "feat1": [0.1, 0.2, 0.3, 0.4],
                    "target": [1.0, 0.0, 1.0, 0.0],
                    "future_return": [0.02, -0.01, 0.03, -0.02],
                }
            )
            self.train_ds = [1]
            self.val_ds = [1]
            self.test_ds = [1]
            self.prepared_df = frame.copy()
            self.split = type("Split", (), {"val": frame.copy(), "test": frame.copy()})()
            self.n_features = 1
            self.scaler = FakeScaler()

        def setup(self) -> None:
            return None

        def train_dataloader(self):
            return FakeLoader()

    class FakeModel:
        def __init__(self, *args, **kwargs) -> None:
            pass

    class FakeCheckpoint:
        def __init__(self, dirpath=None, filename=None, monitor=None, mode=None, save_top_k=None):
            self.best_model_path = str(Path(dirpath) / "best.ckpt") if dirpath else ""

    class FakeEarlyStopping:
        def __init__(self, *args, **kwargs) -> None:
            pass

    class FakeLightningTrainer:
        def __init__(self, *args, **kwargs) -> None:
            self.strategy = type("Strategy", (), {"root_device": "cpu"})()
            self.current_epoch = 1

        def fit(self, model, datamodule=None, train_dataloaders=None, val_dataloaders=None) -> None:
            target_path = None
            callbacks = []
            if datamodule is not None:
                target_path = tmp_path / "AAPL" / "best.ckpt"
            for cb in callbacks:
                _ = cb
            if target_path is not None:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_text("checkpoint", encoding="utf-8")

    cfg = TrainingConfig(
        data=DataConfig(sequence_length=2, forecast_horizon=1, min_history_days=10, train_ratio=0.6, val_ratio=0.2),
        model=ModelConfig(batch_size=4, max_epochs=1, patience=1),
        baseline=BaselineConfig(enabled=True, enable_catboost=True),
        artifacts_dir=tmp_path,
        accelerator="cpu",
    )

    monkeypatch.setattr(trainer, "SymbolDataModule", FakeDataModule)
    monkeypatch.setattr(trainer, "LSTMAttentionModule", FakeModel)
    monkeypatch.setattr(trainer, "ModelCheckpoint", FakeCheckpoint)
    monkeypatch.setattr(trainer, "EarlyStopping", FakeEarlyStopping)
    monkeypatch.setattr(trainer.L, "Trainer", FakeLightningTrainer)
    monkeypatch.setattr(
        trainer,
        "_evaluate_best_checkpoint",
        lambda *args, **kwargs: (
            {"loss": 0.4, "auc": 0.7, "threshold_business_score": 0.65},
            {"loss": 0.5, "auc": 0.68, "threshold_business_score": 0.60},
            None,
            {"enabled": False, "selected_threshold": 0.5, "candidates": []},
            0.5,
            {},
        ),
    )
    monkeypatch.setattr(
        trainer,
        "run_lightgbm_baseline",
        lambda prepared_df, cfg, artifact_dir=None: {
            "status": "completed",
            "model_name": "lightgbm",
            "selection_score": 0.72,
            "val": {"auc": 0.71},
            "test": {"auc": 0.72, "threshold_business_score": 0.72},
            "feature_columns": ["feat1"],
            "selected_decision_threshold": 0.58,
            "inference_backend": "lightgbm_tabular",
            "artifact_paths": {"model_path": str(tmp_path / "AAPL" / "lightgbm_model.pkl"), "calibrator_path": None},
        },
    )
    monkeypatch.setattr(
        trainer,
        "run_catboost_baseline",
        lambda prepared_df, cfg, artifact_dir=None: {
            "status": "completed",
            "model_name": "catboost",
            "selection_score": 0.69,
            "val": {"auc": 0.70},
            "test": {"auc": 0.69, "threshold_business_score": 0.69},
            "feature_columns": ["feat1"],
            "selected_decision_threshold": 0.57,
            "inference_backend": "catboost_tabular",
            "artifact_paths": {"model_path": str(tmp_path / "AAPL" / "catboost_model.pkl"), "calibrator_path": None},
        },
    )

    result = trainer.train_symbol(
        "AAPL",
        pd.DataFrame({"close": list(range(12))}),
        cfg,
        engine=None,
        batch_id="campaign-20260716",
    )

    assert result.status == "completed"
    with open(tmp_path / "AAPL" / "config.json", encoding="utf-8") as fh:
        config_data = json.load(fh)
    with open(tmp_path / "AAPL" / "metrics.json", encoding="utf-8") as fh:
        metrics = json.load(fh)

    assert config_data["architecture_selected"] == "lstm_attention"
    assert config_data["batch_id"] == "campaign-20260716"
    assert config_data["artifacts_dir"] == str(tmp_path)
    assert config_data["artifact_routes"]["selected_model"] == "lstm_attention"
    assert config_data["feature_contract"]["feature_columns"] == ["feat1"]
    assert config_data["feature_contract"]["scaler_feature_names"] == ["feat1"]
    assert config_data["reproducibility"]["seed"] == 42
    assert config_data["artifact_routes"]["models"]["lightgbm"]["inference_backend"] == "lightgbm_tabular"
    assert config_data["artifact_routes"]["models"]["lightgbm"]["feature_contract"] is None
    assert config_data["artifact_routes"]["models"]["catboost"]["inference_backend"] == "catboost_tabular"
    assert metrics["champion"]["model_name"] == "lstm_attention"
    assert metrics["baseline_lightgbm"]["model_name"] == "lightgbm"
    assert metrics["baseline_catboost"]["model_name"] == "catboost"
    assert metrics["challengers"]["lstm_attention"]["model_name"] == "lstm_attention"
    assert {row["model_name"] for row in metrics["challengers"]["ranking"]} == {"lstm_attention", "lightgbm", "catboost"}


def test_train_symbol_auto_selection_keeps_lstm_when_lightgbm_artifact_is_not_inferable(monkeypatch, tmp_path: Path) -> None:
    class FakeScaler:
        feature_names = ["feat1"]

        @staticmethod
        def state_dict() -> dict:
            return {"mean": [0.0], "std": [1.0], "features": ["feat1"]}

    class FakeLoader:
        num_workers = 0

    class FakeDataModule:
        def __init__(self, bars_df, data_cfg, model_cfg, **kwargs) -> None:
            frame = pd.DataFrame({"feat1": [0.1, 0.2, 0.3, 0.4], "target": [1.0, 0.0, 1.0, 0.0], "future_return": [0.02, -0.01, 0.03, -0.02]})
            self.train_ds = [1]
            self.val_ds = [1]
            self.test_ds = [1]
            self.prepared_df = frame.copy()
            self.split = type("Split", (), {"val": frame.copy(), "test": frame.copy()})()
            self.n_features = 1
            self.scaler = FakeScaler()

        def setup(self) -> None:
            return None

        def train_dataloader(self):
            return FakeLoader()

    class FakeModel:
        def __init__(self, *args, **kwargs) -> None:
            pass

    class FakeCheckpoint:
        def __init__(self, dirpath=None, filename=None, monitor=None, mode=None, save_top_k=None):
            self.best_model_path = str(Path(dirpath) / "best.ckpt") if dirpath else ""

    class FakeEarlyStopping:
        def __init__(self, *args, **kwargs) -> None:
            pass

    class FakeLightningTrainer:
        def __init__(self, *args, **kwargs) -> None:
            self.strategy = type("Strategy", (), {"root_device": "cpu"})()
            self.current_epoch = 1

        def fit(self, model, datamodule=None, train_dataloaders=None, val_dataloaders=None) -> None:
            target_path = tmp_path / "AAPL" / "best.ckpt"
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text("checkpoint", encoding="utf-8")

    cfg = TrainingConfig(
        data=DataConfig(sequence_length=2, forecast_horizon=1, min_history_days=10, train_ratio=0.6, val_ratio=0.2),
        model=ModelConfig(batch_size=4, max_epochs=1, patience=1),
        baseline=BaselineConfig(enabled=True, enable_catboost=True),
        champion_selection=ChampionSelectionConfig(enabled=True, allow_auto_selection=True, default_champion="lstm_attention"),
        artifacts_dir=tmp_path,
        accelerator="cpu",
    )

    monkeypatch.setattr(trainer, "SymbolDataModule", FakeDataModule)
    monkeypatch.setattr(trainer, "LSTMAttentionModule", FakeModel)
    monkeypatch.setattr(trainer, "ModelCheckpoint", FakeCheckpoint)
    monkeypatch.setattr(trainer, "EarlyStopping", FakeEarlyStopping)
    monkeypatch.setattr(trainer.L, "Trainer", FakeLightningTrainer)
    monkeypatch.setattr(
        trainer,
        "_evaluate_best_checkpoint",
        lambda *args, **kwargs: (
            {"loss": 0.4, "auc": 0.70, "threshold_business_score": 0.65},
            {"loss": 0.5, "auc": 0.68, "threshold_business_score": 0.60},
            None,
            {"enabled": False, "selected_threshold": 0.5, "candidates": []},
            0.5,
            {},
        ),
    )
    monkeypatch.setattr(
        trainer,
        "run_lightgbm_baseline",
        lambda prepared_df, cfg, artifact_dir=None: {
            "status": "completed",
            "model_name": "lightgbm",
            "selection_score": 0.90,
            "val": {"auc": 0.90},
            "test": {"auc": 0.90, "threshold_business_score": 0.90},
            "feature_columns": ["feat1"],
            "selected_decision_threshold": 0.61,
            "inference_backend": "lightgbm_tabular",
            "artifact_paths": {"model_path": str(tmp_path / "AAPL" / "lightgbm_model.pkl"), "calibrator_path": None},
        },
    )
    monkeypatch.setattr(
        trainer,
        "run_catboost_baseline",
        lambda prepared_df, cfg, artifact_dir=None: {
            "status": "completed",
            "model_name": "catboost",
            "selection_score": 0.88,
            "val": {"auc": 0.88},
            "test": {"auc": 0.88, "threshold_business_score": 0.88},
            "feature_columns": ["feat1"],
            "selected_decision_threshold": 0.59,
            "inference_backend": "catboost_tabular",
            "artifact_paths": {"model_path": str(tmp_path / "AAPL" / "catboost_model.pkl"), "calibrator_path": None},
        },
    )

    result = trainer.train_symbol("AAPL", pd.DataFrame({"close": list(range(12))}), cfg, engine=None)

    assert result.status == "completed"
    with open(tmp_path / "AAPL" / "config.json", encoding="utf-8") as fh:
        config_data = json.load(fh)
    with open(tmp_path / "AAPL" / "metrics.json", encoding="utf-8") as fh:
        metrics = json.load(fh)

    assert config_data["architecture_selected"] == "lstm_attention"
    assert config_data["artifact_routes"]["selected_model"] == "lstm_attention"
    assert metrics["champion"]["model_name"] == "lstm_attention"
    assert any(row["model_name"] == "lightgbm" and row["selection_eligible"] is False for row in metrics["challengers"]["ranking"])


def test_train_symbol_persists_model_governance_snapshot(monkeypatch, tmp_path: Path) -> None:
    class FakeScaler:
        feature_names = ["feat1"]

        @staticmethod
        def state_dict() -> dict:
            return {"mean": [0.0], "std": [1.0], "features": ["feat1"]}

    class FakeLoader:
        num_workers = 0

    class FakeDataModule:
        def __init__(self, bars_df, data_cfg, model_cfg, **kwargs) -> None:
            frame = pd.DataFrame({"feat1": [0.1, 0.2, 0.3, 0.4], "target": [1.0, 0.0, 1.0, 0.0], "future_return": [0.02, -0.01, 0.03, -0.02]})
            self.train_ds = [1]
            self.val_ds = [1]
            self.test_ds = [1]
            self.prepared_df = frame.copy()
            self.split = type("Split", (), {"val": frame.copy(), "test": frame.copy()})()
            self.n_features = 1
            self.scaler = FakeScaler()

        def setup(self) -> None:
            return None

        def train_dataloader(self):
            return FakeLoader()

    class FakeModel:
        def __init__(self, *args, **kwargs) -> None:
            pass

    class FakeCheckpoint:
        def __init__(self, dirpath=None, filename=None, monitor=None, mode=None, save_top_k=None):
            self.best_model_path = str(Path(dirpath) / "best.ckpt") if dirpath else ""

    class FakeEarlyStopping:
        def __init__(self, *args, **kwargs) -> None:
            pass

    class FakeLightningTrainer:
        def __init__(self, *args, **kwargs) -> None:
            self.strategy = type("Strategy", (), {"root_device": "cpu"})()
            self.current_epoch = 1

        def fit(self, model, datamodule=None, train_dataloaders=None, val_dataloaders=None) -> None:
            target_path = tmp_path / "AAPL" / "best.ckpt"
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text("checkpoint", encoding="utf-8")

    governance_calls: list[dict[str, object]] = []
    metrics_calls: list[tuple[str, str]] = []

    cfg = TrainingConfig(
        data=DataConfig(sequence_length=2, forecast_horizon=1, min_history_days=10, train_ratio=0.6, val_ratio=0.2),
        model=ModelConfig(batch_size=4, max_epochs=1, patience=1),
        baseline=BaselineConfig(enabled=True, enable_catboost=False),
        champion_selection=ChampionSelectionConfig(enabled=True, allow_auto_selection=True, default_champion="lstm_attention"),
        artifacts_dir=tmp_path,
        accelerator="cpu",
    )

    monkeypatch.setattr(trainer, "SymbolDataModule", FakeDataModule)
    monkeypatch.setattr(trainer, "LSTMAttentionModule", FakeModel)
    monkeypatch.setattr(trainer, "ModelCheckpoint", FakeCheckpoint)
    monkeypatch.setattr(trainer, "EarlyStopping", FakeEarlyStopping)
    monkeypatch.setattr(trainer.L, "Trainer", FakeLightningTrainer)
    monkeypatch.setattr(trainer, "ensure_registry_entry", lambda engine, symbol: 1)
    monkeypatch.setattr(trainer, "insert_training_run", lambda engine, run_id, registry_id, symbol, status="pending", **kwargs: None)
    monkeypatch.setattr(trainer, "update_training_run", lambda engine, run_id, **kwargs: None)
    monkeypatch.setattr(trainer, "insert_metrics", lambda engine, run_id, symbol, split_name, metrics, **kwargs: metrics_calls.append((run_id, split_name)))
    monkeypatch.setattr(trainer, "replace_model_governance", lambda engine, **kwargs: governance_calls.append(kwargs) or 2)
    monkeypatch.setattr(
        trainer,
        "_evaluate_best_checkpoint",
        lambda *args, **kwargs: (
            {"loss": 0.4, "auc": 0.70, "threshold_business_score": 0.65},
            {"loss": 0.5, "auc": 0.68, "threshold_business_score": 0.60},
            None,
            {"enabled": False, "selected_threshold": 0.5, "candidates": []},
            0.5,
            {},
        ),
    )
    monkeypatch.setattr(
        trainer,
        "run_lightgbm_baseline",
        lambda prepared_df, cfg, artifact_dir=None: {
            "status": "completed",
            "model_name": "lightgbm",
            "selection_score": 0.90,
            "selection_eligible": True,
            "test": {"auc": 0.90, "threshold_business_score": 0.90},
            "feature_columns": ["feat1"],
            "selected_decision_threshold": 0.61,
            "inference_backend": "lightgbm_tabular",
            "artifact_paths": {"model_path": str(tmp_path / "AAPL" / "lightgbm_model.pkl"), "calibrator_path": None},
        },
    )
    monkeypatch.setattr(trainer, "run_catboost_baseline", lambda prepared_df, cfg, artifact_dir=None: {})

    result = trainer.train_symbol("AAPL", pd.DataFrame({"close": list(range(12))}), cfg, engine=cast(Engine, object()))

    assert result.status == "completed"
    assert metrics_calls == [(result.run_id, "val"), (result.run_id, "test")]
    assert len(governance_calls) == 1
    governance_call = governance_calls[0]
    assert governance_call["run_id"] == result.run_id
    assert governance_call["selected_model"] == "lstm_attention"
    assert any(row["model_name"] == "lightgbm" for row in governance_call["ranking"])


def test_train_symbol_continues_when_registry_insert_fails(monkeypatch, tmp_path: Path) -> None:
    class FakeScaler:
        feature_names = ["feat1"]

        @staticmethod
        def state_dict() -> dict:
            return {"mean": [0.0], "std": [1.0], "features": ["feat1"]}

    class FakeLoader:
        num_workers = 0

    class FakeDataModule:
        def __init__(self, bars_df, data_cfg, model_cfg, **kwargs) -> None:
            frame = pd.DataFrame({"feat1": [0.1, 0.2, 0.3, 0.4], "target": [1.0, 0.0, 1.0, 0.0], "future_return": [0.02, -0.01, 0.03, -0.02]})
            self.train_ds = [1]
            self.val_ds = [1]
            self.test_ds = [1]
            self.prepared_df = frame.copy()
            self.split = type("Split", (), {"val": frame.copy(), "test": frame.copy()})()
            self.n_features = 1
            self.scaler = FakeScaler()

        def setup(self) -> None:
            return None

        def train_dataloader(self):
            return FakeLoader()

    class FakeModel:
        def __init__(self, *args, **kwargs) -> None:
            pass

    class FakeCheckpoint:
        def __init__(self, dirpath=None, filename=None, monitor=None, mode=None, save_top_k=None):
            self.best_model_path = str(Path(dirpath) / "best.ckpt") if dirpath else ""

    class FakeEarlyStopping:
        def __init__(self, *args, **kwargs) -> None:
            pass

    class FakeLightningTrainer:
        def __init__(self, *args, **kwargs) -> None:
            self.strategy = type("Strategy", (), {"root_device": "cpu"})()
            self.current_epoch = 1

        def fit(self, model, datamodule=None, train_dataloaders=None, val_dataloaders=None) -> None:
            target_path = tmp_path / "AAPL" / "best.ckpt"
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text("checkpoint", encoding="utf-8")

    monkeypatch.setattr(trainer, "SymbolDataModule", FakeDataModule)
    monkeypatch.setattr(trainer, "LSTMAttentionModule", FakeModel)
    monkeypatch.setattr(trainer, "ModelCheckpoint", FakeCheckpoint)
    monkeypatch.setattr(trainer, "EarlyStopping", FakeEarlyStopping)
    monkeypatch.setattr(trainer.L, "Trainer", FakeLightningTrainer)
    monkeypatch.setattr(trainer, "ensure_registry_entry", lambda engine, symbol: (_ for _ in ()).throw(RuntimeError("db down")))
    monkeypatch.setattr(
        trainer,
        "_evaluate_best_checkpoint",
        lambda *args, **kwargs: (
            {"loss": 0.4, "auc": 0.70, "threshold_business_score": 0.65},
            {"loss": 0.5, "auc": 0.68, "threshold_business_score": 0.60},
            None,
            {"enabled": False, "selected_threshold": 0.5, "candidates": []},
            0.5,
            {},
        ),
    )
    monkeypatch.setattr(trainer, "run_lightgbm_baseline", lambda prepared_df, cfg, artifact_dir=None: {})
    monkeypatch.setattr(trainer, "run_catboost_baseline", lambda prepared_df, cfg, artifact_dir=None: {})

    result = trainer.train_symbol("AAPL", pd.DataFrame({"close": list(range(12))}), _training_config(tmp_path), engine=cast(Engine, object()))

    assert result.status == "completed"
    assert (tmp_path / "AAPL" / "config.json").exists()
    assert (tmp_path / "AAPL" / "metrics.json").exists()


def test_train_symbol_target_optimization_uses_train_split_only(monkeypatch, tmp_path: Path) -> None:
    class FakeScaler:
        feature_names = ["feat1"]

        @staticmethod
        def state_dict() -> dict:
            return {"mean": [0.0], "std": [1.0], "features": ["feat1"]}

    class FakeLoader:
        num_workers = 0

    class FakeDataModule:
        def __init__(self, bars_df, data_cfg, model_cfg, **kwargs) -> None:
            frame = pd.DataFrame(
                {
                    "feat1": [0.1, 0.2, 0.3, 0.4],
                    "target": [1.0, 0.0, 1.0, 0.0],
                    "future_return": [0.02, -0.01, 0.03, -0.02],
                }
            )
            self.train_ds = [1]
            self.val_ds = [1]
            self.test_ds = [1]
            self.prepared_df = frame.copy()
            self.split = type("Split", (), {"val": frame.copy(), "test": frame.copy()})()
            self.n_features = 1
            self.scaler = FakeScaler()

        def setup(self) -> None:
            return None

        def train_dataloader(self):
            return FakeLoader()

    class FakeModel:
        def __init__(self, *args, **kwargs) -> None:
            pass

    class FakeCheckpoint:
        def __init__(self, dirpath=None, filename=None, monitor=None, mode=None, save_top_k=None):
            self.best_model_path = str(Path(dirpath) / "best.ckpt") if dirpath else ""

    class FakeEarlyStopping:
        def __init__(self, *args, **kwargs) -> None:
            pass

    class FakeLightningTrainer:
        def __init__(self, *args, **kwargs) -> None:
            self.strategy = type("Strategy", (), {"root_device": "cpu"})()
            self.current_epoch = 1

        def fit(self, model, datamodule=None, train_dataloaders=None, val_dataloaders=None) -> None:
            target_path = tmp_path / "AAPL" / "best.ckpt"
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text("checkpoint", encoding="utf-8")

    optimization_frame = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=8, freq="D"),
            "close": [10.0, 10.5, 11.0, 10.8, 11.2, 11.5, 11.7, 11.9],
            "adj_close": [10.0, 10.5, 11.0, 10.8, 11.2, 11.5, 11.7, 11.9],
            "feat1": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8],
        }
    )
    train_only_frame = optimization_frame.iloc[:4].reset_index(drop=True)
    optimization_calls: list[pd.DataFrame] = []

    cfg = TrainingConfig(
        data=DataConfig(sequence_length=2, forecast_horizon=1, min_history_days=10, train_ratio=0.6, val_ratio=0.2),
        model=ModelConfig(batch_size=4, max_epochs=1, patience=1),
        target_optimization=TargetOptimizationConfig(enabled=True, candidate_horizons=(1, 2), min_trades_fraction=0.05),
        artifacts_dir=tmp_path,
        accelerator="cpu",
    )

    monkeypatch.setattr(trainer, "SymbolDataModule", FakeDataModule)
    monkeypatch.setattr(trainer, "prepare_symbol_frame", lambda *args, **kwargs: optimization_frame.copy())
    monkeypatch.setattr(
        trainer,
        "chrono_split",
        lambda df, train_ratio, val_ratio, forecast_horizon=0: type(
            "Split",
            (),
            {
                "train": train_only_frame.copy(),
                "val": optimization_frame.iloc[4:6].reset_index(drop=True),
                "test": optimization_frame.iloc[6:].reset_index(drop=True),
            },
        )(),
    )
    monkeypatch.setattr(
        trainer,
        "optimize_target_parameters",
        lambda df, data_cfg, opt_cfg: optimization_calls.append(df.copy()) or {
            "selected_horizon": 2,
            "selected_target_up_threshold": 0.01,
            "selected_target_down_threshold": -0.01,
            "selected_score": 0.42,
            "candidates": [],
        },
    )
    monkeypatch.setattr(trainer, "LSTMAttentionModule", FakeModel)
    monkeypatch.setattr(trainer, "ModelCheckpoint", FakeCheckpoint)
    monkeypatch.setattr(trainer, "EarlyStopping", FakeEarlyStopping)
    monkeypatch.setattr(trainer.L, "Trainer", FakeLightningTrainer)
    monkeypatch.setattr(
        trainer,
        "_evaluate_best_checkpoint",
        lambda *args, **kwargs: (
            {"loss": 0.4, "auc": 0.70, "threshold_business_score": 0.65},
            {"loss": 0.5, "auc": 0.68, "threshold_business_score": 0.60},
            None,
            {"enabled": False, "selected_threshold": 0.5, "candidates": []},
            0.5,
            {},
        ),
    )
    monkeypatch.setattr(trainer, "run_lightgbm_baseline", lambda prepared_df, cfg, artifact_dir=None: {})
    monkeypatch.setattr(trainer, "run_catboost_baseline", lambda prepared_df, cfg, artifact_dir=None: {})

    result = trainer.train_symbol("AAPL", pd.DataFrame({"close": list(range(12))}), cfg, engine=None)

    assert result.status == "completed"
    assert len(optimization_calls) == 1
    pd.testing.assert_frame_equal(optimization_calls[0], train_only_frame)
    with open(tmp_path / "AAPL" / "metrics.json", encoding="utf-8") as fh:
        metrics = json.load(fh)
    assert metrics["target_optimization"]["fit_scope"] == "train_split_only"
    assert metrics["target_optimization"]["fit_rows"] == len(train_only_frame)


