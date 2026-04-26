"""Encart homogène de documentation opérateur pour le watcher."""
from __future__ import annotations

import streamlit as st

from ihm.services.watcher_runtime import build_watcher_doc_reference


def build_watcher_documentation_panel_payload() -> dict[str, str]:
    doc_reference = build_watcher_doc_reference()
    return {
        "title": "📘 Documentation opérateur watcher",
        "quick_summary_markdown": (
            "- **Quand le lancer ?** Juste après `Execution` si des ordres / fills / protections broker-side ont été créés.\n"
            "- **Quand n'est-il pas nécessaire ?** S'il n'y a rien à surveiller après `Execution`, ou si un watcher Windows sain tourne déjà.\n"
            "- **Où regarder les logs ?** Dans `Supervision Ops` pour les runs IHM, et dans les sources Windows importées pour `Task Scheduler` / `NSSM`."
        ),
        "without_watcher_markdown": (
            "| Cas | Sans watcher ? | Commentaire |\n"
            "|---|---|---|\n"
            "| Achat exécuté | **Oui** | Si `Execution` a bien soumis l'ordre d'entrée. |\n"
            "| Stop initial exécuté | **Oui** | S'il a bien été posé broker-side par `Execution`. |\n"
            "| Trailing dynamique automatique | **Non** | C'est précisément le rôle du watcher post-exécution. |"
        ),
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
        st.markdown(payload["quick_summary_markdown"])
        st.markdown("**Sans watcher : ce qui marche / ne marche pas**")
        st.markdown(payload["without_watcher_markdown"])
        st.markdown(payload["link_markdown"])
        st.caption(payload["fallback_caption"])

