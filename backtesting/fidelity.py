"""Primitives de fidélité pour le backtesting pipeline-aware."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd


class PitHistoryRequiredError(RuntimeError):
    """Levée quand un run pipeline exige un historique PIT indisponible."""


class PitMlStrategyUnsupportedError(RuntimeError):
    """Levée quand une stratégie ML PIT explicite n'est pas supportée."""


def resolve_ml_pit_strategy(*, engine_mode: str, ml_mode: str, requested_strategy: str | None) -> str:
    """Résout la stratégie ML PIT effective sans casser les comportements legacy."""
    normalized_requested = str(requested_strategy or "auto").strip().lower()
    normalized_ml_mode = str(ml_mode or "auto").strip().lower()
    normalized_engine_mode = str(engine_mode or "research").strip().lower()

    if normalized_ml_mode == "off":
        return "disabled"
    if normalized_requested != "auto":
        return normalized_requested
    if normalized_ml_mode == "rebuild-missing":
        return "rebuild-missing"
    return "use-persisted" if normalized_engine_mode in {"pipeline", "research"} else "use-persisted"


@dataclass(slots=True)
class ScoreLoadDiagnostics:
    """Diagnostics de provenance des scores chargés pour un backtest."""

    source_table: str
    strict_pit_requested: bool
    history_table_exists: bool
    history_rows_found: int
    capital_preset_key: str | None = None
    config_fingerprint_present: bool = False
    fallback_used: bool = False
    degraded_reasons: tuple[str, ...] = ()

    @property
    def strict_pit_satisfied(self) -> bool:
        return self.source_table == "stock_scores_history" and not self.fallback_used and self.history_rows_found > 0

    def to_dict(self) -> dict[str, object]:
        return {
            "source_table": self.source_table,
            "strict_pit_requested": bool(self.strict_pit_requested),
            "strict_pit_satisfied": bool(self.strict_pit_satisfied),
            "history_table_exists": bool(self.history_table_exists),
            "history_rows_found": int(self.history_rows_found),
            "capital_preset_key": self.capital_preset_key,
            "config_fingerprint_present": bool(self.config_fingerprint_present),
            "fallback_used": bool(self.fallback_used),
            "degraded_reasons": list(self.degraded_reasons),
        }


@dataclass(slots=True)
class ScoreLoadResult:
    """Résultat enrichi du chargement des scores."""

    frame: pd.DataFrame
    diagnostics: ScoreLoadDiagnostics


@dataclass(slots=True)
class SentimentPreparationDiagnostics:
    requested_mode: str
    engine_mode: str
    rows_input: int
    rows_missing_before: int = 0
    rows_missing_after: int = 0
    rows_filled_from_final_score: int = 0
    rebuilt_dates_attempted: int = 0
    rebuilt_dates_succeeded: int = 0
    writeback_enabled: bool = False
    writeback_performed: bool = False
    walk_forward_overlay_applied: bool = False
    walk_forward_artifact_path: str | None = None
    degraded_reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "requested_mode": self.requested_mode,
            "engine_mode": self.engine_mode,
            "rows_input": int(self.rows_input),
            "rows_missing_before": int(self.rows_missing_before),
            "rows_missing_after": int(self.rows_missing_after),
            "rows_filled_from_final_score": int(self.rows_filled_from_final_score),
            "rebuilt_dates_attempted": int(self.rebuilt_dates_attempted),
            "rebuilt_dates_succeeded": int(self.rebuilt_dates_succeeded),
            "writeback_enabled": bool(self.writeback_enabled),
            "writeback_performed": bool(self.writeback_performed),
            "walk_forward_overlay_applied": bool(self.walk_forward_overlay_applied),
            "walk_forward_artifact_path": self.walk_forward_artifact_path,
            "degraded_reasons": list(self.degraded_reasons),
        }


@dataclass(slots=True)
class PreparedScoresResult:
    frame: pd.DataFrame
    diagnostics: SentimentPreparationDiagnostics


@dataclass(slots=True)
class MlPreparationDiagnostics:
    requested_mode: str
    requested_strategy: str
    effective_strategy: str
    engine_mode: str
    predictions_input_rows: int
    expected_symbol_dates: int
    missing_prediction_keys: int
    rebuilt_prediction_rows: int = 0
    rebuild_attempted: bool = False
    persist_enabled: bool = False
    persist_performed: bool = False
    degraded_reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "requested_mode": self.requested_mode,
            "requested_strategy": self.requested_strategy,
            "effective_strategy": self.effective_strategy,
            "engine_mode": self.engine_mode,
            "predictions_input_rows": int(self.predictions_input_rows),
            "expected_symbol_dates": int(self.expected_symbol_dates),
            "missing_prediction_keys": int(self.missing_prediction_keys),
            "rebuilt_prediction_rows": int(self.rebuilt_prediction_rows),
            "rebuild_attempted": bool(self.rebuild_attempted),
            "persist_enabled": bool(self.persist_enabled),
            "persist_performed": bool(self.persist_performed),
            "degraded_reasons": list(self.degraded_reasons),
        }


@dataclass(slots=True)
class PreparedPredictionsResult:
    frame: pd.DataFrame
    diagnostics: MlPreparationDiagnostics


def build_fidelity_manifest(
    *,
    engine_mode: str,
    start_date: date,
    end_date: date,
    capital_preset_key: str | None,
    score_diagnostics: ScoreLoadDiagnostics | None,
    sentiment_diagnostics: SentimentPreparationDiagnostics | None,
    ml_diagnostics: MlPreparationDiagnostics | None,
    sentiment_mode: str,
    ml_mode: str,
    ml_pit_strategy: str,
) -> dict[str, Any]:
    score_payload = score_diagnostics.to_dict() if score_diagnostics is not None else {}
    sentiment_payload = sentiment_diagnostics.to_dict() if sentiment_diagnostics is not None else {}
    ml_payload = ml_diagnostics.to_dict() if ml_diagnostics is not None else {}
    raw_degraded_reasons = score_payload.get("degraded_reasons", [])
    degraded_reasons = list(raw_degraded_reasons) if isinstance(raw_degraded_reasons, (list, tuple)) else []
    for payload in (sentiment_payload, ml_payload):
        extra_reasons = payload.get("degraded_reasons", [])
        if isinstance(extra_reasons, (list, tuple)):
            for reason in extra_reasons:
                if reason not in degraded_reasons:
                    degraded_reasons.append(reason)
    return {
        "engine_mode": engine_mode,
        "strict_pit_requested": engine_mode == "pipeline",
        "strict_pit_satisfied": bool(score_payload.get("strict_pit_satisfied", engine_mode != "pipeline")),
        "degraded": bool(degraded_reasons),
        "degraded_reasons": degraded_reasons,
        "requested_window": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        },
        "capital_preset_key": capital_preset_key,
        "scores": score_payload,
        "sentiment": sentiment_payload,
        "ml": ml_payload,
        "modes": {
            "sentiment_mode": sentiment_mode,
            "ml_mode": ml_mode,
            "ml_pit_strategy": ml_pit_strategy,
        },
    }


def save_fidelity_manifest(manifest: dict[str, Any], output_dir: Path) -> Path:
    """Sauvegarde le manifeste de fidélité d'un run pipeline-aware."""
    output_dir.mkdir(parents=True, exist_ok=True)
    filepath = output_dir / "fidelity_manifest.json"
    filepath.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return filepath


__all__ = [
    "PitHistoryRequiredError",
    "PitMlStrategyUnsupportedError",
    "resolve_ml_pit_strategy",
    "ScoreLoadDiagnostics",
    "ScoreLoadResult",
    "SentimentPreparationDiagnostics",
    "PreparedScoresResult",
    "MlPreparationDiagnostics",
    "PreparedPredictionsResult",
    "build_fidelity_manifest",
    "save_fidelity_manifest",
]


