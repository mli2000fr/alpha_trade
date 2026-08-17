# -*- coding: utf-8 -*-
"""Audit des coûts de TOUS les stress tests (2026-08-17).

Méthode identique à l'audit du benchmark : chaque run de stress a les MÊMES
77 trades que le benchmark (sélection insensible aux coûts). Donc :
    P&L brut (constant) = P&L net benchmark + coût baseline
    coût débité(R) = P&L brut − P&L net(R)
avec coût baseline = (P&L_benchmark − P&L_×3)/2 = 924.90 $ (mesuré).

On exprime ensuite le coût mesuré en bps round-trip et on le compare au coût
CIBLE du scénario :
- cost_rt C      → cible = C bps RT (coût forcé absolu)
- cost_multiplier m → cible = m × 10.32 bps (coût baseline en bps)
- fallback fb    → cible = baseline + effet fallback (≈ 10.3 bps + léger)
- fills impact   → cible = baseline + extra impact

Sortie : logs/audit_stress_costs.txt
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "artifacts" / "backtesting"
REF = "cmp_b25_h20_2026_prodparity_repro_h20cfg_m8"
X3 = "stress_cost_m30"
OUT = ROOT / "logs" / "audit_stress_costs.txt"

# (run, type, cible bps RT)
RUNS = [
    ("stress_cost_m125", "multiplier ×1.25", 1.25 * 10.32),
    ("stress_cost_m15", "multiplier ×1.5", 1.5 * 10.32),
    ("stress_cost_m20", "multiplier ×2", 2.0 * 10.32),
    ("stress_cost_m30", "multiplier ×3", 3.0 * 10.32),
    ("cost_rt10", "RT absolu 10 bps", 10.0),
    ("cost_rt20", "RT absolu 20 bps", 20.0),
    ("cost_rt30", "RT absolu 30 bps", 30.0),
    ("cost_rt44", "RT absolu 44 bps", 44.0),
    ("cost_rt60", "RT absolu 60 bps", 60.0),
    ("fb10", "fallback 10 bps", 10.32),
    ("fb15", "fallback 15 bps", 10.32),
    ("fb20", "fallback 20 bps", 10.32),
    ("fills_imp50", "fills impact 50", 10.32),
    ("fills_imp100", "fills impact 100", 10.32),
    ("fills_imp200", "fills impact 200", 10.32),
    ("fills_lat5", "fills base5+impact100", 10.32),
]


def _net_pnl(run: str) -> float:
    df = pd.read_csv(BASE / run / "trade_audit_log.csv")
    return float(df[df["event_type"] == "exit_closed"]["pnl"].sum())


def main() -> None:
    ref_pnl = _net_pnl(REF)
    x3_pnl = _net_pnl(X3)
    cost_base = (ref_pnl - x3_pnl) / 2.0  # = 924.90 $
    pnl_brut = ref_pnl + cost_base

    # notionals (identiques pour tous les runs)
    df = pd.read_csv(BASE / REF / "trade_audit_log.csv")
    ex = df[df["event_type"] == "exit_closed"]
    notional_in = float((ex["entry_price"] * ex["quantity"]).sum())
    notional_out = float((ex["exit_price"] * ex["quantity"]).sum())
    notional_rt = (notional_in + notional_out) / 2.0

    lines = []
    w = lines.append
    w("=" * 100)
    w("AUDIT DES COÛTS — TOUS LES STRESS TESTS (pile gelée B25 m8, 2026, 77 trades)")
    w("=" * 100)
    w(f"P&L net benchmark = ${ref_pnl:,.2f} | coût baseline mesuré = ${cost_base:,.2f} "
      f"({cost_base/notional_rt*10000:.2f} bps RT) | P&L brut estimé = ${pnl_brut:,.2f}")
    w(f"notional entrée total = ${notional_in:,.0f} | sortie = ${notional_out:,.0f} "
      f"| RT moyen = ${notional_rt:,.0f}")
    w("")
    w(f"{'run':<20}{'type':<24}{'cible bps':>10}{'P&L net $':>14}{'coût $':>12}"
      f"{'coût bps':>10}{'ratio':>8}")
    w("-" * 100)

    rows = []
    # benchmark référence
    cost_ref = cost_base
    bps_ref = cost_ref / notional_rt * 10000
    w(f"{'benchmark':<20}{'baseline':<24}{10.32:>10.2f}{ref_pnl:>14,.0f}{cost_ref:>12,.0f}"
      f"{bps_ref:>10.2f}{1.0:>8.2f}")

    for run, typ, cible in RUNS:
        pnl_r = _net_pnl(run)
        cost_r = pnl_brut - pnl_r
        bps_r = cost_r / notional_rt * 10000
        ratio = bps_r / cible if cible else 0.0
        ok = "✅" if 0.85 <= ratio <= 1.15 else ("⚠️" if 0.7 <= ratio <= 1.3 else "❌")
        w(f"{run:<20}{typ:<24}{cible:>10.2f}{pnl_r:>14,.0f}{cost_r:>12,.0f}"
          f"{bps_r:>10.2f}{ratio:>7.2f} {ok}")
        rows.append((run, typ, cible, pnl_r, cost_r, bps_r, ratio))

    w("")
    w("Lecture : ratio = coût mesuré (bps) / coût cible (bps).")
    w("  - RT absolu : ratio ≈ 1.00 → le coût forcé C bps est bien débité.")
    w("  - multiplier m : ratio ≈ 1.00 → le coût m× baseline est bien débité.")
    w("  - fallback/fills : cible = baseline (10.3 bps) ; le ratio > 1 montre le surcoût réel.")

    text = "\n".join(lines)
    OUT.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
