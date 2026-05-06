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
from ihm.services.watcher_runtime import (
    build_watcher_command,
    build_windows_integration_rows,
)

__all__ = ["_build_watcher_handoff_rows", "_render_watcher_handoff_panel"]


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
