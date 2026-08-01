"""diagnose_ic_by_sector_regime.py — IC cross-sectionnel par secteur et régime.

Mesure l'IC Rank du forward return vol-scalé, segmenté par secteur GICS
et par régime de marché (bull/bear/risk_off). Utilise les données déjà
poolées du Global Ranking.

Usage rapide (depuis un notebook ou python -c) :
    python scripts/diagnose_ic_by_sector_regime.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOGGER = logging.getLogger("diag_sector")

from database.connection import get_sqlalchemy_engine
from modelFactory.config import (
    BaselineConfig, CalibrationConfig, ChampionSelectionConfig,
    DataConfig, GlobalModelConfig, ModelConfig, ReproducibilityConfig,
    ThresholdOptimizationConfig, TargetOptimizationConfig, TrainingConfig,
    WalkForwardConfig,
)
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
    compute_ic_rank,
)
from modelFactory.cross_sectional import (
    build_cross_sectional_features,
    _load_sector_mapping,
)

# ── Config ──────────────────────────────────────────────────────────
cfg = TrainingConfig(
    data=DataConfig(
        feature_set="expert",
        forecast_horizon=10,
        enable_cross_sectional_features=True,
        include_fundamentals_features=True,
        include_factors_features=True,
        include_macro_regime_features=True,
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

# ── Charger symboles depuis config/ticket_mid_cap.txt ─────────────
_ticket_path = _PROJECT_ROOT / "config" / "ticket_mid_cap.txt"
_ticket_raw = _ticket_path.read_text(encoding="utf-8").strip()
_all_mid_cap = [s.strip() for s in _ticket_raw.split(",") if s.strip()]
symbols = _all_mid_cap[:100]  # top 100 pour la vitesse
LOGGER.info("Loaded %d symbols from %s", len(symbols), _ticket_path)

# ── Charger données ─────────────────────────────────────────────────
history_end_date = load_universe_latest_bar_date(engine, symbols, end_date=None)
history_start_date = resolve_training_start_date(history_end_date, None)
universe_df = load_universe_bars(engine, symbols, end_date=history_end_date, start_date=history_start_date)

benchmark_df = load_benchmark_bars(
    engine, "SPY", end_date=history_end_date, start_date=history_start_date,
)

cross_sectional_df, _ = build_cross_sectional_features(
    universe_df, benchmark_df=benchmark_df, min_universe_size=20,
)

# ── Sector mapping ──────────────────────────────────────────────────
sector_map = _load_sector_mapping(engine) or {}
LOGGER.info("Sector map: %d symbols → %d sectors", len(sector_map), len(set(sector_map.values())))

# ── Pooled dataframe (light: juste close, vol20, forward return) ───
parts: list[pd.DataFrame] = []
for symbol in symbols:  # déjà limité à 100
    bars_df = universe_df[universe_df["symbol"] == symbol].sort_values("date").reset_index(drop=True)
    if len(bars_df) < 504:
        continue
    sym_cross = cross_sectional_df[cross_sectional_df["symbol"] == symbol].copy() if cross_sectional_df is not None else None
    prepared = _prepare_global_ranking_frame(
        bars_df, cfg, benchmark_df=benchmark_df, sentiment_df=None,
        selector_df=None, cross_sectional_df=sym_cross, symbol=symbol,
    )
    if prepared.empty:
        continue
    prepared["symbol"] = symbol
    prepared["_sector"] = prepared["symbol"].astype(str).str.upper().map(sector_map).fillna("Unknown")
    # Garder les colonnes nécessaires pour le diagnostic
    _keep = ["symbol", "date", "close", "rolling_volatility_20", "momentum_60",
             "_sector", "regime_bull_market", "regime_risk_off", "volume"]
    _keep = [c for c in _keep if c in prepared.columns]
    parts.append(prepared[_keep])

df = pd.concat(parts, ignore_index=True).sort_values(["date", "symbol"]).reset_index(drop=True)
LOGGER.info("Pooled: %d rows, %d symbols, %d sectors",
            len(df), df["symbol"].nunique(), df["_sector"].nunique())

# ── Forward returns + vol scaling ──────────────────────────────────
for h in (10, 15, 20):
    fwd = df.groupby("symbol")["close"].shift(-h)
    df[f"ret_{h}"] = (fwd / df["close"] - 1.0)
    vol20 = df["rolling_volatility_20"].clip(lower=0.001)
    df[f"ret_{h}_scaled"] = df[f"ret_{h}"] / vol20

# ── Régime flags ───────────────────────────────────────────────────
df["regime"] = "bear"
df.loc[df["regime_bull_market"] > 0.5, "regime"] = "bull"
df.loc[df["regime_risk_off"] > 0.5, "regime"] = "risk_off"

# ── IC par secteur ─────────────────────────────────────────────────
print("\n" + "=" * 70)
print("IC RANK par SECTEUR (Spearman, cross-sectionnel intra-date)")
print("=" * 70)

for h in (10, 15, 20):
    print(f"\n── H={h} ──")
    ret_col = f"ret_{h}_scaled"
    valid = df.dropna(subset=[ret_col])
    results: list[tuple[str, float, float, int]] = []
    for sector, group in valid.groupby("_sector"):
        if len(group) < 2000 or sector == "Unknown":
            continue
        # IC intra-date par secteur
        ics = []
        for date, dg in group.groupby("date"):
            if len(dg) < 5:
                continue
            ic = compute_ic_rank(
                dg["rolling_volatility_20"].values,  # proxy: vol20 rank vs ret
                dg[ret_col].values,
            )
            if ic is not None:
                ics.append(ic)
        if len(ics) < 20:
            continue
        # Pour cet IC, on utilise momentum_60 comme feature de ranking
        if "momentum_60" not in group.columns:
            continue
        ics_mom = []
        for date, dg in group.groupby("date"):
            if len(dg) < 5:
                continue
            ic = compute_ic_rank(dg["momentum_60"].values, dg[ret_col].values)
            if ic is not None:
                ics_mom.append(ic)
        if ics_mom:
            results.append((sector, np.mean(ics_mom), np.std(ics_mom), len(group)))

    results.sort(key=lambda x: abs(x[1]), reverse=True)
    for sec, ic_mean, ic_std, n in results[:15]:
        print(f"  {sec:<35s} IC={ic_mean:+.4f}  σ={ic_std:.3f}  n={n:,}")

# ── IC par régime ──────────────────────────────────────────────────
print("\n" + "=" * 70)
print("IC RANK par RÉGIME (momentum_60 vs forward return)")
print("=" * 70)

for h in (10, 15, 20):
    print(f"\n── H={h} ──")
    ret_col = f"ret_{h}_scaled"
    valid = df.dropna(subset=[ret_col])
    for regime in ["bull", "bear", "risk_off"]:
        rdf = valid[valid["regime"] == regime]
        if len(rdf) < 5000:
            continue
        ics = []
        for date, dg in rdf.groupby("date"):
            if len(dg) < 5:
                continue
            ic = compute_ic_rank(dg["momentum_60"].values, dg[ret_col].values)
            if ic is not None:
                ics.append(ic)
        if ics:
            pos_pct = sum(1 for ic in ics if ic > 0) / len(ics)
            print(f"  {regime:<10s} IC={np.mean(ics):+.4f}  σ={np.std(ics):.3f}  "
                  f"pos={pos_pct:.0%}  n_dates={len(ics)}  n_rows={len(rdf):,}")

# ── IC par market cap (proxy: prix × volume) ──────────────────────
print("\n" + "=" * 70)
print("IC RANK par TAILLE (quintiles de market cap)")
print("=" * 70)

df["_dollar_vol"] = df["close"] * df.get("volume", 1)
def _assign_size_quintile(grp: pd.Series) -> pd.Series:
    try:
        bins = pd.qcut(grp, 5, labels=False, duplicates="drop")
        # Map numeric bins 0..N to labels
        label_map = {0: "micro", 1: "small", 2: "mid", 3: "large", 4: "mega"}
        return pd.Series(bins.map(label_map).fillna("mid"), index=grp.index)
    except Exception:
        return pd.Series("mid", index=grp.index)

df["_size_quintile"] = df.groupby("date")["_dollar_vol"].transform(_assign_size_quintile)

for h in (10, 15, 20):
    print(f"\n── H={h} ──")
    ret_col = f"ret_{h}_scaled"
    valid = df.dropna(subset=[ret_col, "_size_quintile"])
    for size in ["micro", "small", "mid", "large", "mega"]:
        sdf = valid[valid["_size_quintile"] == size]
        if len(sdf) < 5000:
            continue
        ics = []
        for date, dg in sdf.groupby("date"):
            if len(dg) < 5:
                continue
            ic = compute_ic_rank(dg["momentum_60"].values, dg[ret_col].values)
            if ic is not None:
                ics.append(ic)
        if ics:
            pos_pct = sum(1 for ic in ics if ic > 0) / len(ics)
            print(f"  {size:<8s} IC={np.mean(ics):+.4f}  σ={np.std(ics):.3f}  "
                  f"pos={pos_pct:.0%}  n_dates={len(ics)}")

print("\nDone.")
