"""modelFactory/config.py — Configurations immuables du module ML."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True)
class DataConfig:
    """Paramètres de chargement et préparation des données."""

    sequence_length: int = 60
    forecast_horizon: int = 5
    min_history_days: int = 504
    train_ratio: float = 0.70
    val_ratio: float = 0.15
    # test = 1 - train - val
    include_sentiment_features: bool = False
    target_mode: str = "binary"  # binary | swing_cash
    target_up_threshold: float = 0.0
    target_down_threshold: float = 0.0
    decision_threshold: float = 0.5

    def __post_init__(self) -> None:
        if self.sequence_length < 1:
            raise ValueError("sequence_length doit être >= 1.")
        if self.forecast_horizon < 1:
            raise ValueError("forecast_horizon doit être >= 1.")
        if self.min_history_days < self.sequence_length + self.forecast_horizon:
            raise ValueError("min_history_days doit être >= sequence_length + forecast_horizon.")
        if not (0 < self.train_ratio < 1):
            raise ValueError("train_ratio doit être dans ]0, 1[.")
        if not (0 < self.val_ratio < 1):
            raise ValueError("val_ratio doit être dans ]0, 1[.")
        if self.train_ratio + self.val_ratio >= 1.0:
            raise ValueError("train_ratio + val_ratio doit être < 1.")
        if self.target_mode not in {"binary", "swing_cash"}:
            raise ValueError("target_mode doit être 'binary' ou 'swing_cash'.")
        if not (0.0 < self.decision_threshold < 1.0):
            raise ValueError("decision_threshold doit être dans ]0, 1[.")
        if self.target_down_threshold > self.target_up_threshold:
            raise ValueError("target_down_threshold doit être <= target_up_threshold.")


@dataclass(frozen=True, slots=True)
class CalibrationConfig:
    """Paramètres de calibration des probabilités."""

    method: str = "none"  # none | platt
    min_samples: int = 64
    max_iter: int = 100

    def __post_init__(self) -> None:
        if self.method not in {"none", "platt"}:
            raise ValueError("calibration.method doit être 'none' ou 'platt'.")
        if self.min_samples < 2:
            raise ValueError("calibration.min_samples doit être >= 2.")
        if self.max_iter < 1:
            raise ValueError("calibration.max_iter doit être >= 1.")


@dataclass(frozen=True, slots=True)
class WalkForwardConfig:
    """Paramètres d'évaluation walk-forward."""

    enabled: bool = False
    min_train_size: int = 504
    val_size: int = 126
    test_size: int = 126
    step_size: int = 126
    max_splits: int = 3

    def __post_init__(self) -> None:
        if self.min_train_size < 2:
            raise ValueError("walk_forward.min_train_size doit être >= 2.")
        if self.val_size < 1:
            raise ValueError("walk_forward.val_size doit être >= 1.")
        if self.test_size < 1:
            raise ValueError("walk_forward.test_size doit être >= 1.")
        if self.step_size < 1:
            raise ValueError("walk_forward.step_size doit être >= 1.")
        if self.max_splits < 1:
            raise ValueError("walk_forward.max_splits doit être >= 1.")


@dataclass(frozen=True, slots=True)
class ModelConfig:
    """Hyper-paramètres du modèle LSTM + attention."""

    input_size: int = 0  # set dynamically after feature engineering
    hidden_size: int = 128
    num_layers: int = 2
    dropout: float = 0.3
    learning_rate: float = 1e-3
    weight_decay: float = 1e-5
    batch_size: int = 64
    max_epochs: int = 50
    patience: int = 7
    num_classes: int = 2

    def __post_init__(self) -> None:
        if self.hidden_size < 1:
            raise ValueError("hidden_size doit être >= 1.")
        if self.num_layers < 1:
            raise ValueError("num_layers doit être >= 1.")
        if not (0 <= self.dropout < 1):
            raise ValueError("dropout doit être dans [0, 1[.")
        if self.learning_rate <= 0:
            raise ValueError("learning_rate doit être > 0.")
        if self.batch_size < 1:
            raise ValueError("batch_size doit être >= 1.")
        if self.max_epochs < 1:
            raise ValueError("max_epochs doit être >= 1.")


@dataclass(frozen=True, slots=True)
class TrainingConfig:
    """Configuration globale d'un run d'entraînement."""

    data: DataConfig = field(default_factory=DataConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    calibration: CalibrationConfig = field(default_factory=CalibrationConfig)
    walk_forward: WalkForwardConfig = field(default_factory=WalkForwardConfig)
    artifacts_dir: Path = Path("artifacts/models")
    max_workers: int = 4
    accelerator: str = "auto"  # auto | cpu | gpu

    def __post_init__(self) -> None:
        if self.max_workers < 1:
            raise ValueError("max_workers doit être >= 1.")

