"""Tests unitaires — features "direction" (2026-08-23).

Couvre :
1. La liste ``DIRECTIONAL_FEATURES`` (14 features uniques).
2. L'injection dans ``_get_ranking_feature_columns`` : mode direction → seules
   les 14 features de la liste + les features de base (pas les ~40 autres
   cross-sectionnelles, pas de doublons).
3. Le filtrage ``feature_subset`` de ``build_cross_sectional_features`` :
   seule la liste direction est calculée/retournée.
4. La prédiction ``predict_global_rank`` : charge le benchmark quand
   ``benchmark_df is None`` + feature_set="expert" (bug de parité corrigé).
5. La condition benchmark de ``predictor._prepare_prediction_frame`` inclut
   le mode direction.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from modelFactory import global_ranking
from modelFactory import predictor
from modelFactory.config import DataConfig, TrainingConfig
from modelFactory.cross_sectional import (
    CROSS_SECTIONAL_FEATURE_COLUMNS,
    DIRECTIONAL_FEATURES,
    SECTOR_FEATURE_COLUMNS,
    SECTOR_NEUTRAL_FEATURE_COLUMNS,
    SECTOR_ZSCORE_FEATURE_COLUMNS,
    build_cross_sectional_features,
)
from modelFactory.global_ranking import _get_ranking_feature_columns


# ═══════════════════════════════════════════════════════════════════════════
# 1. DIRECTIONAL_FEATURES — la liste
# ═══════════════════════════════════════════════════════════════════════════

def test_directional_features_list_is_exactly_14_unique() -> None:
    assert len(DIRECTIONAL_FEATURES) == 14
    assert len(set(DIRECTIONAL_FEATURES)) == 14, "doublons dans DIRECTIONAL_FEATURES"


def test_directional_features_list_matches_requested_subset() -> None:
    requested = [
        "stock_vs_sector_ret_20", "stock_vs_sector_ret_60",
        "momentum_20_sector_neutral",
        "stock_vs_sector_ret_5", "sector_relative_strength_20",
        "sector_ret_20", "sector_ret_60", "sector_ret_5",
        "momentum_20_xs_rank", "momentum_60_xs_rank", "momentum_10_xs_rank",
        "momentum_5_xs_rank", "momentum_120_xs_rank", "range_position_20_xs_rank",
    ]
    assert set(DIRECTIONAL_FEATURES) == set(requested)


# ═══════════════════════════════════════════════════════════════════════════
# 2. _get_ranking_feature_columns — injection mode direction
# ═══════════════════════════════════════════════════════════════════════════

def _make_cfg(**data_kwargs: Any) -> TrainingConfig:
    data = DataConfig(
        feature_set="expert",
        include_short_score_features=True,
        include_factors_features=True,
        benchmark_symbol="SPY",
        **data_kwargs,
    )
    return TrainingConfig(data=data)


def test_ranking_columns_off_does_not_inject_directional() -> None:
    cfg = _make_cfg(enable_cross_sectional_features=False, include_directional_features=False)
    cols = _get_ranking_feature_columns(cfg)
    # Sans mode direction, les features sectorielles/sector-neutral ne sont pas là
    # (les *_xs_rank sont générées par la normalisation xs_rank, indépendantes).
    directional_in = [f for f in DIRECTIONAL_FEATURES if f in cols]
    # Attention : 6 des 14 sont des *_xs_rank déjà présentes (mécanisme xs_rank).
    assert len(directional_in) <= 6


def test_ranking_columns_directional_injects_exactly_14() -> None:
    cfg = _make_cfg(enable_cross_sectional_features=False, include_directional_features=True)
    cols = _get_ranking_feature_columns(cfg)

    # Toutes les 14 direction présentes
    for f in DIRECTIONAL_FEATURES:
        assert f in cols, f"{f} absente en mode direction"

    # Aucune des ~40 autres features cross/sector/sector-neutral
    family = set(CROSS_SECTIONAL_FEATURE_COLUMNS) | set(SECTOR_FEATURE_COLUMNS) | set(SECTOR_NEUTRAL_FEATURE_COLUMNS) | set(SECTOR_ZSCORE_FEATURE_COLUMNS)
    extra = sorted((family - set(DIRECTIONAL_FEATURES)) & set(cols))
    assert extra == [], f"features cross-sectional non-direction présentes: {extra}"

    # Les *_xs_rank de base (rangs percentiles de features techniques) sont
    # CONSERVÉS : ils ne font pas partie de la famille cross-sectionnelle.
    # Seule la famille cross/sector/sector-neutral non-direction est retirée.
    base_xs = sorted(c for c in cols if c.endswith("_xs_rank") and c not in DIRECTIONAL_FEATURES)
    assert base_xs, "les *_xs_rank de base doivent être conservés en mode direction"

    # Pas de doublons
    assert len(cols) == len(set(cols)), "doublons dans les colonnes ranking"


def test_ranking_columns_directional_with_cross_sectional_keeps_direction_only() -> None:
    cfg = _make_cfg(enable_cross_sectional_features=True, include_directional_features=True)
    cols = _get_ranking_feature_columns(cfg)

    family = set(CROSS_SECTIONAL_FEATURE_COLUMNS) | set(SECTOR_FEATURE_COLUMNS) | set(SECTOR_NEUTRAL_FEATURE_COLUMNS) | set(SECTOR_ZSCORE_FEATURE_COLUMNS)
    extra = sorted((family - set(DIRECTIONAL_FEATURES)) & set(cols))
    assert extra == [], f"features cross-sectional non-direction présentes (BOTH): {extra}"
    for f in DIRECTIONAL_FEATURES:
        assert f in cols, f"{f} absente (BOTH)"
    assert len(cols) == len(set(cols))


def test_ranking_columns_directional_vs_cross_sectional_counts() -> None:
    # Le mode direction doit donner MOINS de features que le cross-sectional complet
    cfg_dir = _make_cfg(enable_cross_sectional_features=False, include_directional_features=True)
    cfg_cs = _make_cfg(enable_cross_sectional_features=True, include_directional_features=False)
    cols_dir = _get_ranking_feature_columns(cfg_dir)
    cols_cs = _get_ranking_feature_columns(cfg_cs)
    assert len(cols_dir) < len(cols_cs)


# ═══════════════════════════════════════════════════════════════════════════
# 3. build_cross_sectional_features — feature_subset
# ═══════════════════════════════════════════════════════════════════════════

def _make_universe() -> pd.DataFrame:
    rng = np.random.default_rng(0)
    dates = pd.date_range("2023-01-01", periods=60, freq="D")
    symbols = ["A", "B", "C", "D", "E"]
    parts: list[pd.DataFrame] = []
    for s in symbols:
        close = 100.0 + np.cumsum(rng.normal(0, 1, 60))
        parts.append(
            pd.DataFrame(
                {
                    "symbol": s,
                    "date": dates,
                    "open": close * 0.99,
                    "high": close * 1.01,
                    "low": close * 0.98,
                    "close": close,
                    "adj_close": close,
                    "volume": rng.integers(100_000, 500_000, 60),
                    "vwap": close,
                    "daily_return": 0.0,
                    "is_filled": 0,
                }
            )
        )
    return pd.concat(parts, ignore_index=True)


def test_build_cross_sectional_feature_subset_returns_direction_only() -> None:
    universe = _make_universe()
    sector_map = {"A": "Tech", "B": "Tech", "C": "Energy", "D": "Energy", "E": "Health"}
    out, diag = build_cross_sectional_features(
        universe,
        min_universe_size=3,
        sector_map=sector_map,
        feature_subset=DIRECTIONAL_FEATURES,
    )
    cols = [c for c in out.columns if c not in ("symbol", "date")]
    # 8 features sectorielles/sector-neutral de la liste direction
    # (les *_xs_rank sont générées par le mécanisme xs_rank du global ranking)
    assert len(cols) == 8
    for c in cols:
        assert c in DIRECTIONAL_FEATURES, f"{c} hors liste direction"
    assert diag["feature_subset"] == DIRECTIONAL_FEATURES


def test_build_cross_sectional_feature_subset_without_sector_map() -> None:
    universe = _make_universe()
    out, diag = build_cross_sectional_features(
        universe,
        min_universe_size=3,
        feature_subset=DIRECTIONAL_FEATURES,
    )
    cols = [c for c in out.columns if c not in ("symbol", "date")]
    # Sans sector_map, aucune feature sectorielle ne peut être calculée → 0 colonne
    assert len(cols) == 0


# ═══════════════════════════════════════════════════════════════════════════
# 4. predict_global_rank — bug benchmark (parité entraînement/prédiction)
# ═══════════════════════════════════════════════════════════════════════════

def _write_ranking_metadata(tmp_path: Path, *, feature_set: str = "expert", benchmark_symbol: str = "SPY") -> Path:
    meta = {
        "feature_columns": ["momentum_20", "relative_strength_20"],
        "model_name": "lightgbm",
        "horizons": [10],
        "feature_set": feature_set,
        "benchmark_symbol": benchmark_symbol,
        "enable_cross_sectional": False,
        "include_directional_features": False,
        "include_sentiment": False,
        "include_screener_scores": False,
        "include_short_score": False,
        "include_macro_vix": False,
        "include_macro_vxn": False,
        "include_macro_vix3m": False,
        "include_macro_move": False,
        "include_fundamentals": False,
        "include_factors": False,
        "include_macro_regime": False,
        "include_score_components": False,
        "include_volume_features": False,
        "horizon_features": {},
    }
    (tmp_path / "_global_ranking_features.json").write_text(json.dumps(meta), encoding="utf-8")
    return tmp_path


def _make_rank_universe() -> pd.DataFrame:
    rng = np.random.default_rng(1)
    dates = pd.date_range("2023-01-01", periods=40, freq="D")
    parts: list[pd.DataFrame] = []
    for s in ["A", "B", "C"]:
        close = 100.0 + np.cumsum(rng.normal(0, 1, 40))
        parts.append(
            pd.DataFrame(
                {
                    "symbol": s,
                    "date": dates,
                    "open": close * 0.99,
                    "high": close * 1.01,
                    "low": close * 0.98,
                    "close": close,
                    "adj_close": close,
                    "volume": rng.integers(100_000, 500_000, 40),
                }
            )
        )
    return pd.concat(parts, ignore_index=True)


def test_predict_global_rank_loads_benchmark_when_missing(monkeypatch, tmp_path: Path) -> None:
    """Bug parité corrigé : quand benchmark_df=None et feature_set="expert",
    predict_global_rank doit charger le benchmark (relative_strength_* sinon à 0)."""
    artifacts = _write_ranking_metadata(tmp_path)
    universe = _make_rank_universe()

    calls: list[tuple[str, Any, Any]] = []
    bench_df = pd.DataFrame(
        {
            "date": pd.date_range("2022-11-01", periods=100, freq="D"),
            "close": np.linspace(90, 110, 100),
            "adj_close": np.linspace(90, 110, 100),
        }
    )

    def _fake_load_benchmark(engine: Any, symbol: str = "SPY", end_date=None, start_date=None):
        calls.append((symbol, start_date, end_date))
        return bench_df

    def _fake_compute_features(bars_df, *, benchmark_df=None, **kwargs):
        n = len(bars_df)
        out = pd.DataFrame(
            {
                "symbol": bars_df["symbol"],
                "date": pd.to_datetime(bars_df["date"]),
                "momentum_20": np.linspace(-0.1, 0.2, n),
                "relative_strength_20": np.linspace(-0.05, 0.1, n),
            }
        )
        return out

    monkeypatch.setattr(global_ranking, "load_benchmark_bars", _fake_load_benchmark)
    monkeypatch.setattr(global_ranking, "compute_features", _fake_compute_features)

    result = global_ranking.predict_global_rank(universe, artifacts, engine=object())

    # Le benchmark a bien été chargé avec le bon symbole (bug corrigé)
    assert len(calls) == 1
    assert calls[0][0] == "SPY"
    # La fonction a produit un résultat (modèle absent → rank neutre 0.5)
    assert result is not None
    assert "global_rank_10" in result.columns
    assert not result.empty


def test_predict_global_rank_does_not_load_benchmark_if_provided(monkeypatch, tmp_path: Path) -> None:
    artifacts = _write_ranking_metadata(tmp_path)
    universe = _make_rank_universe()

    calls: list[tuple[str, Any, Any]] = []

    def _fake_load_benchmark(engine: Any, symbol: str = "SPY", end_date=None, start_date=None):
        calls.append((symbol, start_date, end_date))
        return pd.DataFrame()

    def _fake_compute_features(bars_df, *, benchmark_df=None, **kwargs):
        n = len(bars_df)
        return pd.DataFrame(
            {
                "symbol": bars_df["symbol"],
                "date": pd.to_datetime(bars_df["date"]),
                "momentum_20": np.linspace(-0.1, 0.2, n),
                "relative_strength_20": np.linspace(-0.05, 0.1, n),
            }
        )

    monkeypatch.setattr(global_ranking, "load_benchmark_bars", _fake_load_benchmark)
    monkeypatch.setattr(global_ranking, "compute_features", _fake_compute_features)

    provided = pd.DataFrame({"date": [pd.Timestamp("2023-01-01")], "close": [100.0]})
    result = global_ranking.predict_global_rank(universe, artifacts, benchmark_df=provided, engine=object())

    # benchmark fourni → pas de rechargement
    assert calls == []
    assert result is not None


def test_predict_global_rank_does_not_load_benchmark_when_not_expert(monkeypatch, tmp_path: Path) -> None:
    """feature_set != expert → pas de benchmark nécessaire (relative_strength_* non demandés)."""
    artifacts = _write_ranking_metadata(tmp_path, feature_set="v1")
    universe = _make_rank_universe()

    calls: list[tuple[str, Any, Any]] = []

    def _fake_load_benchmark(engine: Any, symbol: str = "SPY", end_date=None, start_date=None):
        calls.append((symbol, start_date, end_date))
        return pd.DataFrame()

    def _fake_compute_features(bars_df, *, benchmark_df=None, **kwargs):
        n = len(bars_df)
        return pd.DataFrame(
            {
                "symbol": bars_df["symbol"],
                "date": pd.to_datetime(bars_df["date"]),
                "momentum_20": np.linspace(-0.1, 0.2, n),
            }
        )

    monkeypatch.setattr(global_ranking, "load_benchmark_bars", _fake_load_benchmark)
    monkeypatch.setattr(global_ranking, "compute_features", _fake_compute_features)

    result = global_ranking.predict_global_rank(universe, artifacts, engine=object())

    assert calls == []
    assert result is not None


# ═══════════════════════════════════════════════════════════════════════════
# 5. predictor._prepare_prediction_frame — condition benchmark mode direction
# ═══════════════════════════════════════════════════════════════════════════

def test_prepare_prediction_frame_loads_benchmark_in_directional_mode(monkeypatch) -> None:
    """En mode direction (même feature_set != expert), le benchmark doit être chargé."""
    engine = object()
    cutoff = date(2026, 4, 21)

    benchmark_calls: list[tuple[Any, str, Any]] = []

    def _fake_benchmark_cached(db_engine, symbol: str, cutoff_date=None):
        benchmark_calls.append((db_engine, symbol, cutoff_date))
        return pd.DataFrame(
            {
                "date": [pd.Timestamp("2026-04-20"), pd.Timestamp("2026-04-21")],
                "close": [100.0, 101.0],
                "adj_close": [100.0, 101.0],
            }
        )

    bars = pd.DataFrame(
        {
            "date": pd.date_range("2025-01-01", periods=200, freq="D"),
            "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0,
            "adj_close": 100.0, "volume": 1_000_000,
        }
    )

    data_cfg = DataConfig(
        sequence_length=40,
        feature_set="v1",  # PAS expert → le chargement benchmark ne se fait QUE via le mode direction
        include_directional_features=True,
        benchmark_symbol="SPY",
    )

    monkeypatch.setattr(predictor, "load_symbol_bars", lambda *a, **k: bars.copy())
    monkeypatch.setattr(predictor, "_load_benchmark_bars_cached", _fake_benchmark_cached)
    # compute_features réel trop lourd → mock simple qui conserve les colonnes direction
    monkeypatch.setattr(predictor, "compute_features", lambda *a, **k: pd.DataFrame(
        {
            "date": pd.to_datetime(bars["date"]),
            "momentum_20": 0.01,
            "relative_strength_20": 0.01,
        }
    ))
    # is_filled présent pour éviter une KeyError dans compute_features mocké
    # (le mock retourne un DF sans les colonnes attendues → _prepare_prediction_frame
    #  n'utilise que les colonnes présentes).

    df = predictor._prepare_prediction_frame(
        "AAPL",
        data_cfg=data_cfg,
        engine=engine,
        cutoff_date=cutoff,
    )

    # Le benchmark a bien été chargé (mode direction), même sans feature_set="expert"
    assert len(benchmark_calls) == 1
    assert benchmark_calls[0][1] == "SPY"
    assert df is not None
