"""Sprint S7 — Property-based tests sur la neutralisation sectorielle.

Vérifie les invariants critiques de ``selector.ranking.apply_sector_neutrality``
et ``rank_and_select`` :

1. Plafond sectoriel respecté (sauf "Unknown" qui n'a pas de cap).
2. Idempotence : appliquer 2 fois donne le même résultat.
3. Préservation cardinalité : len(out) <= min(len(in), selection_size).
4. Stabilité par permutation des lignes en entrée.
5. Monotonie du final_score : pour chaque secteur, l'ordre relatif est préservé.
"""

from __future__ import annotations

import math

import pandas as pd
import pytest

from selector.config import AlphaScannerConfig
from selector.ranking import apply_sector_neutrality, rank_and_select

hypothesis = pytest.importorskip("hypothesis")
HealthCheck = hypothesis.HealthCheck
given = hypothesis.given
settings = hypothesis.settings
st = hypothesis.strategies


# Univers de secteurs réduit pour la stratégie hypothesis.
_SECTORS = ["Tech", "Health", "Fin", "Energy", "Cons"]


def _row_strategy() -> st.SearchStrategy[dict]:
    return st.fixed_dictionaries(
        {
            "symbol": st.text(alphabet=st.characters(min_codepoint=65, max_codepoint=90), min_size=1, max_size=5),
            "sector": st.sampled_from(_SECTORS),
            "final_score": st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
            "trend_score": st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
            "vcp_score": st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
            "avg_dollar_volume_20d": st.floats(min_value=1e6, max_value=1e10, allow_nan=False, allow_infinity=False),
        }
    )


def _make_df(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    # Garantir unicité des symboles pour éviter les ex-aequo bruyants.
    df["symbol"] = [f"S{i:03d}" for i in range(len(df))]
    return df


@given(
    rows=st.lists(_row_strategy(), min_size=1, max_size=60),
    selection_size=st.integers(min_value=1, max_value=30),
    sector_cap_ratio=st.floats(min_value=0.05, max_value=1.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=80, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_apply_sector_neutrality_respects_sector_cap(
    rows: list[dict], selection_size: int, sector_cap_ratio: float
) -> None:
    df = _make_df(rows)
    config = AlphaScannerConfig.strict_swing_cash(
        selection_size=selection_size, sector_cap_ratio=sector_cap_ratio
    )
    result = apply_sector_neutrality(df, config)

    assert len(result) <= min(len(df), selection_size)
    sector_cap = max(1, int(math.floor(selection_size * sector_cap_ratio)))
    if not result.empty:
        # Cap NE s'applique PAS au secteur "Unknown" (cf. ranking.py:275).
        counts = result[result["sector"] != "Unknown"]["sector"].value_counts()
        for sector, count in counts.items():
            assert count <= sector_cap, f"sector {sector} exceeds cap {sector_cap}: {count}"


@given(
    rows=st.lists(_row_strategy(), min_size=1, max_size=40),
    selection_size=st.integers(min_value=1, max_value=20),
)
@settings(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_apply_sector_neutrality_is_idempotent(rows: list[dict], selection_size: int) -> None:
    df = _make_df(rows)
    config = AlphaScannerConfig.strict_swing_cash(selection_size=selection_size, sector_cap_ratio=0.30)
    once = apply_sector_neutrality(df, config)
    if once.empty:
        return
    # Appliquer une 2e fois sur le résultat (qui est déjà <= selection_size).
    twice = apply_sector_neutrality(once, config)
    assert list(twice["symbol"]) == list(once["symbol"])


@given(
    rows=st.lists(_row_strategy(), min_size=2, max_size=30),
    selection_size=st.integers(min_value=1, max_value=15),
)
@settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_apply_sector_neutrality_is_permutation_stable(
    rows: list[dict], selection_size: int
) -> None:
    df = _make_df(rows)
    config = AlphaScannerConfig.strict_swing_cash(selection_size=selection_size, sector_cap_ratio=0.30)
    result_a = apply_sector_neutrality(df, config)
    result_b = apply_sector_neutrality(df.iloc[::-1].reset_index(drop=True), config)
    # En cas d'ex-aequo total sur les scores, l'ordre stable de pandas peut
    # retourner des symboles différents entre les permutations. On vérifie
    # alors uniquement la cardinalité et la répartition sectorielle.
    assert len(result_a) == len(result_b)
    assert (
        result_a["sector"].value_counts().sort_index().tolist()
        == result_b["sector"].value_counts().sort_index().tolist()
    )


@given(
    rows=st.lists(_row_strategy(), min_size=2, max_size=30),
    selection_size=st.integers(min_value=2, max_value=15),
)
@settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_apply_sector_neutrality_preserves_intra_sector_order(
    rows: list[dict], selection_size: int
) -> None:
    df = _make_df(rows)
    config = AlphaScannerConfig.strict_swing_cash(selection_size=selection_size, sector_cap_ratio=0.50)
    result = apply_sector_neutrality(df, config)
    if result.empty:
        return
    # Pour chaque secteur sélectionné, l'ordre des final_score doit être décroissant.
    for sector, group in result.groupby("sector"):
        scores = group["final_score"].tolist()
        assert scores == sorted(scores, reverse=True), (
            f"sector {sector} scores not decreasing: {scores}"
        )


@given(
    rows=st.lists(_row_strategy(), min_size=1, max_size=30),
    selection_size=st.integers(min_value=1, max_value=15),
)
@settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_rank_and_select_respects_invariants(rows: list[dict], selection_size: int) -> None:
    df = _make_df(rows)
    config = AlphaScannerConfig.strict_swing_cash(selection_size=selection_size, sector_cap_ratio=0.30)
    out = rank_and_select(df, config)
    assert len(out) <= min(len(df), selection_size)
    if not out.empty:
        # rank doit être 1..N consécutif.
        assert out["rank"].tolist() == list(range(1, len(out) + 1))
        # final_score décroissant globalement.
        scores = out["final_score"].tolist()
        assert scores == sorted(scores, reverse=True)


