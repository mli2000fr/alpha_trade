"""Diagnostic rapide post-backtest : entries vs exits."""
import pandas as pd
import json
from pathlib import Path

RUN_DIR = Path("f:/projets/artifacts/backtesting/regime_full_2020_2022_cli")

# ── 1. Charger les trades ──────────────────────────────────────────
df = pd.read_csv(RUN_DIR / "trades.csv")
df["entry_date"] = pd.to_datetime(df["entry_date"])
df["exit_date"] = pd.to_datetime(df["exit_date"])
df["year"] = df["entry_date"].dt.year

print("=" * 70)
print("DIAGNOSTIC ENTRIES vs EXITS")
print("=" * 70)

# ── 2. Retour moyen par exit_reason ────────────────────────────────
print("\n── 1. Retour moyen par type de sortie ──")
for reason in sorted(df["exit_reason"].unique()):
    sub = df[df["exit_reason"] == reason]
    print(f"  {reason:<20} n={len(sub):>5}  return_mean={sub['return_pct'].mean():>7.2f}%  "
          f"return_median={sub['return_pct'].median():>7.2f}%  "
          f"win_rate={(sub['return_pct'] > 0).mean() * 100:>5.1f}%")

# ── 3. Distribution des returns ────────────────────────────────────
print("\n── 2. Distribution des returns (%) ──")
print(df["return_pct"].describe().to_string())

# ── 4. Top/bottom trades ───────────────────────────────────────────
print("\n── 3. Top 5 gagnants ──")
cols = ["symbol", "entry_date", "exit_date", "return_pct", "exit_reason", "holding_days"]
print(df.nlargest(5, "return_pct")[cols].to_string(index=False))

print("\n── 4. Top 5 perdants ──")
print(df.nsmallest(5, "return_pct")[cols].to_string(index=False))

# ── 5. Trades par année ────────────────────────────────────────────
print("\n── 5. Performance par année ──")
for year, grp in df.groupby("year"):
    wr = (grp["return_pct"] > 0).mean() * 100
    print(f"  {year}: {len(grp):>5} trades  win_rate={wr:>5.1f}%  "
          f"mean_return={grp['return_pct'].mean():>7.2f}%  "
          f"total_pnl={grp['pnl'].sum():>10.2f}")

# ── 6. Holding days ────────────────────────────────────────────────
print("\n── 6. Durée de détention (jours) ──")
print(df["holding_days"].describe().to_string())

# ── 7. Returns par durée de holding ────────────────────────────────
print("\n── 7. Win rate par durée de holding ──")
bins = [0, 3, 5, 10, 15, 20, 100]
labels = ["1-3j", "4-5j", "6-10j", "11-15j", "16-20j", "21j+"]
df["holding_bucket"] = pd.cut(df["holding_days"], bins=bins, labels=labels)
for bucket in labels:
    sub = df[df["holding_bucket"] == bucket]
    if len(sub) > 0:
        print(f"  {bucket}: n={len(sub):>4}  win_rate={(sub['return_pct'] > 0).mean() * 100:>5.1f}%  "
              f"mean_return={sub['return_pct'].mean():>7.2f}%")

# ── 8. Profit factor ───────────────────────────────────────────────
wins = df[df["return_pct"] > 0]["return_pct"].sum()
losses = abs(df[df["return_pct"] <= 0]["return_pct"].sum())
pf = wins / losses if losses > 0 else float("inf")
print(f"\n── 8. Profit Factor ──")
print(f"  Gains totaux: {wins:.2f}%")
print(f"  Pertes totales: {losses:.2f}%")
print(f"  Profit Factor: {pf:.3f}")

# ── 9. Ratio gain moyen / perte moyenne ────────────────────────────
avg_win = df[df["return_pct"] > 0]["return_pct"].mean()
avg_loss = abs(df[df["return_pct"] <= 0]["return_pct"].mean())
print(f"\n── 9. Ratio gain/perte moyen ──")
print(f"  Gain moyen: {avg_win:.2f}%")
print(f"  Perte moyenne: {avg_loss:.2f}%")
print(f"  Ratio G/P: {avg_win / avg_loss:.3f}" if avg_loss > 0 else "  Ratio G/P: N/A")

# ── 10. Conclusion ─────────────────────────────────────────────────
print(f"\n{'=' * 70}")
print("CONCLUSION")
print(f"{'=' * 70}")
wr = (df["return_pct"] > 0).mean() * 100
ts_pct = (df["exit_reason"] == "trailing_stop").mean() * 100
tp_pct = (df["exit_reason"] == "take_profit").mean() * 100

print(f"  Win rate globale: {wr:.1f}%")
print(f"  Sorties trailing stop: {ts_pct:.0f}% des trades")
print(f"  Sorties take profit: {tp_pct:.0f}% des trades")
print(f"  Profit factor: {pf:.3f}")

if pf < 1.0:
    print(f"\n  ⚠️  PROFIT FACTOR < 1.0 → la stratégie perd structurellement.")
if ts_pct > 70:
    print(f"  ⚠️  {ts_pct:.0f}% de sorties en trailing stop → le TP ({tp_pct:.0f}%) est rarement atteint.")
    print(f"  → Soit le TP est trop loin, soit les entrées n'ont pas assez d'élan.")
if avg_win < abs(avg_loss):
    print(f"  ⚠️  Le gain moyen ({avg_win:.2f}%) est inférieur à la perte moyenne ({avg_loss:.2f}%).")
    print(f"  → Même avec 50% de win rate, on perdrait de l'argent.")
