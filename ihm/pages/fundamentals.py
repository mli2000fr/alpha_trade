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

import os
import subprocess
import sys
import time
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
                options=["eodhd", "finnhub", "yahoo_finance", "fmp"],
                index=0,
                key="fund_populate_provider",
            )
        with col_pop3:
            populate_overwrite = st.checkbox(
                "Écraser les données existantes (force re-fetch de tous les symboles)",
                value=False,
                key="fund_populate_overwrite",
            )

        # ── Commande CLI équivalente ──
        st.caption("Commande équivalente (copiable pour exécution hors IHM) :")
        # Mapping IHM -> CLI --symbol-source
        _MODE_TO_SYMBOL_SOURCE = {
            "stock-bars-daily": "stock-bars-daily",
            "tradable-universe": "tradable-universe",
            "ticket-recherche": "ticket-recherche",
            "Symboles sans fondamentaux": "missing-fundamentals",
        }
        symbol_source = next(
            (v for k, v in _MODE_TO_SYMBOL_SOURCE.items() if k in universe_mode),
            "missing-fundamentals",
        )
        cli_cmd = [
            sys.executable,
            "-m",
            "dataIntegrityEngine.update_sector",
            "--provider",
            populate_provider,
            "--symbol-source",
            symbol_source,
        ]
        if populate_overwrite or symbol_source in ("stock-bars-daily", "tradable-universe"):
            cli_cmd.append("--overwrite-existing")
        # Les dates sont toujours affichées si renseignées (filtre additionnel valable pour toute source)
        cli_cmd.extend([
            "--start-date", fund_start_date.isoformat(),
            "--end-date", fund_end_date.isoformat(),
        ])
        cli_cmd_display = subprocess.list2cmdline(cli_cmd)
        st.code(cli_cmd_display, language="powershell")

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

        # ── État du fetch en cours ──
        fetch_status = st.session_state.get("fund_populate_status", "")
        if fetch_status == "running":
            _render_live_fundamentals_fetch()
            # Auto-refresh pendant l'exécution
            time.sleep(0.8)
            st.rerun()
        elif fetch_status in ("completed", "failed", "stopped"):
            _render_fundamentals_fetch_results()
            _clear_fundamentals_fetch_state()
        else:
            # ── Bouton de lancement ──
            if st.button("🚀 Lancer le fetch des fondamentaux", type="primary", key="fund_populate_btn"):
                _start_fundamentals_fetch_subprocess(
                    universe_mode=universe_mode,
                    populate_provider=populate_provider,
                    populate_overwrite=populate_overwrite,
                    fund_start_date=fund_start_date,
                    fund_end_date=fund_end_date,
                )
                st.rerun()

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


# ── Helpers pour le fetch en subprocess (avec arrêt et logs live) ──

_FETCH_STATE_KEYS = [
    "fund_populate_status",
    "fund_populate_process",
    "fund_populate_cmd",
    "fund_populate_logs",
    "fund_populate_result",
    "fund_populate_provider",
    "fund_populate_tempfile",
    "fund_populate_output_queue",
    "fund_populate_reader_done",
    "fund_populate_num_symbols",
]


def _start_fundamentals_fetch_subprocess(
    *,
    universe_mode: str,
    populate_provider: str,
    populate_overwrite: bool,
    fund_start_date: _date,
    fund_end_date: _date,
) -> None:
    """Résout les symboles, construit la commande CLI et lance le subprocess."""
    import os
    import queue as _queue_mod

    from database.assets import (
        list_eligible_stock_symbols,
        get_symbols_missing_fundamentals,
        get_symbols_with_stale_market_cap,
    )
    from common.tradable_universe import load_tradable_universe_for_period
    from database.connection import get_sqlalchemy_engine

    # ── Résolution des symboles ──
    if populate_overwrite:
        from modelFactory.db_registry import load_stock_bars_daily_symbols
        symbols = load_stock_bars_daily_symbols(get_sqlalchemy_engine())
    elif "sans fondamentaux" in universe_mode:
        symbols = get_symbols_missing_fundamentals()
        if not symbols:
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
    else:
        symbols = []

    if not symbols:
        st.warning("Aucun symbole à rafraîchir — tous les symboles ont déjà des fondamentaux récents.")
        return

    st.session_state["fund_populate_num_symbols"] = len(symbols)

    # ── Construction de la commande ──
    _MODE_TO_SYMBOL_SOURCE = {
        "stock-bars-daily": "stock-bars-daily",
        "tradable-universe": "tradable-universe",
        "ticket-recherche": "ticket-recherche",
        "Symboles sans fondamentaux": "missing-fundamentals",
    }
    symbol_source = next(
        (v for k, v in _MODE_TO_SYMBOL_SOURCE.items() if k in universe_mode),
        "missing-fundamentals",
    )
    cmd = [
        sys.executable,
        "-m",
        "dataIntegrityEngine.update_sector",
        "--provider",
        populate_provider,
        "--symbol-source",
        symbol_source,
        "--log-every",
        "10",
    ]
    if populate_overwrite or symbol_source in ("stock-bars-daily", "tradable-universe"):
        cmd.append("--overwrite-existing")
    # Toujours passer les dates (filtre additionnel valable pour toute source)
    cmd.extend([
        "--start-date", fund_start_date.isoformat(),
        "--end-date", fund_end_date.isoformat(),
    ])

    # Pas de fichier temporaire : tout passe par --symbol-source

    # ── Copie de l'environnement (FMP_TOKEN etc.) ──
    env = os.environ.copy()
    # Ajouter le répertoire projet au PYTHONPATH si nécessaire
    project_root = str(Path(__file__).resolve().parents[2])
    existing_pythonpath = env.get("PYTHONPATH", "")
    if existing_pythonpath:
        env["PYTHONPATH"] = f"{project_root}{os.pathsep}{existing_pythonpath}"
    else:
        env["PYTHONPATH"] = project_root

    # ── Lancement du subprocess ──
    process = subprocess.Popen(
        cmd,
        cwd=project_root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    # Queue pour la communication inter-thread
    output_queue: _queue_mod.Queue[tuple[str, str]] = _queue_mod.Queue()

    def _reader(stream, stream_name: str) -> None:
        try:
            for line in iter(stream.readline, ""):
                output_queue.put((stream_name, line))
        finally:
            stream.close()

    import threading
    t_stdout = threading.Thread(target=_reader, args=(process.stdout, "stdout"), daemon=True)
    t_stderr = threading.Thread(target=_reader, args=(process.stderr, "stderr"), daemon=True)
    t_stdout.start()
    t_stderr.start()

    # ── Stockage dans la session ──
    st.session_state["fund_populate_status"] = "running"
    st.session_state["fund_populate_process"] = process
    st.session_state["fund_populate_cmd"] = subprocess.list2cmdline(cmd)
    st.session_state["fund_populate_logs"] = []
    st.session_state["fund_populate_result"] = None
    st.session_state["fund_populate_provider"] = populate_provider
    st.session_state["fund_populate_tempfile"] = None
    st.session_state["fund_populate_output_queue"] = output_queue
    st.session_state["fund_populate_reader_done"] = False


def _drain_output_queue() -> None:
    """Lit les lignes disponibles dans la queue et les ajoute aux logs."""
    queue_obj = st.session_state.get("fund_populate_output_queue")
    if queue_obj is None:
        return
    logs = st.session_state.get("fund_populate_logs", [])
    while True:
        try:
            stream_name, line = queue_obj.get_nowait()
        except Exception:
            break
        prefix = "" if stream_name == "stdout" else "[STDERR] "
        logs.append(f"{prefix}{line.rstrip()}")
    st.session_state["fund_populate_logs"] = logs


def _render_live_fundamentals_fetch() -> None:
    """Affiche les logs en direct et le bouton d'arrêt pendant l'exécution."""
    process = st.session_state.get("fund_populate_process")
    if process is None:
        st.session_state["fund_populate_status"] = "failed"
        st.rerun()
        return

    # Vérifier si le process est toujours en cours
    returncode = process.poll()
    _drain_output_queue()

    if returncode is not None:
        # Process terminé
        _drain_output_queue()  # Dernière lecture
        if returncode == 0:
            st.session_state["fund_populate_status"] = "completed"
        elif returncode == -15 or returncode == -9:
            # SIGTERM / SIGKILL
            st.session_state["fund_populate_status"] = "stopped"
        else:
            st.session_state["fund_populate_status"] = "failed"
        # Stocker le returncode et les logs pour l'affichage
        st.session_state["fund_populate_result"] = {
            "returncode": returncode,
            "logs": st.session_state.get("fund_populate_logs", []),
        }
        st.rerun()
        return

    # ── Affichage live ──
    num_symbols = st.session_state.get("fund_populate_num_symbols", "?")
    st.info(f"🟨 Fetch en cours — **{num_symbols}** symboles à traiter")

    col_stop, col_info = st.columns([1, 3])
    with col_stop:
        if st.button("⏹️ Arrêter le fetch", key="fund_populate_stop_btn", type="secondary"):
            process.kill()
            _drain_output_queue()
            st.session_state["fund_populate_status"] = "stopped"
            st.session_state["fund_populate_result"] = {
                "returncode": -15,
                "logs": st.session_state.get("fund_populate_logs", []),
            }
            st.rerun()

    logs = st.session_state.get("fund_populate_logs", [])
    with st.expander("📋 Logs en direct", expanded=True):
        log_text = "\n".join(logs[-100:]) if logs else "En attente des premières lignes…"
        with st.container(height=400):
            st.code(log_text, language="text")


def _render_fundamentals_fetch_results() -> None:
    """Affiche le résultat final du fetch avec téléchargement des logs."""
    result = st.session_state.get("fund_populate_result", {})
    logs = result.get("logs", []) if isinstance(result, dict) else []
    returncode = result.get("returncode", -1) if isinstance(result, dict) else -1
    provider = st.session_state.get("fund_populate_provider", "inconnu")
    cmd_display = st.session_state.get("fund_populate_cmd", "")

    full_log = "\n".join(logs)

    if returncode == 0:
        # Essayer de parser le run summary JSON pour des stats précises
        stored = 0
        failed = 0
        updated = 0
        for line in logs:
            if "::alpha_trade_run_summary::" in line:
                try:
                    import json
                    json_start = line.index("::alpha_trade_run_summary::") + len("::alpha_trade_run_summary::")
                    summary = json.loads(line[json_start:])
                    stored = summary.get("stored", summary.get("updated", 0))
                    updated = summary.get("updated", 0)
                    failed = summary.get("failed", 0)
                except Exception:
                    pass
        if stored > 0 or updated > 0:
            st.success(f"✅ Fetch terminé — {stored or updated} mis à jour, {failed} échecs (source: {provider})")
        else:
            st.success(f"✅ Fetch terminé avec succès (source: {provider})")
    elif returncode == -15 or returncode == -9:
        st.warning(f"⏹️ Fetch arrêté par l'utilisateur (source: {provider})")
    else:
        st.error(f"❌ Fetch terminé avec erreur (code {returncode}, source: {provider})")

    if cmd_display:
        st.caption("Commande exécutée :")
        st.code(cmd_display, language="powershell")

    if full_log.strip():
        with st.expander("📋 Logs d'exécution", expanded=True):
            st.code(full_log[-20000:], language="text")
        st.download_button(
            label="📥 Télécharger les logs",
            data=full_log,
            file_name=f"fundamentals_fetch_{provider}_{_dt.now().strftime('%Y%m%d_%H%M%S')}.log",
            mime="text/plain",
            key="fund_download_logs",
        )

    # Clear caches
    _load_fundamentals_summary.clear()
    _load_coverage_stats.clear()
    _load_sector_distribution.clear()


def _clear_fundamentals_fetch_state() -> None:
    """Nettoie la session state et les fichiers temporaires après un fetch."""
    temp_file = st.session_state.get("fund_populate_tempfile")
    if temp_file and os.path.exists(temp_file):
        try:
            os.unlink(temp_file)
        except OSError:
            pass

    for key in _FETCH_STATE_KEYS:
        if key in st.session_state:
            del st.session_state[key]


if __name__ == "__main__":
    run_page_if_standalone(__name__, render)
