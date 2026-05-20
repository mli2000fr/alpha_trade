"""ihm/pages/execution.py — Suivi des runs d'exécution."""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from ihm.pages import run_page_if_standalone
from ihm.components.db_controls import render_db_unavailable, render_query_diagnostic
from ihm.components.metrics import metric_row
from ihm.components.ops_command_panel import render_ops_command_panel
from ihm.components.run_summary import render_persistent_business_summary
from ihm.components.status_badges import heartbeat_badge, run_status_badge
from ihm.components.symbol_table import render_symbol_table
from ihm.components.tables import show_dataframe
from ihm.services.db import db_available
from ihm.services.queries import get_broker_positions
from ihm.services.queries import get_execution_account_constraints
from ihm.services.queries import get_execution_events
from ihm.services.queries import get_execution_fills
from ihm.services.queries import get_execution_orders
from ihm.services.queries import get_execution_position_lots
from ihm.services.queries import get_execution_positions
from ihm.services.queries import get_execution_reconciliation_results
from ihm.services.queries import get_execution_runs
from ihm.services.queries import get_execution_targets_snapshot
from ihm.services.queries import get_latest_execution_protection_watch_service_summary
from ihm.services.queries import get_latest_run_business_summary
from ihm.services.run_summary import get_run_summary


def _reconciliation_status_badge(status: object) -> str:
    normalized = str(status or "").strip().upper()
    if normalized == "BLOCKED":
        return "🔴 BLOCKED"
    if normalized == "MANUAL_REVIEW":
        return "🟡 MANUAL_REVIEW"
    if normalized == "SAFE_AUTO":
        return "🟢 SAFE_AUTO"
    return f"⚪ {normalized or 'UNKNOWN'}"


def _prepare_reconciliation_display(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    prepared = df.copy()
    if "reconciliation_status" in prepared.columns:
        prepared.insert(
            0,
            "status_badge",
            prepared["reconciliation_status"].map(_reconciliation_status_badge),
        )
    if "has_open_protection" in prepared.columns:
        prepared["has_open_protection"] = prepared["has_open_protection"].map(lambda value: "Oui" if bool(value) else "Non")
    return prepared


def _show_position_lots_table(df: pd.DataFrame, *, title: str, height: int = 260) -> None:
    if df.empty:
        return
    lot_columns = [
        column for column in [
            "symbol", "opened_qty", "remaining_qty", "entry_price", "opened_at",
            "lot_status", "closed_at", "exit_price", "open_exec_run_id", "close_exec_run_id",
        ]
        if column in df.columns
    ]
    show_dataframe(df[lot_columns], title=title, height=height)


# ---------------------------------------------------------------------------
# Sprint S3 / A-014 — alerte réconciliation avec diffs > 24h
# ---------------------------------------------------------------------------

_RECON_UNRESOLVED_STATUSES = {"BLOCKED", "MANUAL_REVIEW"}
_RECON_ALERT_THRESHOLD_HOURS = 24


def _render_reconciliation_age_warning(reconciliation: pd.DataFrame) -> None:
    """Affiche un warning Streamlit si des diffs de réconciliation non résolus
    ont une colonne ``created_at`` vieille de plus de ``_RECON_ALERT_THRESHOLD_HOURS``.
    """
    if "created_at" not in reconciliation.columns:
        return
    if "reconciliation_status" not in reconciliation.columns:
        return

    unresolved_mask = reconciliation["reconciliation_status"].isin(_RECON_UNRESOLVED_STATUSES)
    unresolved = reconciliation[unresolved_mask].copy()
    if unresolved.empty:
        return

    now_utc = datetime.now(timezone.utc)
    created_at_ts = pd.to_datetime(unresolved["created_at"], errors="coerce", utc=True)
    age_hours = (now_utc - created_at_ts).dt.total_seconds() / 3600.0
    old_diffs_count = int((age_hours > _RECON_ALERT_THRESHOLD_HOURS).sum())
    if old_diffs_count > 0:
        max_age_h = float(age_hours.max())
        st.warning(
            f"⚠️ **{old_diffs_count} diff(s) de réconciliation non résolus depuis plus de "
            f"{_RECON_ALERT_THRESHOLD_HOURS}h** (âge max ≈ {max_age_h:.0f}h). "
            "Statuts concernés : BLOCKED / MANUAL_REVIEW. Vérification manuelle recommandée."
        )


def render() -> None:
    st.header("🚀 Execution Engine")

    # --- Bannière régime marché (Axe C plan/prompt/parttern/plan.md) ---
    try:
        from ihm.components.market_regime_banner import render_market_regime_banner
        render_market_regime_banner(compact=False)
    except Exception:  # pragma: no cover - jamais bloquant
        pass

    if not db_available():
        render_db_unavailable("Execution Engine", form_key="execution_db_form")
        return

    account_id = st.session_state.get("selected_account_id")

    # --- Kill switch (Sprint S26 — gap P1) ---
    # Toujours accessible, MEME si aucun run d'exécution n'existe encore.
    with st.expander("🛑 Kill switch — annuler tous les ordres ouverts", expanded=False):
        st.warning(
            "Cette action **annule immédiatement tous les ordres OPEN** du compte sélectionné "
            "via `python -m execution_engine cancel-all`. À utiliser uniquement en cas d'urgence."
        )
        kill_col1, kill_col2 = st.columns([1, 1])
        with kill_col1:
            kill_broker_mode = st.selectbox(
                "Broker mode",
                options=["paper", "live"],
                index=0,
                key="execution_kill_switch_broker_mode",
                help="`paper` = compte simulation Alpaca, `live` = argent réel.",
            )
        with kill_col2:
            kill_dry_run = st.checkbox(
                "Dry-run (lister sans annuler)",
                value=True,
                key="execution_kill_switch_dry_run",
            )
        kill_reason = st.text_input(
            "Raison (consignée dans `execution_kill_switch_runs.reason`)",
            value="manual kill switch from IHM",
            key="execution_kill_switch_reason",
        )
        if not account_id:
            st.error("Aucun compte sélectionné dans la sidebar — impossible de lancer le kill switch.")
        else:
            confirm_phrase = "CONFIRMER" if kill_broker_mode == "live" and not kill_dry_run else None
            render_ops_command_panel(
                "execution_kill_switch",
                account_id=str(account_id),
                confirm_phrase=confirm_phrase,
                command_kwargs={
                    "broker_mode": kill_broker_mode,
                    "confirm_account": str(account_id),
                    "reason": kill_reason,
                    "dry_run": kill_dry_run,
                },
            )

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
    watcher_summary_record = get_latest_run_business_summary(step_key="execution_protection_watch", entity_run_id=selected, account_id=account_id)
    watcher_service_record = get_latest_execution_protection_watch_service_summary(account_id=account_id, exec_run_id=selected)

    # --- KPI ---
    metric_row([
        ("Statut", run_status_badge(status), None),
        ("Cibles", int(row.get("total_targets", 0)), None),
        ("Soumis", int(row.get("total_submitted", 0)), None),
        ("Remplis", int(row.get("total_filled", 0)), None),
    ])
    st.caption(
        "Profil=`{}` | Fenêtre=`{}` | Compte=`{}`".format(
            row.get("execution_profile", "—"),
            row.get("submission_window", "—"),
            row.get("account_id", account_id or "default"),
        )
    )

    render_persistent_business_summary(summary_record, max_metrics=9)

    summary = get_run_summary(summary_record)
    watcher_summary = get_run_summary(watcher_summary_record)
    watcher_service_summary = get_run_summary(watcher_service_record)

    if summary:
        st.subheader("🛡️ Contraintes, protections initiales et indicateurs de risque")
        metric_row([
            ("Stops broker", int(summary.get("targets_with_broker_initial_stop", 0) or 0), None),
            ("Stops soumis", int(summary.get("child_initial_stop_orders_submitted", 0) or 0), None),
            ("Cibles stale", int(summary.get("stale_price_targets", 0) or 0), None),
            ("Échecs protections", int(summary.get("child_order_submit_failures", 0) or 0) + int(watcher_summary.get("submit_failed_items", 0) or 0), None),
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

    risk_run_id = str(row.get("risk_run_id", "") or "").strip()
    snapshot_targets = get_execution_targets_snapshot(selected)
    if not snapshot_targets.empty:
        st.subheader("🎯 Snapshot des cibles consommées")
        target_columns = [
            column for column in [
                "symbol", "candidate_rank", "decision_rank", "selector_signal_mode",
                "selector_earnings_blackout", "selection_explanation", "target_shares", "entry_price",
                "target_weight", "stop_price_initial", "risk_per_share", "risk_budget_dollars",
                "initial_risk_dollars", "target_notional", "price_asof_date", "atr_asof_date",
            ]
            if column in snapshot_targets.columns
        ]
        render_symbol_table(
            snapshot_targets[target_columns],
            key="exec_targets_snapshot",
            symbol_col="symbol",
            title="🎯 Snapshot des cibles consommées — contexte risk/selector figé",
            height=260,
        )
    else:
        detail = f" (risk_run_id={risk_run_id})" if risk_run_id else ""
        st.info(
            "Aucun snapshot de cibles figé trouvé pour ce run"
            f"{detail}. Le fallback direct vers `portfolio_targets` n’est plus affiché ici pour éviter de mélanger la source risque et le run d’exécution."
        )

    # --- Ordres d'exécution / protections ---
    orders = get_execution_orders(selected)
    if not orders.empty:
        st.subheader("📋 Requests et ordres broker")
        render_symbol_table(
            orders,
            key="exec_orders",
            symbol_col="symbol",
            height=260,
        )

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
    else:
        st.info("Aucune request / ordre broker canonique n’a été relu pour ce run.")

    # --- Fills ---
    st.subheader("💰 Exécutions")
    fills = get_execution_fills(selected)
    if not fills.empty and "slippage_bps" in fills.columns:
        avg_slip = fills["slippage_bps"].mean()
        st.metric("Slippage moyen (bps)", f"{avg_slip:.1f}")
    elif int(row.get("total_submitted", 0) or 0) > 0 and int(row.get("total_filled", 0) or 0) == 0:
        st.info("Aucun fill observé pour ce run pour l’instant : les ordres peuvent être encore en file broker ou en attente d’ouverture de marché.")
    show_dataframe(fills, height=300)

    # --- Positions / lots / réconciliation canoniques ---
    st.subheader("📦 Positions et détentions du run")
    projected_positions = get_execution_positions(
        account_id=account_id,
        exec_run_id=selected,
        allow_account_fallback=False,
    )
    if not projected_positions.empty:
        render_symbol_table(
            projected_positions,
            key="exec_projected_positions_run",
            symbol_col="symbol",
            title="🧮 Positions projetées — scope run",
            height=260,
        )
    else:
        st.info("Aucune position projetée scoppée run n’a été reconstruite pour ce run.")

    lots = get_execution_position_lots(
        account_id=account_id,
        exec_run_id=selected,
        allow_account_fallback=False,
    )
    if not lots.empty:
        _show_position_lots_table(lots, title="🪵 Lots touchés par ce run", height=260)
    else:
        st.info("Aucun lot ouvert ou clôturé par ce run n’a été identifié.")

    reconciliation = get_execution_reconciliation_results(
        exec_run_id=selected,
        account_id=account_id,
        allow_account_fallback=False,
    )
    if not reconciliation.empty:
        st.subheader("🧭 Réconciliation actionnable")

        # Sprint S3 / A-014 — alerte si des diffs non résolus sont vieux de > 24h.
        _render_reconciliation_age_warning(reconciliation)

        metric_row([
            ("SAFE_AUTO", int((reconciliation["reconciliation_status"] == "SAFE_AUTO").sum()) if "reconciliation_status" in reconciliation.columns else 0, None),
            ("MANUAL_REVIEW", int((reconciliation["reconciliation_status"] == "MANUAL_REVIEW").sum()) if "reconciliation_status" in reconciliation.columns else 0, None),
            ("BLOCKED", int((reconciliation["reconciliation_status"] == "BLOCKED").sum()) if "reconciliation_status" in reconciliation.columns else 0, None),
            ("Actions", int((reconciliation["action"] != "none").sum()) if "action" in reconciliation.columns else 0, None),
        ])
        if "reason_code" in reconciliation.columns:
            reason_counts_by_symbol = (
                reconciliation.assign(
                    symbol=reconciliation.get("symbol", pd.Series(index=reconciliation.index, dtype="object")).fillna("—"),
                    reason_code=reconciliation["reason_code"].fillna("aucune"),
                )
                .groupby(["symbol", "reconciliation_status", "reason_code"], dropna=False)
                .size()
                .reset_index(name="count")
            )
            if not reason_counts_by_symbol.empty:
                render_symbol_table(
                    reason_counts_by_symbol,
                    key="exec_reconciliation_reason_counts",
                    symbol_col="symbol",
                    title="🧩 Motifs de réconciliation",
                    height=180,
                )
        reconciliation_display = _prepare_reconciliation_display(reconciliation)
        reconciliation_columns = [
            column for column in [
                "status_badge", "symbol", "action", "target_qty", "internal_position_qty",
                "broker_position_qty", "position_delta", "has_open_protection",
                "open_request_buy_qty", "open_request_sell_qty", "open_broker_buy_qty",
                "open_broker_sell_qty", "reason_code", "created_at",
            ]
            if column in reconciliation_display.columns
        ]
        render_symbol_table(
            reconciliation_display[reconciliation_columns],
            key="exec_reconciliation_actionable",
            symbol_col="symbol",
            height=280,
        )
    else:
        st.info("Aucun résultat de réconciliation persisté n’a été trouvé pour ce run.")

    with st.expander("📚 Contexte compte — hors scope strict du run", expanded=False):
        broker_positions = get_broker_positions(account_id=account_id)
        if not broker_positions.empty:
            render_symbol_table(
                broker_positions,
                key="exec_broker_positions_account",
                symbol_col="symbol",
                title="📦 Positions broker — dernier snapshot compte",
                height=240,
            )

        account_positions = get_execution_positions(account_id=account_id)
        if not account_positions.empty:
            show_dataframe(account_positions, title="🧮 Positions projetées — scope compte", height=240)

        account_lots = get_execution_position_lots(account_id=account_id)
        if not account_lots.empty:
            _show_position_lots_table(account_lots, title="🪵 Lots reconstruits — scope compte", height=240)

    # --- Événements ---
    st.subheader("📝 Événements")
    events = get_execution_events(selected)
    render_symbol_table(events, key="exec_events", symbol_col="symbol", height=300)

    # --- Runs récents ---
    with st.expander("Historique des runs", expanded=False):
        show_dataframe(runs, height=300)

    if watcher_summary or watcher_service_summary:
        with st.expander("🛰️ Watcher protections — supervision secondaire", expanded=False):
            metric_row([
                ("Éligibles trail dyn.", int(summary.get("targets_eligible_for_dynamic_trailing", 0) or 0), None),
                ("Trailing activés", int(watcher_summary.get("transitioned_items", 0) or 0), None),
                ("Fallback trailing", int(summary.get("targets_with_trailing_fallback", 0) or 0), None),
                ("Checks trigger", int(watcher_summary.get("trigger_check_count", 0) or 0), None),
                ("Trails soumis", int(watcher_summary.get("transitioned_items", 0) or 0), None),
                ("Annulations KO", int(watcher_summary.get("cancel_failed_items", 0) or 0), None),
            ])
            if watcher_summary:
                render_persistent_business_summary(
                    watcher_summary_record,
                    title="🛰️ Résumé watcher protections",
                    max_metrics=8,
                )
            if watcher_service_summary:
                render_persistent_business_summary(
                    watcher_service_record,
                    title="🫀 Santé du service watcher",
                    max_metrics=7,
                )
                last_heartbeat_at = str(watcher_service_summary.get("last_heartbeat_at", "") or "").strip()
                heartbeat_threshold = float(watcher_service_summary.get("heartbeat_interval_seconds", 0.0) or 0.0)
                heartbeat_indicator = heartbeat_badge(
                    last_heartbeat_at,
                    heartbeat_threshold,
                    service_status=str((watcher_service_record or {}).get("status", "") or ""),
                )
                metric_row([
                    ("Statut service", run_status_badge(str((watcher_service_record or {}).get("status", "—") or "—")), None),
                    ("Scope", str(watcher_service_summary.get("service_scope", "—") or "—"), None),
                    ("Heartbeat", heartbeat_indicator, None),
                    ("Dernier cycle", str(watcher_service_summary.get("last_cycle_at", "—") or "—"), None),
                    ("Watch last cycle", int(watcher_service_summary.get("last_cycle_watched_items", 0) or 0), None),
                    ("Transitions last cycle", int(watcher_service_summary.get("last_cycle_transitioned_items", 0) or 0), None),
                ])


run_page_if_standalone(__name__, render)


