"""Primitives de fidélité pour le backtesting pipeline-aware."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any
from collections.abc import Mapping, Sequence

import pandas as pd


REASON_TAXONOMY: dict[str, dict[str, str]] = {
    "stock_scores_history_empty": {
        "component": "scores",
        "category": "pit_history",
        "severity": "warning",
        "label": "Historique PIT présent mais vide sur la fenêtre demandée.",
    },
    "stock_scores_history_missing": {
        "component": "scores",
        "category": "pit_history",
        "severity": "warning",
        "label": "Historique PIT indisponible, fallback sur snapshot courant.",
    },
    "final_score_missing": {
        "component": "scores",
        "category": "schema",
        "severity": "error",
        "label": "Colonne final_score absente dans les scores chargés.",
    },
    "sentiment_missing_fallback_final_score": {
        "component": "sentiment",
        "category": "coverage",
        "severity": "warning",
        "label": "Fallback sentiment vers final_score sur une partie du run.",
    },
    "sentiment_rebuild_partial_failure": {
        "component": "sentiment",
        "category": "rebuild",
        "severity": "warning",
        "label": "Reconstruction sentiment partiellement échouée.",
    },
    "ml_predictions_missing": {
        "component": "ml",
        "category": "coverage",
        "severity": "warning",
        "label": "Prédictions ML manquantes sur une partie du run.",
    },
    "ml_rebuild_partial_failure": {
        "component": "ml",
        "category": "rebuild",
        "severity": "warning",
        "label": "Reconstruction ML partiellement échouée.",
    },
    "walk_forward_artifact_missing": {
        "component": "walk_forward",
        "category": "artifact",
        "severity": "warning",
        "label": "Artefact walk-forward demandé mais indisponible.",
    },
}

FIDELITY_COMPONENTS: tuple[str, ...] = (
    "bars",
    "scores",
    "sentiment",
    "ml",
    "walk_forward",
    "risk",
    "execution",
)


def _normalize_reason(reason: object) -> str:
    text = str(reason or "").strip().lower().replace(" ", "_")
    return text


def _normalize_reason_list(reasons: object) -> list[str]:
    if not isinstance(reasons, Sequence) or isinstance(reasons, (str, bytes)):
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for reason in reasons:
        value = _normalize_reason(reason)
        if not value or value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return normalized


def _reason_details(reasons: Sequence[str]) -> list[dict[str, str]]:
    details: list[dict[str, str]] = []
    for reason in reasons:
        taxonomy = REASON_TAXONOMY.get(reason)
        if taxonomy is None:
            details.append(
                {
                    "reason": reason,
                    "component": "unknown",
                    "category": "custom",
                    "severity": "warning",
                    "label": reason,
                }
            )
            continue
        details.append(
            {
                "reason": reason,
                "component": taxonomy["component"],
                "category": taxonomy["category"],
                "severity": taxonomy["severity"],
                "label": taxonomy["label"],
            }
        )
    return details


def _normalize_symbols(symbols: object) -> list[str]:
    if not isinstance(symbols, Sequence) or isinstance(symbols, (str, bytes)):
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for symbol in symbols:
        value = str(symbol or "").strip().upper()
        if not value or value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return normalized


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coverage_payload(
    *,
    rows_input: object,
    rows_missing_before: object,
    rows_missing_after: object,
    missing_symbols_before: object,
    missing_symbols_after: object,
) -> dict[str, object]:
    input_rows = max(_safe_int(rows_input), 0)
    missing_before = max(_safe_int(rows_missing_before), 0)
    missing_after = max(_safe_int(rows_missing_after), 0)
    before_symbols = _normalize_symbols(missing_symbols_before)
    after_symbols = _normalize_symbols(missing_symbols_after)
    covered_before = max(input_rows - missing_before, 0)
    covered_after = max(input_rows - missing_after, 0)
    before_ratio = (covered_before / input_rows) if input_rows else 1.0
    after_ratio = (covered_after / input_rows) if input_rows else 1.0
    return {
        "rows_input": input_rows,
        "rows_missing_before": missing_before,
        "rows_missing_after": missing_after,
        "rows_covered_before": covered_before,
        "rows_covered_after": covered_after,
        "coverage_ratio_before": before_ratio,
        "coverage_ratio_after": after_ratio,
        "missing_symbols_before": before_symbols,
        "missing_symbols_after": after_symbols,
        "missing_symbol_count_before": len(before_symbols),
        "missing_symbol_count_after": len(after_symbols),
    }


def _component_status_payload(
    component: str,
    *,
    enabled: bool,
    degraded_reasons: Sequence[str],
    details: Mapping[str, Any] | None = None,
) -> dict[str, object]:
    normalized_reasons = _normalize_reason_list(list(degraded_reasons))
    status = "disabled"
    if enabled:
        status = "degraded" if normalized_reasons else "ok"
    payload: dict[str, object] = {
        "component": component,
        "enabled": bool(enabled),
        "status": status,
        "degraded": bool(enabled and normalized_reasons),
        "degraded_reasons": normalized_reasons,
        "degraded_reason_details": _reason_details(normalized_reasons),
    }
    if details:
        payload["details"] = dict(details)
    return payload


def _extract_component_reasons(component: str, reasons: Sequence[str]) -> list[str]:
    extracted: list[str] = []
    for reason in reasons:
        taxonomy = REASON_TAXONOMY.get(reason)
        if taxonomy is None:
            continue
        if taxonomy["component"] == component:
            extracted.append(reason)
    return extracted


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
    missing_symbols_before: tuple[str, ...] = ()
    missing_symbols_after: tuple[str, ...] = ()
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
            "missing_symbols_before": list(self.missing_symbols_before),
            "missing_symbols_after": list(self.missing_symbols_after),
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
    missing_prediction_keys_after: int = 0
    missing_symbols_before: tuple[str, ...] = ()
    missing_symbols_after: tuple[str, ...] = ()
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
            "missing_prediction_keys_after": int(self.missing_prediction_keys_after),
            "missing_symbols_before": list(self.missing_symbols_before),
            "missing_symbols_after": list(self.missing_symbols_after),
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
    component_details: Mapping[str, Mapping[str, Any]] | None = None,
    requested_score_column: str | None = None,
    walk_forward_artifacts_dir: str | None = None,
) -> dict[str, Any]:
    score_payload = score_diagnostics.to_dict() if score_diagnostics is not None else {}
    sentiment_payload = sentiment_diagnostics.to_dict() if sentiment_diagnostics is not None else {}
    ml_payload = ml_diagnostics.to_dict() if ml_diagnostics is not None else {}
    score_payload["degraded_reasons"] = _normalize_reason_list(score_payload.get("degraded_reasons", []))
    sentiment_payload["degraded_reasons"] = _normalize_reason_list(sentiment_payload.get("degraded_reasons", []))
    ml_payload["degraded_reasons"] = _normalize_reason_list(ml_payload.get("degraded_reasons", []))
    raw_degraded_reasons = score_payload.get("degraded_reasons", [])
    degraded_reasons = list(raw_degraded_reasons) if isinstance(raw_degraded_reasons, list) else []
    for payload in (sentiment_payload, ml_payload):
        extra_reasons = payload.get("degraded_reasons", [])
        if isinstance(extra_reasons, list):
            for reason in extra_reasons:
                if reason not in degraded_reasons:
                    degraded_reasons.append(reason)
    component_details_payload = {str(key): dict(value) for key, value in (component_details or {}).items()}
    bars_payload = component_details_payload.get("bars", {})
    risk_payload = component_details_payload.get("risk", {})
    execution_payload = component_details_payload.get("execution", {})
    walk_forward_requested = bool(walk_forward_artifacts_dir)
    walk_forward_applied = bool(sentiment_payload.get("walk_forward_overlay_applied", False))
    walk_forward_reasons: list[str] = []
    if walk_forward_requested and not walk_forward_applied:
        walk_forward_reasons.append("walk_forward_artifact_missing")
        if "walk_forward_artifact_missing" not in degraded_reasons:
            degraded_reasons.append("walk_forward_artifact_missing")

    coverage_payload = {
        "sentiment": _coverage_payload(
            rows_input=sentiment_payload.get("rows_input", 0),
            rows_missing_before=sentiment_payload.get("rows_missing_before", 0),
            rows_missing_after=sentiment_payload.get("rows_missing_after", 0),
            missing_symbols_before=sentiment_payload.get("missing_symbols_before", []),
            missing_symbols_after=sentiment_payload.get("missing_symbols_after", []),
        ),
        "ml": _coverage_payload(
            rows_input=ml_payload.get("expected_symbol_dates", 0),
            rows_missing_before=ml_payload.get("missing_prediction_keys", 0),
            rows_missing_after=ml_payload.get("missing_prediction_keys_after", ml_payload.get("missing_prediction_keys", 0)),
            missing_symbols_before=ml_payload.get("missing_symbols_before", []),
            missing_symbols_after=ml_payload.get("missing_symbols_after", []),
        ),
    }

    component_status = {
        "bars": _component_status_payload(
            "bars",
            enabled=True,
            degraded_reasons=_normalize_reason_list(bars_payload.get("degraded_reasons", [])),
            details=bars_payload,
        ),
        "scores": _component_status_payload(
            "scores",
            enabled=True,
            degraded_reasons=score_payload.get("degraded_reasons", []),
            details={
                "source_table": score_payload.get("source_table"),
                "strict_pit_requested": score_payload.get("strict_pit_requested"),
                "strict_pit_satisfied": score_payload.get("strict_pit_satisfied"),
                "score_column_requested": requested_score_column or "auto",
            },
        ),
        "sentiment": _component_status_payload(
            "sentiment",
            enabled=sentiment_mode != "off",
            degraded_reasons=sentiment_payload.get("degraded_reasons", []),
            details={
                "requested_mode": sentiment_payload.get("requested_mode", sentiment_mode),
                "coverage": coverage_payload["sentiment"],
            },
        ),
        "ml": _component_status_payload(
            "ml",
            enabled=ml_mode != "off",
            degraded_reasons=ml_payload.get("degraded_reasons", []),
            details={
                "requested_mode": ml_payload.get("requested_mode", ml_mode),
                "effective_strategy": ml_payload.get("effective_strategy", ml_pit_strategy),
                "coverage": coverage_payload["ml"],
            },
        ),
        "walk_forward": _component_status_payload(
            "walk_forward",
            enabled=walk_forward_requested or walk_forward_applied,
            degraded_reasons=walk_forward_reasons,
            details={
                "requested": walk_forward_requested,
                "applied": walk_forward_applied,
                "artifact_path": sentiment_payload.get("walk_forward_artifact_path"),
                "requested_artifacts_dir": walk_forward_artifacts_dir,
            },
        ),
        "risk": _component_status_payload(
            "risk",
            enabled=bool(risk_payload.get("enabled", False)),
            degraded_reasons=_normalize_reason_list(risk_payload.get("degraded_reasons", [])),
            details=risk_payload,
        ),
        "execution": _component_status_payload(
            "execution",
            enabled=bool(execution_payload.get("enabled", False)),
            degraded_reasons=_normalize_reason_list(execution_payload.get("degraded_reasons", [])),
            details=execution_payload,
        ),
    }

    return {
        "taxonomy_version": 1,
        "components": list(FIDELITY_COMPONENTS),
        "engine_mode": engine_mode,
        "strict_pit_requested": engine_mode == "pipeline",
        "strict_pit_satisfied": bool(score_payload.get("strict_pit_satisfied", engine_mode != "pipeline")),
        "degraded": bool(degraded_reasons),
        "degraded_reasons": degraded_reasons,
        "degraded_reason_details": _reason_details(degraded_reasons),
        "requested_window": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        },
        "capital_preset_key": capital_preset_key,
        "coverage": coverage_payload,
        "component_status": component_status,
        "summary": {
            "enabled_components": [name for name, payload in component_status.items() if bool(payload.get("enabled", False))],
            "degraded_components": [name for name, payload in component_status.items() if bool(payload.get("degraded", False))],
        },
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


def build_coverage_summary(manifest: Mapping[str, Any]) -> dict[str, Any]:
    component_status = manifest.get("component_status", {})
    if not isinstance(component_status, Mapping):
        component_status = {}
    coverage = manifest.get("coverage", {})
    if not isinstance(coverage, Mapping):
        coverage = {}
    return {
        "taxonomy_version": manifest.get("taxonomy_version", 1),
        "engine_mode": manifest.get("engine_mode"),
        "strict_pit_requested": bool(manifest.get("strict_pit_requested", False)),
        "strict_pit_satisfied": bool(manifest.get("strict_pit_satisfied", False)),
        "degraded": bool(manifest.get("degraded", False)),
        "degraded_reasons": _normalize_reason_list(manifest.get("degraded_reasons", [])),
        "degraded_reason_details": _reason_details(_normalize_reason_list(manifest.get("degraded_reasons", []))),
        "requested_window": dict(manifest.get("requested_window", {})) if isinstance(manifest.get("requested_window"), Mapping) else {},
        "component_status": {str(name): dict(payload) for name, payload in component_status.items()},
        "coverage": {str(name): dict(payload) for name, payload in coverage.items()},
        "summary": dict(manifest.get("summary", {})) if isinstance(manifest.get("summary"), Mapping) else {},
    }


def save_coverage_summary(manifest: Mapping[str, Any], output_dir: Path) -> Path:
    """Sauvegarde un résumé de couverture focalisé sur la fidélité opérationnelle."""
    output_dir.mkdir(parents=True, exist_ok=True)
    filepath = output_dir / "coverage_summary.json"
    payload = build_coverage_summary(manifest)
    filepath.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
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
    "REASON_TAXONOMY",
    "build_coverage_summary",
    "build_fidelity_manifest",
    "save_fidelity_manifest",
    "save_coverage_summary",
]


