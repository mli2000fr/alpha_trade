"""ihm/pages/settings.py — Paramètres / Santé système."""
from __future__ import annotations

import os
import sys

import streamlit as st

from ihm.components.db_controls import render_db_connection_form
from ihm.components.status_badges import env_badge
from ihm.services.db import db_available, get_db_status


def _check_import(name: str) -> str:
    try:
        __import__(name)
        return f"🟢 `{name}` — OK"
    except ImportError:
        return f"🔴 `{name}` — **MANQUANT**"


def render() -> None:
    st.header("⚙️ Paramètres / Santé")

    # --- Variables d'environnement ---
    st.subheader("🔑 Variables d'environnement")
    for var in ("LOGIN_DB", "PASSWORD_DB", "ALPACA_API_KEY", "ALPACA_SECRET_KEY", "FINNHUB_API_KEY"):
        st.markdown(env_badge(var, os.getenv(var)))

    # --- DB ---
    st.subheader("🗄️ Connexion DB")
    render_db_connection_form("settings_db_connection_form", show_host_fields=True)

    status = get_db_status()
    if db_available():
        st.success("🟢 Connexion MySQL OK")
    else:
        st.error("🔴 Connexion MySQL échouée. Vérifiez LOGIN_DB, PASSWORD_DB et que MySQL est démarré.")
    st.caption(
        f"Source active : `{status.get('source')}` — cible : `{status.get('host')}/{status.get('name')}`"
    )
    if status.get("last_query_error"):
        st.warning(str(status.get("last_query_error")))

    # --- Système ---
    st.subheader("🖥️ Système")
    st.text(f"Python : {sys.version}")
    st.text(f"Répertoire : {os.getcwd()}")

    # --- Dépendances ---
    st.subheader("📦 Dépendances critiques")
    for pkg in ("streamlit", "sqlalchemy", "pandas", "pymysql", "numpy", "torch", "transformers"):
        st.markdown(_check_import(pkg))

    # --- Rappel ---
    st.subheader("🚀 Commande de lancement")
    st.code("python -m streamlit run ihm/app.py", language="powershell")

