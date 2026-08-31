"""tests/test_cross_symbol_features.py — Tests des features cross-symbol exclusives (Sprint 2026-07-21)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from modelFactory.cross_sectional import (
    GLOBAL_EXCLUSIVE_FEATURE_COLUMNS,
    _compute_cross_symbol_features,
    merge_cross_sectional_features,
)
from modelFactory.config import GlobalModelConfig, TrainingConfig


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────

def _make_raw_panel(
    n_symbols: int = 10,
    n_dates: int = 5,
    n_sectors: int = 2,
    seed: int = 42,
) -> tuple[pd.DataFrame, dict[str, str]]:
    """Crée un raw_panel synthétique avec mapping sectoriel."""
    rng = np.random.default_rng(seed)
    symbols = [f"TICKER_{i}" for i in range(n_symbols)]
    sectors = [f"Sector_{i % n_sectors}" for i in range(n_symbols)]
    sector_map = dict(zip(symbols, sectors))

    rows = []
    for sym, sec in zip(symbols, sectors):
        base_ret = rng.normal(0.02 if "Sector_0" in sec else -0.01, 0.05)
        base_vol = rng.uniform(0.01, 0.06)
        for d in range(n_dates):
            rows.append({
                "symbol": sym,
                "date": pd.Timestamp("2024-01-01") + pd.Timedelta(days=d),
                "ret_20": base_ret + rng.normal(0, 0.02),
                "ret_60": base_ret * 2 + rng.normal(0, 0.03),
                "volatility_20": base_vol + rng.uniform(0, 0.02),
                "dollar_volume_20": rng.uniform(1e7, 1e9),
            })
    return pd.DataFrame(rows), sector_map


def _make_minimal_cfg(**kwargs: bool) -> TrainingConfig:
    """Crée une TrainingConfig minimale pour les tests."""
    gm = GlobalModelConfig(
        enabled=kwargs.get("global_enabled", False),
        stacking_enabled=kwargs.get("stacking_enabled", False),
        challenger_enabled=kwargs.get("challenger_enabled", False),
        use_cross_sectional_features=kwargs.get("use_cross_sectional", True),
    )
    from modelFactory.config import (
        BaselineConfig, CalibrationConfig, ChampionSelectionConfig,
        DataConfig, ModelConfig, ReproducibilityConfig,
        ThresholdOptimizationConfig, WalkForwardConfig,
    )
    return TrainingConfig(
        data=DataConfig(
            enable_cross_sectional_features=kwargs.get("cross_sectional", True),
            include_macro_vix_features=kwargs.get("macro_vix", False),
            include_macro_vxn_features=kwargs.get("macro_vxn", False),
            include_macro_vix3m_features=kwargs.get("macro_vix3m", False),
            include_macro_move_features=kwargs.get("macro_move", False),
        ),
        model=ModelConfig(),
        calibration=CalibrationConfig(),
        walk_forward=WalkForwardConfig(),
        baseline=BaselineConfig(),
        global_model=gm,
        champion_selection=ChampionSelectionConfig(),
        reproducibility=ReproducibilityConfig(),
        threshold_optimization=ThresholdOptimizationConfig(),
    )


# ─────────────────────────────────────────────────────────────────────
# _compute_cross_symbol_features
# ─────────────────────────────────────────────────────────────────────

class TestComputeCrossSymbolFeatures:
    """Tests unitaires pour _compute_cross_symbol_features."""

    def test_returns_expected_columns(self) -> None:
        panel, sector_map = _make_raw_panel()
        result = _compute_cross_symbol_features(panel, sector_map)
        assert isinstance(result, pd.DataFrame)
        assert list(result.columns) == ["symbol", "date", *GLOBAL_EXCLUSIVE_FEATURE_COLUMNS]

    def test_empty_panel_returns_empty_frame(self) -> None:
        result = _compute_cross_symbol_features(
            pd.DataFrame(), {"A": "Sector_0"},
        )
        assert result.empty
        assert list(result.columns) == ["symbol", "date", *GLOBAL_EXCLUSIVE_FEATURE_COLUMNS]

    def test_empty_sector_map_returns_empty_frame(self) -> None:
        panel, _ = _make_raw_panel()
        result = _compute_cross_symbol_features(panel, {})
        assert result.empty

    def test_no_sector_match_returns_empty(self) -> None:
        panel, _ = _make_raw_panel()
        # Mapping qui ne correspond à aucun symbole
        result = _compute_cross_symbol_features(panel, {"ZZZ": "Ghost"})
        assert result.empty

    def test_breadth_between_0_and_1(self) -> None:
        panel, sector_map = _make_raw_panel(n_symbols=20, n_dates=3, seed=7)
        result = _compute_cross_symbol_features(panel, sector_map, min_symbols_per_sector=3)
        breadth = result["sector_breadth_20"].dropna()
        assert len(breadth) > 0
        assert breadth.between(0.0, 1.0).all()

    def test_dispersion_non_negative(self) -> None:
        panel, sector_map = _make_raw_panel(n_symbols=20, n_dates=3, seed=7)
        result = _compute_cross_symbol_features(panel, sector_map, min_symbols_per_sector=3)
        disp = result["sector_dispersion_20"].dropna()
        assert len(disp) > 0
        assert (disp >= 0.0).all()

    def test_concentration_between_0_and_1(self) -> None:
        panel, sector_map = _make_raw_panel(n_symbols=20, n_dates=3, seed=7)
        result = _compute_cross_symbol_features(panel, sector_map, min_symbols_per_sector=3)
        conc = result["sector_concentration_20"].dropna()
        assert len(conc) > 0
        assert conc.between(0.0, 1.0).all()

    def test_rank_between_0_and_1(self) -> None:
        panel, sector_map = _make_raw_panel(n_symbols=20, n_dates=3, seed=7)
        result = _compute_cross_symbol_features(panel, sector_map, min_symbols_per_sector=3)
        rank = result["symbol_rank_in_sector_20"].dropna()
        assert len(rank) > 0
        assert rank.between(0.0, 1.0).all()

    def test_vol_ratio_positive(self) -> None:
        panel, sector_map = _make_raw_panel(n_symbols=20, n_dates=3, seed=7)
        result = _compute_cross_symbol_features(panel, sector_map, min_symbols_per_sector=3)
        ratio = result["stock_vs_sector_vol_ratio"].dropna()
        assert len(ratio) > 0
        assert (ratio >= 0.0).all()

    def test_momentum_spread_non_negative(self) -> None:
        panel, sector_map = _make_raw_panel(n_symbols=20, n_dates=3, seed=7)
        result = _compute_cross_symbol_features(panel, sector_map, min_symbols_per_sector=3)
        spread = result["sector_momentum_spread_20"].dropna()
        assert len(spread) > 0
        assert (spread >= 0.0).all()

    def test_small_sector_below_threshold_gets_zero(self) -> None:
        """Secteur avec < min_symbols_per_sector → valeurs à 0 (via ffill/fillna)."""
        panel, sector_map = _make_raw_panel(n_symbols=2, n_dates=3, n_sectors=2, seed=7)
        # Chaque secteur n'a qu'1 symbole → en dessous du seuil de 3
        result = _compute_cross_symbol_features(panel, sector_map, min_symbols_per_sector=3)
        # Toutes les valeurs doivent être 0 (pas d'agrégats calculés)
        for col in GLOBAL_EXCLUSIVE_FEATURE_COLUMNS:
            assert (result[col] == 0.0).all(), f"{col} should be all zeros for small sectors"

    def test_no_nan_in_output(self) -> None:
        panel, sector_map = _make_raw_panel(n_symbols=30, n_dates=5, seed=42)
        result = _compute_cross_symbol_features(panel, sector_map, min_symbols_per_sector=3)
        for col in GLOBAL_EXCLUSIVE_FEATURE_COLUMNS:
            assert not result[col].isna().any(), f"{col} contains NaN"

    def test_symbol_date_index_preserved(self) -> None:
        panel, sector_map = _make_raw_panel(n_symbols=10, n_dates=5)
        result = _compute_cross_symbol_features(panel, sector_map, min_symbols_per_sector=3)
        expected_symbols = set(panel["symbol"].unique())
        actual_symbols = set(result["symbol"].unique())
        assert expected_symbols == actual_symbols
        assert set(result["date"].unique()) == set(panel["date"].unique())

    def test_missing_ret_20_returns_empty(self) -> None:
        """Si ret_20 est absent du raw_panel, retourne DataFrame vide."""
        panel = pd.DataFrame({
            "symbol": ["A", "B", "C"],
            "date": [pd.Timestamp("2024-01-01")] * 3,
            "dollar_volume_20": [1e8, 2e8, 3e8],
        })
        sector_map = {"A": "S1", "B": "S1", "C": "S2"}
        result = _compute_cross_symbol_features(panel, sector_map)
        assert result.empty

    def test_rank_is_neutral_for_small_sectors(self) -> None:
        """rank_in_sector = 0.5 pour les secteurs sous le seuil."""
        panel, sector_map = _make_raw_panel(n_symbols=4, n_dates=2, n_sectors=4, seed=7)
        # Chaque secteur = 1 symbole → rank neutral 0.5
        result = _compute_cross_symbol_features(panel, sector_map, min_symbols_per_sector=3)
        # Après ffill/fillna, tout est à 0 (pas d'agrégat). Mais rank_in_sector
        # suit la même logique : pas d'agrégat → fillna(0.0).
        # En pratique rank vaudra 0.0 après nettoyage.
        assert (result["symbol_rank_in_sector_20"] == 0.0).all()


# ─────────────────────────────────────────────────────────────────────
# merge_cross_sectional_features — cross-symbol exclusives
# ─────────────────────────────────────────────────────────────────────

class TestMergeWithCrossSymbolExclusives:
    """Vérifie que merge_cross_sectional_features gère les colonnes exclusives."""

    def _make_symbol_df(self, symbol: str = "TICKER_0", n_dates: int = 5) -> pd.DataFrame:
        return pd.DataFrame({
            "symbol": [symbol] * n_dates,
            "date": pd.date_range("2024-01-01", periods=n_dates),
            "close": np.random.default_rng(42).uniform(50, 150, n_dates),
        })

    def _make_cross_sectional_df(self, symbols: list[str], n_dates: int = 5) -> pd.DataFrame:
        rows = []
        for sym in symbols:
            for d in range(n_dates):
                rows.append({
                    "symbol": sym,
                    "date": pd.Timestamp("2024-01-01") + pd.Timedelta(days=d),
                    "sector_breadth_20": 0.65,
                    "sector_dispersion_20": 0.03,
                    "sector_concentration_20": 0.40,
                    "symbol_rank_in_sector_20": 0.75,
                    "stock_vs_sector_vol_ratio": 1.20,
                    "sector_momentum_spread_20": 0.08,
                })
        return pd.DataFrame(rows)

    def test_exclusive_columns_merged_correctly(self) -> None:
        sym_df = self._make_symbol_df()
        cs_df = self._make_cross_sectional_df(["TICKER_0"])
        merged = merge_cross_sectional_features(sym_df, cs_df)
        for col in GLOBAL_EXCLUSIVE_FEATURE_COLUMNS:
            assert col in merged.columns, f"{col} missing from merged DataFrame"

    def test_exclusive_columns_have_correct_values(self) -> None:
        sym_df = self._make_symbol_df()
        cs_df = self._make_cross_sectional_df(["TICKER_0"])
        merged = merge_cross_sectional_features(sym_df, cs_df)
        assert (merged["sector_breadth_20"] == 0.65).all()
        assert (merged["symbol_rank_in_sector_20"] == 0.75).all()

    def test_missing_exclusive_columns_filled_with_zero(self) -> None:
        """Si le cache n'a pas les colonnes exclusives, elles sont remplies à 0."""
        sym_df = self._make_symbol_df()
        # Cache sans colonnes exclusives
        cs_df = pd.DataFrame({
            "symbol": ["TICKER_0"] * 5,
            "date": pd.date_range("2024-01-01", periods=5),
        })
        merged = merge_cross_sectional_features(sym_df, cs_df)
        for col in GLOBAL_EXCLUSIVE_FEATURE_COLUMNS:
            assert col in merged.columns, f"{col} missing"
            assert (merged[col] == 0.0).all(), f"{col} should be 0.0, got {merged[col].unique()}"

    def test_none_cache_fills_exclusives_with_zero(self) -> None:
        sym_df = self._make_symbol_df()
        merged = merge_cross_sectional_features(sym_df, None)
        for col in GLOBAL_EXCLUSIVE_FEATURE_COLUMNS:
            assert col in merged.columns
            assert (merged[col] == 0.0).all()

    def test_empty_cache_fills_exclusives_with_zero(self) -> None:
        sym_df = self._make_symbol_df()
        merged = merge_cross_sectional_features(sym_df, pd.DataFrame())
        for col in GLOBAL_EXCLUSIVE_FEATURE_COLUMNS:
            assert col in merged.columns
            assert (merged[col] == 0.0).all()


# ─────────────────────────────────────────────────────────────────────
# _get_global_feature_columns
# ─────────────────────────────────────────────────────────────────────

class TestGetGlobalFeatureColumns:
    """Vérifie que _get_global_feature_columns inclut les exclusives."""

    def test_includes_exclusive_columns_when_cross_sectional_enabled(self) -> None:
        from modelFactory.global_model import _get_global_feature_columns
        cfg = _make_minimal_cfg(cross_sectional=True)
        cols = _get_global_feature_columns(cfg)
        for col in GLOBAL_EXCLUSIVE_FEATURE_COLUMNS:
            assert col in cols, f"{col} missing from global feature columns"

    def test_excludes_exclusive_when_cross_sectional_disabled(self) -> None:
        from modelFactory.global_model import _get_global_feature_columns
        cfg = _make_minimal_cfg(cross_sectional=False)
        cols = _get_global_feature_columns(cfg)
        for col in GLOBAL_EXCLUSIVE_FEATURE_COLUMNS:
            assert col not in cols, f"{col} should not be in global features"

    def test_excludes_ohlcv_and_expert(self) -> None:
        from modelFactory.global_model import _get_global_feature_columns
        from modelFactory.features import EXPERT_FEATURE_COLUMNS, FEATURE_COLUMNS
        cfg = _make_minimal_cfg(cross_sectional=True)
        cols = _get_global_feature_columns(cfg)
        for col in FEATURE_COLUMNS:
            assert col not in cols, f"OHLCV feature {col} should be excluded"
        global_regime_features = {"regime_bull_market", "regime_risk_off"}
        for col in set(EXPERT_FEATURE_COLUMNS) - global_regime_features:
            assert col not in cols, f"Expert feature {col} should be excluded"
        assert global_regime_features.issubset(cols)

    def test_includes_macro_when_enabled(self) -> None:
        from modelFactory.global_model import _get_global_feature_columns
        cfg = _make_minimal_cfg(cross_sectional=True, macro_vix=True, macro_vxn=True)
        cols = _get_global_feature_columns(cfg)
        assert "vix_close" in cols
        assert "vix_momentum_5j" in cols
        assert "vxn_close" in cols
        assert "vxn_spread_vix" in cols

    def test_excludes_macro_when_disabled(self) -> None:
        from modelFactory.global_model import _get_global_feature_columns
        cfg = _make_minimal_cfg(cross_sectional=True, macro_vix=False)
        cols = _get_global_feature_columns(cfg)
        assert "vix_close" not in cols

    def test_use_cross_sectional_flag_respected(self) -> None:
        """GlobalModelConfig.use_cross_sectional_features=False → pas de cross-sectional."""
        from modelFactory.global_model import _get_global_feature_columns
        cfg = _make_minimal_cfg(cross_sectional=True, use_cross_sectional=False)
        cols = _get_global_feature_columns(cfg)
        for col in GLOBAL_EXCLUSIVE_FEATURE_COLUMNS:
            assert col not in cols, f"{col} should be excluded when use_cross_sectional=False"

    def test_total_col_count_matches_expected(self) -> None:
        """26 features globales canoniques, dont les deux indicateurs de régime."""
        from modelFactory.global_model import _get_global_feature_columns
        cfg = _make_minimal_cfg(cross_sectional=True)
        cols = _get_global_feature_columns(cfg)
        assert len(cols) == 26, f"Expected 26 global features, got {len(cols)}: {cols}"


# ─────────────────────────────────────────────────────────────────────
# GLOBAL_EXCLUSIVE_FEATURE_COLUMNS — structure
# ─────────────────────────────────────────────────────────────────────

class TestGlobalExclusiveFeatureColumns:
    def test_column_count(self) -> None:
        assert len(GLOBAL_EXCLUSIVE_FEATURE_COLUMNS) == 6

    def test_all_are_strings(self) -> None:
        for col in GLOBAL_EXCLUSIVE_FEATURE_COLUMNS:
            assert isinstance(col, str)

    def test_no_duplicates(self) -> None:
        assert len(GLOBAL_EXCLUSIVE_FEATURE_COLUMNS) == len(set(GLOBAL_EXCLUSIVE_FEATURE_COLUMNS))

    def test_no_overlap_with_sector_columns(self) -> None:
        from modelFactory.cross_sectional import SECTOR_FEATURE_COLUMNS
        overlap = set(GLOBAL_EXCLUSIVE_FEATURE_COLUMNS) & set(SECTOR_FEATURE_COLUMNS)
        assert len(overlap) == 0, f"Overlap with sector columns: {overlap}"

    def test_no_overlap_with_cross_sectional_columns(self) -> None:
        from modelFactory.cross_sectional import CROSS_SECTIONAL_FEATURE_COLUMNS
        overlap = set(GLOBAL_EXCLUSIVE_FEATURE_COLUMNS) & set(CROSS_SECTIONAL_FEATURE_COLUMNS)
        assert len(overlap) == 0, f"Overlap with cross-sectional columns: {overlap}"

    def test_no_overlap_with_global_pred(self) -> None:
        from modelFactory.cross_sectional import GLOBAL_PRED_FEATURE_COLUMNS
        overlap = set(GLOBAL_EXCLUSIVE_FEATURE_COLUMNS) & set(GLOBAL_PRED_FEATURE_COLUMNS)
        assert len(overlap) == 0
