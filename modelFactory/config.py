"""modelFactory/config.py — Configurations immuables du module ML."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path


@dataclass(frozen=True, slots=True)
class DataConfig:
    """Paramètres de chargement et préparation des données."""

    sequence_length: int = 60
    forecast_horizon: int = 10
    min_history_days: int = 504
    train_ratio: float = 0.70
    val_ratio: float = 0.15
    # test = 1 - train - val
    include_sentiment_features: bool = False
    include_selector_context_features: bool = False
    include_short_score_features: bool = False
    include_macro_vix_features: bool = False     # VIX + VIX9D
    include_macro_vxn_features: bool = False     # VXN (Nasdaq-100 vol)
    include_macro_vix3m_features: bool = False   # VIX3M + term structure ratio
    include_macro_move_features: bool = False    # MOVE (bond volatility)
    enable_cross_sectional_features: bool = False
    cross_sectional_min_universe: int = 20
    feature_set: str = "v1"  # v1 | expert
    benchmark_symbol: str = "SPY"
    target_mode: str = "binary"  # binary | swing_cash | ternary
    label_method: str = "fixed_horizon"  # fixed_horizon | triple_barrier
    target_up_threshold: float = 0.0
    target_down_threshold: float = 0.0
    triple_barrier_stop_atr_mult: float = 2.0
    triple_barrier_tp_atr_mult: float = 3.0
    triple_barrier_max_sessions: int = 20
    decision_threshold: float = 0.5
    training_start_date: date | None = date(2020, 1, 1)
    training_end_date: date | None = None

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
        if self.feature_set not in {"v1", "expert"}:
            raise ValueError("feature_set doit être 'v1' ou 'expert'.")
        if self.cross_sectional_min_universe < 2:
            raise ValueError("cross_sectional_min_universe doit être >= 2.")
        if self.target_mode not in {"binary", "swing_cash", "ternary"}:
            raise ValueError("target_mode doit être 'binary', 'swing_cash' ou 'ternary'.")
        if self.label_method not in {"fixed_horizon", "triple_barrier"}:
            raise ValueError("label_method doit être 'fixed_horizon' ou 'triple_barrier'.")
        if self.label_method == "triple_barrier" and self.target_mode != "ternary":
            raise ValueError("triple_barrier requiert target_mode='ternary'.")
        if self.triple_barrier_stop_atr_mult <= 0 or self.triple_barrier_tp_atr_mult <= 0:
            raise ValueError("Les multiples triple_barrier doivent être > 0.")
        if self.triple_barrier_max_sessions < 1:
            raise ValueError("triple_barrier_max_sessions doit être >= 1.")
        if not (0.0 < self.decision_threshold < 1.0):
            raise ValueError("decision_threshold doit être dans ]0, 1[.")
        if self.target_down_threshold > self.target_up_threshold:
            raise ValueError("target_down_threshold doit être <= target_up_threshold.")
        if not self.benchmark_symbol.strip():
            raise ValueError("benchmark_symbol ne doit pas être vide.")
        if self.training_start_date is not None and not isinstance(self.training_start_date, date):
            raise ValueError("training_start_date doit être une instance date ou None.")
        if self.training_end_date is not None and not isinstance(self.training_end_date, date):
            raise ValueError("training_end_date doit être une instance date ou None.")
        if (
            self.training_start_date is not None
            and self.training_end_date is not None
            and self.training_end_date < self.training_start_date
        ):
            raise ValueError("training_end_date doit être >= training_start_date.")


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
class BaselineConfig:
    """Paramètres de comparaison de baseline tabulaire."""

    enabled: bool = False
    enable_catboost: bool = False
    model_name: str = "lightgbm"
    max_depth: int = 4
    n_estimators: int = 200
    learning_rate: float = 0.05
    catboost_depth: int = 6
    catboost_iterations: int = 300
    catboost_learning_rate: float = 0.03
    random_state: int = 42

    def __post_init__(self) -> None:
        if self.model_name not in {"lightgbm", "catboost"}:
            raise ValueError("baseline.model_name doit être 'lightgbm' ou 'catboost'.")
        if self.max_depth < 1:
            raise ValueError("baseline.max_depth doit être >= 1.")
        if self.n_estimators < 10:
            raise ValueError("baseline.n_estimators doit être >= 10.")
        if self.learning_rate <= 0:
            raise ValueError("baseline.learning_rate doit être > 0.")
        if self.catboost_depth < 1:
            raise ValueError("baseline.catboost_depth doit être >= 1.")
        if self.catboost_iterations < 10:
            raise ValueError("baseline.catboost_iterations doit être >= 10.")
        if self.catboost_learning_rate <= 0:
            raise ValueError("baseline.catboost_learning_rate doit être > 0.")


@dataclass(frozen=True, slots=True)
class GlobalModelConfig:
    """Paramètres du modèle global multi-symboles."""

    enabled: bool = False
    model_name: str = "catboost"  # catboost | lightgbm
    artifact_symbol: str = "__GLOBAL__"
    use_cross_sectional_features: bool = True

    def __post_init__(self) -> None:
        if self.model_name not in {"catboost", "lightgbm"}:
            raise ValueError("global_model.model_name doit être 'catboost' ou 'lightgbm'.")
        if not self.artifact_symbol.strip():
            raise ValueError("global_model.artifact_symbol ne doit pas être vide.")


@dataclass(frozen=True, slots=True)
class TargetOptimizationConfig:
    """Paramètres d'optimisation de la target par horizon swing."""

    enabled: bool = False
    candidate_horizons: tuple[int, ...] = (3, 5, 10, 15)
    candidate_up_thresholds: tuple[float, ...] = (0.0, 0.01, 0.02)
    candidate_down_thresholds: tuple[float, ...] = (0.0, -0.005, -0.01)
    min_trades_fraction: float = 0.15

    def __post_init__(self) -> None:
        if not self.candidate_horizons:
            raise ValueError("target_optimization.candidate_horizons ne doit pas être vide.")
        if any(h < 1 for h in self.candidate_horizons):
            raise ValueError("Tous les candidate_horizons doivent être >= 1.")
        if not self.candidate_up_thresholds:
            raise ValueError("target_optimization.candidate_up_thresholds ne doit pas être vide.")
        if not self.candidate_down_thresholds:
            raise ValueError("target_optimization.candidate_down_thresholds ne doit pas être vide.")
        if min(self.candidate_down_thresholds) > max(self.candidate_up_thresholds):
            raise ValueError(
                "target_optimization requiert au moins une combinaison valide avec candidate_down_threshold <= candidate_up_threshold."
            )
        if not (0.0 < self.min_trades_fraction <= 1.0):
            raise ValueError("target_optimization.min_trades_fraction doit être dans ]0, 1].")


@dataclass(frozen=True, slots=True)
class ThresholdOptimizationConfig:
    """Paramètres de sélection du seuil de décision en validation."""

    enabled: bool = False
    candidate_decision_thresholds: tuple[float, ...] = (0.50, 0.55, 0.60, 0.65, 0.70)
    min_action_rate: float = 0.03
    max_action_rate: float = 0.35
    min_precision_long: float = 0.52

    def __post_init__(self) -> None:
        if not self.candidate_decision_thresholds:
            raise ValueError("threshold_optimization.candidate_decision_thresholds ne doit pas être vide.")
        if any(not (0.0 < t < 1.0) for t in self.candidate_decision_thresholds):
            raise ValueError("Tous les candidate_decision_thresholds doivent être dans ]0, 1[.")
        if not (0.0 <= self.min_action_rate <= 1.0):
            raise ValueError("threshold_optimization.min_action_rate doit être dans [0, 1].")
        if not (0.0 <= self.max_action_rate <= 1.0):
            raise ValueError("threshold_optimization.max_action_rate doit être dans [0, 1].")
        if self.min_action_rate > self.max_action_rate:
            raise ValueError("threshold_optimization.min_action_rate doit être <= max_action_rate.")
        if not (0.0 <= self.min_precision_long <= 1.0):
            raise ValueError("threshold_optimization.min_precision_long doit être dans [0, 1].")


@dataclass(frozen=True, slots=True)
class ChampionSelectionConfig:
    """Paramètres de sélection du modèle champion servi en inférence."""

    enabled: bool = False
    allow_auto_selection: bool = False
    default_champion: str = "lstm_attention"
    selection_metric: str = "selection_score"  # selection_score | business_score | auc
    require_benchmark_report: bool = False
    # Phase 4.2.e — Quarantaine d'un nouveau champion :
    # tant qu'il n'a pas atteint `min_runs` runs walk-forward complétés OU
    # `min_days` jours d'observation depuis sa première complétion, il est
    # exclu de la sélection (fallback sur ``default_champion``).
    min_runs: int = 0
    min_days: int = 0

    def __post_init__(self) -> None:
        if self.default_champion not in {"lstm_attention", "lightgbm", "catboost", "global_model"}:
            raise ValueError("champion_selection.default_champion invalide.")
        if self.selection_metric not in {"selection_score", "business_score", "auc"}:
            raise ValueError("champion_selection.selection_metric doit être 'selection_score', 'business_score' ou 'auc'.")
        if self.min_runs < 0:
            raise ValueError("champion_selection.min_runs doit être >= 0.")
        if self.min_days < 0:
            raise ValueError("champion_selection.min_days doit être >= 0.")


@dataclass(frozen=True, slots=True)
class ModelConfig:
    """Hyper-paramètres du modèle LSTM + attention."""

    input_size: int = 0  # set dynamically after feature engineering
    hidden_size: int = 256
    num_layers: int = 2
    dropout: float = 0.3
    learning_rate: float = 1e-3
    weight_decay: float = 1e-5
    batch_size: int = 32
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
class ReproducibilityConfig:
    """Paramètres centralisés de seed et déterminisme backend."""

    seed: int = 42
    deterministic: bool = True

    def __post_init__(self) -> None:
        if self.seed < 0:
            raise ValueError("reproducibility.seed doit être >= 0.")


@dataclass(frozen=True, slots=True)
class TrainingConfig:
    """Configuration globale d'un run d'entraînement."""

    data: DataConfig = field(default_factory=DataConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    calibration: CalibrationConfig = field(default_factory=CalibrationConfig)
    walk_forward: WalkForwardConfig = field(default_factory=WalkForwardConfig)
    baseline: BaselineConfig = field(default_factory=BaselineConfig)
    global_model: GlobalModelConfig = field(default_factory=GlobalModelConfig)
    target_optimization: TargetOptimizationConfig = field(default_factory=TargetOptimizationConfig)
    threshold_optimization: ThresholdOptimizationConfig = field(default_factory=ThresholdOptimizationConfig)
    champion_selection: ChampionSelectionConfig = field(default_factory=ChampionSelectionConfig)
    reproducibility: ReproducibilityConfig = field(default_factory=ReproducibilityConfig)
    artifacts_dir: Path = Path("artifacts/models")
    max_workers: int = 4
    accelerator: str = "auto"  # auto | cpu | gpu
    debug_train: bool = False

    def __post_init__(self) -> None:
        if self.max_workers < 1:
            raise ValueError("max_workers doit être >= 1.")

