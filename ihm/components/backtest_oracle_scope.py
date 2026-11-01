"""Oracle candidate scope for the standard (non-Winner) replay."""
from __future__ import annotations

import streamlit as st


ORACLE_SCOPES = {
    "top20pct": ("TOP 20 %", 0.20, None),
    "top10pct": ("TOP 10 %", 0.10, None),
    "top10": ("TOP 10 titres", 0.20, 10),
    "top20": ("TOP 20 titres", 0.20, 20),
    "top50": ("TOP 50 titres", 0.20, 50),
}


def render_oracle_scope(rank_mode: str) -> tuple[float, int | None]:
    key = "bt_run_oracle_scope"
    # Apply the new default once, including already-open Streamlit sessions.
    # Later manual choices must survive reruns.
    default_version_key = "bt_run_oracle_scope_default_version"
    if st.session_state.get(default_version_key) != 2:
        st.session_state[key] = "top20"
        st.session_state[default_version_key] = 2
    if st.session_state.get(key) not in ORACLE_SCOPES:
        st.session_state[key] = "top20"
    selected = st.selectbox(
        "Sélection Oracle par séance",
        options=list(ORACLE_SCOPES),
        format_func=lambda value: ORACLE_SCOPES[value][0],
        key=key,
        disabled=rank_mode not in ("ml", "extreme_gate", "extreme_gate_directional"),
        help="S’applique à Extreme Gate et aux campagnes Oracle seules détectées automatiquement "
             "en mode standard. TOP 10 % / 20 % désigne une fraction de l’univers scoré ; "
             "TOP 10 / 20 / 50 désigne un nombre fixe de premiers titres Oracle. "
             "Les filtres ATR, Per-Symbol et les contrôles de risque restent applicables. "
             "Un titre écarté n’est pas remplacé par le rang suivant.",
    )
    _, pct, top_n = ORACLE_SCOPES[selected]
    return pct, top_n
