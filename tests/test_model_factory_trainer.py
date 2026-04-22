from __future__ import annotations

from pathlib import Path
from typing import cast

import pandas as pd
import torch
from sqlalchemy.engine import Engine

from modelFactory.config import DataConfig, ModelConfig, TrainingConfig
from modelFactory import trainer


def _training_config(tmp_path: Path, *, min_history_days: int = 10) -> TrainingConfig:
    return TrainingConfig(
        data=DataConfig(sequence_length=2, forecast_horizon=1, min_history_days=min_history_days, train_ratio=0.6, val_ratio=0.2),
        model=ModelConfig(batch_size=4, max_epochs=1, patience=1),
        artifacts_dir=tmp_path,
        accelerator="cpu",
    )


def test_train_symbol_skips_when_history_too_short(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, dict]] = []
    monkeypatch.setattr(trainer, "ensure_registry_entry", lambda engine, symbol: 1)
    monkeypatch.setattr(trainer, "insert_training_run", lambda engine, run_id, registry_id, symbol, status="pending": None)
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
    monkeypatch.setattr(trainer, "insert_training_run", lambda engine, run_id, registry_id, symbol, status="pending": None)
    monkeypatch.setattr(trainer, "update_training_run", lambda engine, run_id, **kwargs: updates.append(kwargs))

    bars_df = pd.DataFrame({"close": list(range(12))})
    result = trainer.train_symbol("AAPL", bars_df, _training_config(tmp_path, min_history_days=10), engine=cast(Engine, object()))

    assert result.status == "skipped"
    assert result.skip_reason == "insufficient_sequences_after_split"
    assert updates and updates[-1]["status"] == "skipped"


def test_train_symbol_returns_failed_when_datamodule_setup_raises(monkeypatch, tmp_path: Path) -> None:
    class ExplodingDataModule:
        def __init__(self, bars_df, data_cfg, model_cfg, sentiment_df=None) -> None:
            pass

        def setup(self) -> None:
            raise RuntimeError("dataset boom")

    updates: list[dict] = []
    monkeypatch.setattr(trainer, "SymbolDataModule", ExplodingDataModule)
    monkeypatch.setattr(trainer, "ensure_registry_entry", lambda engine, symbol: 1)
    monkeypatch.setattr(trainer, "insert_training_run", lambda engine, run_id, registry_id, symbol, status="pending": None)
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


