"""Courbe Precision/Recall du modèle Oracle Extreme à 5/10/15/20 % (TOP k% par date).

Répond à : « le vrai intérêt d'Oracle Extreme est-il le TOP5 plutôt que le TOP10 ? »

Méthode (par date, puis moyenné) :
- Trie les titres du jour par score (proba_extreme ou global_rank_20 baseline).
- Prend le TOP k% de l'univers du jour (5/10/15/20).
- precision@k = fraction du TOP k% qui sont oracle_extreme10=1.
- recall@k   = vrais extrêmes capturés / total extrêmes du jour.
- Comparé à la prévalence (~20%) et à la baseline B25.

Aucun seuil de P&L : c'est une courbe ML pure, sans décision de trading.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

RUN = Path("artifacts/models/oracle/oracle-wf-20260819034014/oos_predictions.parquet")
K_VALUES = [0.05, 0.10, 0.15, 0.20]
SCORES = [("Oracle Extreme", "proba_extreme"), ("B25 (global_rank_20)", "global_rank_20")]


def pr_curve_by_date(df: pd.DataFrame, score_col: str, target_col: str, k: float) -> dict:
    precs, recs = [], []
    for _, g in df.groupby("date"):
        g = g.dropna(subset=[score_col, target_col])
        if len(g) < 20:
            continue
        n_top = max(1, int(np.ceil(len(g) * k)))
        top = g.nlargest(n_top, score_col)
        n_ext = int(g[target_col].sum())
        precs.append(float(top[target_col].mean()))
        recs.append(float(top[target_col].sum() / n_ext) if n_ext > 0 else np.nan)
    return {
        "precision": float(np.mean(precs)) if precs else np.nan,
        "recall": float(np.nanmean(recs)) if recs else np.nan,
        "n_dates": int(len(precs)),
    }


def report_for(df: pd.DataFrame, label: str) -> list[str]:
    lines = [f"\n=== {label} ==="]
    hdr = f"{'TOP k%':>7} {'precision@k':>12} {'recall@k':>10} {'lift_vs_prev':>13}"
    lines.append(hdr)
    prev = df["oracle_extreme10"].mean()
    for score_name, score_col in SCORES:
        lines.append(f"  [{score_name}]")
        for k in K_VALUES:
            r = pr_curve_by_date(df, score_col, "oracle_extreme10", k)
            lift = r["precision"] / prev if prev else np.nan
            lines.append(
                f"  {k*100:>5.0f}%  {r['precision']*100:>11.1f}%  {r['recall']*100:>9.1f}%  {lift:>12.2f}x"
            )
    return lines


def main() -> None:
    df = pd.read_parquet(RUN)
    print(f"run: {RUN.name} | {len(df):,} lignes | prévalence overall = {df['oracle_extreme10'].mean()*100:.1f}%")

    # ── OVERALL (concat des folds, comme le rapport WF) ──
    lines = report_for(df, "OVERALL (2022-2026H1)")
    print("\n".join(lines))

    # ── Par fold ──
    for f, g in df.groupby("fold_start"):
        prev = g["oracle_extreme10"].mean()
        print("---------------------------------------------")
        print(f"FOLD {f} (N={len(g):,}, prev={prev*100:.1f}%)")
        sub = report_for(g, "")
        print("\n".join(sub[1:]))

    # ── Synthèse compacte : precision@k par fold (Oracle) ──
    print("\n\n=== SYNTHESE precision@k Oracle Extreme par fold ===")
    print(f"{'fold':<12} " + " ".join(f"P@{int(k*100):>3}" for k in K_VALUES))
    for f, g in df.groupby("fold_start"):
        vals = []
        for k in K_VALUES:
            r = pr_curve_by_date(g, "proba_extreme", "oracle_extreme10", k)
            vals.append(f"{r['precision']*100:5.1f}")
        print(f"{str(f):<12} " + " ".join(f"{v:>6}" for v in vals))
    # overall
    vals = []
    for k in K_VALUES:
        r = pr_curve_by_date(df, "proba_extreme", "oracle_extreme10", k)
        vals.append(f"{r['precision']*100:5.1f}")
    print(f"{'OVERALL':<12} " + " ".join(f"{v:>6}" for v in vals))


if __name__ == "__main__":
    main()
