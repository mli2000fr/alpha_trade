"""ihm/pages/ml.py — ML / Prédictions."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from io import BytesIO, StringIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pandas as pd
import streamlit as st

from ihm.pages._shared import ML_PENDING_SELECTED_SYMBOL_KEY, ML_SELECTED_SYMBOL_KEY
from ihm.pages import run_page_if_standalone
from ihm.components.run_summary import render_persistent_business_summary
from ihm.components.db_controls import render_db_connection_form, render_query_diagnostic
from ihm.components.tables import show_dataframe
from ihm.components.symbol_table import render_symbol_table
from ihm.services.db import db_available
from ihm.services.ml_artifacts import (
    get_model_artifacts_dir,
    list_ml_artifact_batches,
    list_ml_artifact_symbols,
    load_ml_artifact_report,
)
from ihm.services.queries import (
    get_model_governance,
    get_model_metrics,
    get_latest_run_business_summary,
    get_ml_batch_comments,
    get_prediction_governance_audit,
    get_prediction_symbols,
    get_predictions,
    get_training_runs,
)
from ihm.services.run_summary import get_run_summary
from database.connection import get_sqlalchemy_engine
from modelFactory.db_registry import get_serving_batch, set_serving_batch

ML_AUDIT_FILTER_SOURCE_LIMIT = 500
ML_SELECTED_AUDIT_NAVIGATION_KEY = "ihm_ml_selected_audit_navigation"
ML_SELECTED_ARTIFACT_BATCH_KEY = "ihm_ml_selected_artifact_batch"


def _sorted_non_empty_strings(values: list[object], *, reverse: bool = False) -> list[str]:
    normalized = {str(value).strip() for value in values if str(value).strip()}
    return sorted(normalized, reverse=reverse)


def _build_prediction_audit_filter_options(
    audit_df: pd.DataFrame,
    governance_df: pd.DataFrame,
) -> dict[str, list[str]]:
    audit_run_ids = audit_df["run_id"].tolist() if "run_id" in audit_df.columns else []
    governance_run_ids = governance_df["run_id"].tolist() if "run_id" in governance_df.columns else []
    audit_selection_modes = (
        audit_df["governance_selection_mode"].tolist() if "governance_selection_mode" in audit_df.columns else []
    )
    governance_selection_modes = governance_df["selection_mode"].tolist() if "selection_mode" in governance_df.columns else []
    return {
        "governance_link_statuses": _sorted_non_empty_strings(
            audit_df["governance_link_status"].tolist() if "governance_link_status" in audit_df.columns else []
        ),
        "selection_modes": _sorted_non_empty_strings(audit_selection_modes + governance_selection_modes),
        "served_models": _sorted_non_empty_strings(audit_df["served_model"].tolist() if "served_model" in audit_df.columns else []),
        "run_ids": _sorted_non_empty_strings(audit_run_ids + governance_run_ids, reverse=True),
    }


def _build_prediction_audit_navigation_options(audit_df: pd.DataFrame) -> list[dict[str, str]]:
    if audit_df.empty:
        return []
    options: list[dict[str, str]] = []
    for index, row in audit_df.reset_index(drop=True).iterrows():
        symbol = str(row.get("symbol") or "—")
        run_id = str(row.get("run_id") or "—")
        prediction_date = str(row.get("prediction_date") or "—")
        served_model = str(row.get("served_model") or "—")
        link_status = str(row.get("governance_link_status") or "—")
        selection_mode = str(row.get("governance_selection_mode") or "")
        artifact_symbol = str(
            row.get("governance_champion_artifact_symbol")
            or row.get("governance_served_artifact_symbol")
            or row.get("symbol")
            or ""
        )
        options.append(
            {
                "id": f"{run_id}|{symbol}|{index}",
                "label": f"{prediction_date} | {symbol} | {run_id} | servi={served_model} | statut={link_status}",
                "run_id": run_id,
                "symbol": symbol,
                "served_model": served_model,
                "selection_mode": selection_mode,
                "artifact_symbol": artifact_symbol,
                "governance_link_status": link_status,
            }
        )
    return options


def _resolve_navigation_symbol(navigation_option: dict[str, str], available_symbols: list[str]) -> str | None:
    artifact_symbol = str(navigation_option.get("artifact_symbol") or "").strip()
    symbol = str(navigation_option.get("symbol") or "").strip()
    if artifact_symbol and artifact_symbol in available_symbols:
        return artifact_symbol
    if symbol and symbol in available_symbols:
        return symbol
    return None


def _match_navigation_row(audit_df: pd.DataFrame, navigation_option: dict[str, str]) -> pd.Series:
    if audit_df.empty:
        return pd.Series(False, index=audit_df.index, dtype="bool")
    mask = pd.Series(True, index=audit_df.index, dtype="bool")
    comparisons = {
        "run_id": navigation_option.get("run_id"),
        "symbol": navigation_option.get("symbol"),
        "served_model": navigation_option.get("served_model"),
    }
    for column, value in comparisons.items():
        if column in audit_df.columns and value:
            mask &= audit_df[column].fillna("").astype(str) == str(value)
    if "prediction_date" in audit_df.columns and navigation_option.get("label"):
        prediction_date = navigation_option["label"].split(" | ", 1)[0]
        mask &= audit_df["prediction_date"].fillna("").astype(str) == prediction_date
    return mask


def _focus_dataframe_on_navigation_row(
    audit_df: pd.DataFrame,
    navigation_option: dict[str, str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if audit_df.empty:
        return audit_df, audit_df
    mask = _match_navigation_row(audit_df, navigation_option)
    focused = audit_df[mask].copy()
    if focused.empty:
        return audit_df, focused
    remaining = audit_df[~mask].copy()
    return pd.concat([focused, remaining], ignore_index=True), focused.head(1).reset_index(drop=True)


def _build_section_export_frame(section: str, frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    export_frame = frame.copy()
    export_frame.insert(0, "section", section)
    return export_frame


def _build_ml_run_export_dataframe(
    *,
    run_id: str,
    focused_audit_row: pd.DataFrame,
    run_governance: pd.DataFrame,
    run_audit_rows: pd.DataFrame,
    run_predictions: pd.DataFrame,
    artifact_report: dict[str, object] | None,
) -> pd.DataFrame:
    sections: list[pd.DataFrame] = []
    if not focused_audit_row.empty:
        sections.append(_build_section_export_frame("selected_audit_row", focused_audit_row))
    if not run_governance.empty:
        sections.append(_build_section_export_frame("run_governance", run_governance))
    if not run_audit_rows.empty:
        sections.append(_build_section_export_frame("run_prediction_audit", run_audit_rows))
    if not run_predictions.empty:
        sections.append(_build_section_export_frame("run_predictions", run_predictions))
    if artifact_report:
        summary_row = pd.DataFrame(
            [
                {
                    "run_id": run_id,
                    "artifact_symbol": artifact_report.get("symbol"),
                    "artifact_run_id": artifact_report.get("run_id"),
                    "artifact_selected_model": artifact_report.get("selected_model"),
                    "artifact_selection_mode": artifact_report.get("selection_mode"),
                    "artifact_selected_decision_threshold": artifact_report.get("selected_decision_threshold"),
                    "artifact_config_path": str(artifact_report.get("config_path") or ""),
                    "artifact_metrics_path": str(artifact_report.get("metrics_path") or ""),
                }
            ]
        )
        sections.append(_build_section_export_frame("artifact_summary", summary_row))
        routes_df = artifact_report.get("routes_df")
        if isinstance(routes_df, pd.DataFrame) and not routes_df.empty:
            sections.append(_build_section_export_frame("artifact_routes_snapshot", routes_df))
        ranking_df = artifact_report.get("ranking_df")
        if isinstance(ranking_df, pd.DataFrame) and not ranking_df.empty:
            sections.append(_build_section_export_frame("artifact_ranking_snapshot", ranking_df))
    if not sections:
        return pd.DataFrame(columns=["section", "run_id"])
    return pd.concat(sections, ignore_index=True, sort=False)


def _build_ml_run_export_filename(run_id: str, symbol: str | None = None) -> str:
    safe_run_id = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in run_id).strip("_") or "run"
    safe_symbol = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in (symbol or "all")).strip("_") or "all"
    return f"ml_run_audit_{safe_symbol}_{safe_run_id}.csv"


def _build_ml_run_export_zip_filename(run_id: str, symbol: str | None = None) -> str:
    return _build_ml_run_export_filename(run_id, symbol).removesuffix(".csv") + ".zip"


def _to_csv_bytes(df: pd.DataFrame) -> bytes:
    buffer = StringIO()
    df.to_csv(buffer, index=False)
    return buffer.getvalue().encode("utf-8-sig")


def _artifact_export_json_bytes(
    artifact_report: dict[str, object] | None,
    *,
    key: str,
    path_key: str,
) -> bytes:
    if artifact_report is None:
        payload = {"errors": ["Aucun artefact sélectionné pour cet export."], "kind": key}
        return json.dumps(payload, indent=2, ensure_ascii=False, default=str).encode("utf-8")
    path_value = artifact_report.get(path_key)
    try:
        if path_value:
            path = Path(path_value)
            if path.exists() and path.is_file():
                return path.read_bytes()
    except Exception:
        pass
    payload = {
        "kind": key,
        "symbol": artifact_report.get("symbol"),
        "run_id": artifact_report.get("run_id"),
        key: artifact_report.get(key) or {},
        "errors": artifact_report.get("errors") or [],
        "warning": f"Fichier source indisponible pour `{path_key}` ; export depuis les données chargées en mémoire.",
    }
    return json.dumps(payload, indent=2, ensure_ascii=False, default=str).encode("utf-8")


def _build_ml_run_export_readme_bytes(
    *,
    export_df: pd.DataFrame,
    artifact_report: dict[str, object] | None,
    focused_audit_row: pd.DataFrame,
    selected_navigation: dict[str, str] | None,
    exported_at: str,
    run_id: str,
    symbol: str | None,
) -> bytes:
    sections = sorted({str(value) for value in export_df.get("section", pd.Series(dtype="object")).dropna().tolist()})
    artifact_symbol = str(artifact_report.get("symbol") or "—") if artifact_report else "—"
    artifact_run_id = str(artifact_report.get("run_id") or "—") if artifact_report else "—"
    selected_row = focused_audit_row.iloc[0].to_dict() if not focused_audit_row.empty else {}
    alignment_status = (
        str(selected_row.get("governance_link_status") or "").strip()
        or str((selected_navigation or {}).get("governance_link_status") or "").strip()
        or "—"
    )
    selected_served_model = (
        str(selected_row.get("served_model") or "").strip()
        or str((selected_navigation or {}).get("served_model") or "").strip()
        or "—"
    )
    selected_selection_mode = (
        str(selected_row.get("governance_selection_mode") or "").strip()
        or str((selected_navigation or {}).get("selection_mode") or "").strip()
        or "—"
    )
    fallback_note = ""
    if artifact_report is None:
        fallback_note = (
            "- Les fichiers `config.json` et `metrics.json` exportés sont des placeholders, car aucun artefact n'a pu être résolu "
            "pour ce run.\n"
        )
    elif artifact_report.get("errors"):
        fallback_note = (
            "- Certains manifestes artefacts ont été reconstruits à partir des données déjà chargées en mémoire, car les fichiers source "
            "n'étaient pas tous disponibles au moment de l'export.\n"
        )
    readme = (
        "Alpha Trade — Export ML du run sélectionné\n"
        "==========================================\n\n"
        "Résumé d'export\n"
        "----------------\n"
        f"Horodatage d'export (UTC) : {exported_at}\n"
        f"Run exporté : {run_id}\n"
        f"Symbole DB : {symbol or '—'}\n"
        f"Modèle servi sur la ligne sélectionnée : {selected_served_model}\n"
        f"Statut d'alignement de la ligne sélectionnée : {alignment_status}\n"
        f"Mode de sélection associé : {selected_selection_mode}\n"
        f"Symbole artefact : {artifact_symbol}\n"
        f"Run artefact courant : {artifact_run_id}\n\n"
        "Contenu de l'archive\n"
        "--------------------\n"
        "- `ml_run_audit_<symbol>_<run>.csv` : export tabulaire consolidé du run sélectionné. La colonne `section` indique la provenance "
        "des lignes (audit, gouvernance, prédictions, snapshots artefacts).\n"
        "- `config.json` : manifeste de serving du symbole/artefact ciblé.\n"
        "- `metrics.json` : manifeste de métriques et de gouvernance challengers/champion du symbole/artefact ciblé.\n"
        "- `export_manifest.json` : méta-informations techniques sur l'archive produite.\n\n"
        "Sections possibles du CSV\n"
        "-------------------------\n"
        f"- {', '.join(sections) if sections else 'aucune section exportée'}\n\n"
        "Notes d'interprétation\n"
        "----------------------\n"
        "- Le CSV décrit le run sélectionné dans l'IHM au moment de l'export.\n"
        "- Les fichiers `config.json` et `metrics.json` correspondent à l'artefact actuellement disponible pour le symbole ciblé.\n"
        "- Si le run d'artefact diffère du `run_id` demandé, cela signifie généralement qu'un run plus récent a remplacé les artefacts sur disque.\n"
        f"{fallback_note}"
    )
    return readme.encode("utf-8")


def _build_ml_run_export_zip_bytes(
    *,
    export_df: pd.DataFrame,
    artifact_report: dict[str, object] | None,
    focused_audit_row: pd.DataFrame,
    selected_navigation: dict[str, str] | None,
    exported_at: str,
    run_id: str,
    symbol: str | None,
) -> bytes:
    csv_name = _build_ml_run_export_filename(run_id, symbol)
    config_bytes = _artifact_export_json_bytes(artifact_report, key="config", path_key="config_path")
    metrics_bytes = _artifact_export_json_bytes(artifact_report, key="metrics", path_key="metrics_path")
    readme_bytes = _build_ml_run_export_readme_bytes(
        export_df=export_df,
        artifact_report=artifact_report,
        focused_audit_row=focused_audit_row,
        selected_navigation=selected_navigation,
        exported_at=exported_at,
        run_id=run_id,
        symbol=symbol,
    )
    manifest = {
        "run_id": run_id,
        "symbol": symbol,
        "artifact_symbol": artifact_report.get("symbol") if artifact_report else None,
        "artifact_run_id": artifact_report.get("run_id") if artifact_report else None,
        "archive_contents": [csv_name, "config.json", "metrics.json", "export_manifest.json", "README.txt"],
    }
    zip_buffer = BytesIO()
    with ZipFile(zip_buffer, mode="w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(csv_name, _to_csv_bytes(export_df))
        archive.writestr("config.json", config_bytes)
        archive.writestr("metrics.json", metrics_bytes)
        archive.writestr("export_manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False, default=str).encode("utf-8"))
        archive.writestr("README.txt", readme_bytes)
    return zip_buffer.getvalue()


def _summarize_prediction_governance_audit(audit_df: pd.DataFrame) -> dict[str, object]:
    if audit_df.empty:
        return {
            "latest_served_model": "—",
            "latest_governance_champion": "—",
            "latest_link_status": "—",
            "mismatch_count": 0,
        }
    latest = audit_df.iloc[0]
    status_series = audit_df["governance_link_status"] if "governance_link_status" in audit_df.columns else pd.Series(dtype="object")
    mismatch_count = int((status_series != "aligned").sum()) if not status_series.empty else 0
    return {
        "latest_served_model": latest.get("served_model", "—") or "—",
        "latest_governance_champion": latest.get("governance_champion_model", "—") or "—",
        "latest_link_status": latest.get("governance_link_status", "—") or "—",
        "mismatch_count": mismatch_count,
    }


def _summarize_ml_runtime_status(
    predict_record: dict[str, object] | None,
    risk_record: dict[str, object] | None,
) -> dict[str, object]:
    predict_summary = get_run_summary(predict_record)
    risk_summary = get_run_summary(risk_record)
    artifact_issue_count = int(predict_summary.get("prediction_artifact_issue_count", 0) or 0) if predict_summary else 0
    fallback_count = int(predict_summary.get("prediction_fallback_count", 0) or 0) if predict_summary else 0
    calibration_fallback_count = int(predict_summary.get("prediction_calibration_fallback_count", 0) or 0) if predict_summary else 0
    return {
        "predict_run_id": str((predict_record or {}).get("entity_run_id") or (predict_record or {}).get("summary_run_id") or "—"),
        "predict_drift_status": str(predict_summary.get("ml_drift_status") or "n/a").strip() if predict_summary else "n/a",
        "predict_kill_switch_active": bool(predict_summary.get("ml_kill_switch_active")) if predict_summary else False,
        "predict_kill_switch_reason": str(predict_summary.get("ml_kill_switch_reason") or "").strip() if predict_summary else "",
        "predict_gate_status": str(predict_summary.get("gate_status") or "enabled").strip() if predict_summary else "enabled",
        "predict_last_served_model": str(predict_summary.get("last_served_model") or "—").strip() if predict_summary else "—",
        "artifact_issue_count": artifact_issue_count,
        "fallback_count": fallback_count,
        "calibration_fallback_count": calibration_fallback_count,
        "last_fallback_reason": str(predict_summary.get("last_fallback_reason") or "").strip() if predict_summary else "",
        "risk_gate_enabled": bool(risk_summary.get("ml_gate_enabled")) if risk_summary and "ml_gate_enabled" in risk_summary else None,
        "risk_gate_reason": str(risk_summary.get("ml_gate_reason") or "").strip() if risk_summary else "",
        "risk_gate_action": str(risk_summary.get("ml_gate_action") or "allow").strip() if risk_summary else "allow",
        "risk_gate_drift_status": str(risk_summary.get("ml_gate_drift_status") or "n/a").strip() if risk_summary else "n/a",
        "risk_prediction_coverage_pct": risk_summary.get("prediction_coverage_pct") if risk_summary else None,
    }


def _summarize_governance_thresholds(artifact_report: dict[str, object] | None) -> dict[str, object]:
    payload = artifact_report.get("governance_thresholds") if isinstance(artifact_report, dict) else None
    if not isinstance(payload, dict):
        return {
            "enabled": False,
            "selection_status": "n/a",
            "selected_threshold": None,
            "min_action_rate": None,
            "max_action_rate": None,
            "min_precision_long": None,
            "selected_action_rate": None,
            "selected_precision_long": None,
            "selected_model_eligible": None,
            "selection_mode": "n/a",
            "selection_reason": "",
        }
    return {
        "enabled": bool(payload.get("enabled", False)),
        "selection_status": str(payload.get("selection_status") or "n/a"),
        "selected_threshold": payload.get("selected_threshold"),
        "min_action_rate": payload.get("min_action_rate"),
        "max_action_rate": payload.get("max_action_rate"),
        "min_precision_long": payload.get("min_precision_long"),
        "selected_action_rate": payload.get("selected_action_rate"),
        "selected_precision_long": payload.get("selected_precision_long"),
        "selected_model_eligible": payload.get("selected_model_eligible"),
        "selection_mode": str(payload.get("selection_mode") or "n/a"),
        "selection_reason": str(payload.get("selection_reason") or ""),
    }


def _prime_selected_symbol_state(symbols: list[str]) -> str | None:
    if not symbols:
        return None

    pending_symbol = st.session_state.pop(ML_PENDING_SELECTED_SYMBOL_KEY, None)
    if isinstance(pending_symbol, str) and pending_symbol in symbols:
        st.session_state[ML_SELECTED_SYMBOL_KEY] = pending_symbol
        return pending_symbol

    selected_symbol = st.session_state.get(ML_SELECTED_SYMBOL_KEY)
    if isinstance(selected_symbol, str) and selected_symbol in symbols:
        return selected_symbol

    st.session_state[ML_SELECTED_SYMBOL_KEY] = symbols[0]
    return symbols[0]


def _render_champion_walk_forward_stability(report: dict[str, object]) -> None:
    stability = report.get("walk_forward_stability")
    if not isinstance(stability, dict):
        return

    st.markdown("**📊 Stabilité Walk-Forward du champion**")
    model = stability.get("selected_model") or report.get("selected_model") or "—"
    horizon = stability.get("selected_horizon")
    horizon_label = f"H{horizon}" if horizon is not None else "horizon non renseigné"
    st.caption(
        f"Champion `{model}` · `{horizon_label}` · source `{stability.get('source') or 'indisponible'}`"
    )

    if not stability.get("available"):
        st.info(
            "Le résumé Walk-Forward existe peut-être, mais le détail par fold n’est pas disponible "
            "dans cet ancien artefact. Un nouvel entraînement est nécessaire pour calculer la stabilité."
        )
        return

    long_summary = stability.get("long") if isinstance(stability.get("long"), dict) else {}
    short_summary = stability.get("short") if isinstance(stability.get("short"), dict) else {}
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Folds évalués", int(stability.get("evaluated_folds") or 0))
    c2.metric("Folds LONG valides", int(long_summary.get("valid_folds") or 0))
    c3.metric("Folds SHORT valides", int(short_summary.get("valid_folds") or 0))
    c4.metric("Diagnostic", str(stability.get("overall_label") or "—"))

    summary_df = stability.get("summary_df")
    if isinstance(summary_df, pd.DataFrame) and not summary_df.empty:
        display_summary = summary_df.rename(columns={
            "side": "Direction",
            "status_label": "Statut",
            "valid_folds": "Folds valides",
            "passing_folds": "Folds F1≥0,35",
            "pass_rate": "Taux folds solides",
            "f1_mean": "F1 moyen",
            "f1_median": "F1 médian",
            "f1_min": "F1 minimum",
            "f1_std": "Écart-type F1",
            "support_total": "Support cumulé",
        })[[
            "Direction", "Statut", "Folds valides", "Folds F1≥0,35",
            "Taux folds solides", "F1 moyen", "F1 médian", "F1 minimum",
            "Écart-type F1", "Support cumulé",
        ]].copy()
        display_summary["Taux folds solides"] = display_summary["Taux folds solides"].map(
            lambda value: f"{float(value):.0%}" if pd.notna(value) else "—"
        )
        for col in ("F1 moyen", "F1 médian", "F1 minimum", "Écart-type F1"):
            display_summary[col] = display_summary[col].map(
                lambda value: round(float(value), 3) if pd.notna(value) else None
            )
        show_dataframe(display_summary, height=150)

    folds_df = stability.get("folds_df")
    if isinstance(folds_df, pd.DataFrame) and not folds_df.empty:
        display_folds = folds_df.rename(columns={
            "fold": "Fold",
            "test_start": "Début test",
            "test_end": "Fin test",
            "test_rows": "Lignes test",
            "n_samples": "Échantillons évalués",
            "f1_macro": "F1 macro",
            "f1_long": "F1 LONG",
            "f1_short": "F1 SHORT",
            "f1_flat": "F1 FLAT",
            "support_long": "Support LONG",
            "support_short": "Support SHORT",
            "long_valid": "Fold LONG valide",
            "short_valid": "Fold SHORT valide",
        })
        wanted = [
            "Fold", "Début test", "Fin test", "Lignes test", "Échantillons évalués",
            "F1 LONG", "Support LONG", "Fold LONG valide",
            "F1 SHORT", "Support SHORT", "Fold SHORT valide", "F1 FLAT", "F1 macro",
        ]
        display_folds = display_folds[[col for col in wanted if col in display_folds.columns]].copy()
        for col in ("F1 LONG", "F1 SHORT", "F1 FLAT", "F1 macro"):
            if col in display_folds.columns:
                display_folds[col] = display_folds[col].map(
                    lambda value: round(float(value), 3) if pd.notna(value) else None
                )
        show_dataframe(display_folds, height=min(420, 70 + 35 * len(display_folds)))

    thresholds = stability.get("thresholds") if isinstance(stability.get("thresholds"), dict) else {}
    with st.expander("ℹ️ Règles du diagnostic de stabilité", expanded=False):
        st.markdown(
            f"""
- Fold valide pour un côté : F1 présent et support estimé ≥ **{thresholds.get('min_side_support', 15)}**.
- Nombre minimal de folds valides : **{thresholds.get('min_valid_folds', 3)}**.
- Fold directionnel solide : F1 ≥ **{thresholds.get('passing_f1', 0.35):.2f}**.
- Direction stable : médiane ≥ **{thresholds.get('stable_median_f1', 0.40):.2f}**, minimum ≥ **{thresholds.get('stable_min_f1', 0.20):.2f}** et au moins **{thresholds.get('stable_pass_rate', 0.60):.0%}** des folds valides solides.

Le support est lu directement lorsqu’il est persisté ; sinon il est estimé avec `n_samples` ou `test_rows` × `true_<side>_pct`.
"""
        )


def render() -> None:
    st.header("🤖 Model Factory — Entraînement & prédictions")
    st.caption(
        "Cette page combine les artefacts `modelFactory` et les tables DB de synthèse/audit "
        "(`model_training_run`, `model_metrics`, `model_governance`, `model_predictions`)."
    )

    st.subheader("🧭 Gouvernance & artefacts de serving")
    artifacts_root = get_model_artifacts_dir()
    artifact_batches = list_ml_artifact_batches(artifacts_root)
    batch_comments: dict[str, str] = {}
    if db_available() and artifact_batches:
        try:
            batch_comments = get_ml_batch_comments(artifact_batches)
        except Exception:
            batch_comments = {}
    if artifact_batches:
        selected_batch = st.selectbox(
            "Campagne d'artefacts",
            options=artifact_batches,
            key=ML_SELECTED_ARTIFACT_BATCH_KEY,
            format_func=lambda batch_id: (
                f"{batch_id} — {batch_comments[batch_id]}"
                if batch_comments.get(batch_id)
                else batch_id
            ),
        )
        artifacts_dir = artifacts_root / selected_batch
        if batch_comments.get(selected_batch):
            st.caption(f"💬 Commentaire du batch : {batch_comments[selected_batch]}")
    else:
        artifacts_dir = artifacts_root
    st.caption(
        f"Cette section lit directement les artefacts `modelFactory` sous `{artifacts_dir}` afin d'exposer le champion servi, les challengers et les routes d'inférence."
    )
    if db_available() and artifact_batches:
        serving_batch = get_serving_batch(get_sqlalchemy_engine())
        promotion_col, serving_status_col = st.columns([1, 2])
        if promotion_col.button("Promouvoir cette campagne pour le serving", key="ml_promote_serving_batch"):
            try:
                set_serving_batch(get_sqlalchemy_engine(), batch_id=selected_batch)
                st.success(f"Campagne de serving active : `{selected_batch}`")
            except Exception as exc:
                st.error(f"Promotion de campagne impossible : {exc}")
        serving_comment = batch_comments.get(str(serving_batch or "").strip())
        serving_label = f"Campagne de serving active : `{serving_batch or 'aucune (fallback historique)'}`"
        if serving_comment:
            serving_label += f" — {serving_comment}"
        serving_status_col.caption(serving_label)

    artifact_symbols = list_ml_artifact_symbols(artifacts_dir)
    db_symbols = get_prediction_symbols() if db_available() else []
    symbols = artifact_symbols or sorted(set(db_symbols), key=lambda sym: (sym.startswith("__"), sym))
    if not symbols:
        st.info("Aucun artefact `modelFactory` détecté pour le moment. Lancez d'abord `ML Train` ou vérifiez le dossier des artefacts.")
        report = None
    else:
        _prime_selected_symbol_state(symbols)
        selected_symbol = st.selectbox(
            "Symbole à inspecter (artefacts)",
            options=symbols,
            format_func=lambda sym: f"{sym} — modèle global" if sym.startswith("__") else sym,
            key=ML_SELECTED_SYMBOL_KEY,
        )
        report = load_ml_artifact_report(selected_symbol, artifacts_dir)
        for error in report["errors"]:
            st.warning(error)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Symbole", str(report["symbol"]))
        col2.metric("Champion servi", str(report["selected_model"] or "—"))
        col3.metric("Mode de sélection", str(report["selection_mode"] or "—"))
        threshold = report["selected_decision_threshold"]
        col4.metric("Decision threshold", f"{float(threshold):.2f}" if threshold is not None else "—")

        if report.get("health_status") == "invalid":
            st.error(
                "🚫 Artefacts locaux invalides — manifestes incomplets/corrompus ou route champion introuvable."
            )
        elif report.get("health_status") == "degraded":
            st.warning(
                f"⚠️ Artefacts locaux dégradés — route sélectionnée `{report.get('selected_model') or '—'}` en état `{report.get('selected_route_health') or 'unknown'}`."
            )
        elif report.get("health_status") == "healthy":
            st.success("✅ Artefacts locaux servables selon les chemins actuellement présents sur disque.")
        selected_route_errors = report.get("selected_route_errors") or []
        if selected_route_errors:
            st.caption("Anomalies de route sélectionnée : " + ", ".join(str(value) for value in selected_route_errors))

        champion = report["champion"] or {}
        st.caption(
            f"Run ID : `{report['run_id'] or '—'}` | "
            f"Métrique champion : `{champion.get('selection_metric', '—')}` | "
            f"Score champion : `{champion.get('selection_score', '—')}`"
        )
        st.caption(
            f"Config : `{report['config_path']}` | Metrics : `{report['metrics_path']}`"
        )

        st.markdown("**Routes d'inférence**")
        show_dataframe(report["routes_df"], height=260)

        st.markdown("**Ranking challengers**")
        show_dataframe(report["ranking_df"], height=260)

        governance_thresholds = _summarize_governance_thresholds(report)
        st.markdown("**Gouvernance seuils / fallback quant-only**")
        gt_col1, gt_col2, gt_col3, gt_col4 = st.columns(4)
        gt_col1.metric("Threshold sélectionné", f"{float(governance_thresholds['selected_threshold']):.2f}" if governance_thresholds["selected_threshold"] is not None else "—")
        gt_col2.metric("Statut sélection", str(governance_thresholds["selection_status"]))
        gt_col3.metric("Min precision", f"{float(governance_thresholds['min_precision_long']):.2f}" if governance_thresholds["min_precision_long"] is not None else "—")
        if governance_thresholds["selected_action_rate"] is not None:
            action_rate_label = f"{float(governance_thresholds['selected_action_rate']):.1%}"
        else:
            action_rate_label = "—"
        gt_col4.metric("Action rate retenu", action_rate_label)
        if governance_thresholds["enabled"]:
            min_action_rate = governance_thresholds["min_action_rate"]
            max_action_rate = governance_thresholds["max_action_rate"]
            min_action_label = f"{float(min_action_rate):.1%}" if min_action_rate is not None else "—"
            max_action_label = f"{float(max_action_rate):.1%}" if max_action_rate is not None else "—"
            st.caption(
                f"Contraintes de gouvernance persistées : action rate [{min_action_label}, {max_action_label}] | "
                f"selection_mode=`{governance_thresholds['selection_mode']}`"
            )
        else:
            st.info("Aucune optimisation de seuil activée dans l'artefact courant : fallback sur le seuil par défaut du modèle.")
        if governance_thresholds["selected_model_eligible"] is False:
            st.warning(
                "Le modèle effectivement servi n'était pas encore éligible selon la gouvernance champion ; un fallback quant-only / champion par défaut peut être attendu côté exploitation."
            )
        if governance_thresholds["selection_reason"]:
            st.caption(f"Raison de sélection : {governance_thresholds['selection_reason']}")

        _render_champion_walk_forward_stability(report)

        attribution_results_df = report.get("attribution_results_df") if isinstance(report.get("attribution_results_df"), pd.DataFrame) else pd.DataFrame()
        attribution_regimes_df = report.get("attribution_regimes_df") if isinstance(report.get("attribution_regimes_df"), pd.DataFrame) else pd.DataFrame()
        if not attribution_results_df.empty:
            st.markdown("**Ablation quant / sentiment / ML**")
            st.caption("Si présent, ce rapport compare l'apport quant-only vs sentiment vs ML, globalement puis par régime de marché.")
            show_dataframe(attribution_results_df, height=220)
            if not attribution_regimes_df.empty:
                st.markdown("**Ablation par régime**")
                show_dataframe(attribution_regimes_df, height=220)

        with st.expander("📄 Manifestes bruts (config / metrics)", expanded=False):
            if report["config"]:
                st.markdown("**config.json**")
                st.code(json.dumps(report["config"], indent=2, default=str), language="json")
            if report["metrics"]:
                st.markdown("**metrics.json**")
                st.code(json.dumps(report["metrics"], indent=2, default=str), language="json")

    if not db_available():
        st.warning("La connexion MySQL est indisponible. Les tableaux SQL ci-dessous ne peuvent pas être chargés, mais la lecture des artefacts locaux reste disponible.")
        render_db_connection_form("ml_db_form")
        return

    st.subheader("🛡️ Drift / gate ML")
    st.caption(
        "Ce panneau croise le dernier résumé `ml_predict` (drift / kill-switch côté serving) et le dernier résumé `risk_management` "
        "(gate effectivement consommé côté risque)."
    )
    latest_predict_summary = get_latest_run_business_summary(step_key="ml_predict")
    latest_risk_summary = get_latest_run_business_summary(step_key="risk_management")
    runtime_status = _summarize_ml_runtime_status(latest_predict_summary, latest_risk_summary)

    status_col_1, status_col_2, status_col_3, status_col_4 = st.columns(4)
    status_col_1.metric("Drift ML Predict", str(runtime_status["predict_drift_status"]))
    status_col_2.metric(
        "Kill-switch Predict",
        "actif" if bool(runtime_status["predict_kill_switch_active"]) else "inactif",
    )
    risk_gate_enabled = runtime_status["risk_gate_enabled"]
    status_col_3.metric(
        "Gate Risk effectif",
        "activé" if risk_gate_enabled is True else ("désactivé" if risk_gate_enabled is False else "n/d"),
    )
    artifact_health_label = str((report or {}).get("health_status") or "n/d") if isinstance(report, dict) else "n/d"
    status_col_4.metric("Santé artefacts", artifact_health_label)

    if risk_gate_enabled is False:
        coverage = runtime_status.get("risk_prediction_coverage_pct")
        coverage_text = f" | couverture ML={float(coverage):.0%}" if isinstance(coverage, (int, float)) else ""
        st.error(
            f"🚫 Gate ML désactivé côté risque — action `{runtime_status['risk_gate_action']}` | drift `{runtime_status['risk_gate_drift_status']}` | raison `{runtime_status['risk_gate_reason'] or 'unknown'}`{coverage_text}"
        )
    elif bool(runtime_status["predict_kill_switch_active"]):
        st.warning(
            f"⚠️ Kill-switch drift déclenché côté `ml_predict` — drift `{runtime_status['predict_drift_status']}` | raison `{runtime_status['predict_kill_switch_reason'] or 'unknown'}`."
        )
    elif str(runtime_status["predict_drift_status"]) not in {"", "n/a", "N/A", "OK"}:
        st.info(
            f"ℹ️ Drift observé côté ML Predict : `{runtime_status['predict_drift_status']}`. Vérifiez l'alignement avec le gate côté risque."
        )

    if int(runtime_status["artifact_issue_count"]) > 0 or int(runtime_status["fallback_count"]) > 0:
        st.caption(
            f"Incidents serving récents — artefacts={runtime_status['artifact_issue_count']} | fallbacks={runtime_status['fallback_count']} | calibrateurs dégradés={runtime_status['calibration_fallback_count']}"
        )
        if runtime_status["last_fallback_reason"]:
            st.caption(f"Dernier fallback serving : {runtime_status['last_fallback_reason']}")

    if latest_predict_summary is not None:
        render_persistent_business_summary(
            latest_predict_summary,
            title="🔮 Dernier résumé ML Predict",
            max_metrics=6,
        )
    else:
        render_query_diagnostic("Aucun résumé persistant `ml_predict` disponible.")

    if latest_risk_summary is not None:
        render_persistent_business_summary(
            latest_risk_summary,
            title="⚖️ Dernier résumé Risk consommateur ML",
            max_metrics=9,
        )
    else:
        render_query_diagnostic("Aucun résumé persistant `risk_management` disponible pour comparer le gate effectif.")

    selected_symbol_for_db = st.session_state.get(ML_SELECTED_SYMBOL_KEY) if symbols else None
    symbol_filter = selected_symbol_for_db if isinstance(selected_symbol_for_db, str) else None

    governance_filter_source = get_model_governance(limit=ML_AUDIT_FILTER_SOURCE_LIMIT, symbol=symbol_filter)
    prediction_audit_filter_source = get_prediction_governance_audit(limit=ML_AUDIT_FILTER_SOURCE_LIMIT, symbol=symbol_filter)
    filter_options = _build_prediction_audit_filter_options(prediction_audit_filter_source, governance_filter_source)

    st.subheader("🎛️ Filtres d'audit DB")
    st.caption(
        "Ces filtres pilotent les vues `model_governance`, l'audit joint `model_predictions ↔ model_governance` "
        "et, quand pertinent, la table des prédictions récentes."
    )
    col1, col2, col3, col4 = st.columns(4)
    selected_link_statuses = col1.multiselect(
        "governance_link_status",
        options=filter_options["governance_link_statuses"],
        key="ml_audit_filter_link_status",
    )
    selected_selection_modes = col2.multiselect(
        "selection_mode",
        options=filter_options["selection_modes"],
        key="ml_audit_filter_selection_mode",
    )
    selected_served_models = col3.multiselect(
        "served_model",
        options=filter_options["served_models"],
        key="ml_audit_filter_served_model",
    )
    selected_run_ids = col4.multiselect(
        "run_id",
        options=filter_options["run_ids"],
        key="ml_audit_filter_run_id",
    )

    # --- Training runs ---
    st.subheader("🏋️ Runs d'entraînement")
    st.caption("Historique des runs `modelFactory` persistés en base, quel que soit le backend finalement servi en inférence.")
    runs = get_training_runs()
    if runs.empty:
        render_query_diagnostic("Aucun run d'entraînement ML trouvé.")
    else:
        render_symbol_table(runs, key="ml_training_runs", symbol_col="symbol", height=300)

    # --- Métriques ---
    st.subheader("📈 Métriques par symbole")
    st.caption("Vue DB résumée par split (`val`, `test`, `wf`). Les comparatifs détaillés challengers/champion sont stockés dans les artefacts disque du symbole.")
    metrics = get_model_metrics()
    if metrics.empty:
        render_query_diagnostic("Aucune métrique ML disponible.")
    else:
        render_symbol_table(metrics, key="ml_metrics_per_symbol", symbol_col="symbol", height=400)

    # --- Gouvernance challengers / champion ---
    st.subheader("🏆 Gouvernance challengers / champion")
    st.caption(
        "La table `model_governance` persiste par run et par symbole le ranking challengers/champion, "
        "le backend d'inférence, l'éligibilité de sélection et les scores utiles à l'audit quotidien."
    )
    governance = get_model_governance(
        limit=ML_AUDIT_FILTER_SOURCE_LIMIT,
        symbol=symbol_filter,
        run_ids=selected_run_ids or None,
        selection_modes=selected_selection_modes or None,
    )
    if governance.empty:
        render_query_diagnostic("Aucune gouvernance ML persistée en base pour le moment.")
    else:
        show_dataframe(governance, height=360)

    preds = get_predictions(
        limit=ML_AUDIT_FILTER_SOURCE_LIMIT,
        symbol=symbol_filter,
        run_ids=selected_run_ids or None,
        served_models=selected_served_models or None,
    )

    # --- Audit serving ↔ gouvernance ---
    st.subheader("🔗 Audit serving ↔ gouvernance")
    st.caption(
        "Cette vue relie chaque ligne de `model_predictions` au snapshot `model_governance` du même `run_id` et `symbol` "
        "afin d'expliquer quel champion a été servi et si la prédiction est alignée avec la gouvernance persistée."
    )
    prediction_audit = get_prediction_governance_audit(
        limit=ML_AUDIT_FILTER_SOURCE_LIMIT,
        symbol=symbol_filter,
        run_ids=selected_run_ids or None,
        selection_modes=selected_selection_modes or None,
        served_models=selected_served_models or None,
        governance_link_statuses=selected_link_statuses or None,
    )
    if prediction_audit.empty:
        render_query_diagnostic("Aucun audit joint prédiction/gouvernance disponible.")
    else:
        audit_summary = _summarize_prediction_governance_audit(prediction_audit)
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Dernier modèle servi", str(audit_summary["latest_served_model"]))
        col2.metric("Champion gouvernance", str(audit_summary["latest_governance_champion"]))
        col3.metric("Statut du lien", str(audit_summary["latest_link_status"]))
        col4.metric("Lignes à investiguer", int(audit_summary["mismatch_count"]))
        if int(audit_summary["mismatch_count"]) > 0:
            st.warning(
                "Certaines prédictions servies ne sont pas parfaitement alignées avec le snapshot de gouvernance persistant. "
                "Vérifiez la colonne `governance_link_status` ci-dessous."
            )
        show_dataframe(prediction_audit, height=360)

        navigation_options = _build_prediction_audit_navigation_options(prediction_audit)
        if navigation_options:
            st.markdown("**Navigation rapide depuis une ligne d'audit**")
            option_by_id = {option["id"]: option for option in navigation_options}
            navigation_ids = list(option_by_id.keys())
            if st.session_state.get(ML_SELECTED_AUDIT_NAVIGATION_KEY) not in option_by_id:
                st.session_state[ML_SELECTED_AUDIT_NAVIGATION_KEY] = navigation_ids[0]
            selected_navigation_id = st.selectbox(
                "Ligne d'audit à détailler",
                options=navigation_ids,
                format_func=lambda option_id: option_by_id[option_id]["label"],
                key=ML_SELECTED_AUDIT_NAVIGATION_KEY,
            )
            selected_navigation = option_by_id[selected_navigation_id]
            target_symbol = _resolve_navigation_symbol(selected_navigation, symbols)
            run_id = selected_navigation["run_id"]
            selection_mode = selected_navigation["selection_mode"]
            served_model = selected_navigation["served_model"]

            col_nav_1, col_nav_2, col_nav_3 = st.columns(3)
            if col_nav_1.button("🔎 Filtrer sur ce run", key="ml_audit_filter_selected_run", use_container_width=True):
                st.session_state["ml_audit_filter_run_id"] = [run_id]
                st.rerun()
            if col_nav_2.button("🧭 Ouvrir l'artefact lié", key="ml_audit_open_artifact", use_container_width=True):
                st.session_state["ml_audit_filter_run_id"] = [run_id]
                if selection_mode and selection_mode != "—":
                    st.session_state["ml_audit_filter_selection_mode"] = [selection_mode]
                if served_model and served_model != "—":
                    st.session_state["ml_audit_filter_served_model"] = [served_model]
                if target_symbol is not None:
                    st.session_state[ML_PENDING_SELECTED_SYMBOL_KEY] = target_symbol
                st.rerun()
            if col_nav_3.button("🏆 Isoler gouvernance + serving", key="ml_audit_focus_governance", use_container_width=True):
                st.session_state["ml_audit_filter_run_id"] = [run_id]
                if selection_mode and selection_mode != "—":
                    st.session_state["ml_audit_filter_selection_mode"] = [selection_mode]
                if served_model and served_model != "—":
                    st.session_state["ml_audit_filter_served_model"] = [served_model]
                st.rerun()

            st.markdown("**Détail du run sélectionné**")
            st.caption(
                f"Run `{run_id}` | symbole DB `{selected_navigation['symbol']}` | "
                f"artefact ciblé `{target_symbol or selected_navigation['artifact_symbol'] or '—'}`"
            )

            run_governance = governance[governance["run_id"] == run_id] if "run_id" in governance.columns else pd.DataFrame()
            run_audit_rows = prediction_audit[prediction_audit["run_id"] == run_id] if "run_id" in prediction_audit.columns else pd.DataFrame()
            ordered_run_audit_rows, focused_audit_row = _focus_dataframe_on_navigation_row(run_audit_rows, selected_navigation)
            run_predictions = preds[preds["run_id"] == run_id] if "run_id" in preds.columns else pd.DataFrame()
            artifact_report_for_navigation = load_ml_artifact_report(target_symbol) if target_symbol is not None else None

            st.markdown("**Focus automatique sur la ligne choisie**")
            if focused_audit_row.empty:
                render_query_diagnostic("La ligne d'audit sélectionnée n'a pas pu être retrouvée dans le tableau filtré.")
            else:
                show_dataframe(focused_audit_row, height=120)

            export_df = _build_ml_run_export_dataframe(
                run_id=run_id,
                focused_audit_row=focused_audit_row,
                run_governance=run_governance,
                run_audit_rows=ordered_run_audit_rows,
                run_predictions=run_predictions,
                artifact_report=artifact_report_for_navigation,
            )
            export_zip_bytes = _build_ml_run_export_zip_bytes(
                export_df=export_df,
                artifact_report=artifact_report_for_navigation,
                focused_audit_row=focused_audit_row,
                selected_navigation=selected_navigation,
                exported_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                run_id=run_id,
                symbol=selected_navigation.get("symbol"),
            )
            st.download_button(
                "📦 Export ZIP du run sélectionné",
                data=export_zip_bytes,
                file_name=_build_ml_run_export_zip_filename(run_id, selected_navigation.get("symbol")),
                mime="application/zip",
                key="ml_selected_run_export_zip",
                use_container_width=True,
            )

            detail_col_1, detail_col_2 = st.columns(2)
            with detail_col_1:
                st.markdown("**Gouvernance du run**")
                if run_governance.empty:
                    render_query_diagnostic("Aucune ligne de gouvernance filtrée pour ce run.")
                else:
                    show_dataframe(run_governance, height=240)
            with detail_col_2:
                st.markdown("**Lignes d'audit du run**")
                if ordered_run_audit_rows.empty:
                    render_query_diagnostic("Aucune ligne d'audit filtrée pour ce run.")
                else:
                    show_dataframe(ordered_run_audit_rows, height=240)

            if target_symbol is not None and artifact_report_for_navigation is not None:
                run_report = artifact_report_for_navigation
                st.markdown("**Artefact ciblé par la navigation**")
                info_col_1, info_col_2, info_col_3, info_col_4 = st.columns(4)
                info_col_1.metric("Artefact symbole", str(run_report["symbol"]))
                info_col_2.metric("Run artefact", str(run_report["run_id"] or "—"))
                info_col_3.metric("Champion artefact", str(run_report["selected_model"] or "—"))
                info_col_4.metric("Mode artefact", str(run_report["selection_mode"] or "—"))
                if run_report["run_id"] and run_report["run_id"] != run_id:
                    st.info(
                        "Le manifeste artefact disponible pour ce symbole ne correspond pas exactement au `run_id` sélectionné. "
                        "Cela indique généralement qu'un run plus récent a remplacé les artefacts de ce symbole."
                    )
                st.caption(f"Config : `{run_report['config_path']}` | Metrics : `{run_report['metrics_path']}`")
            else:
                st.info("Aucun symbole d'artefact local correspondant n'a été trouvé pour cette ligne d'audit.")

    # --- Prédictions ---
    st.subheader("🔮 Prédictions récentes")
    st.caption("La table `model_predictions` contient désormais les champs d'audit de serving utiles au quotidien : `selected_model`, `decision_threshold`, `signal_label`, `calibration_method`.")
    if preds.empty:
        render_query_diagnostic("Aucune prédiction récente disponible.")
    else:
        show_dataframe(preds, height=400)


run_page_if_standalone(__name__, render)


