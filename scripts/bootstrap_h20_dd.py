"""Bootstrap H20 risk : distribution du max drawdown sur plusieurs années.

Source : equity curve quotidienne du run H20 risk (ihm2526_p14_h20risk,
2025-01 → 2026-05, 352 rendements journaliers).

Méthode : block bootstrap (bloc = 20 jours ouvrés, préserve l'autocorrélation)
pour simuler des trajectoires de N années, puis mesurer le max drawdown de
chaque trajectoire → P(DD > 10/15/20%).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

RUN_DIR = Path(r"F:\projets\artifacts\backtesting\ihm2526_p14_h20risk")
OUT = sys.stdout
RNG = np.random.default_rng(20260817)

TRADING_DAYS_PER_YEAR = 250
BLOCK_LEN = 20
N_ITER = 5000


def p(msg: str = "") -> None:
    print(msg, file=OUT)


def max_drawdown_pct(equity: np.ndarray) -> float:
    peak = np.maximum.accumulate(equity)
    dd = (equity - peak) / peak
    return float(-dd.min() * 100.0)


def block_bootstrap(returns: np.ndarray, n_days: int, block_len: int) -> np.ndarray:
    """Reconstruit une trajectoire de n_days rendements par blocs aléatoires."""
    n = len(returns)
    starts = np.arange(0, n - block_len + 1)
    out: list[float] = []
    while len(out) < n_days:
        s = int(RNG.choice(starts))
        out.extend(returns[s:s + block_len].tolist())
    return np.asarray(out[:n_days])


def run(returns: np.ndarray, n_years: int, label: str) -> dict[str, float]:
    n_days = int(n_years * TRADING_DAYS_PER_YEAR)
    rets_path = np.empty(N_ITER)
    dd_path = np.empty(N_ITER)
    for i in range(N_ITER):
        block_ret = block_bootstrap(returns, n_days, BLOCK_LEN)
        # trajectoire d'équité normalisée (compound)
        equity = np.cumprod(1.0 + block_ret)
        rets_path[i] = float((equity[-1] - 1.0) * 100.0)
        dd_path[i] = max_drawdown_pct(equity)
    stats = {
        "n_years": n_years,
        "ret_mean": float(np.mean(rets_path)),
        "ret_ci_lo": float(np.percentile(rets_path, 2.5)),
        "ret_ci_hi": float(np.percentile(rets_path, 97.5)),
        "dd_mean": float(np.mean(dd_path)),
        "dd_median": float(np.median(dd_path)),
        "dd_ci_hi": float(np.percentile(dd_path, 97.5)),
        "dd_p99": float(np.percentile(dd_path, 99.0)),
        "p_dd_gt_10": float(np.mean(dd_path > 10.0) * 100.0),
        "p_dd_gt_15": float(np.mean(dd_path > 15.0) * 100.0),
        "p_dd_gt_20": float(np.mean(dd_path > 20.0) * 100.0),
    }
    p(f"=== {label} : trajectoires de {n_years} an(s) ({n_days} jours ouvrés, {N_ITER} itérations) ===")
    p(f"  Rendement : moyenne {stats['ret_mean']:+.1f}%  IC95 [{stats['ret_ci_lo']:+.1f}%, {stats['ret_ci_hi']:+.1f}%]")
    p(f"  Max DD    : moyenne {stats['dd_mean']:.1f}% | médiane {stats['dd_median']:.1f}% | "
      f"IC95 haut {stats['dd_ci_hi']:.1f}% | p99 {stats['dd_p99']:.1f}%")
    p(f"  P(DD > 10%) : {stats['p_dd_gt_10']:.1f}%")
    p(f"  P(DD > 15%) : {stats['p_dd_gt_15']:.1f}%")
    p(f"  P(DD > 20%) : {stats['p_dd_gt_20']:.1f}%")
    p("")
    return stats


def main() -> None:
    ec = pd.read_csv(RUN_DIR / "equity_curve.csv")
    ec["trade_date"] = pd.to_datetime(ec["trade_date"])
    ec = ec.sort_values("trade_date")
    equity = ec["portfolio_value"].to_numpy(dtype=float)
    returns = np.diff(equity) / equity[:-1]
    p(f"Rendements journaliers H20 risk chargés : {len(returns)} "
      f"(du {ec['trade_date'].iloc[0].date()} au {ec['trade_date'].iloc[-1].date()})")
    p(f"Rendement cumulé observé : {(equity[-1]/equity[0]-1)*100:+.1f}%")
    p(f"Max DD observé (17 mois) : {max_drawdown_pct(equity):.1f}%\n")

    run(returns, n_years=1, label="H20 risk — 1 an")
    run(returns, n_years=2, label="H20 risk — 2 ans")
    run(returns, n_years=3, label="H20 risk — 3 ans")
    run(returns, n_years=4, label="H20 risk — 4 ans")


if __name__ == "__main__":
    main()
