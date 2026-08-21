# -*- coding: utf-8 -*-
"""Audit coûts du backtest IHM suspect 20260817_165433_2785da86.

Vérifie que les coûts sont bien appliqués en comparant le prix d'exécution
enregistré (entry_price) avec l'open réel du jour (stock_bars_daily).
Pour un LONG : entry_price ≈ open × (1 + (5 bps + spread/2)/10000)  → prix plus haut
Pour un SHORT: entry_price ≈ open × (1 − (5 bps + spread/2)/10000)  → prix plus bas
Si entry_price == open exact → pénalité de slippage NON appliquée → BUG (coûts gonflés).
"""
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "artifacts" / "ihm_backtesting_runs" / "run" / "20260817_165433_2785da86"
AUDIT = RUN / "artifacts" / "trade_audit_log.csv"
ENGINE = create_engine("mysql+pymysql://root:root@localhost/alpha_trade", future=True)

df = pd.read_csv(AUDIT)
entries = df[df["event_type"] == "entry_opened"].copy()
entries["exec_date"] = pd.to_datetime(entries["execution_date"]).dt.date

# Prendre un échantillon de trades (les 12 premiers)
sample = entries.head(12)
rows = []
with ENGINE.connect() as c:
    for _, r in sample.iterrows():
        sym = str(r["symbol"]).strip()
        side = str(r["side"]).strip()
        d = r["exec_date"]
        q = c.execute(
            text("SELECT open FROM stock_bars_daily WHERE symbol=:s AND date=:d"),
            {"s": sym, "d": d},
        ).fetchone()
        if q is None:
            rows.append((sym, side, d, None, r["entry_price"], None, None))
            continue
        open_ = float(q[0])
        ep = float(r["entry_price"])
        # sens attendu : long → ep > open ; short → ep < open
        expected_dir = "LONG>open" if ep > open_ else ("SHORT<open" if ep < open_ else "??")
        diff_bps = (ep / open_ - 1.0) * 10000.0
        rows.append((sym, side, d, open_, ep, round(diff_bps, 2), expected_dir))

out = pd.DataFrame(rows, columns=["symbol", "side", "date", "open", "entry_price", "diff_bps", "sens"])
print("Vérification pénalité d'exécution (entry_price vs open réel)")
print("Pour LONG attendu diff>0 (prix plus haut), pour SHORT diff<0 (prix plus bas)")
print(out.to_string(index=False))
print()
print("diff_bps moyen (hors lignes manquantes):", round(out['diff_bps'].mean(), 2))
print("Une pénalité ~5-15 bps est attendue. diff≈0 partout = coûts NON appliqués (BUG).")
