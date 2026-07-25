"""ihm/pages/fundamentals.py — Page Streamlit ``Fondamentaux``.

Affiche les données fondamentales des symboles :
- Dernières valeurs disponibles (PE, ROE, marges, croissance, etc.)
- Distribution des métriques par secteur
- État de la couverture (symboles avec/sans fondamentaux)
- Historique des mises à jour

Les données sont lues depuis ``stock_fundamentals_daily`` et
``stock_metadata``.
"""
from __future__ import annotations

from datetime import date as _date, datetime as _dt, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from ihm.pages import run_page_if_standalone

ARTIFACTS_DIR = Path(__file__).resolve().parents[2] / "artifacts"


# ── Data loading ──


@st.cache_data(ttl=300, show_spinner="Chargement des fondamentaux…")
def _load_fundamentals_summary() -> pd.DataFrame:
    """Load latest fundamental data per symbol from stock_fundamentals_daily."""
    try:
        from sqlalchemy import text as _sa_text
        from database.connection import get_sqlalchemy_engine

        engine = get_sqlalchemy_engine()
        query = _sa_text("""
            SELECT
                sfd.symbol,
                sfd.trade_date,
                sfd.fetched_at,
                sfd.pe_ratio,
                sfd.forward_pe,
                sfd.pb_ratio,
                sfd.ps_ratio,
                sfd.ev_to_ebitda,
                sfd.roe,
                sfd.roa,
                sfd.net_margin,
                sfd.operating_margin,
                sfd.gross_margin,
                sfd.eps_growth_yoy,
                sfd.revenue_growth_yoy,
                sfd.dividend_yield,
                sfd.market_cap,
                sfd.beta,
                sfd.eps,
                sfd.eps_estimate_current,
                sfd.eps_estimate_next,
                sfd.source,
                sm.provider_sector AS sector,
                sm.company_name
            FROM stock_fundamentals_daily sfd
            INNER JOIN (
                SELECT symbol, MAX(trade_date) AS max_date
                FROM stock_fundamentals_daily
                GROUP BY symbol
            ) latest ON sfd.symbol = latest.symbol AND sfd.trade_date = latest.max_date
            LEFT JOIN stock_metadata sm ON sfd.symbol = sm.symbol
            ORDER BY sfd.market_cap IS NULL ASC, sfd.market_cap DESC
        """)
        with engine.connect() as conn:
            df = pd.read_sql_query(query, conn)
        return df
    except Exception as exc:
        st.warning(f"Impossible de charger les fondamentaux : {exc}")
        return pd.DataFrame()


@st.cache_data(ttl=300, show_spinner="Chargement de la couverture…")
def _load_coverage_stats() -> dict[str, Any]:
    """Coverage statistics: how many symbols have fundamentals."""
    try:
        from sqlalchemy import text as _sa_text
        from database.connection import get_sqlalchemy_engine

        engine = get_sqlalchemy_engine()
        query = _sa_text("""
            SELECT
                COUNT(DISTINCT sfd.symbol) AS symbols_with_fundamentals,
                COUNT(DISTINCT sm.symbol) AS total_eligible_symbols,
                MAX(sfd.fetched_at) AS last_fetch,
                COUNT(DISTINCT sfd.source) AS provider_count
            FROM stock_metadata sm
            LEFT JOIN stock_fundamentals_daily sfd ON sm.symbol = sfd.symbol
            WHERE sm.status = 'active'
              AND sm.tradable = 1
              AND sm.bars_available = 1
              AND sm.asset_class = 'us_equity'
        """)
        with engine.connect() as conn:
            row = conn.execute(query).mappings().first()
        if row is None:
            return {}
        return dict(row)
    except Exception:
        return {}


@st.cache_data(ttl=300, show_spinner="Chargement des distributions sectorielles…")
def _load_sector_distribution() -> pd.DataFrame:
    """Distribution of a key metric by sector."""
    try:
        from sqlalchemy import text as _sa_text
        from database.connection import get_sqlalchemy_engine

        engine = get_sqlalchemy_engine()
        query = _sa_text("""
            SELECT
                COALESCE(sm.provider_sector, 'N/A') AS sector,
                COUNT(*) AS symbol_count,
                AVG(sfd.pe_ratio) AS avg_pe,
                AVG(sfd.roe) AS avg_roe,
                AVG(sfd.net_margin) AS avg_net_margin,
                AVG(sfd.revenue_growth_yoy) AS avg_revenue_growth,
                SUM(sfd.market_cap) AS total_market_cap
            FROM stock_fundamentals_daily sfd
            INNER JOIN (
                SELECT symbol, MAX(trade_date) AS max_date
                FROM stock_fundamentals_daily
                GROUP BY symbol
            ) latest ON sfd.symbol = latest.symbol AND sfd.trade_date = latest.max_date
            LEFT JOIN stock_metadata sm ON sfd.symbol = sm.symbol
            GROUP BY COALESCE(sm.provider_sector, 'N/A')
            ORDER BY total_market_cap IS NULL ASC, total_market_cap DESC
        """)
        with engine.connect() as conn:
            df = pd.read_sql_query(query, conn)
        return df
    except Exception:
        return pd.DataFrame()


# ── Page ──


def fundamentals_page() -> None:
    st.set_page_config(page_title="Fondamentaux", page_icon="📊", layout="wide")
    st.title("📊 Fondamentaux")

    # ── Coverage stats ──
    coverage = _load_coverage_stats()
    if coverage:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric(
                "Symboles avec fondamentaux",
                coverage.get("symbols_with_fundamentals", 0),
            )
        with col2:
            total = coverage.get("total_eligible_symbols", 0)
            with_fund = coverage.get("symbols_with_fundamentals", 0)
            pct = f"{with_fund / total * 100:.1f}%" if total else "N/A"
            st.metric("Symboles éligibles", total, delta=pct)
        with col3:
            last_fetch = coverage.get("last_fetch")
            if last_fetch:
                delta_td = _dt.now() - pd.Timestamp(last_fetch).to_pydatetime()
                st.metric("Dernière mise à jour", str(last_fetch)[:19], delta=f"il y a {delta_td.days}j")
            else:
                st.metric("Dernière mise à jour", "Jamais")
        with col4:
            st.metric("Fournisseurs", coverage.get("provider_count", 0))

    st.divider()

    # ── Populate action ──
    with st.expander("🔧 Peupler / rafraîchir les fondamentaux", expanded=False):
        st.markdown(
            "Lance un fetch EODHD pour les symboles sélectionnés et stocke les résultats "
            "dans `stock_fundamentals_daily`. Coût : ~1 appel API par symbole."
        )

        # ── Univers de symboles ──
        st.markdown("##### Univers de symboles")
        universe_mode = st.selectbox(
            "Source des symboles",
            options=[
                "stock-bars-daily (symboles avec OHLCV chargé)",
                "tradable-universe (univers tradable PIT)",
                "ticket-recherche (watchlist manuelle)",
                "Symboles sans fondamentaux (provider_sector ou market_cap manquant)",
            ],
            index=0,  # défaut : stock-bars-daily
            key="fund_populate_mode",
            help="Détermine quels symboles seront fetchés. Tous les symboles de la source sont traités.",
        )

        # ── Période (utilisé par tradable-universe ; informatif pour les autres) ──
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            fund_start_date = st.date_input(
                "Date de début",
                value=_date(2015, 1, 1),
                key="fund_start_date",
                help="Pour tradable-universe : filtre les symboles tradables sur cette période. Pour les autres sources : informatif.",
            )
        with col_d2:
            fund_end_date = st.date_input(
                "Date de fin",
                value=_date.today(),
                key="fund_end_date",
                help="Pour tradable-universe : borne haute. Pour les autres sources : informatif.",
            )

        col_pop2, col_pop3 = st.columns(2)
        with col_pop2:
            populate_provider = st.selectbox(
                "Fournisseur",
                options=["eodhd", "finnhub", "yahoo_finance"],
                index=0,
                key="fund_populate_provider",
            )
        with col_pop3:
            populate_overwrite = st.checkbox(
                "Écraser les données existantes (force re-fetch de tous les symboles)",
                value=False,
                key="fund_populate_overwrite",
            )

        # ── Preview ──
        if st.button("🔍 Aperçu des symboles concernés", key="fund_populate_preview"):
            with st.spinner("Résolution de l'univers…"):
                try:
                    from database.assets import (
                        list_eligible_stock_symbols,
                        get_symbols_missing_fundamentals,
                        get_symbols_with_stale_market_cap,
                    )
                    from common.tradable_universe import load_tradable_universe_for_period
                    from database.connection import get_sqlalchemy_engine

                    if "sans fondamentaux" in universe_mode:
                        symbols = get_symbols_missing_fundamentals()
                    elif "stock-bars-daily" in universe_mode:
                        from modelFactory.db_registry import load_stock_bars_daily_symbols
                        symbols = load_stock_bars_daily_symbols(get_sqlalchemy_engine())
                    elif "tradable-universe" in universe_mode:
                        symbols = load_tradable_universe_for_period(
                            get_sqlalchemy_engine(),
                            fund_start_date,
                            fund_end_date,
                        )
                    elif "ticket-recherche" in universe_mode:
                        from modelFactory.db_registry import load_symbols_for_source
                        symbols = load_symbols_for_source(get_sqlalchemy_engine(), "ticket-recherche")


                    if not symbols:
                        st.success("✅ Aucun symbole à rafraîchir — tout est à jour.")
                    else:
                        st.info(f"**{len(symbols)} symboles** concernés : {', '.join(symbols[:20])}{'…' if len(symbols) > 20 else ''}")
                except Exception as exc:
                    st.error(f"Erreur lors de la résolution : {exc}")

        if st.button("🚀 Lancer le fetch des fondamentaux", type="primary", key="fund_populate_btn"):
            with st.spinner(f"Fetch des fondamentaux en cours ({populate_provider})…"):
                try:
                    from modelFactory.fundamental_features import fetch_and_store_fundamentals
                    from database.assets import (
                        list_eligible_stock_symbols,
                        get_symbols_missing_fundamentals,
                        get_symbols_with_stale_market_cap,
                    )
                    from common.tradable_universe import load_tradable_universe_for_period
                    from database.connection import get_sqlalchemy_engine

                    if populate_overwrite:
                        from modelFactory.db_registry import load_stock_bars_daily_symbols
                        symbols = load_stock_bars_daily_symbols(get_sqlalchemy_engine())
                    elif "sans fondamentaux" in universe_mode:
                        symbols = get_symbols_missing_fundamentals()
                        if not symbols:
                            # Fallback: refresh stale
                            symbols = get_symbols_with_stale_market_cap(max_age_days=30)
                        if not symbols:
                            symbols = list_eligible_stock_symbols()
                    elif "stock-bars-daily" in universe_mode:
                        from modelFactory.db_registry import load_stock_bars_daily_symbols
                        symbols = load_stock_bars_daily_symbols(get_sqlalchemy_engine())
                    elif "tradable-universe" in universe_mode:
                        symbols = load_tradable_universe_for_period(
                            get_sqlalchemy_engine(),
                            fund_start_date,
                            fund_end_date,
                        )
                    elif "ticket-recherche" in universe_mode:
                        from modelFactory.db_registry import load_symbols_for_source
                        symbols = load_symbols_for_source(get_sqlalchemy_engine(), "ticket-recherche")


                    if not symbols:
                        st.warning("Aucun symbole à rafraîchir — tous les symboles ont déjà des fondamentaux récents.")
                    else:
                        st.info(f"{len(symbols)} symboles à traiter : {', '.join(symbols[:10])}{'…' if len(symbols) > 10 else ''}")
                        result = fetch_and_store_fundamentals(
                            symbols,
                            provider=populate_provider,
                        )
                        if result["stored"] > 0:
                            st.success(f"✅ {result['stored']} fondamentaux stockés avec succès (source: {populate_provider})")
                        if result["failed"] > 0:
                            st.error(f"❌ {result['failed']} échecs")
                            if result.get("errors"):
                                st.code("\n".join(result["errors"][:10]))
                        # Clear caches so the page refreshes
                        _load_fundamentals_summary.clear()
                        _load_coverage_stats.clear()
                        _load_sector_distribution.clear()
                        st.rerun()
                except Exception as exc:
                    st.error(f"Erreur lors du fetch : {exc}")

    st.divider()

    # ── Tabs ──
    tab1, tab2, tab3 = st.tabs(["📋 Détail par symbole", "📊 Distribution sectorielle", "🔍 Recherche"])

    # ── Tab 1: Symbol detail ──
    with tab1:
        df = _load_fundamentals_summary()
        if df.empty:
            st.info(
                "Aucune donnée fondamentale disponible. "
                "Lancez `python -m dataIntegrityEngine.update_sector --fetch-fundamentals` "
                "pour peupler la table `stock_fundamentals_daily`."
            )
        else:
            st.write(f"**{len(df)} symboles** avec données fondamentales")

            # Filters
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                sectors = sorted(df["sector"].dropna().unique().tolist())
                selected_sectors = st.multiselect("Filtrer par secteur", sectors, default=[])
            with col_f2:
                min_cap = st.number_input(
                    "Market cap minimum (M$)",
                    min_value=0,
                    value=0,
                    step=100,
                )

            filtered = df.copy()
            if selected_sectors:
                filtered = filtered[filtered["sector"].isin(selected_sectors)]
            if min_cap > 0:
                filtered = filtered[filtered["market_cap"].fillna(0) >= min_cap * 1_000_000]

            st.write(f"**{len(filtered)} symboles** après filtres")

            display_cols = [
                "symbol", "company_name", "sector",
                "market_cap", "pe_ratio", "forward_pe", "pb_ratio",
                "roe", "roa", "net_margin", "revenue_growth_yoy",
                "dividend_yield", "beta", "source",
            ]
            display_cols = [c for c in display_cols if c in filtered.columns]

            # Format
            styled = filtered[display_cols].style.format({
                "market_cap": lambda x: f"${x / 1e9:,.1f}B" if pd.notna(x) and x > 0 else "N/A",
                "pe_ratio": lambda x: f"{x:.1f}" if pd.notna(x) and x > 0 else "N/A",
                "forward_pe": lambda x: f"{x:.1f}" if pd.notna(x) and x > 0 else "N/A",
                "pb_ratio": lambda x: f"{x:.2f}" if pd.notna(x) and x > 0 else "N/A",
                "roe": lambda x: f"{x * 100:.1f}%" if pd.notna(x) else "N/A",
                "roa": lambda x: f"{x * 100:.1f}%" if pd.notna(x) else "N/A",
                "net_margin": lambda x: f"{x * 100:.1f}%" if pd.notna(x) else "N/A",
                "revenue_growth_yoy": lambda x: f"{x * 100:.1f}%" if pd.notna(x) else "N/A",
                "dividend_yield": lambda x: f"{x * 100:.2f}%" if pd.notna(x) else "N/A",
                "beta": lambda x: f"{x:.2f}" if pd.notna(x) else "N/A",
            }, na_rep="N/A")

            st.dataframe(styled, use_container_width=True, height=600)

    # ── Tab 2: Sector distribution ──
    with tab2:
        sector_df = _load_sector_distribution()
        if sector_df.empty:
            st.info("Aucune donnée sectorielle disponible.")
        else:
            st.write(f"**{len(sector_df)} secteurs**")

            col_s1, col_s2 = st.columns(2)
            with col_s1:
                st.subheader("PE Ratio moyen par secteur")
                pe_data = sector_df[["sector", "avg_pe"]].dropna()
                pe_data = pe_data[pe_data["avg_pe"] > 0].sort_values("avg_pe")
                st.bar_chart(pe_data.set_index("sector")["avg_pe"], height=400)

            with col_s2:
                st.subheader("ROE moyen par secteur")
                roe_data = sector_df[["sector", "avg_roe"]].dropna().sort_values("avg_roe")
                st.bar_chart(roe_data.set_index("sector")["avg_roe"], height=400)

            col_s3, col_s4 = st.columns(2)
            with col_s3:
                st.subheader("Croissance revenu par secteur")
                growth_data = sector_df[["sector", "avg_revenue_growth"]].dropna().sort_values("avg_revenue_growth")
                st.bar_chart(growth_data.set_index("sector")["avg_revenue_growth"], height=400)

            with col_s4:
                st.subheader("Market Cap totale par secteur")
                cap_data = sector_df[["sector", "total_market_cap"]].dropna().sort_values("total_market_cap")
                st.bar_chart(cap_data.set_index("sector")["total_market_cap"], height=400)

    # ── Tab 3: Search ──
    with tab3:
        search_symbol = st.text_input("Rechercher un symbole", placeholder="Ex: AAPL, MSFT…").strip().upper()
        if search_symbol:
            try:
                from sqlalchemy import text as _sa_text
                from database.connection import get_sqlalchemy_engine

                engine = get_sqlalchemy_engine()
                query = _sa_text("""
                    SELECT *
                    FROM stock_fundamentals_daily
                    WHERE symbol = :symbol
                    ORDER BY trade_date DESC
                    LIMIT 10
                """)
                with engine.connect() as conn:
                    result_df = pd.read_sql_query(query, conn, params={"symbol": search_symbol})

                if result_df.empty:
                    st.warning(f"Aucune donnée fondamentale pour **{search_symbol}**")
                else:
                    st.write(f"**{len(result_df)} entrées** pour {search_symbol}")
                    # Format nicely
                    display = result_df.drop(columns=["id"], errors="ignore")
                    # Reorder: symbol, trade_date, fetched_at first
                    first_cols = ["symbol", "trade_date", "fetched_at", "source"]
                    other_cols = [c for c in display.columns if c not in first_cols]
                    display = display[first_cols + other_cols]

                    st.dataframe(display, use_container_width=True)

                    # Quick stats
                    latest = result_df.iloc[0] if not result_df.empty else None
                    if latest is not None:
                        st.subheader("Dernières valeurs")
                        cols = st.columns(4)
                        metrics = [
                            ("PE Ratio", latest.get("pe_ratio")),
                            ("ROE", f"{latest.get('roe', 0) * 100:.1f}%" if latest.get("roe") is not None else "N/A"),
                            ("Net Margin", f"{latest.get('net_margin', 0) * 100:.1f}%" if latest.get("net_margin") is not None else "N/A"),
                            ("Market Cap", f"${latest.get('market_cap', 0) / 1e9:,.1f}B" if latest.get("market_cap") else "N/A"),
                            ("Beta", latest.get("beta")),
                            ("Rev Growth", f"{latest.get('revenue_growth_yoy', 0) * 100:.1f}%" if latest.get("revenue_growth_yoy") is not None else "N/A"),
                            ("Div Yield", f"{latest.get('dividend_yield', 0) * 100:.2f}%" if latest.get("dividend_yield") is not None else "N/A"),
                            ("Source", latest.get("source")),
                        ]
                        for i, (label, value) in enumerate(metrics):
                            cols[i % 4].metric(label, str(value) if value is not None else "N/A")
            except Exception as exc:
                st.error(f"Erreur lors de la recherche : {exc}")


def render() -> None:
    """Point d'entrée standard pour la navigation IHM (appelé par ihm/app.py)."""
    fundamentals_page()


if __name__ == "__main__":
    run_page_if_standalone(__name__, render)
