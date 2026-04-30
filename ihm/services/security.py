"""Sécurité IHM (Phase 6.2 du refactor).

Trois protections optionnelles, toutes opt-in via variables d'environnement
pour ne pas casser l'usage local par défaut :

1. ``IHM_AUTH_TOKEN`` — token partagé exigé pour accéder à l'IHM (auth basique).
2. ``IHM_REQUIRE_LOCALHOST`` — exige que l'IHM tourne en ``--server.address``
   = ``localhost`` ou ``127.0.0.1`` (sinon ``warning`` rouge).
3. ``IHM_RUNS_RETENTION_DAYS`` — rotation des artefacts pipeline
   (cf. ``ihm.services.process_registry.rotate_pipeline_artifacts``).

Toutes les fonctions sont safe à appeler hors Streamlit (no-op).
"""
from __future__ import annotations

import os
import socket
from typing import Final

AUTH_TOKEN_ENV: Final[str] = "IHM_AUTH_TOKEN"
REQUIRE_LOCALHOST_ENV: Final[str] = "IHM_REQUIRE_LOCALHOST"
SESSION_AUTH_KEY: Final[str] = "_ihm_auth_validated"


def auth_token_required() -> bool:
    """True si la variable d'env ``IHM_AUTH_TOKEN`` est définie et non vide."""
    return bool((os.getenv(AUTH_TOKEN_ENV) or "").strip())


def _expected_token() -> str:
    return (os.getenv(AUTH_TOKEN_ENV) or "").strip()


def is_localhost_required() -> bool:
    raw = (os.getenv(REQUIRE_LOCALHOST_ENV) or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _resolve_server_address() -> str:
    """Best-effort lecture de l'adresse Streamlit configurée."""
    # Streamlit pose STREAMLIT_SERVER_ADDRESS quand `--server.address=...` est utilisé.
    raw = (os.getenv("STREAMLIT_SERVER_ADDRESS") or "").strip()
    return raw or ""


def is_listening_on_localhost_only() -> bool:
    """True si l'IHM est explicitement bindée sur loopback."""
    addr = _resolve_server_address().lower()
    if not addr:
        # Pas d'info → on considère "localhost" par défaut Streamlit (true).
        return True
    if addr in {"localhost", "127.0.0.1", "::1"}:
        return True
    try:
        # Résolution best-effort.
        ip = socket.gethostbyname(addr)
        return ip.startswith("127.")
    except OSError:
        return False


def render_auth_gate() -> bool:
    """Affiche un formulaire de login si ``IHM_AUTH_TOKEN`` est défini.

    Retourne ``True`` quand l'utilisateur est authentifié (ou auth désactivée).
    Sinon affiche le formulaire et retourne ``False`` — l'appelant doit alors
    interrompre le rendu de la page courante (``st.stop()``).
    """
    if not auth_token_required():
        return True
    try:
        import streamlit as st  # import différé : pas de dépendance hors IHM
    except ImportError:
        return True
    if st.session_state.get(SESSION_AUTH_KEY) is True:
        return True

    st.title("🔒 Alpha Trade — Authentification requise")
    st.caption("Variable d'environnement `IHM_AUTH_TOKEN` détectée. Saisissez le token partagé.")
    with st.form("ihm_auth_form"):
        token = st.text_input("Token", type="password")
        submitted = st.form_submit_button("Se connecter")
    if submitted:
        if token.strip() and token.strip() == _expected_token():
            st.session_state[SESSION_AUTH_KEY] = True
            st.rerun()
        else:
            st.error("Token invalide.")
    return False


def render_security_banner() -> None:
    """Bannière sidebar : alerte si l'IHM est exposée sans auth ou hors localhost."""
    try:
        import streamlit as st
    except ImportError:
        return
    addr = _resolve_server_address() or "localhost (défaut)"
    if is_localhost_required() and not is_listening_on_localhost_only():
        st.sidebar.error(
            f"⚠️ IHM exposée sur `{addr}` mais `IHM_REQUIRE_LOCALHOST=1`. "
            "Stoppez Streamlit et relancez avec `--server.address=localhost`."
        )
    elif not is_listening_on_localhost_only() and not auth_token_required():
        st.sidebar.warning(
            f"⚠️ IHM exposée sur `{addr}` sans `IHM_AUTH_TOKEN`. "
            "Activez l'auth ou bindez sur `localhost`."
        )


__all__ = [
    "AUTH_TOKEN_ENV",
    "REQUIRE_LOCALHOST_ENV",
    "auth_token_required",
    "is_localhost_required",
    "is_listening_on_localhost_only",
    "render_auth_gate",
    "render_security_banner",
]

