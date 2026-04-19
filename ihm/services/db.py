"""ihm/services/db.py — Helper connexion DB pour l'IHM Streamlit."""
from __future__ import annotations

import logging
from typing import Any

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

LOGGER = logging.getLogger(__name__)


@st.cache_resource(show_spinner=False)
def get_engine() -> Engine | None:
    """Retourne le SQLAlchemy engine, ou None si indisponible."""
    try:
        from database.connection import get_sqlalchemy_engine
        engine = get_sqlalchemy_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return engine
    except Exception as exc:
        LOGGER.warning("DB indisponible : %s", exc)
        return None


def db_available() -> bool:
    return get_engine() is not None


def safe_query(query: str, params: dict[str, Any] | None = None) -> pd.DataFrame:
    """Exécute une requête SQL et retourne un DataFrame. Retourne vide si erreur."""
    engine = get_engine()
    if engine is None:
        return pd.DataFrame()
    try:
        with engine.connect() as conn:
            return pd.read_sql_query(text(query), conn, params=params or {})
    except Exception as exc:
        LOGGER.warning("Requête échouée : %s — %s", query[:80], exc)
        return pd.DataFrame()


def safe_scalar(query: str, params: dict[str, Any] | None = None) -> Any:
    """Exécute une requête qui retourne un scalaire. Retourne None si erreur."""
    engine = get_engine()
    if engine is None:
        return None
    try:
        with engine.connect() as conn:
            result = conn.execute(text(query), params or {})
            row = result.fetchone()
            return row[0] if row else None
    except Exception:
        return None

