"""modelFactory/trainer.py — Service d'entraînement mono-symbole."""
from __future__ import annotations

import json
import logging
import pickle
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import torch

try:
    import lightning as L
    from lightning.pytorch.callbacks import EarlyStopping, ModelCheckpoint
except ImportError:  # pragma: no cover
    import pytorch_lightning as L  # type: ignore[no-redef]
    from pytorch_lightning.callbacks import EarlyStopping, ModelCheckpoint  # type: ignore[no-redef]

from sqlalchemy.engine import Engine

from modelFactory.config import TrainingConfig
from modelFactory.dataset import SymbolDataModule
from modelFactory.db_registry import (
    ensure_registry_entry,
    insert_metrics,
    insert_training_run,
    update_training_run,
)
from modelFactory.model import LSTMAttentionModule

LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

class TrainResult:
    """Résultat d'un entraînement mono-symbole."""

    def __init__(self, symbol: str, run_id: str, status: str, metrics: Optional[dict[str, Any]] = None,
                 skip_reason: Optional[str] = None) -> None:
        self.symbol = symbol
        self.run_id = run_id
        self.status = status
        self.metrics = metrics or {}
        self.skip_reason = skip_reason


# ---------------------------------------------------------------------------
# Trainer service
# ---------------------------------------------------------------------------

def train_symbol(
    symbol: str,
    bars_df: "pd.DataFrame",
    cfg: TrainingConfig,
    engine: Optional[Engine] = None,
) -> TrainResult:
    """Entraîne un modèle LSTM+Attention pour un symbole unique.

    Returns:
        TrainResult avec status completed|skipped|failed.
    """
    import pandas as pd  # noqa: F811 (lazy import pour picklability worker)

    # Optimisation Tensor Cores (RTX 30xx/40xx/50xx)
    torch.set_float32_matmul_precision("medium")

    run_id = f"{symbol}_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}"
    registry_id: int = 0

    # --- DB: create run entry ---
    if engine is not None:
        registry_id = ensure_registry_entry(engine, symbol)
        insert_training_run(engine, run_id, registry_id, symbol, status="running")

    try:
        # --- Check history ---
        if len(bars_df) < cfg.data.min_history_days:
            reason = f"history_too_short rows={len(bars_df)} min={cfg.data.min_history_days}"
            LOGGER.warning("train_symbol skipped symbol=%s reason=%s", symbol, reason)
            if engine:
                update_training_run(engine, run_id, status="skipped", skip_reason=reason, finished_at=datetime.now(timezone.utc))
            return TrainResult(symbol, run_id, "skipped", skip_reason=reason)

        # --- DataModule ---
        dm = SymbolDataModule(bars_df, cfg.data, cfg.model)
        dm.setup()

        if dm.train_ds is None or dm.val_ds is None or len(dm.train_ds) == 0 or len(dm.val_ds) == 0:
            reason = "insufficient_sequences_after_split"
            LOGGER.warning("train_symbol skipped symbol=%s reason=%s", symbol, reason)
            if engine:
                update_training_run(engine, run_id, status="skipped", skip_reason=reason, finished_at=datetime.now(timezone.utc))
            return TrainResult(symbol, run_id, "skipped", skip_reason=reason)

        # --- Artifact dir ---
        sym_dir = (Path(cfg.artifacts_dir) / symbol).resolve()
        sym_dir.mkdir(parents=True, exist_ok=True)

        # --- Model ---
        model = LSTMAttentionModule(
            input_size=dm.n_features,
            hidden_size=cfg.model.hidden_size,
            num_layers=cfg.model.num_layers,
            dropout=cfg.model.dropout,
            learning_rate=cfg.model.learning_rate,
            weight_decay=cfg.model.weight_decay,
            num_classes=cfg.model.num_classes,
        )

        # --- Callbacks ---
        ckpt_callback = ModelCheckpoint(
            dirpath=str(sym_dir),
            filename="best",
            monitor="val_loss",
            mode="min",
            save_top_k=1,
        )
        early_stop = EarlyStopping(monitor="val_loss", patience=cfg.model.patience, mode="min")

        # --- Trainer ---
        trainer = L.Trainer(
            max_epochs=cfg.model.max_epochs,
            accelerator=cfg.accelerator,
            devices=1,
            callbacks=[ckpt_callback, early_stop],
            enable_progress_bar=False,
            logger=False,
            enable_model_summary=False,
        )

        trainer.fit(model, datamodule=dm)

        # --- Test ---
        test_results: list[dict] = []
        if dm.test_ds is not None and len(dm.test_ds) > 0:
            test_results = trainer.test(model, datamodule=dm)

        # --- Collect metrics ---
        val_metrics = {
            "loss": ckpt_callback.best_model_score.item() if ckpt_callback.best_model_score is not None else None,
            "directional_accuracy": trainer.callback_metrics.get("val_acc", torch.tensor(0.0)).item(),
            "precision": trainer.callback_metrics.get("val_precision", torch.tensor(0.0)).item(),
            "recall": trainer.callback_metrics.get("val_recall", torch.tensor(0.0)).item(),
            "auc": trainer.callback_metrics.get("val_auc", torch.tensor(0.0)).item(),
        }
        test_metrics = {}
        if test_results:
            test_metrics = {
                "loss": test_results[0].get("test_loss"),
                "directional_accuracy": test_results[0].get("test_acc"),
            }

        # --- Save artifacts ---
        # Copy best checkpoint to a canonical name
        best_ckpt = sym_dir / "best.ckpt"
        if ckpt_callback.best_model_path:
            best_src = Path(ckpt_callback.best_model_path).resolve()
            best_dst = best_ckpt.resolve()
            if best_src.exists() and best_src != best_dst:
                best_dst.unlink(missing_ok=True)
                best_src.rename(best_dst)
            elif not best_dst.exists() and best_src.exists():
                # same file, nothing to do
                pass

        # Scaler
        scaler_path = sym_dir / "scaler.pkl"
        with open(scaler_path, "wb") as f:
            pickle.dump(dm.scaler.state_dict(), f)

        # Config
        config_path = sym_dir / "config.json"
        config_data = {
            "data": asdict(cfg.data),
            "model": {**asdict(cfg.model), "input_size": dm.n_features},
            "symbol": symbol,
            "run_id": run_id,
            "feature_columns": dm.scaler.feature_names,
        }
        with open(config_path, "w") as f:
            json.dump(config_data, f, indent=2, default=str)

        # Metrics JSON
        all_metrics = {"val": val_metrics, "test": test_metrics}
        with open(sym_dir / "metrics.json", "w") as f:
            json.dump(all_metrics, f, indent=2)

        # --- DB: persist ---
        if engine is not None:
            update_training_run(
                engine, run_id,
                status="completed",
                finished_at=datetime.now(timezone.utc),
                epochs_run=trainer.current_epoch,
                best_epoch=ckpt_callback.best_model_score is not None and trainer.current_epoch or 0,
                checkpoint_path=str(best_ckpt),
                scaler_path=str(scaler_path),
                config_path=str(config_path),
            )
            insert_metrics(engine, run_id, symbol, "val", val_metrics)
            if test_metrics:
                insert_metrics(engine, run_id, symbol, "test", test_metrics)

        LOGGER.info("train_symbol completed symbol=%s run_id=%s val_loss=%.4f",
                     symbol, run_id, val_metrics.get("loss", -1))
        return TrainResult(symbol, run_id, "completed", metrics=all_metrics)

    except Exception as exc:
        LOGGER.exception("train_symbol failed symbol=%s run_id=%s", symbol, run_id)
        if engine is not None:
            update_training_run(engine, run_id, status="failed", skip_reason=str(exc)[:200], finished_at=datetime.now(timezone.utc))
        return TrainResult(symbol, run_id, "failed", skip_reason=str(exc))





