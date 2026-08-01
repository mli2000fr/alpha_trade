"""diagnose_feature_ic.py — Diagnostic du signal dans les features brutes.

Mesure l'IC cross-sectionnel (Spearman) de chaque feature vs le forward return
à chaque horizon, par secteur, et par régime de marché.

Usage:
    python diagnose_feature_ic.py [--symbols N] [--horizons 10,15,20]
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# ── Setup ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
LOGGER = logging.getLogger("diagnose_feature_ic")

# Ajouter le projet au path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from database.connection import get_sqlalchemy_engine
from modelFactory.config import TrainingConfig
from modelFactory.data_loader import (
    load_benchmark_bars,
    load_universe_bars,
    load_universe_latest_bar_date,
    resolve_training_start_date,
)
from modelFactory.global_ranking import (
    _GLOBAL_RANKING_HORIZONS,
    _get_ranking_feature_columns,
    _prepare_global_ranking_frame,
    _compute_sector_neutral_inplace,
    _XS_RANK_SOURCE_FEATURES,
    _xs_rank_column_name,
)
from modelFactory.cross_sectional import (
    build_cross_sectional_features,
    merge_cross_sectional_features,
    SECTOR_NEUTRAL_FEATURE_COLUMNS,
    _load_sector_mapping,
)
from modelFactory.features import get_feature_columns


def compute_cross_sectional_ic(
    df: pd.DataFrame,
    score_col: str,
    return_col: str,
    *,
    date_col: str = "date",
    min_symbols_per_date: int = 10,
) -> dict:
    """IC Rank (Spearman) cross-sectionnel par date pour une feature."""
    import warnings
    from scipy.stats import spearmanr

    _df = df.dropna(subset=[score_col, return_col])
    if _df.empty or len(_df[date_col].unique()) < 5:
        return {"ic_mean": None, "ic_std": None, "n_dates": 0, "ic_positive_pct": None}

    ics: list[float] = []
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=UserWarning, message=".*constant.*")
        for _date, _group in _df.groupby(date_col):
            if len(_group) < min_symbols_per_date:
                continue
            try:
                corr, _ = spearmanr(_group[score_col], _group[return_col])
                if not np.isnan(corr):
                    ics.append(float(corr))
            except Exception:
                pass

    if not ics:
        return {"ic_mean": None, "ic_std": None, "n_dates": 0, "ic_positive_pct": None}

    return {
        "ic_mean": float(np.mean(ics)),
        "ic_std": float(np.std(ics)) if len(ics) > 1 else 0.0,
        "ic_ir": float(np.mean(ics)) / float(np.std(ics)) if len(ics) > 1 and np.std(ics) > 0 else float("nan"),
        "n_dates": len(ics),
        "ic_positive_pct": sum(1 for ic in ics if ic > 0) / len(ics),
    }


def diagnose_features(
    symbols: list[str],
    cfg: TrainingConfig,
    engine,
    *,
    horizons: tuple[int, ...] = (10, 15, 20),
) -> dict:
    """Diagnostique l'IC de chaque feature vs le forward return à chaque horizon."""

    # ── Chargement des données (réplique de train_global_ranking_wf) ──
    history_end_date = load_universe_latest_bar_date(
        engine, symbols, end_date=cfg.data.training_end_date,
    )
    history_start_date = resolve_training_start_date(
        history_end_date, cfg.data.training_start_date,
    )
    universe_df = load_universe_bars(
        engine, symbols, end_date=history_end_date, start_date=history_start_date,
    )
    if universe_df.empty:
        LOGGER.error("Empty universe")
        return {}

    # Limiter aux top N par volume
    _max_sym = cfg.data.global_ranking_max_symbols
    if _max_sym > 0 and len(symbols) > _max_sym:
        _vol_rank = universe_df.groupby("symbol")["volume"].mean().sort_values(ascending=False)
        symbols = _vol_rank.head(_max_sym).index.tolist()

    benchmark_df = None
    if cfg.data.feature_set == "expert":
        benchmark_df = load_benchmark_bars(
            engine, cfg.data.benchmark_symbol,
            end_date=history_end_date, start_date=history_start_date,
        )

    cross_sectional_df = None
    if cfg.data.enable_cross_sectional_features:
        cross_sectional_df, _ = build_cross_sectional_features(
            universe_df, benchmark_df=benchmark_df,
            min_universe_size=cfg.data.cross_sectional_min_universe,
        )

    # ── Feature columns ──
    feature_columns = _get_ranking_feature_columns(cfg)
    LOGGER.info("Diagnosing %d features on %d symbols, horizons=%s",
                len(feature_columns), len(symbols), horizons)

    # ── Build pooled dataframe ──
    _base_parts: list[pd.DataFrame] = []
    for symbol in symbols:
        bars_df = universe_df[universe_df["symbol"] == symbol].sort_values("date").reset_index(drop=True)
        if len(bars_df) < cfg.data.min_history_days:
            continue
        sym_cross = None
        if cross_sectional_df is not None and not cross_sectional_df.empty:
            sym_cross = cross_sectional_df[cross_sectional_df["symbol"] == symbol].copy()

        prepared = _prepare_global_ranking_frame(
            bars_df, cfg,
            benchmark_df=benchmark_df,
            sentiment_df=None,
            selector_df=None,
            cross_sectional_df=sym_cross,
            symbol=symbol,
        )
        if prepared.empty:
            continue
        prepared["symbol"] = symbol
        _f64 = [c for c in prepared.columns if prepared[c].dtype == np.float64]
        if _f64:
            prepared[_f64] = prepared[_f64].astype(np.float32)
        _base_parts.append(prepared)
        del bars_df, sym_cross, prepared

    if not _base_parts:
        LOGGER.error("No prepared data")
        return {}

    base_df = pd.concat(_base_parts, ignore_index=True).sort_values(["date", "symbol"]).reset_index(drop=True)
    del _base_parts

    # ── XS ranks ──
    _xs_available = [s for s in _XS_RANK_SOURCE_FEATURES if s in base_df.columns]
    if _xs_available:
        _xs_ranked = base_df.groupby("date")[_xs_available].rank(pct=True).astype(np.float64)
        _xs_ranked.columns = [_xs_rank_column_name(c) for c in _xs_available]
        for _col in _xs_ranked.columns:
            base_df[_col] = _xs_ranked[_col]

    # ── Sector-neutral ──
    _sn_cols_in = [c for c in SECTOR_NEUTRAL_FEATURE_COLUMNS if c in feature_columns]
    if _sn_cols_in and cfg.data.enable_cross_sectional_features:
        _compute_sector_neutral_inplace(base_df, feature_columns, engine)

    base_df = base_df.dropna(subset=feature_columns).reset_index(drop=True)

    # ── Load sector mapping for diagnosis ──
    sector_map: dict[str, str] = {}
    try:
        sector_map = _load_sector_mapping(engine) or {}
    except Exception:
        pass
    if sector_map:
        base_df["_sector"] = base_df["symbol"].astype(str).str.upper().map(sector_map)
    else:
        base_df["_sector"] = "unknown"

    # ── Forward returns et vol scaling (réplique exacte du training) ──
    for horizon in horizons:
        h_suffix = f"_{horizon}"
        _fwd_close = base_df.groupby("symbol")["close"].shift(-horizon)
        base_df[f"future_return{h_suffix}"] = (_fwd_close / base_df["close"] - 1.0)
        if horizon >= 5:
            _vol20 = base_df["rolling_volatility_20"].clip(lower=0.001)
            base_df[f"future_return{h_suffix}"] = (
                base_df[f"future_return{h_suffix}"] / _vol20
            ).astype(float)

    LOGGER.info("Pooled dataframe: %d rows, %d symbols, %d features",
                len(base_df), base_df["symbol"].nunique(), len(feature_columns))

    # ── Diagnostiquer chaque feature ──
    results: dict[str, dict] = {}

    for horizon in horizons:
        h_suffix = f"_{horizon}"
        return_col = f"future_return{h_suffix}"
        h_results: dict[str, dict] = {}
        LOGGER.info("─" * 60)
        LOGGER.info("Horizon H=%d — diagnosing %d features...", horizon, len(feature_columns))

        for feat in feature_columns:
            if feat not in base_df.columns:
                continue
            diag = compute_cross_sectional_ic(base_df, feat, return_col)
            if diag["ic_mean"] is not None:
                h_results[feat] = diag

        # Trier par |IC mean| décroissant
        h_sorted = sorted(h_results.items(), key=lambda kv: abs(kv[1]["ic_mean"]), reverse=True)
        results[str(horizon)] = {
            "top20": [(f, d) for f, d in h_sorted[:20]],
            "bottom20": [(f, d) for f, d in h_sorted[-20:]],
            "all": {f: d for f, d in h_sorted},
        }

        # ── Top 20 ──
        LOGGER.info("Top 20 features by |IC| for H=%d:", horizon)
        for feat, diag in h_sorted[:20]:
            LOGGER.info(
                "  %-45s IC=%-+.4f  σ=%.4f  IR=%-+.2f  pos=%.0f%%  n=%d",
                feat, diag["ic_mean"], diag["ic_std"],
                diag.get("ic_ir", float("nan")),
                diag.get("ic_positive_pct", 0) * 100,
                diag["n_dates"],
            )

        # ── IC par secteur (top 20 features seulement, pour la vitesse) ──
        LOGGER.info("─" * 40)
        LOGGER.info("IC by sector for H=%d (top sectors, using top 20 features):", horizon)
        _top20_feats = [f for f, _ in h_sorted[:20]]
        sector_ics: dict[str, list[float]] = {}
        _valid = base_df.dropna(subset=[return_col])
        for _sector, _group in _valid.groupby("_sector"):
            if len(_group) < 500 or _sector == "unknown":
                continue
            _sector_ics: list[float] = []
            for feat in _top20_feats:
                if feat not in _group.columns:
                    continue
                _d = compute_cross_sectional_ic(_group, feat, return_col)
                if _d["ic_mean"] is not None:
                    _sector_ics.append(abs(_d["ic_mean"]))
            if _sector_ics:
                sector_ics[_sector] = _sector_ics

        _top_sectors = sorted(sector_ics.items(), key=lambda kv: np.mean(kv[1]), reverse=True)[:10]
        for _sec, _ics in _top_sectors:
            LOGGER.info("  %-30s mean|IC|=%.4f  n_features=%d", _sec, np.mean(_ics), len(_ics))

        # ── IC par régime (top 20 features seulement) ──
        if "regime_bull_market" in base_df.columns and "regime_risk_off" in base_df.columns:
            LOGGER.info("─" * 40)
            LOGGER.info("IC by regime for H=%d (using top 20 features):", horizon)
            for _regime_name, _regime_mask in [
                ("bull", base_df["regime_bull_market"] > 0.5),
                ("bear", (base_df["regime_bull_market"] < 0.5) & (base_df["regime_risk_off"] < 0.5)),
                ("risk_off", base_df["regime_risk_off"] > 0.5),
            ]:
                _regime_df = _valid[_regime_mask]
                if len(_regime_df) < 1000:
                    continue
                _regime_ics: list[float] = []
                for feat in _top20_feats:
                    if feat not in _regime_df.columns:
                        continue
                    _d = compute_cross_sectional_ic(_regime_df, feat, return_col)
                    if _d["ic_mean"] is not None:
                        _regime_ics.append(abs(_d["ic_mean"]))
                if _regime_ics:
                    LOGGER.info("  %-12s mean|IC|=%.4f  n_rows=%d",
                                _regime_name, np.mean(_regime_ics), len(_regime_df))

        # ── Résumé du signal ──
        LOGGER.info("─" * 40)
        _all_abs_ic = [abs(v["ic_mean"]) for v in h_results.values()]
        _ic_gt_002 = sum(1 for v in h_results.values() if abs(v["ic_mean"]) > 0.02)
        _ic_gt_005 = sum(1 for v in h_results.values() if abs(v["ic_mean"]) > 0.05)
        _ic_gt_010 = sum(1 for v in h_results.values() if abs(v["ic_mean"]) > 0.10)
        LOGGER.info(
            "H=%d SIGNAL SUMMARY: mean|IC|=%.4f  |IC|>0.02: %d/%d  |IC|>0.05: %d  |IC|>0.10: %d",
            horizon, np.mean(_all_abs_ic), _ic_gt_002, len(h_results),
            _ic_gt_005, _ic_gt_010,
        )

    return results


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Diagnose feature IC for Global Ranking")
    parser.add_argument("--symbols", type=int, default=100,
                        help="Max symbols to load (default: 100, for speed)")
    parser.add_argument("--horizons", type=str, default="10,15,20",
                        help="Horizons to diagnose (comma-separated)")
    parser.add_argument("--top-k", type=int, default=20,
                        help="Number of top/bottom features to report")
    args = parser.parse_args()

    horizons = tuple(int(h.strip()) for h in args.horizons.split(","))

    # ── Construire une TrainingConfig minimale ──
    from modelFactory.config import (
        BaselineConfig, CalibrationConfig, ChampionSelectionConfig,
        DataConfig, GlobalModelConfig, ModelConfig, ReproducibilityConfig,
        ThresholdOptimizationConfig, TargetOptimizationConfig, TrainingConfig,
        WalkForwardConfig,
    )

    cfg = TrainingConfig(
        data=DataConfig(
            feature_set="expert",
            forecast_horizon=10,
            enable_cross_sectional_features=True,
            include_fundamentals_features=True,
            include_factors_features=True,
            include_macro_regime_features=True,
            include_macro_vix_features=True,
            include_macro_vxn_features=True,
            include_macro_vix3m_features=True,
            include_macro_move_features=True,
            global_ranking_max_symbols=args.symbols,
        ),
        baseline=BaselineConfig(),
        global_model=GlobalModelConfig(enabled=True, model_name="lightgbm"),
        walk_forward=WalkForwardConfig(enabled=True),
        reproducibility=ReproducibilityConfig(),
        calibration=CalibrationConfig(),
        champion_selection=ChampionSelectionConfig(),
        threshold_optimization=ThresholdOptimizationConfig(),
        target_optimization=TargetOptimizationConfig(),
        model=ModelConfig(),
    )

    engine = get_sqlalchemy_engine()

    # ── Charger les symboles ──
    import pandas as _pd
    symbols_df = _pd.read_sql(
        "SELECT DISTINCT symbol FROM stock_bars_daily "
        "WHERE date >= '2020-01-01' "
        "ORDER BY symbol LIMIT 500",
        engine,
    )
    symbols = symbols_df["symbol"].tolist()

    LOGGER.info("Loaded %d symbols, will diagnose up to %d", len(symbols), args.symbols)

    results = diagnose_features(symbols, cfg, engine, horizons=horizons)

    # ── Sauvegarder ──
    out_path = Path("artifacts/diagnostics/feature_ic_diagnosis.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Convertir en dict simple pour JSON
    serializable = {}
    for h, hdata in results.items():
        serializable[h] = {
            "top20": [(f, d) for f, d in hdata["top20"]],
            "bottom20": [(f, d) for f, d in hdata["bottom20"]],
            "summary": {
                "n_features_with_ic": len(hdata["all"]),
                "mean_abs_ic": float(np.mean([abs(v["ic_mean"]) for v in hdata["all"].values()])),
                "features_ic_gt_002": sum(1 for v in hdata["all"].values() if abs(v["ic_mean"]) > 0.02),
                "features_ic_gt_005": sum(1 for v in hdata["all"].values() if abs(v["ic_mean"]) > 0.05),
            },
        }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=2, default=str)
    LOGGER.info("Results saved to %s", out_path)


if __name__ == "__main__":
    main()
