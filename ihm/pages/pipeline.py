"""ihm/pages/pipeline.py — Vue séquentielle et pilotage du pipeline métier."""
from __future__ import annotations

from typing import Any, cast

import streamlit as st

from ihm.pages import run_page_if_standalone
from ihm.services.db import get_runtime_db_config
from ihm.services.pipeline_runner import (
    PipelineLaunchOptions,
    build_pipeline_command,
    format_command_for_display,
    get_pipeline_steps,
    run_pipeline_step,
)

RESULTS_STATE_KEY = "ihm_pipeline_run_results"


def _build_launch_options() -> tuple[PipelineLaunchOptions, bool]:
    selected_account_id = cast(str | None, st.session_state.get("selected_account_id"))

    with st.expander("⚙️ Paramètres d'exécution", expanded=True):
        st.caption(
            "Les sous-processus lancés depuis l'IHM héritent de la configuration DB active et, "
            "pour les étapes concernées, du compte Alpaca sélectionné dans la sidebar."
        )

        if selected_account_id:
            st.info(f"Compte Alpaca actuellement sélectionné : `{selected_account_id}`")
        else:
            st.info("Aucun compte Alpaca explicitement sélectionné — le compte par défaut sera utilisé si nécessaire.")

        col1, col2, col3 = st.columns(3)
        with col1:
            trade_date = st.text_input(
                "Trade date / as-of (YYYY-MM-DD)",
                key="pipeline_trade_date",
                help="Utilisé par Signal Aggregator, Risk, Execution et Corporate Actions Apply.",
            )
        with col2:
            risk_account_equity = st.number_input(
                "Equity pour le module Risk",
                min_value=0.0,
                value=float(st.session_state.get("pipeline_risk_account_equity", 100_000.0)),
                step=1_000.0,
                format="%.2f",
                key="pipeline_risk_account_equity",
            )
        with col3:
            execution_mode = cast(
                str,
                st.selectbox(
                    "Mode Execution",
                    options=["simulate", "paper", "live"],
                    index=["simulate", "paper", "live"].index(
                        cast(str, st.session_state.get("pipeline_execution_mode", "simulate"))
                        if st.session_state.get("pipeline_execution_mode", "simulate") in {"simulate", "paper", "live"}
                        else "simulate"
                    ),
                    key="pipeline_execution_mode",
                ),
            )

        col4, col5, col6 = st.columns(3)
        with col4:
            execution_run_id = st.text_input(
                "Execution — risk_run_id optionnel",
                key="pipeline_execution_run_id",
                help="Laissez vide pour exécuter sur le dernier run disponible.",
            )
        with col5:
            allow_outside_rth = st.checkbox(
                "Execution hors RTH",
                value=bool(st.session_state.get("pipeline_allow_outside_rth", False)),
                key="pipeline_allow_outside_rth",
            )
        with col6:
            auto_rebalance = st.checkbox(
                "Auto rebalance",
                value=bool(st.session_state.get("pipeline_auto_rebalance", False)),
                key="pipeline_auto_rebalance",
            )

        live_confirmed = True
        if execution_mode == "live":
            st.warning("Mode LIVE sélectionné : cette action peut envoyer de vrais ordres chez le broker.")
            live_confirmed = st.checkbox(
                "Je confirme explicitement le lancement en LIVE",
                value=bool(st.session_state.get("pipeline_live_confirmed", False)),
                key="pipeline_live_confirmed",
            )

    return (
        PipelineLaunchOptions(
            account_id=selected_account_id,
            trade_date=trade_date,
            risk_account_equity=float(risk_account_equity),
            execution_mode=cast(Any, execution_mode),
            execution_run_id=execution_run_id,
            allow_outside_rth=bool(allow_outside_rth),
            auto_rebalance=bool(auto_rebalance),
        ),
        live_confirmed,
    )


def _render_result(step_key: str, result_state: dict[str, object] | None) -> None:
    if not result_state:
        return

    returncode = int(cast(int | str, result_state.get("returncode", -1)))
    executed_at = str(result_state.get("executed_at", "—"))
    duration_seconds = float(cast(float | int | str, result_state.get("duration_seconds", 0.0)))
    account_id = result_state.get("account_id")
    command_display = str(result_state.get("command_display", ""))
    stdout = str(result_state.get("stdout", "") or "")
    stderr = str(result_state.get("stderr", "") or "")

    status_label = "✅ Succès" if returncode == 0 else f"❌ Échec (code {returncode})"
    if returncode == 0:
        st.success(f"Dernière exécution : {status_label}")
    else:
        st.error(f"Dernière exécution : {status_label}")

    metric_col1, metric_col2, metric_col3 = st.columns(3)
    metric_col1.metric("Date/heure", executed_at)
    metric_col2.metric("Durée", f"{duration_seconds:.2f}s")
    metric_col3.metric("Compte", str(account_id or "global"))

    if command_display:
        with st.expander("Commande réellement exécutée", expanded=False):
            st.code(command_display, language="powershell")

    if stdout:
        with st.expander("Logs stdout", expanded=returncode != 0):
            st.code(stdout, language="text")
    if stderr:
        with st.expander("Logs stderr", expanded=returncode != 0):
            st.code(stderr, language="text")


def render() -> None:
    st.header("🔄 Pipeline Quotidien")
    st.caption("Ordre d'exécution strict — chaque étape dépend de la précédente.")

    options, live_confirmed = _build_launch_options()
    db_config = get_runtime_db_config()
    results = cast(dict[str, dict[str, object]], st.session_state.setdefault(RESULTS_STATE_KEY, {}))

    for step in get_pipeline_steps():
        command_preview = format_command_for_display(build_pipeline_command(step.key, options))
        with st.expander(f"**{step.num}. {step.name}**", expanded=False):
            info_col, action_col = st.columns([5, 2])

            with info_col:
                st.markdown(f"**Description** : {step.desc}")
                st.markdown(f"**Tables impactées** : `{step.tables}`")
                st.markdown(f"**Dépendances** : {step.deps}")
                if step.account_usage == "alpaca":
                    st.caption(f"🏦 Cette étape utilise le compte Alpaca sélectionné : `{options.account_id or 'default'}`")
                else:
                    st.caption("🌐 Cette étape est globale et n'utilise pas le sélecteur de compte Alpaca.")
                st.code(command_preview, language="powershell")

            with action_col:
                execution_locked = step.key == "execution" and options.execution_mode == "live" and not live_confirmed
                run_clicked = st.button(
                    "▶️ Exécuter",
                    key=f"run_pipeline_step_{step.key}",
                    type="primary",
                    use_container_width=True,
                    disabled=execution_locked,
                )
                if execution_locked:
                    st.warning("Confirmez d'abord le mode LIVE dans les paramètres ci-dessus.")

                if run_clicked:
                    with st.spinner(f"Exécution de {step.name} en cours…"):
                        result = run_pipeline_step(step.key, options, db_config=db_config)
                    results[step.key] = result.to_state()

            _render_result(step.key, results.get(step.key))


run_page_if_standalone(__name__, render)


