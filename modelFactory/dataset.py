"""modelFactory/dataset.py — Séquences, scaling, Dataset PyTorch et DataModule Lightning."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader, Dataset

from modelFactory.config import DataConfig, ModelConfig
from modelFactory.features import FEATURE_COLUMNS, build_target, compute_features

LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Split chronologique
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class ChronoSplit:
    """Résultat d'un split chronologique."""
    train: pd.DataFrame
    val: pd.DataFrame
    test: pd.DataFrame


def chrono_split(df: pd.DataFrame, train_ratio: float, val_ratio: float) -> ChronoSplit:
    """Split chronologique sans shuffle. Le df doit être trié par date."""
    n = len(df)
    i_train = int(n * train_ratio)
    i_val = i_train + int(n * val_ratio)
    return ChronoSplit(
        train=df.iloc[:i_train].reset_index(drop=True),
        val=df.iloc[i_train:i_val].reset_index(drop=True),
        test=df.iloc[i_val:].reset_index(drop=True),
    )


# ---------------------------------------------------------------------------
# Scaler (fit on train only)
# ---------------------------------------------------------------------------

class FeatureScaler:
    """Standard scaler fit on train split only."""

    def __init__(self) -> None:
        self.mean_: Optional[np.ndarray] = None
        self.std_: Optional[np.ndarray] = None
        self.feature_names: list[str] = FEATURE_COLUMNS

    def fit(self, df: pd.DataFrame) -> "FeatureScaler":
        vals = df[self.feature_names].values.astype(np.float64)
        self.mean_ = np.nanmean(vals, axis=0)
        self.std_ = np.nanstd(vals, axis=0)
        self.std_[self.std_ < 1e-8] = 1.0  # avoid div-by-zero
        return self

    def transform(self, df: pd.DataFrame) -> np.ndarray:
        assert self.mean_ is not None, "Scaler not fitted"
        vals = df[self.feature_names].values.astype(np.float64)
        return (vals - self.mean_) / self.std_

    def state_dict(self) -> dict:
        return {"mean": self.mean_.tolist(), "std": self.std_.tolist(), "features": self.feature_names}  # type: ignore[union-attr]

    @classmethod
    def from_state_dict(cls, d: dict) -> "FeatureScaler":
        s = cls()
        s.mean_ = np.array(d["mean"])
        s.std_ = np.array(d["std"])
        s.feature_names = d["features"]
        return s


# ---------------------------------------------------------------------------
# Sequence builder
# ---------------------------------------------------------------------------

def build_sequences(features: np.ndarray, targets: np.ndarray, seq_len: int) -> tuple[np.ndarray, np.ndarray]:
    """Construit des séquences glissantes [N, seq_len, n_features] et labels [N].

    Exclut les séquences dont le target est NaN.
    """
    X_list, y_list = [], []
    for i in range(seq_len, len(features)):
        t = targets[i]
        if np.isnan(t):
            continue
        X_list.append(features[i - seq_len: i])
        y_list.append(t)
    if not X_list:
        return np.empty((0, seq_len, features.shape[1])), np.empty(0)
    return np.array(X_list, dtype=np.float32), np.array(y_list, dtype=np.float32)


# ---------------------------------------------------------------------------
# PyTorch Dataset
# ---------------------------------------------------------------------------

class SequenceDataset(Dataset):  # type: ignore[type-arg]
    def __init__(self, X: np.ndarray, y: np.ndarray) -> None:
        self.X = torch.from_numpy(X)
        self.y = torch.from_numpy(y).long()

    def __len__(self) -> int:
        return len(self.y)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
        return self.X[idx], self.y[idx]


# ---------------------------------------------------------------------------
# Lightning DataModule
# ---------------------------------------------------------------------------

try:
    import lightning as L
except ImportError:  # pragma: no cover
    import pytorch_lightning as L  # type: ignore[no-redef]


class SymbolDataModule(L.LightningDataModule):
    """DataModule pour un symbole unique."""

    def __init__(self, bars_df: pd.DataFrame, data_cfg: DataConfig, model_cfg: ModelConfig) -> None:
        super().__init__()
        self.bars_df = bars_df
        self.data_cfg = data_cfg
        self.model_cfg = model_cfg
        self.scaler = FeatureScaler()
        self.train_ds: Optional[SequenceDataset] = None
        self.val_ds: Optional[SequenceDataset] = None
        self.test_ds: Optional[SequenceDataset] = None
        self.n_features: int = len(FEATURE_COLUMNS)
        self._num_workers = min(os.cpu_count() or 0, 4)

    def setup(self, stage: Optional[str] = None) -> None:
        # 1. Feature engineering
        df = compute_features(self.bars_df)
        # 2. Target
        df["target"] = build_target(df, self.data_cfg.forecast_horizon)
        # 3. Chrono split
        split = chrono_split(df, self.data_cfg.train_ratio, self.data_cfg.val_ratio)
        # 4. Fit scaler on train
        self.scaler.fit(split.train)
        # 5. Transform + build sequences
        for name, part in [("train", split.train), ("val", split.val), ("test", split.test)]:
            feats = self.scaler.transform(part)
            targets = part["target"].values
            X, y = build_sequences(feats, targets, self.data_cfg.sequence_length)
            ds = SequenceDataset(X, y) if len(X) > 0 else None
            setattr(self, f"{name}_ds", ds)
            LOGGER.info("dataset split=%s sequences=%d", name, len(X))

    def train_dataloader(self) -> DataLoader:  # type: ignore[type-arg]
        assert self.train_ds is not None
        nw = self._num_workers
        return DataLoader(self.train_ds, batch_size=self.model_cfg.batch_size, shuffle=True, drop_last=False,
                          num_workers=nw, persistent_workers=nw > 0)

    def val_dataloader(self) -> DataLoader:  # type: ignore[type-arg]
        assert self.val_ds is not None
        nw = self._num_workers
        return DataLoader(self.val_ds, batch_size=self.model_cfg.batch_size, shuffle=False,
                          num_workers=nw, persistent_workers=nw > 0)

    def test_dataloader(self) -> DataLoader:  # type: ignore[type-arg]
        assert self.test_ds is not None
        nw = self._num_workers
        return DataLoader(self.test_ds, batch_size=self.model_cfg.batch_size, shuffle=False,
                          num_workers=nw, persistent_workers=nw > 0)

