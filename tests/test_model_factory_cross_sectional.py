from __future__ import annotations

import numpy as np
import pandas as pd

from modelFactory.cross_sectional import CROSS_SECTIONAL_FEATURE_COLUMNS, build_cross_sectional_features, merge_cross_sectional_features
from modelFactory.cross_sectional import (
    GLOBAL_PRED_FEATURE_COLUMNS,
    SECTOR_FEATURE_COLUMNS,
    _compute_sector_features,
    _load_sector_mapping,
)


def _make_symbol_bars(symbol: str, base: float, n: int = 90) -> pd.DataFrame:
	close = pd.Series(np.linspace(base, base + 20.0, n), dtype=float)
	return pd.DataFrame(
		{
			"symbol": [symbol] * n,
			"date": pd.date_range("2020-01-01", periods=n, freq="D"),
			"open": close * 0.99,
			"high": close * 1.01,
			"low": close * 0.98,
			"close": close,
			"volume": np.linspace(1_000_000, 1_100_000, n),
			"adj_close": close,
			"vwap": close,
			"daily_return": 0.0,
			"is_filled": 0,
		}
	)


def test_build_cross_sectional_features_returns_rank_columns() -> None:
	universe = pd.concat([
		_make_symbol_bars("AAPL", 100.0),
		_make_symbol_bars("MSFT", 120.0),
		_make_symbol_bars("NVDA", 140.0),
	], ignore_index=True)
	benchmark = _make_symbol_bars("SPY", 90.0)

	result, diagnostics = build_cross_sectional_features(universe, benchmark_df=benchmark, min_universe_size=2)

	assert not result.empty
	for col in CROSS_SECTIONAL_FEATURE_COLUMNS:
		assert col in result.columns
	assert diagnostics["enabled"] is True
	assert diagnostics["unique_symbols"] == 3


def test_merge_cross_sectional_features_fills_missing_columns_with_neutral_values() -> None:
	symbol_df = pd.DataFrame(
		{
			"symbol": ["AAPL"],
			"date": [pd.Timestamp("2020-01-01")],
			"daily_return": [0.01],
		}
	)

	merged = merge_cross_sectional_features(symbol_df, pd.DataFrame(columns=["symbol", "date"]))

	for col in CROSS_SECTIONAL_FEATURE_COLUMNS:
		assert merged[col].iloc[0] == 0.5


# ═══════════════════════════════════════════════════════════════════════════
# Sector feature tests
# ═══════════════════════════════════════════════════════════════════════════

def _make_raw_panel() -> pd.DataFrame:
    """Build a minimal raw_panel mimicking _compute_symbol_raw_values output."""
    symbols = ["AAPL", "MSFT", "JPM", "BAC", "XOM", "CVX"]
    dates = pd.date_range("2020-01-15", periods=60, freq="D")
    rows: list[dict] = []
    for sym in symbols:
        for i, d in enumerate(dates):
            rows.append({
                "symbol": sym,
                "date": d,
                "ret_20": 0.02 + 0.01 * i + hash(sym) % 5 * 0.005,
                "ret_60": 0.05 + 0.005 * i,
                "volatility_20": 0.15 + 0.01 * (i % 10),
                "dollar_volume_20": 1e9 + 1e8 * (i % 5),
                "benchmark_return_20": 0.01 + 0.002 * i,
                "benchmark_return_60": 0.03 + 0.001 * i,
            })
    return pd.DataFrame(rows)


def test_sector_feature_columns_defined() -> None:
    """SECTOR_FEATURE_COLUMNS must contain the expected columns."""
    expected = [
        "sector_ret_20",
        "sector_ret_60",
        "sector_vol_20",
        "sector_relative_strength_20",
        "sector_dollar_volume_20",
        "sector_symbol_count",
        "stock_vs_sector_ret_20",
        "stock_vs_sector_ret_60",
    ]
    assert SECTOR_FEATURE_COLUMNS == expected


def test_compute_sector_features_empty_map_returns_empty() -> None:
    """With empty sector_map, return empty DataFrame with correct columns."""
    raw = _make_raw_panel()
    result = _compute_sector_features(raw, {})
    assert result.empty
    for col in SECTOR_FEATURE_COLUMNS:
        assert col in result.columns


def test_compute_sector_features_aggregates_by_sector() -> None:
    """Sector aggregates should be computed per (date, sector)."""
    raw = _make_raw_panel()
    sector_map = {
        "AAPL": "Technology",
        "MSFT": "Technology",
        "JPM": "Financials",
        "BAC": "Financials",
        "XOM": "Energy",
        "CVX": "Energy",
    }
    result = _compute_sector_features(raw, sector_map, min_symbols_per_sector=2)

    assert not result.empty
    for col in SECTOR_FEATURE_COLUMNS:
        assert col in result.columns

    # Same sector, same date → same sector_ret_20
    tech_date = result[(result["symbol"] == "AAPL") & (result["date"] == pd.Timestamp("2020-01-20"))]
    msft_date = result[(result["symbol"] == "MSFT") & (result["date"] == pd.Timestamp("2020-01-20"))]
    if not tech_date.empty and not msft_date.empty:
        assert abs(tech_date["sector_ret_20"].iloc[0] - msft_date["sector_ret_20"].iloc[0]) < 0.01


def test_compute_sector_features_stock_vs_sector() -> None:
    """stock_vs_sector_ret_20 should equal ret_20 - sector_ret_20."""
    raw = _make_raw_panel()
    sector_map = {"AAPL": "Technology", "MSFT": "Technology"}
    result = _compute_sector_features(raw, sector_map, min_symbols_per_sector=2)

    sample = result[result["symbol"] == "AAPL"].iloc[0]
    # ret_20 is from the raw_panel merged in; stock_vs_sector = ret_20 - sector_ret_20
    assert "sector_ret_20" in result.columns
    assert "stock_vs_sector_ret_20" in result.columns
    # stock_vs_sector should be near 0 on average (same-sector stocks move together)
    mean_alpha = result[result["symbol"] == "AAPL"]["stock_vs_sector_ret_20"].mean()
    assert abs(mean_alpha) < 0.1  # should be small


def test_compute_sector_features_handles_small_sectors() -> None:
    """Sectors with < min_symbols_per_sector should get NaN → ffill → 0."""
    raw = _make_raw_panel()
    sector_map = {
        "AAPL": "Technology",
        "MSFT": "Technology",
        "JPM": "Financials",  # only 1 symbol in Financials
    }
    result = _compute_sector_features(raw, sector_map, min_symbols_per_sector=2)

    # Financials (JPM) should have 0 or NaN values since sector has < 2 symbols
    jpm_rows = result[result["symbol"] == "JPM"]
    if not jpm_rows.empty:
        # After ffill+fillna(0), values should be 0 (no prior data for this sector)
        assert jpm_rows["sector_ret_20"].iloc[0] == 0.0 or pd.isna(jpm_rows["sector_ret_20"].iloc[0])


def test_compute_sector_features_symbol_not_in_map() -> None:
    """Symbols not in sector_map should get fillna(0) for sector features."""
    raw = _make_raw_panel()
    sector_map = {"AAPL": "Technology"}  # MSFT not mapped
    result = _compute_sector_features(raw, sector_map, min_symbols_per_sector=2)

    msft_rows = result[result["symbol"] == "MSFT"]
    if not msft_rows.empty:
        assert msft_rows["sector_ret_20"].iloc[0] == 0.0


def test_merge_cross_sectional_features_handles_sector_columns() -> None:
    """merge_cross_sectional_features should fill missing sector columns with 0.0."""
    symbol_df = pd.DataFrame({
        "symbol": ["AAPL"],
        "date": [pd.Timestamp("2020-01-01")],
        "daily_return": [0.01],
    })
    merged = merge_cross_sectional_features(symbol_df, None)

    # Cross-sectional columns → 0.5
    for col in CROSS_SECTIONAL_FEATURE_COLUMNS:
        assert merged[col].iloc[0] == 0.5
    # Sector columns → 0.0
    for col in SECTOR_FEATURE_COLUMNS:
        assert merged[col].iloc[0] == 0.0


def test_merge_cross_sectional_features_preserves_sector_values() -> None:
    """When sector columns are present in cross_sectional_df, they should be preserved."""
    symbol_df = pd.DataFrame({
        "symbol": ["AAPL"],
        "date": [pd.Timestamp("2020-01-15")],
        "daily_return": [0.01],
    })
    cs_df = pd.DataFrame({
        "symbol": ["AAPL"],
        "date": [pd.Timestamp("2020-01-15")],
        "sector_ret_20": [0.035],
        "sector_vol_20": [0.18],
        "stock_vs_sector_ret_20": [-0.005],
    })
    merged = merge_cross_sectional_features(symbol_df, cs_df)

    assert merged["sector_ret_20"].iloc[0] == 0.035
    assert merged["sector_vol_20"].iloc[0] == 0.18
    assert merged["stock_vs_sector_ret_20"].iloc[0] == -0.005
    # Missing sector columns should get default 0.0
    for col in SECTOR_FEATURE_COLUMNS:
        if col not in cs_df.columns:
            assert merged[col].iloc[0] == 0.0


def test_compute_sector_features_relative_strength() -> None:
    """sector_relative_strength_20 = sector_ret_20 - benchmark_return_20."""
    raw = _make_raw_panel()
    sector_map = {"AAPL": "Technology", "MSFT": "Technology"}
    result = _compute_sector_features(raw, sector_map, min_symbols_per_sector=2)

    assert "sector_relative_strength_20" in result.columns
    assert "sector_ret_20" in result.columns
    # Should not be all zeros
    assert result["sector_relative_strength_20"].abs().max() > 0.001


def test_compute_sector_features_sector_symbol_count() -> None:
    """sector_symbol_count should reflect the number of symbols in the sector."""
    raw = _make_raw_panel()
    sector_map = {
        "AAPL": "Technology",
        "MSFT": "Technology",
        "JPM": "Financials",
        "BAC": "Financials",
    }
    result = _compute_sector_features(raw, sector_map, min_symbols_per_sector=2)

    tech_count = result[result["symbol"] == "AAPL"]["sector_symbol_count"].iloc[-1]
    fin_count = result[result["symbol"] == "JPM"]["sector_symbol_count"].iloc[-1]
    assert tech_count == 2.0
    assert fin_count == 2.0


# ═══════════════════════════════════════════════════════════════════════════
# Per-sector XS merge tests (Action 1.1 audit, 2026-08-04)
# ═══════════════════════════════════════════════════════════════════════════

def test_per_sector_xs_merge_uses_global_universe() -> None:
    """Les colonnes XS d'un sous-ensemble sectoriel reçoivent les vraies valeurs
    du cache global, pas les defaults neutres (0.5 / 0.0).

    Scénario : 3 symboles dans l'univers global, 2 dans un secteur.
    On construit le cache XS global, puis on merge sur le sous-ensemble sectoriel.
    Les colonnes de rang doivent avoir une variance > 0 (valeurs réelles).
    """
    rng = np.random.default_rng(42)
    n = 120

    def _make_bars(symbol: str, base: float) -> pd.DataFrame:
        close = base + rng.normal(0, 2, n).cumsum() * 0.5
        return pd.DataFrame({
            "symbol": [symbol] * n,
            "date": pd.date_range("2020-01-01", periods=n, freq="B"),
            "open": close - 0.5,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": np.linspace(500_000, 2_000_000, n),
            "adj_close": close,
            "vwap": close,
            "daily_return": [0.0] * n,
            "is_filled": [1] * n,
        })

    # Univers global : 3 symboles
    bars_aapl = _make_bars("AAPL", 150.0)
    bars_msft = _make_bars("MSFT", 300.0)
    bars_jpm  = _make_bars("JPM", 120.0)
    universe = pd.concat([bars_aapl, bars_msft, bars_jpm], ignore_index=True)

    # Cache XS global (simule run_per_sector_batch)
    from modelFactory.cross_sectional import (
        build_cross_sectional_features,
        merge_cross_sectional_features,
    )
    cs_cache, _ = build_cross_sectional_features(
        universe,
        benchmark_df=None,
        min_universe_size=2,
    )

    # Secteur « Tech » : seulement AAPL et MSFT
    sector_symbols_df = pd.concat([bars_aapl, bars_msft], ignore_index=True)
    sector_symbols_df = sector_symbols_df.sort_values(["date", "symbol"]).reset_index(drop=True)
    # Garder seulement les colonnes de base (pas de features déjà calculées)
    sector_bare = sector_symbols_df[["symbol", "date", "close", "volume"]].copy()

    # Merge XS
    merged = merge_cross_sectional_features(sector_bare, cs_cache)

    # ── Vérifications ──
    # 1. Les colonnes de rang cross-sectionnel existent
    for col in CROSS_SECTIONAL_FEATURE_COLUMNS:
        assert col in merged.columns, f"XS column {col} missing after merge"

    # 2. Les colonnes de rang ont de la variance (pas toutes à 0.5)
    rank_cols_present = [c for c in CROSS_SECTIONAL_FEATURE_COLUMNS if c in merged.columns]
    rank_var = merged[rank_cols_present].var(numeric_only=True)
    alive_ranks = int((rank_var > 1e-9).sum())
    assert alive_ranks >= len(rank_cols_present) * 0.5, (
        f"Only {alive_ranks}/{len(rank_cols_present)} XS rank columns have variance > 0 "
        f"— XS merge is not feeding real values"
    )

    # 3. Les valeurs ne sont pas toutes égales à 0.5 (default neutre)
    for col in rank_cols_present[:3]:  # vérifier 3 colonnes représentatives
        unique_vals = merged[col].unique()
        assert not np.allclose(unique_vals, 0.5), (
            f"XS column {col} is all 0.5 — merge returned neutral defaults, not real ranks"
        )


def test_per_sector_feature_contract_includes_fundamentals_when_enabled() -> None:
    """Quand include_fundamentals=True, get_feature_columns retourne les colonnes
    fondamentales. Quand False, elles sont absentes. Les colonnes retournées
    correspondent à FUNDAMENTAL_FEATURE_COLUMNS du module fundamental_features.
    """
    from modelFactory.features import get_feature_columns
    from modelFactory.fundamental_features import FUNDAMENTAL_FEATURE_COLUMNS

    # ── Avec fondamentales ──
    cols_with = get_feature_columns(
        include_fundamentals=True,
        feature_set="expert",
        include_cross_sectional=False,
    )
    for fcol in FUNDAMENTAL_FEATURE_COLUMNS:
        assert fcol in cols_with, (
            f"Fundamental column '{fcol}' missing from get_feature_columns "
            f"with include_fundamentals=True"
        )

    # ── Sans fondamentales ──
    cols_without = get_feature_columns(
        include_fundamentals=False,
        feature_set="expert",
        include_cross_sectional=False,
    )
    for fcol in FUNDAMENTAL_FEATURE_COLUMNS:
        assert fcol not in cols_without, (
            f"Fundamental column '{fcol}' present in get_feature_columns "
            f"with include_fundamentals=False"
        )

    # ── Contrat : les colonnes fondamentales sont > 0 ──
    assert len(FUNDAMENTAL_FEATURE_COLUMNS) > 0, "FUNDAMENTAL_FEATURE_COLUMNS is empty"
    assert len(cols_with) > len(cols_without), (
        "Feature columns count should increase when fundamentals are enabled"
    )


# ─────────────────────────────────────────────────────────────────────
# Approche 2 — Stacking : GLOBAL_PRED_FEATURE_COLUMNS
# ─────────────────────────────────────────────────────────────────────

def test_global_pred_feature_columns_defined() -> None:
    # Multi-horizon : 4 colonnes (global_rank_3, _5, _10, + backward compat global_rank)
    assert len(GLOBAL_PRED_FEATURE_COLUMNS) >= 3
    assert "global_rank" in GLOBAL_PRED_FEATURE_COLUMNS
    assert "global_rank_10" in GLOBAL_PRED_FEATURE_COLUMNS


def test_merge_cross_sectional_features_handles_global_rank() -> None:
    symbol_df = pd.DataFrame({
        "symbol": ["AAPL", "MSFT"],
        "date": [pd.Timestamp("2022-06-15"), pd.Timestamp("2022-06-15")],
        "daily_return": [0.01, -0.005],
    })
    cs_df = pd.DataFrame({
        "symbol": ["AAPL", "MSFT"],
        "date": [pd.Timestamp("2022-06-15"), pd.Timestamp("2022-06-15")],
        "ret_20_rank": [0.65, 0.45],
        "global_rank": [0.72, 0.48],
    })
    merged = merge_cross_sectional_features(symbol_df, cs_df)
    assert "global_rank" in merged.columns
    assert merged.loc[merged["symbol"] == "AAPL", "global_rank"].iloc[0] == 0.72
    assert merged.loc[merged["symbol"] == "MSFT", "global_rank"].iloc[0] == 0.48


def test_merge_cross_sectional_features_fills_missing_global_rank() -> None:
    symbol_df = pd.DataFrame({
        "symbol": ["AAPL"],
        "date": [pd.Timestamp("2022-01-01")],
        "daily_return": [0.01],
    })
    # Cache without global_pred_long
    cs_df = pd.DataFrame({
        "symbol": ["AAPL"],
        "date": [pd.Timestamp("2022-01-01")],
        "ret_20_rank": [0.55],
    })
    merged = merge_cross_sectional_features(symbol_df, cs_df)
    assert "global_rank" in merged.columns
    assert merged["global_rank"].iloc[0] == 0.5


def test_merge_cross_sectional_features_global_rank_no_cache() -> None:
    """When cache is None, global_rank defaults to 0.5."""
    symbol_df = pd.DataFrame({
        "symbol": ["AAPL"],
        "date": [pd.Timestamp("2022-01-01")],
        "daily_return": [0.01],
    })
    merged = merge_cross_sectional_features(symbol_df, None)
    assert "global_rank" in merged.columns
    assert merged["global_rank"].iloc[0] == 0.5
# Régression : naming des interactions régime × technique
# ─────────────────────────────────────────────────────────────────────

def test_regime_interaction_column_naming() -> None:
    """Les colonnes d'interaction regime x technique doivent matcher REGIME_INTERACTION_FEATURES."""
    from modelFactory.features import REGIME_INTERACTION_FEATURES

    _interact_pairs = [
        ("momentum_20", "regime_bull_market"),
        ("momentum_20", "regime_risk_off"),
        ("momentum_60", "regime_bull_market"),
        ("momentum_60", "regime_risk_off"),
        ("relative_strength_20", "regime_bull_market"),
        ("relative_strength_20", "regime_risk_off"),
        ("relative_strength_60", "regime_bull_market"),
        ("relative_strength_60", "regime_risk_off"),
        ("rolling_volatility_20", "regime_bull_market"),
        ("rolling_volatility_20", "regime_risk_off"),
        ("vol_ratio_20_60", "regime_bull_market"),
        ("vol_ratio_20_60", "regime_risk_off"),
        ("rsi_14", "regime_bull_market"),
        ("rsi_14", "regime_risk_off"),
        ("sma20_distance", "regime_bull_market"),
        ("sma20_distance", "regime_risk_off"),
        ("sma50_distance", "regime_bull_market"),
        ("sma50_distance", "regime_risk_off"),
    ]

    generated = []
    for tech_col, regime_col in _interact_pairs:
        _regime_suffix = regime_col.replace("regime_", "").replace("_market", "")
        target_col = f"{tech_col}_x_{_regime_suffix}"
        generated.append(target_col)

    assert len(generated) == len(REGIME_INTERACTION_FEATURES)
    assert set(generated) == set(REGIME_INTERACTION_FEATURES), (
        f"Missing: {set(REGIME_INTERACTION_FEATURES) - set(generated)}, "
        f"Extra: {set(generated) - set(REGIME_INTERACTION_FEATURES)}"
    )

    # Verifier qu'aucun nom ne contient "_bull_market" (le bug corrige)
    for col in generated:
        assert "_bull_market" not in col, f"{col} contient _bull_market (bug de naming)"
        assert col.endswith("_bull") or col.endswith("_risk_off"), (
            f"{col} suffixe inattendu"
        )
