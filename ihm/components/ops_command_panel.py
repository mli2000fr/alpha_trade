"""Sprint S26 — composant Streamlit générique pour panneaux de commandes ops.

Affiche pour chaque ``OpsCommandSpec`` :
- titre + description,
- bandeau d'état si un run est déjà actif,
- bouton "Lancer" (avec confirmation pour les commandes ``danger``),
- aperçu de la commande shell qui sera exécutée,
- accès aux 3 derniers runs (statut + bouton "Voir logs").

Le composant **n'embarque pas** de paramètres spécifiques (ex. ``--account``) :
les pages appelantes les passent via ``command_kwargs`` ou des widgets
préfixés. Cela garde la signature unique pour toutes les commandes.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

from ihm.services.ops_runner import (
    OPS_COMMAND_CATALOG,
    OpsCommandKey,
    build_ops_command,
    list_active_ops_runs,
    start_ops_command,
)
from ihm.services.process_registry import (
    list_active_pipeline_runs,
    load_pipeline_history,
    read_pipeline_logs,
    stop_pipeline_run,
)


def _format_command(command: list[str]) -> str:
    return " ".join(f'"{arg}"' if " " in arg else arg for arg in command)


def render_ops_command_panel(
    key: OpsCommandKey,
    *,
    account_id: str | None = None,
    db_config: dict[str, str | None] | None = None,
    confirm_phrase: str | None = None,
    command_kwargs: dict[str, Any] | None = None,
    show_history: bool = True,
    history_limit: int = 3,
) -> None:
    """Affiche un panneau de lancement pour la commande ops `key`.

    Parameters
    ----------
    key
        Clé de la commande dans :data:`OPS_COMMAND_CATALOG`.
    account_id
        Compte Alpaca à propager.
    db_config
        Config DB héritée par le sous-processus.
    confirm_phrase
        Si fournie (typiquement pour ``danger=True``), exige que l'utilisateur
        retape cette phrase avant que le bouton ne soit actif.
    command_kwargs
        Kwargs additionnels passés à :func:`build_ops_command` (ex.
        ``broker_mode``, ``trade_date``, ``backup_path``…).
    show_history
        Affiche les derniers runs.
    history_limit
        Nombre de runs récents à afficher.
    """
    spec = OPS_COMMAND_CATALOG[key]
    command_kwargs = dict(command_kwargs or {})
    if account_id and "account" not in command_kwargs:
        command_kwargs["account"] = account_id

    container = st.container(border=True)
    with container:
        title = f"{spec.icon} {spec.label}"
        if spec.danger:
            title += "  🔴"
        st.markdown(f"#### {title}")
        st.caption(spec.description)

        # Aperçu commande
        try:
            preview = build_ops_command(key, **command_kwargs)
            st.code(_format_command(preview), language="powershell")
        except ValueError as exc:
            st.warning(str(exc))
            preview = None

        # Runs actifs
        active = list_active_ops_runs(key)
        if active:
            for run in active:
                run_id = str(run.get("run_id", ""))
                st.info(
                    f"Un run est déjà en cours (`{run_id}`, statut `{run.get('status')}`).",
                    icon="⏳",
                )
                stop_clicked = st.button(
                    f"⏹ Arrêter `{run_id}`",
                    key=f"ops_stop_{key}_{run_id}",
                )
                if stop_clicked:
                    stop_pipeline_run(run_id)
                    st.rerun()

        # Confirmation pour commandes dangereuses
        unlocked = True
        if confirm_phrase:
            typed = st.text_input(
                f"⚠️ Pour confirmer, retape exactement : `{confirm_phrase}`",
                key=f"ops_confirm_{key}",
            )
            unlocked = typed.strip() == confirm_phrase

        # Bouton Lancer
        launch_label = f"🚀 Lancer — {spec.label}"
        disabled = (
            preview is None
            or bool(active)
            or (confirm_phrase is not None and not unlocked)
        )
        clicked = st.button(
            launch_label,
            key=f"ops_launch_{key}",
            type="primary" if not spec.danger else "secondary",
            disabled=disabled,
            use_container_width=True,
        )
        if clicked:
            try:
                record = start_ops_command(
                    key,
                    account_id=account_id,
                    db_config=db_config,
                    **command_kwargs,
                )
            except ValueError as exc:
                st.error(str(exc))
            except Exception as exc:  # pragma: no cover - défensif
                st.error(f"Échec lancement : {exc}")
            else:
                st.success(f"Run lancé en arrière-plan : `{record.run_id}`")
                st.rerun()

        if show_history:
            _render_recent_runs(key, history_limit)


def _render_recent_runs(key: OpsCommandKey, limit: int) -> None:
    """Affiche les `limit` derniers runs (terminés ou non) pour cette commande."""
    history = load_pipeline_history()
    rows = [r for r in history if str(r.get("step_key", "")) == f"ops:{key}"]
    rows = rows[:limit]
    if not rows:
        return
    with st.expander(f"📜 {len(rows)} dernier(s) run(s)", expanded=False):
        for r in rows:
            run_id = str(r.get("run_id", ""))
            status = str(r.get("status", "?"))
            executed_at = str(r.get("executed_at", "?"))
            rc = r.get("returncode")
            badge = "🟢" if status == "completed" and rc in (0, None) else (
                "🔴" if status in {"failed", "timeout"} or (rc not in (0, None)) else "🟡"
            )
            st.markdown(f"- {badge} `{run_id}` — {status} — {executed_at} — rc={rc}")
            try:
                logs = read_pipeline_logs(run_id, stream="all")
            except Exception:
                logs = ""
            if logs:
                st.download_button(
                    "⬇️ Télécharger les logs",
                    data=logs,
                    file_name=f"{run_id}_combined.log",
                    mime="text/plain",
                    key=f"ops_dl_{key}_{run_id}",
                )


__all__ = ["render_ops_command_panel"]


