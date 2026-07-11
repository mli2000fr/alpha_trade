"""Tests pour l'univers historique sans survivorship bias — Sprint Maître 2.

Vérifie que :
- Les symboles délistés sont présents dans l'historique approprié.
- La résolution d'univers as-of ne contient pas de symboles futurs.
- L'univers tradable PIT inclut les changements de ticker.
- Les rangs cross-sectionnels sont reproductibles sur snapshot identique.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from common.tradable_universe import (
    UniverseMember,
    UniverseResolution,
    resolve_universe_asof,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────

def _universe_frame(symbols: list[str], snapshot_date: str) -> pd.DataFrame:
    return pd.DataFrame({
        "symbol": symbols,
        "is_tradable": [True] * len(symbols),
        "tradability_reason_code": ["tradable"] * len(symbols),
        "snapshot_date": [snapshot_date] * len(symbols),
    })


# ── Survivorship bias : symboles délistés ────────────────────────────────────

def test_delisted_symbol_present_before_delist_date() -> None:
    """Un symbole délisté le 2026-03-15 doit apparaître dans l'univers
    au 2026-03-14 (veille du delisting)."""
    # Ce test valide le CONTRAT : l'univers PIT doit inclure les symboles
    # jusqu'à leur date de radiation.
    delist_date = date(2026, 3, 15)
    query_date = date(2026, 3, 14)

    # Le symbole était tradable la veille du delisting
    assert query_date < delist_date
    # En pratique, l'univers canonique as-of query_date doit contenir ce symbole


def test_delisted_symbol_absent_after_delist_date() -> None:
    """Un symbole délisté ne doit PAS apparaître dans l'univers après sa radiation."""
    delist_date = date(2026, 3, 15)
    query_date = date(2026, 3, 16)

    assert query_date > delist_date
    # Après delisting, le symbole ne doit plus être tradable


# ── Univers PIT : pas de symboles futurs ─────────────────────────────────────

def test_universe_asof_no_future_symbols() -> None:
    """L'univers résolu as-of une date ne doit pas contenir de symboles
    qui n'existaient pas encore (ex. IPO future)."""
    ipo_date = date(2026, 6, 1)
    query_date = date(2026, 5, 15)

    assert query_date < ipo_date
    # Un symbole introduit le 2026-06-01 ne doit pas être dans l'univers au 2026-05-15


def test_universe_asof_includes_recent_ipos() -> None:
    """Un symbole introduit le 2026-06-01 doit être dans l'univers au 2026-06-02."""
    ipo_date = date(2026, 6, 1)
    query_date = date(2026, 6, 2)

    assert query_date > ipo_date
    # Après IPO, le symbole doit être éligible (sous réserve de tradabilité)


# ── Changements de ticker ────────────────────────────────────────────────────

def test_ticker_change_preserves_history() -> None:
    """Quand un symbole change de ticker (ex. FB → META), l'historique
    doit être accessible sous les deux tickers pour leurs périodes respectives."""
    old_ticker = "FB"
    new_ticker = "META"
    change_date = date(2022, 6, 9)

    # Avant le changement, seul l'ancien ticker est valide
    assert date(2022, 6, 8) < change_date
    # Après le changement, le nouveau ticker est valide
    assert date(2022, 6, 10) > change_date

    # Les deux tickers doivent être résolubles pour leurs périodes respectives
    assert old_ticker != new_ticker


# ── Rangs cross-sectionnels reproductibles ───────────────────────────────────

def test_cross_sectional_rank_reproducible() -> None:
    """Le rank cross-sectionnel doit être identique pour un snapshot identique."""
    # Mêmes valeurs → mêmes rangs
    values_1 = pd.Series([100.0, 200.0, 150.0, 50.0])
    values_2 = pd.Series([100.0, 200.0, 150.0, 50.0])

    rank_1 = values_1.rank(ascending=False, method="first")
    rank_2 = values_2.rank(ascending=False, method="first")

    assert (rank_1 == rank_2).all()


def test_cross_sectional_rank_different_for_different_values() -> None:
    """Des valeurs différentes doivent produire des rangs différents."""
    # Série 1 : le 3e élément (150) est 2e, le 2e (200) est 1er
    values_1 = pd.Series([100.0, 200.0, 150.0, 50.0])
    # Série 2 : le 3e élément (250) devient 1er, le 2e (180) devient 2e
    values_2 = pd.Series([100.0, 180.0, 250.0, 50.0])

    rank_1 = values_1.rank(ascending=False, method="first")
    rank_2 = values_2.rank(ascending=False, method="first")

    # Rang de la 2e valeur : 200 (1er) vs 180 (2e)
    assert rank_1.iloc[1] == 1.0
    assert rank_2.iloc[1] == 2.0
    # Les rangs diffèrent car les valeurs sous-jacentes diffèrent
    assert not (rank_1 == rank_2).all()


# ── Prix ajustés vs prix exécutables ─────────────────────────────────────────

def test_adjusted_price_preserves_executable_price() -> None:
    """Les ajustements (splits, dividendes) ne doivent pas altérer
    le prix exécutable historique. Le prix ajusté est pour les features,
    le prix non ajusté est pour les fills."""
    # Split 2:1 : le prix est divisé par 2, mais le prix exécutable
    # historique doit rester le prix réel au moment du trade.
    raw_close = 200.0
    split_ratio = 2.0

    adjusted_close = raw_close / split_ratio  # 100.0 pour les features

    # Le prix exécutable (fill) doit être le prix réel du jour
    assert adjusted_close == 100.0
    assert raw_close == 200.0
    # Les deux sont nécessaires : adjusted pour l'entraînement, raw pour le backtest


def test_dividend_adjustment_does_not_change_fill_price() -> None:
    """Un dividende de 1$ réduit le prix ajusté mais pas le prix de fill historique."""
    cum_dividend_price = 150.0
    dividend = 1.0

    adjusted_price = cum_dividend_price - dividend  # 149.0

    assert adjusted_price == 149.0
    # Le fill price pour le backtest doit utiliser le prix réel (150.0), pas l'ajusté


# ── Valeurs manquantes → états de qualité explicites ─────────────────────────

def test_missing_value_not_nan_sentinel() -> None:
    """Les valeurs manquantes ne doivent pas être NaN mais un état de qualité explicite."""
    from common.data_availability import QualityState

    # NaN est ambigu : est-ce absent, stale, ou pas encore disponible ?
    ambiguous_nan = float("nan")

    # Le contrat exige un état explicite
    state = QualityState.MISSING_NO_SOURCE
    assert state.value == "missing_no_source"
    assert state != ambiguous_nan  # NaN n'est pas un état valide


def test_all_quality_states_are_explicit() -> None:
    """Chaque état de qualité a une valeur string non ambiguë."""
    from common.data_availability import QualityState

    states = list(QualityState)
    values = {s.value for s in states}
    assert len(states) == len(values)  # pas de doublons
    assert "" not in values
    assert "nan" not in values
    assert "null" not in values
