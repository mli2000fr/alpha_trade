"""ihm/pages/weights_calibration_runs.py — Gouvernance des calibrations empiriques."""
from __future__ import annotations

import json
from collections.abc import Mapping, Sequence

import pandas as pd
import streamlit as st

from ihm.components.db_controls import render_db_unavailable, render_query_diagnostic
from ihm.pages import run_page_if_standalone
from ihm.services.db import db_available, get_last_query_error
from ihm.services.queries import get_weights_calibration_runs


def _parse_json_payload(value: object) -> dict[str, object] | list[object]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, list):
        return list(value)
    text_value = str(value or "").strip()
    if not text_value:
        return {}
    try:
        parsed = json.loads(text_value)
    except Exception:
        return {}
    if isinstance(parsed, dict):
        return parsed
    if isinstance(parsed, list):
        return parsed
    return {}


def _build_candidates_frame(value: object) -> pd.DataFrame:
    payload = _parse_json_payload(value)
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        return pd.DataFrame()
    rows: list[dict[str, object]] = []
    for item in payload:
        if not isinstance(item, Mapping):
            continue
        row = {key: item.get(key) for key in item}
        weights = item.get("weights")
        if isinstance(weights, Mapping):
            for key, weight_value in weights.items():
                row[str(key)] = weight_value
        rows.append(row)
    return pd.DataFrame(rows)


def _build_overview_metrics(df: pd.DataFrame) -> dict[str, object]:
    if df.empty:
        return {
            "runs": 0,
            "latest_run_id": "—",
            "latest_regime": "—",
            "latest_metric": "—",
        }
    latest = df.iloc[0]
    metric_name = str(latest.get("metric_name") or "unknown").strip()
    metric_value = latest.get("metric_value")
    metric_label = metric_name
    try:
        if metric_value not in (None, ""):
            metric_label = f"{metric_name}={float(metric_value):.4f}"
    except (TypeError, ValueError):
        pass
    return {
        "runs": int(len(df)),
        "latest_run_id": str(latest.get("run_id") or "—").strip() or "—",
        "latest_regime": str(latest.get("market_regime_mode") or "all").strip() or "all",
        "latest_metric": metric_label,
    }


def render() -> None:
    st.header("🧮 Weights Calibration Runs")
    st.caption("Historique des calibrations empiriques conviction / sentiment / risk, incluant la segmentation par régime marché.")

    if not db_available():
        render_db_unavailable("Weights Calibration Runs", form_key="weights_calibration_runs_db_form")
        return

    scope_labels = {
        "Tous": None,
        "risk": "risk",
        "conviction": "conviction",
        "sentiment": "sentiment",
    }
    selected_scope_label = st.selectbox("Scope", list(scope_labels), index=1)
    selected_scope = scope_labels[selected_scope_label]

    history = get_weights_calibration_runs(scope=selected_scope, limit=200)
    if history.empty:
        if get_last_query_error():
            render_query_diagnostic("Aucun run trouvé dans `weights_calibration_runs`.")
        else:
            st.info("Aucun run trouvé dans `weights_calibration_runs`.")
        return

    regime_options = ["Tous"]
    if "market_regime_mode" in history.columns:
        regime_values = sorted(
            {
                str(value).strip() or "all"
                for value in history["market_regime_mode"].fillna("all").tolist()
            }
        )
        regime_options.extend([value for value in regime_values if value not in regime_options])
    selected_regime = st.selectbox("Régime marché", regime_options)

    filtered = history.copy()
    if selected_regime != "Tous" and "market_regime_mode" in filtered.columns:
        filtered = filtered.loc[
            filtered["market_regime_mode"].fillna("all").astype(str).str.strip().str.lower()
            == selected_regime.lower()
        ].reset_index(drop=True)

    metrics = _build_overview_metrics(filtered)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Runs", metrics["runs"])
    col2.metric("Dernier run", metrics["latest_run_id"])
    col3.metric("Dernier régime", metrics["latest_regime"])
    col4.metric("Dernière métrique", metrics["latest_metric"])

    run_ids = [str(value).strip() for value in filtered.get("run_id", pd.Series(dtype=str)).tolist() if str(value).strip()]
    selected_run = st.selectbox("Run de calibration", run_ids, index=0 if run_ids else None)

    st.subheader("📚 Historique")
    table_columns = [
        column
        for column in [
            "run_id",
            "calibrated_at",
            "scope",
            "market_regime_mode",
            "window_start",
            "window_end",
            "metric_name",
            "metric_value",
            "observations_evaluated",
            "scenarios_evaluated",
            "final_value",
            "total_return_pct",
            "sharpe_ratio",
            "max_drawdown_pct",
        ]
        if column in filtered.columns
    ]
    st.dataframe(filtered[table_columns] if table_columns else filtered, use_container_width=True, hide_index=True)

    if not selected_run:
        return
    details_df = filtered.loc[filtered["run_id"].astype(str) == selected_run]
    if details_df.empty:
        st.info("Run introuvable dans le filtre courant.")
        return

    selected_row = details_df.iloc[0]
    st.subheader("🔎 Détail du run")
    detail_columns = [
        column
        for column in [
            "run_id",
            "scope",
            "market_regime_mode",
            "window_start",
            "window_end",
            "metric_name",
            "metric_value",
            "observations_evaluated",
            "scenarios_evaluated",
            "latest_best_scenario_name",
            "final_value",
            "total_return_pct",
            "sharpe_ratio",
            "max_drawdown_pct",
            "artifact_dir",
            "git_sha",
            "schema_version",
        ]
        if column in details_df.columns
    ]
    if detail_columns:
        st.dataframe(details_df[detail_columns], use_container_width=True, hide_index=True)

    best_weights = _parse_json_payload(selected_row.get("best_weights"))
    if isinstance(best_weights, dict) and best_weights:
        with st.expander("⚙️ Best weights", expanded=True):
            st.json(best_weights)

    candidates_df = _build_candidates_frame(selected_row.get("candidates"))
    if not candidates_df.empty:
        with st.expander("🧪 Candidats évalués", expanded=False):
            st.dataframe(candidates_df, use_container_width=True, hide_index=True)


run_page_if_standalone(__name__, render)


