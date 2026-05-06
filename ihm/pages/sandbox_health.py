"""Sprint S24.2 — Page IHM Sandbox health (streak 30 j)."""
from __future__ import annotations

import streamlit as st

from ihm.components.help_tooltip import _help
from ihm.components.kpi_card import kpi_card
from ihm.components.section_header import section_header
from ihm.services.sandbox_health_loader import load_day, load_rollup
from ihm.theme.badges import status_badge

PAGE = "sandbox_health"

_STATUS_BADGES = {
    "success": ("🟢", "ok"),
    "failure": ("🔴", "danger"),
    "cancelled": ("🟡", "warning"),
    "missing": ("⚪", "neutral"),
    "unknown": ("⚪", "neutral"),
}


def _streak_level(green: int) -> str:
    if green >= 30:
        return "ok"
    if green >= 7:
        return "warning"
    return "danger"


def render() -> None:
    section_header(
        st,
        title="Sandbox health (30 j)",
        subtitle="Stabilité de la sandbox nightly paper sur 30 jours glissants",
        help_key="overview",
        page=PAGE,
        icon="🟢",
    )

    rollup = load_rollup()
    if not rollup:
        st.warning(
            "Aucun rollup disponible. Lancez "
            "`python scripts/sandbox_health_rollup.py` ou attendez "
            "le prochain run du workflow `sandbox_nightly`."
        )
        return

    streak_green = int(rollup.get("streak_green", 0))
    level = _streak_level(streak_green)
    st.caption(status_badge(
        f"Streak verte : {streak_green} j / objectif 30",
        level,
    ))

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        kpi_card(st, "Streak verte (j)", streak_green,
                 help_key="streak_green", page=PAGE)
    with col2:
        kpi_card(st, "Échecs (30 j)", int(rollup.get("n_failure", 0)),
                 help_key="n_failure", page=PAGE)
    with col3:
        kpi_card(st, "Succès (30 j)", int(rollup.get("n_success", 0)),
                 help_key="n_success", page=PAGE)
    with col4:
        kpi_card(st, "Jours observés", int(rollup.get("n_days_observed", 0)),
                 help_key="n_days_observed", page=PAGE)

    st.divider()
    st.markdown("### 📅 Calendrier")
    calendar = rollup.get("calendar", [])
    if calendar:
        # rendu compact : 1 ligne par jour, badge couleur + lien détail
        for entry in calendar:
            d = entry["date"]
            status = entry["status"]
            icon, lvl = _STATUS_BADGES.get(status, _STATUS_BADGES["unknown"])
            st.write(f"{icon} `{d}` — {status_badge(status.upper(), lvl)}")
    else:
        st.info("Calendrier vide.")

    st.divider()
    st.markdown("### 🔍 Détail d'un jour")
    if calendar:
        choices = [c["date"] for c in calendar]
        selected = st.selectbox(
            "Date",
            choices,
            help=_help(PAGE, "select_day"),
            key="sandbox_health_select_day",
        )
        day_payload = load_day(selected) if selected else {}
        if day_payload:
            st.json(day_payload)
        else:
            st.info(f"Pas de health.json pour {selected}.")

    st.divider()
    last_failure = rollup.get("last_failure")
    if last_failure:
        st.warning(f"Dernier échec observé : **{last_failure}**. "
                   "Voir `doc/sandbox_health_runbook.md`.")

