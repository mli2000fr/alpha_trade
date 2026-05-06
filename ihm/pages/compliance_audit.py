"""Sprint S19.5 / S24.4 — Page Compliance & Audit (stub).

Vue placeholder : visualisation chaîne audit HMAC + statut DR drill +
statut CVE + statut couverture/mutation. Le contenu réel est livré en
S24.4 ; cette page expose un squelette navigable + tooltips pour
permettre l'enregistrement dans la navigation et l'audit YAML help dès
S19/S20.
"""
from __future__ import annotations

import streamlit as st

from ihm.components.help_tooltip import _help
from ihm.components.kpi_card import kpi_card
from ihm.components.section_header import section_header
from ihm.theme.badges import status_badge

PAGE = "compliance_audit"


def render() -> None:
    section_header(
        st,
        title="Compliance & Audit",
        subtitle="Chaîne HMAC, DR drill, CVE, couverture & mutation",
        help_key="overview",
        page=PAGE,
        icon="📜",
    )

    st.caption(
        status_badge("Vue squelette — contenu détaillé livré S24.4", "info")
    )

    tabs = st.tabs(
        ["🔗 Chaîne HMAC", "🛟 DR drill", "🛡️ CVE", "🧪 Couverture & Mutation"]
    )

    with tabs[0]:
        st.markdown("**Chaîne audit HMAC** — vérifie l'intégrité bout-en-bout.")
        kpi_card(
            st, "Status chaîne", "✅ valide",
            help_key="hmac_chain_status", page=PAGE,
        )
        st.info("Le détail (offsets, rotation clés, dernier sceau) sera "
                "branché à `service/audit_chain.py` lors du Sprint S24.4.")

    with tabs[1]:
        st.markdown("**DR drill** — restauration mensuelle vérifiée en CI.")
        kpi_card(
            st, "Dernier drill", "OK (J-7)",
            help_key="dr_drill_last", page=PAGE,
        )

    with tabs[2]:
        st.markdown("**Vulnérabilités** — SBOM scan automatique.")
        kpi_card(
            st, "CVE critiques ouvertes", 0,
            help_key="cve_open", page=PAGE,
        )

    with tabs[3]:
        col1, col2 = st.columns(2)
        with col1:
            kpi_card(
                st, "Couverture branches (%)", 0,
                help_key="coverage_branches", page=PAGE,
            )
        with col2:
            kpi_card(
                st, "Score mutation (%)", 0,
                help_key="mutation_score", page=PAGE,
            )
        st.caption(
            "Sources : `artifacts/coverage/branches.json`, "
            "`artifacts/mutation_runs/<date>/score.json`."
        )

    st.divider()
    st.checkbox(
        "Activer l'export PDF (futur)",
        value=False,
        help=_help(PAGE, "export_pdf"),
        key="compliance_export_pdf",
    )

