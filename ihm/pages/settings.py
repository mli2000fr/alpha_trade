"""ihm/pages/settings.py — Paramètres / Santé système."""
from __future__ import annotations

import os
import sys

import streamlit as st

from ihm.components.status_badges import env_badge
from ihm.services.db import db_available


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
    if db_available():
        st.success("🟢 Connexion MySQL OK")
    else:
        st.error("🔴 Connexion MySQL échouée. Vérifiez LOGIN_DB, PASSWORD_DB et que MySQL est démarré.")

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

