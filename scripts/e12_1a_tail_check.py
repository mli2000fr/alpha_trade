"""E12-1A (suite) — Economie du filtre NO-TRADE a plusieurs quantiles.

Lit artifacts/models/oracle/e12_1a_truebad.parquet (replay PROD deja fait).
Pour chaque feature : filtre sur le quantile du bas (q=25/15/10/5/2.5%) -> 
  - % TRUE_BAD retires ; pertes TRUE_BAD evitees (sum ret, %) ;
  - gains WINNER perdus (sum ret, %) ; ratio$ = |TB evit| / WIN perdu ;
  - NET = TB_evit + WIN_lost (sum ret, en %) : si NET > 0 le filtre est rentable.
Zero optimisation : on regarde simplement si UNE feature permet un filtre rentable
a UN seuil ; c'est le test du gate user ("sans supprimer trop de TP gagnants").
"""
from __future__ import annotations

import sys
sys.path.insert(0, "f:/projets")

from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path("artifacts/models/oracle/e12_1a_truebad.parquet")
QS = (0.25, 0.15, 0.10, 0.05, 0.025)
FEATS = ["proba_extreme", "atr_pct_20", "sym_r5", "sym_r10", "sym_r21",
         "dist_sma20", "dist_sma50", "spy_r21", "spy_vol21", "rsp_r21", "iwm_r21",
         "breadth_up21", "breadth_sma20", "xs_disp21", "mkt_atr"]


def main() -> None:
    t = pd.read_parquet(OUT)
    y = t["TRUE_BAD"].astype(int)
    print(f"n={len(t):,} | TRUE_BAD={y.sum():,} ({100*y.mean():.1f}%) | "
          f"WINNER={int(t['WINNER'].sum()):,} | MOVED_LOSER={int(t['MOVED_LOSER'].sum()):,}")
    tot_tb = float(t.loc[y == 1, "ret"].sum())
    tot_win = float(t.loc[t["WINNER"], "ret"].sum())
    print(f"total TRUE_BAD sum ret = {100*tot_tb:.0f}% | total WINNER sum ret = {100*tot_win:.0f}%")

    print("\n" + "=" * 118)
    print("MEILLEUR ratio$ (|TB evit|/WIN perdu) par feature + NET vrai associe")
    print("=" * 118)
    print("  NET vrai = |TB_evit| - WIN_perdu (en sum ret %) : >0 = filtre rentable")
    print(f"  {'feature':<14} {'bestQ':>6} {'bestRatio':>9} {'TBevit%':>9} {'WINperdu%':>9} "
          f"{'NET%':>8} {'%TB_rem':>8}")
    best_rows = []
    for f in FEATS:
        sub = t[[f, "TRUE_BAD", "ret", "WINNER"]].dropna()
        if len(sub) < 500 or sub["TRUE_BAD"].nunique() < 2:
            continue
        yy = sub["TRUE_BAD"].astype(int)
        x = sub[f]
        med_tb = float(x[yy == 1].median())
        med_win = float(x[yy == 0].median())
        sign = -1.0 if med_tb < med_win else 1.0
        xs = x * sign
        best = None
        for q in QS:
            th = xs.quantile(q)
            sel = xs <= th
            tb_evit = float(sub[sel & yy.astype(bool)]["ret"].sum())
            win_lost = float(sub[sel & sub["WINNER"]]["ret"].sum())
            if abs(win_lost) < 1e-9:
                continue
            ratio = abs(tb_evit / win_lost)
            net = -tb_evit - win_lost      # NET vrai = |TB evit| - WIN perdu
            tb_rem = 100 * (sel & yy.astype(bool)).sum() / max(len(yy[yy == 1]), 1)
            if best is None or net > best[4]:
                best = (ratio, q, tb_evit, win_lost, net, tb_rem)
        if best is None:
            continue
        ratio, q, tb_evit, win_lost, net, tb_rem = best
        best_rows.append((f, q, ratio, tb_evit, win_lost, net, tb_rem))
        print(f"  {f:<14} {100*q:>5.0f}% {ratio:>9.2f} {100*tb_evit:>9.0f} {100*win_lost:>9.0f} "
              f"{100*net:>8.0f} {tb_rem:>7.0f}%")

    print("\n" + "=" * 118)
    print("MEILLEUR NET VRAI (sum ret %) par feature : un NET > 0 = filtre rentable")
    print("=" * 118)
    net_rows = []
    for f in FEATS:
        sub = t[[f, "TRUE_BAD", "ret", "WINNER"]].dropna()
        if len(sub) < 500 or sub["TRUE_BAD"].nunique() < 2:
            continue
        yy = sub["TRUE_BAD"].astype(int)
        x = sub[f]
        med_tb = float(x[yy == 1].median())
        med_win = float(x[yy == 0].median())
        sign = -1.0 if med_tb < med_win else 1.0
        xs = x * sign
        bnet = None
        for q in QS:
            th = xs.quantile(q)
            sel = xs <= th
            tb_evit = float(sub[sel & yy.astype(bool)]["ret"].sum())
            win_lost = float(sub[sel & sub["WINNER"]]["ret"].sum())
            net = -tb_evit - win_lost
            if bnet is None or net > bnet[1]:
                bnet = (100 * q, net)
        net_rows.append((f, bnet[0], bnet[1]))
        print(f"  {f:<14} bestQ={bnet[0]:>4.0f}% NET={100*bnet[1]:>9.0f}% ret")

    print("\n" + "=" * 118)
    print("LECTURE")
    print("=" * 118)
    max_ratio = max((r[2] for r in best_rows), default=0.0)
    max_net = max((r[5] for r in best_rows), default=-1e18)
    print(f"  meilleur ratio$ = {max_ratio:.2f} (il faut > ~1.0 pour etre rentable en net)")
    print(f"  meilleur NET vrai = {100*max_net:.0f}% (il faut > 0)")
    if max_ratio < 1.0 and max_net < 0:
        print("  -> AUCUNE feature ne permet un filtre NO-TRADE rentable a aucun seuil.")
        print("  -> Le cluster TRUE_BAD (~20%, tous semestres) n'est pas separable a l'entree")
        print("     avec ces features PIT. Gate user NON satisfait -> fermer E12-1A.")


if __name__ == "__main__":
    main()
