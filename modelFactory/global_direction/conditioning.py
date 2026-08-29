"""modelFactory/global_direction/conditioning.py — Diagnostic de conditionnement.

Question : l'Oracle Extreme (gate TOP20/TOP10) **détruit-il** un signal
directionnel qui existerait sur un univers plus large, ou **aucun signal**
n'existe-t-il déjà dans l'univers complet ?

Pour 4 profondeurs d'univers, on mesure la séparabilité des 12 features de base
(statiques à J, PIT) :
- **univers complet** (pool_pct=1.0)
- **Oracle TOP50** (pool_pct=0.50)
- **Oracle TOP20** (pool_pct=0.20, le gate de production)
- **Oracle TOP10** (pool_pct=0.10)

Pour chaque (profondeur, feature) :
- ``ic_mean_folds`` / ``ic_std_folds`` : IC Spearman vs décile, par fold WF ;
- ``auc_bad5_good5`` : AUC(D1-D5 vs D6-D10) ; ``auc_d1_d10`` : AUC(D1 vs D10) ;
- ``top_decile_lift`` : rendement futur moyen du top décile CROSS-SECTIONNEL du
  jour (par feature) − rendement moyen global ;
- ``top_decile_good5_frac`` : fraction de D6-D10 dans le top décile ;
- ``bad5_mean`` / ``good5_mean`` : rendement futur moyen des D1-D5 / D6-D10 ;
- ``stable_folds`` / ``total_folds`` : stabilité du SIGNE de l'IC par fold ;
- ``coverage`` : fraction de lignes avec valeur.

Sortie : ``artifacts/conditioning_direction_separability.csv``.

Usage :
    python -m modelFactory.global_direction.conditioning --batch-id ...
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from database.connection import get_sqlalchemy_engine
from modelFactory.directional_data_research.harness import assemble_pool
from modelFactory.global_direction.config import resolve_global_direction_batch_id
from modelFactory.global_direction.dataset import DECILE_COL, RETURN_COL
from modelFactory.global_direction.temporal import BASE_FEATURES, build_panel
from modelFactory.oracle.train import roc_auc

LOGGER = logging.getLogger(__name__)

DEPTHS = [1.00, 0.50, 0.20, 0.10]


def _ic_spearman(series: pd.Series, decile: pd.Series) -> float | None:
    s = series.astype(float)
    if s.nunique() < 2 or decile.nunique() < 2:
        return None
    try:
        c = s.corr(decile, method="spearman")
        return float(c) if np.isfinite(c) else None
    except Exception:
        return None


def _auc(series: pd.Series, decile: pd.Series, good: tuple = (6, 10), bad: tuple = (1, 5)) -> float | None:
    mask = decile.isin([*bad, *good])
    if mask.sum() < 2:
        return None
    y = np.where(decile[mask].isin(good), 1.0, 0.0)
    s = series[mask].astype(float).to_numpy()
    return roc_auc(y, s)


def _top_decile_stats(sub: pd.DataFrame, feature: str) -> dict[str, float | None]:
    """Top décile cross-sectionnel PAR DATE (le rang se fait le jour même)."""
    sub = sub.dropna(subset=[feature, RETURN_COL])
    if len(sub) < 20:
        return {"top_decile_lift": None, "top_decile_good5_frac": None}
    sub = sub.copy()
    sub["_rank"] = sub.groupby("date")[feature].rank(pct=True, ascending=True)
    top = sub[sub["_rank"] >= 0.9]
    overall_mean = float(sub[RETURN_COL].mean())
    top_mean = float(top[RETURN_COL].mean())
    dec = sub[DECILE_COL]
    top_dec = top[DECILE_COL]
    good5 = float((top_dec >= 6).mean()) if len(top_dec) else None
    return {
        "top_decile_lift": top_mean - overall_mean,
        "top_decile_good5_frac": good5,
    }


def measure_depth(
    pool: pd.DataFrame,
    panel: pd.DataFrame,
    base_features: list[str],
) -> pd.DataFrame:
    """Séparabilité de chaque feature de base à une profondeur d'univers donnée."""
    merged = pool.merge(panel[["date", "symbol"] + base_features], on=["date", "symbol"], how="left")
    merged = merged.drop_duplicates(subset=["date", "symbol"])
    dec = merged[DECILE_COL].astype(int)
    rows: list[dict[str, Any]] = []
    for f in base_features:
        if f not in merged.columns:
            continue
        s = merged[f]
        # IC par fold
        fold_ics: list[float] = []
        for fold, g in merged.groupby("fold_start"):
            ic = _ic_spearman(g[f], g[DECILE_COL].astype(int))
            if ic is not None:
                fold_ics.append(ic)
        overall_ic = _ic_spearman(s, dec)
        auc_d = _auc(s, dec)
        auc_10 = _auc(s, dec, good=(10,), bad=(1,))
        sub = merged.dropna(subset=[f, RETURN_COL])
        bad5 = sub.loc[sub[DECILE_COL].isin([1, 2, 3, 4, 5]), RETURN_COL]
        good5 = sub.loc[sub[DECILE_COL].isin([6, 7, 8, 9, 10]), RETURN_COL]
        ts = _top_decile_stats(merged, f)
        stable = 0
        total = 0
        if overall_ic is not None:
            for ic in fold_ics:
                total += 1
                if (ic > 0) == (overall_ic > 0):
                    stable += 1
        rows.append({
            "feature": f,
            "ic_mean_folds": float(np.mean(fold_ics)) if fold_ics else None,
            "ic_std_folds": float(np.std(fold_ics)) if fold_ics else None,
            "auc_bad5_good5": auc_d,
            "auc_d1_d10": auc_10,
            "top_decile_lift": ts["top_decile_lift"],
            "top_decile_good5_frac": ts["top_decile_good5_frac"],
            "bad5_mean": float(bad5.mean()) if len(bad5) else None,
            "good5_mean": float(good5.mean()) if len(good5) else None,
            "bad5_good5_ratio": (float(good5.mean() - bad5.mean()) if len(bad5) and len(good5) else None),
            "stable_folds": stable,
            "total_folds": total,
            "coverage": float(s.notna().mean()),
        })
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnostic de conditionnement (profondeurs d'univers).")
    parser.add_argument("--batch-id", default=None)
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2026-05-29")
    parser.add_argument("--out", default="artifacts/conditioning_direction_separability.csv")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    batch_id = args.batch_id or resolve_global_direction_batch_id()
    if not batch_id:
        raise SystemExit("Aucun batch_id résolu.")
    engine = get_sqlalchemy_engine()

    # Univers complet (pool_pct=1.0) : tous les symboles + labels
    pool_full = assemble_pool(engine, batch_id, start_date=args.start_date, end_date=args.end_date,
                              pool_pct=1.00)
    if pool_full.empty:
        raise SystemExit("Univers complet vide.")
    symbols = sorted(pool_full["symbol"].unique())
    LOGGER.info("univers complet : %d lignes, %d symboles", len(pool_full), len(symbols))

    # Panel de base (12 features, sans dérivées) sur l'univers complet
    panel, _tcols, meta = build_panel(engine, symbols, args.start_date, args.end_date,
                                      with_derivations=False)
    base_avail = meta["base_available"]
    LOGGER.info("features de base : %s", base_avail)
    if not base_avail:
        raise SystemExit("Aucune feature de base.")

    parts: list[pd.DataFrame] = []
    for depth in DEPTHS:
        pool = assemble_pool(engine, batch_id, start_date=args.start_date, end_date=args.end_date,
                             pool_pct=depth)
        label = "full" if depth == 1.0 else f"top{int(depth * 100)}"
        LOGGER.info("profondeur %s : %d lignes, %d symboles", label, len(pool), pool["symbol"].nunique())
        m = measure_depth(pool, panel, base_avail)
        m.insert(0, "depth", label)
        m.insert(1, "pool_pct", depth)
        m.insert(2, "n_rows", len(pool))
        parts.append(m)

    out = pd.concat(parts, ignore_index=True)
    out.to_csv(args.out, index=False)
    print(f"→ CSV : {args.out} ({len(out)} lignes)")

    # Rapport : par feature, comparaison full → top10
    print("\n=== CONDITIONNEMENT : IC moyen par fold / AUC / lift par profondeur ===")
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", None)
    for f in base_avail:
        sub = out[out["feature"] == f]
        print(f"\n-- {f} --")
        sys.stdout.buffer.write(sub[["depth", "ic_mean_folds", "auc_bad5_good5", "top_decile_lift",
                                     "top_decile_good5_frac", "bad5_mean", "good5_mean",
                                     "stable_folds", "total_folds", "coverage"]]
                                .to_string(index=False).encode("utf-8", errors="replace"))


if __name__ == "__main__":
    main()
