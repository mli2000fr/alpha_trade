"""ihm/pages/execution.py — Suivi des runs d'exécution."""
from __future__ import annotations

import streamlit as st

from ihm.pages import run_page_if_standalone
from ihm.components.db_controls import render_db_unavailable, render_query_diagnostic
from ihm.components.metrics import metric_row
from ihm.components.run_summary import render_persistent_business_summary
from ihm.components.status_badges import run_status_badge
from ihm.components.tables import show_dataframe
from ihm.services.db import db_available
from ihm.services.queries import (
    get_latest_run_business_summary,
    get_execution_account_constraints,
    get_execution_orders,
    get_broker_positions,
    get_execution_events,
    get_execution_fills,
    get_execution_runs,
    get_portfolio_targets,
)
from ihm.services.run_summary import get_run_summary


def render() -> None:
    st.header("🚀 Execution Engine")

    if not db_available():
        render_db_unavailable("Execution Engine", form_key="execution_db_form")
        return

    account_id = st.session_state.get("selected_account_id")
    runs = get_execution_runs(account_id=account_id)
    if runs.empty:
        render_query_diagnostic("Aucun run d'exécution trouvé.")
        return

    # --- Sélection du run ---
    run_ids = runs["exec_run_id"].tolist()
    selected = st.selectbox("Run d'exécution", run_ids)

    row = runs[runs["exec_run_id"] == selected].iloc[0]
    status = str(row.get("status", ""))
    summary_record = get_latest_run_business_summary(step_key="execution", entity_run_id=selected, account_id=account_id)

    # --- KPI ---
    metric_row([
        ("Statut", run_status_badge(status), None),
        ("Cibles", int(row.get("total_targets", 0)), None),
        ("Soumis", int(row.get("total_submitted", 0)), None),
        ("Remplis", int(row.get("total_filled", 0)), None),
    ])

    render_persistent_business_summary(summary_record, max_metrics=9)

    summary = get_run_summary(summary_record)
    if summary:
        st.subheader("🛡️ Protections et indicateurs de risque")
        metric_row([
            ("Stops broker", int(summary.get("targets_with_broker_initial_stop", 0) or 0), None),
            ("Éligibles trail dyn.", int(summary.get("targets_eligible_for_dynamic_trailing", 0) or 0), None),
            ("Trailing activés", int(summary.get("dynamic_trailing_activations", 0) or 0), None),
            ("Fallback trailing", int(summary.get("targets_with_trailing_fallback", 0) or 0), None),
            ("Stops soumis", int(summary.get("child_initial_stop_orders_submitted", 0) or 0), None),
            ("Trails soumis", int(summary.get("child_trailing_stop_orders_submitted", 0) or 0), None),
            ("Checks trigger", int(summary.get("dynamic_trailing_trigger_checks", 0) or 0), None),
            ("Timeouts trail dyn.", int(summary.get("dynamic_trailing_timeouts", 0) or 0), None),
            ("Annulations KO", int(summary.get("dynamic_trailing_cancel_failures", 0) or 0), None),
            ("Cibles stale", int(summary.get("stale_price_targets", 0) or 0), None),
            ("Échecs protections", int(summary.get("child_order_submit_failures", 0) or 0), None),
        ])
        st.caption(
            "Notional cible = `{}` | Risque initial = `{}` | Budget risque = `{}` | Stops prêts = `{}`".format(
                summary.get("total_target_notional", 0.0),
                summary.get("total_initial_risk_dollars", 0.0),
                summary.get("total_risk_budget_dollars", 0.0),
                summary.get("targets_with_risk_controls", 0),
            )
        )

    if row.get("error_message"):
        st.error(f"Erreur : {row['error_message']}")

    constraints = get_execution_account_constraints(selected)
    if constraints:
        st.subheader("⚖️ Contraintes de compte appliquées")
        account_type = str(constraints.get("account_type", "—") or "—")
        effective_pdt_rule = str(constraints.get("effective_pdt_rule", "—") or "—")
        swing_only = bool(constraints.get("swing_only", False))
        equity = constraints.get("equity")
        buying_power = constraints.get("buying_power_available")
        settled_cash = constraints.get("settled_cash_available")
        daytrade_count = constraints.get("daytrade_count")
        remaining_slots = constraints.get("remaining_day_trade_slots")

        metric_row([
            ("Type de compte", account_type, None),
            ("PDT effectif", effective_pdt_rule, None),
            ("Mode swing uniquement", "Oui" if swing_only else "Non", None),
            ("Day trades restants", int(remaining_slots or 0), None),
        ])
        st.caption(
            f"Capital = `{equity}` | Pouvoir d'achat = `{buying_power}` | Trésorerie réglée = `{settled_cash}` | Day trades broker = `{daytrade_count}`"
        )
        message = str(constraints.get("message", "") or "").strip()
        if message:
            st.info(message)

    # --- Runs récents ---
    with st.expander("Historique des runs", expanded=False):
        show_dataframe(runs, height=300)

    # --- Événements ---
    st.subheader("📝 Événements")
    events = get_execution_events(selected)
    show_dataframe(events, height=300)

    # --- Ordres d'exécution / protections ---
    orders = get_execution_orders(selected)
    if not orders.empty:
        st.subheader("📋 Ordres soumis")
        show_dataframe(orders, height=260)

        if "parent_intent_id" in orders.columns:
            child_orders = orders[orders["parent_intent_id"].notna()].copy()
            if not child_orders.empty:
                st.subheader("🧷 Ordres enfants et protections")
                protection_counts = child_orders.groupby(["intent_role", "order_type", "status"]).size().reset_index(name="count")
                show_dataframe(protection_counts, height=180)
                protection_columns = [
                    column for column in [
                        "symbol", "intent_role", "order_type", "status", "qty",
                        "limit_price", "stop_price", "trail_percent", "broker_order_id", "created_at",
                    ]
                    if column in child_orders.columns
                ]
                show_dataframe(child_orders[protection_columns], height=260)

    # --- Fills ---
    st.subheader("💰 Exécutions")
    fills = get_execution_fills(selected)
    if not fills.empty and "slippage_bps" in fills.columns:
        avg_slip = fills["slippage_bps"].mean()
        st.metric("Slippage moyen (bps)", f"{avg_slip:.1f}")
    show_dataframe(fills, height=300)

    risk_run_id = str(row.get("risk_run_id", "") or "").strip()
    if risk_run_id:
        source_targets = get_portfolio_targets(run_id=risk_run_id)
        if not source_targets.empty:
            st.subheader("🎯 Cibles source et paramètres risque")
            target_columns = [
                column for column in [
                    "symbol", "decision_rank", "shares", "entry_price", "target_weight",
                    "stop_price_initial", "risk_per_share", "risk_budget_dollars", "initial_risk_dollars",
                    "target_notional", "price_asof_date", "atr_asof_date",
                ]
                if column in source_targets.columns
            ]
            show_dataframe(source_targets[target_columns], height=260)

    # --- Positions broker ---
    st.subheader("📦 Positions broker — dernier snapshot")
    show_dataframe(get_broker_positions(account_id=account_id), height=300)


run_page_if_standalone(__name__, render)


