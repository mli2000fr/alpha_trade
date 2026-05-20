"""ihm/pages/weights_calibration_runs.py — Gouvernance des calibrations empiriques."""
from __future__ import annotations

import json
from collections.abc import Mapping, Sequence

import pandas as pd
import streamlit as st

from ihm.components.db_controls import render_db_unavailable, render_query_diagnostic
from ihm.pages import run_page_if_standalone
from ihm.services.db import db_available, get_last_query_error
from ihm.services.queries import get_weights_calibration_runs, get_weights_calibration_segment_drifts


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
            "eligible_segments": 0,
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
    eligible_segments = 0
    if "eligible_for_live" in df.columns:
        eligible_series = pd.to_numeric(df["eligible_for_live"], errors="coerce").fillna(0)
        eligible_segments = int((eligible_series > 0).sum())
    return {
        "runs": int(len(df)),
        "latest_run_id": str(latest.get("run_id") or "—").strip() or "—",
        "latest_regime": str(latest.get("market_regime_mode") or "all").strip() or "all",
        "latest_metric": metric_label,
        "eligible_segments": eligible_segments,
    }


def render() -> None:
    st.header("🧮 Weights Calibration Runs")
    st.caption(
        "Historique des calibrations empiriques conviction / sentiment / risk, incluant la segmentation par régime, horizon et fenêtre."
    )

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

    horizon_options = ["Tous"]
    if "horizon_days" in history.columns:
        horizon_values = sorted(
            {
                int(value)
                for value in pd.to_numeric(history["horizon_days"], errors="coerce").dropna().tolist()
            }
        )
        horizon_options.extend([f"{value}j" for value in horizon_values])
    selected_horizon = st.selectbox("Horizon", horizon_options)

    lookback_options = ["Tous"]
    if "lookback_months" in history.columns:
        lookback_values = sorted(
            {
                int(value)
                for value in pd.to_numeric(history["lookback_months"], errors="coerce").dropna().tolist()
            }
        )
        lookback_options.extend([f"{value}m" for value in lookback_values])
    selected_lookback = st.selectbox("Fenêtre", lookback_options)

    live_promotion_label = st.selectbox("Promotion live", ["Tous", "Promus", "Bloqués"], index=0)

    filtered = history.copy()
    if selected_regime != "Tous" and "market_regime_mode" in filtered.columns:
        filtered = filtered.loc[
            filtered["market_regime_mode"].fillna("all").astype(str).str.strip().str.lower()
            == selected_regime.lower()
        ].reset_index(drop=True)
    if selected_horizon != "Tous" and "horizon_days" in filtered.columns:
        horizon_value = int(selected_horizon.removesuffix("j"))
        filtered = filtered.loc[
            pd.to_numeric(filtered["horizon_days"], errors="coerce").fillna(-1).astype(int) == horizon_value
        ].reset_index(drop=True)
    if selected_lookback != "Tous" and "lookback_months" in filtered.columns:
        lookback_value = int(selected_lookback.removesuffix("m"))
        filtered = filtered.loc[
            pd.to_numeric(filtered["lookback_months"], errors="coerce").fillna(-1).astype(int) == lookback_value
        ].reset_index(drop=True)
    if live_promotion_label != "Tous" and "eligible_for_live" in filtered.columns:
        eligible_mask = pd.to_numeric(filtered["eligible_for_live"], errors="coerce").fillna(0) > 0
        filtered = filtered.loc[eligible_mask if live_promotion_label == "Promus" else ~eligible_mask].reset_index(drop=True)

    metrics = _build_overview_metrics(filtered)
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Runs", metrics["runs"])
    col2.metric("Dernier run", metrics["latest_run_id"])
    col3.metric("Dernier régime", metrics["latest_regime"])
    col4.metric("Dernière métrique", metrics["latest_metric"])
    col5.metric("Segments promus", metrics["eligible_segments"])

    run_ids = [str(value).strip() for value in filtered.get("run_id", pd.Series(dtype=str)).tolist() if str(value).strip()]
    selected_run = st.selectbox("Run de calibration", run_ids, index=0 if run_ids else None)

    st.subheader("📚 Historique")
    table_columns = [
        column
        for column in [
            "run_id",
            "calibrated_at",
            "calibration_batch_id",
            "scope",
            "market_regime_mode",
            "segment_key",
            "horizon_days",
            "lookback_months",
            "eligible_for_live",
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
            "calibration_batch_id",
            "scope",
            "market_regime_mode",
            "segment_key",
            "horizon_days",
            "lookback_months",
            "distinct_snapshot_days",
            "distinct_symbols",
            "eligible_for_live",
            "eligibility_reason",
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

    calibration_batch_id = str(selected_row.get("calibration_batch_id") or "").strip() or None
    if calibration_batch_id:
        drifts_df = get_weights_calibration_segment_drifts(
            calibration_batch_id=calibration_batch_id,
            source_run_id=str(selected_row.get("run_id") or "").strip() or None,
            limit=50,
        )
        if not drifts_df.empty:
            with st.expander("📉 Drifts inter-segments", expanded=False):
                st.dataframe(drifts_df, use_container_width=True, hide_index=True)


run_page_if_standalone(__name__, render)


