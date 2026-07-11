"""Contrat partagé de sélection ML-first.

Ce module décrit les invariants du cutover sans activer le nouveau runtime.
Les implémentations train, predict, live et backtest doivent importer ce
contrat au lieu de redéfinir localement la portée ou les règles de sélection.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

UniverseSource = Literal["tradable-universe"]
PredictionTargetMode = Literal["ternary"]
ScoreRole = Literal["feature_veto"]
FeatureScope = Literal["full_tradable_universe"]
VetoTiming = Literal["post_prediction_ranking"]
TrainingWorkflow = Literal["separate"]

LIVE_WORKFLOW_STAGES: tuple[str, ...] = (
    "import_market_data",
    "data_integrity",
    "universe_metrics",
    "sync_latest_quotes",
    "sync_earnings",
    "publish_tradable_universe",
    "feature_engineering_pit",
    "ml_predict",
    "ml_ranking",
    "post_prediction_vetos",
    "risk_management",
    "execution",
)


@dataclass(frozen=True, slots=True)
class SelectionCapacity:
    """Plafonds de positions partagés par live et backtest."""

    max_positions: int
    max_long_positions: int
    max_short_positions: int

    def __post_init__(self) -> None:
        if self.max_positions < 1:
            raise ValueError("max_positions doit être >= 1.")
        if self.max_long_positions < 0:
            raise ValueError("max_long_positions doit être >= 0.")
        if self.max_short_positions < 0:
            raise ValueError("max_short_positions doit être >= 0.")
        if self.max_long_positions > self.max_positions:
            raise ValueError("max_long_positions ne peut pas dépasser max_positions.")
        if self.max_short_positions > self.max_positions:
            raise ValueError("max_short_positions ne peut pas dépasser max_positions.")


@dataclass(frozen=True, slots=True)
class MLFirstSelectionContract:
    """Invariants non configurables du chemin nominal après cutover."""

    universe_source: UniverseSource = "tradable-universe"
    prediction_target_mode: PredictionTargetMode = "ternary"
    score_role: ScoreRole = "feature_veto"
    feature_scope: FeatureScope = "full_tradable_universe"
    veto_timing: VetoTiming = "post_prediction_ranking"
    training_workflow: TrainingWorkflow = "separate"
    prediction_required: bool = True
    separate_side_ranking: bool = True
    live_workflow_stages: tuple[str, ...] = LIVE_WORKFLOW_STAGES
    capacity: SelectionCapacity = field(
        default_factory=lambda: SelectionCapacity(
            max_positions=20,
            max_long_positions=20,
            max_short_positions=2,
        )
    )

    def __post_init__(self) -> None:
        if self.universe_source != "tradable-universe":
            raise ValueError("L'univers nominal doit être tradable-universe.")
        if self.prediction_target_mode != "ternary":
            raise ValueError("Le cutover ML-first exige une prédiction ternaire.")
        if self.score_role != "feature_veto":
            raise ValueError("Le score ne peut être utilisé que comme feature ou veto.")
        if self.feature_scope != "full_tradable_universe":
            raise ValueError("Les features doivent couvrir tout l'univers tradable.")
        if self.veto_timing != "post_prediction_ranking":
            raise ValueError("Les vetos doivent intervenir après le ranking ML.")
        if self.training_workflow != "separate":
            raise ValueError("Le training doit rester séparé du workflow live quotidien.")
        if not self.prediction_required:
            raise ValueError("Une prédiction ML est obligatoire pour toute sélection.")
        if not self.separate_side_ranking:
            raise ValueError("Les rankings long et short doivent être séparés.")
        if self.live_workflow_stages != LIVE_WORKFLOW_STAGES:
            raise ValueError("Le workflow live doit respecter les 12 étapes canoniques.")


ML_FIRST_SELECTION_CONTRACT = MLFirstSelectionContract()