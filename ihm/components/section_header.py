"""Sprint S20 — Composant ``section_header`` standardisé."""
from __future__ import annotations

from ihm.components.help_tooltip import _help


def section_header(
    st_module,
    title: str,
    subtitle: str | None = None,
    help_key: str | None = None,
    page: str | None = None,
    icon: str | None = None,
) -> None:
    """Affiche un titre de section avec icône, sous-titre et tooltip.

    Si ``help_key`` et ``page`` sont fournis, le tooltip est construit
    via :func:`ihm.components.help_tooltip._help`.
    """
    label = f"{icon} {title}" if icon else title
    if help_key and page:
        tooltip = _help(page, help_key)
        st_module.markdown(f"### {label}", help=tooltip if tooltip else None)
    else:
        st_module.markdown(f"### {label}")
    if subtitle:
        st_module.caption(subtitle)

