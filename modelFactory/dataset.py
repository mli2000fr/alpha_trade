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
from modelFactory.cross_sectional import CROSS_SECTIONAL_FEATURE_COLUMNS, build_cross_sectional_features, merge_cross_sectional_features
from modelFactory.features import FEATURE_COLUMNS, build_target, compute_features, compute_future_return, get_feature_columns

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


@dataclass(frozen=True, slots=True)
class WalkForwardSplit:
    """Fenêtre d'évaluation walk-forward."""

    split_index: int
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


def generate_walk_forward_splits(
    df: pd.DataFrame,
    *,
    min_train_size: int,
    val_size: int,
    test_size: int,
    step_size: int,
    max_splits: int,
) -> list[WalkForwardSplit]:
    """Construit des splits walk-forward en fenêtre expanding."""
    splits: list[WalkForwardSplit] = []
    train_end = min_train_size
    split_index = 0
    n = len(df)

    while split_index < max_splits:
        val_end = train_end + val_size
        test_end = val_end + test_size
        if test_end > n:
            break
        splits.append(
            WalkForwardSplit(
                split_index=split_index,
                train=df.iloc[:train_end].reset_index(drop=True),
                val=df.iloc[train_end:val_end].reset_index(drop=True),
                test=df.iloc[val_end:test_end].reset_index(drop=True),
            )
        )
        split_index += 1
        train_end += step_size

    return splits


# ---------------------------------------------------------------------------
# Scaler (fit on train only)
# ---------------------------------------------------------------------------

class FeatureScaler:
    """Standard scaler fit on train split only."""

    def __init__(self, feature_names: list[str] | None = None) -> None:
        self.mean_: Optional[np.ndarray] = None
        self.std_: Optional[np.ndarray] = None
        self.feature_names: list[str] = feature_names or list(FEATURE_COLUMNS)

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


def build_sequence_dataset(df: pd.DataFrame, scaler: FeatureScaler, seq_len: int) -> SequenceDataset | None:
    """Construit un `SequenceDataset` à partir d'un split préparé."""
    feats = scaler.transform(df)
    targets = df["target"].values
    X, y = build_sequences(feats, targets, seq_len)
    return SequenceDataset(X, y) if len(X) > 0 else None


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

    def __init__(
        self,
        bars_df: pd.DataFrame,
        data_cfg: DataConfig,
        model_cfg: ModelConfig,
        sentiment_df: pd.DataFrame | None = None,
        benchmark_df: pd.DataFrame | None = None,
        universe_df: pd.DataFrame | None = None,
    ) -> None:
        super().__init__()
        self.bars_df = bars_df
        self.data_cfg = data_cfg
        self.model_cfg = model_cfg
        self.sentiment_df = sentiment_df
        self.benchmark_df = benchmark_df
        self.universe_df = universe_df
        self._feature_cols = get_feature_columns(
            data_cfg.include_sentiment_features,
            feature_set=data_cfg.feature_set,
            include_cross_sectional=data_cfg.enable_cross_sectional_features,
        )
        self.scaler = FeatureScaler(feature_names=self._feature_cols)
        self.train_ds: Optional[SequenceDataset] = None
        self.val_ds: Optional[SequenceDataset] = None
        self.test_ds: Optional[SequenceDataset] = None
        self.prepared_df: Optional[pd.DataFrame] = None
        self.split: Optional[ChronoSplit] = None
        self.n_features: int = len(self._feature_cols)
        self.cross_sectional_feature_columns: list[str] = list(CROSS_SECTIONAL_FEATURE_COLUMNS) if data_cfg.enable_cross_sectional_features else []
        self.cross_sectional_diagnostics: dict[str, object] = {}
        self._pin_memory = torch.cuda.is_available()
        default_num_workers = min(os.cpu_count() or 0, 4)
        self._force_single_process_dataloader = os.name == "nt" and self._pin_memory
        self._num_workers = 0 if self._force_single_process_dataloader else default_num_workers
        if self._force_single_process_dataloader:
            LOGGER.info(
                "windows+cuda detected -> forcing dataloader num_workers=0 persistent_workers=False to avoid teardown crashes"
            )

    def setup(self, stage: Optional[str] = None) -> None:
        df = prepare_symbol_frame(
            self.bars_df,
            self.data_cfg,
            sentiment_df=self.sentiment_df,
            benchmark_df=self.benchmark_df,
            universe_df=self.universe_df,
        )
        self.prepared_df = df
        self.cross_sectional_diagnostics = dict(df.attrs.get("cross_sectional_diagnostics", {}))
        # 2. Chrono split
        split = chrono_split(df, self.data_cfg.train_ratio, self.data_cfg.val_ratio)
        self.split = split
        # 3. Fit scaler on train
        self.scaler.fit(split.train)
        # 4. Transform + build sequences
        for name, part in [("train", split.train), ("val", split.val), ("test", split.test)]:
            ds = build_sequence_dataset(part, self.scaler, self.data_cfg.sequence_length)
            setattr(self, f"{name}_ds", ds)
            LOGGER.info("dataset split=%s sequences=%d", name, len(ds) if ds is not None else 0)

    def train_dataloader(self) -> DataLoader:  # type: ignore[type-arg]
        assert self.train_ds is not None
        return self._build_dataloader(self.train_ds, shuffle=True)

    def val_dataloader(self) -> DataLoader:  # type: ignore[type-arg]
        assert self.val_ds is not None
        return self._build_dataloader(self.val_ds, shuffle=False)

    def test_dataloader(self) -> DataLoader:  # type: ignore[type-arg]
        assert self.test_ds is not None
        return self._build_dataloader(self.test_ds, shuffle=False)

    def _build_dataloader(self, dataset: SequenceDataset, *, shuffle: bool) -> DataLoader:  # type: ignore[type-arg]
        nw = self._num_workers
        return DataLoader(
            dataset,
            batch_size=self.model_cfg.batch_size,
            shuffle=shuffle,
            drop_last=False,
            num_workers=nw,
            persistent_workers=nw > 0,
            pin_memory=self._pin_memory,
        )


def prepare_symbol_frame(
    bars_df: pd.DataFrame,
    data_cfg: DataConfig,
    sentiment_df: pd.DataFrame | None = None,
    benchmark_df: pd.DataFrame | None = None,
    universe_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Prépare le DataFrame final features + target pour un symbole."""
    df = compute_features(
        bars_df,
        sentiment_df=sentiment_df,
        include_sentiment=data_cfg.include_sentiment_features,
        benchmark_df=benchmark_df,
        feature_set=data_cfg.feature_set,
    )
    cross_sectional_diagnostics: dict[str, object] = {}
    if data_cfg.enable_cross_sectional_features:
        cross_sectional_df, cross_sectional_diagnostics = build_cross_sectional_features(
            universe_df,
            benchmark_df=benchmark_df,
            min_universe_size=data_cfg.cross_sectional_min_universe,
        )
        df = merge_cross_sectional_features(df, cross_sectional_df)
    df["future_return"] = compute_future_return(df, horizon=data_cfg.forecast_horizon)
    df["target"] = build_target(
        df,
        horizon=data_cfg.forecast_horizon,
        mode=data_cfg.target_mode,
        positive_threshold=data_cfg.target_up_threshold,
        negative_threshold=data_cfg.target_down_threshold,
    )
    active_features = get_feature_columns(
        data_cfg.include_sentiment_features,
        feature_set=data_cfg.feature_set,
        include_cross_sectional=data_cfg.enable_cross_sectional_features,
    )
    df = df.dropna(subset=active_features).reset_index(drop=True)
    df.attrs["cross_sectional_diagnostics"] = cross_sectional_diagnostics
    return df


