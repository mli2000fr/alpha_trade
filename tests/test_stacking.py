"""tests/test_stacking.py — Tests d'integration pour le Stacking Global Rank.

Verifie que :
- get_feature_columns inclut global_rank quand stacking active
- merge_cross_sectional_features fusionne global_rank correctement
- Le feature contract et fingerprint changent avec le stacking
"""
from __future__ import annotations

import pandas as pd

from modelFactory.cross_sectional import (
    GLOBAL_PRED_FEATURE_COLUMNS,
    merge_cross_sectional_features,
)
from modelFactory.features import (
    build_feature_contract,
    fingerprint,
    get_feature_columns,
)


# ── Feature columns — stacking ──

class TestFeatureColumnsWithStacking:
    def test_global_rank_included_when_stacking_on(self) -> None:
        cols = get_feature_columns(
            include_cross_sectional=True, include_global_stacking=True,
        )
        assert "global_rank" in cols
        # Multi-horizon : GLOBAL_PRED_FEATURE_COLUMNS inclut global_rank_3/5/10 + global_rank
        assert len(GLOBAL_PRED_FEATURE_COLUMNS) == 4
        assert GLOBAL_PRED_FEATURE_COLUMNS[0] == "global_rank_3"

    def test_global_rank_not_included_without_cross_sectional(self) -> None:
        cols = get_feature_columns(include_global_stacking=True)
        assert "global_rank" not in cols

    def test_global_rank_not_included_without_stacking_flag(self) -> None:
        cols = get_feature_columns(include_cross_sectional=True)
        assert "global_rank" not in cols

    def test_no_duplicates_with_stacking(self) -> None:
        cols = get_feature_columns(
            feature_set="expert", include_cross_sectional=True, include_global_stacking=True,
        )
        assert len(cols) == len(set(cols))

    def test_stacking_adds_columns(self) -> None:
        cols_without = get_feature_columns(include_cross_sectional=True)
        cols_with = get_feature_columns(
            include_cross_sectional=True, include_global_stacking=True,
        )
        # Multi-horizon: 4 global_rank columns + interaction features
        assert len(cols_with) > len(cols_without)
        assert "global_rank" in cols_with
        assert "global_rank_3" in cols_with
        assert "global_rank" not in cols_without


# ── merge_cross_sectional_features — stacking ──

class TestMergeWithGlobalRank:
    def test_merge_preserves_global_rank_value(self) -> None:
        symbol_df = pd.DataFrame({
            "symbol": ["AAPL", "MSFT"],
            "date": pd.to_datetime(["2022-06-15", "2022-06-15"]),
            "daily_return": [0.01, -0.005],
        })
        cs_df = pd.DataFrame({
            "symbol": ["AAPL", "MSFT"],
            "date": pd.to_datetime(["2022-06-15", "2022-06-15"]),
            "ret_20_rank": [0.65, 0.45],
            "global_rank": [0.72, 0.48],
        })
        merged = merge_cross_sectional_features(symbol_df, cs_df)
        assert merged.loc[0, "global_rank"] == 0.72
        assert merged.loc[1, "global_rank"] == 0.48

    def test_merge_fills_missing_global_rank_with_neutral(self) -> None:
        symbol_df = pd.DataFrame({
            "symbol": ["AAPL"],
            "date": pd.to_datetime(["2022-01-01"]),
            "daily_return": [0.01],
        })
        cs_df = pd.DataFrame({
            "symbol": ["AAPL"],
            "date": pd.to_datetime(["2022-01-01"]),
            "ret_20_rank": [0.55],
        })
        merged = merge_cross_sectional_features(symbol_df, cs_df)
        assert merged["global_rank"].iloc[0] == 0.5

    def test_merge_without_cache_fills_global_rank(self) -> None:
        symbol_df = pd.DataFrame({
            "symbol": ["AAPL"],
            "date": pd.to_datetime(["2022-01-01"]),
            "daily_return": [0.01],
        })
        merged = merge_cross_sectional_features(symbol_df, None)
        assert "global_rank" in merged.columns
        assert merged["global_rank"].iloc[0] == 0.5

    def test_merge_handles_empty_cache(self) -> None:
        symbol_df = pd.DataFrame({
            "symbol": ["AAPL"],
            "date": pd.to_datetime(["2022-01-01"]),
            "daily_return": [0.01],
        })
        merged = merge_cross_sectional_features(symbol_df, pd.DataFrame())
        assert merged["global_rank"].iloc[0] == 0.5


# ── Fingerprint & Feature Contract — stacking ──

class TestFingerprintWithStacking:
    def test_fingerprint_changes_with_stacking(self) -> None:
        fp_off = fingerprint(include_cross_sectional=True, include_global_stacking=False)
        fp_on = fingerprint(include_cross_sectional=True, include_global_stacking=True)
        assert fp_off != fp_on
        assert len(fp_off) == 16
        assert len(fp_on) == 16

    def test_contract_includes_global_rank(self) -> None:
        contract = build_feature_contract(
            include_cross_sectional=True, include_global_stacking=True,
        )
        assert "global_rank" in contract["feature_columns"]

    def test_fingerprint_stable(self) -> None:
        fp1 = fingerprint(
            feature_set="expert", include_cross_sectional=True, include_global_stacking=True,
        )
        fp2 = fingerprint(
            feature_set="expert", include_cross_sectional=True, include_global_stacking=True,
        )
        assert fp1 == fp2

    def test_contract_includes_stacking_flag(self) -> None:
        contract = build_feature_contract(
            include_cross_sectional=True, include_global_stacking=True,
        )
        assert "global_rank" in contract["feature_columns"]
        assert contract["feature_fingerprint"] is not None

    def test_contract_without_stacking_excludes_global_rank(self) -> None:
        contract = build_feature_contract(include_cross_sectional=True)
        assert "global_rank" not in contract["feature_columns"]


# ── Scenario E2E simplifie : per-symbol recoit global_rank ──

class TestStackingE2E:
    def test_per_symbol_receives_global_rank_via_cache(self) -> None:
        cache = pd.DataFrame({
            "symbol": ["AAPL"] * 3,
            "date": pd.to_datetime(["2022-06-10", "2022-06-13", "2022-06-14"]),
            "ret_20_rank": [0.60, 0.62, 0.58],
            "global_rank": [0.71, 0.73, 0.69],
        })
        bars = pd.DataFrame({
            "symbol": ["AAPL"] * 3,
            "date": pd.to_datetime(["2022-06-10", "2022-06-13", "2022-06-14"]),
            "daily_return": [0.01, -0.005, 0.02],
        })
        merged = merge_cross_sectional_features(bars, cache)
        assert "global_rank" in merged.columns
        assert merged["global_rank"].tolist() == [0.71, 0.73, 0.69]
        cols = get_feature_columns(
            include_cross_sectional=True, include_global_stacking=True,
        )
        assert "global_rank" in cols

    def test_symbol_without_global_rank_gets_neutral(self) -> None:
        cache = pd.DataFrame({
            "symbol": ["MSFT"],
            "date": pd.to_datetime(["2022-06-10"]),
            "ret_20_rank": [0.60],
            "global_rank": [0.71],
        })
        bars = pd.DataFrame({
            "symbol": ["AAPL"],
            "date": pd.to_datetime(["2022-06-10"]),
            "daily_return": [0.01],
        })
        merged = merge_cross_sectional_features(bars, cache)
        assert merged["global_rank"].iloc[0] == 0.5
