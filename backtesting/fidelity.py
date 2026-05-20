"""Primitives de fidélité pour le backtesting pipeline-aware."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
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
    "prediction_missing": {
        "component": "ml",
        "category": "missing_cause",
        "severity": "warning",
        "label": "Prédiction persistée absente et aucun artefact exploitable invoqué.",
    },
    "artifact_missing": {
        "component": "ml",
        "category": "missing_cause",
        "severity": "warning",
        "label": "Artefact ML requis manquant pour reconstruire la prédiction.",
    },
    "artifact_invalid": {
        "component": "ml",
        "category": "missing_cause",
        "severity": "warning",
        "label": "Artefact ML présent mais invalide, corrompu ou incompatible.",
    },
    "rebuild_unavailable": {
        "component": "ml",
        "category": "missing_cause",
        "severity": "warning",
        "label": "Rebuild ML tenté mais non exploitable faute de contexte suffisant.",
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


def _normalize_string_list(values: object) -> list[str]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return normalized


def _normalize_symbol_cause_mapping(value: object) -> dict[str, list[str]]:
    if not isinstance(value, Mapping):
        return {}
    normalized: dict[str, list[str]] = {}
    for raw_symbol, raw_causes in value.items():
        symbol = str(raw_symbol or "").strip().upper()
        if not symbol:
            continue
        causes = _normalize_reason_list(raw_causes)
        if causes:
            normalized[symbol] = causes
    return normalized


def _normalize_count_mapping(value: object) -> dict[str, int]:
    if not isinstance(value, Mapping):
        return {}
    normalized: dict[str, int] = {}
    for raw_key, raw_count in value.items():
        key = _normalize_reason(raw_key)
        count = _safe_int(raw_count)
        if key and count > 0:
            normalized[key] = count
    return normalized


def _normalize_trade_date_series(frame: pd.DataFrame) -> pd.Series:
    if "trade_date" not in frame.columns or frame.empty:
        return pd.Series(dtype="datetime64[ns]")
    return pd.to_datetime(frame["trade_date"], errors="coerce").dt.normalize()


def _infer_score_source_counts(scores_day: pd.DataFrame) -> dict[str, int]:
    if scores_day.empty:
        return {}
    if "score_source" in scores_day.columns and scores_day["score_source"].notna().any():
        source_series = scores_day["score_source"].astype("string")
    else:
        inferred = pd.Series(pd.NA, index=scores_day.index, dtype="object")
        if "final_score_walk_forward" in scores_day.columns:
            mask = scores_day["final_score_walk_forward"].notna()
            inferred = inferred.where(~mask, "final_score_walk_forward")
        if "final_score_sentiment" in scores_day.columns:
            mask = inferred.isna() & scores_day["final_score_sentiment"].notna()
            inferred = inferred.where(~mask, "final_score_sentiment")
        if "final_score" in scores_day.columns:
            mask = inferred.isna() & scores_day["final_score"].notna()
            inferred = inferred.where(~mask, "final_score")
        source_series = inferred.astype("string")
    counts = source_series.dropna().value_counts()
    return {str(key): int(value) for key, value in counts.items()}


def _sorted_unique_symbols(frame: pd.DataFrame, *, mask: pd.Series | None = None) -> list[str]:
    if frame.empty or "symbol" not in frame.columns:
        return []
    working = frame.loc[mask] if mask is not None else frame
    if working.empty:
        return []
    return sorted({str(symbol).strip().upper() for symbol in working["symbol"].dropna().tolist() if str(symbol).strip()})


def build_replay_diagnostic_summary(
    *,
    scores_df: pd.DataFrame,
    predictions_df: pd.DataFrame | None,
    signals_df: pd.DataFrame | None,
    fidelity_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    """Construit un diagnostic court par séance pour expliquer le replay backtest.

    Le payload est volontairement compact et orienté debug opérateur : couverture
    scores/sentiment/ML, sélections de la séance et sources de score dominantes.
    """
    normalized_scores = scores_df.copy() if isinstance(scores_df, pd.DataFrame) else pd.DataFrame()
    normalized_preds = predictions_df.copy() if isinstance(predictions_df, pd.DataFrame) else pd.DataFrame()
    normalized_signals = signals_df.copy() if isinstance(signals_df, pd.DataFrame) else pd.DataFrame()

    if not normalized_scores.empty:
        normalized_scores["trade_date"] = _normalize_trade_date_series(normalized_scores)
    if not normalized_preds.empty:
        normalized_preds["trade_date"] = _normalize_trade_date_series(normalized_preds)
    if not normalized_signals.empty and "trade_date" in normalized_signals.columns:
        normalized_signals["trade_date"] = _normalize_trade_date_series(normalized_signals)

    all_dates: set[pd.Timestamp] = set()
    for frame in (normalized_scores, normalized_preds, normalized_signals):
        if isinstance(frame, pd.DataFrame) and not frame.empty and "trade_date" in frame.columns:
            all_dates.update(pd.DatetimeIndex(frame["trade_date"].dropna().tolist()))

    sessions: list[dict[str, Any]] = []
    for trade_date in sorted(all_dates):
        scores_day = normalized_scores.loc[normalized_scores["trade_date"] == trade_date].copy() if not normalized_scores.empty else pd.DataFrame()
        preds_day = normalized_preds.loc[normalized_preds["trade_date"] == trade_date].copy() if not normalized_preds.empty else pd.DataFrame()
        signals_day = normalized_signals.loc[normalized_signals["trade_date"] == trade_date].copy() if not normalized_signals.empty else pd.DataFrame()

        candidate_symbols = _sorted_unique_symbols(scores_day)
        prediction_symbols = set(_sorted_unique_symbols(preds_day))
        if "selected" in signals_day.columns:
            selected_mask = signals_day["selected"].fillna(False).astype(bool)
            selected_symbols = _sorted_unique_symbols(signals_day, mask=selected_mask)
            selected_count = int(selected_mask.sum())
            selected_score_source_counts = _infer_score_source_counts(signals_day.loc[selected_mask])
        else:
            selected_symbols = _sorted_unique_symbols(signals_day)
            selected_count = len(selected_symbols)
            selected_score_source_counts = _infer_score_source_counts(signals_day)

        missing_sentiment_mask = (
            scores_day["final_score_sentiment"].isna()
            if "final_score_sentiment" in scores_day.columns
            else pd.Series(False, index=scores_day.index)
        )
        missing_sentiment_symbols = _sorted_unique_symbols(scores_day, mask=missing_sentiment_mask)
        missing_ml_symbols = sorted(set(candidate_symbols) - prediction_symbols)

        session_payload = {
            "trade_date": pd.Timestamp(trade_date).date().isoformat(),
            "candidate_rows": int(len(scores_day)),
            "candidate_symbols": candidate_symbols,
            "candidate_symbol_count": len(candidate_symbols),
            "score_source_counts": _infer_score_source_counts(scores_day),
            "predictions_rows": int(len(preds_day)),
            "prediction_symbol_count": len(prediction_symbols),
            "missing_sentiment_rows": int(missing_sentiment_mask.sum()) if len(scores_day) else 0,
            "missing_sentiment_symbols": missing_sentiment_symbols,
            "missing_ml_symbol_count": len(missing_ml_symbols),
            "missing_ml_symbols": missing_ml_symbols,
            "selected_count": selected_count,
            "selected_symbols": selected_symbols,
            "selected_score_source_counts": selected_score_source_counts,
            "degraded": bool(missing_sentiment_symbols or missing_ml_symbols),
        }
        sessions.append(session_payload)

    degraded_sessions = [session["trade_date"] for session in sessions if bool(session.get("degraded", False))]
    return {
        "taxonomy_version": fidelity_manifest.get("taxonomy_version", 1),
        "engine_mode": fidelity_manifest.get("engine_mode"),
        "requested_window": dict(fidelity_manifest.get("requested_window", {})) if isinstance(fidelity_manifest.get("requested_window"), Mapping) else {},
        "session_count": len(sessions),
        "degraded_session_count": len(degraded_sessions),
        "degraded_sessions": degraded_sessions,
        "sessions": sessions,
    }


def save_replay_diagnostic_summary(summary: Mapping[str, Any], output_dir: Path) -> dict[str, Path]:
    """Sauvegarde le diagnostic court par séance en JSON canonique + CSV aplati."""
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "replay_diagnostic_summary.json"
    csv_path = output_dir / "replay_diagnostic_sessions.csv"
    json_path.write_text(json.dumps(dict(summary), ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    sessions = summary.get("sessions", []) if isinstance(summary, Mapping) else []
    rows: list[dict[str, object]] = []
    if isinstance(sessions, Sequence) and not isinstance(sessions, (str, bytes)):
        for session in sessions:
            if not isinstance(session, Mapping):
                continue
            rows.append(
                {
                    "trade_date": session.get("trade_date"),
                    "candidate_rows": session.get("candidate_rows", 0),
                    "candidate_symbol_count": session.get("candidate_symbol_count", 0),
                    "score_source_counts": json.dumps(session.get("score_source_counts", {}), ensure_ascii=False, sort_keys=True),
                    "predictions_rows": session.get("predictions_rows", 0),
                    "prediction_symbol_count": session.get("prediction_symbol_count", 0),
                    "missing_sentiment_rows": session.get("missing_sentiment_rows", 0),
                    "missing_sentiment_symbols": ", ".join(_normalize_string_list(session.get("missing_sentiment_symbols", []))),
                    "missing_ml_symbol_count": session.get("missing_ml_symbol_count", 0),
                    "missing_ml_symbols": ", ".join(_normalize_string_list(session.get("missing_ml_symbols", []))),
                    "selected_count": session.get("selected_count", 0),
                    "selected_symbols": ", ".join(_normalize_string_list(session.get("selected_symbols", []))),
                    "selected_score_source_counts": json.dumps(session.get("selected_score_source_counts", {}), ensure_ascii=False, sort_keys=True),
                    "degraded": bool(session.get("degraded", False)),
                }
            )
    pd.DataFrame(rows).to_csv(csv_path, index=False)
    return {
        "replay_diagnostic_summary_json": json_path,
        "replay_diagnostic_sessions_csv": csv_path,
    }


def _build_scores_provenance(score_payload: Mapping[str, Any], *, requested_score_column: str | None) -> dict[str, object]:
    source_table = str(score_payload.get("source_table") or "unknown")
    fallback_used = bool(score_payload.get("fallback_used", False))
    provenance_kind = "persisted_history"
    if source_table == "stock_scores" or fallback_used:
        provenance_kind = "current_snapshot_fallback"
    return {
        "component": "scores",
        "provenance_kind": provenance_kind,
        "source_table": source_table,
        "strict_pit_requested": bool(score_payload.get("strict_pit_requested", False)),
        "strict_pit_satisfied": bool(score_payload.get("strict_pit_satisfied", False)),
        "history_table_exists": bool(score_payload.get("history_table_exists", False)),
        "history_rows_found": _safe_int(score_payload.get("history_rows_found", 0)),
        "capital_preset_key": score_payload.get("capital_preset_key"),
        "config_fingerprint_present": bool(score_payload.get("config_fingerprint_present", False)),
        "score_column_requested": requested_score_column or "auto",
    }


def _build_sentiment_provenance(sentiment_payload: Mapping[str, Any], *, sentiment_mode: str) -> dict[str, object]:
    source_tags: list[str] = []
    if sentiment_mode == "off":
        source_tags.append("disabled")
    else:
        source_tags.append("persisted_scores_snapshot")
        if _safe_int(sentiment_payload.get("rebuilt_dates_succeeded", 0)) > 0:
            source_tags.append("rebuilt_missing_snapshots")
        if _safe_int(sentiment_payload.get("rows_filled_from_final_score", 0)) > 0:
            source_tags.append("fallback_final_score")
        if bool(sentiment_payload.get("walk_forward_overlay_applied", False)):
            source_tags.append("walk_forward_overlay")
    return {
        "component": "sentiment",
        "requested_mode": sentiment_payload.get("requested_mode", sentiment_mode),
        "engine_mode": sentiment_payload.get("engine_mode"),
        "source_tags": source_tags,
        "rebuilt_dates_attempted": _safe_int(sentiment_payload.get("rebuilt_dates_attempted", 0)),
        "rebuilt_dates_succeeded": _safe_int(sentiment_payload.get("rebuilt_dates_succeeded", 0)),
        "rows_filled_from_final_score": _safe_int(sentiment_payload.get("rows_filled_from_final_score", 0)),
        "writeback_enabled": bool(sentiment_payload.get("writeback_enabled", False)),
        "writeback_performed": bool(sentiment_payload.get("writeback_performed", False)),
        "walk_forward_overlay_applied": bool(sentiment_payload.get("walk_forward_overlay_applied", False)),
        "walk_forward_artifact_path": sentiment_payload.get("walk_forward_artifact_path"),
    }


def _build_ml_provenance(ml_payload: Mapping[str, Any], *, ml_mode: str, ml_pit_strategy: str) -> dict[str, object]:
    source_tags: list[str] = []
    if ml_mode == "off":
        source_tags.append("disabled")
    else:
        if _safe_int(ml_payload.get("predictions_input_rows", 0)) > 0:
            source_tags.append("persisted_predictions")
        if _safe_int(ml_payload.get("rebuilt_prediction_rows", 0)) > 0:
            source_tags.append("rebuilt_predictions")
        if _safe_int(ml_payload.get("missing_prediction_keys_after", 0)) > 0:
            source_tags.append("remaining_missing_predictions")
        if not source_tags:
            source_tags.append("no_prediction_coverage")
    return {
        "component": "ml",
        "requested_mode": ml_payload.get("requested_mode", ml_mode),
        "requested_strategy": ml_payload.get("requested_strategy", ml_pit_strategy),
        "effective_strategy": ml_payload.get("effective_strategy", ml_pit_strategy),
        "engine_mode": ml_payload.get("engine_mode"),
        "source_tags": source_tags,
        "predictions_input_rows": _safe_int(ml_payload.get("predictions_input_rows", 0)),
        "expected_symbol_dates": _safe_int(ml_payload.get("expected_symbol_dates", 0)),
        "rebuilt_prediction_rows": _safe_int(ml_payload.get("rebuilt_prediction_rows", 0)),
        "rebuild_attempted": bool(ml_payload.get("rebuild_attempted", False)),
        "persist_enabled": bool(ml_payload.get("persist_enabled", False)),
        "persist_performed": bool(ml_payload.get("persist_performed", False)),
        "missing_cause_breakdown": _normalize_count_mapping(ml_payload.get("missing_cause_breakdown", {})),
        "missing_causes_by_symbol": _normalize_symbol_cause_mapping(ml_payload.get("missing_causes_by_symbol", {})),
    }


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
    missing_cause_breakdown: dict[str, int] = field(default_factory=dict)
    missing_causes_by_symbol: dict[str, tuple[str, ...]] = field(default_factory=dict)
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
            "missing_cause_breakdown": {str(key): int(value) for key, value in self.missing_cause_breakdown.items()},
            "missing_causes_by_symbol": {
                str(symbol): list(causes)
                for symbol, causes in self.missing_causes_by_symbol.items()
            },
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

    provenance_payload = {
        "scores": _build_scores_provenance(score_payload, requested_score_column=requested_score_column),
        "sentiment": _build_sentiment_provenance(sentiment_payload, sentiment_mode=sentiment_mode),
        "ml": _build_ml_provenance(ml_payload, ml_mode=ml_mode, ml_pit_strategy=ml_pit_strategy),
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
        "provenance": provenance_payload,
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
    provenance = manifest.get("provenance", {})
    if not isinstance(provenance, Mapping):
        provenance = {}
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
        "provenance": {str(name): dict(payload) for name, payload in provenance.items()},
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


