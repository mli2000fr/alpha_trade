import pandas as pd
import numpy as np

tr = pd.read_csv("artifacts/backtesting/b25_2025_rankw/trades.csv")
tr["is_win"] = tr["return_pct"] > 0
tr["is_loss"] = tr["return_pct"] < 0
tr["entry_date"] = pd.to_datetime(tr["entry_date"])

ts = tr[tr["exit_reason"] == "trailing_stop"].copy()
print("=== trailing_stop : distribution des pertes par délai ===")
ts["hold_bucket"] = pd.cut(ts["holding_days"], bins=[0, 1, 2, 3, 5, 10, 60], labels=["0-1j", "2j", "3j", "4-5j", "6-10j", ">10j"])
for hb, sub in ts.groupby("hold_bucket", observed=True):
    l = sub[sub["is_loss"]]
    print(f"  {hb}: n={len(sub)} | win={sub['is_win'].mean()*100:.0f}% | pnl={sub['pnl'].sum():.0f} | loss_pnl={l['pnl'].sum():.0f} | return_moy={sub['return_pct'].mean():.2f}%")

print("\n=== trailing_stop : perte moyenne par tranche ===")
l = ts[ts["is_loss"]]
bins = [-100, -7, -6, -5, -4, -3, -2, 0]
labels = ["<-7%", "-7/-6", "-6/-5", "-5/-4", "-4/-3", "-3/-2", "-2/0"]
l2 = l.copy()
l2["tr"] = pd.cut(l2["return_pct"], bins=bins, labels=labels)
for t, sub in l2.groupby("tr", observed=True):
    print(f"  {t}: n={len(sub)} | return moy={sub['return_pct'].mean():.2f}% | holding moy={sub['holding_days'].mean():.1f}j | pnl={sub['pnl'].sum():.0f}")

print("\n=== Perdants vs gagnants : proba/rank ===")
for col in ["predicted_proba", "conviction", "rank", "selection_rank", "score"]:
    if col in tr.columns:
        print(f"  {col}: win mean={tr.loc[tr['is_win'], col].mean():.4f} | loss mean={tr.loc[tr['is_loss'], col].mean():.4f}")

print("\n=== perdants: combien sortent en 1-2j (SL immédiat?) ===")
early = ts[(ts["is_loss"]) & (ts["holding_days"] <= 2)]
print(f"  pertes trailing en <=2j: {len(early)}/{len(l)} | pnl={early['pnl'].sum():.0f}")
print(f"  -> part des pertes totales: {early['pnl'].sum()/tr['pnl'][tr['pnl']<0].sum()*100:.0f}%")

print("\n=== 10 pires trades ===")
print(tr.nsmallest(10, "return_pct")[["symbol", "side", "entry_date", "exit_reason", "holding_days", "return_pct", "pnl", "rank"]].to_string(index=False))
