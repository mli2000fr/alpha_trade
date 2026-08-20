import pandas as pd
import numpy as np

tr = pd.read_csv("artifacts/backtesting/b25_2025_rankw/trades.csv")
tr["is_win"] = tr["return_pct"] > 0
tr["is_loss"] = tr["return_pct"] < 0
tr["entry_date"] = pd.to_datetime(tr["entry_date"])
tr["month"] = tr["entry_date"].dt.to_period("M").astype(str)

print("=== 1. Perte par exit_reason ===")
for er, sub in tr.groupby("exit_reason"):
    l = sub[sub["is_loss"]]
    print(f"  {er}: n={len(sub)} | losses={len(l)} | pnl_sum={sub['pnl'].sum():.0f} | loss_pnl={l['pnl'].sum():.0f} | win={sub['is_win'].mean()*100:.0f}%")

print("\n=== 2. P&L par mois ===")
for m, sub in tr.groupby("month"):
    l = sub[sub["is_loss"]]
    print(f"  {m}: n={len(sub)} | win={sub['is_win'].mean()*100:.0f}% | pnl={sub['pnl'].sum():.0f} | loss_pnl={l['pnl'].sum():.0f}")

print("\n=== 3. P&L par secteur (n>=4) ===")
sect = tr.groupby("sector").agg(n=("pnl", "size"), win=("is_win", "mean"), pnl=("pnl", "sum"),
                                loss_pnl=("pnl", lambda s: s[s < 0].sum())).reset_index()
sect = sect[sect["n"] >= 4].sort_values("pnl")
print(sect.to_string(index=False))

print("\n=== 4. Perte par délai de détention ===")
tr["hold_bucket"] = pd.cut(tr["holding_days"], bins=[0, 2, 5, 10, 20, 60], labels=["0-2j", "3-5j", "6-10j", "11-20j", ">20j"])
for hb, sub in tr.groupby("hold_bucket", observed=True):
    l = sub[sub["is_loss"]]
    print(f"  {hb}: n={len(sub)} | win={sub['is_win'].mean()*100:.0f}% | pnl={sub['pnl'].sum():.0f} | loss_pnl={l['pnl'].sum():.0f}")

print("\n=== 5. trailing_stop : win/loss ===")
ts = tr[tr["exit_reason"] == "trailing_stop"]
print(f"  trailing_stop n={len(ts)} | win={ts['is_win'].mean()*100:.1f}% | return moy={ts['return_pct'].mean():.2f}% | median={ts['return_pct'].median():.2f}%")
print("  return_pct quartiles:", ts["return_pct"].quantile([0.25, 0.5, 0.75]).to_dict())
# trailing stop en perte vs en gain
tsl = ts[ts["is_loss"]]
print(f"  trailing_stop PERTE: n={len(tsl)} | return moy={tsl['return_pct'].mean():.2f}% | holding moy={tsl['holding_days'].mean():.1f}j")
tsw = ts[ts["is_win"]]
print(f"  trailing_stop GAIN: n={len(tsw)} | return moy={tsw['return_pct'].mean():.2f}% | holding moy={tsw['holding_days'].mean():.1f}j")
