"""P2-4 (suite) — mécanique de sortie des trades par jambe.

Le signal long est horizon H10+ (IC −0.011 sur H10, positif seulement au-delà),
mais les trades longs sortent en ~5j via trailing stop. Vérifie :
1. exit_reason par jambe (trailing_stop vs take_profit vs stop_loss)
2. PnL par jambe × bucket de holding_days
3. Les longs qui tiennent >10j gagnent-ils ?
"""
import os
import sys

sys.path.insert(0, r"F:\projets")

import numpy as np
import pandas as pd

TRADES_CSV = r"F:\projets\artifacts\backtesting\b25_p23_control\trades.csv"


def main() -> None:
    t = pd.read_csv(TRADES_CSV)
    t["pnl"] = pd.to_numeric(t["pnl"], errors="coerce")
    t["holding_days"] = pd.to_numeric(t["holding_days"], errors="coerce")
    t["side_b"] = np.where(t["side"].astype(str).str.lower().isin(["buy", "long"]), "LONG", "SHORT")

    print("=" * 78)
    print("1. EXIT_REASON PAR JAMBE")
    print("=" * 78)
    print(
        t.pivot_table(index="exit_reason", columns="side_b", values="pnl",
                      aggfunc=["count", "sum", "mean"]).round(1).to_string()
    )

    print("\n" + "=" * 78)
    print("2. PNL PAR JAMBE × BUCKET HOLDING_DAYS")
    print("=" * 78)
    t["hold_bucket"] = pd.cut(t["holding_days"], bins=[0, 3, 5, 8, 12, 20, 100],
                              labels=["0-3j", "3-5j", "5-8j", "8-12j", "12-20j", "20j+"])
    print(
        t.pivot_table(index="hold_bucket", columns="side_b", values="pnl",
                      aggfunc=["count", "sum", "mean"]).round(1).to_string()
    )

    print("\n" + "=" * 78)
    print("3. WIN-RATE PAR JAMBE × BUCKET HOLDING_DAYS")
    print("=" * 78)
    print(
        (t.pivot_table(index="hold_bucket", columns="side_b", values="pnl",
                       aggfunc=lambda s: 100.0 * (s > 0).mean())).round(1).to_string()
    )

    print("\n" + "=" * 78)
    print("4. PNL PAR JAMBE × EXIT_REASON × BUCKET (top)")
    print("=" * 78)
    for side in ["LONG", "SHORT"]:
        s = t[t["side_b"] == side]
        g = s.groupby(["exit_reason", "hold_bucket"]).agg(n=("pnl", "size"), pnl=("pnl", "sum"),
                                                          win=("pnl", lambda x: 100.0 * (x > 0).mean()))
        print(f"\n{side} :")
        print(g.round(1).to_string())


if __name__ == "__main__":
    main()
