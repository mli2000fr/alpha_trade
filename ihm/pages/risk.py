"""ihm/pages/risk.py — Décisions de risque et portefeuille cible."""
from __future__ import annotations

import streamlit as st

from ihm.components.run_summary import render_persistent_business_summary
from ihm.pages import run_page_if_standalone
from ihm.components.db_controls import render_db_unavailable, render_query_diagnostic
from ihm.components.symbol_table import render_symbol_table
from ihm.services.db import db_available, get_last_query_error
from ihm.services.queries import get_latest_run_business_summary, get_portfolio_targets, get_risk_decisions, get_risk_run_ids
from ihm.services.run_summary import get_run_summary


def _render_ml_gate_status(record: dict[str, object] | None) -> None:
    summary = get_run_summary(record)
    if not summary or "ml_gate_enabled" not in summary:
        return

    gate_enabled = bool(summary.get("ml_gate_enabled"))
    reason = str(summary.get("ml_gate_reason") or "unknown").strip()
    action = str(summary.get("ml_gate_action") or "allow").strip()
    drift_status = str(summary.get("ml_gate_drift_status") or "n/a").strip()
    prediction_coverage = summary.get("prediction_coverage_pct")
    coverage_text = ""
    if isinstance(prediction_coverage, (int, float)):
        coverage_text = f" | couverture ML={float(prediction_coverage):.0%}"

    if not gate_enabled:
        st.error(
            f"🚫 Gate ML désactivé — action `{action}` | drift `{drift_status}` | raison `{reason}`{coverage_text}"
        )
        if prediction_coverage == 0:
            st.caption(
                "La couverture ML à 0% est attendue ici : `risk_management` a refusé la consommation de `model_predictions`."
            )
        return

    if drift_status == "WARN":
        st.warning(
            f"⚠️ Drift ML en WARN mais gate encore actif — action `{action}` | raison `{reason}`{coverage_text}"
        )
    elif drift_status not in {"", "n/a", "N/A", "OK"}:
        st.info(
            f"ℹ️ Gate ML actif avec drift `{drift_status}` — action `{action}` | raison `{reason}`{coverage_text}"
        )


def render() -> None:
    st.header("⚖️ Risk Management")

    # --- Bannière régime marché (impact direct sur sizing & slots) ---
    try:
        from ihm.components.market_regime_banner import render_market_regime_banner
        render_market_regime_banner(compact=True)
    except Exception:  # pragma: no cover - jamais bloquant
        pass

    if not db_available():
        render_db_unavailable("Risk Management", form_key="risk_db_form")
        return

    # --- Sélecteur de run ---
    run_ids = get_risk_run_ids()
    selected_run = None
    if run_ids:
        selected_run = st.selectbox("Run de risque", ["Dernier run"] + run_ids)
        if selected_run == "Dernier run":
            selected_run = run_ids[0] if run_ids else None
    else:
        if get_last_query_error():
            render_query_diagnostic("Aucun run de risque trouvé dans `risk_decisions`.")
        else:
            st.info("Aucun run de risque trouvé dans `risk_decisions`.")
        return

    summary_record = get_latest_run_business_summary(step_key="risk_management", entity_run_id=selected_run)
    render_persistent_business_summary(
        summary_record,
        max_metrics=9,
    )
    _render_ml_gate_status(summary_record)

    # --- Décisions ---
    st.subheader("📋 Décisions de risque")
    decisions = get_risk_decisions(selected_run)
    if not decisions.empty:
        # Colorisation
        if "decision" in decisions.columns:
            accepted = len(decisions[decisions["decision"].str.upper() == "ACCEPTED"])
            rejected = len(decisions[decisions["decision"].str.upper() == "REJECTED"])
            reduced = len(decisions[decisions["decision"].str.upper() == "REDUCED"])
            c1, c2, c3 = st.columns(3)
            c1.metric("🟢 Acceptés", accepted)
            c2.metric("🟡 Réduits", reduced)
            c3.metric("🔴 Rejetés", rejected)

        # Synthèse par secteur
        if "sector" in decisions.columns and "decision" in decisions.columns:
            with st.expander("Synthèse par secteur"):
                pivot = decisions.groupby(["sector", "decision"]).size().unstack(fill_value=0)
                st.dataframe(pivot, use_container_width=True)

        if "decision_reason" in decisions.columns:
            with st.expander("Motifs de rejet / réduction"):
                reason_counts = decisions.groupby(["decision", "decision_reason"]).size().reset_index(name="count")
                st.dataframe(reason_counts.sort_values(["decision", "count"], ascending=[True, False]), use_container_width=True)

        cols_show = [c for c in [
            "candidate_rank", "decision_rank", "symbol", "decision", "decision_reason", "sector",
            "entry_price", "atr_20", "approved_shares", "target_notional", "target_weight",
            "risk_per_share", "risk_budget_dollars", "initial_risk_dollars",
            "correlation_blocker", "correlation_value",
            "score_snapshot_date", "price_asof_date", "atr_asof_date",
            "prediction_asof_date", "ml_metrics_asof_date",
            "conviction_score", "predicted_proba", "historical_win_rate", "sizing_method",
        ] if c in decisions.columns]
        render_symbol_table(
            decisions[cols_show] if cols_show else decisions,
            key="risk_decisions",
            symbol_col="symbol",
            height=400,
        )
    else:
        render_query_diagnostic("Aucune décision pour ce run.")

    # --- Portefeuille cible ---
    st.subheader("🎯 Portefeuille cible")
    targets = get_portfolio_targets(selected_run)
    if not targets.empty:
        cols_show = [c for c in [
            "decision_rank", "symbol", "shares", "entry_price", "stop_price_initial", "atr_20",
            "risk_per_share", "initial_risk_dollars", "risk_budget_dollars", "target_notional",
            "target_weight", "sector", "price_asof_date", "atr_asof_date",
            "conviction_score", "sizing_method", "kelly_fraction", "score_used", "score_source",
        ] if c in targets.columns]
        render_symbol_table(
            targets[cols_show] if cols_show else targets,
            key="risk_portfolio_targets",
            symbol_col="symbol",
            height=400,
        )
    else:
        render_query_diagnostic("Aucun portefeuille cible pour ce run.")


run_page_if_standalone(__name__, render)

