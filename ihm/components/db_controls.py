"""ihm/components/db_controls.py — Contrôles de connexion DB pour l'IHM."""
from __future__ import annotations

import streamlit as st

from ihm.services.db import (
    clear_runtime_db_config,
    get_db_status,
    get_last_query_error,
    reset_db_caches,
    set_runtime_db_config,
)


def render_db_connection_form(form_key: str, *, show_host_fields: bool = True) -> None:
    """Affiche un formulaire de connexion DB réutilisable."""
    status = get_db_status()
    host = str(status.get("host") or "localhost")
    name = str(status.get("name") or "alpha_trade")
    user = str(status.get("user") or "")
    current_password = str(status.get("password") or "")
    source = str(status.get("source") or "inconnue")
    connected = bool(status.get("connected"))
    db_error = status.get("last_db_error")

    if connected:
        st.success(f"🟢 Connecté à `{name}` sur `{host}` via `{source}`.")
    else:
        st.info("Cette partie de l'IHM dépend de la base MySQL Alpha Trade.")
        if db_error:
            st.warning(str(db_error))

    with st.form(form_key, clear_on_submit=False):
        if show_host_fields:
            col1, col2 = st.columns(2)
            with col1:
                host_value = st.text_input("Hôte MySQL", value=host)
            with col2:
                name_value = st.text_input("Base de données", value=name)
        else:
            host_value = host
            name_value = name

        col3, col4 = st.columns(2)
        with col3:
            user_value = st.text_input("Login DB", value=user)
        with col4:
            password_value = st.text_input("Mot de passe DB", value="", type="password")
        st.caption("Laissez le mot de passe vide pour conserver la valeur déjà active si nécessaire.")

        action_col1, action_col2, action_col3 = st.columns(3)
        connect_clicked = action_col1.form_submit_button("Tester / connecter", width="stretch")
        env_clicked = action_col2.form_submit_button("Utiliser ENV", width="stretch")
        refresh_clicked = action_col3.form_submit_button("Rafraîchir", width="stretch")

    if connect_clicked:
        set_runtime_db_config(
            host=host_value,
            name=name_value,
            user=user_value,
            password=password_value or current_password,
        )
        st.rerun()

    if env_clicked:
        clear_runtime_db_config()
        st.rerun()

    if refresh_clicked:
        reset_db_caches(clear_errors=False)
        st.rerun()


def render_db_unavailable(page_label: str, *, form_key: str) -> None:
    """Affiche un message explicite si une page nécessite la DB."""
    st.warning(f"La page **{page_label}** nécessite une connexion à la base Alpha Trade.")
    render_db_connection_form(form_key=form_key)


def render_query_diagnostic(empty_message: str) -> bool:
    """Affiche soit le diagnostic SQL, soit un message de vide métier.

    Retourne True si un message a été affiché à la place d'un tableau.
    """
    query_error = get_last_query_error()
    if query_error:
        st.warning(query_error)
        return True
    st.info(empty_message)
    return True


