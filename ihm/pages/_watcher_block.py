"""ihm/pages/_watcher_block.py — Phase 6.2 (Backlog L10).

Panneau « 12.bis Watcher post-exécution » extrait de ``pipeline.py``.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from ihm.components.watcher_documentation import render_watcher_documentation_panel
from ihm.services.pipeline_runner import (
    PipelineLaunchOptions,
    format_command_for_display,
)
from ihm.services.db import get_runtime_db_config
from ihm.services.watcher_runtime import (
    build_watcher_command,
    build_windows_integration_rows,
    launch_watcher_once,
    serialize_local_watcher_control_state,
    start_local_watcher_service,
    stop_local_watcher_service,
)

__all__ = [
    "_build_watcher_handoff_rows",
    "_render_watcher_handoff_panel",
    "_render_watcher_launch_controls",
]


def _build_watcher_handoff_rows(
    account_id: str | None,
    *,
    take_profit_pct: float = 0.08,
    trailing_stop_pct: float = 0.05,
    trailing_trigger: str = "multiple_r",
    trailing_r_multiple: float = 1.0,
    trailing_profit_pct: float = 0.03,
) -> list[dict[str, str]]:
    effective_account = (account_id or "default").strip() or "default"
    rows = [
        {
            "Mode": "Run once (CLI local)",
            "Quand l'utiliser": "Juste après l'étape 12 `Execution` pour un contrôle ponctuel ou un dépannage opérateur.",
            "Comment lancer": format_command_for_display(
                build_watcher_command(
                    mode="once",
                    account_id=effective_account,
                    profit_taker_pct=take_profit_pct,
                    trailing_stop_pct=trailing_stop_pct,
                    trailing_activation_trigger=trailing_trigger,
                    trailing_activation_r_multiple=trailing_r_multiple,
                    trailing_activation_profit_pct=trailing_profit_pct,
                )
            ),
        },
        {
            "Mode": "Service local / CLI service",
            "Quand l'utiliser": "Après l'étape 12 si vous voulez une surveillance continue des protections pendant la session du jour.",
            "Comment lancer": format_command_for_display(
                build_watcher_command(
                    mode="service",
                    account_id=effective_account,
                    profit_taker_pct=take_profit_pct,
                    trailing_stop_pct=trailing_stop_pct,
                    trailing_activation_trigger=trailing_trigger,
                    trailing_activation_r_multiple=trailing_r_multiple,
                    trailing_activation_profit_pct=trailing_profit_pct,
                )
            ),
        },
    ]
    for entry in build_windows_integration_rows(account_id=effective_account):
        rows.append(
            {
                "Mode": str(entry.get("mode", "") or ""),
                "Quand l'utiliser": str(entry.get("when_to_use", "") or ""),
                "Comment lancer": str(entry.get("command", "") or ""),
            }
        )
    return rows


def _render_watcher_handoff_panel(options: PipelineLaunchOptions) -> None:
    with st.container(border=True):
        st.markdown("**12.bis — Watcher post-exécution (hors workflow 1 → 14)**")
        st.info(
            "Le watcher se lance juste après `Execution` pour surveiller les protections broker-side. Il ne remplace pas les étapes 13 et 14 : "
            "les Corporate Actions peuvent s'enchaîner pendant que le watcher tourne."
        )
        st.markdown(
            "- **Quand ?** Dès que l'étape 12 `Execution` a produit des ordres / protections à surveiller.\n"
            "- **Ordre ?** `1 → 11` préparation, `12` exécution, **watcher post-exécution**, puis `13 → 14` corporate actions.\n"
            "- **Pour un nouvel arrivant** : en manuel, lancez un `run once` juste après `Execution`; en exploitation, préférez Task Scheduler ou NSSM."
        )
        st.caption(
            "Le pilotage détaillé, les logs live et le statut Windows réel sont visibles dans la page `Supervision Ops`."
        )
        render_watcher_documentation_panel(
            intro=(
                "Référence rapide pour un nouvel arrivant : quand lancer le watcher, dans quel ordre, "
                "avec quels modes (`once`, service local, Task Scheduler, NSSM) et comment s'onboarder en 5 minutes."
            )
        )
        _render_watcher_launch_controls(options)
        st.dataframe(
            pd.DataFrame(
                _build_watcher_handoff_rows(
                    options.account_id,
                    take_profit_pct=float(getattr(options, "execution_take_profit_pct", 0.08) or 0.08),
                    trailing_stop_pct=float(getattr(options, "execution_trailing_stop_pct", 0.05) or 0.05),
                    trailing_trigger=str(getattr(options, "execution_trailing_trigger", "multiple_r") or "multiple_r"),
                    trailing_r_multiple=float(getattr(options, "execution_trailing_r_multiple", 1.0) or 1.0),
                    trailing_profit_pct=float(getattr(options, "execution_trailing_profit_pct", 0.03) or 0.03),
                )
            ),
            use_container_width=True,
            hide_index=True,
        )


def _render_watcher_launch_controls(options: PipelineLaunchOptions) -> None:
    """Boutons IHM pour lancer le watcher de protections (run once / service local).

    Réutilise les helpers de ``ihm.services.watcher_runtime`` déjà utilisés par
    la page Supervision Ops, afin que les deux pages partagent la même
    sémantique de garde-fous (un seul service ou un seul ``once`` actif à la
    fois par compte).
    """
    account_id = (options.account_id or "").strip() or None
    try:
        control_state = serialize_local_watcher_control_state(account_id=account_id)
    except Exception as exc:  # pragma: no cover - défense IHM
        st.warning(f"Impossible de récupérer l'état du watcher local : {exc}")
        control_state = {
            "local_service_active": False,
            "local_service_run_id": "",
            "local_once_active": False,
            "local_once_run_id": "",
        }

    once_busy = bool(control_state.get("local_once_active"))
    service_active = bool(control_state.get("local_service_active"))

    status_bits: list[str] = []
    if once_busy:
        status_bits.append(
            f"Run once en cours : `{control_state.get('local_once_run_id', '') or '?'}`"
        )
    if service_active:
        status_bits.append(
            f"Service local actif : `{control_state.get('local_service_run_id', '') or '?'}`"
        )
    if status_bits:
        st.info(" · ".join(status_bits))

    action_cols = st.columns(3)
    run_once_clicked = action_cols[0].button(
        "▶️ Run watcher once",
        type="primary",
        use_container_width=True,
        disabled=once_busy or service_active,
        key="pipeline_watcher_run_once_btn",
        help="Exécute un scan unique du watcher de protections pour le compte sélectionné.",
    )
    service_clicked = action_cols[1].button(
        "🔁 Démarrer service local",
        use_container_width=True,
        disabled=once_busy or service_active,
        key="pipeline_watcher_service_start_btn",
        help="Démarre un service local IHM (boucle continue) pour surveiller les protections.",
    )
    stop_clicked = action_cols[2].button(
        "⏹️ Stop service local",
        use_container_width=True,
        disabled=not service_active,
        key="pipeline_watcher_service_stop_btn",
        help="Arrête le service local IHM (n'agit pas sur Task Scheduler ni NSSM).",
    )

    db_config = get_runtime_db_config()
    broker_mode = str(getattr(options, "execution_mode", "paper") or "paper")
    if broker_mode not in {"paper", "live"}:
        broker_mode = "paper"

    if run_once_clicked:
        try:
            record = launch_watcher_once(
                db_config=db_config,
                account_id=account_id,
                broker_mode=broker_mode,
            )
        except RuntimeError as exc:
            st.warning(str(exc))
        else:
            st.success(f"Watcher once lancé en arrière-plan : `{record.run_id}`")
            st.rerun()

    if service_clicked:
        try:
            record = start_local_watcher_service(
                db_config=db_config,
                account_id=account_id,
                broker_mode=broker_mode,
            )
        except RuntimeError as exc:
            st.warning(str(exc))
        else:
            st.success(f"Service watcher local IHM lancé : `{record.run_id}`")
            st.rerun()

    if stop_clicked:
        run_id = str(control_state.get("local_service_run_id", "") or "")
        if not run_id:
            st.warning("Aucun service watcher local actif à arrêter.")
        else:
            try:
                stopped = stop_local_watcher_service(run_id)
            except RuntimeError as exc:
                st.warning(str(exc))
            else:
                if stopped:
                    st.success(f"Arrêt demandé pour le service watcher local `{run_id}`.")
                    st.rerun()
                else:
                    st.warning("Le service watcher local n'est plus actif.")

