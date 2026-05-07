"""Tableau réutilisable avec sélection de ligne et actions par symbole.

Encapsule ``st.dataframe(..., on_select="rerun", selection_mode="single-row")``
pour offrir une expérience uniforme :

* sélection d'une ligne du tableau ;
* affichage d'une barre d'actions sous le tableau quand une ligne est
  sélectionnée :

  - bouton « 📈 Voir l'historique des bars » → ouvre
    :func:`ihm.components.symbol_bars_dialog.show_symbol_bars_dialog` ;
  - boutons custom additionnels (paramètre ``extra_actions``) — typiquement
    « Vendre tout » sur la page Comptes Alpaca.

Si la colonne symbole n'est pas présente dans le DataFrame, le helper
dégrade gracieusement vers :func:`ihm.components.tables.show_dataframe`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import pandas as pd
import streamlit as st

from ihm.components.symbol_bars_dialog import show_symbol_bars_dialog

ActionCallback = Callable[[str, "pd.Series[Any]"], None]


@dataclass(frozen=True)
class ActionSpec:
    """Spécification d'un bouton d'action exposé sous une ligne sélectionnée.

    Attributes
    ----------
    label:
        Libellé du bouton (peut contenir un emoji).
    callback:
        Fonction ``(symbol, row) -> None`` exécutée au clic.
    key:
        Identifiant unique (sera préfixé par la ``key`` du tableau).
    confirm:
        Si ``True``, demande confirmation : 1er clic arme l'état, 2e clic
        exécute. Permet d'éviter les actions destructives accidentelles.
    confirm_label:
        Libellé du bouton de confirmation (utilisé si ``confirm=True``).
    """

    label: str
    callback: ActionCallback
    key: str
    confirm: bool = False
    confirm_label: str | None = None


def _selected_row_index(table_key: str) -> int | None:
    state = st.session_state.get(table_key)
    if state is None:
        return None
    selection = getattr(state, "selection", None) or (state.get("selection") if isinstance(state, dict) else None)
    if not selection:
        return None
    rows = getattr(selection, "rows", None) or (selection.get("rows") if isinstance(selection, dict) else None)
    if not rows:
        return None
    try:
        return int(rows[0])
    except (TypeError, ValueError, IndexError):
        return None


def _resolve_symbol(df: pd.DataFrame, row_index: int, symbol_col: str) -> str | None:
    if row_index < 0 or row_index >= len(df):
        return None
    if symbol_col not in df.columns:
        return None
    raw = df.iloc[row_index].get(symbol_col)
    if raw is None:
        return None
    symbol = str(raw).strip()
    return symbol or None


def _render_action_bar(
    *,
    df: pd.DataFrame,
    row_index: int,
    symbol: str,
    table_key: str,
    extra_actions: list[ActionSpec],
    bars_lookback_days: int,
) -> None:
    row = df.iloc[row_index]
    columns = st.columns(1 + len(extra_actions))
    bars_button_key = f"{table_key}__bars_btn_{symbol}"
    if columns[0].button(f"📈 Voir l'historique des bars ({symbol})", key=bars_button_key, use_container_width=True):
        show_symbol_bars_dialog(symbol, lookback_days=bars_lookback_days)

    for idx, spec in enumerate(extra_actions, start=1):
        column = columns[idx]
        confirm_state_key = f"{table_key}__confirm_{spec.key}_{symbol}"
        if spec.confirm and st.session_state.get(confirm_state_key):
            confirm_label = spec.confirm_label or f"✅ Confirmer {spec.label}"
            if column.button(confirm_label, key=f"{table_key}__{spec.key}_confirm_btn_{symbol}", use_container_width=True, type="primary"):
                st.session_state.pop(confirm_state_key, None)
                try:
                    spec.callback(symbol, row)
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Action `{spec.label}` échouée pour `{symbol}` : {exc}")
            if column.button("Annuler", key=f"{table_key}__{spec.key}_cancel_btn_{symbol}", use_container_width=True):
                st.session_state.pop(confirm_state_key, None)
                st.rerun()
        else:
            if column.button(spec.label, key=f"{table_key}__{spec.key}_btn_{symbol}", use_container_width=True):
                if spec.confirm:
                    st.session_state[confirm_state_key] = True
                    st.rerun()
                else:
                    try:
                        spec.callback(symbol, row)
                    except Exception as exc:  # noqa: BLE001
                        st.error(f"Action `{spec.label}` échouée pour `{symbol}` : {exc}")


def render_symbol_table(
    df: pd.DataFrame,
    *,
    key: str,
    symbol_col: str = "symbol",
    title: str | None = None,
    height: int = 400,
    extra_actions: list[ActionSpec] | None = None,
    bars_lookback_days: int = 365,
    hide_index: bool = True,
) -> str | None:
    """Affiche un DataFrame cliquable, ouvrant une popin de bars par symbole.

    Si ``symbol_col`` est absente du DataFrame (ou si le DataFrame est vide),
    on dégrade vers :func:`show_dataframe` (compat ascendante).

    Returns
    -------
    Le symbole sélectionné dans le tableau (ou ``None`` si aucune sélection).
    """
    if title:
        st.subheader(title)
    if df is None or df.empty:
        st.info("Aucune donnée disponible.")
        return None
    if symbol_col not in df.columns:
        # Pas de colonne symbole : on rend la table standard sans actions.
        st.dataframe(df, width="stretch", height=height, hide_index=hide_index)
        return None

    extra_actions = list(extra_actions or [])

    # Affichage du tableau avec sélection mono-ligne.
    st.dataframe(
        df,
        width="stretch",
        height=height,
        hide_index=hide_index,
        on_select="rerun",
        selection_mode="single-row",
        key=key,
    )

    row_index = _selected_row_index(key)
    if row_index is None:
        st.caption("ℹ️ Sélectionne une ligne pour afficher l'historique des bars.")
        return None

    symbol = _resolve_symbol(df, row_index, symbol_col)
    if not symbol:
        st.caption("ℹ️ La ligne sélectionnée n'a pas de symbole exploitable.")
        return None

    _render_action_bar(
        df=df,
        row_index=row_index,
        symbol=symbol,
        table_key=key,
        extra_actions=extra_actions,
        bars_lookback_days=bars_lookback_days,
    )
    return symbol


__all__ = ["ActionSpec", "render_symbol_table"]


