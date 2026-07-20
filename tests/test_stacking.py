"""tests/test_stacking.py — Tests d'intégration pour l'Approche 2 Stacking.

Vérifie que :
- get_feature_columns inclut global_pred_long quand stacking activé
- merge_cross_sectional_features fusionne global_pred_long correctement
- Le feature contract et fingerprint changent avec le stacking
- Le flux per-symbol reçoit bien la feature globale (scénario E2E simplifié)
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from modelFactory.config import GlobalModelConfig, TrainingConfig
from modelFactory.cross_sectional import (
    CROSS_SECTIONAL_FEATURE_COLUMNS,
    GLOBAL_PRED_FEATURE_COLUMNS,
    SECTOR_FEATURE_COLUMNS,
    merge_cross_sectional_features,
)
from modelFactory.features import (
    build_feature_contract,
    fingerprint,
    get_feature_columns,
)


# ─────────────────────────────────────────────────────────────────────
# Feature columns — stacking
# ─────────────────────────────────────────────────────────────────────

class TestFeatureColumnsWithStacking:
    def test_global_pred_included_when_stacking_on(self) -> None:
        cols = get_feature_columns(
            include_cross_sectional=True, include_global_stacking=True,
        )
        assert "global_pred_long" in cols
        assert "ret_20_rank" in cols   # cross-sectional still there
        assert "sector_ret_20" in cols  # sector still there

    def test_global_pred_not_included_without_cross_sectional(self) -> None:
        """Stacking sans cross-sectional n'ajoute rien."""
        cols = get_feature_columns(include_global_stacking=True)
        assert "global_pred_long" not in cols

    def test_global_pred_not_included_without_stacking_flag(self) -> None:
        """Sans le flag stacking, pas de global_pred même avec cross-sectional."""
        cols = get_feature_columns(include_cross_sectional=True)
        assert "global_pred_long" not in cols

    def test_no_duplicates_with_stacking(self) -> None:
        """Aucun doublon quand stacking + cross-sectional activés."""
        cols = get_feature_columns(
            feature_set="expert", include_cross_sectional=True, include_global_stacking=True,
        )
        assert len(cols) == len(set(cols))

    def test_stacking_adds_exactly_one_column(self) -> None:
        cols_without = get_feature_columns(include_cross_sectional=True)
        cols_with = get_feature_columns(
            include_cross_sectional=True, include_global_stacking=True,
        )
        assert len(cols_with) == len(cols_without) + 1
        assert "global_pred_long" in cols_with
        assert "global_pred_long" not in cols_without


# ─────────────────────────────────────────────────────────────────────
# merge_cross_sectional_features — stacking
# ─────────────────────────────────────────────────────────────────────

class TestMergeWithGlobalPred:
    def test_merge_preserves_global_pred_values(self) -> None:
        """global_pred_long présent dans le cache → valeurs préservées."""
        symbol_df = pd.DataFrame({
            "symbol": ["AAPL", "MSFT"],
            "date": pd.to_datetime(["2022-06-15", "2022-06-15"]),
            "daily_return": [0.01, -0.005],
        })
        cs_df = pd.DataFrame({
            "symbol": ["AAPL", "MSFT"],
            "date": pd.to_datetime(["2022-06-15", "2022-06-15"]),
            "ret_20_rank": [0.65, 0.45],
            "global_pred_long": [0.72, 0.48],
        })
        merged = merge_cross_sectional_features(symbol_df, cs_df)

        assert merged.loc[0, "global_pred_long"] == 0.72
        assert merged.loc[1, "global_pred_long"] == 0.48

    def test_merge_fills_missing_global_pred_with_neutral(self) -> None:
        """Cache sans global_pred_long → fillna(0.5)."""
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
        assert merged["global_pred_long"].iloc[0] == 0.5

    def test_merge_without_cache_fills_all_columns(self) -> None:
        """Aucun cache → toutes les colonnes (y compris global_pred) = defaults."""
        symbol_df = pd.DataFrame({
            "symbol": ["AAPL"],
            "date": pd.to_datetime(["2022-01-01"]),
            "daily_return": [0.01],
        })
        merged = merge_cross_sectional_features(symbol_df, None)

        assert "global_pred_long" in merged.columns
        assert merged["global_pred_long"].iloc[0] == 0.5
        assert merged["ret_20_rank"].iloc[0] == 0.5
        assert merged["sector_ret_20"].iloc[0] == 0.0

    def test_merge_handles_empty_global_pred_cache(self) -> None:
        """Cache vide → toutes les colonnes = defaults."""
        symbol_df = pd.DataFrame({
            "symbol": ["AAPL"],
            "date": pd.to_datetime(["2022-01-01"]),
            "daily_return": [0.01],
        })
        merged = merge_cross_sectional_features(symbol_df, pd.DataFrame())
        assert merged["global_pred_long"].iloc[0] == 0.5


# ─────────────────────────────────────────────────────────────────────
# Fingerprint & Feature Contract — stacking
# ─────────────────────────────────────────────────────────────────────

class TestFingerprintWithStacking:
    def test_fingerprint_changes_with_stacking(self) -> None:
        fp_off = fingerprint(include_cross_sectional=True, include_global_stacking=False)
        fp_on = fingerprint(include_cross_sectional=True, include_global_stacking=True)
        assert fp_off != fp_on
        assert len(fp_off) == 16
        assert len(fp_on) == 16

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
        assert "global_pred_long" in contract["feature_columns"]
        assert contract["feature_fingerprint"] is not None

    def test_contract_without_stacking_excludes_global_pred(self) -> None:
        contract = build_feature_contract(include_cross_sectional=True)
        assert "global_pred_long" not in contract["feature_columns"]


# ─────────────────────────────────────────────────────────────────────
# Scénario E2E simplifié : per-symbol reçoit global_pred
# ─────────────────────────────────────────────────────────────────────

class TestStackingE2E:
    """Simule le flux : global_pred mergé dans le cache → per-symbol l'utilise."""

    def test_per_symbol_receives_global_pred_via_cache(self) -> None:
        """Un symbole seul récupère sa global_pred depuis le cache cross-sectional."""
        # Simule le cache cross-sectional enrichi (comme dans l'orchestrateur)
        cache = pd.DataFrame({
            "symbol": ["AAPL"] * 3,
            "date": pd.to_datetime(["2022-06-10", "2022-06-13", "2022-06-14"]),
            "ret_20_rank": [0.60, 0.62, 0.58],
            "global_pred_long": [0.71, 0.73, 0.69],
        })

        # Simule les barres du symbole
        bars = pd.DataFrame({
            "symbol": ["AAPL"] * 3,
            "date": pd.to_datetime(["2022-06-10", "2022-06-13", "2022-06-14"]),
            "daily_return": [0.01, -0.005, 0.02],
        })

        # Merge (comme dans _train_worker → train_symbol → merge_cross_sectional_features)
        merged = merge_cross_sectional_features(bars, cache)

        assert "global_pred_long" in merged.columns
        assert merged["global_pred_long"].tolist() == [0.71, 0.73, 0.69]
        # La feature doit être dans get_feature_columns
        cols = get_feature_columns(
            include_cross_sectional=True, include_global_stacking=True,
        )
        assert "global_pred_long" in cols

    def test_symbol_without_global_pred_gets_neutral(self) -> None:
        """Un symbole absent du cache global_pred reçoit 0.5 (neutre)."""
        cache = pd.DataFrame({
            "symbol": ["MSFT"],
            "date": pd.to_datetime(["2022-06-10"]),
            "ret_20_rank": [0.60],
            "global_pred_long": [0.71],
        })
        bars = pd.DataFrame({
            "symbol": ["AAPL"],
            "date": pd.to_datetime(["2022-06-10"]),
            "daily_return": [0.01],
        })
        merged = merge_cross_sectional_features(bars, cache)
        # AAPL n'est pas dans le cache → left join → NaN → fillna(0.5)
        assert merged["global_pred_long"].iloc[0] == 0.5
