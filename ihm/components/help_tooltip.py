"""Sprint S20 — Helper ``_help(page, key)`` pour les tooltips Streamlit.

Charge l'entrée correspondante depuis ``ihm/help/<page>.yaml`` (via
``ihm.services.help_loader.load_help``) puis formate un markdown court
adapté au paramètre ``help=`` des widgets Streamlit.

Si l'entrée est manquante, retourne ``""`` et logge un warning : la page
ne doit JAMAIS planter à cause d'un tooltip absent.
"""
from __future__ import annotations

import logging
from typing import Any

from ihm.services.help_loader import load_help

logger = logging.getLogger(__name__)


def _format_field(value: Any) -> str:
    if value is None:
        return "—"
    return str(value).strip()


def _help(page: str, key: str) -> str:
    """Retourne le markdown formaté à passer à ``st.<widget>(help=...)``."""
    entry = load_help(page).get(key)
    if entry is None:
        logger.debug("Tooltip manquant : help[%s][%s]", page, key)
        return ""
    title = _format_field(entry.get("title", key))
    description = _format_field(entry.get("description", ""))
    impact = _format_field(entry.get("impact", ""))
    example = _format_field(entry.get("example", ""))
    default = _format_field(entry.get("default", "—"))
    rng = _format_field(entry.get("range", "—"))
    doc_ref = _format_field(entry.get("doc_ref", ""))

    parts = [f"**{title}**", "", description]
    if impact and impact != "—":
        parts += ["", f"**Impact** : {impact}"]
    if example and example != "—":
        parts += ["", f"**Exemple** : {example}"]
    parts += ["", f"**Défaut** : `{default}` — **Plage** : `{rng}`"]
    if doc_ref and doc_ref != "—":
        # Fix anomalie (e) — un tooltip Streamlit ne peut PAS suivre un
        # chemin relatif (page blanche). Sans ``IHM_DOC_BASE_URL``, on
        # se contente d'afficher la référence sous forme de code.
        import os as _os

        base = _os.environ.get("IHM_DOC_BASE_URL", "").strip().rstrip("/")
        if base:
            parts += ["", f"[📖 Doc]({base}/{doc_ref})"]
        else:
            parts += ["", f"📖 Doc : `{doc_ref}`"]
    return "\n".join(parts)


def help_or_default(page: str, key: str, default: str) -> str:
    """Variante : retourne ``default`` si la clé est absente."""
    rendered = _help(page, key)
    return rendered if rendered else default

