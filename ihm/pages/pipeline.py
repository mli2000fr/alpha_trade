"""ihm/pages/pipeline.py — Vue séquentielle du pipeline métier."""
from __future__ import annotations

import streamlit as st

PIPELINE_STEPS = [
    {
        "num": "1", "name": "Import Alpaca Bar",
        "desc": "Ingestion des barres OHLCV journalières depuis Alpaca Market Data.",
        "tables": "stock_bars",
        "cli": "python -m dataIntegrityEngine.import_alpaca_bar",
        "deps": "—",
    },
    {
        "num": "1a", "name": "Corporate Actions Sync",
        "desc": "Ingestion des dividendes/splits depuis Alpaca (référentiel). Se fait AVANT le sanitizer.",
        "tables": "corporate_actions_events",
        "cli": "python -m corporate_actions sync --skip-existing",
        "deps": "import_alpaca_bar",
    },
    {
        "num": "2", "name": "Data Sanitizer Daily",
        "desc": "Nettoyage, alignement calendrier, détection d'anomalies sur les barres brutes.",
        "tables": "stock_bars_daily, cleaning_audit_log",
        "cli": "python -m dataIntegrityEngine.data_sanitizer_daily",
        "deps": "import_alpaca_bar, corporate_actions sync",
    },
    {
        "num": "3", "name": "Stock Screener",
        "desc": "Scores de base : liquidité 30j, force relative 6m vs SPY, range 10 ans.",
        "tables": "stock_scores",
        "cli": "python -m dataIntegrityEngine.stock_screener",
        "deps": "data_sanitizer_daily",
    },
    {
        "num": "4", "name": "Alpha Scanner",
        "desc": "Scoring avancé Minervini/VCP + neutralisation sectorielle + sélection Top N.",
        "tables": "stock_scores (update)",
        "cli": "python -m selector.alpha_scanner",
        "deps": "stock_screener",
    },
    {
        "num": "5", "name": "Sentiment Pipeline",
        "desc": "Ingestion news → scoring FinBERT → features ticker/secteur journalières.",
        "tables": "ticker_daily_sentiment_features, sector_daily_sentiment_features",
        "cli": "python -m event_sentiment",
        "deps": "alpha_scanner",
    },
    {
        "num": "6", "name": "Signal Aggregator",
        "desc": "Fusion quant (75%) + sentiment ticker (15%) + macro sectoriel (10%) → final_score_sentiment.",
        "tables": "stock_scores (update final_score_sentiment)",
        "cli": "python -m event_sentiment.signal_aggregator",
        "deps": "sentiment_pipeline",
    },
    {
        "num": "7", "name": "Risk Management",
        "desc": "Sizing ATR/Kelly, contraintes portefeuille, circuit breaker → portefeuille cible.",
        "tables": "risk_decisions, portfolio_targets",
        "cli": "python -m risk_management.run_risk --account-equity 100000",
        "deps": "signal_aggregator",
    },
    {
        "num": "8", "name": "Execution",
        "desc": "Soumission ordres Alpaca (market/limit), bracket synthétique TP+TS, réconciliation, TCA.",
        "tables": "execution_runs, execution_orders, execution_fills, execution_events, broker_positions_snapshots",
        "cli": "python run_execution.py simulate  # ou paper / live",
        "deps": "run_risk",
    },
    {
        "num": "8a", "name": "Corporate Actions Apply",
        "desc": "Application des dividendes/splits sur les positions existantes. Se fait APRÈS l'exécution.",
        "tables": "corporate_actions_applications, portfolio_cash_ledger",
        "cli": "python -m corporate_actions apply",
        "deps": "run_execution",
    },
]


def render() -> None:
    st.header("🔄 Pipeline Quotidien")
    st.caption("Ordre d'exécution strict — chaque étape dépend de la précédente.")

    for step in PIPELINE_STEPS:
        with st.expander(f"**{step['num']}. {step['name']}**", expanded=False):
            st.markdown(f"**Description** : {step['desc']}")
            st.markdown(f"**Tables impactées** : `{step['tables']}`")
            st.markdown(f"**Dépendances** : {step['deps']}")
            st.code(step["cli"], language="powershell")

