"""Sprint S19.1 — Stubs d'API pour les extractions BLOCK 1 + BLOCK 3.

Le découpage S6.1 historique a extrait 7/9 blocs de
:func:`ihm.pages._execution_center._build_launch_options` en helpers
``_render_<block>_block``. Restent inline dans la façade actuelle :

* **BLOCK 1** — paramètres d'exécution (capital preset, dates, equity,
  mode, RTH, account/swing, fenêtre + trailing + debug)
  → contrat : :func:`render_execution_block(execution_defaults, selected_account_id) -> dict`
* **BLOCK 3** — Model Factory (preset, cible, walk-forward, hyperparams,
  grilles candidate)
  → contrat : :func:`render_model_factory_block() -> dict`

Ce module fournit des **stubs Streamlit-aware** qui :

1. Rendent les widgets avec ``help=`` (audit S20.5),
2. Retournent un dict comportant les clés contractuelles attendues par
   ``tests/test_ihm_pipeline_e2e.py``,
3. Sont **non-régressifs** : ils ne sont *pas* utilisés par
   :func:`_build_launch_options` (lequel conserve son code inline). La
   substitution effective sera réalisée lors d'une PR dédiée S19.1-bis.

Voir ``prompt/tod/29_ihm_refactor_delivery_report.md`` §4.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import streamlit as st

PAGE = "execution_center"


def render_execution_block(
    execution_defaults: Any | None = None,
    selected_account_id: str | None = None,
) -> dict[str, Any]:
    """Stub Sprint S19.1 — BLOCK 1 (Execution).

    Retourne un dict avec les clés contractuelles attendues par les
    tests AppTest. L'implémentation complète (≈ 320 lignes) sera
    extraite de ``_build_launch_options`` lors de la PR S19.1-bis.
    """
    if "pipeline_trade_date" not in st.session_state:
        st.session_state["pipeline_trade_date"] = date.today().isoformat()
    trade_date = st.text_input(
        "Trade date / as-of (YYYY-MM-DD)",
        key="pipeline_trade_date",
        help="Date logique partagée par toutes les étapes du pipeline.",
    )
    execution_mode = st.selectbox(
        "Mode Execution",
        options=["simulate", "paper", "live"],
        index=0,
        key="pipeline_execution_mode",
        help="`simulate` : aucun ordre. `paper` : sandbox broker. `live` : argent réel.",
    )
    execution_account_type = st.selectbox(
        "Execution — type de compte",
        options=["margin", "cash"],
        index=1,
        key="pipeline_execution_account_type",
        help="Défaut swing : `cash`.",
    )
    execution_swing_only = st.checkbox(
        "Execution — swing only",
        value=False,
        key="pipeline_execution_swing_only",
        help="Depuis FINRA 2026-06-04 : PDT supprimée, day trading libre. Défaut : False.",
    )
    execution_submission_window = st.selectbox(
        "Execution — fenêtre de soumission",
        options=["post_close", "pre_open", "both"],
        index=2,
        key="pipeline_execution_submission_window",
        help="`both` : essaie post-close puis pre-open.",
    )
    execution_trailing_trigger = st.selectbox(
        "Trigger d'activation du trailing",
        options=["multiple_r", "profit_pct"],
        index=0,
        key="pipeline_execution_trailing_trigger",
        help="`multiple_r` : armer après N×R atteint.",
    )
    execution_max_entry_gap_pct = float(
        st.number_input(
            "Gap d'entrée max (fraction)",
            min_value=0.0,
            max_value=1.0,
            value=float(st.session_state.get("pipeline_execution_max_entry_gap_pct", 0.0)),
            step=0.005,
            format="%.4f",
            key="pipeline_execution_max_entry_gap_pct",
            help="Ex. 0.03 = bloque une entrée si le prix courant s'éloigne trop du close précédent.",
        )
    )
    execution_debug = st.checkbox(
        "Execution — `--debug` (logs DEBUG)",
        value=False,
        key="pipeline_execution_debug",
        help="Active les logs DEBUG côté run_execution.py.",
    )
    selected_capital_preset = st.session_state.get("selected_capital_preset")
    capital_preset_key = st.session_state.get(
        "pipeline_capital_preset_key", "custom"
    )
    return {
        "trade_date": trade_date,
        "execution_mode": execution_mode,
        "execution_account_type": execution_account_type,
        "execution_swing_only": execution_swing_only,
        "execution_submission_window": execution_submission_window,
        "execution_max_entry_gap_pct": execution_max_entry_gap_pct,
        "execution_trailing_trigger": execution_trailing_trigger,
        "execution_debug": execution_debug,
        "selected_capital_preset": selected_capital_preset,
        "capital_preset_key": capital_preset_key,
    }


def render_model_factory_block() -> dict[str, Any]:
    """Stub Sprint S19.1 — BLOCK 3 (Model Factory).

    Retourne un dict avec les clés contractuelles attendues par les
    tests AppTest. L'implémentation complète (≈ 700 lignes) sera
    extraite de ``_build_launch_options`` lors de la PR S19.1-bis,
    avec sous-découpage en ``_render_model_factory_{preset,grids,hyperparams}.py``.
    """
    ml_accelerator = st.selectbox(
        "Accélérateur ML",
        options=["cpu", "gpu", "auto"],
        index=2,
        key="pipeline_ml_accelerator",
        help="`auto` détecte la présence d'un GPU CUDA.",
    )
    ml_target_mode = st.selectbox(
        "Mode cible ML",
        options=["swing_5d", "swing_10d", "intraday"],
        index=0,
        key="pipeline_ml_target_mode",
        help="Horizon de prédiction du modèle champion.",
    )
    ml_walkforward = st.checkbox(
        "Activer walk-forward",
        value=True,
        key="pipeline_ml_walkforward",
        help="Validation hors échantillon roulante.",
    )
    ml_wf_max_splits = int(
        st.number_input(
            "Walk-forward — splits max",
            min_value=1,
            max_value=20,
            value=5,
            step=1,
            key="pipeline_ml_wf_max_splits",
            help="Nombre maximum de splits walk-forward.",
        )
    )
    ml_candidate_horizons_selection = st.multiselect(
        "Horizons candidats",
        options=["1d", "3d", "5d", "10d", "20d"],
        default=["5d", "10d"],
        key="pipeline_ml_candidate_horizons_selection",
        help="Horizons à explorer en grille candidate.",
    )
    ml_min_trades_fraction = float(
        st.slider(
            "Fraction minimum de trades",
            min_value=0.0,
            max_value=1.0,
            value=0.3,
            step=0.05,
            key="pipeline_ml_min_trades_fraction",
            help="Filtre minimum de trades sur la fenêtre d'entraînement.",
        )
    )
    return {
        "ml_accelerator": ml_accelerator,
        "ml_target_mode": ml_target_mode,
        "ml_walkforward": ml_walkforward,
        "ml_wf_max_splits": ml_wf_max_splits,
        "ml_candidate_horizons_selection": ml_candidate_horizons_selection,
        "ml_min_trades_fraction": ml_min_trades_fraction,
    }



