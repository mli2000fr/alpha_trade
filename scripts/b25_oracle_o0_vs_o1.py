"""Comparaison O0 vs O1 (Oracle Extreme) par fold — même protocole que S4 WF.

Objectif (retour utilisateur 2026-08-20) :
  - O0 = features B25/expert, SANS global_rank_20  → PAS touché par le stacking leakage
  - O1 = O0 + global_rank_20 (+ extras Oracle)      → touché (2022 partiel, 2025 100%)
  Question : O0 ≈ O1 ?  O1 >> O0 ?  O0 détecte-t-il les extrêmes sans direction ?

On réutilise le dataset E2 déjà construit (326 273 lignes, 181 features expert +
global_rank_20 + cibles + garde) pour éviter de recalculer les features (coûteux).
Le protocole reproduit walk_forward.py : folds expansifs, train = oracle_available_date
< test_start (T2 bloquant), métriques par fold.

Le dataset E2 contient des colonnes en trop (oracle_*, labels) qu'il faut exclure
des features. On reconstruit la liste feature canonique O0 à partir des colonnes
réelles, puis ablation_features() pour O1.

Usage :
    python -m scripts.b25_oracle_o0_vs_o1
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "f:/projets")

from modelFactory.oracle.dataset import (
    GUARD_COL,
    ORACLE_EXTRA_FEATURES,
    TARGET_COL,
    ablation_features,
    expert_feature_columns,
)
from modelFactory.oracle.train import (
    precision_recall_at_top_pct,
    roc_auc,
    train_lightgbm,
)

DATASET = Path("artifacts/models/oracle/e2_feature_dataset.parquet")
TEST_WINDOWS = [
    ("2022-01-01", "2022-12-31"),
    ("2023-01-01", "2023-12-31"),
    ("2024-01-01", "2024-12-31"),
    ("2025-01-01", "2025-12-31"),
    ("2026-01-01", "2026-05-29"),
]

# Colonnes à EXCLURE des features (cibles/labels/garde/identifiants)
_NON_FEATURE = {
    "date", "symbol", TARGET_COL, "future_return",
    "oracle_pct_rank", "oracle_decile", GUARD_COL,
}


def main() -> None:
    df = pd.read_parquet(DATASET)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df[GUARD_COL] = pd.to_datetime(df[GUARD_COL]).dt.normalize()

    # ── Liste feature canonique O0 (expert + xs_ranks présents dans le dataset) ──
    expert = [c for c in expert_feature_columns() if c in df.columns]
    xs = [c for c in df.columns if c.endswith("_xs_rank")]
    feature_columns = expert + xs

    ab_cols = {
        "O0": ablation_features(feature_columns, include_global_rank=False, include_oracle_extras=False),
        "O1": ablation_features(feature_columns, include_global_rank=True, include_oracle_extras=True),
    }
    for name, cols in ab_cols.items():
        cols = [c for c in cols if c in df.columns and c not in _NON_FEATURE]
        ab_cols[name] = cols
        print(f"[{name}] {len(cols)} features | contient global_rank_20: {'global_rank_20' in cols} | extras: {[c for c in ORACLE_EXTRA_FEATURES if c in cols]}")

    results: dict[str, dict] = {}
    for ab in ("O0", "O1"):
        cols = ab_cols[ab]
        per_fold: list[dict] = []
        oos_parts: list[pd.DataFrame] = []
        for t_start, t_end in TEST_WINDOWS:
            train = df[df[GUARD_COL] < pd.Timestamp(t_start)]
            test = df[(df["date"] >= pd.Timestamp(t_start)) & (df["date"] <= pd.Timestamp(t_end))]
            if train.empty or test.empty:
                print(f"  {ab} fold {t_start}: VIDE (train={len(train)} test={len(test)})")
                continue
            y_tr = train[TARGET_COL].astype(int)
            if y_tr.nunique() < 2 or test[TARGET_COL].astype(int).nunique() < 2:
                print(f"  {ab} fold {t_start}: target constant — skipped")
                continue
            X_tr = train[cols].astype(float)
            X_te = test[cols].astype(float)
            model = train_lightgbm(X_tr, y_tr, X_te, test[TARGET_COL].astype(int))
            proba = model.predict(X_te)
            oos = test[["date", "symbol", TARGET_COL, "future_return", "global_rank_20"]].copy()
            oos["proba"] = proba
            oos["fold_start"] = t_start
            oos_parts.append(oos)

            pr = precision_recall_at_top_pct(oos, "proba", target_col=TARGET_COL)
            base_pr = precision_recall_at_top_pct(oos, "global_rank_20", target_col=TARGET_COL)
            prev = float(oos[TARGET_COL].astype(float).mean())
            auc = roc_auc(oos[TARGET_COL].to_numpy(), proba)
            # Capture directionnelle : précision TOP-only et BOTTOM-only dans le top-10% score
            top_only = oos.dropna(subset=["proba"]).copy()
            top_only["is_top"] = (top_only["future_return"] >= top_only.groupby("date")["future_return"].transform(
                lambda s: s.rank(pct=True) >= 0.90))
            bot_only = oos.dropna(subset=["proba"]).copy()
            bot_only["is_bot"] = (bot_only["future_return"] <= bot_only.groupby("date")["future_return"].transform(
                lambda s: s.rank(pct=True) <= 0.10))
            n_top = max(1, int(np.ceil(len(oos) / len(oos["date"].unique()) * 0.10)) * len(oos["date"].unique()) // 1)
            # precision top-10% intra-date du score → proportion de vrais top / vrais bottom
            g = oos.groupby("date")
            oos["_rk"] = oos.groupby("date")["proba"].rank(pct=True)
            band = oos[oos["_rk"] >= 0.90]
            top_band_frac = float((band["future_return"] >= band.groupby("date")["future_return"].transform(
                lambda s: s.rank(pct=True) >= 0.90)).mean())
            bot_band_frac = float((band["future_return"] <= band.groupby("date")["future_return"].transform(
                lambda s: s.rank(pct=True) <= 0.10)).mean())

            per_fold.append({
                "fold": t_start, "n_train": len(train), "n_test": len(test),
                "prev": prev,
                "prec10": pr["precision"], "recall10": pr["recall"],
                "base_prec10": base_pr["precision"],
                "auc": auc,
                "top_frac_in_band": top_band_frac,
                "bot_frac_in_band": bot_band_frac,
            })
            print(f"  {ab} fold {t_start}: prec10={pr['precision']:.3f} (base {base_pr['precision']:.3f}) "
                  f"AUC={auc:.3f} prev={prev:.3f} top_band={top_band_frac:.3f} bot_band={bot_band_frac:.3f}")
        if oos_parts:
            oos = pd.concat(oos_parts, ignore_index=True)
            pr_all = precision_recall_at_top_pct(oos, "proba", target_col=TARGET_COL)
            base_all = precision_recall_at_top_pct(oos, "global_rank_20", target_col=TARGET_COL)
            auc_all = roc_auc(oos[TARGET_COL].to_numpy(), oos["proba"].to_numpy())
            n_beat = sum(1 for f in per_fold if f["prec10"] is not None and f["base_prec10"] is not None
                         and f["prec10"] > f["base_prec10"])
            results[ab] = {
                "per_fold": per_fold,
                "overall_prec10": pr_all["precision"],
                "overall_base_prec10": base_all["precision"],
                "overall_auc": auc_all,
                "fold_stability_pct": 100.0 * n_beat / len(per_fold) if per_fold else None,
                "n_folds": len(per_fold),
            }

    # ── Rapport côte à côte ──
    print("\n=== O0 vs O1 — côte à côte (par fold) ===")
    header = (f"{'fold':<12}{'O0 prec10':>10}{'O1 prec10':>10}{'base':>8}{'O0 AUC':>8}{'O1 AUC':>8}"
              f"{'O0 top':>8}{'O1 top':>8}{'O0 bot':>8}{'O1 bot':>8}")
    print(header)
    print("-" * len(header))
    for i, f0 in enumerate(results["O0"]["per_fold"]):
        f1 = results["O1"]["per_fold"][i]
        print(f"{f0['fold']:<12}{f0['prec10'] or 0:>10.3f}{f1['prec10'] or 0:>10.3f}"
              f"{f0['base_prec10'] or 0:>8.3f}{f0['auc'] or 0:>8.3f}{f1['auc'] or 0:>8.3f}"
              f"{f0['top_frac_in_band'] or 0:>8.3f}{f1['top_frac_in_band'] or 0:>8.3f}"
              f"{f0['bot_frac_in_band'] or 0:>8.3f}{f1['bot_frac_in_band'] or 0:>8.3f}")
    print("-" * len(header))
    o0, o1 = results["O0"], results["O1"]
    print(f"{'OVERALL':<12}{o0['overall_prec10'] or 0:>10.3f}{o1['overall_prec10'] or 0:>10.3f}"
          f"{o0['overall_base_prec10'] or 0:>8.3f}{o0['overall_auc'] or 0:>8.3f}{o1['overall_auc'] or 0:>8.3f}")
    print(f"\nfold_stability (bat B25) : O0={o0['fold_stability_pct']:.1f}%  O1={o1['fold_stability_pct']:.1f}%")
    d = (o1["overall_prec10"] or 0) - (o0["overall_prec10"] or 0)
    verdict = "O0 = O1 : le rank B25 n'apporte rien" if abs(d) < 0.01 else (
        "O1 >> O0 : rank utile (a requalifier en OOF)" if d > 0 else "O0 > O1")
    print(f"delta prec10 (O1 - O0) = {d:+.3f} pts -> {verdict}")


if __name__ == "__main__":
    main()
