"""Primitives de fidélité pour le backtesting pipeline-aware."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, cast
from collections.abc import Mapping, Sequence

import pandas as pd

from common.quantity_utils import normalize_share_quantity

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


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
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


def _normalize_timestamp_value(value: object) -> pd.Timestamp:
    timestamp = pd.to_datetime(value, errors="coerce")
    if pd.isna(timestamp):
        return pd.NaT
    normalized = pd.Timestamp(timestamp)
    if normalized.tzinfo is not None:
        normalized = normalized.tz_convert("UTC").tz_localize(None)
    return normalized.normalize()


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


def _sorted_unique_values(frame: pd.DataFrame, column: str) -> list[str]:
    if frame.empty or column not in frame.columns:
        return []
    return sorted({str(value).strip() for value in frame[column].dropna().tolist() if str(value).strip()})


def _status_from_flag(degraded: bool) -> str:
    return "degraded" if degraded else "ok"


def _extract_run_level_ref(component_details: Mapping[str, Any], *paths: tuple[str, ...]) -> str | None:
    current: object = component_details
    for key in paths:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    text = str(current or "").strip()
    return text or None


def _build_session_scores_snapshot_id(
    *,
    trade_date: pd.Timestamp,
    scores_day: pd.DataFrame,
    scores_provenance: Mapping[str, Any],
) -> str:
    capital_preset_key = None
    config_fingerprint = None
    if not scores_day.empty and "capital_preset_key" in scores_day.columns:
        capital_values = _sorted_unique_values(scores_day, "capital_preset_key")
        capital_preset_key = capital_values[0] if capital_values else None
    if not scores_day.empty and "config_fingerprint" in scores_day.columns:
        fingerprint_values = _sorted_unique_values(scores_day, "config_fingerprint")
        config_fingerprint = fingerprint_values[0] if fingerprint_values else None
    capital_preset_key = capital_preset_key or str(scores_provenance.get("capital_preset_key") or "na")
    config_fingerprint = config_fingerprint or (
        "present" if bool(scores_provenance.get("config_fingerprint_present", False)) else "na"
    )
    source_table = str(scores_provenance.get("source_table") or "unknown")
    return f"{pd.Timestamp(trade_date).date().isoformat()}|{source_table}|{capital_preset_key}|{config_fingerprint}"


def _build_component_attribution(
    *,
    score_source_counts: Mapping[str, int],
    selected_score_source_counts: Mapping[str, int],
    missing_sentiment_symbols: Sequence[str],
    missing_ml_symbols: Sequence[str],
    ml_missing_causes_by_symbol: Mapping[str, Sequence[str]],
    walk_forward_symbols: Sequence[str],
    selected_symbols: Sequence[str],
    signals_day: pd.DataFrame,
    provenance_refs: Mapping[str, Any],
    fidelity_manifest: Mapping[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    risk_details = cast(Mapping[str, Any], cast(Mapping[str, Any], fidelity_manifest.get("component_status", {})).get("risk", {}).get("details", {})) if isinstance(cast(Mapping[str, Any], fidelity_manifest.get("component_status", {})).get("risk", {}), Mapping) else {}
    execution_details = cast(Mapping[str, Any], cast(Mapping[str, Any], fidelity_manifest.get("component_status", {})).get("execution", {}).get("details", {})) if isinstance(cast(Mapping[str, Any], fidelity_manifest.get("component_status", {})).get("execution", {}), Mapping) else {}

    risk_signal_count = int(len(signals_day)) if not signals_day.empty and "decision" in signals_day.columns else int(len(selected_symbols))
    execution_signal_count = int(len(signals_day)) if not signals_day.empty and any(col in signals_day.columns for col in ("execution_date", "fill_price", "filled_qty", "replay_exit_reason")) else 0
    walk_forward_requested = bool(cast(Mapping[str, Any], fidelity_manifest.get("component_status", {})).get("walk_forward", {}).get("details", {}).get("requested", False)) if isinstance(cast(Mapping[str, Any], fidelity_manifest.get("component_status", {})).get("walk_forward", {}), Mapping) else False

    component_attribution: dict[str, Any] = {
        "scores": {
            "status": _status_from_flag(str(cast(Mapping[str, Any], fidelity_manifest.get("provenance", {})).get("scores", {}).get("provenance_kind", "persisted_history")) != "persisted_history"),
            "score_source_counts": dict(score_source_counts),
            "snapshot_id": provenance_refs.get("scores_snapshot_id"),
        },
        "sentiment": {
            "status": _status_from_flag(bool(missing_sentiment_symbols)),
            "missing_symbol_count": len(missing_sentiment_symbols),
            "missing_symbols": list(missing_sentiment_symbols),
        },
        "ml": {
            "status": _status_from_flag(bool(missing_ml_symbols)),
            "missing_symbol_count": len(missing_ml_symbols),
            "missing_symbols": list(missing_ml_symbols),
            "missing_causes_by_symbol": {str(symbol): list(causes) for symbol, causes in ml_missing_causes_by_symbol.items()},
            "ml_run_ids": list(provenance_refs.get("ml_run_ids", [])),
        },
        "walk_forward": {
            "status": _status_from_flag(bool(walk_forward_requested and not walk_forward_symbols and cast(Mapping[str, Any], fidelity_manifest.get("component_status", {})).get("walk_forward", {}).get("status") == "degraded")),
            "applied_symbol_count": len(walk_forward_symbols),
            "applied_symbols": list(walk_forward_symbols),
            "selected_score_source_counts": dict(selected_score_source_counts),
        },
        "risk": {
            "status": _status_from_flag(bool(risk_details.get("enabled", False)) and risk_signal_count == 0 and bool(selected_symbols) is False),
            "enabled": bool(risk_details.get("enabled", False)),
            "signal_count": risk_signal_count,
            "risk_run_id": provenance_refs.get("risk_run_id"),
        },
        "execution": {
            "status": _status_from_flag(bool(execution_details.get("enabled", False)) and execution_signal_count == 0 and bool(selected_symbols) is True),
            "enabled": bool(execution_details.get("enabled", False)),
            "signal_count": execution_signal_count,
            "exec_run_id": provenance_refs.get("exec_run_id"),
        },
    }
    degraded_components = [
        component_name
        for component_name, payload in component_attribution.items()
        if isinstance(payload, Mapping) and str(payload.get("status") or "") == "degraded"
    ]
    return component_attribution, degraded_components


def _build_critical_symbol_payload(
    *,
    candidate_symbols: Sequence[str],
    selected_symbols: Sequence[str],
    missing_sentiment_symbols: Sequence[str],
    missing_ml_symbols: Sequence[str],
    ml_missing_causes_by_symbol: Mapping[str, Sequence[str]],
    walk_forward_symbols: Sequence[str],
    score_source_by_symbol: Mapping[str, str],
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    criticality_order = {
        "execution": 6,
        "risk": 5,
        "ml": 4,
        "sentiment": 3,
        "walk_forward": 2,
        "scores": 1,
    }
    selected_set = set(selected_symbols)
    missing_sentiment_set = set(missing_sentiment_symbols)
    missing_ml_set = set(missing_ml_symbols)
    walk_forward_set = set(walk_forward_symbols)
    symbol_payloads: list[dict[str, Any]] = []

    for symbol in candidate_symbols:
        components: set[str] = set()
        reasons: list[str] = []
        if symbol in missing_sentiment_set:
            components.add("sentiment")
            reasons.append("sentiment_missing")
        if symbol in missing_ml_set:
            components.add("ml")
            reasons.extend(list(ml_missing_causes_by_symbol.get(symbol, ["prediction_missing"])))
        source = str(score_source_by_symbol.get(symbol) or "")
        if source == "final_score":
            components.add("scores")
            reasons.append("score_fallback_final_score")
        if symbol in walk_forward_set:
            components.add("walk_forward")
        if not components:
            continue
        criticality = sum(criticality_order.get(component, 0) for component in components) + (10 if symbol in selected_set else 0)
        symbol_payloads.append(
            {
                "symbol": symbol,
                "selected": bool(symbol in selected_set),
                "components": sorted(components, key=lambda component: (-criticality_order.get(component, 0), component)),
                "reasons": list(dict.fromkeys(reasons)),
                "score_source": source or None,
                "criticality": criticality,
            }
        )

    symbol_payloads.sort(key=lambda item: (-int(item.get("criticality", 0)), str(item.get("symbol") or "")))
    top_symbol = symbol_payloads[0] if symbol_payloads else None
    if top_symbol is not None:
        top_symbol = {key: value for key, value in top_symbol.items() if key != "criticality"}
    sanitized_payloads = [{key: value for key, value in payload.items() if key != "criticality"} for payload in symbol_payloads]
    return top_symbol, sanitized_payloads


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
    provenance_payload = fidelity_manifest.get("provenance", {})
    if not isinstance(provenance_payload, Mapping):
        provenance_payload = {}
    component_status_payload = fidelity_manifest.get("component_status", {})
    if not isinstance(component_status_payload, Mapping):
        component_status_payload = {}
    walk_forward_component = component_status_payload.get("walk_forward", {})
    if not isinstance(walk_forward_component, Mapping):
        walk_forward_component = {}
    risk_component = component_status_payload.get("risk", {})
    if not isinstance(risk_component, Mapping):
        risk_component = {}
    execution_component = component_status_payload.get("execution", {})
    if not isinstance(execution_component, Mapping):
        execution_component = {}

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
        score_source_counts = _infer_score_source_counts(scores_day)
        score_source_by_symbol = {}
        if not scores_day.empty:
            inferred_sources = _infer_score_source_counts(scores_day)
            if "score_source" in scores_day.columns and scores_day["score_source"].notna().any():
                score_source_by_symbol = {
                    str(row["symbol"]).strip().upper(): str(row["score_source"])
                    for _, row in scores_day[["symbol", "score_source"]].dropna().drop_duplicates(subset=["symbol"], keep="last").iterrows()
                }
            else:
                for _, row in scores_day.iterrows():
                    symbol = str(row.get("symbol") or "").strip().upper()
                    if not symbol:
                        continue
                    if pd.notna(row.get("final_score_walk_forward")):
                        score_source_by_symbol[symbol] = "final_score_walk_forward"
                    elif pd.notna(row.get("final_score_sentiment")):
                        score_source_by_symbol[symbol] = "final_score_sentiment"
                    elif pd.notna(row.get("final_score")):
                        score_source_by_symbol[symbol] = "final_score"
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
        walk_forward_symbols = sorted(
            {
                symbol
                for symbol, source in score_source_by_symbol.items()
                if source == "final_score_walk_forward"
            }
        )
        ml_missing_causes_by_symbol = {}
        ml_provenance = provenance_payload.get("ml", {})
        if isinstance(ml_provenance, Mapping):
            raw_causes_by_symbol = ml_provenance.get("missing_causes_by_symbol", {})
            if isinstance(raw_causes_by_symbol, Mapping):
                for symbol in missing_ml_symbols:
                    causes = raw_causes_by_symbol.get(symbol, [])
                    ml_missing_causes_by_symbol[symbol] = _normalize_reason_list(causes)
        provenance_refs = {
            "scores_snapshot_id": _build_session_scores_snapshot_id(
                trade_date=trade_date,
                scores_day=scores_day,
                scores_provenance=cast(Mapping[str, Any], provenance_payload.get("scores", {})) if isinstance(provenance_payload.get("scores", {}), Mapping) else {},
            ),
            "ml_run_ids": _sorted_unique_values(preds_day, "run_id"),
            "calibration_run_ids": _sorted_unique_values(scores_day, "calibration_run_id"),
            "risk_run_id": _extract_run_level_ref(cast(Mapping[str, Any], risk_component.get("details", {})), "diagnostics", "risk_run_id") or _extract_run_level_ref(cast(Mapping[str, Any], execution_component.get("details", {})), "phase2_execution", "risk_run_id"),
            "exec_run_id": _extract_run_level_ref(cast(Mapping[str, Any], execution_component.get("details", {})), "phase2_execution", "exec_run_id") or _extract_run_level_ref(cast(Mapping[str, Any], execution_component.get("details", {})), "phase3_execution_replay", "exec_run_id"),
        }
        component_attribution, degraded_components = _build_component_attribution(
            score_source_counts=score_source_counts,
            selected_score_source_counts=selected_score_source_counts,
            missing_sentiment_symbols=missing_sentiment_symbols,
            missing_ml_symbols=missing_ml_symbols,
            ml_missing_causes_by_symbol=ml_missing_causes_by_symbol,
            walk_forward_symbols=walk_forward_symbols,
            selected_symbols=selected_symbols,
            signals_day=signals_day,
            provenance_refs=provenance_refs,
            fidelity_manifest=fidelity_manifest,
        )
        critical_symbol, critical_symbols = _build_critical_symbol_payload(
            candidate_symbols=candidate_symbols,
            selected_symbols=selected_symbols,
            missing_sentiment_symbols=missing_sentiment_symbols,
            missing_ml_symbols=missing_ml_symbols,
            ml_missing_causes_by_symbol=ml_missing_causes_by_symbol,
            walk_forward_symbols=walk_forward_symbols,
            score_source_by_symbol=score_source_by_symbol,
        )

        session_payload = {
            "trade_date": pd.Timestamp(trade_date).date().isoformat(),
            "scoring_rows": int(len(scores_day)),
            "scoring_symbols": candidate_symbols,
            "scoring_symbol_count": len(candidate_symbols),
            "score_source_counts": score_source_counts,
            "predictions_rows": int(len(preds_day)),
            "prediction_symbol_count": len(prediction_symbols),
            "missing_sentiment_rows": int(missing_sentiment_mask.sum()) if len(scores_day) else 0,
            "missing_sentiment_symbols": missing_sentiment_symbols,
            "missing_ml_symbol_count": len(missing_ml_symbols),
            "missing_ml_symbols": missing_ml_symbols,
            "selected_count": selected_count,
            "selected_symbols": selected_symbols,
            "selected_score_source_counts": selected_score_source_counts,
            "degraded_components": degraded_components,
            "component_attribution": component_attribution,
            "critical_symbol": critical_symbol,
            "critical_symbols": critical_symbols,
            "provenance_refs": provenance_refs,
            "degraded": bool(degraded_components),
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
                    "scoring_rows": session.get("scoring_rows", 0),
                    "scoring_symbol_count": session.get("scoring_symbol_count", 0),
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
                    "degraded_components": ", ".join(_normalize_string_list(session.get("degraded_components", []))),
                    "critical_symbol": session.get("critical_symbol", {}).get("symbol") if isinstance(session.get("critical_symbol"), Mapping) else None,
                    "critical_components": ", ".join(_normalize_string_list(session.get("critical_symbol", {}).get("components", []))) if isinstance(session.get("critical_symbol"), Mapping) else "",
                    "scores_snapshot_id": session.get("provenance_refs", {}).get("scores_snapshot_id") if isinstance(session.get("provenance_refs"), Mapping) else None,
                    "ml_run_ids": ", ".join(_normalize_string_list(session.get("provenance_refs", {}).get("ml_run_ids", []))) if isinstance(session.get("provenance_refs"), Mapping) else "",
                    "risk_run_id": session.get("provenance_refs", {}).get("risk_run_id") if isinstance(session.get("provenance_refs"), Mapping) else None,
                    "exec_run_id": session.get("provenance_refs", {}).get("exec_run_id") if isinstance(session.get("provenance_refs"), Mapping) else None,
                    "degraded": bool(session.get("degraded", False)),
                }
            )
    pd.DataFrame(rows).to_csv(csv_path, index=False)
    return {
        "replay_diagnostic_summary_json": json_path,
        "replay_diagnostic_sessions_csv": csv_path,
    }


def _sorted_session_dates_from_frames(*frames: pd.DataFrame) -> list[pd.Timestamp]:
    session_dates: set[pd.Timestamp] = set()
    for frame in frames:
        if not isinstance(frame, pd.DataFrame) or frame.empty or "trade_date" not in frame.columns:
            continue
        session_dates.update(pd.DatetimeIndex(pd.to_datetime(frame["trade_date"], errors="coerce").dropna().dt.normalize().tolist()))
    return sorted(session_dates)


def _normalize_research_selected_rows(research_signals_df: pd.DataFrame) -> pd.DataFrame:
    if research_signals_df.empty:
        return pd.DataFrame()
    frame = research_signals_df.copy()
    frame["trade_date"] = _normalize_trade_date_series(frame)
    if "selected" in frame.columns:
        frame = frame.loc[frame["selected"].fillna(False).astype(bool)].copy()
    return frame


def _portfolio_entries_to_parity_frame(entries: Sequence[object]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for entry in entries:
        symbol = str(getattr(entry, "symbol", "") or "").strip().upper()
        snapshot_date = getattr(entry, "score_snapshot_date", None)
        trade_date = pd.Timestamp(snapshot_date) if snapshot_date is not None else pd.NaT
        rows.append(
            {
                "trade_date": trade_date,
                "symbol": symbol,
                "selection_rank": getattr(entry, "selection_rank", None),
                "decision_rank": getattr(entry, "decision_rank", None),
                "score_used": getattr(entry, "score_used", None),
                "score_source": getattr(entry, "score_source", None),
                "conviction_score": getattr(entry, "conviction_score", None),
                "conviction_source": (
                    "core.conviction:score_plus_prediction"
                    if getattr(entry, "predicted_proba", None) is not None
                    else "core.conviction:score_only"
                ),
                "predicted_proba": getattr(entry, "predicted_proba", None),
                "decision": str(getattr(entry, "decision", "") or ""),
                "decision_reason": getattr(entry, "decision_reason", None),
                "decision_reason_code": str(getattr(entry, "decision_reason_code", "") or "") or None,
                "target_weight": getattr(entry, "target_weight", None),
                "approved_shares": getattr(entry, "approved_shares", None),
                "score_snapshot_date": snapshot_date.isoformat() if hasattr(snapshot_date, "isoformat") else None,
                "prediction_asof_date": (
                    getattr(entry, "prediction_asof_date", None).isoformat()
                    if hasattr(getattr(entry, "prediction_asof_date", None), "isoformat")
                    else None
                ),
            }
        )
    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame["trade_date"] = pd.to_datetime(frame["trade_date"], errors="coerce").dt.normalize()
    return frame


def build_candidate_target_parity_summary(
    *,
    research_signals_df: pd.DataFrame,
    risk_entries: Sequence[object],
    phase2_mode: str,
) -> dict[str, Any]:
    """Construit un comparatif candidat research -> target risk par séance."""
    normalized_research = _normalize_research_selected_rows(research_signals_df)
    risk_frame = _portfolio_entries_to_parity_frame(risk_entries)
    session_dates = _sorted_session_dates_from_frames(normalized_research, risk_frame)

    sessions: list[dict[str, Any]] = []
    for trade_date in session_dates:
        research_day = normalized_research.loc[normalized_research["trade_date"] == trade_date].copy() if not normalized_research.empty else pd.DataFrame()
        risk_day = risk_frame.loc[risk_frame["trade_date"] == trade_date].copy() if not risk_frame.empty else pd.DataFrame()
        accepted_risk_day = risk_day.loc[pd.to_numeric(risk_day.get("approved_shares"), errors="coerce").fillna(0).astype(float) > 0].copy() if not risk_day.empty else pd.DataFrame()
        rejected_risk_day = risk_day.loc[pd.to_numeric(risk_day.get("approved_shares"), errors="coerce").fillna(0).astype(float) <= 0].copy() if not risk_day.empty else pd.DataFrame()

        research_symbols = _sorted_unique_symbols(research_day)
        target_symbols = _sorted_unique_symbols(accepted_risk_day)
        rejected_symbols = _sorted_unique_symbols(rejected_risk_day)
        common_symbols = sorted(set(research_symbols) & set(target_symbols))
        research_only_symbols = sorted(set(research_symbols) - set(target_symbols))
        risk_only_symbols = sorted(set(target_symbols) - set(research_symbols))
        rejection_reason_counts = {
            str(key): int(value)
            for key, value in rejected_risk_day["decision_reason_code"].dropna().astype(str).value_counts().items()
        } if not rejected_risk_day.empty and "decision_reason_code" in rejected_risk_day.columns else {}

        divergence_reasons: list[str] = []
        if research_only_symbols:
            divergence_reasons.append("research_only_candidates")
        if risk_only_symbols:
            divergence_reasons.append("risk_only_targets")
        if not rejected_risk_day.empty:
            divergence_reasons.append("risk_rejections")

        common_rows: list[dict[str, object]] = []
        for symbol in common_symbols:
            research_row = research_day.loc[research_day["symbol"] == symbol].iloc[0]
            risk_row = accepted_risk_day.loc[accepted_risk_day["symbol"] == symbol].iloc[0]
            common_rows.append(
                {
                    "symbol": symbol,
                    "research_rank": float(research_row.get("rank")) if pd.notna(research_row.get("rank")) else None,
                    "research_score": float(research_row.get("score")) if pd.notna(research_row.get("score")) else None,
                    "research_score_source": research_row.get("score_source"),
                    "research_conviction": float(research_row.get("conviction")) if pd.notna(research_row.get("conviction")) else None,
                    "research_conviction_source": research_row.get("conviction_source"),
                    "risk_selection_rank": int(risk_row.get("selection_rank")) if pd.notna(risk_row.get("selection_rank")) else None,
                    "risk_decision_rank": int(risk_row.get("decision_rank")) if pd.notna(risk_row.get("decision_rank")) else None,
                    "risk_score_used": float(risk_row.get("score_used")) if pd.notna(risk_row.get("score_used")) else None,
                    "risk_score_source": risk_row.get("score_source"),
                    "risk_conviction_score": float(risk_row.get("conviction_score")) if pd.notna(risk_row.get("conviction_score")) else None,
                    "risk_conviction_source": risk_row.get("conviction_source"),
                    "target_weight": float(risk_row.get("target_weight")) if pd.notna(risk_row.get("target_weight")) else None,
                    "approved_shares": float(risk_row.get("approved_shares")) if pd.notna(risk_row.get("approved_shares")) else None,
                }
            )

        rejected_rows: list[dict[str, object]] = []
        for _, row in rejected_risk_day.iterrows():
            rejected_rows.append(
                {
                    "symbol": row.get("symbol"),
                    "selection_rank": int(row.get("selection_rank")) if pd.notna(row.get("selection_rank")) else None,
                    "score_used": float(row.get("score_used")) if pd.notna(row.get("score_used")) else None,
                    "score_source": row.get("score_source"),
                    "conviction_score": float(row.get("conviction_score")) if pd.notna(row.get("conviction_score")) else None,
                    "conviction_source": row.get("conviction_source"),
                    "decision": row.get("decision"),
                    "decision_reason": row.get("decision_reason"),
                    "decision_reason_code": row.get("decision_reason_code"),
                }
            )

        sessions.append(
            {
                "trade_date": pd.Timestamp(trade_date).date().isoformat(),
                "research_selected_count": len(research_symbols),
                "risk_target_count": len(target_symbols),
                "risk_rejected_count": len(rejected_symbols),
                "common_symbol_count": len(common_symbols),
                "research_only_symbols": research_only_symbols,
                "risk_only_symbols": risk_only_symbols,
                "risk_rejected_symbols": rejected_symbols,
                "rejection_reason_counts": rejection_reason_counts,
                "divergence_reasons": divergence_reasons,
                "parity_status": "diverged" if divergence_reasons else "aligned",
                "common_rows": common_rows,
                "rejected_rows": rejected_rows,
            }
        )

    diverged_sessions = [session["trade_date"] for session in sessions if session.get("parity_status") == "diverged"]
    return {
        "enabled": True,
        "phase2_mode": phase2_mode,
        "session_count": len(sessions),
        "diverged_session_count": len(diverged_sessions),
        "diverged_sessions": diverged_sessions,
        "sessions": sessions,
    }


def save_candidate_target_parity_summary(summary: Mapping[str, Any], output_dir: Path) -> dict[str, Path]:
    """Sauvegarde le comparatif candidate->target au format JSON + CSV."""
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "candidate_target_parity_summary.json"
    csv_path = output_dir / "candidate_target_parity_sessions.csv"
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
                    "parity_status": session.get("parity_status"),
                    "research_selected_count": session.get("research_selected_count", 0),
                    "risk_target_count": session.get("risk_target_count", 0),
                    "risk_rejected_count": session.get("risk_rejected_count", 0),
                    "common_symbol_count": session.get("common_symbol_count", 0),
                    "research_only_symbols": ", ".join(_normalize_string_list(session.get("research_only_symbols", []))),
                    "risk_only_symbols": ", ".join(_normalize_string_list(session.get("risk_only_symbols", []))),
                    "risk_rejected_symbols": ", ".join(_normalize_string_list(session.get("risk_rejected_symbols", []))),
                    "divergence_reasons": ", ".join(_normalize_string_list(session.get("divergence_reasons", []))),
                    "rejection_reason_counts": json.dumps(session.get("rejection_reason_counts", {}), ensure_ascii=False, sort_keys=True),
                }
            )
    pd.DataFrame(rows).to_csv(csv_path, index=False)
    return {
        "candidate_target_parity_summary_json": json_path,
        "candidate_target_parity_sessions_csv": csv_path,
    }


def _normalize_compare_frame(frame: pd.DataFrame | None) -> pd.DataFrame:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return pd.DataFrame(columns=["symbol", "decision", "approved_shares", "target_weight", "conviction_score", "run_id"])
    normalized = frame.copy()
    if "symbol" in normalized.columns:
        normalized["symbol"] = normalized["symbol"].astype(str).str.strip().str.upper()
    return normalized


def _normalize_live_buy_symbol_set(frame: pd.DataFrame) -> list[str]:
    if frame.empty or "symbol" not in frame.columns:
        return []
    decisions = frame.get("decision")
    approved = pd.to_numeric(frame.get("approved_shares"), errors="coerce").fillna(0.0)
    buy_like_mask = approved > 0
    if isinstance(decisions, pd.Series):
        normalized_decisions = decisions.astype(str).str.strip().str.upper()
        buy_like_mask = buy_like_mask | normalized_decisions.isin({"BUY", "ACCEPTED", "LONG"})
    return _sorted_unique_symbols(frame, mask=buy_like_mask)


def _research_selected_symbols_for_date(research_signals_df: pd.DataFrame, trade_date: pd.Timestamp) -> list[str]:
    if research_signals_df.empty or "trade_date" not in research_signals_df.columns:
        return []
    normalized = research_signals_df.copy()
    normalized["trade_date"] = _normalize_trade_date_series(normalized)
    normalized = normalized.loc[normalized["trade_date"] == trade_date].copy()
    if normalized.empty:
        return []
    if "selected" in normalized.columns:
        selected = normalized["selected"]
        normalized = normalized.loc[selected.notna() & selected.astype(bool)].copy()
    return _sorted_unique_symbols(normalized)


def _portfolio_entries_to_compare_frame(entries: Sequence[object], *, run_id: str | None = None) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for entry in entries:
        symbol = str(getattr(entry, "symbol", "") or "").strip().upper()
        if not symbol:
            continue
        approved_shares = normalize_share_quantity(_safe_float(getattr(entry, "approved_shares", 0.0), 0.0))
        raw_decision = str(getattr(entry, "decision", "") or "").strip().upper()
        decision = "BUY" if approved_shares > 0 or raw_decision in {"ACCEPTED", "BUY", "LONG"} else "HOLD"
        rows.append(
            {
                "symbol": symbol,
                "decision": decision,
                "approved_shares": approved_shares,
                "target_weight": float(getattr(entry, "target_weight", 0.0) or 0.0),
                "conviction_score": getattr(entry, "conviction_score", None),
                "run_id": run_id,
            }
        )
    return pd.DataFrame(rows)


def _execution_targets_to_compare_frame(targets: Sequence[object], *, run_id: str | None = None) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for target in targets:
        symbol = str(getattr(target, "symbol", "") or "").strip().upper()
        if not symbol:
            continue
        rows.append(
            {
                "symbol": symbol,
                "decision": "BUY",
                "approved_shares": normalize_share_quantity(_safe_float(getattr(target, "target_shares", 0.0), 0.0)),
                "target_weight": float(getattr(target, "target_weight", 0.0) or 0.0),
                "conviction_score": getattr(target, "conviction_score", None),
                "run_id": run_id or getattr(target, "risk_run_id", None),
            }
        )
    return pd.DataFrame(rows)


def _extract_compare_value(item: object, name: str, default: object = None) -> object:
    if isinstance(item, Mapping):
        return item.get(name, default)
    return getattr(item, name, default)


def _first_present_text(series: pd.Series | None) -> str | None:
    if not isinstance(series, pd.Series):
        return None
    for value in series.tolist():
        if pd.isna(value):
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _first_present_float(series: pd.Series | None) -> float | None:
    if not isinstance(series, pd.Series):
        return None
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    if numeric.empty:
        return None
    return float(numeric.iloc[0])


def _aggregate_trade_compare_frame(frame: pd.DataFrame | None) -> pd.DataFrame:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return pd.DataFrame(columns=["symbol", "decision", "approved_shares", "avg_fill_price", "detail_reason", "detail_date", "pnl", "run_id"])
    normalized = frame.copy()
    if "symbol" in normalized.columns:
        normalized["symbol"] = normalized["symbol"].astype(str).str.strip().str.upper()
    if "side" in normalized.columns:
        normalized_side = normalized["side"].astype(str).str.strip().str.upper()
        inferred_decision = normalized_side.map({"BUY": "BUY", "SELL": "SELL", "LONG": "BUY", "SHORT": "SELL"})
    else:
        inferred_decision = pd.Series(pd.NA, index=normalized.index, dtype="object")
    if "decision" not in normalized.columns:
        normalized["decision"] = inferred_decision
    else:
        normalized["decision"] = normalized["decision"].where(normalized["decision"].notna(), inferred_decision)
    if "approved_shares" not in normalized.columns:
        quantity_source = None
        for candidate_column in ("filled_qty", "closed_qty", "target_shares", "shares"):
            if candidate_column in normalized.columns:
                quantity_source = candidate_column
                break
        if quantity_source is not None:
            normalized["approved_shares"] = normalized[quantity_source]
        else:
            normalized["approved_shares"] = 0.0
    normalized["approved_shares"] = pd.to_numeric(normalized["approved_shares"], errors="coerce").fillna(0.0)
    if "avg_fill_price" in normalized.columns:
        normalized["avg_fill_price"] = pd.to_numeric(normalized["avg_fill_price"], errors="coerce")
    else:
        normalized["avg_fill_price"] = pd.NA
    if "pnl" in normalized.columns:
        normalized["pnl"] = pd.to_numeric(normalized["pnl"], errors="coerce")
    else:
        normalized["pnl"] = pd.NA
    if "detail_reason" not in normalized.columns:
        normalized["detail_reason"] = None
    if "detail_date" not in normalized.columns:
        normalized["detail_date"] = None
    if "run_id" not in normalized.columns:
        normalized["run_id"] = None
    rows: list[dict[str, object]] = []
    for symbol, group in normalized.groupby("symbol", sort=False):
        total_qty = float(pd.to_numeric(group["approved_shares"], errors="coerce").fillna(0.0).sum())
        price_series = pd.to_numeric(group.get("avg_fill_price"), errors="coerce")
        weighted_price = None
        valid_prices = price_series.dropna()
        if not valid_prices.empty:
            qty_weights = pd.to_numeric(group.loc[valid_prices.index, "approved_shares"], errors="coerce").fillna(0.0)
            positive_weight = float(qty_weights.sum())
            if positive_weight > 0:
                weighted_price = float((valid_prices * qty_weights).sum() / positive_weight)
            else:
                weighted_price = float(valid_prices.mean())
        pnl_series = pd.to_numeric(group.get("pnl"), errors="coerce")
        pnl_value = float(pnl_series.dropna().sum()) if isinstance(pnl_series, pd.Series) and not pnl_series.dropna().empty else None
        detail_dates = pd.to_datetime(group.get("detail_date"), errors="coerce") if "detail_date" in group.columns else pd.Series(dtype="datetime64[ns]")
        detail_date = None
        if isinstance(detail_dates, pd.Series) and not detail_dates.dropna().empty:
            detail_date = pd.Timestamp(detail_dates.dropna().max()).date().isoformat()
        rows.append(
            {
                "symbol": symbol,
                "decision": _first_present_text(group.get("decision")),
                "approved_shares": total_qty,
                "avg_fill_price": weighted_price,
                "detail_reason": _first_present_text(group.get("detail_reason")),
                "detail_date": detail_date,
                "pnl": pnl_value,
                "run_id": _first_present_text(group.get("run_id")),
            }
        )
    return pd.DataFrame(rows)


def _execution_fills_to_compare_frame(fills: Sequence[object], *, run_id: str | None = None) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for fill in fills:
        symbol = str(_extract_compare_value(fill, "symbol", "") or "").strip().upper()
        if not symbol:
            continue
        filled_qty = float(_extract_compare_value(fill, "filled_qty", 0.0) or 0.0)
        rows.append(
            {
                "symbol": symbol,
                "decision": "BUY" if filled_qty >= 0 else "SELL",
                "approved_shares": abs(filled_qty),
                "avg_fill_price": _extract_compare_value(fill, "avg_fill_price"),
                "detail_reason": _extract_compare_value(fill, "intent_role"),
                "detail_date": _extract_compare_value(fill, "fill_timestamp"),
                "run_id": run_id or _extract_compare_value(fill, "run_id") or _extract_compare_value(fill, "exec_run_id"),
            }
        )
    return _aggregate_trade_compare_frame(pd.DataFrame(rows))


def _exit_signals_to_compare_frame(signals_df: pd.DataFrame, *, execution_date: pd.Timestamp) -> pd.DataFrame:
    if not isinstance(signals_df, pd.DataFrame) or signals_df.empty:
        return pd.DataFrame(columns=["symbol", "decision", "approved_shares", "avg_fill_price", "detail_reason", "detail_date", "run_id"])
    frame = signals_df.copy()
    if "execution_date" not in frame.columns:
        return pd.DataFrame(columns=["symbol", "decision", "approved_shares", "avg_fill_price", "detail_reason", "detail_date", "run_id"])
    frame["execution_date"] = pd.to_datetime(frame["execution_date"], errors="coerce").dt.normalize()
    filtered = frame.loc[frame["execution_date"] == execution_date].copy()
    if filtered.empty or "replay_exit_price" not in filtered.columns:
        return pd.DataFrame(columns=["symbol", "decision", "approved_shares", "avg_fill_price", "detail_reason", "detail_date", "run_id"])
    filtered = filtered.loc[pd.to_numeric(filtered["replay_exit_price"], errors="coerce").notna()].copy()
    if filtered.empty:
        return pd.DataFrame(columns=["symbol", "decision", "approved_shares", "avg_fill_price", "detail_reason", "detail_date", "run_id"])
    rows = pd.DataFrame(
        {
            "symbol": filtered.get("symbol"),
            "decision": "SELL",
            "approved_shares": pd.to_numeric(filtered.get("filled_qty", filtered.get("approved_shares", 0.0)), errors="coerce").fillna(0.0).abs(),
            "avg_fill_price": pd.to_numeric(filtered.get("replay_exit_price"), errors="coerce"),
            "detail_reason": filtered.get("replay_exit_reason"),
            "detail_date": filtered.get("replay_exit_date"),
            "run_id": "backtest_exit_lifecycle",
        }
    )
    return _aggregate_trade_compare_frame(rows)


def _position_lots_to_exit_compare_frame(lots_df: pd.DataFrame | None) -> pd.DataFrame:
    if not isinstance(lots_df, pd.DataFrame) or lots_df.empty:
        return pd.DataFrame(columns=["symbol", "decision", "approved_shares", "avg_fill_price", "detail_reason", "detail_date", "run_id"])
    frame = lots_df.copy()
    closed_qty = pd.to_numeric(frame.get("closed_qty"), errors="coerce").fillna(0.0)
    exit_price = pd.to_numeric(frame.get("exit_price"), errors="coerce")
    filtered = frame.loc[(closed_qty > 0) & exit_price.notna()].copy()
    if filtered.empty:
        return pd.DataFrame(columns=["symbol", "decision", "approved_shares", "avg_fill_price", "detail_reason", "detail_date", "run_id"])
    rows = pd.DataFrame(
        {
            "symbol": filtered.get("symbol"),
            "decision": "SELL",
            "approved_shares": pd.to_numeric(filtered.get("closed_qty"), errors="coerce").fillna(0.0),
            "avg_fill_price": pd.to_numeric(filtered.get("exit_price"), errors="coerce"),
            "detail_reason": filtered.get("close_intent_role"),
            "detail_date": filtered.get("closed_at"),
            "run_id": filtered.get("run_id"),
        }
    )
    return _aggregate_trade_compare_frame(rows)


def _exit_signals_to_pnl_frame(signals_df: pd.DataFrame, *, execution_date: pd.Timestamp) -> pd.DataFrame:
    if not isinstance(signals_df, pd.DataFrame) or signals_df.empty:
        return pd.DataFrame(columns=["symbol", "approved_shares", "pnl", "detail_date", "run_id"])
    frame = signals_df.copy()
    if "execution_date" not in frame.columns:
        return pd.DataFrame(columns=["symbol", "approved_shares", "pnl", "detail_date", "run_id"])
    frame["execution_date"] = pd.to_datetime(frame["execution_date"], errors="coerce").dt.normalize()
    filtered = frame.loc[frame["execution_date"] == execution_date].copy()
    if filtered.empty:
        return pd.DataFrame(columns=["symbol", "approved_shares", "pnl", "detail_date", "run_id"])
    exit_price = pd.to_numeric(filtered.get("replay_exit_price"), errors="coerce")
    fill_price = pd.to_numeric(filtered.get("fill_price"), errors="coerce")
    filled_qty = pd.to_numeric(filtered.get("filled_qty", filtered.get("approved_shares", 0.0)), errors="coerce").fillna(0.0)
    filtered = filtered.loc[exit_price.notna() & fill_price.notna() & (filled_qty != 0)].copy()
    if filtered.empty:
        return pd.DataFrame(columns=["symbol", "approved_shares", "pnl", "detail_date", "run_id"])
    rows = pd.DataFrame(
        {
            "symbol": filtered.get("symbol"),
            "approved_shares": filled_qty.loc[filtered.index].abs(),
            "pnl": (exit_price.loc[filtered.index] - fill_price.loc[filtered.index]) * filled_qty.loc[filtered.index],
            "detail_date": filtered.get("replay_exit_date"),
            "run_id": "backtest_exit_lifecycle",
        }
    )
    return _aggregate_trade_compare_frame(rows)


def _position_lots_to_pnl_frame(lots_df: pd.DataFrame | None) -> pd.DataFrame:
    if not isinstance(lots_df, pd.DataFrame) or lots_df.empty:
        return pd.DataFrame(columns=["symbol", "approved_shares", "pnl", "detail_date", "run_id"])
    frame = lots_df.copy()
    closed_qty = pd.to_numeric(frame.get("closed_qty"), errors="coerce").fillna(0.0)
    pnl_series = pd.to_numeric(frame.get("realized_pnl"), errors="coerce")
    filtered = frame.loc[(closed_qty > 0) & pnl_series.notna()].copy()
    if filtered.empty:
        return pd.DataFrame(columns=["symbol", "approved_shares", "pnl", "detail_date", "run_id"])
    rows = pd.DataFrame(
        {
            "symbol": filtered.get("symbol"),
            "approved_shares": pd.to_numeric(filtered.get("closed_qty"), errors="coerce").fillna(0.0),
            "pnl": pd.to_numeric(filtered.get("realized_pnl"), errors="coerce"),
            "detail_date": filtered.get("closed_at"),
            "run_id": filtered.get("run_id"),
        }
    )
    return _aggregate_trade_compare_frame(rows)


def _qty_within_compare_tolerance(live_qty: float, replay_qty: float, *, pct: float = 0.05, abs_: float = 1.0) -> bool:
    diff = abs(float(live_qty) - float(replay_qty))
    if diff <= abs_:
        return True
    base = max(abs(float(live_qty)), abs(float(replay_qty)), 1.0)
    return (diff / base) <= pct


def _status_for_trade_section(*, live_available: bool, replay_available: bool, divergent: bool) -> str:
    if not live_available and not replay_available:
        return "disabled"
    if not live_available:
        return "missing_live"
    if not replay_available:
        return "missing_replay"
    return "diverged" if divergent else "aligned"


def _summarize_trade_lifecycle_section(
    *,
    component: str,
    live_df: pd.DataFrame,
    replay_df: pd.DataFrame,
    live_available: bool,
    comparison_basis: str | None = None,
    price_tolerance_bps: float = 25.0,
    compare_reason: bool = False,
) -> dict[str, object]:
    live_idx = {str(row.get("symbol")): row for row in _aggregate_trade_compare_frame(live_df).to_dict("records") if str(row.get("symbol") or "").strip()}
    replay_idx = {str(row.get("symbol")): row for row in _aggregate_trade_compare_frame(replay_df).to_dict("records") if str(row.get("symbol") or "").strip()}
    union_symbols = sorted(set(live_idx) | set(replay_idx))
    divergence_kind_counts: dict[str, int] = {}
    top_divergences: list[dict[str, object]] = []
    price_deltas: list[float] = []
    n_matched = 0
    n_divergent = 0
    for symbol in union_symbols:
        live_row = live_idx.get(symbol)
        replay_row = replay_idx.get(symbol)
        divergence_kind = "match"
        live_price = float(live_row.get("avg_fill_price") or 0.0) if live_row is not None and live_row.get("avg_fill_price") is not None else None
        replay_price = float(replay_row.get("avg_fill_price") or 0.0) if replay_row is not None and replay_row.get("avg_fill_price") is not None else None
        live_qty = float(live_row.get("approved_shares") or 0.0) if live_row is not None else 0.0
        replay_qty = float(replay_row.get("approved_shares") or 0.0) if replay_row is not None else 0.0
        if live_row is None:
            divergence_kind = "missing_live"
        elif replay_row is None:
            divergence_kind = "missing_replay"
        elif str(live_row.get("decision") or "").upper() != str(replay_row.get("decision") or "").upper():
            divergence_kind = "action_mismatch"
        elif not _qty_within_compare_tolerance(live_qty, replay_qty):
            divergence_kind = "qty_mismatch"
        elif compare_reason and str(live_row.get("detail_reason") or "").strip().lower() != str(replay_row.get("detail_reason") or "").strip().lower():
            divergence_kind = "reason_mismatch"
        elif live_price is not None and replay_price is not None:
            base = max(abs(live_price), abs(replay_price), 1e-9)
            delta_bps = abs(live_price - replay_price) / base * 10000.0
            price_deltas.append(delta_bps)
            if delta_bps > price_tolerance_bps:
                divergence_kind = "price_mismatch"
        if divergence_kind == "match":
            n_matched += 1
            continue
        n_divergent += 1
        divergence_kind_counts[divergence_kind] = divergence_kind_counts.get(divergence_kind, 0) + 1
        if len(top_divergences) < 5:
            top_divergences.append(
                {
                    "component": component,
                    "symbol": symbol,
                    "divergence_kind": divergence_kind,
                    "live_qty": live_qty,
                    "replay_qty": replay_qty,
                    "live_price": live_price,
                    "replay_price": replay_price,
                    "live_reason": live_row.get("detail_reason") if live_row is not None else None,
                    "replay_reason": replay_row.get("detail_reason") if replay_row is not None else None,
                    "live_date": live_row.get("detail_date") if live_row is not None else None,
                    "replay_date": replay_row.get("detail_date") if replay_row is not None else None,
                }
            )
    divergence_score = (n_divergent / len(union_symbols)) if union_symbols else 0.0
    replay_available = bool(replay_idx)
    status = _status_for_trade_section(live_available=live_available, replay_available=replay_available, divergent=n_divergent > 0)
    payload: dict[str, object] = {
        "component": component,
        "status": status,
        "live_available": bool(live_available),
        "replay_available": replay_available,
        "comparable": bool(live_available and replay_available),
        "n_symbols_live": len(live_idx),
        "n_symbols_replay": len(replay_idx),
        "n_matched": n_matched,
        "n_divergent": n_divergent,
        "divergence_score": round(float(divergence_score), 6),
        "alignment_score": round(float(1.0 - divergence_score), 6) if live_available and replay_available else 0.0,
        "live_run_id": _first_present_text(_aggregate_trade_compare_frame(live_df).get("run_id")),
        "replay_run_id": _first_present_text(_aggregate_trade_compare_frame(replay_df).get("run_id")),
        "divergence_kind_counts": divergence_kind_counts,
        "top_divergences": top_divergences,
        "mean_price_delta_bps": round(float(sum(price_deltas) / len(price_deltas)), 6) if price_deltas else 0.0,
        "max_price_delta_bps": round(float(max(price_deltas)), 6) if price_deltas else 0.0,
    }
    if comparison_basis:
        payload["comparison_basis"] = comparison_basis
    return payload


def _summarize_pnl_section(
    *,
    live_df: pd.DataFrame,
    replay_df: pd.DataFrame,
    live_available: bool,
    comparison_basis: str | None = None,
    pnl_tolerance_abs: float = 5.0,
    pnl_tolerance_pct: float = 0.10,
) -> dict[str, object]:
    live_idx = {str(row.get("symbol")): row for row in _aggregate_trade_compare_frame(live_df).to_dict("records") if str(row.get("symbol") or "").strip()}
    replay_idx = {str(row.get("symbol")): row for row in _aggregate_trade_compare_frame(replay_df).to_dict("records") if str(row.get("symbol") or "").strip()}
    union_symbols = sorted(set(live_idx) | set(replay_idx))
    divergence_kind_counts: dict[str, int] = {}
    top_divergences: list[dict[str, object]] = []
    n_matched = 0
    n_divergent = 0
    for symbol in union_symbols:
        live_row = live_idx.get(symbol)
        replay_row = replay_idx.get(symbol)
        divergence_kind = "match"
        live_pnl = float(live_row.get("pnl") or 0.0) if live_row is not None else 0.0
        replay_pnl = float(replay_row.get("pnl") or 0.0) if replay_row is not None else 0.0
        live_qty = float(live_row.get("approved_shares") or 0.0) if live_row is not None else 0.0
        replay_qty = float(replay_row.get("approved_shares") or 0.0) if replay_row is not None else 0.0
        if live_row is None:
            divergence_kind = "missing_live"
        elif replay_row is None:
            divergence_kind = "missing_replay"
        elif not _qty_within_compare_tolerance(live_qty, replay_qty):
            divergence_kind = "qty_mismatch"
        else:
            diff = abs(live_pnl - replay_pnl)
            base = max(abs(live_pnl), abs(replay_pnl), 1.0)
            if diff > pnl_tolerance_abs and (diff / base) > pnl_tolerance_pct:
                divergence_kind = "pnl_mismatch"
        if divergence_kind == "match":
            n_matched += 1
            continue
        n_divergent += 1
        divergence_kind_counts[divergence_kind] = divergence_kind_counts.get(divergence_kind, 0) + 1
        if len(top_divergences) < 5:
            top_divergences.append(
                {
                    "component": "pnl",
                    "symbol": symbol,
                    "divergence_kind": divergence_kind,
                    "live_pnl": live_pnl,
                    "replay_pnl": replay_pnl,
                    "live_qty": live_qty,
                    "replay_qty": replay_qty,
                }
            )
    divergence_score = (n_divergent / len(union_symbols)) if union_symbols else 0.0
    replay_available = bool(replay_idx)
    status = _status_for_trade_section(live_available=live_available, replay_available=replay_available, divergent=n_divergent > 0)
    total_live_pnl = float(sum(float(row.get("pnl") or 0.0) for row in live_idx.values()))
    total_replay_pnl = float(sum(float(row.get("pnl") or 0.0) for row in replay_idx.values()))
    payload: dict[str, object] = {
        "component": "pnl",
        "status": status,
        "live_available": bool(live_available),
        "replay_available": replay_available,
        "comparable": bool(live_available and replay_available),
        "n_symbols_live": len(live_idx),
        "n_symbols_replay": len(replay_idx),
        "n_matched": n_matched,
        "n_divergent": n_divergent,
        "divergence_score": round(float(divergence_score), 6),
        "alignment_score": round(float(1.0 - divergence_score), 6) if live_available and replay_available else 0.0,
        "live_run_id": _first_present_text(_aggregate_trade_compare_frame(live_df).get("run_id")),
        "replay_run_id": _first_present_text(_aggregate_trade_compare_frame(replay_df).get("run_id")),
        "realized_pnl_live": round(total_live_pnl, 6),
        "realized_pnl_replay": round(total_replay_pnl, 6),
        "realized_pnl_gap": round(total_live_pnl - total_replay_pnl, 6),
        "divergence_kind_counts": divergence_kind_counts,
        "top_divergences": top_divergences,
    }
    if comparison_basis:
        payload["comparison_basis"] = comparison_basis
    return payload


def _build_candidate_live_compare_section(
    *,
    research_selected_symbols: Sequence[str],
    live_candidate_symbols: Sequence[str],
    live_available: bool,
) -> dict[str, object]:
    research_set = {str(symbol).strip().upper() for symbol in research_selected_symbols if str(symbol or "").strip()}
    live_set = {str(symbol).strip().upper() for symbol in live_candidate_symbols if str(symbol or "").strip()}
    union = sorted(research_set | live_set)
    intersection = sorted(research_set & live_set)
    research_only = sorted(research_set - live_set)
    live_only = sorted(live_set - research_set)
    alignment_score = (len(intersection) / len(union)) if union else 1.0
    status = "missing_live"
    if live_available:
        status = "aligned" if not research_only and not live_only else "diverged"
    top_divergences = [
        {
            "component": "candidates",
            "symbol": symbol,
            "divergence_kind": "missing_live_candidate",
        }
        for symbol in research_only[:5]
    ] + [
        {
            "component": "candidates",
            "symbol": symbol,
            "divergence_kind": "unexpected_live_candidate",
        }
        for symbol in live_only[:5]
    ]
    return {
        "component": "candidates",
        "status": status,
        "live_available": bool(live_available),
        "research_selected_count": len(research_set),
        "live_candidate_count": len(live_set),
        "intersection_count": len(intersection),
        "alignment_score": round(float(alignment_score), 6),
        "research_only_symbols": research_only,
        "live_only_symbols": live_only,
        "top_divergences": top_divergences,
    }


def _summarize_parity_section(
    *,
    component: str,
    live_df: pd.DataFrame,
    replay_df: pd.DataFrame,
    trade_date: pd.Timestamp,
    account_id: str,
    live_available: bool,
    comparison_basis: str | None = None,
) -> dict[str, object]:
    from backtesting.parity import compare_decisions

    report = compare_decisions(
        _normalize_compare_frame(live_df),
        _normalize_compare_frame(replay_df),
        trade_date=trade_date.date(),
        account_id=account_id,
    )
    divergence_kind_counts: dict[str, int] = {}
    top_divergences: list[dict[str, object]] = []
    for row in report.rows:
        if row.divergence_kind == "match":
            continue
        divergence_kind_counts[row.divergence_kind] = divergence_kind_counts.get(row.divergence_kind, 0) + 1
        if len(top_divergences) < 5:
            top_divergences.append(
                {
                    "component": component,
                    "symbol": row.symbol,
                    "divergence_kind": row.divergence_kind,
                    "live_decision": row.live_decision,
                    "replay_decision": row.replay_decision,
                    "live_qty": row.live_qty,
                    "replay_qty": row.replay_qty,
                }
            )
    status = "missing_live"
    if live_available:
        status = "aligned" if report.n_divergent == 0 else "diverged"
    payload: dict[str, object] = {
        "component": component,
        "status": status,
        "live_available": bool(live_available),
        "n_symbols_live": int(report.n_symbols_live),
        "n_symbols_replay": int(report.n_symbols_replay),
        "n_matched": int(report.n_matched),
        "n_divergent": int(report.n_divergent),
        "divergence_score": round(float(report.divergence_score), 6),
        "alignment_score": round(float(1.0 - report.divergence_score), 6),
        "live_run_id": report.live_run_id,
        "replay_run_id": report.replay_run_id,
        "divergence_kind_counts": divergence_kind_counts,
        "top_divergences": top_divergences,
    }
    if comparison_basis:
        payload["comparison_basis"] = comparison_basis
    return payload


def _collect_compare_session_dates(
    *,
    fidelity_manifest: Mapping[str, Any],
    research_signals_df: pd.DataFrame,
    risk_entries: Sequence[object],
    live_risk_decisions: Mapping[str, pd.DataFrame],
    live_portfolio_targets: Mapping[str, Sequence[object]],
    live_execution_targets: Mapping[str, Sequence[object]],
) -> list[pd.Timestamp]:
    dates: set[pd.Timestamp] = set()
    if isinstance(research_signals_df, pd.DataFrame) and not research_signals_df.empty and "trade_date" in research_signals_df.columns:
        dates.update(pd.DatetimeIndex(_normalize_trade_date_series(research_signals_df).dropna().tolist()))
    for entry in risk_entries:
        snapshot_date = getattr(entry, "score_snapshot_date", None)
        if snapshot_date is None:
            continue
        try:
            dates.add(pd.Timestamp(snapshot_date).normalize())
        except Exception:
            continue
    for mapping in (live_risk_decisions, live_portfolio_targets, live_execution_targets):
        if not isinstance(mapping, Mapping):
            continue
        for raw_key in mapping:
            try:
                dates.add(pd.Timestamp(str(raw_key)).normalize())
            except Exception:
                continue
    return sorted(dates)


def _build_compare_to_live_markdown(summary: Mapping[str, Any]) -> str:
    global_scores = summary.get("global_scores", {}) if isinstance(summary.get("global_scores", {}), Mapping) else {}
    top_divergences = summary.get("top_divergences", []) if isinstance(summary.get("top_divergences", []), Sequence) and not isinstance(summary.get("top_divergences", []), (str, bytes)) else []
    lines = [
        "# Compare-to-live professionnel",
        "",
        f"- Account: {summary.get('account_id') or 'default'}",
        f"- Fenêtre: {summary.get('requested_window', {}).get('start_date') if isinstance(summary.get('requested_window', {}), Mapping) else '—'} → {summary.get('requested_window', {}).get('end_date') if isinstance(summary.get('requested_window', {}), Mapping) else '—'}",
        f"- Séances comparées: {summary.get('session_count', 0)}",
        f"- Séances avec live exploitable: {summary.get('live_session_count', 0)}",
        f"- Score global: {global_scores.get('fidelity_score', 0.0):.3f}" if isinstance(global_scores.get('fidelity_score'), (int, float)) else "- Score global: —",
        "",
        "## Scores par niveau",
    ]
    for key in (
        "candidate_alignment_score",
        "risk_alignment_score",
        "portfolio_alignment_score",
        "execution_alignment_score",
        "fills_alignment_score",
        "exits_alignment_score",
        "pnl_alignment_score",
    ):
        value = global_scores.get(key)
        if isinstance(value, (int, float)):
            lines.append(f"- {key}: {float(value):.3f}")
    lines.append("")
    lines.append("## Top divergences")
    if top_divergences:
        for item in top_divergences[:10]:
            if not isinstance(item, Mapping):
                continue
            lines.append(
                "- "
                f"{item.get('trade_date', '—')} | {item.get('component', 'unknown')} | "
                f"{item.get('symbol', '—')} | {item.get('divergence_kind', 'unknown')}"
            )
    else:
        lines.append("- Aucune divergence majeure détectée sur les sections comparables.")
    return "\n".join(lines) + "\n"


def build_compare_to_live_summary(
    *,
    fidelity_manifest: Mapping[str, Any],
    research_signals_df: pd.DataFrame,
    risk_entries: Sequence[object],
    execution_targets: Sequence[object],
    execution_fills: Sequence[object] = (),
    exit_signals_df: pd.DataFrame | None = None,
    live_risk_decisions: Mapping[str, pd.DataFrame] | None = None,
    live_portfolio_targets: Mapping[str, Sequence[object]] | None = None,
    live_execution_targets: Mapping[str, Sequence[object]] | None = None,
    live_execution_fills: Mapping[str, pd.DataFrame] | None = None,
    live_position_lots: Mapping[str, pd.DataFrame] | None = None,
    live_compare_context: Mapping[str, Mapping[str, Any]] | None = None,
    account_id: str = "default",
    phase2_mode: str = "off",
) -> dict[str, Any]:
    normalized_live_risk = {
        str(key): _normalize_compare_frame(value)
        for key, value in (live_risk_decisions or {}).items()
        if isinstance(value, pd.DataFrame)
    }
    normalized_live_portfolio = {
        str(key): list(value)
        for key, value in (live_portfolio_targets or {}).items()
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes))
    }
    normalized_live_execution = {
        str(key): list(value)
        for key, value in (live_execution_targets or {}).items()
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes))
    }
    normalized_live_execution_fills = {
        str(key): _aggregate_trade_compare_frame(value)
        for key, value in (live_execution_fills or {}).items()
        if isinstance(value, pd.DataFrame)
    }
    normalized_live_position_lots = {
        str(key): value.copy()
        for key, value in (live_position_lots or {}).items()
        if isinstance(value, pd.DataFrame)
    }

    session_dates = _collect_compare_session_dates(
        fidelity_manifest=fidelity_manifest,
        research_signals_df=research_signals_df,
        risk_entries=risk_entries,
        live_risk_decisions=normalized_live_risk,
        live_portfolio_targets=normalized_live_portfolio,
        live_execution_targets=normalized_live_execution,
    )

    sessions: list[dict[str, Any]] = []
    all_top_divergences: list[dict[str, object]] = []
    score_accumulator: dict[str, list[float]] = {
        "candidates": [],
        "risk": [],
        "portfolio": [],
        "execution": [],
        "fills": [],
        "exits": [],
        "pnl": [],
    }
    for trade_date in session_dates:
        trade_date_key = pd.Timestamp(trade_date).date().isoformat()
        live_risk_day = normalized_live_risk.get(trade_date_key, pd.DataFrame())
        live_portfolio_day = _execution_targets_to_compare_frame(
            normalized_live_portfolio.get(trade_date_key, []),
            run_id=f"live_portfolio:{trade_date_key}",
        )
        live_execution_day = _execution_targets_to_compare_frame(
            normalized_live_execution.get(trade_date_key, []),
            run_id=f"live_execution:{trade_date_key}",
        )
        live_execution_fills_day = _aggregate_trade_compare_frame(normalized_live_execution_fills.get(trade_date_key, pd.DataFrame()))
        live_position_lots_day = normalized_live_position_lots.get(trade_date_key, pd.DataFrame())

        research_selected_symbols = _research_selected_symbols_for_date(research_signals_df, trade_date)
        live_candidate_symbols = _normalize_live_buy_symbol_set(live_risk_day)
        risk_day = _portfolio_entries_to_compare_frame(
            [entry for entry in risk_entries if _normalize_timestamp_value(getattr(entry, "score_snapshot_date", pd.NaT)) == trade_date],
            run_id="backtest_risk",
        )
        execution_day = _execution_targets_to_compare_frame(
            [target for target in execution_targets if _normalize_timestamp_value(getattr(target, "trade_date", pd.NaT)) == trade_date],
            run_id="backtest_execution",
        )
        replay_fills_day = _execution_fills_to_compare_frame(
            [fill for fill in execution_fills if _normalize_timestamp_value(_extract_compare_value(fill, "fill_timestamp", pd.NaT)) == trade_date],
            run_id="backtest_execution_fills",
        )
        replay_exits_day = _exit_signals_to_compare_frame(
            exit_signals_df if isinstance(exit_signals_df, pd.DataFrame) else pd.DataFrame(),
            execution_date=trade_date,
        )
        replay_pnl_day = _exit_signals_to_pnl_frame(
            exit_signals_df if isinstance(exit_signals_df, pd.DataFrame) else pd.DataFrame(),
            execution_date=trade_date,
        )
        live_exits_day = _position_lots_to_exit_compare_frame(live_position_lots_day)
        live_pnl_day = _position_lots_to_pnl_frame(live_position_lots_day)
        portfolio_day = _portfolio_entries_to_compare_frame(
            [
                entry
                for entry in risk_entries
                if _normalize_timestamp_value(getattr(entry, "score_snapshot_date", pd.NaT)) == trade_date
                and normalize_share_quantity(_safe_float(getattr(entry, "approved_shares", 0.0), 0.0)) > 0
            ],
            run_id="backtest_portfolio",
        )

        candidate_section = _build_candidate_live_compare_section(
            research_selected_symbols=research_selected_symbols,
            live_candidate_symbols=live_candidate_symbols,
            live_available=bool(not live_risk_day.empty),
        )
        risk_section = _summarize_parity_section(
            component="risk_decisions",
            live_df=live_risk_day,
            replay_df=risk_day,
            trade_date=trade_date,
            account_id=account_id,
            live_available=bool(not live_risk_day.empty),
        )
        portfolio_section = _summarize_parity_section(
            component="portfolio_targets",
            live_df=live_portfolio_day,
            replay_df=portfolio_day,
            trade_date=trade_date,
            account_id=account_id,
            live_available=bool(not live_portfolio_day.empty),
            comparison_basis="risk_targets_vs_live_portfolio_targets",
        )
        execution_section = _summarize_parity_section(
            component="execution_targets",
            live_df=live_execution_day,
            replay_df=execution_day,
            trade_date=trade_date,
            account_id=account_id,
            live_available=bool(not live_execution_day.empty),
            comparison_basis="execution_targets_snapshot",
        )
        fills_section = _summarize_trade_lifecycle_section(
            component="fills",
            live_df=live_execution_fills_day,
            replay_df=replay_fills_day,
            live_available=bool(not live_execution_fills_day.empty),
            comparison_basis="execution_broker_fills_by_exec_run",
        )
        exits_section = _summarize_trade_lifecycle_section(
            component="exits",
            live_df=live_exits_day,
            replay_df=replay_exits_day,
            live_available=bool(not live_exits_day.empty),
            comparison_basis="closed_lots_by_open_exec_run",
            compare_reason=True,
        )
        pnl_section = _summarize_pnl_section(
            live_df=live_pnl_day,
            replay_df=replay_pnl_day,
            live_available=bool(not live_pnl_day.empty),
            comparison_basis="realized_pnl_from_closed_lots",
        )

        session_scores = [
            float(candidate_section.get("alignment_score", 0.0)) if bool(candidate_section.get("live_available", False)) else None,
            float(risk_section.get("alignment_score", 0.0)) if bool(risk_section.get("live_available", False)) else None,
            float(portfolio_section.get("alignment_score", 0.0)) if bool(portfolio_section.get("live_available", False)) else None,
            float(execution_section.get("alignment_score", 0.0)) if bool(execution_section.get("live_available", False)) else None,
            float(fills_section.get("alignment_score", 0.0)) if bool(fills_section.get("comparable", False)) else None,
            float(exits_section.get("alignment_score", 0.0)) if bool(exits_section.get("comparable", False)) else None,
            float(pnl_section.get("alignment_score", 0.0)) if bool(pnl_section.get("comparable", False)) else None,
        ]
        comparable_scores = [score for score in session_scores if isinstance(score, float)]
        fidelity_score = (sum(comparable_scores) / len(comparable_scores)) if comparable_scores else 0.0

        session_top_divergences: list[dict[str, object]] = []
        for section in (candidate_section, risk_section, portfolio_section, execution_section, fills_section, exits_section, pnl_section):
            top_items = section.get("top_divergences", [])
            if not isinstance(top_items, Sequence) or isinstance(top_items, (str, bytes)):
                continue
            for item in top_items[:3]:
                if not isinstance(item, Mapping):
                    continue
                enriched = {"trade_date": trade_date_key, **dict(item)}
                session_top_divergences.append(enriched)
                all_top_divergences.append(enriched)

        if bool(candidate_section.get("live_available", False)):
            score_accumulator["candidates"].append(float(candidate_section.get("alignment_score", 0.0)))
        if bool(risk_section.get("live_available", False)):
            score_accumulator["risk"].append(float(risk_section.get("alignment_score", 0.0)))
        if bool(portfolio_section.get("live_available", False)):
            score_accumulator["portfolio"].append(float(portfolio_section.get("alignment_score", 0.0)))
        if bool(execution_section.get("live_available", False)):
            score_accumulator["execution"].append(float(execution_section.get("alignment_score", 0.0)))
        if bool(fills_section.get("comparable", False)):
            score_accumulator["fills"].append(float(fills_section.get("alignment_score", 0.0)))
        if bool(exits_section.get("comparable", False)):
            score_accumulator["exits"].append(float(exits_section.get("alignment_score", 0.0)))
        if bool(pnl_section.get("comparable", False)):
            score_accumulator["pnl"].append(float(pnl_section.get("alignment_score", 0.0)))

        sessions.append(
            {
                "trade_date": trade_date_key,
                "matching_context": dict(live_compare_context.get(trade_date_key, {})) if isinstance(live_compare_context, Mapping) and isinstance(live_compare_context.get(trade_date_key, {}), Mapping) else {},
                "live_presence": {
                    "risk_decisions": not live_risk_day.empty,
                    "portfolio_targets": not live_portfolio_day.empty,
                    "execution_targets": not live_execution_day.empty,
                    "fills": not live_execution_fills_day.empty,
                    "exits": not live_exits_day.empty,
                    "pnl": not live_pnl_day.empty,
                },
                "counts": {
                    "research_selected": len(research_selected_symbols),
                    "live_candidates": len(live_candidate_symbols),
                    "backtest_risk_rows": len(risk_day),
                    "live_risk_rows": len(live_risk_day),
                    "backtest_portfolio_rows": int(portfolio_section.get("n_symbols_replay", 0)),
                    "live_portfolio_rows": int(portfolio_section.get("n_symbols_live", 0)),
                    "backtest_execution_rows": int(execution_section.get("n_symbols_replay", 0)),
                    "live_execution_rows": int(execution_section.get("n_symbols_live", 0)),
                    "backtest_fill_rows": int(fills_section.get("n_symbols_replay", 0)),
                    "live_fill_rows": int(fills_section.get("n_symbols_live", 0)),
                    "backtest_exit_rows": int(exits_section.get("n_symbols_replay", 0)),
                    "live_exit_rows": int(exits_section.get("n_symbols_live", 0)),
                    "backtest_pnl_rows": int(pnl_section.get("n_symbols_replay", 0)),
                    "live_pnl_rows": int(pnl_section.get("n_symbols_live", 0)),
                },
                "candidate_compare": candidate_section,
                "risk_compare": risk_section,
                "portfolio_compare": portfolio_section,
                "execution_compare": execution_section,
                "fills_compare": fills_section,
                "exits_compare": exits_section,
                "pnl_compare": pnl_section,
                "fidelity_score": round(float(fidelity_score), 6),
                "top_divergences": session_top_divergences[:10],
            }
        )

    candidate_scores = score_accumulator["candidates"]
    risk_scores = score_accumulator["risk"]
    portfolio_scores = score_accumulator["portfolio"]
    execution_scores = score_accumulator["execution"]
    fills_scores = score_accumulator["fills"]
    exits_scores = score_accumulator["exits"]
    pnl_scores = score_accumulator["pnl"]
    # Score de fidélité global pondéré par proximité au fill réel :
    # pnl=4, fills=4, exits=3, execution=3, portfolio=2, risk=2, candidates=1
    _SECTION_WEIGHTS: dict[str, int] = {
        "candidates": 1,
        "risk": 2,
        "portfolio": 2,
        "execution": 3,
        "exits": 3,
        "fills": 4,
        "pnl": 4,
    }
    _avg = lambda scores: round(sum(scores) / len(scores), 6) if scores else None

    def _weighted_fidelity_score(
        per_section: dict[str, list[float]],
        weights: dict[str, int],
    ) -> float:
        total_weight = 0.0
        total_weighted = 0.0
        for key, w in weights.items():
            scores = per_section.get(key, [])
            if scores:
                total_weighted += sum(scores) / len(scores) * w
                total_weight += w
        return round(total_weighted / total_weight, 6) if total_weight > 0 else 0.0

    _per_section: dict[str, list[float]] = {
        "candidates": candidate_scores,
        "risk": risk_scores,
        "portfolio": portfolio_scores,
        "execution": execution_scores,
        "fills": fills_scores,
        "exits": exits_scores,
        "pnl": pnl_scores,
    }
    global_scores = {
        "candidate_alignment_score": _avg(candidate_scores) if candidate_scores else 0.0,
        "risk_alignment_score": _avg(risk_scores) if risk_scores else 0.0,
        "portfolio_alignment_score": _avg(portfolio_scores) if portfolio_scores else 0.0,
        "execution_alignment_score": _avg(execution_scores) if execution_scores else 0.0,
        "fills_alignment_score": _avg(fills_scores) if fills_scores else 0.0,
        "exits_alignment_score": _avg(exits_scores) if exits_scores else 0.0,
        "pnl_alignment_score": _avg(pnl_scores) if pnl_scores else 0.0,
        "fidelity_score": _weighted_fidelity_score(_per_section, _SECTION_WEIGHTS),
        "fidelity_score_method": "weighted_by_proximity_to_fill",
    }
    live_session_count = sum(
        1
        for session in sessions
        if isinstance(session.get("live_presence"), Mapping) and any(bool(value) for value in cast(Mapping[str, object], session.get("live_presence", {})).values())
    )
    top_divergences_sorted = sorted(
        all_top_divergences,
        key=lambda item: (str(item.get("trade_date") or ""), str(item.get("component") or ""), str(item.get("symbol") or "")),
    )
    return {
        "enabled": True,
        "account_id": account_id,
        "engine_mode": fidelity_manifest.get("engine_mode"),
        "phase2_mode": phase2_mode,
        "requested_window": dict(fidelity_manifest.get("requested_window", {})) if isinstance(fidelity_manifest.get("requested_window", {}), Mapping) else {},
        "compare_sections": ["candidates", "risk_decisions", "portfolio_targets", "execution_targets", "fills", "exits", "pnl"],
        "session_count": len(sessions),
        "live_session_count": live_session_count,
        "global_scores": global_scores,
        "top_divergences": top_divergences_sorted[:20],
        "sessions": sessions,
    }


def save_compare_to_live_summary(summary: Mapping[str, Any], output_dir: Path) -> dict[str, Path]:
    """Sauvegarde le rapport compare-to-live en JSON + CSV + Markdown."""
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "compare_to_live_summary.json"
    csv_path = output_dir / "compare_to_live_sessions.csv"
    markdown_path = output_dir / "compare_to_live_summary.md"
    payload = dict(summary)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    sessions = summary.get("sessions", []) if isinstance(summary, Mapping) else []
    rows: list[dict[str, object]] = []
    if isinstance(sessions, Sequence) and not isinstance(sessions, (str, bytes)):
        for session in sessions:
            if not isinstance(session, Mapping):
                continue
            rows.append(
                {
                    "trade_date": session.get("trade_date"),
                    "fidelity_score": session.get("fidelity_score", 0.0),
                    "candidate_status": session.get("candidate_compare", {}).get("status") if isinstance(session.get("candidate_compare"), Mapping) else None,
                    "candidate_alignment_score": session.get("candidate_compare", {}).get("alignment_score") if isinstance(session.get("candidate_compare"), Mapping) else None,
                    "risk_status": session.get("risk_compare", {}).get("status") if isinstance(session.get("risk_compare"), Mapping) else None,
                    "risk_divergence_score": session.get("risk_compare", {}).get("divergence_score") if isinstance(session.get("risk_compare"), Mapping) else None,
                    "portfolio_status": session.get("portfolio_compare", {}).get("status") if isinstance(session.get("portfolio_compare"), Mapping) else None,
                    "portfolio_divergence_score": session.get("portfolio_compare", {}).get("divergence_score") if isinstance(session.get("portfolio_compare"), Mapping) else None,
                    "execution_status": session.get("execution_compare", {}).get("status") if isinstance(session.get("execution_compare"), Mapping) else None,
                    "execution_divergence_score": session.get("execution_compare", {}).get("divergence_score") if isinstance(session.get("execution_compare"), Mapping) else None,
                    "fills_status": session.get("fills_compare", {}).get("status") if isinstance(session.get("fills_compare"), Mapping) else None,
                    "fills_divergence_score": session.get("fills_compare", {}).get("divergence_score") if isinstance(session.get("fills_compare"), Mapping) else None,
                    "exits_status": session.get("exits_compare", {}).get("status") if isinstance(session.get("exits_compare"), Mapping) else None,
                    "exits_divergence_score": session.get("exits_compare", {}).get("divergence_score") if isinstance(session.get("exits_compare"), Mapping) else None,
                    "pnl_status": session.get("pnl_compare", {}).get("status") if isinstance(session.get("pnl_compare"), Mapping) else None,
                    "pnl_divergence_score": session.get("pnl_compare", {}).get("divergence_score") if isinstance(session.get("pnl_compare"), Mapping) else None,
                    "top_divergences": json.dumps(session.get("top_divergences", []), ensure_ascii=False, default=str),
                }
            )
    pd.DataFrame(rows).to_csv(csv_path, index=False)
    markdown_path.write_text(_build_compare_to_live_markdown(summary), encoding="utf-8")
    return {
        "compare_to_live_summary_json": json_path,
        "compare_to_live_sessions_csv": csv_path,
        "compare_to_live_summary_md": markdown_path,
    }


def _normalize_phase_modes_from_payload(*payloads: Mapping[str, Any] | None) -> dict[str, str]:
    phase_modes: dict[str, str] = {}
    for payload in payloads:
        if not isinstance(payload, Mapping):
            continue
        for key, value in payload.items():
            if not str(key).startswith("phase"):
                continue
            if not str(key).endswith("_mode"):
                continue
            text = str(value or "").strip()
            if text:
                phase_modes[str(key)] = text
    return dict(sorted(phase_modes.items()))


def _safe_ratio(numerator: object, denominator: object) -> float:
    base = _safe_int(denominator, 0)
    if base <= 0:
        return 0.0
    return float(_safe_int(numerator, 0)) / float(base)


def _sanitize_baseline_id(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def build_fidelity_baseline_snapshot(
    *,
    fidelity_manifest: Mapping[str, Any],
    replay_diagnostic_summary: Mapping[str, Any] | None = None,
    candidate_target_parity_summary: Mapping[str, Any] | None = None,
    compare_to_live_summary: Mapping[str, Any] | None = None,
    execution_broker_like_summary: Mapping[str, Any] | None = None,
    baseline_id: str | None = None,
) -> dict[str, Any]:
    """Construit un snapshot canonique compact pour la non-régression fidélité."""
    manifest_requested_window = fidelity_manifest.get("requested_window", {})
    requested_window = dict(manifest_requested_window) if isinstance(manifest_requested_window, Mapping) else {}
    manifest_component_status = fidelity_manifest.get("component_status", {})
    component_status = dict(manifest_component_status) if isinstance(manifest_component_status, Mapping) else {}
    execution_component = component_status.get("execution", {}) if isinstance(component_status, Mapping) else {}
    execution_details = execution_component.get("details", {}) if isinstance(execution_component, Mapping) else {}
    compare_global_scores = compare_to_live_summary.get("global_scores", {}) if isinstance(compare_to_live_summary, Mapping) else {}
    broker_semantics = execution_broker_like_summary.get("broker_semantics", {}) if isinstance(execution_broker_like_summary, Mapping) else {}
    broker_status_counts = execution_broker_like_summary.get("order_status_counts", {}) if isinstance(execution_broker_like_summary, Mapping) else {}
    broker_state_counts = execution_broker_like_summary.get("broker_state_counts", {}) if isinstance(execution_broker_like_summary, Mapping) else {}
    phase_modes = _normalize_phase_modes_from_payload(
        cast(Mapping[str, Any], fidelity_manifest.get("modes", {})) if isinstance(fidelity_manifest.get("modes", {}), Mapping) else {},
        cast(Mapping[str, Any], execution_details) if isinstance(execution_details, Mapping) else {},
        cast(Mapping[str, Any], execution_broker_like_summary.get("phase_modes", {})) if isinstance(execution_broker_like_summary, Mapping) else {},
    )
    available_sections = {
        "fidelity_manifest": True,
        "replay_diagnostic_summary": isinstance(replay_diagnostic_summary, Mapping) and bool(replay_diagnostic_summary),
        "candidate_target_parity_summary": isinstance(candidate_target_parity_summary, Mapping) and bool(candidate_target_parity_summary),
        "compare_to_live_summary": isinstance(compare_to_live_summary, Mapping) and bool(compare_to_live_summary),
        "execution_broker_like_summary": isinstance(execution_broker_like_summary, Mapping) and bool(execution_broker_like_summary),
    }
    metrics = {
        "degraded_reason_count": float(len(_normalize_reason_list(fidelity_manifest.get("degraded_reasons", [])))),
        "sentiment_coverage_ratio_after": float(
            cast(Mapping[str, Any], fidelity_manifest.get("coverage", {})).get("sentiment", {}).get("coverage_ratio_after", 1.0)
            if isinstance(cast(Mapping[str, Any], fidelity_manifest.get("coverage", {})).get("sentiment", {}), Mapping)
            else 1.0
        ),
        "ml_coverage_ratio_after": float(
            cast(Mapping[str, Any], fidelity_manifest.get("coverage", {})).get("ml", {}).get("coverage_ratio_after", 1.0)
            if isinstance(cast(Mapping[str, Any], fidelity_manifest.get("coverage", {})).get("ml", {}), Mapping)
            else 1.0
        ),
        "replay_session_count": float(_safe_int(replay_diagnostic_summary.get("session_count", 0) if isinstance(replay_diagnostic_summary, Mapping) else 0)),
        "replay_degraded_session_ratio": _safe_ratio(
            replay_diagnostic_summary.get("degraded_session_count", 0) if isinstance(replay_diagnostic_summary, Mapping) else 0,
            replay_diagnostic_summary.get("session_count", 0) if isinstance(replay_diagnostic_summary, Mapping) else 0,
        ),
        "parity_session_count": float(_safe_int(candidate_target_parity_summary.get("session_count", 0) if isinstance(candidate_target_parity_summary, Mapping) else 0)),
        "parity_diverged_session_ratio": _safe_ratio(
            candidate_target_parity_summary.get("diverged_session_count", 0) if isinstance(candidate_target_parity_summary, Mapping) else 0,
            candidate_target_parity_summary.get("session_count", 0) if isinstance(candidate_target_parity_summary, Mapping) else 0,
        ),
        "compare_live_session_count": float(_safe_int(compare_to_live_summary.get("session_count", 0) if isinstance(compare_to_live_summary, Mapping) else 0)),
        "compare_live_live_session_count": float(_safe_int(compare_to_live_summary.get("live_session_count", 0) if isinstance(compare_to_live_summary, Mapping) else 0)),
        "compare_live_fidelity_score": float(compare_global_scores.get("fidelity_score", 0.0)) if isinstance(compare_global_scores, Mapping) else 0.0,
        "compare_live_candidate_alignment_score": float(compare_global_scores.get("candidate_alignment_score", 0.0)) if isinstance(compare_global_scores, Mapping) else 0.0,
        "compare_live_risk_alignment_score": float(compare_global_scores.get("risk_alignment_score", 0.0)) if isinstance(compare_global_scores, Mapping) else 0.0,
        "compare_live_portfolio_alignment_score": float(compare_global_scores.get("portfolio_alignment_score", 0.0)) if isinstance(compare_global_scores, Mapping) else 0.0,
        "compare_live_execution_alignment_score": float(compare_global_scores.get("execution_alignment_score", 0.0)) if isinstance(compare_global_scores, Mapping) else 0.0,
        "compare_live_fills_alignment_score": float(compare_global_scores.get("fills_alignment_score", 0.0)) if isinstance(compare_global_scores, Mapping) else 0.0,
        "compare_live_exits_alignment_score": float(compare_global_scores.get("exits_alignment_score", 0.0)) if isinstance(compare_global_scores, Mapping) else 0.0,
        "compare_live_pnl_alignment_score": float(compare_global_scores.get("pnl_alignment_score", 0.0)) if isinstance(compare_global_scores, Mapping) else 0.0,
        "broker_order_count": float(_safe_int(execution_broker_like_summary.get("order_count", 0) if isinstance(execution_broker_like_summary, Mapping) else 0)),
        "broker_filled_orders": float(_safe_int(broker_status_counts.get("FILLED", 0) if isinstance(broker_status_counts, Mapping) else 0)),
        "broker_canceled_orders": float(_safe_int(broker_status_counts.get("CANCELED", 0) if isinstance(broker_status_counts, Mapping) else 0)),
        "broker_rejected_orders": float(_safe_int(broker_semantics.get("rejected_orders", 0) if isinstance(broker_semantics, Mapping) else 0)),
        "broker_timed_out_orders": float(_safe_int(broker_semantics.get("timed_out_orders", 0) if isinstance(broker_semantics, Mapping) else 0)),
        "broker_stale_orders": float(_safe_int(broker_state_counts.get("stale", 0) if isinstance(broker_state_counts, Mapping) else 0)),
    }
    return {
        "snapshot_version": 1,
        "baseline_id": _sanitize_baseline_id(baseline_id),
        "engine_mode": fidelity_manifest.get("engine_mode"),
        "requested_window": requested_window,
        "capital_preset_key": fidelity_manifest.get("capital_preset_key"),
        "phase_modes": phase_modes,
        "available_sections": available_sections,
        "metrics": {name: round(float(value), 6) for name, value in metrics.items()},
        "summary": {
            "degraded": bool(fidelity_manifest.get("degraded", False)),
            "degraded_components": list(cast(Mapping[str, Any], fidelity_manifest.get("summary", {})).get("degraded_components", [])) if isinstance(cast(Mapping[str, Any], fidelity_manifest.get("summary", {})).get("degraded_components", []), Sequence) and not isinstance(cast(Mapping[str, Any], fidelity_manifest.get("summary", {})).get("degraded_components", []), (str, bytes)) else [],
            "live_sections_available": [
                section_name
                for section_name in ("compare_to_live_summary", "execution_broker_like_summary")
                if bool(available_sections.get(section_name, False))
            ],
        },
        "sources": {
            "fidelity_manifest": {
                "taxonomy_version": fidelity_manifest.get("taxonomy_version", 1),
                "strict_pit_requested": bool(fidelity_manifest.get("strict_pit_requested", False)),
                "strict_pit_satisfied": bool(fidelity_manifest.get("strict_pit_satisfied", False)),
            },
            "replay_diagnostic_summary": {
                "session_count": _safe_int(replay_diagnostic_summary.get("session_count", 0) if isinstance(replay_diagnostic_summary, Mapping) else 0),
                "degraded_session_count": _safe_int(replay_diagnostic_summary.get("degraded_session_count", 0) if isinstance(replay_diagnostic_summary, Mapping) else 0),
            },
            "candidate_target_parity_summary": {
                "session_count": _safe_int(candidate_target_parity_summary.get("session_count", 0) if isinstance(candidate_target_parity_summary, Mapping) else 0),
                "diverged_session_count": _safe_int(candidate_target_parity_summary.get("diverged_session_count", 0) if isinstance(candidate_target_parity_summary, Mapping) else 0),
            },
            "compare_to_live_summary": {
                "session_count": _safe_int(compare_to_live_summary.get("session_count", 0) if isinstance(compare_to_live_summary, Mapping) else 0),
                "live_session_count": _safe_int(compare_to_live_summary.get("live_session_count", 0) if isinstance(compare_to_live_summary, Mapping) else 0),
                "top_divergence_count": len(compare_to_live_summary.get("top_divergences", [])) if isinstance(compare_to_live_summary, Mapping) and isinstance(compare_to_live_summary.get("top_divergences", []), Sequence) and not isinstance(compare_to_live_summary.get("top_divergences", []), (str, bytes)) else 0,
            },
            "execution_broker_like_summary": {
                "order_count": _safe_int(execution_broker_like_summary.get("order_count", 0) if isinstance(execution_broker_like_summary, Mapping) else 0),
                "session_count": _safe_int(execution_broker_like_summary.get("session_count", 0) if isinstance(execution_broker_like_summary, Mapping) else 0),
            },
        },
    }


def save_fidelity_baseline_snapshot(snapshot: Mapping[str, Any], output_dir: Path) -> Path:
    """Sauvegarde le snapshot canonique d'un run pour promotion/compare future."""
    output_dir.mkdir(parents=True, exist_ok=True)
    filepath = output_dir / "fidelity_baseline_snapshot.json"
    filepath.write_text(json.dumps(dict(snapshot), ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return filepath


def save_fidelity_baseline_promotion_manifest(manifest: Mapping[str, Any], output_dir: Path) -> Path:
    """Sauvegarde le manifeste de promotion associé à une baseline figée."""
    output_dir.mkdir(parents=True, exist_ok=True)
    filepath = output_dir / "promotion_manifest.json"
    filepath.write_text(json.dumps(dict(manifest), ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return filepath


def _load_json_mapping(path: Path) -> dict[str, Any] | None:
    if not path.exists() or not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return dict(payload) if isinstance(payload, Mapping) else None


def _resolve_report_artifacts_dir(source_report_path: Path | None) -> Path | None:
    if source_report_path is None:
        return None
    return source_report_path.parent if source_report_path.name.lower() == "report.json" else source_report_path


def _load_json_artifact_from_report(
    artifacts: Mapping[str, Any],
    artifact_key: str,
    *,
    artifacts_dir: Path | None,
) -> dict[str, Any] | None:
    artifact_path_raw = str(artifacts.get(artifact_key) or "").strip()
    if not artifact_path_raw:
        return None
    artifact_path = Path(artifact_path_raw)
    if not artifact_path.is_absolute() and artifacts_dir is not None:
        artifact_path = (artifacts_dir / artifact_path).resolve()
    return _load_json_mapping(artifact_path)


def _extract_run_id_from_report_path(source_report_path: Path | None) -> str | None:
    if source_report_path is None:
        return None
    artifacts_dir = _resolve_report_artifacts_dir(source_report_path)
    if artifacts_dir is None:
        return None
    run_dir = artifacts_dir.parent if artifacts_dir.name.lower() == "artifacts" else artifacts_dir
    text = str(run_dir.name or "").strip()
    return text or None


def build_fidelity_baseline_promotion_manifest(
    *,
    baseline_id: str,
    snapshot: Mapping[str, Any],
    source_report: Mapping[str, Any],
    baseline_dir: Path,
    label: str | None = None,
    source_report_path: Path | None = None,
    source_run_id: str | None = None,
    promoted_at: str | None = None,
) -> dict[str, Any]:
    """Construit le manifeste stable d'une baseline promue."""
    source_summary = source_report.get("summary", {}) if isinstance(source_report.get("summary", {}), Mapping) else {}
    source_params = source_report.get("params", {}) if isinstance(source_report.get("params", {}), Mapping) else {}
    source_artifacts = source_report.get("artifacts", {}) if isinstance(source_report.get("artifacts", {}), Mapping) else {}
    resolved_source_run_id = _sanitize_baseline_id(source_run_id) or _extract_run_id_from_report_path(source_report_path)
    snapshot_path = baseline_dir / "fidelity_baseline_snapshot.json"
    return {
        "promotion_version": 1,
        "baseline_id": baseline_id,
        "label": str(label or baseline_id),
        "promoted_at": str(promoted_at or date.today().isoformat()),
        "storage_convention": {
            "baseline_dir": str(baseline_dir),
            "snapshot_filename": "fidelity_baseline_snapshot.json",
            "manifest_filename": "promotion_manifest.json",
        },
        "source_run": {
            "run_id": resolved_source_run_id,
            "report_json": str(source_report_path) if source_report_path is not None else None,
            "artifacts_dir": str(_resolve_report_artifacts_dir(source_report_path)) if source_report_path is not None else None,
        },
        "source_summary": {
            "requested_window": dict(cast(Mapping[str, Any], source_params.get("requested_window", snapshot.get("requested_window", {}))))
            if isinstance(source_params.get("requested_window", snapshot.get("requested_window", {})), Mapping)
            else dict(cast(Mapping[str, Any], snapshot.get("requested_window", {}))) if isinstance(snapshot.get("requested_window", {}), Mapping) else {},
            "start": source_params.get("start"),
            "end": source_params.get("end"),
            "engine_mode": source_params.get("engine_mode", snapshot.get("engine_mode")),
            "phase_modes": {
                key: source_params.get(key, cast(Mapping[str, Any], snapshot.get("phase_modes", {})).get(key) if isinstance(snapshot.get("phase_modes", {}), Mapping) else None)
                for key in ("phase2_mode", "phase3_mode", "phase4_mode", "phase5_mode", "phase7_mode")
            },
            "capital_preset_key": source_params.get("capital_preset_key", snapshot.get("capital_preset_key")),
            "final_value": source_summary.get("final_value"),
            "total_return_pct": source_summary.get("total_return_pct"),
            "sharpe_ratio": source_summary.get("sharpe_ratio"),
            "max_drawdown_pct": source_summary.get("max_drawdown_pct"),
        },
        "source_artifacts": {
            "available_keys": sorted(str(key) for key in source_artifacts),
            "report_artifact_count": len(source_artifacts),
        },
        "baseline_snapshot": {
            "path": str(snapshot_path),
            "snapshot_version": snapshot.get("snapshot_version", 1),
            "available_sections": dict(cast(Mapping[str, Any], snapshot.get("available_sections", {}))) if isinstance(snapshot.get("available_sections", {}), Mapping) else {},
            "metric_names": sorted(str(metric_name) for metric_name in cast(Mapping[str, Any], snapshot.get("metrics", {})).keys()) if isinstance(snapshot.get("metrics", {}), Mapping) else [],
        },
    }


def promote_fidelity_baseline_from_report(
    report_payload: Mapping[str, Any],
    *,
    baseline_id: str,
    destination_root: Path,
    label: str | None = None,
    source_report_path: Path | None = None,
    source_run_id: str | None = None,
    promoted_at: str | None = None,
) -> dict[str, Path]:
    """Promeut une baseline stable à partir d'un `report.json` de run réel."""
    normalized_baseline_id = _sanitize_baseline_id(baseline_id)
    if normalized_baseline_id is None:
        raise ValueError("baseline_id doit être renseigné pour promouvoir une baseline fidélité.")
    fidelity_manifest = report_payload.get("fidelity", {})
    if not isinstance(fidelity_manifest, Mapping) or not fidelity_manifest:
        raise ValueError("report_payload doit contenir un bloc `fidelity` exploitable.")
    report_params = report_payload.get("params", {}) if isinstance(report_payload.get("params", {}), Mapping) else {}
    artifacts = report_payload.get("artifacts", {})
    artifacts_mapping = dict(artifacts) if isinstance(artifacts, Mapping) else {}
    artifacts_dir = _resolve_report_artifacts_dir(source_report_path)
    replay_diagnostic_summary = _load_json_artifact_from_report(
        artifacts_mapping,
        "replay_diagnostic_summary_json",
        artifacts_dir=artifacts_dir,
    )
    candidate_target_parity_summary = _load_json_artifact_from_report(
        artifacts_mapping,
        "candidate_target_parity_summary_json",
        artifacts_dir=artifacts_dir,
    )
    compare_to_live_summary = _load_json_artifact_from_report(
        artifacts_mapping,
        "compare_to_live_summary_json",
        artifacts_dir=artifacts_dir,
    )
    execution_broker_like_summary = _load_json_artifact_from_report(
        artifacts_mapping,
        "execution_broker_like_summary_json",
        artifacts_dir=artifacts_dir,
    )
    snapshot = build_fidelity_baseline_snapshot(
        fidelity_manifest=fidelity_manifest,
        replay_diagnostic_summary=replay_diagnostic_summary,
        candidate_target_parity_summary=candidate_target_parity_summary,
        compare_to_live_summary=compare_to_live_summary,
        execution_broker_like_summary=execution_broker_like_summary,
        baseline_id=normalized_baseline_id,
    )
    report_phase_modes = _normalize_phase_modes_from_payload(cast(Mapping[str, Any], report_params))
    snapshot_phase_modes = snapshot.get("phase_modes", {})
    if report_phase_modes and isinstance(snapshot_phase_modes, Mapping):
        snapshot["phase_modes"] = {
            **dict(report_phase_modes),
            **dict(snapshot_phase_modes),
        }
    baseline_dir = destination_root / normalized_baseline_id
    snapshot_path = save_fidelity_baseline_snapshot(snapshot, baseline_dir)
    promotion_manifest = build_fidelity_baseline_promotion_manifest(
        baseline_id=normalized_baseline_id,
        snapshot=snapshot,
        source_report=report_payload,
        baseline_dir=baseline_dir,
        label=label,
        source_report_path=source_report_path,
        source_run_id=source_run_id,
        promoted_at=promoted_at,
    )
    promotion_manifest_path = save_fidelity_baseline_promotion_manifest(promotion_manifest, baseline_dir)
    return {
        "fidelity_baseline_snapshot_json": snapshot_path,
        "fidelity_baseline_promotion_manifest_json": promotion_manifest_path,
    }


def promote_fidelity_baseline_from_report_path(
    report_path: Path,
    *,
    baseline_id: str,
    destination_root: Path,
    label: str | None = None,
    source_run_id: str | None = None,
    promoted_at: str | None = None,
) -> dict[str, Path]:
    """Charge un `report.json` puis promeut la baseline correspondante."""
    report_payload = _load_json_mapping(report_path)
    if report_payload is None:
        raise ValueError(f"Impossible de charger un report JSON exploitable depuis `{report_path}`.")
    return promote_fidelity_baseline_from_report(
        report_payload,
        baseline_id=baseline_id,
        destination_root=destination_root,
        label=label,
        source_report_path=report_path,
        source_run_id=source_run_id,
        promoted_at=promoted_at,
    )


def _resolve_baseline_entry(
    catalog: Mapping[str, Any],
    *,
    baseline_id: str | None,
    requested_window: Mapping[str, Any],
) -> dict[str, Any] | None:
    baselines = catalog.get("baselines", [])
    if not isinstance(baselines, Sequence) or isinstance(baselines, (str, bytes)):
        return None
    normalized_id = _sanitize_baseline_id(baseline_id)
    exact_window = dict(requested_window) if isinstance(requested_window, Mapping) else {}
    for entry in baselines:
        if not isinstance(entry, Mapping):
            continue
        if normalized_id is not None and _sanitize_baseline_id(entry.get("baseline_id")) == normalized_id:
            return dict(entry)
    if normalized_id is not None:
        return None
    for entry in baselines:
        if not isinstance(entry, Mapping):
            continue
        entry_window = entry.get("requested_window", {})
        if isinstance(entry_window, Mapping) and dict(entry_window) == exact_window:
            return dict(entry)
    return None


def _default_baseline_metric_thresholds() -> dict[str, dict[str, object]]:
    return {
        "sentiment_coverage_ratio_after": {"comparison": "min", "abs": 0.0},
        "ml_coverage_ratio_after": {"comparison": "min", "abs": 0.0},
        "replay_degraded_session_ratio": {"comparison": "max", "abs": 0.0},
        "parity_diverged_session_ratio": {"comparison": "max", "abs": 0.0},
        "compare_live_fidelity_score": {"comparison": "min", "abs": 0.02},
        "compare_live_candidate_alignment_score": {"comparison": "min", "abs": 0.02},
        "compare_live_risk_alignment_score": {"comparison": "min", "abs": 0.02},
        "compare_live_portfolio_alignment_score": {"comparison": "min", "abs": 0.02},
        "compare_live_execution_alignment_score": {"comparison": "min", "abs": 0.02},
        "compare_live_fills_alignment_score": {"comparison": "min", "abs": 0.02},
        "compare_live_exits_alignment_score": {"comparison": "min", "abs": 0.02},
        "compare_live_pnl_alignment_score": {"comparison": "min", "abs": 0.02},
        "broker_stale_orders": {"comparison": "max", "abs": 0.0},
    }


def _normalize_metric_thresholds(value: object) -> dict[str, dict[str, object]]:
    if not isinstance(value, Mapping):
        return {}
    normalized: dict[str, dict[str, object]] = {}
    for raw_metric_name, raw_rule in value.items():
        metric_name = str(raw_metric_name or "").strip()
        if not metric_name or not isinstance(raw_rule, Mapping):
            continue
        comparison = str(raw_rule.get("comparison") or raw_rule.get("direction") or "abs").strip().lower()
        tolerance_abs = float(raw_rule.get("abs", 0.0) or 0.0)
        normalized[metric_name] = {
            "comparison": comparison if comparison in {"abs", "min", "max"} else "abs",
            "abs": tolerance_abs,
            "label": str(raw_rule.get("label") or metric_name),
        }
    return normalized


def _evaluate_numeric_baseline_check(
    *,
    metric_name: str,
    baseline_value: object,
    current_value: object,
    rule: Mapping[str, object],
) -> dict[str, object]:
    baseline_float = float(baseline_value or 0.0)
    current_float = float(current_value or 0.0)
    comparison = str(rule.get("comparison") or "abs")
    tolerance_abs = float(rule.get("abs", 0.0) or 0.0)
    delta = round(current_float - baseline_float, 6)
    failed = False
    tolerated_min = baseline_float - tolerance_abs
    tolerated_max = baseline_float + tolerance_abs
    if comparison == "min":
        failed = current_float < tolerated_min
    elif comparison == "max":
        failed = current_float > tolerated_max
    else:
        failed = abs(delta) > tolerance_abs
    return {
        "check_type": "metric",
        "name": metric_name,
        "label": str(rule.get("label") or metric_name),
        "comparison": comparison,
        "baseline_value": round(baseline_float, 6),
        "current_value": round(current_float, 6),
        "delta": delta,
        "tolerance_abs": round(tolerance_abs, 6),
        "status": "failed" if failed else "passed",
    }


def _evaluate_exact_mapping_check(
    *,
    name: str,
    label: str,
    baseline_value: object,
    current_value: object,
) -> dict[str, object]:
    baseline_mapping = dict(baseline_value) if isinstance(baseline_value, Mapping) else {}
    current_mapping = dict(current_value) if isinstance(current_value, Mapping) else {}
    return {
        "check_type": "metadata",
        "name": name,
        "label": label,
        "comparison": "exact",
        "baseline_value": baseline_mapping,
        "current_value": current_mapping,
        "status": "passed" if baseline_mapping == current_mapping else "failed",
    }


def build_fidelity_baseline_comparison(
    current_snapshot: Mapping[str, Any],
    *,
    catalog_path: Path,
    baseline_id: str | None = None,
) -> dict[str, Any]:
    """Compare un snapshot courant à une baseline décrite dans un catalogue JSON."""
    catalog_payload = _load_json_mapping(catalog_path)
    if catalog_payload is None:
        return {
            "comparison_version": 1,
            "status": "missing_catalog",
            "catalog_path": str(catalog_path),
            "baseline_id": _sanitize_baseline_id(baseline_id),
            "checks": [],
        }

    entry = _resolve_baseline_entry(
        catalog_payload,
        baseline_id=baseline_id,
        requested_window=cast(Mapping[str, Any], current_snapshot.get("requested_window", {})) if isinstance(current_snapshot.get("requested_window", {}), Mapping) else {},
    )
    if entry is None:
        return {
            "comparison_version": 1,
            "status": "missing_baseline",
            "catalog_path": str(catalog_path),
            "catalog_version": catalog_payload.get("version", 1),
            "baseline_id": _sanitize_baseline_id(baseline_id),
            "checks": [],
        }

    snapshot_path_raw = str(entry.get("snapshot_path") or "").strip()
    resolved_snapshot_path = (catalog_path.parent / snapshot_path_raw).resolve() if snapshot_path_raw and not Path(snapshot_path_raw).is_absolute() else Path(snapshot_path_raw) if snapshot_path_raw else None
    if resolved_snapshot_path is None:
        return {
            "comparison_version": 1,
            "status": "missing_snapshot_path",
            "catalog_path": str(catalog_path),
            "catalog_version": catalog_payload.get("version", 1),
            "baseline_id": _sanitize_baseline_id(entry.get("baseline_id")),
            "baseline_label": entry.get("label"),
            "checks": [],
        }

    baseline_snapshot = _load_json_mapping(resolved_snapshot_path)
    if baseline_snapshot is None:
        return {
            "comparison_version": 1,
            "status": "missing_snapshot",
            "catalog_path": str(catalog_path),
            "catalog_version": catalog_payload.get("version", 1),
            "baseline_id": _sanitize_baseline_id(entry.get("baseline_id")),
            "baseline_label": entry.get("label"),
            "baseline_snapshot_path": str(resolved_snapshot_path),
            "checks": [],
        }

    baseline_metrics = baseline_snapshot.get("metrics", {})
    current_metrics = current_snapshot.get("metrics", {})
    metric_thresholds = _default_baseline_metric_thresholds()
    metric_thresholds.update(_normalize_metric_thresholds(entry.get("metric_thresholds", {})))
    checks: list[dict[str, object]] = []
    if isinstance(entry.get("requested_window", {}), Mapping):
        checks.append(
            _evaluate_exact_mapping_check(
                name="requested_window",
                label="Fenêtre demandée",
                baseline_value=entry.get("requested_window", {}),
                current_value=current_snapshot.get("requested_window", {}),
            )
        )
    baseline_phase_modes = entry.get("phase_modes", baseline_snapshot.get("phase_modes", {}))
    if isinstance(baseline_phase_modes, Mapping) and baseline_phase_modes:
        checks.append(
            _evaluate_exact_mapping_check(
                name="phase_modes",
                label="Chaîne de phases",
                baseline_value=baseline_phase_modes,
                current_value=current_snapshot.get("phase_modes", {}),
            )
        )
    if isinstance(baseline_metrics, Mapping) and isinstance(current_metrics, Mapping):
        for metric_name, rule in metric_thresholds.items():
            if metric_name not in baseline_metrics or metric_name not in current_metrics:
                continue
            checks.append(
                _evaluate_numeric_baseline_check(
                    metric_name=metric_name,
                    baseline_value=baseline_metrics.get(metric_name),
                    current_value=current_metrics.get(metric_name),
                    rule=rule,
                )
            )
    failed_checks = [check for check in checks if str(check.get("status") or "") == "failed"]
    passed_checks = [check for check in checks if str(check.get("status") or "") == "passed"]
    return {
        "comparison_version": 1,
        "status": "aligned" if not failed_checks else "diverged",
        "catalog_path": str(catalog_path),
        "catalog_version": catalog_payload.get("version", 1),
        "baseline_id": _sanitize_baseline_id(entry.get("baseline_id")),
        "baseline_label": entry.get("label"),
        "baseline_snapshot_path": str(resolved_snapshot_path),
        "requested_window": dict(cast(Mapping[str, Any], current_snapshot.get("requested_window", {}))) if isinstance(current_snapshot.get("requested_window", {}), Mapping) else {},
        "phase_modes": dict(cast(Mapping[str, Any], current_snapshot.get("phase_modes", {}))) if isinstance(current_snapshot.get("phase_modes", {}), Mapping) else {},
        "checked_count": len(checks),
        "passed_count": len(passed_checks),
        "failed_count": len(failed_checks),
        "failed_checks": failed_checks,
        "checks": checks,
        "baseline_metrics": dict(baseline_metrics) if isinstance(baseline_metrics, Mapping) else {},
        "current_metrics": dict(current_metrics) if isinstance(current_metrics, Mapping) else {},
    }


def save_fidelity_baseline_comparison(comparison: Mapping[str, Any], output_dir: Path) -> dict[str, Path]:
    """Sauvegarde le résultat de comparaison baseline fidélité en JSON + CSV."""
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "fidelity_baseline_comparison.json"
    csv_path = output_dir / "fidelity_baseline_comparison_checks.csv"
    json_path.write_text(json.dumps(dict(comparison), ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    checks = comparison.get("checks", []) if isinstance(comparison, Mapping) else []
    rows: list[dict[str, object]] = []
    if isinstance(checks, Sequence) and not isinstance(checks, (str, bytes)):
        for check in checks:
            if not isinstance(check, Mapping):
                continue
            rows.append(
                {
                    "name": check.get("name"),
                    "label": check.get("label"),
                    "check_type": check.get("check_type"),
                    "comparison": check.get("comparison"),
                    "status": check.get("status"),
                    "baseline_value": json.dumps(check.get("baseline_value"), ensure_ascii=False, default=str),
                    "current_value": json.dumps(check.get("current_value"), ensure_ascii=False, default=str),
                    "delta": check.get("delta"),
                    "tolerance_abs": check.get("tolerance_abs"),
                }
            )
    pd.DataFrame(rows).to_csv(csv_path, index=False)
    return {
        "fidelity_baseline_comparison_json": json_path,
        "fidelity_baseline_comparison_checks_csv": csv_path,
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


def evaluate_ml_coverage_gate(
    *,
    engine_mode: str,
    ml_mode: str,
    ml_diagnostics: MlPreparationDiagnostics | None,
    min_coverage_ratio: float | None,
) -> dict[str, object]:
    """Évalue un gating dur sur la couverture ML pour les runs pipeline.

    Le gating est considéré actif uniquement si :
    - ``engine_mode == 'pipeline'`` ;
    - ``ml_mode != 'off'`` ;
    - ``min_coverage_ratio`` est renseigné et > 0.

    Retourne un payload sérialisable explicitant si le run est autorisé.
    """
    normalized_engine_mode = str(engine_mode or "research").strip().lower() or "research"
    normalized_ml_mode = str(ml_mode or "auto").strip().lower() or "auto"
    threshold = None if min_coverage_ratio is None else float(min_coverage_ratio)
    if threshold is not None and not 0.0 <= threshold <= 1.0:
        raise ValueError("min_coverage_ratio doit être compris entre 0.0 et 1.0.")

    enabled = (
        normalized_engine_mode == "pipeline"
        and normalized_ml_mode != "off"
        and threshold is not None
        and threshold > 0.0
    )
    if not enabled:
        return {
            "enabled": False,
            "allowed": True,
            "required_ratio": threshold,
            "coverage_ratio": None,
            "expected_symbol_dates": 0,
            "missing_prediction_keys_after": 0,
            "reason": "disabled",
        }

    expected_symbol_dates = max(int(getattr(ml_diagnostics, "expected_symbol_dates", 0) or 0), 0)
    missing_prediction_keys_after = max(
        int(
            (
                getattr(ml_diagnostics, "missing_prediction_keys_after", 0)
                if ml_diagnostics is not None
                else 0
            )
            or (
                getattr(ml_diagnostics, "missing_prediction_keys", 0)
                if ml_diagnostics is not None
                else 0
            )
        ),
        0,
    )
    coverage_ratio = (
        1.0
        if expected_symbol_dates <= 0
        else max(0.0, float(expected_symbol_dates - missing_prediction_keys_after) / float(expected_symbol_dates))
    )
    allowed = expected_symbol_dates <= 0 or coverage_ratio + 1e-12 >= float(threshold)
    reason = "ok" if allowed else "coverage_below_threshold"
    return {
        "enabled": True,
        "allowed": bool(allowed),
        "required_ratio": float(threshold),
        "coverage_ratio": float(coverage_ratio),
        "expected_symbol_dates": int(expected_symbol_dates),
        "missing_prediction_keys_after": int(missing_prediction_keys_after),
        "reason": reason,
    }


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


def build_fidelity_symbol_matrix(
    *,
    scores_df: pd.DataFrame,
    predictions_df: pd.DataFrame | None,
    fidelity_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    """Construit une matrice symbole × état PIT pour chaque composant.

    Pour chaque symbole candidat du run, détermine son état par composant :
    ``persisted`` / ``rebuilt`` / ``fallback`` / ``absent``.

    Cette matrice permet d'identifier rapidement quels symboles ont dégradé
    quelle couche (scores, sentiment, ml, walk_forward).
    """
    normalized_scores = scores_df.copy() if isinstance(scores_df, pd.DataFrame) else pd.DataFrame()
    normalized_preds = predictions_df.copy() if isinstance(predictions_df, pd.DataFrame) else pd.DataFrame()
    if not normalized_scores.empty:
        normalized_scores["trade_date"] = _normalize_trade_date_series(normalized_scores)
    if not normalized_preds.empty:
        normalized_preds["trade_date"] = _normalize_trade_date_series(normalized_preds)

    provenance_payload = fidelity_manifest.get("provenance", {})
    if not isinstance(provenance_payload, Mapping):
        provenance_payload = {}

    scores_provenance = cast(Mapping[str, Any], provenance_payload.get("scores", {})) if isinstance(provenance_payload.get("scores"), Mapping) else {}
    ml_provenance = cast(Mapping[str, Any], provenance_payload.get("ml", {})) if isinstance(provenance_payload.get("ml"), Mapping) else {}

    scores_provenance_kind = str(scores_provenance.get("provenance_kind") or "persisted_history")
    ml_source_tags: list[str] = list(ml_provenance.get("source_tags", []))
    ml_causes_by_symbol: dict[str, list[str]] = {
        str(symbol): list(causes)
        for symbol, causes in _normalize_symbol_cause_mapping(ml_provenance.get("missing_causes_by_symbol", {})).items()
    }

    # Ensemble des symboles prédits disponibles (toutes séances)
    predicted_symbols: set[str] = set()
    rebuilt_symbols: set[str] = set()
    if not normalized_preds.empty and "symbol" in normalized_preds.columns:
        predicted_symbols = {str(symbol).strip().upper() for symbol in normalized_preds["symbol"].dropna().tolist() if str(symbol).strip()}
    # Déterminer les symboles reconstruits depuis les source_tags ML
    if "rebuilt_predictions" in ml_source_tags and not normalized_preds.empty and "predicted_source" in normalized_preds.columns:
        rebuilt_symbols = {
            str(row["symbol"]).strip().upper()
            for _, row in normalized_preds[["symbol", "predicted_source"]].dropna(subset=["symbol"]).iterrows()
            if str(row.get("predicted_source") or "").strip().lower() == "rebuilt"
        }

    # All candidate symbols across all sessions
    candidate_symbols = _sorted_unique_symbols(normalized_scores) if not normalized_scores.empty else []
    matrix_rows: list[dict[str, Any]] = []

    for symbol in candidate_symbols:
        symbol_scores = normalized_scores.loc[normalized_scores["symbol"].astype(str).str.upper() == symbol.upper()] if not normalized_scores.empty and "symbol" in normalized_scores.columns else pd.DataFrame()
        session_count = int(symbol_scores["trade_date"].nunique()) if not symbol_scores.empty and "trade_date" in symbol_scores.columns else 0

        # Scores state
        if scores_provenance_kind == "current_snapshot_fallback":
            scores_state = "fallback"
        else:
            scores_state = "persisted"

        # Score source (walk_forward / sentiment / base)
        score_source: str | None = None
        if not symbol_scores.empty:
            if "score_source" in symbol_scores.columns and symbol_scores["score_source"].notna().any():
                source_values = symbol_scores["score_source"].dropna().astype(str).tolist()
                score_source = source_values[-1] if source_values else None
            elif "final_score_walk_forward" in symbol_scores.columns and symbol_scores["final_score_walk_forward"].notna().any():
                score_source = "final_score_walk_forward"
            elif "final_score_sentiment" in symbol_scores.columns and symbol_scores["final_score_sentiment"].notna().any():
                score_source = "final_score_sentiment"
            elif "final_score" in symbol_scores.columns and symbol_scores["final_score"].notna().any():
                score_source = "final_score"

        # Sentiment state
        if not symbol_scores.empty and "final_score_sentiment" in symbol_scores.columns:
            sentiment_na_count = int(symbol_scores["final_score_sentiment"].isna().sum())
            sentiment_total = int(len(symbol_scores))
            if sentiment_na_count == sentiment_total:
                sentiment_state = "absent"
            elif sentiment_na_count > 0:
                sentiment_state = "fallback"
            else:
                sentiment_state = "persisted"
        else:
            sentiment_state = "absent"

        # ML state
        if symbol in predicted_symbols:
            if symbol in rebuilt_symbols:
                ml_state = "rebuilt"
            else:
                ml_state = "persisted"
        else:
            ml_state = "absent"
        ml_causes: list[str] = ml_causes_by_symbol.get(symbol, [])

        # Walk-forward state
        walk_forward_state = "applied" if score_source == "final_score_walk_forward" else "not_applied"

        matrix_rows.append(
            {
                "symbol": symbol,
                "session_count": session_count,
                "scores_state": scores_state,
                "score_source": score_source,
                "sentiment_state": sentiment_state,
                "ml_state": ml_state,
                "ml_missing_causes": ml_causes,
                "walk_forward_state": walk_forward_state,
                "degraded": bool(sentiment_state in ("fallback", "absent") or ml_state == "absent" or scores_state == "fallback"),
            }
        )

    matrix_rows.sort(key=lambda row: (-int(bool(row.get("degraded", False))), str(row.get("symbol") or "")))
    degraded_count = sum(1 for row in matrix_rows if bool(row.get("degraded", False)))
    return {
        "taxonomy_version": int(fidelity_manifest.get("taxonomy_version", 1)),
        "engine_mode": fidelity_manifest.get("engine_mode"),
        "symbol_count": len(matrix_rows),
        "degraded_symbol_count": degraded_count,
        "component_states": ["persisted", "rebuilt", "fallback", "absent"],
        "symbols": matrix_rows,
    }


def save_fidelity_symbol_matrix(matrix: Mapping[str, Any], output_dir: Path) -> dict[str, Path]:
    """Sauvegarde la matrice symbole × état PIT en JSON canonique + CSV aplati."""
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "fidelity_symbol_matrix.json"
    csv_path = output_dir / "fidelity_symbol_matrix.csv"
    json_path.write_text(json.dumps(dict(matrix), ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    symbols = matrix.get("symbols", []) if isinstance(matrix, Mapping) else []
    rows: list[dict[str, object]] = []
    if isinstance(symbols, Sequence) and not isinstance(symbols, (str, bytes)):
        for entry in symbols:
            if not isinstance(entry, Mapping):
                continue
            rows.append(
                {
                    "symbol": entry.get("symbol"),
                    "session_count": entry.get("session_count", 0),
                    "scores_state": entry.get("scores_state"),
                    "score_source": entry.get("score_source"),
                    "sentiment_state": entry.get("sentiment_state"),
                    "ml_state": entry.get("ml_state"),
                    "ml_missing_causes": ", ".join(_normalize_string_list(entry.get("ml_missing_causes", []))),
                    "walk_forward_state": entry.get("walk_forward_state"),
                    "degraded": bool(entry.get("degraded", False)),
                }
            )
    pd.DataFrame(rows).to_csv(csv_path, index=False)
    return {
        "fidelity_symbol_matrix_json": json_path,
        "fidelity_symbol_matrix_csv": csv_path,
    }


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
    "build_candidate_target_parity_summary",
    "build_compare_to_live_summary",
    "build_fidelity_baseline_comparison",
    "build_fidelity_baseline_snapshot",
    "build_coverage_summary",
    "build_fidelity_manifest",
    "build_fidelity_symbol_matrix",
    "evaluate_ml_coverage_gate",
    "build_replay_diagnostic_summary",
    "save_fidelity_baseline_comparison",
    "save_fidelity_baseline_snapshot",
    "save_fidelity_manifest",
    "save_fidelity_symbol_matrix",
    "save_candidate_target_parity_summary",
    "save_compare_to_live_summary",
    "save_coverage_summary",
    "save_replay_diagnostic_summary",
]


