"""modelFactory/dataset.py — Séquences, scaling, Dataset PyTorch et DataModule Lightning."""
from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from functools import partial
from typing import Callable, Optional

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader, Dataset

from modelFactory.config import DataConfig, ModelConfig
from modelFactory.cross_sectional import CROSS_SECTIONAL_FEATURE_COLUMNS, build_cross_sectional_features, merge_cross_sectional_features
from modelFactory.features import FEATURE_COLUMNS, build_target, compute_features, compute_future_return, get_feature_columns
from modelFactory.labeling import TripleBarrierConfig, build_triple_barrier_targets
from modelFactory.reproducibility import build_torch_generator, derive_seed, seed_worker

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


def _validate_ordered_frame(df: pd.DataFrame, *, date_column: str | None = None) -> None:
    if df.empty:
        return
    if date_column is not None and date_column in df.columns:
        dates = pd.to_datetime(df[date_column])
        if not dates.is_monotonic_increasing:
            raise ValueError(f"Le DataFrame doit être trié par {date_column} croissant.")


def _purged_bounds(*, start: int, end: int, purge_tail: int) -> tuple[int, int]:
    """Retire les ``purge_tail`` dernières lignes d'un intervalle [start, end[.

    Cela empêche une target calculée sur ``t + horizon`` de traverser
    la frontière vers le fold suivant (Sprint 3 Point 3.4).
    """
    purge_tail = max(int(purge_tail), 0)
    if purge_tail == 0:
        return start, end
    return start, max(start, end - purge_tail)


def _embargoed_start(*, val_end: int, embargo_rows: int) -> int:
    """Décale le début du test de ``embargo_rows`` après la fin de la validation.

    L'embargo empêche le test de contenir des observations trop proches
    temporellement de la validation, ce qui pourrait créer une corrélation
    fallacieuse entre les folds (Sprint 3 Point 3.4).
    """
    embargo_rows = max(int(embargo_rows), 0)
    return val_end + embargo_rows


def _purge_by_dates(
    df: pd.DataFrame,
    *,
    start_dates: pd.Index,
    purge_tail_dates: int,
    date_column: str = "date",
) -> pd.DataFrame:
    if start_dates.empty:
        return df.iloc[0:0].copy().reset_index(drop=True)
    keep_dates = start_dates[: max(0, len(start_dates) - max(int(purge_tail_dates), 0))]
    if len(keep_dates) == 0:
        return df.iloc[0:0].copy().reset_index(drop=True)
    return df[df[date_column].isin(set(keep_dates))].reset_index(drop=True)


def chrono_split(
    df: pd.DataFrame,
    train_ratio: float,
    val_ratio: float,
    *,
    forecast_horizon: int = 0,
    embargo_rows: int = 0,
    date_column: str | None = "date",
) -> ChronoSplit:
    """Split chronologique sans shuffle avec purge anti-lookahead et embargo.

    Les ``forecast_horizon`` dernières lignes du train et de la validation sont
    retirées afin d'éviter qu'une target calculée sur ``t + horizon`` traverse la
    frontière vers le split suivant.

    Un embargo de ``embargo_rows`` lignes est inséré entre la validation et le
    test pour garantir l'indépendance temporelle des folds (Sprint 3 Point 3.4).
    """
    _validate_ordered_frame(df, date_column=date_column)
    n = len(df)
    i_train = int(n * train_ratio)
    i_val = i_train + int(n * val_ratio)
    train_start, train_end = _purged_bounds(start=0, end=i_train, purge_tail=forecast_horizon)
    val_start, val_end = _purged_bounds(start=i_train, end=i_val, purge_tail=forecast_horizon)
    # L'embargo s'applique APRES la frontière non-purgée i_val,
    # pas après val_end (les lignes purgées entre val_end et i_val
    # sont intentionnellement exclues de tous les folds).
    test_start = _embargoed_start(val_end=i_val, embargo_rows=embargo_rows)
    test_start = min(test_start, n)  # clamp si embargo dépasse la fin
    return ChronoSplit(
        train=df.iloc[train_start:train_end].reset_index(drop=True),
        val=df.iloc[val_start:val_end].reset_index(drop=True),
        test=df.iloc[test_start:].reset_index(drop=True),
    )


def generate_walk_forward_splits(
    df: pd.DataFrame,
    *,
    min_train_size: int,
    val_size: int,
    test_size: int,
    step_size: int,
    max_splits: int,
    forecast_horizon: int = 0,
    embargo_rows: int = 0,
    date_column: str | None = "date",
) -> list[WalkForwardSplit]:
    """Construit des splits walk-forward en fenêtre expanding avec purge et embargo."""
    _validate_ordered_frame(df, date_column=date_column)
    splits: list[WalkForwardSplit] = []
    train_end = min_train_size
    split_index = 0
    n = len(df)

    while split_index < max_splits:
        val_end = train_end + val_size
        test_start_raw = val_end
        test_end = test_start_raw + test_size
        if test_end > n:
            break
        train_start, purged_train_end = _purged_bounds(start=0, end=train_end, purge_tail=forecast_horizon)
        val_start, purged_val_end = _purged_bounds(start=train_end, end=val_end, purge_tail=forecast_horizon)
        # Embargo après la frontière non-purgée val_end (les lignes purgées
        # entre purged_val_end et val_end sont exclues de tous les folds).
        test_start = _embargoed_start(val_end=val_end, embargo_rows=embargo_rows)
        test_start = min(test_start, n)
        test_end = min(test_start + test_size, n)
        if test_start >= test_end:
            # L'embargo a consommé tout le test — on arrête
            break
        splits.append(
            WalkForwardSplit(
                split_index=split_index,
                train=df.iloc[train_start:purged_train_end].reset_index(drop=True),
                val=df.iloc[val_start:purged_val_end].reset_index(drop=True),
                test=df.iloc[test_start:test_end].reset_index(drop=True),
            )
        )
        split_index += 1
        train_end += step_size

    return splits


def chrono_split_by_dates(
    df: pd.DataFrame,
    *,
    train_ratio: float,
    val_ratio: float,
    forecast_horizon: int = 0,
    embargo_dates: int = 0,
    date_column: str = "date",
) -> ChronoSplit:
    """Split chronologique par dates uniques avec purge et embargo.

    L'embargo de ``embargo_dates`` jours est inséré entre la validation
    et le test (Sprint 3 Point 3.4).
    """
    if date_column not in df.columns:
        raise ValueError(f"Colonne date absente: {date_column}")
    _validate_ordered_frame(df, date_column=date_column)
    dated = df.copy()
    dated[date_column] = pd.to_datetime(dated[date_column])
    unique_dates = pd.Index(sorted(dated[date_column].unique()))
    n_dates = len(unique_dates)
    i_train = int(n_dates * train_ratio)
    i_val = i_train + int(n_dates * val_ratio)
    train = _purge_by_dates(dated, start_dates=unique_dates[:i_train], purge_tail_dates=forecast_horizon, date_column=date_column)
    val = _purge_by_dates(dated, start_dates=unique_dates[i_train:i_val], purge_tail_dates=forecast_horizon, date_column=date_column)
    # Embargo : sauter ``embargo_dates`` dates après la fin de val
    embargo_dates = max(int(embargo_dates), 0)
    test_date_start = i_val + embargo_dates
    test_dates = unique_dates[test_date_start:]
    test = dated[dated[date_column].isin(set(test_dates))].reset_index(drop=True)
    return ChronoSplit(train=train, val=val, test=test)


# ---------------------------------------------------------------------------
# Validation d'isolation des folds (Sprint 3 Point 3.4)
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class FoldIsolationReport:
    """Rapport de vérification d'isolation train/validation/test."""

    is_valid: bool
    folds_disjoint: bool
    purge_adequate: bool
    embargo_present: bool
    train_val_overlap: int
    val_test_overlap: int
    train_test_overlap: int
    purge_rows: int
    embargo_rows: int
    label_horizon: int
    violations: list[str]


def validate_fold_isolation(
    split: ChronoSplit,
    *,
    label_horizon: int = 0,
    embargo_rows: int = 0,
    date_column: str | None = "date",
) -> FoldIsolationReport:
    """Vérifie qu'aucun label ou paramètre ne traverse les frontières de fold.

    Cette fonction contrôle les 3 propriétés d'isolation :
    1. **Disjointness** : train ∩ val = ∅, val ∩ test = ∅, train ∩ test = ∅
       (vérifié par contenu si ``date_column`` est fourni, sinon par index)
    2. **Purge** : les ``label_horizon`` dernières lignes de train et val sont
       exclues pour empêcher une target forward-looking de chevaucher le fold suivant
    3. **Embargo** : un gap de ``embargo_rows`` lignes existe entre val et test

    Parameters
    ----------
    split : ChronoSplit
        Le split à valider.
    label_horizon : int
        Horizon maximal du label (``forecast_horizon`` pour fixed-horizon,
        ``max_sessions`` pour triple-barrier).
    embargo_rows : int
        Nombre de lignes d'embargo attendues entre val et test.
    date_column : str | None
        Colonne de date pour la vérification temporelle.

    Returns
    -------
    FoldIsolationReport
    """
    violations: list[str] = []

    # ── 1. Disjointness (par contenu si date_column dispo) ──────────────
    train_val_overlap = 0
    val_test_overlap = 0
    train_test_overlap = 0

    if date_column and date_column in split.train.columns:
        # Comparaison par dates (plus robuste que les index reset)
        train_dates = set(pd.to_datetime(split.train[date_column]).dt.date)
        val_dates = set(pd.to_datetime(split.val[date_column]).dt.date)
        test_dates = set(pd.to_datetime(split.test[date_column]).dt.date)
        train_val_overlap = len(train_dates & val_dates)
        val_test_overlap = len(val_dates & test_dates)
        train_test_overlap = len(train_dates & test_dates)
    else:
        # Fallback : comparaison par index (moins fiable car reset_index)
        train_idx = set(split.train.index)
        val_idx = set(split.val.index)
        test_idx = set(split.test.index)
        # Attention : après reset_index(drop=True), les index peuvent se chevaucher
        # même si les données sont disjointes. On vérifie quand même.
        train_val_overlap = len(train_idx & val_idx)
        val_test_overlap = len(val_idx & test_idx)
        train_test_overlap = len(train_idx & test_idx)

    folds_disjoint = (train_val_overlap == 0 and val_test_overlap == 0 and train_test_overlap == 0)

    if not folds_disjoint:
        details = []
        if train_val_overlap > 0:
            details.append(f"train∩val={train_val_overlap}")
        if val_test_overlap > 0:
            details.append(f"val∩test={val_test_overlap}")
        if train_test_overlap > 0:
            details.append(f"train∩test={train_test_overlap}")
        violations.append(f"Folds non disjoints: {', '.join(details)}")

    # ── 2. Purge adequacy ───────────────────────────────────────────────
    purge_adequate = True
    if label_horizon > 0 and date_column and date_column in split.train.columns:
        train_dates = pd.to_datetime(split.train[date_column])
        val_dates = pd.to_datetime(split.val[date_column])
        test_dates = pd.to_datetime(split.test[date_column])
        if not train_dates.empty and not val_dates.empty:
            last_train = train_dates.max()
            first_val = val_dates.min()
            gap_train_val = (first_val - last_train).days
            if gap_train_val < label_horizon:
                violations.append(
                    f"Gap train→val insuffisant: {gap_train_val}j < {label_horizon}j (label_horizon)"
                )
                purge_adequate = False
        if not val_dates.empty and not test_dates.empty:
            last_val = val_dates.max()
            first_test = test_dates.min()
            gap_val_test = (first_test - last_val).days
            if gap_val_test < label_horizon:
                violations.append(
                    f"Gap val→test insuffisant: {gap_val_test}j < {label_horizon}j (label_horizon)"
                )
                purge_adequate = False

    # ── 3. Embargo ──────────────────────────────────────────────────────
    embargo_present = embargo_rows > 0
    if embargo_rows > 0 and date_column and date_column in split.val.columns and date_column in split.test.columns:
        val_dates = pd.to_datetime(split.val[date_column])
        test_dates = pd.to_datetime(split.test[date_column])
        if not val_dates.empty and not test_dates.empty:
            last_val = val_dates.max()
            first_test = test_dates.min()
            gap_val_test = (first_test - last_val).days
            if gap_val_test < embargo_rows:
                violations.append(
                    f"Embargo val→test insuffisant: {gap_val_test}j < {embargo_rows}j"
                )
                embargo_present = False

    is_valid = len(violations) == 0

    return FoldIsolationReport(
        is_valid=is_valid,
        folds_disjoint=folds_disjoint,
        purge_adequate=purge_adequate,
        embargo_present=embargo_present,
        train_val_overlap=train_val_overlap,
        val_test_overlap=val_test_overlap,
        train_test_overlap=train_test_overlap,
        purge_rows=label_horizon,
        embargo_rows=embargo_rows,
        label_horizon=label_horizon,
        violations=violations,
    )


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
        return {
            "schema_version": 1,
            "mean": self.mean_.tolist(),
            "std": self.std_.tolist(),
            "features": self.feature_names,
        }  # type: ignore[union-attr]

    @classmethod
    def from_state_dict(cls, d: dict) -> "FeatureScaler":
        if not isinstance(d, dict):
            raise ValueError("Scaler state invalide: payload non-dict.")
        mean = d.get("mean")
        std = d.get("std")
        features = d.get("features")
        if not isinstance(features, list) or not features:
            raise ValueError("Scaler state invalide: features absentes ou invalides.")
        if mean is None or std is None:
            raise ValueError("Scaler state invalide: mean/std absents.")
        s = cls(feature_names=[str(feature) for feature in features])
        s.mean_ = np.asarray(mean, dtype=np.float64)
        s.std_ = np.asarray(std, dtype=np.float64)
        if s.mean_.ndim != 1 or s.std_.ndim != 1 or len(s.mean_) != len(s.std_) or len(s.mean_) != len(s.feature_names):
            raise ValueError("Scaler state invalide: dimensions mean/std/features incohérentes.")
        if not np.isfinite(s.mean_).all() or not np.isfinite(s.std_).all():
            raise ValueError("Scaler state invalide: mean/std non finis.")
        return s


# ---------------------------------------------------------------------------
# Sequence builder
# ---------------------------------------------------------------------------

def build_sequences(features: np.ndarray, targets: np.ndarray, seq_len: int) -> tuple[np.ndarray, np.ndarray]:
    """Construit des séquences glissantes [N, seq_len, n_features] et labels [N].

    Exclut les séquences dont le target est NaN.
    """
    X_list, y_list = [], []
    if seq_len < 1:
        raise ValueError("seq_len doit être >= 1.")
    if features.ndim != 2:
        raise ValueError("features doit être un tableau 2D.")
    if len(features) != len(targets):
        raise ValueError("features et targets doivent avoir la même longueur.")

    for end_index in range(seq_len - 1, len(features)):
        target = targets[end_index]
        if not np.isfinite(target):
            continue
        X_list.append(features[end_index - seq_len + 1 : end_index + 1])
        y_list.append(target)

    if not X_list:
        return np.empty((0, seq_len, features.shape[1]), dtype=np.float32), np.empty(0, dtype=np.float32)
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
        selector_df: pd.DataFrame | None = None,
        reproducibility_seed: int = 42,
        *,
        cross_sectional_df: pd.DataFrame | None = None,
    ) -> None:
        super().__init__()
        self.bars_df = bars_df
        self.data_cfg = data_cfg
        self.model_cfg = model_cfg
        self.sentiment_df = sentiment_df
        self.benchmark_df = benchmark_df
        self.universe_df = universe_df
        self.selector_df = selector_df
        self.cross_sectional_df = cross_sectional_df
        self.reproducibility_seed = int(reproducibility_seed)
        self._feature_cols = get_feature_columns(
            data_cfg.include_sentiment_features,
            feature_set=data_cfg.feature_set,
            include_cross_sectional=data_cfg.enable_cross_sectional_features,
            include_selector_context=data_cfg.include_selector_context_features,
            include_short_score=data_cfg.include_short_score_features,
            include_macro_vix=data_cfg.include_macro_vix_features,
            include_macro_vxn=data_cfg.include_macro_vxn_features,
            include_macro_vix3m=data_cfg.include_macro_vix3m_features,
            include_macro_move=data_cfg.include_macro_move_features,
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
        # Sur Windows, le multiprocessing utilise 'spawn' (pas 'fork').
        # Lancer des DataLoader workers (>0) depuis un ProcessPoolExecutor
        # (orchestrateur multi-symboles) provoque des crashes worker
        # (RuntimeError: DataLoader worker exited unexpectedly) et des
        # deadlocks car Lightning ne récupère pas toujours l'erreur.
        # On force donc num_workers=0 sur tout Windows, avec ou sans CUDA.
        # Le gain de parallélisme DataLoader est négligeable sans GPU
        # (pin_memory=False de toute façon) et le SequenceDataset est
        # trivial (indexation de tenseurs en mémoire).
        self._force_single_process_dataloader = os.name == "nt"
        self._num_workers = 0 if self._force_single_process_dataloader else default_num_workers
        if self._force_single_process_dataloader:
            LOGGER.info(
                "forcing dataloader num_workers=0 persistent_workers=False "
                "(windows os.name=%s cuda=%s py_ver=%s)",
                os.name,
                self._pin_memory,
                sys.version_info[:2],
            )

    def setup(self, stage: Optional[str] = None) -> None:
        df = prepare_symbol_frame(
            self.bars_df,
            self.data_cfg,
            sentiment_df=self.sentiment_df,
            benchmark_df=self.benchmark_df,
            universe_df=self.universe_df,
            selector_df=self.selector_df,
            cross_sectional_df=self.cross_sectional_df,
        )
        self.prepared_df = df
        self.cross_sectional_diagnostics = dict(df.attrs.get("cross_sectional_diagnostics", {}))
        # 2. Chrono split
        split = chrono_split(
            df,
            self.data_cfg.train_ratio,
            self.data_cfg.val_ratio,
            forecast_horizon=self.data_cfg.forecast_horizon,
        )
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
        generator_seed = derive_seed(self.reproducibility_seed, "symbol_datamodule", "train" if shuffle else "eval")
        worker_init_fn: Callable[[int], None] | None = None
        if nw > 0:
            # functools.partial est picklable (contrairement à lambda) — requis
            # par Python 3.14+ qui utilise 'spawn' pour le multiprocessing.
            worker_init_fn = partial(seed_worker, generator_seed)
        return DataLoader(
            dataset,
            batch_size=self.model_cfg.batch_size,
            shuffle=shuffle,
            drop_last=False,
            num_workers=nw,
            persistent_workers=nw > 0,
            pin_memory=self._pin_memory,
            generator=build_torch_generator(generator_seed),
            worker_init_fn=worker_init_fn,
        )


def prepare_symbol_frame(
    bars_df: pd.DataFrame,
    data_cfg: DataConfig,
    sentiment_df: pd.DataFrame | None = None,
    benchmark_df: pd.DataFrame | None = None,
    universe_df: pd.DataFrame | None = None,
    selector_df: pd.DataFrame | None = None,
    *,
    cross_sectional_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Prepare le DataFrame final features + target pour un symbole.

    If ``cross_sectional_df`` is provided (pre-computed via
    ``build_cross_sectional_features_from_db``), the ``universe_df``
    parameter is ignored for cross-sectional computation.
    """
    df = compute_features(
        bars_df,
        sentiment_df=sentiment_df,
        include_sentiment=data_cfg.include_sentiment_features,
        benchmark_df=benchmark_df,
        feature_set=data_cfg.feature_set,
        selector_df=selector_df,
        include_selector_context=data_cfg.include_selector_context_features,
        include_short_score=data_cfg.include_short_score_features,
        include_macro_vix=data_cfg.include_macro_vix_features,
        include_macro_vxn=data_cfg.include_macro_vxn_features,
        include_macro_vix3m=data_cfg.include_macro_vix3m_features,
        include_macro_move=data_cfg.include_macro_move_features,
    )
    cross_sectional_diagnostics: dict[str, object] = {}
    if data_cfg.enable_cross_sectional_features:
        if cross_sectional_df is not None:
            # Pre-computed by caller (symbol-by-symbol loading)
            pass
        else:
            cross_sectional_df, cross_sectional_diagnostics = build_cross_sectional_features(
                universe_df,
                benchmark_df=benchmark_df,
                min_universe_size=data_cfg.cross_sectional_min_universe,
            )
        df = merge_cross_sectional_features(df, cross_sectional_df)
    if data_cfg.label_method == "triple_barrier":
        triple_targets = build_triple_barrier_targets(
            df,
            TripleBarrierConfig(
                stop_atr_mult=data_cfg.triple_barrier_stop_atr_mult,
                tp_atr_mult=data_cfg.triple_barrier_tp_atr_mult,
                max_sessions=data_cfg.triple_barrier_max_sessions,
            ),
        )
        df["future_return"] = triple_targets["future_return"]
        df["target"] = triple_targets["target"]
    else:
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
        include_selector_context=data_cfg.include_selector_context_features,
        include_short_score=data_cfg.include_short_score_features,
        include_macro_vix=data_cfg.include_macro_vix_features,
        include_macro_vxn=data_cfg.include_macro_vxn_features,
        include_macro_vix3m=data_cfg.include_macro_vix3m_features,
        include_macro_move=data_cfg.include_macro_move_features,
    )
    df = df.dropna(subset=active_features).reset_index(drop=True)
    df.attrs["cross_sectional_diagnostics"] = cross_sectional_diagnostics
    return df


