"""Sprint S20.6 — Résolution des liens ``doc_ref`` des tooltips/glossaire.

Un ``doc_ref`` (ex. ``doc/execution.md#bracket``) est une **référence
relative au repo**, pas une URL HTTP servie par Streamlit. Cliquer
dessus produit donc une page blanche (404 silencieux).

Ce service expose deux helpers :

* :func:`resolve_doc_ref` — retourne :
    * le contenu markdown du fichier référencé s'il existe localement,
    * sinon une URL externe construite via la variable d'environnement
      ``IHM_DOC_BASE_URL`` (typiquement
      ``https://github.com/<org>/alpha_trade/blob/main``).
* :func:`render_doc_ref_inline` — rendu Streamlit prêt à l'emploi
  (à utiliser depuis :mod:`ihm.pages.glossary` et tout autre endroit
  qui veut afficher un lien doc cliquable + viewer inline).

L'objectif est d'éviter à l'opérateur de naviguer hors de l'IHM :
le markdown s'affiche dans un ``st.expander`` au-dessous du terme.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# Racine du projet (3 niveaux au-dessus de ce fichier : ihm/services/ → ihm/ → racine)
PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True, slots=True)
class DocRefResolution:
    """Résultat de la résolution d'une référence doc."""

    raw: str
    """``doc_ref`` initial, ex. ``doc/execution.md#bracket``."""

    file_path: Path | None
    """Chemin absolu vers le fichier markdown local si trouvé, sinon ``None``."""

    anchor: str | None
    """Ancre éventuelle (partie après ``#``) — informative."""

    external_url: str | None
    """URL externe (GitHub) construite si ``IHM_DOC_BASE_URL`` est défini."""

    @property
    def has_local_content(self) -> bool:
        return self.file_path is not None and self.file_path.is_file()

    def read_markdown(self) -> str:
        """Lit le markdown local. Vide si fichier absent."""
        if not self.has_local_content:
            return ""
        assert self.file_path is not None
        try:
            return self.file_path.read_text(encoding="utf-8")
        except OSError:
            return ""


def resolve_doc_ref(doc_ref: str | None) -> DocRefResolution | None:
    """Résout un ``doc_ref`` (chemin relatif au projet) en chemin absolu.

    Retourne ``None`` si ``doc_ref`` est vide ou égal à ``"—"``.
    """
    if not doc_ref or doc_ref.strip() in {"", "—"}:
        return None

    raw = doc_ref.strip()
    path_part, _, anchor = raw.partition("#")

    # Sécurité : on refuse toute tentative d'évasion via "../.." ⇒
    # on résout le chemin et on vérifie qu'il reste sous PROJECT_ROOT.
    candidate = (PROJECT_ROOT / path_part).resolve()
    file_path: Path | None = None
    try:
        candidate.relative_to(PROJECT_ROOT)
    except ValueError:
        file_path = None
    else:
        file_path = candidate if candidate.is_file() else None

    base = os.environ.get("IHM_DOC_BASE_URL", "").strip().rstrip("/")
    external = f"{base}/{raw}" if base else None

    return DocRefResolution(
        raw=raw,
        file_path=file_path,
        anchor=(anchor or None),
        external_url=external,
    )


def render_doc_ref_inline(st_module, doc_ref: str | None, *, key_suffix: str = "") -> None:
    """Affiche un bloc compact « 📖 Documentation » sous un terme.

    Comportement :
      * si le fichier markdown est trouvé en local ⇒ ``st.expander`` qui
        rend le contenu (offline, pas de page blanche) ;
      * sinon, si ``IHM_DOC_BASE_URL`` est défini ⇒ lien externe ;
      * sinon ⇒ ``st.caption`` neutre indiquant la référence (sans
        tenter d'ouvrir une URL relative qui produirait une 404).
    """
    resolution = resolve_doc_ref(doc_ref)
    if resolution is None:
        return

    if resolution.has_local_content:
        with st_module.expander(
            f"📖 Documentation : `{resolution.raw}`", expanded=False
        ):
            st_module.markdown(resolution.read_markdown())
            if resolution.anchor:
                st_module.caption(f"↳ Section : `#{resolution.anchor}`")
        return

    if resolution.external_url:
        st_module.caption(
            f"📎 [Documentation : {resolution.raw}]({resolution.external_url})"
        )
        return

    # Fallback : on n'émet PAS de lien Markdown (qui produirait une page
    # blanche en cliquant sur un chemin relatif non servi par Streamlit).
    st_module.caption(f"📎 Référence documentaire : `{resolution.raw}`")

