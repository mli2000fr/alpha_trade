# -*- coding: utf-8 -*-
"""Audit comptable des coûts — benchmark 2026 (B25 m8).

Méthode la plus fiable : les runs ×1 (benchmark) et ×3 (stress_cost_m30) ont les
MÊMES 77 trades (sélection insensible aux coûts). La différence de P&L net par
trade ÷ 2 = coût réellement débité par trade au niveau baseline (×1).

Ensuite on recalcule le coût « attendu » par la formule du simulateur :
- entrée : slippage_bps = 5.0 + spread/2  → coût = notional_entrée × slippage/10000
- sortie : fees_rate = (comm 1 + slip 2 bps) + spread/2 → coût = notional_sortie × fees_rate
et on compare coût mesuré vs coût attendu par trade (validation de la formule).

On recharge aussi le spread réel (load_spreads) pour afficher le spread appliqué
par trade vs la médiane globale (44 bps).

Sortie : logs/cost_audit_2026.txt
"""
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RUN_X1 = ROOT / "artifacts" / "backtesting" / "cmp_b25_h20_2026_prodparity_repro_h20cfg_m8"
RUN_X3 = ROOT / "artifacts" / "backtesting" / "stress_cost_m30"
OUT = ROOT / "logs" / "cost_audit_2026.txt"

MAX_REALISTIC_SPREAD_BPS = 300.0
FALLBACK_BPS = 5.0            # DEFAULT_COST_MODEL.spread_bps
COMM_BPS = 1.0                # canonical
SLIP_BPS = 2.0                # canonical


def _fmt(x: float, nd: int = 2) -> str:
    return f"{x:,.{nd}f}"


def _get_spread_bps(spread_df, trade_day, symbol, fallback_bps=FALLBACK_BPS):
    if spread_df is None or spread_df.empty:
        return max(float(fallback_bps), 0.0)
    if symbol not in spread_df.columns or trade_day not in spread_df.index:
        return max(float(fallback_bps), 0.0)
    try:
        value = float(spread_df.at[trade_day, symbol])
        if np.isfinite(value) and value >= 0:
            if value > MAX_REALISTIC_SPREAD_BPS:
                return max(float(fallback_bps), 0.0)
            return value
        return max(float(fallback_bps), 0.0)
    except (KeyError, ValueError):
        return max(float(fallback_bps), 0.0)


def main() -> None:
    sys.path.insert(0, str(ROOT))
    from backtesting.data_loader import load_spreads
    from sqlalchemy import create_engine

    a = pd.read_csv(RUN_X1 / "trade_audit_log.csv")
    b = pd.read_csv(RUN_X3 / "trade_audit_log.csv")
    ea = a[a["event_type"] == "exit_closed"].reset_index(drop=True)
    eb = b[b["event_type"] == "exit_closed"].reset_index(drop=True)
    assert (ea["symbol"].values == eb["symbol"].values).all()

    engine = create_engine("mysql+pymysql://root:root@localhost/alpha_trade", future=True)
    spread_df = load_spreads(engine, date(2026, 1, 2), date(2026, 5, 31))
    global_median = float(spread_df.stack().median()) if not spread_df.empty else float("nan")

    # ── Notionals ────────────────────────────────────────────────────────
    ea["notional_in"] = ea["entry_price"].astype(float) * ea["quantity"].astype(float)
    ea["notional_out"] = ea["exit_price"].astype(float) * ea["quantity"].astype(float)
    ea["notional_avg"] = (ea["notional_in"] + ea["notional_out"]) / 2.0

    # ── Coût MESURÉ par trade (différence ×1 − ×3, divisée par 2) ───────
    ea["cost_measured"] = (ea["pnl"].astype(float) - eb["pnl"].astype(float)) / 2.0

    # ── Coût ATTENDU par formule (rechargement du spread réel) ──────────
    d_in = pd.to_datetime(ea["execution_date"])
    d_out = pd.to_datetime(ea["event_date"])
    rows = []
    for i, r in ea.iterrows():
        spr_in = _get_spread_bps(spread_df, d_in[i], r["symbol"])
        spr_out = _get_spread_bps(spread_df, d_out[i], r["symbol"])
        slip_in_bps = 5.0 + spr_in / 2.0
        fees_out_bps = COMM_BPS + SLIP_BPS + spr_out / 2.0
        cost_in = r["notional_in"] * slip_in_bps / 10_000.0
        cost_out = r["notional_out"] * fees_out_bps / 10_000.0
        rows.append({
            "symbol": r["symbol"], "side": r["side"],
            "d_in": d_in[i], "d_out": d_out[i],
            "spr_in_bps": spr_in, "spr_out_bps": spr_out,
            "cost_in": cost_in, "cost_out": cost_out,
            "cost_formula": cost_in + cost_out,
            "cost_measured": r["cost_measured"],
            "notional_in": r["notional_in"], "notional_out": r["notional_out"],
        })
    aud = pd.DataFrame(rows)
    aud["notional_avg"] = (aud["notional_in"] + aud["notional_out"]) / 2.0

    w: list[str] = []
    wl = w.append
    wl("=" * 80)
    wl("AUDIT COMPTABLE DES COÛTS — benchmark 2026 (B25 m8, 77 trades)")
    wl("=" * 80)
    wl(f"Spread réel médian (TOUS symboles) : {_fmt(global_median)} bps")
    wl(f"Notional entrée total : ${_fmt(aud['notional_in'].sum(), 0)}")
    wl(f"Notional sortie total : ${_fmt(aud['notional_out'].sum(), 0)}")
    wl(f"Notional moyen/trade  : ${_fmt(aud['notional_avg'].sum()/len(aud), 0)}")

    wl("\n## 1. Coût MESURÉ (réellement débité, par différence ×3−×1 ÷2)")
    cm = aud["cost_measured"]
    wl(f"  coût total mesuré      : ${_fmt(cm.sum(), 2)}  (pour 77 trades)")
    wl(f"  coût moyen / trade     : ${_fmt(cm.mean(), 2)}")
    wl(f"  coût médian / trade    : ${_fmt(cm.median(), 2)}")
    wl(f"  min / max / trade      : ${_fmt(cm.min(), 2)} / ${_fmt(cm.max(), 2)}")
    wl(f"  coût en bps round-trip (coût/notional moyen ×10000) : {_fmt(cm.sum()/aud['notional_avg'].sum()*10000)} bps")

    wl("\n## 2. Coût ATTENDU (formule simulateur, spread réel rechargé)")
    cf = aud["cost_formula"]
    wl(f"  coût total formule     : ${_fmt(cf.sum(), 2)}")
    wl(f"  coût moyen / trade     : ${_fmt(cf.mean(), 2)}")
    wl(f"  coût en bps round-trip : {_fmt(cf.sum()/aud['notional_avg'].sum()*10000)} bps")
    wl(f"  RATIO mesuré/formule   : {_fmt(cm.sum()/cf.sum(), 3)}  (≈1 = formule fidèle)")

    wl("\n## 3. Spread réellement appliqué aux TITRES TRADÉS")
    ss = pd.concat([aud["spr_in_bps"], aud["spr_out_bps"]])
    wl(f"  spread moyen sur les trades : {_fmt(ss.mean(),1)} bps  (vs médiane globale {_fmt(global_median,1)})")
    wl(f"  spread médian sur les trades: {_fmt(ss.median(),1)} bps")
    wl(f"  % de trades avec spread = fallback 5 bps : {_fmt((ss <= 5.0+1e-9).mean()*100,1)} %")
    wl(f"  spread max sur un trade    : {_fmt(ss.max(),1)} bps")
    wl(f"  spread p90 sur les trades  : {_fmt(ss.quantile(0.90),1)} bps")

    wl("\n## 4. Décomposition moyenne du coût par trade (formule)")
    wl(f"  spread entrée (5+spread/2) : ${_fmt((aud['cost_in']).mean(),2)}  ({_fmt((aud['cost_in']/aud['notional_in']*10000).mean(),1)} bps)")
    wl(f"  sortie (3bps+spread/2)     : ${_fmt((aud['cost_out']).mean(),2)}  ({_fmt((aud['cost_out']/aud['notional_out']*10000).mean(),1)} bps)")
    wl(f"  part spread vs fixe : spread ≈ {_fmt(aud['spr_in_bps'].mean()/2/ (5+aud['spr_in_bps'].mean()/2) *100,0)} % du coût d'entrée")

    wl("\n## 5. Top 8 trades par coût (mesuré)")
    top = aud.reindex(aud["cost_measured"].sort_values(ascending=False).index).head(8)
    for _, r in top.iterrows():
        wl(f"  {r['symbol']:<7} {str(r['side']):<5} in {r['d_in'].date()}  notional ${_fmt(r['notional_in'],0):>9}  "
           f"spr_in {_fmt(r['spr_in_bps'],1):>5}  coût mes ${_fmt(r['cost_measured'],2):>8}  coût form ${_fmt(r['cost_formula'],2):>8}")

    wl("\n## 6. Validation ×3 (coût ×3 attendu vs mesuré)")
    c3_measured = eb["pnl"].astype(float).sum()  # pnl net x3
    c1 = ea["pnl"].astype(float).sum()
    # coût total ×3 mesuré = (c1 − c3) ; coût ×1 = (c1−c3)/2
    wl(f"  P&L net ×1 = ${_fmt(c1,2)}  |  ×3 = ${_fmt(c3_measured,2)}")
    wl(f"  coût total ×1 = ${_fmt((c1-c3_measured)/2,2)}  |  ×3 = ${_fmt((c1-c3_measured)*3/2,2)}")
    wl(f"  coût ×3 attendu (3× formule ×1) = ${_fmt(3*cf.sum(),2)}")

    text = "\n".join(w)
    OUT.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
