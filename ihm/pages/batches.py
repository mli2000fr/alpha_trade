"""Catalogue, installation et exécution des batchs planifiés."""
from __future__ import annotations

from typing import Any

import streamlit as st

from ihm.pages import run_page_if_standalone
from ihm.services.batch_management import (
    BatchSpec,
    build_install_command,
    build_run_command,
    build_uninstall_command,
    format_command,
    format_schedule,
    install_all_batches,
    install_batch,
    list_active_batch_runs,
    load_batch_specs,
    query_windows_task_states,
    read_batch_log_tail,
    start_batch,
    uninstall_all_batches,
    uninstall_batch,
)
from ihm.services.db import get_last_query_error, get_runtime_db_config, safe_query
from ihm.services.process_registry import load_pipeline_history, read_pipeline_logs


@st.cache_data(ttl=15, show_spinner=False)
def _task_states() -> tuple[dict[str, dict[str, Any]], str | None]:
    return query_windows_task_states()


@st.cache_data(ttl=15, show_spinner=False)
def _latest_collection_runs() -> tuple[dict[str, dict[str, Any]], str | None]:
    frame = safe_query(
        """
        SELECT r.batch_name, r.provider, r.status, r.started_at, r.finished_at,
               r.requested_count, r.received_count, r.persisted_count,
               r.empty_count, r.failed_count, r.warning_count, r.error_message
        FROM pit_collection_runs r
        INNER JOIN (
            SELECT batch_name, MAX(started_at) AS max_started_at
            FROM pit_collection_runs GROUP BY batch_name
        ) latest
         ON latest.batch_name = r.batch_name
         AND latest.max_started_at = r.started_at
        UNION ALL
        SELECT 'analyst_snapshot_collection' AS batch_name, a.provider, a.status,
               a.started_at, a.finished_at, a.requested_symbols AS requested_count,
               a.successful_symbols AS received_count,
               (COALESCE(a.estimates_rows_inserted, 0)
                + COALESCE(a.eps_trend_rows_inserted, 0)
                + COALESCE(a.eps_revision_rows_inserted, 0)
                + COALESCE(a.targets_rows_inserted, 0)
                + COALESCE(a.recommendations_rows_inserted, 0)) AS persisted_count,
               a.empty_symbols AS empty_count, a.failed_symbols AS failed_count,
               (COALESCE(a.schema_error_count, 0) + COALESCE(a.parse_error_count, 0)) AS warning_count,
               NULL AS error_message
        FROM analyst_snapshot_collection_run a
        WHERE a.started_at = (SELECT MAX(started_at) FROM analyst_snapshot_collection_run)
        """
    )
    error = get_last_query_error()
    if frame.empty:
        return {}, error
    rows: dict[str, dict[str, Any]] = {}
    for row in frame.to_dict(orient="records"):
        rows[str(row.get("batch_name"))] = row
    return rows, error


def _priority_badge(priority: str) -> str:
    icons = {"P0": "🔴", "P1": "🟠", "P2": "🟡", "P3": "🔵", "P4": "⚪"}
    return f"{icons.get(priority, '⚪')} {priority}"


def _task_badge(task: dict[str, Any] | None) -> str:
    if not task:
        return "⚪ Non installé"
    state = str(task.get("state") or "Inconnu")
    if state == "Running":
        return "🔵 En cours"
    if not task.get("enabled", True) or state == "Disabled":
        return "⏸️ Installé, désactivé"
    return f"🟢 Installé · {state}"


def _value(value: Any) -> str:
    if value is None or str(value) in {"", "NaT", "nan", "None"}:
        return "—"
    return str(value)


def _render_last_run(row: dict[str, Any] | None) -> None:
    if not row:
        st.caption("Aucune exécution suivie dans pit_collection_runs.")
        return
    status = str(row.get("status") or "INCONNU")
    icon = "✅" if status in {"SUCCESS", "COMPLETED", "OK"} else ("🔄" if status == "RUNNING" else "❌")
    st.markdown(f"**Dernière collecte :** {icon} {status}")
    st.caption(
        f"Début {_value(row.get('started_at'))} · Fin {_value(row.get('finished_at'))} · "
        f"demandés {_value(row.get('requested_count'))} · reçus {_value(row.get('received_count'))} · "
        f"persistés {_value(row.get('persisted_count'))} · échecs {_value(row.get('failed_count'))} · "
        f"alertes {_value(row.get('warning_count'))}"
    )
    if row.get("error_message"):
        st.error(str(row["error_message"]))


def _render_batch(
    spec: BatchSpec,
    task: dict[str, Any] | None,
    db_run: dict[str, Any] | None,
    *,
    run_as: str,
    active: list[dict[str, object]],
    recent: dict[str, object] | None,
) -> None:
    status_bits = [_priority_badge(spec.priority), _task_badge(task)]
    if not spec.enabled:
        status_bits.append("⏸️ Désactivé dans batch.yaml")
    elif not spec.runnable:
        status_bits.append(f"🧪 {spec.status}")
    if active:
        status_bits.append("🔄 Lancé depuis cette IHM")

    with st.expander(f"{' · '.join(status_bits)} — {spec.name}", expanded=bool(active)):
        st.write(spec.description)
        if spec.research_notice:
            st.warning(f"🔬 Usage recherche — {spec.research_notice}")
        if not spec.runnable:
            requirement = spec.activation_requirement or (
                f"Corriger le statut {spec.status} et passer enabled à true dans batch.yaml "
                "uniquement après validation opérationnelle."
            )
            st.error(f"🔴 Activation bloquée — {requirement}")
            if spec.unlock_steps:
                st.markdown("**Comment le débloquer :**")
                for index, step in enumerate(spec.unlock_steps, start=1):
                    st.markdown(f"{index}. {step}")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Calendrier configuré :** {format_schedule(spec)}")
            st.markdown(f"**Fournisseur(s) :** {spec.provider}")
            universe = spec.symbols_file or spec.universe_scope or "non applicable"
            st.markdown(f"**Univers :** {universe}")
        with col2:
            st.markdown(f"**Tâche Windows :** {spec.task_name}")
            st.markdown(f"**Dernière exécution Windows :** {_value(task.get('last_run_time') if task else None)}")
            st.markdown(f"**Prochaine exécution Windows :** {_value(task.get('next_run_time') if task else None)}")
            if task and task.get("last_result") is not None:
                st.markdown(f"**Code retour Windows :** {task['last_result']}")

        tables = ", ".join(spec.tables)
        st.markdown("**Tables impactées :** " + (tables or "aucune tant que la source n’est pas activée"))
        _render_last_run(db_run)

        with st.expander("Commandes et détails techniques"):
            st.caption("Installation / réinstallation de la tâche Windows")
            st.code(format_command(build_install_command(spec, run_as=run_as)), language="powershell")
            st.caption("Exécution immédiate, sans attendre le calendrier")
            st.code(format_command(build_run_command(spec)), language="powershell")
            st.caption("Désinstallation de la tâche Windows uniquement")
            st.code(format_command(build_uninstall_command(spec)), language="powershell")
            st.caption(f"Journal principal : {spec.log_file} · Statut de configuration : {spec.status}")

        install_col, run_col, uninstall_col = st.columns(3)
        with install_col:
            if st.button("♻️ Installer / réinstaller", key=f"batch_install_{spec.name}", use_container_width=True):
                with st.spinner(f"Installation de {spec.name}…"):
                    result = install_batch(spec, run_as=run_as)
                if result.ok:
                    st.success("Tâche Windows installée ou mise à jour.")
                    _task_states.clear()
                else:
                    st.error(f"Échec de l’installation (code {result.returncode}).")
                    st.code((result.stderr or result.stdout or "Aucun détail")[-6000:], language="text")
        with run_col:
            scheduled_running = bool(task and str(task.get("state")) == "Running")
            disabled = not spec.runnable or bool(active) or scheduled_running
            if st.button("▶️ Lancer maintenant", key=f"batch_run_{spec.name}", disabled=disabled, use_container_width=True):
                try:
                    record = start_batch(spec, db_config=get_runtime_db_config())
                except Exception as exc:
                    st.error(f"Impossible de lancer le batch : {exc}")
                else:
                    st.success(f"Batch lancé en arrière-plan · run {record.run_id}")
                    st.rerun()
            if not spec.runnable:
                st.caption("Activation impossible tant que le batch est désactivé ou en attente de fournisseur/quota.")
            elif active:
                st.caption("Une exécution lancée depuis l’IHM est déjà active.")
            elif scheduled_running:
                st.caption("La tâche Windows est déjà en cours : un doublon est bloqué.")
        with uninstall_col:
            uninstall_disabled = task is None or bool(active) or scheduled_running
            if st.button(
                "🗑️ Désinstaller", key=f"batch_uninstall_{spec.name}",
                disabled=uninstall_disabled, use_container_width=True,
                help="Supprime uniquement la tâche du Planificateur Windows. Configuration, données et journaux sont conservés.",
            ):
                with st.spinner(f"Désinstallation de {spec.name}…"):
                    result = uninstall_batch(spec)
                if result.ok:
                    st.success("Tâche Windows désinstallée. Les données et la configuration sont conservées.")
                    _task_states.clear()
                    st.rerun()
                else:
                    st.error(f"Échec de la désinstallation (code {result.returncode}).")
                    st.code((result.stderr or result.stdout or "Aucun détail")[-6000:], language="text")
            if task is None:
                st.caption("Aucune tâche Windows à désinstaller.")

        launcher_log = read_batch_log_tail(spec)
        ihm_log = read_pipeline_logs(str(recent.get("run_id")), "all") if recent and recent.get("run_id") else ""
        if launcher_log or ihm_log:
            with st.expander("Derniers journaux"):
                selected_log = ihm_log or launcher_log
                st.code(selected_log[-12000:], language="text")
                st.download_button(
                    "Télécharger le journal affiché", selected_log,
                    file_name=f"{spec.name}.log", mime="text/plain",
                    key=f"batch_log_{spec.name}",
                )


def _render_bulk_result(action: str, results: dict[str, Any], skipped: list[str]) -> None:
    succeeded = [name for name, result in results.items() if result.ok]
    failed = {name: result for name, result in results.items() if not result.ok}
    if failed:
        st.error(
            f"{action} terminée avec erreurs : {len(succeeded)} succès, "
            f"{len(failed)} échec(s), {len(skipped)} ignoré(s)."
        )
        with st.expander("Détails des échecs globaux", expanded=True):
            for name, result in failed.items():
                st.markdown(f"**{name}** — code {result.returncode}")
                st.code((result.stderr or result.stdout or "Aucun détail")[-4000:], language="text")
    else:
        st.success(
            f"{action} terminée : {len(succeeded)} tâche(s) traitée(s), "
            f"{len(skipped)} ignorée(s). Actualisez les états pour confirmer."
        )
    if skipped:
        st.warning("Ignorés car en cours d’exécution : " + ", ".join(skipped))


def render() -> None:
    st.title("🗓️ Batchs planifiés")
    st.caption(
        "Catalogue central de batch.yaml : rôle de chaque collecte, priorité, état réel du "
        "Planificateur Windows, dernières écritures et pilotage manuel."
    )

    specs = load_batch_specs()
    tasks, task_error = _task_states()
    db_runs, db_error = _latest_collection_runs()
    active = list_active_batch_runs()
    active_by_batch: dict[str, list[dict[str, object]]] = {}
    for row in active:
        name = str(row.get("step_key") or "").removeprefix("batch:")
        active_by_batch.setdefault(name, []).append(row)
    history_by_batch: dict[str, dict[str, object]] = {}
    for row in load_pipeline_history():
        key = str(row.get("step_key") or "")
        if key.startswith("batch:"):
            history_by_batch.setdefault(key.removeprefix("batch:"), row)

    installed_runnable = sum(spec.task_name in tasks and spec.runnable for spec in specs)
    installed_dormant = sum(spec.task_name in tasks and not spec.runnable for spec in specs)
    top1, top2, top3, top4, top5 = st.columns(5)
    top1.metric("Configurés", len(specs))
    top2.metric("Exécutables (batch.yaml)", sum(spec.runnable for spec in specs))
    top3.metric("Installés et exécutables", installed_runnable)
    top4.metric("Installés mais dormants", installed_dormant)
    top5.metric("En cours via l’IHM", len(active))

    if installed_dormant:
        st.info(
            f"{installed_dormant} tâche(s) Windows sont installées mais neutralisées par "
            "enabled=false ou un statut d’attente dans batch.yaml. Elles ne collectent aucune donnée."
        )

    if task_error:
        st.warning(f"État du Planificateur Windows indisponible : {task_error}")
    if db_error:
        st.info(f"Historique détaillé indisponible : {db_error}")

    controls = st.columns([2, 2, 1, 1])
    search = controls[0].text_input("Rechercher", placeholder="Nom, table, fournisseur…")
    priorities = controls[1].multiselect(
        "Priorités", [f"P{i}" for i in range(5)], default=[f"P{i}" for i in range(5)]
    )
    state_filter = controls[2].selectbox(
        "État", ["Tous", "Installés", "Non installés", "Exécutables", "En attente"]
    )
    run_as = controls[3].selectbox(
        "Compte tâche", ["Interactive", "System"],
        help="Interactive est recommandé. System requiert généralement des droits administrateur.",
    )

    busy_names = {
        spec.name for spec in specs
        if active_by_batch.get(spec.name)
        or str((tasks.get(spec.task_name) or {}).get("state") or "") == "Running"
    }
    global_col1, global_col2, global_col3 = st.columns(3)
    if global_col1.button("🔄 Actualiser les états", use_container_width=True):
        _task_states.clear()
        _latest_collection_runs.clear()
        st.rerun()
    if global_col2.button(
        "♻️ Installer / réinstaller tous", use_container_width=True,
        help="Installe les 19 tâches configurées. Les batchs enabled=false resteront dormants.",
    ):
        install_specs = [spec for spec in specs if spec.name not in busy_names]
        with st.spinner(f"Installation de {len(install_specs)} tâche(s) Windows…"):
            results = install_all_batches(install_specs, run_as=run_as)
        _task_states.clear()
        _render_bulk_result("Installation globale", results, sorted(busy_names))
    installed_specs = [spec for spec in specs if spec.task_name in tasks]
    uninstall_specs = [spec for spec in installed_specs if spec.name not in busy_names]
    if global_col3.button(
        "🗑️ Désinstaller tous les batchs",
        disabled=not installed_specs,
        use_container_width=True,
        help="Supprime toutes les tâches Batch installées, mais conserve batch.yaml, les données et les journaux.",
    ):
        with st.spinner(f"Désinstallation de {len(uninstall_specs)} tâche(s) Windows…"):
            results = uninstall_all_batches(uninstall_specs)
        _task_states.clear()
        _render_bulk_result("Désinstallation globale", results, sorted(busy_names))

    needle = search.strip().lower()
    visible: list[BatchSpec] = []
    for spec in specs:
        installed = spec.task_name in tasks
        haystack = " ".join((spec.name, spec.description, spec.provider, " ".join(spec.tables))).lower()
        if spec.priority not in priorities or (needle and needle not in haystack):
            continue
        if state_filter == "Installés" and not installed:
            continue
        if state_filter == "Non installés" and installed:
            continue
        if state_filter == "Exécutables" and not spec.runnable:
            continue
        if state_filter == "En attente" and spec.runnable:
            continue
        visible.append(spec)

    st.caption(f"{len(visible)} batch(s) affiché(s) sur {len(specs)}.")
    for spec in visible:
        batch_active = active_by_batch.get(spec.name, [])
        recent = batch_active[0] if batch_active else history_by_batch.get(spec.name)
        _render_batch(
            spec, tasks.get(spec.task_name), db_runs.get(spec.name),
            run_as=run_as, active=batch_active, recent=recent,
        )


run_page_if_standalone(__name__, render)
