# -*- coding: utf-8 -*-
"""Test 4 (2026-08-17) — Bootstrap / Monte-Carlo de la distribution de trades B25 (m8).

Question centrale : avec la distribution de trades que B25 produit, quelle est la
probabilité que le compte réel subisse un DD > 15 % ? Et un DD > 10 % ?

Pile gelée (m8) sur 4 années distinctes (2022/2024/2025/2026), runs production-parity :
- 2022 : cmp_b25_h20_2022_prodparity_p23_m8
- 2024 : cmp_b25_h20_2024_prodparity_p24_m8
- 2025 : cmp_b25_h20_2025_prodparity_p23_m8
- 2026 : cmp_b25_h20_2026_prodparity_repro_h20cfg_m8  (= benchmark archivé)

Méthodes :
A) Stationary bootstrap des rendements journaliers (equity_curve) — capture le vrai
   max drawdown intra-année. N=5000.
B) Bootstrap des trades (resampling avec remise + réordonnancement) — contribution
   = return_pct × (entry_cost/equity). N=5000.
C) Pool combiné : tous les trades des 4 ans mélangés (= échantillon multi-régimes).

Sortie : logs/bootstrap_m8_report.txt
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "logs" / "bootstrap_m8_report.txt"
N_ITER = 5000
RNG = np.random.default_rng(42)

RUNS = {
    "2022": "cmp_b25_h20_2022_prodparity_p23_m8",
    "2024": "cmp_b25_h20_2024_prodparity_p24_m8",
    "2025": "cmp_b25_h20_2025_prodparity_p23_m8",
    "2026": "cmp_b25_h20_2026_prodparity_repro_h20cfg_m8",
}


def _fmt(x: float, nd: int = 2) -> str:
    return f"{x:,.{nd}f}"


def _pct(x: float) -> str:
    return f"{x*100:.2f}%"


def _max_dd(equity: np.ndarray) -> float:
    peak = np.maximum.accumulate(equity)
    return float(np.max(1.0 - equity / peak)) if len(equity) else 0.0


def _stats(arr: np.ndarray) -> dict:
    return {
        "mean": float(arr.mean()),
        "p5": float(np.percentile(arr, 5)),
        "p25": float(np.percentile(arr, 25)),
        "p50": float(np.percentile(arr, 50)),
        "p75": float(np.percentile(arr, 75)),
        "p95": float(np.percentile(arr, 95)),
        "max": float(arr.max()),
        "min": float(arr.min()),
    }


def stationary_bootstrap_daily(returns: np.ndarray, n_iter: int, rng) -> np.ndarray:
    """Politis-Romano stationary bootstrap : blocs de taille géométrique."""
    n = len(returns)
    mean_block = 10.0
    p = 1.0 / mean_block
    out = np.empty((n_iter, n))
    for i in range(n_iter):
        idx = np.empty(n, dtype=int)
        pos = 0
        while pos < n:
            start = rng.integers(0, n)
            length = rng.geometric(p)
            for j in range(length):
                if pos >= n:
                    break
                idx[pos] = (start + j) % n
                pos += 1
        out[i] = returns[idx]
    return out


def main() -> None:
    w_lines: list[str] = []
    w = w_lines.append
    w("=" * 78)
    w("TEST 4 — BOOTSTRAP / MONTE-CARLO · B25 m8 (2022/2024/2025/2026)")
    w("=" * 78)

    # Charger equity curves + rendements journaliers
    eq: dict[str, np.ndarray] = {}
    ret: dict[str, np.ndarray] = {}
    n_days = {}
    for year, run in RUNS.items():
        d = pd.read_csv(ROOT / "artifacts" / "backtesting" / run / "equity_curve.csv")
        eq[year] = d["portfolio_value"].to_numpy(dtype=float)
        r = np.diff(eq[year]) / eq[year][:-1]
        ret[year] = r
        n_days[year] = len(r)

    w("\n## A. STATIONARY BOOTSTRAP JOURNALIER (N=%d, bloc moyen 10j)" % N_ITER)
    w(f"{'année':<6}{'n_jours':>8}{'ret réel':>10}{'DD réel':>9} | "
      f"{'ret moy':>8}{'ret p5':>8}{'ret p95':>8}{'P(ret<0)':>9} | "
      f"{'DD moy':>8}{'DD p95':>8}{'DD max':>8}{'P(DD>10%)':>10}{'P(DD>15%)':>10}")
    dd_all_years = []
    for year in ["2022", "2024", "2025", "2026"]:
        r = ret[year]
        real_ret = eq[year][-1] / eq[year][0] - 1.0
        real_dd = _max_dd(eq[year])
        boot = stationary_bootstrap_daily(r, N_ITER, RNG)
        eq_sim = 100_000.0 * np.cumprod(1.0 + boot, axis=1)
        rets = eq_sim[:, -1] / eq_sim[:, 0] - 1.0
        dds = np.array([_max_dd(eq_sim[i]) for i in range(N_ITER)])
        dd_all_years.append(dds)
        p_neg = float((rets < 0).mean())
        p_dd10 = float((dds > 0.10).mean())
        p_dd15 = float((dds > 0.15).mean())
        st_r = _stats(rets)
        st_d = _stats(dds)
        w(f"{year:<6}{n_days[year]:>8}{_pct(real_ret):>10}{_pct(real_dd):>9} | "
          f"{_pct(st_r['mean']):>8}{_pct(st_r['p5']):>8}{_pct(st_r['p95']):>8}{_pct(p_neg):>9} | "
          f"{_pct(st_d['mean']):>8}{_pct(st_d['p95']):>8}{_pct(st_d['max']):>8}{_pct(p_dd10):>10}{_pct(p_dd15):>10}")

    # ── Bootstrap trades par année ───────────────────────────────────────
    w("\n## B. BOOTSTRAP DES TRADES (resampling + réordonnancement, N=%d)" % N_ITER)
    trades_by_year = {}
    for year, run in RUNS.items():
        df = pd.read_csv(ROOT / "artifacts" / "backtesting" / run / "trade_audit_log.csv")
        ex = df[df["event_type"] == "exit_closed"].copy()
        ex["return_pct"] = ex["return_pct"].astype(float) / 100.0  # fraction
        # poids relatif de chaque trade ≈ notional d'entrée / equity initiale.
        # entry_cost n'est rempli que sur entry_opened → utiliser entry_price×qty.
        equity0 = float(df[df["event_type"] == "daily_leverage_snapshot"]["current_equity"].iloc[0])
        ex["notional"] = ex["entry_price"].astype(float) * ex["quantity"].astype(float)
        ex["w"] = ex["notional"] / equity0
        ex = ex.dropna(subset=["w", "return_pct"])
        trades_by_year[year] = ex[["w", "return_pct"]].to_numpy(dtype=float)

    w(f"{'année':<6}{'n_tr':>6} | "
      f"{'ret moy':>8}{'ret p5':>8}{'ret p95':>8}{'P(ret<0)':>9} | "
      f"{'DD moy':>8}{'DD p95':>8}{'DD max':>8}{'P(DD>10%)':>10}{'P(DD>15%)':>10}")
    for year in ["2022", "2024", "2025", "2026"]:
        tw = trades_by_year[year]
        n_tr = len(tw)
        rets = np.empty(N_ITER)
        dds = np.empty(N_ITER)
        for i in range(N_ITER):
            sample = tw[RNG.integers(0, n_tr, size=n_tr)]  # resample avec remise
            RNG.shuffle(sample)                            # réordonne
            cap = 100_000.0
            curve = [cap]
            for w_i, r_i in sample:
                cap = cap * (1.0 + w_i * r_i)
                curve.append(cap)
            curve = np.array(curve)
            rets[i] = curve[-1] / curve[0] - 1.0
            dds[i] = _max_dd(curve)
        p_neg = float((rets < 0).mean())
        p_dd10 = float((dds > 0.10).mean())
        p_dd15 = float((dds > 0.15).mean())
        st_r = _stats(rets)
        st_d = _stats(dds)
        w(f"{year:<6}{n_tr:>6} | "
          f"{_pct(st_r['mean']):>8}{_pct(st_r['p5']):>8}{_pct(st_r['p95']):>8}{_pct(p_neg):>9} | "
          f"{_pct(st_d['mean']):>8}{_pct(st_d['p95']):>8}{_pct(st_d['max']):>8}{_pct(p_dd10):>10}{_pct(p_dd15):>10}")

    # ── C. Pool combiné (toutes années confondues) ──────────────────────
    w("\n## C. POOL COMBINÉ — tous les trades B25 m8 (2022+2024+2025+2026)")
    pool = np.vstack([trades_by_year[y] for y in ["2022", "2024", "2025", "2026"]])
    n_pool = len(pool)
    w(f"  trades dans le pool : {n_pool}")
    w("  Simulation : séquence de %d trades (resampling + réordonnancement) × %d" % (n_pool, N_ITER))
    rets = np.empty(N_ITER)
    dds = np.empty(N_ITER)
    for i in range(N_ITER):
        sample = pool[RNG.integers(0, n_pool, size=n_pool)]
        RNG.shuffle(sample)
        cap = 100_000.0
        curve = [cap]
        for w_i, r_i in sample:
            cap = cap * (1.0 + w_i * r_i)
            curve.append(cap)
        curve = np.array(curve)
        rets[i] = curve[-1] / curve[0] - 1.0
        dds[i] = _max_dd(curve)
    st_r = _stats(rets)
    st_d = _stats(dds)
    w(f"  ret  : moy {_pct(st_r['mean'])} | p5 {_pct(st_r['p5'])} | p25 {_pct(st_r['p25'])} | "
      f"p50 {_pct(st_r['p50'])} | p75 {_pct(st_r['p75'])} | p95 {_pct(st_r['p95'])}")
    w(f"  P(ret < 0)        = {_pct(float((rets < 0).mean()))}")
    w(f"  DD   : moy {_pct(st_d['mean'])} | p95 {_pct(st_d['p95'])} | max {_pct(st_d['max'])}")
    w(f"  P(DD > 10%)       = {_pct(float((dds > 0.10).mean()))}")
    w(f"  P(DD > 15%)       = {_pct(float((dds > 0.15).mean()))}")
    w(f"  P(DD > 20%)       = {_pct(float((dds > 0.20).mean()))}")

    # ── Distribution DD combinée toutes années (journalier) ─────────────
    w("\n## D. RÉPONSE CENTRALE — P(DD réel > seuil) sur le compte multi-années")
    # simule 4 années consécutives de rendements journaliers bootstrappés (blocs)
    r_all = np.concatenate([ret[y] for y in ["2022", "2024", "2025", "2026"]])
    boot = stationary_bootstrap_daily(r_all, N_ITER, RNG)
    eq_sim = 100_000.0 * np.cumprod(1.0 + boot, axis=1)
    dds_multi = np.array([_max_dd(eq_sim[i]) for i in range(N_ITER)])
    rets_multi = eq_sim[:, -1] / eq_sim[:, 0] - 1.0
    st_d = _stats(dds_multi)
    st_r = _stats(rets_multi)
    w(f"  (4 ans consécutifs simulés, bloc journalier, N={N_ITER})")
    w(f"  DD   : moy {_pct(st_d['mean'])} | p50 {_pct(st_d['p50'])} | p95 {_pct(st_d['p95'])} | max {_pct(st_d['max'])}")
    for s in (0.05, 0.10, 0.15, 0.20, 0.25):
        w(f"  P(DD > {s*100:.0f}%) = {_pct(float((dds_multi > s).mean()))}")
    w(f"  ret combiné : moy {_pct(st_r['mean'])} | p5 {_pct(st_r['p5'])} | p95 {_pct(st_r['p95'])} | P(ret<0) {_pct(float((rets_multi<0).mean()))}")

    text = "\n".join(w_lines)
    OUT.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
