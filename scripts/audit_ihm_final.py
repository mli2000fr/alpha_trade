# -*- coding: utf-8 -*-
"""Audit final du run IHM 20260817_165433_2785da86 : pullback + coûts de sortie."""
import pandas as pd
from sqlalchemy import create_engine, text

RUN = "artifacts/ihm_backtesting_runs/run/20260817_165433_2785da86/artifacts/trade_audit_log.csv"
ENGINE = create_engine("mysql+pymysql://root:root@localhost/alpha_trade", future=True)

df = pd.read_csv(RUN)
entries = df[df["event_type"] == "entry_opened"].copy()
exits = df[df["event_type"] == "exit_closed"].copy()
entries["exec_date"] = pd.to_datetime(entries["execution_date"]).dt.date

# 1. Pullback : % de trades à entry_price ≈ open×(1±1%)
n_pull = 0
n_tot = 0
diffs = []
with ENGINE.connect() as c:
    for _, r in entries.iterrows():
        q = c.execute(
            text("SELECT open FROM stock_bars_daily WHERE symbol=:s AND date=:d"),
            {"s": str(r["symbol"]).strip(), "d": r["exec_date"]},
        ).fetchone()
        if q is None:
            continue
        n_tot += 1
        diff_bps = (float(r["entry_price"]) / float(q[0]) - 1.0) * 10000
        diffs.append(diff_bps)
        if abs(abs(diff_bps) - 100.0) < 1.0:  # ±1% exact
            n_pull += 1
print(f"1) PULLBACK 1% : {n_pull}/{n_tot} entrées ({n_pull/n_tot*100:.1f}%) à entry_price = open ± 1% exact")

# 2. Coût de sortie : vérifier que les frais sont appliqués (exit_price vs close réel)
#    Pour un long, on vend → exit_price ≈ prix_de_sortie_brut × (1 − fees)
#    Test simple : coût total du run ≈ somme des frais estimés
exits2 = exits.copy()
exits2["notional_in"] = exits2["entry_price"] * exits2["quantity"]
exits2["notional_out"] = exits2["exit_price"] * exits2["quantity"]
exits2["notional_rt"] = (exits2["notional_in"] + exits2["notional_out"]) / 2.0
notional_rt_total = exits2["notional_rt"].sum()
# coût estimé à ~10.3 bps RT (comme le benchmark)
est_cost = notional_rt_total * 10.32 / 10000
print(f"2) notional RT total: ${notional_rt_total:,.0f} | coût estimé (~10.3 bps RT): ${est_cost:,.0f}")
print(f"   P&L net exits: ${exits2['pnl'].sum():,.1f} | P&L brut estimé: ${exits2['pnl'].sum()+est_cost:,.1f}")

# 3. Taille de positions et levier
en2 = entries.copy()
en2["notional_in"] = en2["entry_price"] * en2["quantity"]
print(f"3) notional entrée moyen: ${en2['notional_in'].mean():,.0f} | equity 4000 → poids moyen {en2['notional_in'].mean()/4000*100:.1f}%")
snap = df[df["event_type"] == "daily_leverage_snapshot"]
print(f"   gross moyen: {snap['gross_exposure_before_pct'].mean()*100:.1f}% | max {snap['gross_exposure_before_pct'].max()*100:.1f}%")

# 4. Exit reasons
print("4) exit_reason:", exits["exit_reason"].value_counts().to_dict())
print("   exit_source:", exits["exit_source"].value_counts(dropna=False).to_dict())
