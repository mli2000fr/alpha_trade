"""E5-D : validation historique gelée — comparaison 5 périodes × 3 variantes.

Variantes gelées (aucun autre tuning) :
  - 3x7  = baseline post-fix (min(3xATR, 7%))
  - 4x13 = alternative conservatrice (min(4xATR, 13%))
  - noTP = candidat agressif (min(50xATR, 100%) = jamais atteint)

Périodes : 2022, 2023, 2024, 2025, 2026H1.
2025 + 2026H1 proviennent d'E5-C (runs cmp_b25_h20_{year}_...).

Gates (fixés AVANT lancement) :
  1. no-TP doit battre 3x7 sur >= 4 périodes sur 5 en PF ou expectancy
  2. aucun effondrement de DD
  3. pas de dépendance à une seule année
  4. LONG et SHORT pas d'inversion catastrophique
  5. 4x13 = benchmark "moins extrême"
"""
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path("artifacts/backtesting")

RUNS = {
    "3x7": {
        "2022": "cmp_b25_h20_2022_postfix_tp_m8",
        "2023": "cmp_b25_h20_2023h1_postfix_tp_m8",
        "2024": "cmp_b25_h20_2024h1_postfix_tp_m8",
        "2025": "cmp_b25_h20_2025_postfix_tp_m8",
        "2026": "cmp_b25_h20_2026_postfix_tp_m8",
    },
    "4x13": {
        "2022": "cmp_b25_h20_2022_tp4x13_m8",
        "2023": "cmp_b25_h20_2023h1_tp4x13_m8",
        "2024": "cmp_b25_h20_2024h1_tp4x13_m8",
        "2025": "cmp_b25_h20_2025_tp4x13_m8",
        "2026": "cmp_b25_h20_2026_tp4x13_m8",
    },
    "noTP": {
        "2022": "cmp_b25_h20_2022_notp_m8",
        "2023": "cmp_b25_h20_2023h1_notp_m8",
        "2024": "cmp_b25_h20_2024h1_notp_m8",
        "2025": "cmp_b25_h20_2025_notp_m8",
        "2026": "cmp_b25_h20_2026_notp_m8",
    },
}

PERIODS = ["2022", "2023", "2024", "2025", "2026"]
PERIOD_LABEL = {"2022": "2022", "2023": "2023 H1", "2024": "2024 H1", "2025": "2025", "2026": "2026 H1"}
LABEL = {"3x7": "3xATR/7%", "4x13": "4xATR/13%", "noTP": "no-TP"}


def load_summary(name):
    rp = ROOT / name / "report.json"
    if not rp.exists():
        return None
    return json.loads(rp.read_text(encoding="utf-8")).get("summary", {})


def main():
    # Collecter par période
    data = {}
    for period in PERIODS:
        data[period] = {}
        for var in RUNS:
            name = RUNS[var][period]
            s = load_summary(name)
            if s is None:
                data[period][var] = None
            else:
                data[period][var] = {
                    "ret": s.get("total_return_pct", 0),
                    "pf": s.get("profit_factor", 0),
                    "sharpe": s.get("sharpe_ratio", 0),
                    "dd": s.get("max_drawdown_pct", 0),
                    "n": s.get("total_trades", 0),
                    "win": s.get("win_rate_pct", 0),
                    "net": s.get("pnl_net", 0),
                    "l_pnl": s.get("long_pnl_total", 0),
                    "s_pnl": s.get("short_pnl_total", 0),
                    "l_n": s.get("long_trades", 0),
                    "s_n": s.get("short_trades", 0),
                }

    # Tableau principal Ret/PF/DD
    print("=" * 100)
    print("E5-D — VALIDATION HISTORIQUE GELÉE (3 variantes, 5 périodes)")
    print("=" * 100)
    for var in RUNS:
        print(f"\n### {LABEL[var]}  (Ret% | PF | DD% | net | N)")
        print(f"{'Période':10} {'Ret%':>8} {'PF':>6} {'DD%':>7} {'Sharpe':>7} {'net':>9} {'N':>5}")
        for period in PERIODS:
            d = data[period][var]
            if d is None:
                print(f"{PERIOD_LABEL[period]:10}  ABSENT")
                continue
            print(f"{PERIOD_LABEL[period]:10} {d['ret']:8.2f} {d['pf']:6.2f} {d['dd']:7.2f} "
                  f"{d['sharpe']:7.2f} {d['net']:9.0f} {d['n']:5d}")

    # Vue compacte par métrique : period x variant
    def compact(metric, fmt="{:>8}", header=""):
        print(f"\n### {header or metric}")
        print(f"{'Période':10} " + "".join(f"{LABEL[v]:>10}" for v in RUNS))
        for period in PERIODS:
            cells = []
            for v in RUNS:
                d = data[period][v]
                cells.append(fmt.format(d[metric]) if d else "    ABS")
            print(f"{PERIOD_LABEL[period]:10} " + "".join(f"{c:>10}" for c in cells))

    compact("ret", "{:>7.1f}%", "Retour %")
    compact("pf", "{:>7.2f}", "Profit factor")
    compact("dd", "{:>7.1f}%", "Max drawdown %")
    compact("net", "{:>8.0f}", "PnL net ($)")

    # Gates
    print("\n" + "=" * 100)
    print("GATES")
    print("=" * 100)
    # Gate 1 : no-TP bat 3x7 sur >=4/5 en PF ou expectancy (net/N)
    wins = 0
    details = []
    for period in PERIODS:
        d3 = data[period]["3x7"]
        dn = data[period]["noTP"]
        if d3 is None or dn is None:
            continue
        pf3, pf_n = d3["pf"], dn["pf"]
        exp3 = d3["net"] / d3["n"] if d3["n"] else 0
        exp_n = dn["net"] / dn["n"] if dn["n"] else 0
        win_pf = pf_n > pf3
        win_exp = exp_n > exp3
        if win_pf or win_exp:
            wins += 1
        details.append(f"{period}: PF {pf3:.2f}→{pf_n:.2f} ({'O' if win_pf else 'X'}), "
                       f"exp {exp3:.0f}→{exp_n:.0f} ({'O' if win_exp else 'X'})")
    print(f"\nGATE 1 — no-TP bat 3x7 sur >= 4/5 périodes (PF OU expectancy) :")
    for d in details:
        print(f"   {d}")
    print(f"   → {wins}/5  {'PASS' if wins >= 4 else 'FAIL'}")

    # Gate 2 : DD no-TP vs 3x7 (pas d'effondrement = DD no-TP pas massivement pire)
    print(f"\nGATE 2 — DD no-TP vs 3x7 :")
    dd_ok = True
    for period in PERIODS:
        d3 = data[period]["3x7"]
        dn = data[period]["noTP"]
        if d3 is None or dn is None:
            continue
        ratio = dn["dd"] / d3["dd"] if d3["dd"] else float("inf")
        flag = "OK" if dn["dd"] <= d3["dd"] * 1.5 + 2.0 else "MAUVAIS"
        if flag != "OK":
            dd_ok = False
        print(f"   {period}: 3x7 DD {d3['dd']:.1f}% → noTP DD {dn['dd']:.1f}%  ({flag})")
    print(f"   → {'PASS' if dd_ok else 'FAIL'}")

    # Gate 3 : pas de dépendance à une seule année (no-TP ne doit pas dépendre
    # d'UN SEUL bon résultat — au moins 3/5 périodes à net > 0 et pas qu'une seule)
    print(f"\nGATE 3 — dépendance à une seule année (no-TP) :")
    pos = 0
    for period in PERIODS:
        dn = data[period]["noTP"]
        if dn and dn["net"] > 0:
            pos += 1
    print(f"   no-TP net>0 sur {pos}/5 périodes")
    print(f"   → {'PASS' if pos >= 3 else 'FAIL'}")

    # Gate 4 : pas d'inversion catastrophique LONG/SHORT
    print(f"\nGATE 4 — inversion LONG/SHORT :")
    inv_ok = True
    for period in PERIODS:
        d3 = data[period]["3x7"]
        dn = data[period]["noTP"]
        if d3 is None or dn is None:
            continue
        # regarder si un côté passe de positif à fortement négatif
        for side, lbl in [("l_pnl", "LONG"), ("s_pnl", "SHORT")]:
            v3 = d3[side]
            vn = dn[side]
            if v3 > 0 and vn < -abs(v3) * 0.5:
                print(f"   {period} {lbl}: 3x7 {v3:.0f} → noTP {vn:.0f}  (INVERSION)")
                inv_ok = False
    print(f"   → {'PASS' if inv_ok else 'FAIL'}")

    # Gate 5 : 4x13 benchmark — stabilité
    print(f"\nGATE 5 — 4x13 benchmark (stabilité) :")
    for period in PERIODS:
        d3 = data[period]["3x7"]
        d4 = data[period]["4x13"]
        if d3 is None or d4 is None:
            continue
        delta = d4["net"] - d3["net"]
        print(f"   {period}: 4x13 net {d4['net']:>8.0f} vs 3x7 {d3['net']:>8.0f}  (Δ {delta:>+8.0f})")


if __name__ == "__main__":
    main()
