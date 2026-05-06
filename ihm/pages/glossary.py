"""Sprint S20.4 — Page Glossaire (recherchable).

Charge depuis ``ihm/help/glossary.yaml`` et affiche les entrées dans des
``st.expander``. Filtre fuzzy via ``st.text_input``.
"""
from __future__ import annotations

import streamlit as st

from ihm.components.help_tooltip import _help
from ihm.components.section_header import section_header
from ihm.services.help_loader import load_help

PAGE = "glossary"


def _matches(query: str, term: str, entry: dict) -> bool:
    if not query:
        return True
    q = query.lower()
    if q in term.lower():
        return True
    for field in ("title", "description"):
        value = entry.get(field, "")
        if isinstance(value, str) and q in value.lower():
            return True
    return False


def render() -> None:
    section_header(
        st,
        title="Glossaire",
        subtitle="Termes techniques (sizing, OCO, parity, drift, …)",
        help_key="overview",
        page=PAGE,
        icon="📚",
    )

    query = st.text_input(
        "🔎 Rechercher",
        value="",
        help=_help(PAGE, "search"),
        key="glossary_search",
    )

    entries = load_help(PAGE)
    # Exclure l'entrée 'overview' / 'search' qui sont des metas.
    glossary_entries = {
        k: v for k, v in entries.items() if k not in {"overview", "search"}
    }

    visible = [(k, v) for k, v in glossary_entries.items() if _matches(query, k, v)]
    visible.sort(key=lambda kv: kv[0].lower())

    if not visible:
        st.info("Aucun terme ne correspond à la recherche.")
        return

    st.caption(f"{len(visible)} terme(s) affiché(s).")
    for key, entry in visible:
        title = entry.get("title", key)
        with st.expander(f"📖 {title}"):
            st.markdown(entry.get("description", "—"))
            doc_ref = entry.get("doc_ref")
            if doc_ref and doc_ref != "—":
                st.caption(f"📎 [{doc_ref}]({doc_ref})")

