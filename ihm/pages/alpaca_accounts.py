"""ihm/pages/alpaca_accounts.py — Consultation des comptes Alpaca."""
from __future__ import annotations

from typing import Any, cast

import pandas as pd
import streamlit as st

from ihm.components.db_controls import render_db_connection_form
from ihm.components.metrics import metric_row
from ihm.components.symbol_table import ActionSpec, render_symbol_table
from ihm.components.tables import show_dataframe
from ihm.pages import run_page_if_standalone
from ihm.services.alpaca_accounts import (
	build_account_label,
	close_position_all,
	get_live_account,
	get_live_orders,
	get_live_portfolio_history,
	get_live_positions,
	get_registered_accounts,
	resolve_selected_account_id,
)
from ihm.services.orphan_adoption_service import adopt_after_close
from ihm.services.db import db_available
from ihm.services.queries import (
	get_broker_account_snapshots_history,
	get_execution_orders,
	get_execution_runs,
)
from service.broker_failover import build_failover_doctrine_summary

_PAGE_ACCOUNT_SELECT_KEY = "alpaca_accounts_page_account_id"


def _format_currency(value: object) -> str:
	try:
		amount = float(cast(float | int | str, value))
	except (TypeError, ValueError):
		return "—"
	return f"${amount:,.2f}"


def _format_bool(value: object) -> str:
	return "Oui" if bool(value) else "Non"


def _build_account_details_dataframe(account_payload: dict[str, Any]) -> pd.DataFrame:
	fields = [
		("Statut", account_payload.get("status")),
		("Devise", account_payload.get("currency")),
		("Type de compte", account_payload.get("account_type") or account_payload.get("type")),
		("Multiplier", account_payload.get("multiplier")),
		("Pattern day trader", _format_bool(account_payload.get("pattern_day_trader"))),
		("Trading bloqué", _format_bool(account_payload.get("trading_blocked"))),
		("Compte bloqué", _format_bool(account_payload.get("account_blocked"))),
		("Transferts bloqués", _format_bool(account_payload.get("transfers_blocked"))),
		("Short autorisé", _format_bool(account_payload.get("shorting_enabled"))),
		("Créé le", account_payload.get("created_at")),
		("Dernière equity broker", _format_currency(account_payload.get("last_equity"))),
	]
	rows = [
		{"Champ": label, "Valeur": value if value not in (None, "") else "—"}
		for label, value in fields
	]
	return pd.DataFrame(rows)


def _render_live_account_summary(account_payload: dict[str, Any]) -> None:
	metric_row(
		[
			("Equity", _format_currency(account_payload.get("equity") or account_payload.get("portfolio_value")), None),
			("Cash", _format_currency(account_payload.get("cash")), None),
			("Buying power", _format_currency(account_payload.get("buying_power")), None),
			("Day trades", int(float(account_payload.get("daytrade_count") or 0)), None),
		]
	)
	st.caption(
		"Statut=`{}` | PDT=`{}` | Trading bloqué=`{}` | Short autorisé=`{}`".format(
			account_payload.get("status", "—"),
			_format_bool(account_payload.get("pattern_day_trader")),
			_format_bool(account_payload.get("trading_blocked")),
			_format_bool(account_payload.get("shorting_enabled")),
		)
	)
	show_dataframe(_build_account_details_dataframe(account_payload), height=420)


def _render_capital_history(*, account_id: str, portfolio_history: pd.DataFrame, snapshot_history: pd.DataFrame) -> None:
	st.subheader("📈 Évolution du capital")
	if not portfolio_history.empty and {"timestamp", "equity"}.issubset(portfolio_history.columns):
		st.caption("Source prioritaire : endpoint broker Alpaca `portfolio history`.")
		chart_df = portfolio_history[["timestamp", "equity"]].dropna().copy().set_index("timestamp")
		st.line_chart(chart_df, y="equity", use_container_width=True, height=320)
		first_equity = float(chart_df["equity"].iloc[0])
		last_equity = float(chart_df["equity"].iloc[-1])
		delta_pct = ((last_equity / first_equity) - 1.0) * 100.0 if first_equity else 0.0
		metric_row(
			[
				("Points série", len(chart_df), None),
				("Départ", _format_currency(first_equity), None),
				("Dernier point", _format_currency(last_equity), None),
				("Variation", f"{delta_pct:.2f}%", None),
			]
		)
		history_columns = [column for column in ["timestamp", "equity", "profit_loss", "profit_loss_pct"] if column in portfolio_history.columns]
		show_dataframe(portfolio_history[history_columns], title="Historique broker détaillé", height=260)
		return

	if not snapshot_history.empty and {"created_at", "equity"}.issubset(snapshot_history.columns):
		st.caption(
			"Fallback : historique reconstruit depuis `broker_account_snapshots` en base Alpha Trade. "
			"La granularité dépend des runs d'exécution persistés."
		)
		prepared = snapshot_history[["created_at", "equity", "cash", "settled_cash", "buying_power", "snapshot_kind"]].dropna(subset=["created_at", "equity"]).copy()
		if not prepared.empty:
			prepared["created_at"] = pd.to_datetime(prepared["created_at"], utc=True, errors="coerce")
			prepared = prepared.sort_values("created_at", ascending=True)
			chart_df = prepared[["created_at", "equity"]].set_index("created_at")
			st.line_chart(chart_df, y="equity", use_container_width=True, height=320)
			show_dataframe(prepared.sort_values("created_at", ascending=False), title="Snapshots broker persistés", height=260)
			return

	st.info(
		f"Aucun historique de capital exploitable pour le compte `{account_id}` : ni `portfolio history` live, ni `broker_account_snapshots` disponibles."
	)


def _clear_page_caches() -> None:
	get_live_account.clear()
	get_live_positions.clear()
	get_live_orders.clear()
	get_live_portfolio_history.clear()
	get_broker_account_snapshots_history.clear()
	get_execution_orders.clear()
	get_execution_runs.clear()


def _build_failover_doctrine_dataframe(summary: dict[str, Any]) -> pd.DataFrame:
	return pd.DataFrame(
		[
			{"Champ": "Broker primaire", "Valeur": summary.get("primary_broker") or "—"},
			{"Champ": "Broker secondaire", "Valeur": summary.get("secondary_broker") or "—"},
			{"Champ": "Seuil circuit breaker", "Valeur": summary.get("circuit_breaker_threshold") or "—"},
			{"Champ": "Mode après bascule", "Valeur": summary.get("mode_when_tripped") or "—"},
			{"Champ": "Écritures suspendues", "Valeur": _format_bool(summary.get("writes_suspended"))},
			{"Champ": "Sentinelle RESUME", "Valeur": summary.get("resume_flag_path") or "—"},
			{"Champ": "Sentinelle présente", "Valeur": _format_bool(summary.get("resume_flag_present"))},
		]
	)


def _render_failover_doctrine_panel() -> None:
	summary = build_failover_doctrine_summary()
	st.subheader("🛡️ Doctrine broker primaire / secondaire")
	st.caption(
		"Le mode normal reste `Alpaca` en primaire. En cas de panne répétée, la lecture peut basculer en mode dégradé "
		"vers le secondaire, mais les écritures restent suspendues jusqu'à reprise opérateur explicite."
	)
	show_dataframe(_build_failover_doctrine_dataframe(summary), height=240)
	steps = summary.get("steps") or []
	if steps:
		for step in steps:
			st.markdown(f"- {step}")
	if bool(summary.get("resume_flag_present")):
		st.warning("La sentinelle `RESUME` est présente : une reprise opérateur a été demandée ou doit être consommée par le wrapper failover.")
	else:
		st.info("Aucune sentinelle `RESUME` détectée : toute reprise après failover nécessite une action opérateur explicite.")


def render() -> None:
	st.header("🏦 Comptes Alpaca")
	st.caption(
		"Consultation centralisée des comptes Alpaca : état live du compte, évolution du capital, positions ouvertes et historique des ordres."
	)

	accounts = get_registered_accounts()
	if not accounts:
		st.warning("Aucun compte Alpaca configuré. Vérifie `config.yaml` ou les variables d'environnement `ALPACA_*`.")
		return

	account_ids = [account.account_id for account in accounts]
	account_labels = {account.account_id: build_account_label(account) for account in accounts}
	default_account_id = resolve_selected_account_id(st.session_state.get("selected_account_id"))
	resolved_default_account_id = str(default_account_id) if default_account_id in account_ids else account_ids[0]
	default_index = account_ids.index(resolved_default_account_id)

	selector_col, action_col = st.columns([4, 1])
	with selector_col:
		selected_account_id = st.selectbox(
			"Compte à consulter",
			options=account_ids,
			index=default_index,
			format_func=lambda account_id: str(account_labels.get(account_id, account_id)),
			key=_PAGE_ACCOUNT_SELECT_KEY,
		)
	with action_col:
		st.write("")
		st.write("")
		if st.button("Rafraîchir", use_container_width=True):
			_clear_page_caches()
			st.rerun()

	st.session_state["selected_account_id"] = selected_account_id
	selected_account = next(account for account in accounts if account.account_id == selected_account_id)
	st.info(
		f"Compte actif : `{selected_account.account_id}` | label=`{selected_account.label}` | mode=`{selected_account.mode}` | rafraîchissement auto ~60s."
	)

	with st.container(border=True):
		st.subheader("🧾 État live du compte")
		try:
			account_payload = get_live_account(selected_account_id)
		except Exception as exc:  # noqa: BLE001
			st.warning(f"Impossible de lire l'état live du compte via Alpaca : {exc}")
		else:
			if not account_payload:
				st.info("Le broker n'a retourné aucun payload compte exploitable.")
			else:
				_render_live_account_summary(account_payload)
				with st.expander("Payload brut broker", expanded=False):
					st.json(account_payload)

	left_col, right_col = st.columns(2)

	with left_col:
		with st.container(border=True):
			try:
				positions_df = get_live_positions(selected_account_id)
			except Exception as exc:  # noqa: BLE001
				st.warning(f"Impossible de lire les positions live : {exc}")
			else:
				def _sell_all_callback(symbol: str, row: pd.Series) -> None:  # noqa: ARG001
					try:
						close_payload = close_position_all(selected_account_id, symbol)
					except Exception as exc:  # noqa: BLE001
						st.error(f"❌ Échec de la clôture de `{symbol}` : {exc}")
						return
					st.toast(f"Position {symbol} clôturée auprès du broker.", icon="✅")
					# Sprint 2026-05 — adoption synchrone de la vente manuelle
					# (Q5 / Q6 du FAQ opérateur). Crée immédiatement le
					# ``OrderIntent`` ``adopted_exit`` correspondant dans le
					# journal canonique sans attendre le prochain cycle de
					# réconciliation broker.
					try:
						adopted = adopt_after_close(
							account_id=selected_account_id,
							symbol=symbol,
							close_payload=close_payload,
						)
					except Exception as exc:  # noqa: BLE001
						st.warning(
							f"Vente {symbol} OK côté broker mais l'adoption canonique a échoué : {exc}. "
							"La prochaine réconciliation rattrapera l'audit trail."
						)
					else:
						if adopted:
							st.toast(
								f"Vente {symbol} adoptée dans le journal Alpha Trade.",
								icon="📒",
							)
					# Invalide tous les caches dépendants pour rafraîchir simultanément :
					# - tableau « Positions ouvertes (broker) » (le symbole peut disparaître),
					# - tableau « Historique des ordres (broker) » (l'ordre de clôture y apparaît),
					# - état du compte (cash / buying power impactés).
					get_live_positions.clear()
					get_live_orders.clear()
					get_live_account.clear()
					get_execution_orders.clear()
					# Réinitialise la sélection pour que la barre d'actions ne reste pas
					# affichée sur une ligne potentiellement disparue après le rerun.
					st.session_state.pop("alpaca_live_positions", None)
					st.rerun()

				render_symbol_table(
					positions_df,
					key="alpaca_live_positions",
					symbol_col="symbol",
					title="📦 Positions ouvertes (broker)",
					height=320,
					extra_actions=[
						ActionSpec(
							label="🔴 Vendre tout",
							callback=_sell_all_callback,
							key="sell_all",
							confirm=True,
							confirm_label="✅ Confirmer la vente totale",
						),
					],
				)

	with right_col:
		with st.container(border=True):
			try:
				orders_df = get_live_orders(selected_account_id)
			except Exception as exc:  # noqa: BLE001
				st.warning(f"Impossible de lire l'historique live des ordres : {exc}")
			else:
				render_symbol_table(
					orders_df,
					key="alpaca_live_orders",
					symbol_col="symbol",
					title="🧾 Historique des ordres (broker)",
					height=320,
				)

	snapshot_history_df = pd.DataFrame()
	if db_available():
		snapshot_history_df = get_broker_account_snapshots_history(selected_account_id)
	with st.container(border=True):
		try:
			portfolio_history_df = get_live_portfolio_history(selected_account_id)
		except Exception as exc:  # noqa: BLE001
			st.warning(f"Impossible de lire `portfolio history` chez Alpaca : {exc}")
			portfolio_history_df = pd.DataFrame()
		_render_capital_history(
			account_id=selected_account_id,
			portfolio_history=portfolio_history_df,
			snapshot_history=snapshot_history_df,
		)

	with st.container(border=True):
		_render_failover_doctrine_panel()

	with st.container(border=True):
		st.subheader("🗂️ Historique canonique Alpha Trade")
		st.caption(
			"Cette zone exploite la base Alpha Trade pour compléter les données live du broker avec les snapshots et runs persistés par le moteur d'exécution."
		)
		if not db_available():
			st.info("Connexion DB absente : les historiques canoniques Alpha Trade ne sont pas disponibles pour l'instant.")
			with st.expander("Configurer la connexion DB", expanded=False):
				render_db_connection_form("alpaca_accounts_db_form", show_host_fields=True)
		else:
			execution_runs_df = get_execution_runs(limit=20, account_id=selected_account_id)
			canonical_orders_df = get_execution_orders(account_id=selected_account_id)
			recent_snapshot_columns = [
				column
				for column in [
					"created_at",
					"snapshot_kind",
					"equity",
					"cash",
					"settled_cash",
					"buying_power",
					"daytrade_count",
					"exec_run_id",
				]
				if column in snapshot_history_df.columns
			]
			if recent_snapshot_columns:
				show_dataframe(
					snapshot_history_df[recent_snapshot_columns],
					title="🧮 Snapshots broker persistés",
					height=240,
				)
			render_symbol_table(
				canonical_orders_df,
				key="alpaca_canonical_orders",
				symbol_col="symbol",
				title="📋 Ordres canoniques d'exécution (DB)",
				height=260,
			)
			show_dataframe(execution_runs_df, title="🚀 Runs d'exécution récents (DB)", height=240)


run_page_if_standalone(__name__, render)


