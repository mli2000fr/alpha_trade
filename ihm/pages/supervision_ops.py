"""ihm/pages/supervision_ops.py — Supervision opérationnelle cross-run."""
from __future__ import annotations

import streamlit as st

from ihm.components.metrics import format_duration_hhmmss
from ihm.components.db_controls import render_db_unavailable
from ihm.components.metrics import metric_row
from ihm.components.tables import show_dataframe
from ihm.pages import run_page_if_standalone
from ihm.services.db import db_available
from ihm.services.db import get_runtime_db_config
from ihm.services.ops_supervision import build_ops_supervision_snapshot
from ihm.services.windows_watcher_bridge import read_windows_log_source
from ihm.services.watcher_runtime import build_watcher_log_download_name
from ihm.services.watcher_runtime import get_watcher_run_record
from ihm.services.watcher_runtime import launch_watcher_once
from ihm.services.watcher_runtime import read_watcher_run_logs
from ihm.services.watcher_runtime import restart_local_watcher_service
from ihm.services.watcher_runtime import stop_local_watcher_service

WATCHER_ACK_KEY = "ops_watcher_control_ack"
WATCHER_OVERRIDE_KEY = "ops_watcher_control_override"
WATCHER_LIMIT_KEY = "ops_watcher_control_limit"
WATCHER_SERVICE_INTERVAL_KEY = "ops_watcher_service_interval"
WATCHER_IDLE_INTERVAL_KEY = "ops_watcher_idle_interval"
WATCHER_HEARTBEAT_INTERVAL_KEY = "ops_watcher_heartbeat_interval"
WATCHER_HISTORY_SELECTED_RUN_KEY = "ops_watcher_history_selected_run"
WATCHER_LOG_FILTER_KEY = "ops_watcher_log_filter"
WATCHER_LOG_TAIL_LINES = 200
WINDOWS_LOG_SOURCE_SELECTED_KEY = "ops_windows_watcher_log_source"


def _tail_text(content: str, max_lines: int = WATCHER_LOG_TAIL_LINES) -> str:
    lines = content.splitlines()
    if len(lines) <= max_lines:
        return content
    return "\n".join(lines[-max_lines:])


def _render_log_block(title: str, content: str, *, key: str, expanded: bool = False) -> None:
    tailed = _tail_text(content)
    suffix = ""
    if tailed != content:
        suffix = f" — affichage limité aux {WATCHER_LOG_TAIL_LINES} dernières lignes"
    with st.expander(f"{title}{suffix}", expanded=expanded):
        if tailed.strip():
            with st.container(height=320, key=f"{key}_container"):
                st.code(tailed, language="text")
        else:
            st.info("Aucun log watcher disponible pour le moment.")


def _render_selected_watcher_run(record: dict[str, object] | None, *, run_id: str, log_filter: str) -> None:
    if record is None:
        st.warning("Le run watcher sélectionné n'est plus disponible dans l'historique IHM.")
        return

    status = str(record.get("status", "") or "").lower()
    if status == "completed":
        st.success(f"Run watcher sélectionné : `{run_id}` terminé avec succès.")
    elif status in {"failed", "timeout", "stopped"}:
        st.error(f"Run watcher sélectionné : `{run_id}` en statut `{status}`.")
    else:
        st.warning(f"Run watcher sélectionné : `{run_id}` en cours (`{status or 'running'}`).")

    metric_row([
        ("Run ID", run_id, None),
        ("Durée", format_duration_hhmmss(record.get("duration_seconds", 0.0)), None),
        ("stdout", int(record.get("stdout_lines", 0) or 0), None),
        ("stderr", int(record.get("stderr_lines", 0) or 0), None),
    ])
    st.caption(
        f"Commande : `{record.get('command_display', '')}` | Compte : `{record.get('account_id') or 'global'}` | Retour : `{record.get('returncode')}`"
    )
    logs = read_watcher_run_logs(run_id, stream=log_filter)
    st.download_button(
        label=f"⬇️ Télécharger le log ({log_filter})",
        data=logs,
        file_name=build_watcher_log_download_name(run_id, stream=log_filter),
        mime="text/plain",
        key=f"watcher_download_{run_id}_{log_filter}",
    )
    _render_log_block(
        "Logs watcher local",
        logs,
        key=f"watcher_logs_{run_id}_{log_filter}",
        expanded=True,
    )


def _render_selected_windows_log_source(log_sources_df, *, source_name: str) -> None:
    if log_sources_df is None or log_sources_df.empty:
        st.info("Aucune source de log Windows détectée.")
        return

    matches = log_sources_df[log_sources_df["source"] == source_name]
    if matches.empty:
        st.warning("La source de log Windows sélectionnée n'est plus disponible.")
        return
    row = matches.iloc[0].to_dict()
    path_value = str(row.get("path", "") or "")
    logs = read_windows_log_source(path_value)
    st.caption(
        f"Source : `{row.get('source', '—')}` | Runtime : `{row.get('runtime', '—')}` | Path : `{path_value or '—'}` | Existe : `{row.get('exists', False)}`"
    )
    st.download_button(
        label="⬇️ Télécharger le log Windows importé",
        data=logs,
        file_name=(path_value.split("\\")[-1] if path_value else f"watcher_windows_{source_name}.log"),
        mime="text/plain",
        key=f"watcher_windows_download_{source_name}",
    )
    _render_log_block(
        "Logs Windows importés",
        logs,
        key=f"watcher_windows_logs_{source_name}",
        expanded=True,
    )


@st.fragment(run_every="2s")
def _render_watcher_runtime_observability(*, account_id: str | None) -> None:
    snapshot = build_ops_supervision_snapshot(account_id=account_id)
    watcher_history = snapshot.get("watcher_history")
    control_state = dict(snapshot.get("watcher_control", {}))

    st.caption(
        "Logs live et historique dédiés aux watchers lancés depuis l'IHM. Rafraîchissement automatique toutes les 2 secondes quand un watcher local reste actif."
    )
    show_dataframe(watcher_history, height=220)

    if watcher_history is None or watcher_history.empty:
        return

    labels: dict[str, str] = {}
    for row in watcher_history.to_dict(orient="records"):
        run_id = str(row.get("run_id", "") or "")
        if not run_id:
            continue
        labels[run_id] = (
            f"{row.get('type', 'watcher')} | {run_id} | {row.get('status_badge', row.get('status', ''))} | {row.get('executed_at', '')}"
        )
    if not labels:
        return

    preferred_run_id = str(
        control_state.get("local_service_run_id")
        or control_state.get("local_once_run_id")
        or next(iter(labels.keys()))
    )
    if st.session_state.get(WATCHER_HISTORY_SELECTED_RUN_KEY) not in labels:
        st.session_state[WATCHER_HISTORY_SELECTED_RUN_KEY] = preferred_run_id

    filter_col, select_col = st.columns([1.5, 3.5])
    stream_map = {"tout": "all", "stdout": "stdout", "stderr": "stderr"}
    filter_value = str(
        filter_col.radio(
            "Flux watcher",
            options=["tout", "stdout", "stderr"],
            horizontal=True,
            key=WATCHER_LOG_FILTER_KEY,
        )
    )
    selected_run_id = str(
        select_col.selectbox(
            "Run watcher à inspecter",
            options=list(labels.keys()),
            format_func=lambda rid: labels[rid],
            key=WATCHER_HISTORY_SELECTED_RUN_KEY,
        )
    )
    _render_selected_watcher_run(
        get_watcher_run_record(selected_run_id),
        run_id=selected_run_id,
        log_filter=stream_map[filter_value],
    )


@st.fragment(run_every="5s")
def _render_windows_runtime_observability(*, account_id: str | None) -> None:
    snapshot = build_ops_supervision_snapshot(account_id=account_id)
    windows_runtime_df = snapshot.get("watcher_windows_runtime")
    windows_log_sources_df = snapshot.get("watcher_windows_log_sources")
    windows_bridge_df = snapshot.get("watcher_windows_bridge")

    st.caption(
        "Lecture read-only du vrai statut Windows via un bridge PowerShell allowlisté. Aucun start/stop/install n'est exécuté depuis cette page."
    )
    show_dataframe(windows_runtime_df, height=180)
    show_dataframe(windows_bridge_df, height=120)

    if windows_log_sources_df is None or windows_log_sources_df.empty:
        st.info("Aucune source de log Task Scheduler / NSSM détectée ou accessible pour le moment.")
        return

    st.markdown("**Sources de logs Windows importables**")
    show_dataframe(windows_log_sources_df, height=160)
    source_names = [str(row.get("source", "") or "") for row in windows_log_sources_df.to_dict(orient="records") if row.get("source")]
    if not source_names:
        return
    if st.session_state.get(WINDOWS_LOG_SOURCE_SELECTED_KEY) not in source_names:
        st.session_state[WINDOWS_LOG_SOURCE_SELECTED_KEY] = source_names[0]
    selected_source = str(
        st.selectbox(
            "Source Windows à inspecter",
            options=source_names,
            key=WINDOWS_LOG_SOURCE_SELECTED_KEY,
        )
    )
    _render_selected_windows_log_source(windows_log_sources_df, source_name=selected_source)


def _render_windows_integration_panel(*, snapshot: dict[str, object]) -> None:
    st.subheader("🪟 Intégration Windows explicite")
    st.info(
        "Aide opérateur en lecture seule : cette section rappelle comment raccorder proprement le watcher au packaging Windows sans l'exécuter depuis l'IHM."
    )
    integration_df = snapshot.get("watcher_windows_integration")
    if integration_df is None or integration_df.empty:
        st.info("Aucune recommandation d'intégration Windows disponible.")
        return
    for row in integration_df.to_dict(orient="records"):
        title = f"{row.get('mode', 'Mode')} — {row.get('target', 'Usage')}"
        with st.expander(title, expanded=False):
            st.caption(str(row.get("when_to_use", "") or ""))
            st.code(str(row.get("command", "") or ""), language="powershell")


def _restart_button_label(control_state: dict[str, object]) -> str:
    return "♻️ Restart service local IHM" if bool(control_state.get("local_service_active")) else "▶️ Démarrer service local IHM"


def _render_watcher_ops_controls(*, account_id: str | None, snapshot: dict[str, object]) -> None:
    control_state = dict(snapshot.get("watcher_control", {}))
    metric_row([
        ("Service local IHM", "actif" if bool(control_state.get("local_service_active")) else "inactif", None),
        ("Run service local", str(control_state.get("local_service_run_id", "—") or "—"), None),
        ("Run once local", str(control_state.get("local_once_run_id", "—") or "—"), None),
    ])

    if bool(control_state.get("external_fresh_service_detected")):
        scope = str(control_state.get("fresh_service_scope", "") or "global")
        st.warning(
            f"Un watcher avec heartbeat frais est déjà détecté sur le scope `{scope}` hors process local IHM actif. Les démarrages locaux restent bloqués par défaut pour éviter de doubler un service Windows packagé."
        )
    elif bool(control_state.get("local_service_active")):
        st.success("Un service watcher local IHM est actuellement actif et peut être arrêté ou relancé depuis cette page.")

    for message in list(control_state.get("guardrail_messages", [])):
        st.info(str(message))

    st.caption(
        "Ces boutons pilotent uniquement un process lancé depuis l'IHM courante. Ils n'installent ni ne redémarrent Task Scheduler, NSSM, secrets Windows ou packaging machine."
    )
    acknowledged = st.checkbox(
        "Je confirme que ce pilotage est local à l'IHM et ne remplace pas l'exploitation Windows packagée.",
        key=WATCHER_ACK_KEY,
    )
    override_external = st.checkbox(
        "Autoriser exceptionnellement un démarrage local même si un heartbeat watcher frais est déjà détecté.",
        key=WATCHER_OVERRIDE_KEY,
        disabled=not acknowledged or not bool(control_state.get("external_fresh_service_detected")),
    )

    settings_cols = st.columns(4)
    limit = int(settings_cols[0].number_input("Limit watch", min_value=1, value=100, step=1, key=WATCHER_LIMIT_KEY))
    service_interval = float(
        settings_cols[1].number_input("Interval service (s)", min_value=5.0, value=30.0, step=5.0, key=WATCHER_SERVICE_INTERVAL_KEY)
    )
    idle_interval = float(
        settings_cols[2].number_input("Interval idle (s)", min_value=5.0, value=120.0, step=5.0, key=WATCHER_IDLE_INTERVAL_KEY)
    )
    heartbeat_interval = float(
        settings_cols[3].number_input(
            "Heartbeat (s)",
            min_value=5.0,
            value=300.0,
            step=5.0,
            key=WATCHER_HEARTBEAT_INTERVAL_KEY,
        )
    )

    blocked_by_external_guardrail = bool(control_state.get("external_fresh_service_detected")) and not bool(control_state.get("local_service_active")) and not override_external
    once_busy = bool(control_state.get("local_once_active"))
    service_active = bool(control_state.get("local_service_active"))

    action_cols = st.columns(3)
    run_once_clicked = action_cols[0].button(
        "▶️ Run watcher once",
        type="primary",
        use_container_width=True,
        disabled=(not acknowledged) or blocked_by_external_guardrail or once_busy or service_active,
    )
    restart_clicked = action_cols[1].button(
        _restart_button_label(control_state),
        use_container_width=True,
        disabled=(not acknowledged) or blocked_by_external_guardrail or once_busy,
    )
    stop_clicked = action_cols[2].button(
        "⏹️ Stop service local IHM",
        use_container_width=True,
        disabled=(not acknowledged) or not service_active,
    )

    db_config = get_runtime_db_config()

    if run_once_clicked:
        try:
            record = launch_watcher_once(db_config=db_config, account_id=account_id, limit=limit)
        except RuntimeError as exc:
            st.warning(str(exc))
        else:
            st.success(f"Watcher once lancé en arrière-plan : `{record.run_id}`")
            st.rerun()

    if restart_clicked:
        try:
            record = restart_local_watcher_service(
                db_config=db_config,
                account_id=account_id,
                limit=limit,
                service_interval_seconds=service_interval,
                idle_interval_seconds=idle_interval,
                heartbeat_interval_seconds=heartbeat_interval,
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


def render() -> None:
    st.header("🛟 Supervision Ops")
    st.caption(
        "Vue dédiée à la supervision opérationnelle : état des services, heartbeats stale, derniers runs critiques et alertes synthétiques."
    )
    st.info(
        "Cette page supervise l'exécution et la santé des services. L'installation Task Scheduler / NSSM, la gestion des secrets Windows et le packaging runtime restent pilotés par les scripts PowerShell."
    )
    if not db_available():
        render_db_unavailable("Supervision Ops", form_key="ops_supervision_db_form")
        return
    account_id = st.session_state.get("selected_account_id")
    snapshot = build_ops_supervision_snapshot(account_id=account_id)
    metrics = dict(snapshot.get("metrics", {}))
    metric_row([
        ("Services suivis", int(metrics.get("services_monitored", 0) or 0), None),
        ("Services stale", int(metrics.get("services_stale", 0) or 0), None),
        ("Services à surveiller", int(metrics.get("services_warn", 0) or 0), None),
        ("Alertes critiques", int(metrics.get("critical_alerts", 0) or 0), None),
        ("Runs IHM actifs", int(metrics.get("active_runs", 0) or 0), None),
    ])
    with st.container(border=True):
        st.subheader("🎛️ Pilotage watcher depuis l'IHM")
        _render_watcher_ops_controls(account_id=account_id, snapshot=snapshot)
    with st.container(border=True):
        st.subheader("🖥️ Logs live & historique watcher IHM")
        _render_watcher_runtime_observability(account_id=account_id)
    with st.container(border=True):
        st.subheader("🪟 Statut Windows réel & logs importés")
        _render_windows_runtime_observability(account_id=account_id)
    alerts = list(snapshot.get("alerts", []))
    with st.container(border=True):
        st.subheader("🚨 Alertes synthétiques")
        if not alerts:
            st.success("🟢 Aucun signal d'alerte critique détecté pour le moment.")
        else:
            for alert in alerts:
                severity = str(alert.get("severity", "info") or "info")
                message = str(alert.get("message", "") or "").strip()
                if not message:
                    continue
                if severity == "error":
                    st.error(message)
                elif severity == "warn":
                    st.warning(message)
                else:
                    st.info(message)
    with st.container(border=True):
        st.subheader("🫀 État des services")
        st.caption("Le heartbeat est colorisé automatiquement en vert / orange / rouge selon sa fraîcheur et le statut du service.")
        show_dataframe(snapshot.get("service_health"), height=280)
    with st.container(border=True):
        st.subheader("🧭 Derniers runs critiques")
        st.caption("Vue synthétique des derniers runs métier structurants pour l'opérationnel quotidien.")
        show_dataframe(snapshot.get("latest_runs"), height=260)
    with st.container(border=True):
        st.subheader("🏃 Runs IHM en cours")
        st.caption("Pipelines ou workflows lancés depuis l'IHM encore actifs au moment de la consultation.")
        show_dataframe(snapshot.get("active_runs"), height=220)
    with st.container(border=True):
        _render_windows_integration_panel(snapshot=snapshot)
run_page_if_standalone(__name__, render)
