"""Sprint S20 — Carte KPI standardisée."""
from __future__ import annotations

from typing import Any

from ihm.components.help_tooltip import _help


def kpi_card(
    st_module,
    label: str,
    value: Any,
    delta: Any | None = None,
    help_key: str | None = None,
    page: str | None = None,
    level: str = "neutral",
) -> None:
    """Affiche un ``st.metric`` avec tooltip help YAML.

    ``level`` (ok/warning/danger/neutral/info) prépare une intégration
    badge — pour l'instant utilisé comme caption discrète.
    """
    tooltip = _help(page, help_key) if (page and help_key) else None
    st_module.metric(
        label=label,
        value=value,
        delta=delta,
        help=tooltip if tooltip else None,
    )

