"""Composants réutilisables pour le diagnostic de dépendances Alpha Scanner."""
from __future__ import annotations

from typing import cast

import pandas as pd
import streamlit as st

from ihm.components.status_badges import badge


DependencyDiagnostic = dict[str, object]


def dependency_badge(status: str, label: str) -> str:
    status_map = {"green": "ok", "orange": "warn", "red": "error"}
    status_label = {"green": "OK", "orange": "À surveiller", "red": "Bloquant"}.get(status, "Inconnu")
    return badge(f"{label} · {status_label}", status_map.get(status, "info"))


def get_dependency_payload(diagnostic: DependencyDiagnostic | None, step_key: str) -> dict[str, object] | None:
    if not isinstance(diagnostic, dict):
        return None
    dependencies = diagnostic.get("dependencies")
    if not isinstance(dependencies, dict):
        return None
    payload = dependencies.get(step_key)
    return payload if isinstance(payload, dict) else None


def format_dependency_latest_date(value: object) -> str:
    text_value = str(value or "").strip()
    return text_value or "—"


def format_dependency_symbol_count(value: object) -> str:
    try:
        return f"{int(str(value))}"
    except (TypeError, ValueError):
        return "0"


def build_alpha_scanner_dependency_rows(diagnostic: DependencyDiagnostic | None) -> pd.DataFrame:
    if not isinstance(diagnostic, dict):
        return pd.DataFrame()
    dependencies = diagnostic.get("dependencies")
    if not isinstance(dependencies, dict) or not dependencies:
        return pd.DataFrame()

    rows: list[dict[str, object]] = []
    for payload in dependencies.values():
        if not isinstance(payload, dict):
            continue
        rows.append(
            {
                "Dépendance": dependency_badge(str(payload.get("status") or "red"), str(payload.get("label") or "dépendance")),
                "latest_date": format_dependency_latest_date(payload.get("latest_date")),
                "% couverture": f"{float(payload.get('coverage_pct') or 0.0):.1f}%",
                "N symboles": format_dependency_symbol_count(payload.get("covered_symbols")),
                "Univers": format_dependency_symbol_count(payload.get("eligible_symbols")),
                "Diagnostic": str(payload.get("reason") or "—"),
                "Commande": str(payload.get("command") or "—"),
            }
        )
    return pd.DataFrame(rows)


def render_dependency_metrics(payload: dict[str, object]) -> None:
    metric_col1, metric_col2, metric_col3 = st.columns(3)
    metric_col1.metric("latest_date", format_dependency_latest_date(payload.get("latest_date")))
    metric_col2.metric("% couverture", f"{float(payload.get('coverage_pct') or 0.0):.1f}%")
    metric_col3.metric("N symboles", format_dependency_symbol_count(payload.get("covered_symbols")))
    st.caption(
        f"Univers éligible de référence : `{format_dependency_symbol_count(payload.get('eligible_symbols'))}` symbole(s) | "
        f"table : `{payload.get('table')}`"
    )
    st.caption(str(payload.get("reason") or "Diagnostic indisponible."))


def render_alpha_scanner_dependency_panel(
    diagnostic: DependencyDiagnostic | None,
    *,
    title: str,
    expanded: bool = False,
    show_commands: bool = True,
) -> None:
    rows = build_alpha_scanner_dependency_rows(diagnostic)
    if rows.empty:
        return

    all_red = bool(diagnostic.get("all_red")) if isinstance(diagnostic, dict) else False
    any_red_or_orange = bool(diagnostic.get("any_red_or_orange")) if isinstance(diagnostic, dict) else False

    if all_red:
        st.error(
            "Alpha Scanner détecte deux dépendances rouges : les filtres `spread_bps` et `earnings_blackout` risquent d'être inexploitables."
        )
    elif any_red_or_orange:
        st.warning(
            "Alpha Scanner détecte une couverture partielle ou vieillissante sur ses dépendances quotes/earnings."
        )
    else:
        st.success("Dépendances Alpha Scanner OK : quotes et earnings sont alimentés pour les filtres stricts.")

    with st.expander(title, expanded=expanded):
        st.dataframe(rows, use_container_width=True, hide_index=True)
        if show_commands:
            quotes_payload = get_dependency_payload(diagnostic, "sync_latest_quotes")
            earnings_payload = get_dependency_payload(diagnostic, "sync_earnings_calendar")
            if quotes_payload or earnings_payload:
                cmd_col1, cmd_col2 = st.columns(2)
                if quotes_payload:
                    with cmd_col1:
                        st.code(str(quotes_payload.get("command") or "python -m dataIntegrityEngine.sync_latest_quotes"), language="powershell")
                if earnings_payload:
                    with cmd_col2:
                        st.code(str(earnings_payload.get("command") or "python -m dataIntegrityEngine.sync_earnings_calendar"), language="powershell")

