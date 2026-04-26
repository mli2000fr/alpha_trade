"""Encart homogène de documentation opérateur pour le watcher."""
from __future__ import annotations

import streamlit as st

from ihm.services.watcher_runtime import build_watcher_doc_reference


def build_watcher_documentation_panel_payload() -> dict[str, str]:
    doc_reference = build_watcher_doc_reference()
    return {
        "title": "📘 Documentation opérateur watcher",
        "link_markdown": f"**{doc_reference['label']}** : [{doc_reference['relative_path']}]({doc_reference['uri']})",
        "fallback_caption": (
            "Si le navigateur bloque l'ouverture directe du fichier local, ouvrez ce chemin depuis le workspace : "
            f"`{doc_reference['absolute_path']}`"
        ),
        **doc_reference,
    }


def render_watcher_documentation_panel(*, intro: str | None = None) -> None:
    payload = build_watcher_documentation_panel_payload()
    with st.container(border=True):
        st.markdown(f"**{payload['title']}**")
        if intro:
            st.caption(intro)
        st.markdown(payload["link_markdown"])
        st.caption(payload["fallback_caption"])

