"""Composants partagés pour la sélection des artefacts screener dans l'IHM."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from ihm.services.screener_artifact_history import (
    SHARED_SELECTED_SCREENER_ARTIFACTS_DIR_KEY,
    build_global_screener_artifact_history,
    build_screener_artifact_history_rows,
    format_screener_artifact_history_label,
    resolve_selected_screener_artifacts_dir,
)
from ihm.services.screener_preferences import (
    load_persisted_selected_screener_artifacts_dir,
    save_persisted_selected_screener_artifacts_dir,
)


def build_screener_artifact_history_dataframe(history_entries: list[dict[str, object]]) -> pd.DataFrame:
    return pd.DataFrame(build_screener_artifact_history_rows(history_entries))


def render_shared_screener_artifact_selector(
    *,
    selectbox_key: str,
    title: str,
    caption: str,
    empty_message: str,
    history_title: str,
) -> tuple[str, dict[str, object]]:
    st.subheader(title)
    st.caption(caption)

    history_entries = build_global_screener_artifact_history()
    if not history_entries:
        st.info(empty_message)
        return "", {}

    session_selected_dir = str(st.session_state.get(SHARED_SELECTED_SCREENER_ARTIFACTS_DIR_KEY, "") or "").strip()
    persisted_selected_dir = load_persisted_selected_screener_artifacts_dir()
    preferred_dir = session_selected_dir or persisted_selected_dir
    selected_dir, entry_map = resolve_selected_screener_artifacts_dir(history_entries, preferred_dir)
    if not entry_map:
        st.info(empty_message)
        return "", {}

    restored_from_persistence = not session_selected_dir and bool(persisted_selected_dir)
    options = list(entry_map.keys())
    st.session_state[SHARED_SELECTED_SCREENER_ARTIFACTS_DIR_KEY] = selected_dir
    if st.session_state.get(selectbox_key) != selected_dir:
        st.session_state[selectbox_key] = selected_dir

    selected_dir = st.selectbox(
        "Répertoire d'artefacts screener",
        options=options,
        format_func=lambda value: format_screener_artifact_history_label(entry_map[value]),
        index=options.index(selected_dir),
        key=selectbox_key,
    )
    st.session_state[SHARED_SELECTED_SCREENER_ARTIFACTS_DIR_KEY] = selected_dir
    if persisted_selected_dir != selected_dir:
        save_persisted_selected_screener_artifacts_dir(selected_dir)

    selected_entry = entry_map[selected_dir]
    if restored_from_persistence:
        st.caption("Préférence restaurée depuis la dernière session IHM.")
    st.caption(
        "Sélection partagée avec `Overview` et `Screening` · "
        f"Couverture : {selected_entry.get('coverage_label', 'Période non renseignée')} · "
        f"MAJ : {selected_entry.get('updated_at_label', 'inconnue')}"
    )

    history_df = build_screener_artifact_history_dataframe(history_entries)
    if not history_df.empty:
        with st.expander(history_title, expanded=False):
            st.dataframe(history_df, use_container_width=True, hide_index=True)

    return selected_dir, selected_entry

