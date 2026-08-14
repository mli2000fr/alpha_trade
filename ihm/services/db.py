"""ihm/services/db.py — Helper connexion DB pour l'IHM Streamlit."""
from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from typing import Any
from urllib.parse import quote_plus

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from database.connection import (
    DEFAULT_DB_HOST,
    DEFAULT_DB_NAME,
    DEFAULT_DB_PASSWORD_ENV,
    DEFAULT_DB_USER_ENV,
)

LOGGER = logging.getLogger(__name__)

SESSION_DB_HOST_KEY = "ihm_db_host"
SESSION_DB_NAME_KEY = "ihm_db_name"
SESSION_DB_USER_KEY = "ihm_db_user"
SESSION_DB_PASSWORD_KEY = "ihm_db_password"
SESSION_LAST_DB_ERROR_KEY = "ihm_last_db_error"
SESSION_LAST_QUERY_ERROR_KEY = "ihm_last_query_error"


def _set_state(key: str, value: str | None) -> None:
    if value is None:
        st.session_state.pop(key, None)
    else:
        st.session_state[key] = value


def _set_last_db_error(message: str | None) -> None:
    _set_state(SESSION_LAST_DB_ERROR_KEY, message)


def _set_last_query_error(message: str | None) -> None:
    _set_state(SESSION_LAST_QUERY_ERROR_KEY, message)


def get_last_db_error() -> str | None:
    return st.session_state.get(SESSION_LAST_DB_ERROR_KEY)


def get_last_query_error() -> str | None:
    return st.session_state.get(SESSION_LAST_QUERY_ERROR_KEY)


def get_runtime_db_config() -> dict[str, str | None]:
    """Retourne la config DB active pour l'IHM (saisie Streamlit > env > défauts)."""
    session_host = st.session_state.get(SESSION_DB_HOST_KEY)
    session_name = st.session_state.get(SESSION_DB_NAME_KEY)
    session_user = st.session_state.get(SESSION_DB_USER_KEY)
    session_password = st.session_state.get(SESSION_DB_PASSWORD_KEY)

    host = session_host or os.getenv("DB_HOST") or DEFAULT_DB_HOST
    name = session_name or os.getenv("DB_NAME") or DEFAULT_DB_NAME
    user = session_user or os.getenv(DEFAULT_DB_USER_ENV)
    password = session_password or os.getenv(DEFAULT_DB_PASSWORD_ENV)

    has_manual_override = any(
        key in st.session_state
        for key in (SESSION_DB_HOST_KEY, SESSION_DB_NAME_KEY, SESSION_DB_USER_KEY, SESSION_DB_PASSWORD_KEY)
    )

    return {
        "host": host,
        "name": name,
        "user": user,
        "password": password,
        "source": "saisie IHM" if has_manual_override else "variables d'environnement",
    }


def set_runtime_db_config(*, host: str, name: str, user: str, password: str) -> None:
    """Mémorise une configuration DB saisie depuis l'IHM."""
    _set_state(SESSION_DB_HOST_KEY, host.strip() or DEFAULT_DB_HOST)
    _set_state(SESSION_DB_NAME_KEY, name.strip() or DEFAULT_DB_NAME)
    _set_state(SESSION_DB_USER_KEY, user.strip())
    _set_state(SESSION_DB_PASSWORD_KEY, password)
    reset_db_caches(clear_errors=True)


def clear_runtime_db_config() -> None:
    """Supprime les overrides de saisie et repasse sur les variables d'environnement."""
    for key in (SESSION_DB_HOST_KEY, SESSION_DB_NAME_KEY, SESSION_DB_USER_KEY, SESSION_DB_PASSWORD_KEY):
        st.session_state.pop(key, None)
    reset_db_caches(clear_errors=True)


def reset_db_caches(*, clear_errors: bool = False) -> None:
    """Réinitialise les caches DB/requêtes pour forcer une reconnexion propre."""
    _get_cached_engine.clear()
    st.cache_data.clear()
    _set_last_query_error(None)
    if clear_errors:
        _set_last_db_error(None)


def _build_database_url(*, host: str, name: str, user: str, password: str) -> str:
    safe_user = quote_plus(user)
    safe_password = quote_plus(password)
    return f"mysql+pymysql://{safe_user}:{safe_password}@{host}/{name}?charset=utf8mb4"


def _engine_options() -> dict[str, object]:
    return {
        "echo": False,
        "pool_pre_ping": True,
        "pool_recycle": 3600,
        "pool_size": 2,
        "max_overflow": 3,
    }


def _format_db_connection_error(
    exc: Exception,
    *,
    host: str,
    name: str,
    user: str,
    source: str,
) -> str:
    message = str(exc)
    lowered = message.lower()
    target = f"`{host}/{name}`"
    if "access denied" in lowered or "(1045" in lowered:
        return (
            f"Accès MySQL refusé pour l'utilisateur `{user}` sur {target} via `{source}`. "
            "Vérifiez les identifiants `LOGIN_DB` / `PASSWORD_DB` actifs dans l'IHM ou les variables d'environnement, "
            "puis les droits SQL de cet utilisateur."
        )
    if "unknown database" in lowered or "(1049" in lowered:
        return (
            f"Base MySQL introuvable sur {target} via `{source}`. "
            "Vérifiez `DB_NAME` et la base effectivement ciblée."
        )
    if any(token in lowered for token in ("can't connect", "connection refused", "timed out", "timeout expired", "2003")):
        return (
            f"Serveur MySQL inaccessible sur `{host}` pour la base `{name}` via `{source}`. "
            "Vérifiez `DB_HOST`, le port MySQL et que le service est démarré."
        )
    return f"Connexion MySQL impossible sur {target} avec la source `{source}` : {message}"


def validate_db_connection_config(
    config: Mapping[str, str | None],
    *,
    source: str | None = None,
) -> str | None:
    """Retourne un message d'erreur si la config DB est invalide ou inaccessible."""
    host = str(config.get("host") or DEFAULT_DB_HOST)
    name = str(config.get("name") or DEFAULT_DB_NAME)
    user = str(config.get("user") or "").strip()
    password = str(config.get("password") or "")
    source_label = source or str(config.get("source") or "variables d'environnement")

    if not user or not password:
        return (
            "Identifiants MySQL manquants. Renseignez `LOGIN_DB` / `PASSWORD_DB` "
            "ou utilisez le formulaire de connexion dans l'IHM."
        )

    engine: Engine | None = None
    try:
        engine = create_engine(_build_database_url(host=host, name=name, user=user, password=password), **_engine_options())
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return None
    except Exception as exc:
        return _format_db_connection_error(exc, host=host, name=name, user=user, source=source_label)
    finally:
        if engine is not None:
            engine.dispose()


@st.cache_resource(show_spinner=False)
def _get_cached_engine(db_url: str) -> Engine:
    return create_engine(db_url, **_engine_options())


def get_engine() -> Engine | None:
    """Retourne le SQLAlchemy engine, ou None si indisponible."""
    config = get_runtime_db_config()
    user = str(config.get("user") or "")
    password = str(config.get("password") or "")
    host = str(config.get("host") or DEFAULT_DB_HOST)
    name = str(config.get("name") or DEFAULT_DB_NAME)

    validation_error = validate_db_connection_config(config, source=str(config.get("source") or "variables d'environnement"))
    if validation_error:
        _set_last_db_error(validation_error)
        return None

    try:
        engine = _get_cached_engine(_build_database_url(host=host, name=name, user=user, password=password))
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        _set_last_db_error(None)
        return engine
    except Exception as exc:
        message = _format_db_connection_error(
            exc,
            host=host,
            name=name,
            user=user,
            source=str(config.get("source") or "variables d'environnement"),
        )
        LOGGER.warning("DB indisponible : %s", exc)
        _set_last_db_error(message)
        return None


def db_available() -> bool:
    return get_engine() is not None


def get_db_status() -> dict[str, str | bool | None]:
    config = get_runtime_db_config()
    connected = db_available()
    return {
        **config,
        "connected": connected,
        "last_db_error": get_last_db_error(),
        "last_query_error": get_last_query_error(),
    }


def _format_query_error(exc: Exception, query: str) -> str:
    message = str(exc)
    lowered = message.lower()
    if any(token in lowered for token in ("doesn't exist", "unknown table", "no such table")):
        return f"Table SQL absente ou non migrée pour cette page. Requête concernée : `{query[:80].strip()}...`"
    if any(token in lowered for token in ("unknown column", "no such column")):
        return f"Schéma SQL inattendu pour cette page. Vérifiez les migrations. Requête concernée : `{query[:80].strip()}...`"
    return f"Erreur SQL : {message}"


def safe_query(query: str, params: dict[str, Any] | None = None) -> pd.DataFrame:
    """Exécute une requête SQL et retourne un DataFrame. Retourne vide si erreur."""
    engine = get_engine()
    if engine is None:
        _set_last_query_error(get_last_db_error())
        return pd.DataFrame()
    try:
        with engine.connect() as conn:
            df = pd.read_sql_query(text(query), conn, params=params or {})
        _set_last_query_error(None)
        return df
    except Exception as exc:
        message = _format_query_error(exc, query)
        LOGGER.warning("Requete echouee : %s — %s", query[:80], exc)
        _set_last_query_error(message)
        return pd.DataFrame()


def safe_scalar(query: str, params: dict[str, Any] | None = None) -> Any:
    """Exécute une requête qui retourne un scalaire. Retourne None si erreur."""
    engine = get_engine()
    if engine is None:
        _set_last_query_error(get_last_db_error())
        return None
    try:
        with engine.connect() as conn:
            result = conn.execute(text(query), params or {})
            row = result.fetchone()
        _set_last_query_error(None)
        return row[0] if row else None
    except Exception as exc:
        message = _format_query_error(exc, query)
        LOGGER.warning("Requete scalaire echouee : %s — %s", query[:80], exc)
        _set_last_query_error(message)
        return None


def safe_execute(query: str, params: dict[str, Any] | None = None) -> bool:
    """Exécute une requête d'écriture (UPDATE/INSERT/DELETE) avec commit.

    Retourne ``True`` si la requête a réussi, ``False`` sinon (erreur
    exposée via ``get_last_query_error``).
    """
    engine = get_engine()
    if engine is None:
        _set_last_query_error(get_last_db_error())
        return False
    try:
        with engine.begin() as conn:
            conn.execute(text(query), params or {})
        _set_last_query_error(None)
        return True
    except Exception as exc:
        message = _format_query_error(exc, query)
        LOGGER.warning("Ecriture echouee : %s — %s", query[:80], exc)
        _set_last_query_error(message)
        return False

