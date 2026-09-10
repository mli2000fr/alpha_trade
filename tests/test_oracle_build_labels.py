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
import importlib

from modelFactory.oracle.build_labels import (
    classify_target_quality,
    check_universe_equality,
    compute_cross_sectional_ranks,
)
from modelFactory.oracle.security_continuity import (
    SecurityDiscontinuity,
    path_crosses_known_discontinuity,
    split_frame_on_discontinuities,
)


def test_dynamic_builder_loads_prices_for_admitted_symbols(monkeypatch):
    labels_module = importlib.import_module("modelFactory.oracle.build_labels")
    dynamic_module = importlib.import_module("modelFactory.oracle.dynamic_universe")
    membership = pd.DataFrame({
        "date": pd.to_datetime(["2024-01-02", "2024-01-02"]),
        "symbol": ["AAA", "BBB"],
    })
    monkeypatch.setattr(
        dynamic_module, "load_dynamic_universe_from_bars",
        lambda *args, **kwargs: (membership, {"rows": 2, "symbols": 2, "dates": 1}),
    )
    observed = {}

    class EmptyPrices:
        close = pd.DataFrame()

    def fake_prices(engine, symbols, start_date):
        observed["symbols"] = symbols
        return EmptyPrices()

    monkeypatch.setattr(labels_module, "load_price_matrices", fake_prices)
    result = labels_module.build_labels(
        "batch-p0f", engine=object(), symbols=["AAA", "BBB"],
        start_date="2024-01-01", end_date="2024-12-31",
        universe_mode="pit_dynamic_bars",
    )
    assert observed["symbols"] == ["AAA", "BBB"]
    assert result["reason"] == "no_bars"


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


class TestOracleTargetQuality:
    @staticmethod
    def _registry():
        return {
            "WFRD": (
                SecurityDiscontinuity(
                    symbol="WFRD",
                    last_predecessor_date=pd.Timestamp("2019-12-13"),
                    first_successor_date=pd.Timestamp("2019-12-20"),
                    reason="chapter_11_old_equity_cancelled",
                ),
            ),
        }

    def test_missing_real_exit_bar_is_rejected(self):
        reason = classify_target_quality(
            symbol="AAPL",
            start=pd.Timestamp("2025-01-02"),
            end=pd.Timestamp("2025-01-31"),
            start_price=100.0,
            end_price=np.nan,
            start_source="eodhd_eod",
            end_source=None,
            extreme_breaks=0,
            registry={},
        )
        assert reason == "missing_exit_bar"

    def test_known_security_identity_break_has_priority(self):
        reason = classify_target_quality(
            symbol="WFRD",
            start=pd.Timestamp("2019-12-13"),
            end=pd.Timestamp("2019-12-20"),
            start_price=0.019,
            end_price=24.5,
            start_source="eodhd_eod",
            end_source="eodhd_eod",
            extreme_breaks=1,
            registry=self._registry(),
        )
        assert reason == "known_security_discontinuity"

    def test_large_but_plausible_move_is_preserved(self):
        reason = classify_target_quality(
            symbol="BIOTECH",
            start=pd.Timestamp("2025-01-02"),
            end=pd.Timestamp("2025-01-31"),
            start_price=10.0,
            end_price=37.2,
            start_source="eodhd_eod",
            end_source="eodhd_eod",
            extreme_breaks=0,
            registry={},
        )
        assert reason is None

    def test_unexplained_extreme_price_break_is_quarantined(self):
        reason = classify_target_quality(
            symbol="UNKNOWN",
            start=pd.Timestamp("2025-01-02"),
            end=pd.Timestamp("2025-01-31"),
            start_price=0.02,
            end_price=25.0,
            start_source="eodhd_eod",
            end_source="eodhd_eod",
            extreme_breaks=1,
            registry={},
        )
        assert reason == "extreme_unadjusted_price_jump"

    def test_feature_history_is_split_at_security_break(self):
        frame = pd.DataFrame({
            "date": pd.to_datetime(["2019-12-12", "2019-12-13", "2019-12-20", "2019-12-23"]),
            "close": [0.02, 0.019, 24.5, 25.0],
        })
        parts = list(split_frame_on_discontinuities(frame, "WFRD", self._registry()))
        assert [len(part) for part in parts] == [2, 2]
        assert parts[1]["date"].min() == pd.Timestamp("2019-12-20")

    def test_path_crossing_rule_is_inclusive(self):
        assert path_crosses_known_discontinuity(
            "WFRD",
            pd.Timestamp("2019-12-13"),
            pd.Timestamp("2019-12-20"),
            self._registry(),
        )
        assert not path_crosses_known_discontinuity(
            "WFRD",
            pd.Timestamp("2019-12-20"),
            pd.Timestamp("2020-01-20"),
            self._registry(),
        )
