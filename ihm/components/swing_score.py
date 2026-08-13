"""ihm/components/swing_score.py — Bloc « Swing Score » de la page d'accueil.

Deux sources de symboles possibles :
- 📄 fichier uploadé (symboles séparés par `,`) ;
- 🗄️ un univers sélectionné dans la liste déroulante (identique à celle du bloc
  « T1. ML Train (hors pipeline quotidien) » de la page Pipeline).

Sortie : fichier texte avec les top N symboles séparés par des virgules
(même format que le fichier d'entrée).
"""
from __future__ import annotations

import logging

import pandas as pd
import streamlit as st

from ihm.services.swing_score import (
    LARGE_UNIVERSE_WARNING_THRESHOLD,
    UNIVERSE_SYMBOL_SOURCE_LABELS,
    UNIVERSE_SYMBOL_SOURCE_OPTIONS,
    compute_swing_scores,
    parse_symbols,
    resolve_universe_symbols,
)

LOGGER = logging.getLogger(__name__)

_SESSION_RESULT_KEY = "swing_score_last_result"
_SOURCE_RADIO_KEY = "swing_score_source_radio"
_UPLOADER_KEY = "swing_score_file_uploader"
_UNIVERSE_SELECT_KEY = "swing_score_universe_select"
_TOP_N_KEY = "swing_score_top_n"
_RUN_KEY = "swing_score_run_button"

_SOURCE_FILE = "Fichier uploadé"
_SOURCE_UNIVERSE = "Univers de symboles"

_FORMULA_CAPTION = (
    "25% ATR% + 20% Dollar Volume + 20% Relative Volume "
    "+ 15% Momentum + 10% Beta + 10% Market-cap fit"
)


def _read_uploaded_symbols(uploaded) -> list[str]:
    try:
        text_content = uploaded.getvalue().decode("utf-8", errors="replace")
    except Exception as exc:  # pragma: no cover - fichier illisible
        st.error(f"Lecture du fichier impossible : {exc}")
        return []
    symbols = parse_symbols(text_content)
    if not symbols:
        st.warning("Aucun symbole valide trouvé dans le fichier.")
    return symbols


@st.cache_data(ttl=300, show_spinner=False)
def _cached_resolve_universe(symbol_source: str) -> list[str]:
    """Résolution de l'univers mise en cache 5 min (au moment du calcul)."""
    return resolve_universe_symbols(symbol_source)


def _build_output_text(result: pd.DataFrame, top_n: int) -> str:
    """Liste des top N symboles séparés par des virgules (même format que l'entrée)."""
    return ",".join(str(symbol) for symbol in result["symbol"].head(top_n))


def _render_result(result: pd.DataFrame, top_n: int, diagnostics: dict, source_symbols_count: int) -> None:
    top_frame = result.head(top_n)
    st.success(
        f"✅ {source_symbols_count} symboles au départ · "
        f"{diagnostics.get('scored', 0)} scorés · "
        f"Top {min(top_n, len(result))} retournés"
    )
    if diagnostics.get("missing"):
        st.caption("Symboles sans données suffisantes : " + ", ".join(diagnostics.get("missing", [])))

    st.dataframe(
        top_frame,
        width="stretch",
        height=min(420, 35 * len(top_frame) + 38),
    )

    output_text = _build_output_text(result, top_n)
    st.download_button(
        label=f"⬇️ Télécharger le Top {top_n} (symboles séparés par `,`)",
        data=output_text.encode("utf-8"),
        file_name=f"swing_score_top_{top_n}.txt",
        mime="text/plain",
        key="swing_score_download",
    )


def render_swing_score_block() -> None:
    with st.container(border=True):
        st.subheader("🎯 Swing Score — Top symboles swing")
        st.caption(_FORMULA_CAPTION)

        source_mode = st.radio(
            "Source des symboles",
            options=[f"📄 {_SOURCE_FILE}", f"🗄️ {_SOURCE_UNIVERSE}"],
            horizontal=True,
            key=_SOURCE_RADIO_KEY,
        )

        uploaded = None
        selected_source = ""
        if source_mode.endswith(_SOURCE_UNIVERSE):
            selected_source = str(
                st.selectbox(
                    "Univers de symboles",
                    options=UNIVERSE_SYMBOL_SOURCE_OPTIONS,
                    index=0,
                    key=_UNIVERSE_SELECT_KEY,
                    format_func=lambda value: UNIVERSE_SYMBOL_SOURCE_LABELS.get(str(value), str(value)),
                    help=(
                        "Même liste que le bloc « T1. ML Train (hors pipeline quotidien) » de la page Pipeline. "
                        "`tradable-universe` = dernier snapshot PIT canonique publié ; "
                        "union historique = tous les symboles tradables sur toute l'histoire."
                    ),
                )
            )
        else:
            uploaded = st.file_uploader(
                "Fichier de symboles (séparés par `,`)",
                type=["txt", "csv"],
                key=_UPLOADER_KEY,
                help="Ex. config/ticket_mid_cap_400.txt — un symbole par ligne ou liste séparée par des virgules.",
            )

        top_n = st.number_input(
            "Top N à retourner",
            min_value=1,
            max_value=20000,
            value=100,
            step=100,
            key=_TOP_N_KEY,
        )

        run_disabled = source_mode.endswith(_SOURCE_FILE) and uploaded is None
        run_clicked = st.button(
            "⚡ Calculer le Swing Score",
            key=_RUN_KEY,
            type="primary",
            disabled=run_disabled,
        )

        if run_clicked:
            if source_mode.endswith(_SOURCE_UNIVERSE):
                try:
                    symbols = _cached_resolve_universe(selected_source)
                except Exception as exc:  # pragma: no cover - jamais bloquant
                    LOGGER.exception("Swing Score — résolution univers")
                    st.error(f"Impossible de résoudre l'univers : {exc}")
                    return
                if not symbols:
                    st.error("Aucun symbole dans l'univers sélectionné.")
                    return
                if len(symbols) > LARGE_UNIVERSE_WARNING_THRESHOLD:
                    st.warning(
                        f"Univers large ({len(symbols)} symboles) : le calcul peut prendre quelques instants."
                    )
            else:
                symbols = _read_uploaded_symbols(uploaded)
                if not symbols:
                    return

            try:
                with st.spinner(f"Calcul du Swing Score sur {len(symbols)} symboles…"):
                    result, diagnostics = compute_swing_scores(symbols)
            except Exception as exc:  # pragma: no cover - jamais bloquant
                LOGGER.exception("Swing Score — erreur inattendue")
                st.error(f"Erreur pendant le calcul : {exc}")
                return
            if result.empty:
                st.error(
                    "Aucune donnée OHLCV exploitable en base pour ces symboles "
                    f"({diagnostics.get('requested', 0)} demandés)."
                )
                return
            st.session_state[_SESSION_RESULT_KEY] = {
                "result": result,
                "top_n": int(top_n),
                "diagnostics": diagnostics,
                "source_symbols_count": len(symbols),
            }

        cached = st.session_state.get(_SESSION_RESULT_KEY)
        if cached:
            _render_result(
                cached["result"],
                cached["top_n"],
                cached["diagnostics"],
                cached.get("source_symbols_count", len(cached["result"])),
            )
