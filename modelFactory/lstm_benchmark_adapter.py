"""modelFactory/lstm_benchmark_adapter.py — Adaptateur LSTM pour BenchmarkRunner (Point 4.1).

Permet au ``BenchmarkRunner`` d'intégrer l'architecture LSTM+Attention dans le
protocole de benchmark unifié (mêmes folds, mêmes baselines, multi-seeds).

L'adaptateur prend un DataFrame tabulaire préparé (``prepared_df``) déjà splitté
et :
1. Construit des séquences temporelles depuis les features tabulaires
2. Entraîne un ``LSTMAttentionModule`` via PyTorch Lightning
3. Retourne les métriques dans le format standard de ``run_tabular_baseline()``

Usage ::

    from modelFactory.lstm_benchmark_adapter import run_lstm_benchmark
    result = run_lstm_benchmark(prepared_df, training_cfg,
                                seq_len=20, artifact_dir=Path("lstm_artifacts"))
"""
from __future__ import annotations

import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader

try:
    import lightning as L
except ImportError:  # pragma: no cover
    import pytorch_lightning as L  # type: ignore[no-redef]

from modelFactory.dataset import SequenceDataset
from modelFactory.model import LSTMAttentionModule

LOGGER = logging.getLogger(__name__)

# ── Constantes ──────────────────────────────────────────────────────────────

DEFAULT_SEQ_LEN = 20
DEFAULT_BATCH_SIZE = 32
DEFAULT_MAX_EPOCHS = 50
DEFAULT_PATIENCE = 7
DEFAULT_HIDDEN_SIZE = 128
DEFAULT_NUM_LAYERS = 2
DEFAULT_DROPOUT = 0.3
DEFAULT_LEARNING_RATE = 1e-3


# ── Helpers ─────────────────────────────────────────────────────────────────


def _build_sequences(
    df: pd.DataFrame,
    feature_cols: list[str],
    seq_len: int,
    target_col: str = "target",
) -> tuple[np.ndarray, np.ndarray]:
    """Construit des séquences [N, seq_len, n_features] depuis un DataFrame tabulaire.

    Les lignes sont groupées en fenêtres glissantes de ``seq_len``.
    La target est celle de la dernière ligne de chaque fenêtre.
    """
    X_arr = df[feature_cols].to_numpy(float)
    y_arr = df[target_col].astype(int).to_numpy()

    n_samples = len(df) - seq_len + 1
    if n_samples <= 0:
        return np.empty((0, seq_len, len(feature_cols))), np.empty((0,))

    X_seq = np.lib.stride_tricks.sliding_window_view(X_arr, (seq_len, X_arr.shape[1]))  # type: ignore[arg-type]
    # sliding_window_view returns shape [n_samples, 1, seq_len, n_features] — squeeze the 1
    X_seq = X_seq[:, 0, :, :]  # [n_samples, seq_len, n_features]
    y_seq = y_arr[seq_len - 1:]  # target de la dernière ligne

    return X_seq, y_seq


def _validate_target_distribution(y_train: np.ndarray, y_val: np.ndarray) -> dict[str, object]:
    """Vérifie la distribution des targets dans les folds."""
    diagnostics: dict[str, object] = {}
    for name, y in [("train", y_train), ("val", y_val)]:
        unique, counts = np.unique(y, return_counts=True)
        dist = dict(zip(unique.tolist(), counts.tolist()))
        diagnostics[name] = {"n": len(y), "distribution": dist}
    return diagnostics


# ── Fonction principale ─────────────────────────────────────────────────────


def run_lstm_benchmark(
    prepared_df: pd.DataFrame,
    cfg: Any,  # TrainingConfig
    *,
    seq_len: int = DEFAULT_SEQ_LEN,
    batch_size: int = DEFAULT_BATCH_SIZE,
    max_epochs: int = DEFAULT_MAX_EPOCHS,
    patience: int = DEFAULT_PATIENCE,
    hidden_size: int = DEFAULT_HIDDEN_SIZE,
    num_layers: int = DEFAULT_NUM_LAYERS,
    dropout: float = DEFAULT_DROPOUT,
    learning_rate: float = DEFAULT_LEARNING_RATE,
    artifact_dir: Path | None = None,
) -> dict[str, Any]:
    """Exécute un benchmark LSTM pour un symbole unique.

    Parameters
    ----------
    prepared_df : pd.DataFrame
        DataFrame déjà préparé avec colonnes features et ``target``.
    cfg : TrainingConfig
        Configuration d'entraînement (contient data, baseline, etc.).
    seq_len : int
        Longueur des séquences temporelles.
    batch_size : int
        Taille des batchs.
    max_epochs : int
        Nombre max d'époques.
    patience : int
        Patience pour l'early stopping.
    hidden_size : int
        Taille cachée du LSTM.
    num_layers : int
        Nombre de couches LSTM.
    dropout : float
        Dropout rate.
    learning_rate : float
        Learning rate.
    artifact_dir : Path | None
        Répertoire pour sauvegarder les artefacts.

    Returns
    -------
    dict
        Résultat au format standard ``run_tabular_baseline()`` :
        ``{"status", "model_name", "seed", "val": {...}, "test": {...},
           "artifact_paths": {...}}``
    """
    from modelFactory.dataset import tabular_split
    from modelFactory.evaluation import compute_multiclass_metrics, check_model_collapse
    from modelFactory.features import get_feature_columns

    t0 = time.perf_counter()

    # ── 1. Résoudre les colonnes de features ──────────────────────────
    data_cfg = cfg.data
    is_ternary = data_cfg.target_mode == "ternary"
    num_classes = 3 if is_ternary else 2

    feature_cols = get_feature_columns(
        include_sentiment=data_cfg.include_sentiment_features,
        feature_set=getattr(data_cfg, "feature_set", None),
        include_cross_sectional=getattr(data_cfg, "enable_cross_sectional_features", False),
        include_selector_context=getattr(data_cfg, "include_selector_context_features", False),
        include_short_score=getattr(data_cfg, "include_short_score_features", False),
    )
    available_cols = [c for c in feature_cols if c in prepared_df.columns]
    if not available_cols:
        return {"status": "skipped", "reason": "no_feature_columns_available"}

    # ── 2. Split train/val/test ──────────────────────────────────────
    try:
        train_df, val_df, test_df = tabular_split(
            prepared_df,
            train_ratio=data_cfg.train_ratio,
            val_ratio=data_cfg.val_ratio,
            forecast_horizon=getattr(data_cfg, "forecast_horizon", 1),
        )
    except Exception as exc:
        return {"status": "failed", "reason": f"split_error:{exc}"}

    # ── 3. Construire les séquences ──────────────────────────────────
    X_train_seq, y_train = _build_sequences(train_df, available_cols, seq_len, "target")
    X_val_seq, y_val = _build_sequences(val_df, available_cols, seq_len, "target")
    X_test_seq, y_test = _build_sequences(test_df, available_cols, seq_len, "target")

    min_samples = seq_len + 10
    if len(X_train_seq) < min_samples:
        return {
            "status": "skipped",
            "reason": f"insufficient_data: train={len(X_train_seq)} < {min_samples}",
            "seq_len": seq_len,
        }

    # ── 4. Normaliser les données ────────────────────────────────────
    # Scale per feature sur le train
    train_mean = X_train_seq.mean(axis=(0, 1), keepdims=True)
    train_std = X_train_seq.std(axis=(0, 1), keepdims=True)
    train_std[train_std == 0] = 1.0  # éviter division par zéro

    X_train_seq = (X_train_seq - train_mean) / train_std
    X_val_seq = (X_val_seq - train_mean) / train_std
    if len(X_test_seq) > 0:
        X_test_seq = (X_test_seq - train_mean) / train_std

    # ── 5. Créer les DataLoaders ─────────────────────────────────────
    train_ds = SequenceDataset(X_train_seq, y_train)
    val_ds = SequenceDataset(X_val_seq, y_val)

    train_loader = DataLoader(
        train_ds, batch_size=batch_size, shuffle=True,
        num_workers=0, pin_memory=torch.cuda.is_available(),
    )
    val_loader = DataLoader(
        val_ds, batch_size=batch_size, shuffle=False,
        num_workers=0, pin_memory=torch.cuda.is_available(),
    )

    # ── 6. Entraîner le modèle ───────────────────────────────────────
    seed = int(getattr(cfg.reproducibility, "seed", 42))
    L.seed_everything(seed, workers=True)

    model = LSTMAttentionModule(
        input_size=len(available_cols),
        hidden_size=hidden_size,
        num_layers=num_layers,
        dropout=dropout,
        learning_rate=learning_rate,
        num_classes=num_classes,
    )

    # Sauvegarde temporaire du checkpoint
    artifact_path = None
    if artifact_dir is not None:
        artifact_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = artifact_dir / "lstm_model.ckpt"
    else:
        tmp = tempfile.NamedTemporaryFile(suffix=".ckpt", delete=False)
        artifact_path = Path(tmp.name)
        tmp.close()

    checkpoint_callback = L.pytorch.callbacks.ModelCheckpoint(
        dirpath=str(artifact_path.parent),
        filename="lstm_model",
        monitor="val_loss",
        mode="min",
        save_top_k=1,
        save_last=False,
    )
    early_stop = L.pytorch.callbacks.EarlyStopping(
        monitor="val_loss",
        patience=patience,
        mode="min",
        verbose=False,
    )

    # Désactiver les logs Lightning sauf erreurs
    trainer = L.Trainer(
        max_epochs=max_epochs,
        callbacks=[checkpoint_callback, early_stop],
        enable_progress_bar=False,
        enable_model_summary=False,
        logger=False,
        accelerator="auto",
        devices=1,
    )

    try:
        trainer.fit(model, train_loader, val_loader)
    except Exception as exc:
        LOGGER.warning("LSTM training failed: %s", exc)
        return {"status": "failed", "reason": f"training_error:{exc}"}

    latency_train_ms = (time.perf_counter() - t0) * 1000.0

    # ── 7. Prédictions sur val/test ──────────────────────────────────
    best_path = str(artifact_path.parent / "lstm_model.ckpt")
    if not os.path.exists(best_path):
        # Tenter le path du ModelCheckpoint
        best_path = str(artifact_path)
    if not os.path.exists(best_path):
        return {"status": "failed", "reason": "checkpoint_not_found"}

    loaded = LSTMAttentionModule.load_from_checkpoint(best_path)
    loaded.eval()
    loaded.freeze()

    def _predict_proba(dl: DataLoader, n_classes: int) -> np.ndarray:
        all_probs = []
        with torch.no_grad():
            for batch_X, _ in dl:
                logits, _ = loaded.net(batch_X)
                probs = torch.softmax(logits, dim=1).cpu().numpy()
                all_probs.append(probs)
        if all_probs:
            return np.concatenate(all_probs, axis=0)
        return np.empty((0, n_classes))

    val_probs = _predict_proba(val_loader, num_classes)
    test_loader = None
    test_probs = np.empty((0, num_classes))
    if len(X_test_seq) > 0:
        test_ds = SequenceDataset(X_test_seq, y_test)
        test_loader = DataLoader(
            test_ds, batch_size=batch_size, shuffle=False,
            num_workers=0, pin_memory=False,
        )
        test_probs = _predict_proba(test_loader, num_classes)

    # ── 8. Métriques tabulaires ──────────────────────────────────────
    from modelFactory.evaluation import compute_multiclass_metrics, check_model_collapse

    val_metrics: dict[str, Any] = {}
    test_metrics: dict[str, Any] = {}

    if len(val_probs) > 0:
        val_metrics = compute_multiclass_metrics(
            y_true=y_val[:len(val_probs)],
            y_proba=val_probs,
            num_classes=num_classes,
            class_names=["short", "flat", "long"] if is_ternary else None,
        )
        collapse = check_model_collapse(val_probs)
        val_metrics["collapsed"] = collapse.collapsed if hasattr(collapse, "collapsed") else False
        val_metrics["collapse_reason"] = getattr(collapse, "reason", None)

    if len(test_probs) > 0:
        test_metrics = compute_multiclass_metrics(
            y_true=y_test[:len(test_probs)],
            y_proba=test_probs,
            num_classes=num_classes,
            class_names=["short", "flat", "long"] if is_ternary else None,
        )

    # ── 9. Métriques de complexité ───────────────────────────────────
    params_count = sum(p.numel() for p in loaded.net.parameters() if p.requires_grad)
    memory_bytes = os.path.getsize(best_path) if os.path.exists(best_path) else 0

    # ── 10. Latence d'inférence ─────────────────────────────────────
    latency_predict_ms = 0.0
    if len(val_probs) > 0:
        try:
            sample = torch.from_numpy(X_val_seq[:min(100, len(X_val_seq))]).float()
            t0_pred = time.perf_counter()
            with torch.no_grad():
                loaded.net(sample)
            latency_predict_ms = (time.perf_counter() - t0_pred) * 1000.0
        except Exception:
            latency_predict_ms = 0.0

    # ── 11. Nettoyage ───────────────────────────────────────────────
    if artifact_dir is None and os.path.exists(best_path):
        try:
            os.unlink(best_path)
        except OSError:
            pass

    artifact_info: dict[str, str] = {}
    if artifact_dir is not None and os.path.exists(best_path):
        artifact_info["model_path"] = str(best_path)
        artifact_info["model_format"] = "ckpt"

    return {
        "status": "completed",
        "model_name": "lstm_attention",
        "seed": seed,
        "feature_columns": available_cols,
        "val": val_metrics,
        "test": test_metrics,
        "latency_train_ms": latency_train_ms,
        "params_count": params_count,
        "memory_bytes": memory_bytes,
        "latency_predict_ms": latency_predict_ms,
        "artifact_paths": artifact_info,
        "inference_backend": "lstm_attention",
        "seq_len": seq_len,
        "hidden_size": hidden_size,
        "num_layers": num_layers,
    }
