"""Sprint S19.4 — Page IHM Tax Compliance (wash sales, lots, exports).

Câblée à ``tax/wash_sale.py`` via ``ihm/services/tax_data.py``. Aucune
logique métier n'est introduite ici — la page se contente d'orchestrer
les filtres, le calcul wash sale et le rendu.
"""
from __future__ import annotations

import io
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from ihm.components.help_tooltip import _help
from ihm.components.kpi_card import kpi_card
from ihm.components.section_header import section_header
from ihm.services import tax_data
from ihm.theme.badges import status_badge

PAGE = "tax_compliance"


def render() -> None:
    section_header(
        st,
        title="Tax Compliance",
        subtitle="Wash sales (IRS §1091), lots ajustés, export 1099-B",
        help_key="overview",
        page=PAGE,
        icon="💰",
    )

    st.caption(
        status_badge("Mode démo : lots de référence", "info")
        + " — câblage DB ``fills`` planifié S21.4"
    )

    # --- Filtres -----------------------------------------------------------
    today = date.today()
    col1, col2, col3 = st.columns(3)
    with col1:
        date_from = st.date_input(
            "Période — début",
            value=today - timedelta(days=90),
            help=_help(PAGE, "date_from"),
            key="tax_date_from",
        )
    with col2:
        date_to = st.date_input(
            "Période — fin",
            value=today,
            help=_help(PAGE, "date_to"),
            key="tax_date_to",
        )
    with col3:
        symbol_filter = st.text_input(
            "Symbole (optionnel)",
            value="",
            help=_help(PAGE, "symbol_filter"),
            key="tax_symbol_filter",
        ).strip().upper() or None

    account = st.selectbox(
        "Compte",
        options=[st.session_state.get("selected_account_id", "default")],
        help=_help(PAGE, "account"),
        key="tax_account",
    )

    # --- Données -----------------------------------------------------------
    lots = tax_data.load_demo_lots()
    lots = tax_data.filter_lots(
        lots, symbol=symbol_filter, date_from=date_from, date_to=date_to
    )
    report = tax_data.compute_report(lots)

    # --- KPI ---------------------------------------------------------------
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        kpi_card(st, "Lots", len(lots), help_key="kpi_lots", page=PAGE)
    with col_b:
        kpi_card(
            st,
            "Wash sales détectées",
            len(report.adjustments),
            help_key="kpi_wash_count",
            page=PAGE,
        )
    with col_c:
        kpi_card(
            st,
            "Perte non déductible ($)",
            f"{report.total_disallowed_loss:,.2f}",
            help_key="kpi_disallowed",
            page=PAGE,
        )

    # --- Table lots --------------------------------------------------------
    st.subheader("Lots")
    rows = tax_data.lots_to_table(lots, report)
    if not rows:
        st.info(f"Aucun lot pour le compte « {account} » sur la période choisie.")
        return
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # --- Export CSV -------------------------------------------------------
    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    st.download_button(
        "📥 Exporter CSV (1099-B équivalent)",
        data=buffer.getvalue(),
        file_name=f"tax_lots_{date_from}_{date_to}.csv",
        mime="text/csv",
        help=_help(PAGE, "export_csv"),
        key="tax_export_csv",
    )

    # --- Détail ajustements ----------------------------------------------
    if report.adjustments:
        st.subheader("Ajustements wash sale")
        adj_df = pd.DataFrame(
            [
                {
                    "sale_lot_id": a.sale_lot_id,
                    "replacement_lot_id": a.replacement_lot_id,
                    "symbol": a.symbol,
                    "disallowed_loss": a.disallowed_loss,
                    "sale_date": a.sale_date.isoformat(),
                    "replacement_date": a.replacement_date.isoformat(),
                }
                for a in report.adjustments
            ]
        )
        st.dataframe(adj_df, use_container_width=True, hide_index=True)
    else:
        st.success("Aucune wash sale détectée sur la période.")

