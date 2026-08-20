"""E6 — Table de lift Y3-LONG sur le pool extrême O0 (pré-E6-B).

Réutilise EXACTEMENT le pipeline E6 (mêmes folds, mêmes features O0, mêmes modèles
CatBoost/LightGBM via e6_direction_diagnostic) mais collecte les probabilités OOS
par ligne pour construire :
  - taux succès LONG par décile de P(long_success) (CatBoost & LightGBM)
  - precision@5/10/20% (cross-sectionnel par date, moyenné)
  - recall correspondant
  - calibration observée vs prédite (bins de proba)
Le but : vérifier si le top décile dépasse la prévalence de base (0.176) d'un
facteur suffisant (cible 25-30%+) avant de lancer E6-B.

Sortie : print + artifacts/models/oracle/e6_y3_lift.parquet
"""
from __future__ import annotations

import sys
sys.path.insert(0, "f:/projets")

from pathlib import Path

import numpy as np
import pandas as pd

from scripts.e6_direction_diagnostic import (  # réutilisation stricte du pipeline
    FOLDS,
    GUARD_COL,
    MODELS,
    _fit_predict,
    merge_pools,
    roc_auc,
)

OUT = Path("artifacts/models/oracle/e6_y3_lift.parquet")


def collect_oos_probas(df: pd.DataFrame, feature_columns: list[str], target: str) -> pd.DataFrame:
    """Réplique run_wf pour collecter (date, symbol, y, proba) OOS par fold."""
    parts: list[pd.DataFrame] = []
    for t_start, t_end in FOLDS:
        train = df[df[GUARD_COL] < pd.Timestamp(t_start)]
        test = df[(df["date"] >= pd.Timestamp(t_start)) & (df["date"] <= pd.Timestamp(t_end))]
        if len(train) < 100 or len(test) < 50:
            continue
        y_tr = train[target].astype(int)
        y_te = test[target].astype(int)
        if y_tr.nunique() < 2 or y_te.nunique() < 2:
            continue
        X_tr = train[feature_columns].astype(float)
        X_te = test[feature_columns].astype(float)
        test = test.copy()
        for m in MODELS:
            _, proba = _fit_predict(m, X_tr, y_tr, X_te, y_te)
            test[f"_proba_{m}"] = proba
        parts.append(test[["date", "symbol", target, "_proba_catboost", "_proba_lightgbm"]])
    if not parts:
        raise SystemExit("aucun fold collecté")
    return pd.concat(parts, ignore_index=True)


def decile_table(oos: pd.DataFrame, target: str) -> pd.DataFrame:
    """Taux succès LONG par décile de proba (CatBoost & LightGBM)."""
    rows = []
    for m in MODELS:
        col = f"_proba_{m}"
        d = oos[[target, col]].dropna().copy()
        if d.empty:
            continue
        d["decile"] = pd.qcut(d[col], 10, labels=False, duplicates="drop") + 1
        for dec in sorted(d["decile"].unique()):
            sub = d[d["decile"] == dec]
            rows.append({
                "model": m, "decile": int(dec), "n": len(sub),
                "prev": float(sub[target].mean()),
                "proba_min": float(sub[col].min()),
                "proba_mean": float(sub[col].mean()),
                "proba_max": float(sub[col].max()),
            })
    return pd.DataFrame(rows)


def precision_at_top_pct(oos: pd.DataFrame, target: str) -> pd.DataFrame:
    """precision@5/10/20% cross-sectionnel par date (top pct de proba intra-date)."""
    rows = []
    for m in MODELS:
        col = f"_proba_{m}"
        d = oos[[ "date", target, col]].dropna().copy()
        d["_rk"] = d.groupby("date")[col].rank(pct=True)
        for pct in (0.05, 0.10, 0.20):
            top = d[d["_rk"] >= 1.0 - pct]
            if top.empty:
                continue
            # moyenné par date d'abord (évite le biais des jours à + de lignes)
            per_day = top.groupby("date")[target].mean()
            rows.append({
                "model": m, "top_pct": pct,
                "precision": float(per_day.mean()),
                "n_rows": len(top),
                "n_dates": len(per_day),
            })
    return pd.DataFrame(rows)


def calibration_table(oos: pd.DataFrame, target: str) -> pd.DataFrame:
    """Calibration observée vs prédite par bin de proba (CatBoost & LightGBM)."""
    rows = []
    for m in MODELS:
        col = f"_proba_{m}"
        d = oos[[target, col]].dropna().copy()
        if d.empty:
            continue
        bins = np.arange(0.0, 1.0001, 0.10)
        d["bin"] = pd.cut(d[col], bins=bins, include_lowest=True)
        for b, sub in d.groupby("bin", observed=True):
            rows.append({
                "model": m,
                "bin": f"{b.left:.2f}-{b.right:.2f}",
                "n": len(sub),
                "pred_mean": float(sub[col].mean()),
                "obs_mean": float(sub[target].mean()),
            })
    return pd.DataFrame(rows)


def main() -> None:
    df, feature_columns = merge_pools()
    pool = df[df["extreme_pool"]].copy()
    pool_y3 = pool.dropna(subset=["y3_long"]).copy()
    print(f"pool extrême O0 pour Y3-LONG : {len(pool_y3):,} lignes | features O0: {len(feature_columns)}")
    print(f"prévalence base y3_long (pool extrême) : {pool_y3['y3_long'].mean():.4f}")

    oos = collect_oos_probas(pool_y3, feature_columns, "y3_long")
    print(f"OOS collecté : {len(oos):,} lignes")
    for m in MODELS:
        print(f"  [{m}] AUC OOS y3_long = {roc_auc(oos['y3_long'].astype(int).to_numpy(), oos[f'_proba_{m}'].to_numpy()):.4f}")

    print("\n=== DÉCILES P(long_success) → taux succès LONG ===")
    dec = decile_table(oos, "y3_long")
    for m in MODELS:
        sub = dec[dec["model"] == m].sort_values("decile")
        print(f"\n  {m.upper()}:")
        print(f"    {'dec':>4} {'n':>7} {'succ%':>8} {'proba_min':>10} {'proba_mean':>11} {'proba_max':>10}")
        for r in sub.itertuples():
            print(f"    {r.decile:>4} {r.n:>7} {100*r.prev:>7.2f}% {r.proba_min:>10.4f} {r.proba_mean:>11.4f} {r.proba_max:>10.4f}")
    d10_cb = dec[(dec["model"] == "catboost") & (dec["decile"] == dec[dec["model"] == "catboost"]["decile"].max())]
    if not d10_cb.empty:
        base = pool_y3["y3_long"].mean()
        print(f"\n  TOP décile CatBoost : {100*d10_cb['prev'].iloc[0]:.1f}% vs base {100*base:.1f}% "
              f"(lift {d10_cb['prev'].iloc[0]/base:.2f}x)")

    print("\n=== PRECISION@5/10/20% (cross-sectionnel par date) ===")
    prec = precision_at_top_pct(oos, "y3_long")
    for r in prec.itertuples():
        print(f"  {r.model:<10} top {int(r.top_pct*100):>2}% : precision = {100*r.precision:.2f}% "
              f"(n={r.n_rows:,}, {r.n_dates} dates)")
    base = pool_y3["y3_long"].mean()
    for r in prec.itertuples():
        if r.model == "catboost":
            print(f"    → lift vs base ({100*base:.1f}%) : {r.precision/base:.2f}x")

    print("\n=== CALIBRATION (pred vs obs) ===")
    cal = calibration_table(oos, "y3_long")
    for m in MODELS:
        sub = cal[cal["model"] == m]
        print(f"\n  {m.upper()}:")
        for r in sub.itertuples():
            print(f"    bin {r.bin:<11} n={r.n:>6} pred={100*r.pred_mean:5.1f}% obs={100*r.obs_mean:5.1f}%")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    oos.to_parquet(OUT, index=False)
    print(f"\npersisted: {OUT}")


if __name__ == "__main__":
    main()
