"""Sprint S24.4 — Page Compliance & Audit (version finale).

6 onglets : HMAC | DR | CVE | Cov+Mut | TLAPS+Fuzz | Sandbox.
Chaque KPI passe par ``kpi_card`` + tooltip YAML + badge couleur selon
seuils. Bouton de téléchargement du snapshot complet (JSON signable).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import streamlit as st

from ihm.components.help_tooltip import _help
from ihm.components.kpi_card import kpi_card
from ihm.components.section_header import section_header
from ihm.services import compliance_loader as loader
from ihm.theme.badges import status_badge

PAGE = "compliance_audit"


def _level_bool(v: bool | None) -> str:
    if v is True:
        return "ok"
    if v is False:
        return "danger"
    return "neutral"


def _level_count(v: int | None, *, danger_at: int = 1, warn_at: int = 0) -> str:
    if v is None:
        return "neutral"
    if v >= danger_at:
        return "danger"
    if v > warn_at:
        return "warning"
    return "ok"


def _level_pct(v: float | None, *, ok_at: float, warn_at: float) -> str:
    if v is None:
        return "neutral"
    if v >= ok_at:
        return "ok"
    if v >= warn_at:
        return "warning"
    return "danger"


def _fmt(v) -> str:
    return "—" if v is None else str(v)


def render() -> None:
    section_header(
        st,
        title="Compliance & Audit",
        subtitle="Chaîne HMAC, DR, CVE, couverture, mutation, TLAPS, fuzz, sandbox",
        help_key="overview",
        page=PAGE,
        icon="📜",
    )

    snapshot = loader.load_full_snapshot()
    hmac = snapshot["hmac_chain"]
    dr = snapshot["dr_drill"]
    cve = snapshot["cve"]
    cov = snapshot["coverage"]
    mut = snapshot["mutation"]
    tlaps = snapshot["tlaps"]
    fuzz = snapshot["fuzz"]
    sandbox = snapshot["sandbox"]

    tabs = st.tabs([
        "🔗 HMAC",
        "🛟 DR",
        "🛡️ CVE",
        "🧪 Cov + Mut",
        "✅ TLAPS + Fuzz",
        "🟢 Sandbox",
    ])

    # --- 1. HMAC ----------------------------------------------------------
    with tabs[0]:
        st.markdown("**Chaîne audit HMAC** — vérifie l'intégrité bout-en-bout.")
        st.caption(status_badge(
            f"Statut : {'OK' if hmac.get('ok') else ('KO' if hmac.get('ok') is False else '—')}",
            _level_bool(hmac.get("ok")),
        ))
        col1, col2 = st.columns(2)
        with col1:
            kpi_card(st, "Statut chaîne", _fmt(hmac.get("ok")),
                     help_key="hmac_chain_status", page=PAGE)
        with col2:
            kpi_card(st, "Anomalies détectées", _fmt(hmac.get("anomalies_count")),
                     help_key="hmac_chain_status", page=PAGE)
        if hmac.get("error"):
            st.warning(f"Source indisponible : {hmac['error']}")

    # --- 2. DR drill ------------------------------------------------------
    with tabs[1]:
        st.markdown("**DR drill** — restauration mensuelle vérifiée en CI.")
        st.caption(status_badge(
            f"Dernier drill : {_fmt(dr.get('last_date'))}",
            _level_bool(dr.get("ok")),
        ))
        col1, col2, col3 = st.columns(3)
        with col1:
            kpi_card(st, "Dernier drill", _fmt(dr.get("last_date")),
                     help_key="dr_drill_last", page=PAGE)
        with col2:
            kpi_card(st, "RTO (min)", _fmt(dr.get("rto_minutes")),
                     help_key="dr_drill_last", page=PAGE)
        with col3:
            kpi_card(st, "RPO (min)", _fmt(dr.get("rpo_minutes")),
                     help_key="dr_drill_last", page=PAGE)

    # --- 3. CVE -----------------------------------------------------------
    with tabs[2]:
        st.markdown("**Vulnérabilités** — SBOM scan automatique.")
        crit = cve.get("critical")
        st.caption(status_badge(
            f"CVE critiques : {_fmt(crit)}",
            _level_count(crit, danger_at=1, warn_at=0),
        ))
        col1, col2, col3 = st.columns(3)
        with col1:
            kpi_card(st, "CVE critiques", _fmt(crit),
                     help_key="cve_open", page=PAGE)
        with col2:
            kpi_card(st, "CVE high", _fmt(cve.get("high")),
                     help_key="cve_open", page=PAGE)
        with col3:
            kpi_card(st, "Dernier scan", _fmt(cve.get("scanned_at")),
                     help_key="cve_open", page=PAGE)

    # --- 4. Couverture + Mutation ----------------------------------------
    with tabs[3]:
        col1, col2 = st.columns(2)
        with col1:
            br = cov.get("branches_pct")
            kpi_card(st, "Couverture branches (%)", _fmt(br),
                     help_key="coverage_branches", page=PAGE)
            st.caption(status_badge(
                "≥ 90 % global cible",
                _level_pct(br, ok_at=90, warn_at=80),
            ))
        with col2:
            sc = mut.get("score_pct")
            kpi_card(st, "Score mutation (%)", _fmt(sc),
                     help_key="mutation_score", page=PAGE)
            st.caption(status_badge(
                f"≥ 70 % cible — date {_fmt(mut.get('date'))}",
                _level_pct(sc, ok_at=70, warn_at=50),
            ))

    # --- 5. TLAPS + Fuzz --------------------------------------------------
    with tabs[4]:
        col1, col2 = st.columns(2)
        with col1:
            n_ok = tlaps.get("n_ok")
            n_total = tlaps.get("n_specs")
            kpi_card(st, "TLAPS preuves OK",
                     f"{_fmt(n_ok)} / {_fmt(n_total)}",
                     help_key="tlaps_proofs", page=PAGE)
            st.caption(status_badge(
                f"tool={_fmt(tlaps.get('tool'))} date={_fmt(tlaps.get('date'))}",
                "ok" if (n_ok and n_total and n_ok == n_total) else "warning",
            ))
        with col2:
            n_div = fuzz.get("n_diverged")
            n_sc = fuzz.get("n_scenarios")
            kpi_card(st, "Fuzz divergences",
                     f"{_fmt(n_div)} / {_fmt(n_sc)}",
                     help_key="fuzz_diff_rate", page=PAGE)
            rate = fuzz.get("divergence_rate")
            st.caption(status_badge(
                f"taux {_fmt(rate)} — date {_fmt(fuzz.get('date'))}",
                _level_count(n_div, danger_at=1, warn_at=0),
            ))

    # --- 6. Sandbox -------------------------------------------------------
    with tabs[5]:
        streak = sandbox.get("streak_green")
        kpi_card(st, "Streak verte (j)", _fmt(streak),
                 help_key="sandbox_streak", page=PAGE)
        st.caption(status_badge(
            f"Échecs 30 j : {_fmt(sandbox.get('n_failure'))} — "
            f"dernier échec : {_fmt(sandbox.get('last_failure'))}",
            "ok" if (streak and streak >= 30) else (
                "warning" if (streak and streak >= 7) else "danger"
            ),
        ))
        st.caption("Détail : page **🟢 Sandbox health**.")

    st.divider()

    # --- Téléchargement snapshot ----------------------------------------
    st.markdown("### 📥 Snapshot auditeur")
    payload_str = json.dumps(
        {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            **snapshot,
        },
        indent=2,
    )
    st.download_button(
        "Télécharger compliance_snapshot.json",
        data=payload_str,
        file_name=f"compliance_snapshot_{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.json",
        mime="application/json",
        help=_help(PAGE, "snapshot_download"),
    )
    st.checkbox(
        "Activer l'export PDF (futur)",
        value=False,
        help=_help(PAGE, "export_pdf"),
        key="compliance_export_pdf",
    )

