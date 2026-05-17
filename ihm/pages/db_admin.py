"""ihm/pages/db_admin.py — Administration et purge sélective de la base."""
from __future__ import annotations

import streamlit as st

from ihm.components.db_controls import render_db_connection_form, render_db_unavailable
from ihm.components.ops_command_panel import render_ops_command_panel
from ihm.pages import run_page_if_standalone
from ihm.services.db import get_engine, get_runtime_db_config, reset_db_caches
from ihm.services.db_admin import (
	FUNCTIONALITY_GROUP_ORDER,
	PROTECTED_TABLES,
	TableCatalogEntry,
	TablePurgePlan,
	build_table_purge_plan,
	execute_table_purge,
	list_grouped_tables,
	load_database_table_snapshot,
)

CHECKBOX_PREFIX = "ihm_db_admin_table_"
CONFIRM_PURGE_KEY = "ihm_db_admin_confirm_purge"
PENDING_RESET_TABLES_KEY = "ihm_db_admin_pending_reset_tables"
PENDING_RESET_CONFIRM_KEY = "ihm_db_admin_pending_reset_confirm"
LAST_PURGE_FEEDBACK_KEY = "ihm_db_admin_last_purge_feedback"


def _checkbox_key(table_name: str) -> str:
	return f"{CHECKBOX_PREFIX}{table_name}"


def _set_selection(grouped_tables: dict[str, list[TableCatalogEntry]], *, value: bool) -> None:
	for entries in grouped_tables.values():
		for entry in entries:
			if entry.exists_in_database and not entry.protected:
				st.session_state[_checkbox_key(entry.table_name)] = value


def _apply_pending_widget_resets(grouped_tables: dict[str, list[TableCatalogEntry]]) -> None:
	reset_tables = st.session_state.pop(PENDING_RESET_TABLES_KEY, None)
	if isinstance(reset_tables, list):
		known_tables = {entry.table_name for entries in grouped_tables.values() for entry in entries}
		for table_name in reset_tables:
			if isinstance(table_name, str) and table_name in known_tables:
				st.session_state[_checkbox_key(table_name)] = False

	if bool(st.session_state.pop(PENDING_RESET_CONFIRM_KEY, False)):
		st.session_state[CONFIRM_PURGE_KEY] = False


def _render_last_purge_feedback() -> None:
	feedback = st.session_state.pop(LAST_PURGE_FEEDBACK_KEY, None)
	if not isinstance(feedback, dict):
		return

	executed_tables_raw = feedback.get("executed_tables")
	total_rows_raw = feedback.get("total_rows_affected")
	executed_tables = [table_name for table_name in executed_tables_raw if isinstance(table_name, str)] if isinstance(executed_tables_raw, list) else []
	total_rows = total_rows_raw if isinstance(total_rows_raw, int) and total_rows_raw >= 0 else 0

	if not executed_tables:
		st.success("Vidage terminé.")
		return

	st.success(
		f"Vidage terminé pour {len(executed_tables)} table(s). Total de lignes affectées : {total_rows}."
	)
	st.caption("Tables vidées lors de la dernière exécution : " + ", ".join(f"`{table_name}`" for table_name in executed_tables))


def _build_execute_blockers(plan: TablePurgePlan, *, confirm_purge: bool) -> tuple[str, ...]:
	blockers: list[str] = []

	if not plan.operations:
		if plan.protected_tables and not plan.missing_tables and not plan.blocked_by_dependencies:
			blockers.append("La sélection courante ne contient aucune table purgeable exécutable.")
		else:
			blockers.append("Aucune commande SQL exécutable n'a été générée pour la sélection courante.")

	if plan.missing_tables:
		blockers.append("Retirez les tables absentes de la sélection avant exécution.")

	if plan.blocked_by_dependencies:
		blockers.append("Sélectionnez également les tables dépendantes listées ci-dessus avant de lancer le vidage.")

	if not confirm_purge:
		blockers.append("Cochez la case de confirmation pour activer le bouton d'exécution.")

	return tuple(blockers)


def _render_group(group_name: str, entries: list[TableCatalogEntry]) -> None:
	purgeable_count = sum(1 for entry in entries if entry.exists_in_database and not entry.protected)
	with st.expander(f"{group_name} ({len(entries)} tables, {purgeable_count} purgeables)", expanded=True):
		for entry in entries:
			cols = st.columns([3.6, 1.5, 1.4, 2.5])
			disabled = bool(entry.protected or not entry.exists_in_database)
			help_text = None
			if entry.protected:
				help_text = "Table protégée : elle reste visible mais ne peut pas être vidée depuis l'IHM."
			elif not entry.exists_in_database:
				help_text = "Table attendue dans le référentiel projet mais absente de la base connectée."

			cols[0].checkbox(
				entry.table_name,
				key=_checkbox_key(entry.table_name),
				disabled=disabled,
				help=help_text,
			)

			row_estimate = "—" if entry.row_estimate is None else f"≈ {entry.row_estimate:,}".replace(",", " ")
			cols[1].markdown(f"**Lignes**  \n{row_estimate}")
			cols[2].markdown(
				"**Statut**  \n"
				+ (
					"🔒 protégée"
					if entry.protected
					else "🟢 présente"
					if entry.exists_in_database
					else "⚪ absente"
				)
			)
			cols[3].markdown(
				"**Action**  \n"
				+ (
					"exclue"
					if entry.protected
					else "DELETE FROM"
					if entry.exists_in_database
					else "indisponible"
				)
			)


def render() -> None:
	st.header("🗃️ Administration DB")
	st.caption(
		"Catalogue des tables groupées par fonctionnalité. Le bouton de purge vide uniquement les données des tables cochées ; aucune table n'est supprimée."
	)
	st.warning(
		"⚠️ Les tables `stock_metadata`, `stock_bars`, `stock_bars_daily`, `news_raw`, `news_ticker_map` et `news_ingestion_checkpoint` sont explicitement protégées et ne peuvent pas être vidées depuis cette page."
	)

	with st.expander("🗄️ Connexion DB", expanded=False):
		render_db_connection_form("db_admin_connection_form", show_host_fields=True)

	engine = get_engine()
	if engine is None:
		render_db_unavailable("Administration DB", form_key="db_admin_inline_connection_form")
		return

	snapshot = load_database_table_snapshot(engine)
	grouped_tables = list_grouped_tables(snapshot)
	_apply_pending_widget_resets(grouped_tables)
	active_db = get_runtime_db_config()

	st.info(
		f"Base active : `{active_db.get('name')}` sur `{active_db.get('host')}` — source `{active_db.get('source')}`."
	)
	_render_last_purge_feedback()

	action_col1, action_col2, action_col3 = st.columns(3)
	if action_col1.button("Sélectionner toutes les tables purgeables", use_container_width=True):
		_set_selection(grouped_tables, value=True)
		st.rerun()
	if action_col2.button("Tout désélectionner", use_container_width=True):
		_set_selection(grouped_tables, value=False)
		st.rerun()
	if action_col3.button("Rafraîchir le catalogue", use_container_width=True):
		reset_db_caches(clear_errors=False)
		st.rerun()

	for group_name in FUNCTIONALITY_GROUP_ORDER:
		entries = grouped_tables.get(group_name)
		if entries:
			_render_group(group_name, entries)
	for group_name, entries in grouped_tables.items():
		if group_name not in FUNCTIONALITY_GROUP_ORDER:
			_render_group(group_name, entries)

	selected_tables = [
		entry.table_name
		for entries in grouped_tables.values()
		for entry in entries
		if st.session_state.get(_checkbox_key(entry.table_name), False)
	]

	st.divider()
	st.subheader("🧹 Plan de vidage")

	if not selected_tables:
		st.info("Cochez une ou plusieurs tables purgeables pour afficher le plan SQL correspondant.")
		return

	plan = build_table_purge_plan(selected_tables, snapshot)

	if plan.protected_tables:
		st.warning(
			"Tables protégées ignorées : " + ", ".join(f"`{table_name}`" for table_name in plan.protected_tables)
		)

	if plan.missing_tables:
		st.error(
			"Tables absentes dans la base connectée : " + ", ".join(f"`{table_name}`" for table_name in plan.missing_tables)
		)

	if plan.blocked_by_dependencies:
		st.error(
			"Certaines suppressions seraient bloquées par des tables filles non sélectionnées. Sélectionnez aussi les dépendances listées ci-dessous avant de lancer le vidage."
		)
		for table_name, dependent_tables in plan.blocked_by_dependencies.items():
			st.markdown(
				f"- `{table_name}` dépend encore de : {', '.join(f'`{child_table}`' for child_table in dependent_tables)}"
			)

	if plan.cycle_tables:
		st.warning(
			"Cycle de dépendances détecté sur : " + ", ".join(f"`{table_name}`" for table_name in plan.cycle_tables)
			+ ". L'ordre final est un best effort ; validez soigneusement avant exécution."
		)

	if plan.operations:
		st.caption("Ordre d'exécution calculé pour respecter au mieux les clés étrangères détectées.")
		st.code("\n".join(operation.statement for operation in plan.operations), language="sql")
		for operation in plan.operations:
			st.caption(f"- `{operation.table_name}` : {operation.reason}")
	else:
		st.info("Aucune commande exécutable pour la sélection courante.")

	confirm_purge = st.checkbox(
		"Je confirme vouloir vider définitivement les données des tables sélectionnées.",
		key=CONFIRM_PURGE_KEY,
	)
	execution_blockers = _build_execute_blockers(plan, confirm_purge=confirm_purge)
	can_execute = not execution_blockers

	if execution_blockers:
		st.info("Le bouton d'exécution reste désactivé tant que les points suivants ne sont pas validés :")
		for blocker in execution_blockers:
			st.markdown(f"- {blocker}")
	else:
		st.success("Confirmation reçue : le bouton d'exécution est prêt.")

	if st.button(
		"🧨 Vider les tables sélectionnées",
		type="primary",
		use_container_width=True,
		disabled=not can_execute or not confirm_purge,
	):
		try:
			result = execute_table_purge(engine, plan)
		except Exception as exc:
			st.error(f"Échec du vidage : {exc}")
		else:
			st.session_state[PENDING_RESET_TABLES_KEY] = list(result.executed_tables)
			st.session_state[PENDING_RESET_CONFIRM_KEY] = True
			st.session_state[LAST_PURGE_FEEDBACK_KEY] = {
				"executed_tables": list(result.executed_tables),
				"total_rows_affected": result.total_rows_affected,
			}
			reset_db_caches(clear_errors=False)
			st.rerun()

	protected_names = ", ".join(sorted(PROTECTED_TABLES))
	st.caption(f"Tables protégées côté IHM : `{protected_names}`.")

	# ---- Sprint S26 (gap P3) — Restauration depuis backup ------------
	st.divider()
	st.subheader("♻️ Restauration depuis backup")
	st.caption(
		"Exécute `scripts/restore_from_backup.py` pour restaurer la base depuis un dump SQL "
		"(option `--dump-path`). Action **destructive** — confirmation requise."
	)
	with st.container(border=True):
		backup_path = st.text_input(
			"Chemin du dump SQL (`--dump-path`)",
			key="db_admin_restore_dump_path",
			placeholder="/backups/alpha_trade-20260506.sql.gz",
		)
		col1, col2, col3 = st.columns(3)
		with col1:
			dry_run = st.checkbox("Dry-run", value=True, key="db_admin_restore_dry_run")
		with col2:
			skip_alembic = st.checkbox("Skip Alembic", value=False, key="db_admin_restore_skip_alembic")
		with col3:
			skip_audit = st.checkbox("Skip audit", value=False, key="db_admin_restore_skip_audit")
		if backup_path.strip():
			render_ops_command_panel(
				"restore_from_backup",
				confirm_phrase=None if dry_run else "RESTORE",
				command_kwargs={
					"backup_path": backup_path.strip(),
					"dry_run": dry_run,
					"skip_alembic": skip_alembic,
					"skip_audit": skip_audit,
				},
			)
		else:
			st.info("Renseigne le chemin du dump pour activer le bouton.")


run_page_if_standalone(__name__, render)



