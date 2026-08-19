"""Tests unitaires du builder de labels Oracle — Sprint S1.

Couvre les fonctions pures (sans DB) :
- ``compute_cross_sectional_ranks`` : définition du percentile cross-sectionnel
  identique à l'audit §19 (fraction de l'univers ≤ rendement), déciles, top/bottom 10 % ;
- ``check_universe_equality`` : contrôle bit-for-bit ``global_rank_history`` ↔
  ``model_predictions``.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from modelFactory.oracle.build_labels import (
    check_universe_equality,
    compute_cross_sectional_ranks,
)


# ═══════════════════════════════════════════════════════════════════
# compute_cross_sectional_ranks
# ═══════════════════════════════════════════════════════════════════

class TestComputeCrossSectionalRanks:
    def test_pct_rank_matches_audit_definition(self):
        # 4 rendements croissants : pct_rank = fraction de l'univers <= rendement
        returns = pd.Series([0.10, 0.20, 0.30, 0.40], index=["A", "B", "C", "D"])
        df = compute_cross_sectional_ranks(returns, top_pct=0.10)
        # D (0.40) est au-dessus de 100% de l'univers → pct_rank 1.0
        assert df.loc["D", "oracle_pct_rank"] == pytest.approx(1.0)
        # A (0.10) est au-dessus de 25% de l'univers (lui-même inclus)
        assert df.loc["A", "oracle_pct_rank"] == pytest.approx(0.25)
        # B (0.20) → 50%
        assert df.loc["B", "oracle_pct_rank"] == pytest.approx(0.50)

    def test_deciles_are_1_to_10(self):
        returns = pd.Series(np.arange(1.0, 11.0), index=[f"S{i}" for i in range(10)])
        df = compute_cross_sectional_ranks(returns, top_pct=0.10)
        assert set(df["oracle_decile"].unique()).issubset(set(range(1, 11)))
        assert df["oracle_decile"].min() == 1
        assert df["oracle_decile"].max() == 10

    def test_top10_and_bottom10_thresholds(self):
        # 10 symboles, top_pct 0.10 → le meilleur = top, le pire = bottom → extreme10=1 pour les deux
        returns = pd.Series(np.arange(1.0, 11.0), index=[f"S{i}" for i in range(10)])
        df = compute_cross_sectional_ranks(returns, top_pct=0.10)
        assert df.loc["S9", "oracle_extreme10"] == 1   # rendement max (10.0)
        assert df.loc["S0", "oracle_extreme10"] == 1  # rendement min (1.0)
        assert df.loc["S4", "oracle_extreme10"] == 0   # médiane → ni top ni bottom

    def test_nan_ignored(self):
        returns = pd.Series([0.10, 0.20, 0.30, np.nan], index=["A", "B", "C", "D"])
        df = compute_cross_sectional_ranks(returns, top_pct=0.10)
        assert set(df.index) == {"A", "B", "C"}
        assert len(df) == 3

    def test_empty_after_nan(self):
        returns = pd.Series([np.nan, np.nan], index=["A", "B"])
        df = compute_cross_sectional_ranks(returns, top_pct=0.10)
        assert df.empty
        assert list(df.columns) == [
            "oracle_pct_rank", "oracle_decile", "oracle_extreme10",
        ]


# ═══════════════════════════════════════════════════════════════════
# check_universe_equality
# ═══════════════════════════════════════════════════════════════════

class TestCheckUniverseEquality:
    def test_equal(self):
        keys = {("2025-01-02", "AAPL"), ("2025-01-02", "MSFT")}
        result = check_universe_equality(keys, set(keys))
        assert result["equal"] is True
        assert result["only_in_ranks"] == 0
        assert result["only_in_preds"] == 0

    def test_divergence_counts_and_samples(self):
        ranks = {("2025-01-02", "AAPL"), ("2025-01-02", "MSFT")}
        preds = {("2025-01-02", "AAPL"), ("2025-01-02", "NVDA")}
        result = check_universe_equality(ranks, preds)
        assert result["equal"] is False
        assert result["only_in_ranks"] == 1
        assert result["only_in_preds"] == 1
        assert result["samples_only_ranks"] == [("2025-01-02", "MSFT")]
        assert result["samples_only_preds"] == [("2025-01-02", "NVDA")]
