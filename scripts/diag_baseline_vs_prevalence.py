"""Diagnostic : baseline vs prévalence du label oracle_extreme10 par fold.

Répond à la question : le 0.336 du rapport WF est-il la prévalence ?
Non — c'est la précision@10% du rang global_rank_20 (B25) sur la cible extreme.
Ici on affiche : N, N extreme, prévalence, precision@10 Oracle, precision@10 B25,
et la construction du label (vérification ~20%/date).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

RUN = Path("artifacts/models/oracle/oracle-wf-20260819034014/oos_predictions.parquet")
PCT = 0.10


def precision_at_top_pct(df: pd.DataFrame, score_col: str, target_col: str) -> float:
    rows = []
    for _, g in df.groupby("date"):
        g = g.dropna(subset=[score_col, target_col])
        if len(g) < 20:
            continue
        n_top = max(1, int(np.ceil(len(g) * PCT)))
        top = g.nlargest(n_top, score_col)
        rows.append(float(top[target_col].mean()))
    return float(np.mean(rows)) if rows else float("nan")


def main() -> None:
    df = pd.read_parquet(RUN)
    df["fold"] = df["fold_start"]
    print(f"cols: {list(df.columns)}")
    print(f"total: {len(df):,} | extreme=1: {int(df['oracle_extreme10'].sum()):,} "
          f"({df['oracle_extreme10'].mean()*100:.1f}%)")

    print("\n=== Par fold ===")
    print(f"{'fold':<12}{'N':>9}{'N_ext':>8}{'prev%':>7}{'prec@10 Oracle':>15}"
          f"{'prec@10 B25':>12}{'N dates':>8}")
    for f, g in df.groupby("fold"):
        prev = g["oracle_extreme10"].mean() * 100
        p_or = precision_at_top_pct(g, "proba_extreme", "oracle_extreme10") * 100
        p_b25 = precision_at_top_pct(g, "global_rank_20", "oracle_extreme10") * 100
        n_dates = g["date"].nunique()
        print(f"{str(f):<12}{len(g):>9,}{int(g['oracle_extreme10'].sum()):>8,}"
              f"{prev:>7.1f}{p_or:>15.1f}{p_b25:>12.1f}{n_dates:>8}")

    # OVERALL
    prev = df["oracle_extreme10"].mean() * 100
    p_or = precision_at_top_pct(df, "proba_extreme", "oracle_extreme10") * 100
    p_b25 = precision_at_top_pct(df, "global_rank_20", "oracle_extreme10") * 100
    print(f"\nOVERALL : prévalence={prev:.1f}%  prec@10 Oracle={p_or:.1f}%  prec@10 B25={p_b25:.1f}%")
    print(f"Lift vs prévalence : Oracle {p_or/prev:.2f}x | B25 {p_b25/prev:.2f}x")
    print(f"Lift Oracle vs B25 : {p_or/p_b25:.2f}x")

    # Vérification construction du label : prévalence PAR DATE
    per_date = df.groupby("date")["oracle_extreme10"].mean()
    print(f"\n=== Prévalence par date (construction du label) ===")
    print(f"n_dates={len(per_date)} | mean={per_date.mean()*100:.1f}% | min={per_date.min()*100:.1f}% "
          f"| max={per_date.max()*100:.1f}%")
    # distribution des tailles d'univers par date
    sizes = df.groupby("date").size()
    print(f"univers par date : median={sizes.median():.0f} min={sizes.min()} max={sizes.max()}")
    # échantillon de dates
    sample = df[df["date"].isin(df["date"].unique()[:3])]
    print("\nExemple 3 dates (univers complet du fold 2022) :")
    for d, g in sample.groupby("date"):
        print(f"  {d.date()}: N={len(g)}  extreme={int(g['oracle_extreme10'].sum())} "
              f"({g['oracle_extreme10'].mean()*100:.1f}%)")


if __name__ == "__main__":
    main()
