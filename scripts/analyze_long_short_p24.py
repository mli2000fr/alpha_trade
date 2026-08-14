"""P2-4 — Diagnostic side-spécifique : pourquoi les longs sous-performent ?

Analyse la jambe LONG vs SHORT du backtest control propre `b25_p23_control`
(B25, 5+5 bps, 2019-01→2024-06, 386 trades) à partir de trades.csv.

Produit :
1. Stats par jambe : n, win-rate, PnL total/moyen, payoff, holding days
2. Distribution des rangs sélectionnés par jambe (le long = top ranks ?)
3. PnL par jambe × secteur (top/bottom)
4. PnL par jambe × année d'entrée
5. Stats de return_pct par jambe (moyenne/médiane/écart-type)

Usage : python scripts/analyze_long_short_p24.py
"""
import os
import sys

sys.path.insert(0, r"F:\projets")

import numpy as np
import pandas as pd

RUN_DIR = r"F:\projets\artifacts\backtesting\b25_p23_control"
TRADES_CSV = os.path.join(RUN_DIR, "trades.csv")
OUT_CSV = r"F:\projets\artifacts\metrics\p24_long_short_trades.csv"


def _side_of(t: pd.DataFrame) -> pd.Series:
    return np.where(t["side"].astype(str).str.lower().isin(["buy", "long"]), "LONG", "SHORT")


def _fmt_pnl(v: float) -> str:
    return f"{v:+,.1f}"


def main() -> None:
    trades = pd.read_csv(TRADES_CSV)
    trades["pnl"] = pd.to_numeric(trades["pnl"], errors="coerce")
    trades["return_pct"] = pd.to_numeric(trades["return_pct"], errors="coerce")
    trades["holding_days"] = pd.to_numeric(trades["holding_days"], errors="coerce")
    trades["selection_rank"] = pd.to_numeric(trades["selection_rank"], errors="coerce")
    trades["predicted_proba"] = pd.to_numeric(trades["predicted_proba"], errors="coerce")
    trades["side_b"] = _side_of(trades)
    trades["entry_year"] = pd.to_datetime(trades["entry_date"], utc=False).dt.year

    print(f"trades.csv : {len(trades)} lignes")
    print(f"PnL total control : {_fmt_pnl(trades['pnl'].sum())}")

    # ── 1. Stats par jambe ──
    print("\n" + "=" * 78)
    print("1. STATS PAR JAMBE (LONG vs SHORT)")
    print("=" * 78)
    rows = []
    for side in ["LONG", "SHORT"]:
        t = trades[trades["side_b"] == side]
        wins = t[t["pnl"] > 0]
        losses = t[t["pnl"] <= 0]
        avg_win = wins["pnl"].mean() if len(wins) else np.nan
        avg_loss = losses["pnl"].mean() if len(losses) else np.nan
        payoff = (avg_win / abs(avg_loss)) if avg_loss and not np.isnan(avg_loss) else np.nan
        r = {
            "side": side,
            "n": len(t),
            "win_rate_pct": 100.0 * len(wins) / len(t),
            "pnl_total": t["pnl"].sum(),
            "pnl_mean": t["pnl"].mean(),
            "pnl_median": t["pnl"].median(),
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "payoff": payoff,
            "ret_mean_pct": t["return_pct"].mean(),
            "ret_median_pct": t["return_pct"].median(),
            "ret_std_pct": t["return_pct"].std(),
            "holding_days_mean": t["holding_days"].mean(),
            "predicted_proba_mean": t["predicted_proba"].mean(),
            "selection_rank_mean": t["selection_rank"].mean(),
        }
        rows.append(r)
        print(
            f"{side:5s} n={r['n']:3d} win={r['win_rate_pct']:5.1f}%  "
            f"PnL={_fmt_pnl(r['pnl_total'])}  moy={_fmt_pnl(r['pnl_mean'])}  "
            f"payoff={payoff:.2f}  ret_moy={r['ret_mean_pct']:+.2f}%  "
            f"hold={r['holding_days_mean']:5.2f}j  proba_moy={r['predicted_proba_mean']:.3f}  "
            f"sel_rank_moy={r['selection_rank_mean']:.1f}"
        )
    sides_df = pd.DataFrame(rows)
    sides_df.to_csv(OUT_CSV, index=False)
    print(f"\n→ {OUT_CSV}")

    # ── 2. Distribution des rangs sélectionnés par jambe ──
    print("\n" + "=" * 78)
    print("2. RANG DE SÉLECTION PAR JAMBE (1 = meilleur score du jour)")
    print("=" * 78)
    for side in ["LONG", "SHORT"]:
        t = trades[trades["side_b"] == side]
        print(f"\n{side} :")
        print(
            t.groupby("selection_rank")
            .agg(n=("pnl", "size"), pnl=("pnl", "sum"), win=("pnl", lambda s: 100.0 * (s > 0).mean()))
            .to_string()
        )

    # ── 3. PnL par jambe × secteur ──
    print("\n" + "=" * 78)
    print("3. PNL PAR JAMBE × SECTEUR")
    print("=" * 78)
    pivot = (
        trades.pivot_table(index="sector", columns="side_b", values="pnl", aggfunc=["sum", "count"], fill_value=0)
        .sort_values(("sum", "LONG"))
    )
    print(pivot.to_string())

    # ── 4. PnL par jambe × année ──
    print("\n" + "=" * 78)
    print("4. PNL PAR JAMBE × ANNÉE D'ENTRÉE")
    print("=" * 78)
    pivot_y = (
        trades.pivot_table(index="entry_year", columns="side_b", values="pnl", aggfunc=["sum", "count"], fill_value=0)
    )
    print(pivot_y.to_string())

    # ── 5. Distribution return_pct par jambe ──
    print("\n" + "=" * 78)
    print("5. DISTRIBUTION return_pct PAR JAMBE")
    print("=" * 78)
    for side in ["LONG", "SHORT"]:
        t = trades[trades["side_b"] == side]
        q = t["return_pct"].quantile([0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0])
        print(f"{side} : " + "  ".join(f"q{qx:.2f}={q[qx]:+.2f}%" for qx in q.index))


if __name__ == "__main__":
    main()
