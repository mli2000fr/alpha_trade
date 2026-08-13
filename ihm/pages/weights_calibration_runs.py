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


def _prepare_drift_frames(
    df: pd.DataFrame,
    *,
    selected_run_id: str | None = None,
) -> dict[str, pd.DataFrame]:
    if df.empty:
        empty = pd.DataFrame()
        return {"all": empty, "selected": empty, "summary": empty}

    prepared = df.copy()
    for column in ("metric_delta", "final_value_drift_pct"):
        if column in prepared.columns:
            prepared[column] = pd.to_numeric(prepared[column], errors="coerce")
            prepared[f"abs_{column}"] = prepared[column].abs()
    sort_columns = [
        column
        for column in ["abs_final_value_drift_pct", "abs_metric_delta", "compared_at"]
        if column in prepared.columns
    ]
    ascending = [False] * len(sort_columns)
    if sort_columns:
        prepared = prepared.sort_values(by=sort_columns, ascending=ascending, kind="mergesort").reset_index(drop=True)

    selected = prepared
    if selected_run_id and "source_run_id" in prepared.columns:
        selected = prepared.loc[prepared["source_run_id"].astype(str) == str(selected_run_id)].reset_index(drop=True)

    summary = pd.DataFrame()
    if "comparison_kind" in prepared.columns:
        grouped = prepared.groupby("comparison_kind", dropna=False)
        summary = grouped.size().rename("drift_rows").to_frame().reset_index()
        if "abs_metric_delta" in prepared.columns:
            summary = summary.merge(
                grouped["abs_metric_delta"].max().rename("max_abs_metric_delta").reset_index(),
                on="comparison_kind",
                how="left",
            )
        if "abs_final_value_drift_pct" in prepared.columns:
            summary = summary.merge(
                grouped["abs_final_value_drift_pct"].max().rename("max_abs_final_value_drift_pct").reset_index(),
                on="comparison_kind",
                how="left",
            )
        if "compared_at" in prepared.columns:
            summary = summary.merge(
                grouped["compared_at"].max().rename("latest_compared_at").reset_index(),
                on="comparison_kind",
                how="left",
            )
        summary = summary.sort_values(by=["drift_rows", "comparison_kind"], ascending=[False, True], kind="mergesort")

    return {"all": prepared, "selected": selected, "summary": summary.reset_index(drop=True)}


def _build_drift_metrics(df: pd.DataFrame) -> dict[str, object]:
    if df.empty:
        return {
            "drift_rows": 0,
            "comparison_kinds": 0,
            "max_abs_metric_delta": None,
            "max_abs_final_value_drift_pct": None,
        }
    max_abs_metric_delta = None
    if "abs_metric_delta" in df.columns:
        metric_series = pd.to_numeric(df["abs_metric_delta"], errors="coerce").dropna()
        if not metric_series.empty:
            max_abs_metric_delta = float(metric_series.max())
    max_abs_final_value_drift_pct = None
    if "abs_final_value_drift_pct" in df.columns:
        final_value_series = pd.to_numeric(df["abs_final_value_drift_pct"], errors="coerce").dropna()
        if not final_value_series.empty:
            max_abs_final_value_drift_pct = float(final_value_series.max())
    comparison_kinds = 0
    if "comparison_kind" in df.columns:
        comparison_kinds = int(df["comparison_kind"].fillna("unknown").astype(str).nunique())
    return {
        "drift_rows": int(len(df)),
        "comparison_kinds": comparison_kinds,
        "max_abs_metric_delta": max_abs_metric_delta,
        "max_abs_final_value_drift_pct": max_abs_final_value_drift_pct,
    }


def _build_drift_chart_frames(
    all_drifts: pd.DataFrame,
    *,
    selected_drifts: pd.DataFrame | None = None,
) -> dict[str, pd.DataFrame]:
    summary_chart = pd.DataFrame()
    if not all_drifts.empty and "comparison_kind" in all_drifts.columns:
        summary_chart = all_drifts.copy()
        aggregation: dict[str, str] = {}
        if "abs_metric_delta" in summary_chart.columns:
            aggregation["abs_metric_delta"] = "max"
        if "abs_final_value_drift_pct" in summary_chart.columns:
            aggregation["abs_final_value_drift_pct"] = "max"
        if aggregation:
            summary_chart = (
                summary_chart.groupby("comparison_kind", dropna=False)
                .agg(aggregation)
                .rename(
                    columns={
                        "abs_metric_delta": "max_abs_metric_delta",
                        "abs_final_value_drift_pct": "max_abs_final_value_drift_pct",
                    }
                )
                .sort_index()
            )
        else:
            summary_chart = pd.DataFrame(index=sorted(all_drifts["comparison_kind"].dropna().astype(str).unique().tolist()))

    detail_source = selected_drifts if selected_drifts is not None and not selected_drifts.empty else all_drifts
    detail_chart = pd.DataFrame()
    metric_direction_chart = pd.DataFrame()
    final_value_direction_chart = pd.DataFrame()
    timeline_chart = pd.DataFrame()
    if not detail_source.empty:
        detail_chart = detail_source.copy()
        label_source = detail_chart.get("target_segment_key")
        if label_source is None or label_source.isna().all():
            label_source = detail_chart.get("source_segment_key")
        if label_source is not None:
            detail_chart["drift_label"] = label_source.fillna("unknown").astype(str)
        else:
            detail_chart["drift_label"] = detail_chart.index.astype(str)
        value_columns = [
            column
            for column in ["metric_delta", "final_value_drift_pct"]
            if column in detail_chart.columns
        ]
        if value_columns:
            detail_chart = detail_chart[["drift_label", *value_columns]].drop_duplicates(subset=["drift_label"]).set_index("drift_label")
        detailed_labels = detail_source.copy()
        target_label_source = detailed_labels.get("target_segment_key")
        if target_label_source is None or target_label_source.isna().all():
            target_label_source = detailed_labels.get("source_segment_key")
        comparison_label_source = detailed_labels.get("comparison_kind")
        if target_label_source is not None:
            detailed_labels["chart_label"] = target_label_source.fillna("unknown").astype(str)
            if comparison_label_source is not None:
                detailed_labels["chart_label"] = (
                    comparison_label_source.fillna("unknown").astype(str)
                    + " | "
                    + detailed_labels["chart_label"]
                )
        else:
            detailed_labels["chart_label"] = detailed_labels.index.astype(str)
        if "metric_delta" in detailed_labels.columns:
            metric_direction_chart = (
                detailed_labels[["chart_label", "metric_delta"]]
                .drop_duplicates(subset=["chart_label"])
                .set_index("chart_label")
            )
            metric_direction_chart = metric_direction_chart.reindex(
                metric_direction_chart["metric_delta"].abs().sort_values(ascending=False).index
            )
        if "final_value_drift_pct" in detailed_labels.columns:
            final_value_direction_chart = (
                detailed_labels[["chart_label", "final_value_drift_pct"]]
                .drop_duplicates(subset=["chart_label"])
                .set_index("chart_label")
            )
            final_value_direction_chart = final_value_direction_chart.reindex(
                final_value_direction_chart["final_value_drift_pct"].abs().sort_values(ascending=False).index
            )
    timeline_source = detail_source if selected_drifts is not None and not detail_source.empty else all_drifts
    if not timeline_source.empty and "compared_at" in timeline_source.columns:
        timeline = timeline_source.copy()
        timeline["compared_at"] = pd.to_datetime(timeline["compared_at"], errors="coerce")
        timeline = timeline.dropna(subset=["compared_at"])
        timeline_value_columns = [
            column
            for column in ["metric_delta", "final_value_drift_pct"]
            if column in timeline.columns
        ]
        if not timeline.empty and timeline_value_columns:
            timeline_chart = (
                timeline.groupby("compared_at", dropna=False)[timeline_value_columns]
                .mean()
                .sort_index()
            )
    return {
        "summary_chart": summary_chart,
        "detail_chart": detail_chart,
        "metric_direction_chart": metric_direction_chart,
        "final_value_direction_chart": final_value_direction_chart,
        "timeline_chart": timeline_chart,
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

    # ── Gouvernance live : activation/désactivation du run sélectionné ──
    if "eligible_for_live" in details_df.columns:
        _is_eligible = pd.to_numeric(details_df["eligible_for_live"], errors="coerce").fillna(0).iloc[0] > 0
        gov_col1, gov_col2 = st.columns([1, 2])
        with gov_col1:
            if _is_eligible:
                st.success("✅ Éligible live — activable par le fallback `empirical_calibration`.")
                _deactivate = st.button(
                    "🔒 Bloquer pour le live",
                    key="weights_cal_deactivate_live",
                    type="secondary",
                )
                if _deactivate:
                    from ihm.services.queries import set_weights_calibration_live_eligibility

                    if set_weights_calibration_live_eligibility(
                        run_id=str(selected_run),
                        eligible=False,
                        reason="Désactivé manuellement via IHM (gouvernance calibrations)",
                    ):
                        st.cache_data.clear()
                        st.success(f"Run `{selected_run}` bloqué pour le live.")
                        st.rerun()
                    else:
                        st.error("Échec de l'écriture en DB.")
            else:
                st.warning("⛔ Non éligible live.")
                _activate = st.button(
                    "✅ Promouvoir pour le live",
                    key="weights_cal_activate_live",
                    type="primary",
                    help="Vérifie d'abord la validation OOS : un run in-sample ne doit pas être activé.",
                )
                if _activate:
                    from ihm.services.queries import set_weights_calibration_live_eligibility

                    if set_weights_calibration_live_eligibility(
                        run_id=str(selected_run),
                        eligible=True,
                        reason="Promu manuellement via IHM (gouvernance calibrations)",
                    ):
                        st.cache_data.clear()
                        st.success(f"Run `{selected_run}` promu pour le live.")
                        st.rerun()
                    else:
                        st.error("Échec de l'écriture en DB.")
        with gov_col2:
            st.caption(
                "Le live consomme les runs éligibles via `risk_management.empirical_calibration.fallback_levels` "
                "du config.yaml (résolution par segment/régime/horizon). Bloquer désactive immédiatement le fallback vers ce run."
            )

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
            limit=200,
        )
        if not drifts_df.empty:
            drift_frames = _prepare_drift_frames(
                drifts_df,
                selected_run_id=str(selected_row.get("run_id") or "").strip() or None,
            )
            drift_metrics = _build_drift_metrics(drift_frames["selected"] if not drift_frames["selected"].empty else drift_frames["all"])
            drift_col1, drift_col2, drift_col3, drift_col4 = st.columns(4)
            drift_col1.metric("Drifts batch", drift_metrics["drift_rows"])
            drift_col2.metric("Types", drift_metrics["comparison_kinds"])
            drift_col3.metric(
                "Max |Δ métrique|",
                f"{float(drift_metrics['max_abs_metric_delta']):.4f}"
                if drift_metrics["max_abs_metric_delta"] is not None
                else "—",
            )
            drift_col4.metric(
                "Max |Δ final_value|",
                f"{float(drift_metrics['max_abs_final_value_drift_pct']):.2%}"
                if drift_metrics["max_abs_final_value_drift_pct"] is not None
                else "—",
            )
            with st.expander("📉 Drifts inter-segments", expanded=False):
                chart_frames = _build_drift_chart_frames(
                    drift_frames["all"],
                    selected_drifts=drift_frames["selected"],
                )
                tab_summary, tab_run, tab_timeline, tab_tables = st.tabs(
                    ["Synthèse", "Run sélectionné", "Timeline", "Tables"]
                )
                with tab_summary:
                    if not chart_frames["summary_chart"].empty:
                        st.caption("Amplitude absolue max par type de comparaison")
                        st.bar_chart(chart_frames["summary_chart"], use_container_width=True)
                    if not drift_frames["summary"].empty:
                        st.caption("Synthèse tabulaire par type de comparaison")
                        st.dataframe(drift_frames["summary"], use_container_width=True, hide_index=True)
                with tab_run:
                    if not chart_frames["metric_direction_chart"].empty:
                        st.caption("Δ métrique signé par segment de comparaison")
                        st.bar_chart(chart_frames["metric_direction_chart"], use_container_width=True)
                    if not chart_frames["final_value_direction_chart"].empty:
                        st.caption("Δ final_value signé par segment de comparaison")
                        st.bar_chart(chart_frames["final_value_direction_chart"], use_container_width=True)
                    if not chart_frames["detail_chart"].empty:
                        st.caption("Vue consolidée des dérives du run sélectionné")
                        st.bar_chart(chart_frames["detail_chart"], use_container_width=True)
                    elif "source_run_id" in drift_frames["all"].columns:
                        st.info("Aucun drift directement rattaché au run sélectionné dans ce batch ; affichage du batch complet dans les autres onglets.")
                with tab_timeline:
                    if not chart_frames["timeline_chart"].empty:
                        st.caption("Évolution moyenne des drifts sur le batch")
                        st.line_chart(chart_frames["timeline_chart"], use_container_width=True)
                    else:
                        st.info("Timeline indisponible : la colonne `compared_at` ou les métriques de drift sont absentes.")
                with tab_tables:
                    if not drift_frames["selected"].empty:
                        st.caption("Drifts reliés au run sélectionné")
                        st.dataframe(drift_frames["selected"], use_container_width=True, hide_index=True)
                    st.caption("Batch complet trié par ampleur de dérive")
                    st.dataframe(drift_frames["all"], use_container_width=True, hide_index=True)


run_page_if_standalone(__name__, render)


