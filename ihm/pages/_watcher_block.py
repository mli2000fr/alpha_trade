"""ihm/pages/_watcher_block.py — Phase 6.2 (Backlog L10).

Panneau « 12.bis Watcher post-exécution » extrait de ``pipeline.py``.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st
from typing import Any

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
    launch_watcher_once_for_all_accounts,
    list_alpaca_account_ids,
    serialize_all_accounts_watcher_control_state,
    serialize_local_watcher_control_state,
    start_local_watcher_service,
    start_local_watcher_service_for_all_accounts,
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
    manual_buy_stop_loss_pct: float = 0.05,
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
                    manual_buy_stop_loss_pct=manual_buy_stop_loss_pct,
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
                    manual_buy_stop_loss_pct=manual_buy_stop_loss_pct,
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
    with st.expander("**12.bis — Watcher post-exécution (hors workflow 1 → 14)**", expanded=False):
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
                    manual_buy_stop_loss_pct=float(getattr(options, "execution_manual_buy_stop_loss_pct", 0.05) or 0.05),
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

    # Issue 1 (2026-05) — Option « Tous les comptes Alpaca » : si cochée, le
    # bouton « Run watcher once » et « Démarrer service local IHM » bouclent
    # sur tous les comptes déclarés (config.yaml + env vars) et lancent un
    # processus watcher par compte. Chaque compte conserve son verrou leader
    # propre et ses propres logs (Supervision Ops).
    available_account_ids: list[str] = []
    try:
        available_account_ids = list_alpaca_account_ids()
    except Exception:  # pragma: no cover - défense IHM
        available_account_ids = []
    multi_account_supported = len(available_account_ids) > 1
    multi_account_enabled = False
    multi_account_state: dict[str, Any] = {}
    if multi_account_supported:
        multi_account_enabled = st.checkbox(
            f"🌐 Tous les comptes Alpaca ({len(available_account_ids)} : "
            f"{', '.join(available_account_ids)})",
            value=False,
            key="pipeline_watcher_multi_account_toggle",
            help=(
                "Quand cochée, lance un processus watcher par compte Alpaca déclaré. "
                "Chaque compte garde son propre verrou leader et ses propres logs. "
                "Les comptes ayant déjà un watcher actif sont ignorés."
            ),
        )
        if multi_account_enabled:
            try:
                multi_account_state = serialize_all_accounts_watcher_control_state()
            except Exception as exc:  # pragma: no cover - défense IHM
                st.warning(f"État multi-comptes indisponible : {exc}")
                multi_account_state = {}
            any_active = bool(
                multi_account_state.get("any_service_active")
                or multi_account_state.get("any_once_active")
            )
            if any_active:
                active_lines: list[str] = []
                for aid, st_account in (multi_account_state.get("accounts") or {}).items():
                    if st_account.get("local_service_active"):
                        active_lines.append(
                            f"• `{aid}` : service local actif "
                            f"(`{st_account.get('local_service_run_id', '?')}`)"
                        )
                    elif st_account.get("local_once_active"):
                        active_lines.append(
                            f"• `{aid}` : run once en cours "
                            f"(`{st_account.get('local_once_run_id', '?')}`)"
                        )
                if active_lines:
                    st.caption(
                        "Comptes déjà couverts (ils seront ignorés au prochain lancement) :\n"
                        + "\n".join(active_lines)
                    )

    action_cols = st.columns(3)
    run_once_clicked = action_cols[0].button(
        "▶️ Run watcher once",
        type="primary",
        use_container_width=True,
        disabled=(once_busy or service_active) and not multi_account_enabled,
        key="pipeline_watcher_run_once_btn",
        help=(
            "Exécute un scan unique du watcher de protections "
            + ("pour tous les comptes Alpaca déclarés." if multi_account_enabled
               else "pour le compte sélectionné.")
        ),
    )
    service_clicked = action_cols[1].button(
        "🔁 Démarrer service local",
        use_container_width=True,
        disabled=(once_busy or service_active) and not multi_account_enabled,
        key="pipeline_watcher_service_start_btn",
        help=(
            "Démarre un service local IHM (boucle continue) "
            + ("par compte Alpaca déclaré." if multi_account_enabled
               else "pour le compte sélectionné.")
        ),
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

    common_watcher_kwargs: dict[str, Any] = dict(
        broker_mode=broker_mode,
        profit_taker_pct=float(getattr(options, "execution_take_profit_pct", 0.08) or 0.08),
        trailing_stop_pct=float(getattr(options, "execution_trailing_stop_pct", 0.05) or 0.05),
        manual_buy_stop_loss_pct=float(getattr(options, "execution_manual_buy_stop_loss_pct", 0.05) or 0.05),
        trailing_activation_trigger=str(getattr(options, "execution_trailing_trigger", "multiple_r") or "multiple_r"),
        trailing_activation_r_multiple=float(getattr(options, "execution_trailing_r_multiple", 1.0) or 1.0),
        trailing_activation_profit_pct=float(getattr(options, "execution_trailing_profit_pct", 0.03) or 0.03),
    )

    if run_once_clicked:
        try:
            if multi_account_enabled:
                records = launch_watcher_once_for_all_accounts(
                    db_config=db_config, **common_watcher_kwargs,
                )
            else:
                records = [launch_watcher_once(
                    db_config=db_config, account_id=account_id, **common_watcher_kwargs,
                )]
        except RuntimeError as exc:
            st.warning(str(exc))
        else:
            if multi_account_enabled:
                st.success(
                    "Watcher once lancé pour "
                    f"{len(records)} compte(s) : "
                    + ", ".join(f"`{r.account_id or '?'}`→`{r.run_id}`" for r in records)
                )
            else:
                st.success(f"Watcher once lancé en arrière-plan : `{records[0].run_id}`")
            st.rerun()

    if service_clicked:
        try:
            if multi_account_enabled:
                records = start_local_watcher_service_for_all_accounts(
                    db_config=db_config, **common_watcher_kwargs,
                )
            else:
                records = [start_local_watcher_service(
                    db_config=db_config, account_id=account_id, **common_watcher_kwargs,
                )]
        except RuntimeError as exc:
            st.warning(str(exc))
        else:
            if multi_account_enabled:
                st.success(
                    "Service watcher local IHM démarré pour "
                    f"{len(records)} compte(s) : "
                    + ", ".join(f"`{r.account_id or '?'}`→`{r.run_id}`" for r in records)
                )
            else:
                st.success(f"Service watcher local IHM lancé : `{records[0].run_id}`")
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

