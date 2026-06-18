"""Quick analysis of backtest run."""
import json, pandas as pd

BASE = "f:/projets/artifacts/ihm_backtesting_runs/run/20260618_012409_c8419e4e/artifacts"

# Report
with open(f"{BASE}/report.json") as f:
    r = json.load(f)
s = r["summary"]
d = r["diagnostics"]

print("=" * 60)
print("COMPARAISON AVANT/APRÈS CORRECTIFS")
print("=" * 60)

print(f"\n{'Métrique':<30} {'AVANT (41eabc77)':<20} {'APRÈS (c8419e4e)':<20}")
print("-" * 70)

# Before: from regime_full_2020_2022_cli (100k equity, different scale)
# We need same equity scale. The before run was 100k, now is 2k.
# Let me compare ratios instead.

print(f"{'Total trades':<30} {'1537':<20} {s['total_trades']:<20}")
print(f"{'Win rate %':<30} {'36.6%':<20} {s['win_rate_pct']:.1f}%")
print(f"{'Profit factor':<30} {'0.967':<20} {s['profit_factor']:.3f}")
print(f"{'Total return %':<30} {'-24.7%':<20} {s['total_return_pct']:.1f}%")
print(f"{'CAGR %':<30} {'-9.0%':<20} {s['cagr_pct']:.1f}%")
print(f"{'Max DD %':<30} {'28.1%':<20} {s['max_drawdown_pct']:.1f}%")
print(f"{'Sharpe':<30} {'-0.50':<20} {s['sharpe_ratio']:.3f}")
print(f"{'Avg holding days':<30} {'7.0':<20} {s['avg_trade_duration_days']:.1f}")
print()

print("Exit breakdown:")
print(f"{'take_profit':<20} {'339 (22%)':<20} {d['take_profit_exits']} ({d['take_profit_exits']/max(1,s['total_trades'])*100:.0f}%)")
print(f"{'trailing_stop':<20} {'1198 (78%)':<20} {d['trailing_stop_exits']} ({d['trailing_stop_exits']/max(1,s['total_trades'])*100:.0f}%)")
print(f"{'time_stop':<20} {'0 (0%)':<20} {d['time_stop_exits']} ({d['time_stop_exits']/max(1,s['total_trades'])*100:.0f}%)")
print(f"{'initial_stop':<20} {'0 (0%)':<20} {d['initial_stop_exits']}")
print()

# Trades per year
t = pd.read_csv(f"{BASE}/trades.csv")
t["entry_date"] = pd.to_datetime(t["entry_date"])
t["year"] = t["entry_date"].dt.year
print("Trades per year:")
print(f"{'Year':<8} {'Before n':<12} {'Before WR':<10} {'After n':<12} {'After WR':<10} {'After PnL':<12}")
print("-" * 60)
for y in sorted(t["year"].unique()):
    grp = t[t["year"] == y]
    wr = (grp["return_pct"] > 0).mean() * 100
    pnl = grp["pnl"].sum()
    # Before data from earlier analysis
    before_n = {2020: 502, 2021: 514, 2022: 521, 2023: 0, 2024: 0, 2025: 0}.get(y, 0)
    before_wr = {2020: 42.4, 2021: 38.3, 2022: 29.4}.get(y, 0)
    print(f"{y:<8} {before_n:<12} {before_wr:<10.1f}% {len(grp):<12} {wr:<10.1f}% {pnl:<12.0f}")

# Regime
mr = pd.read_csv(f"{BASE}/market_regimes.csv")
print(f"\nRegime distribution: {mr['market_regime'].value_counts().to_dict()}")

# Phase2
with open(f"{BASE}/phase2_risk_summary.json") as f:
    p2 = json.load(f)
print(f"Phase2: {p2.get('entries_total')} entries, {p2.get('entries_blocked_by_regime')} blocked by regime")
print(f"Rotation: triggered={p2.get('rotation_triggered')}, cum_return={p2.get('rotation_cumulative_return')}")
print(f"Breakout blocked: {d.get('blocked_by_breakout', 0)}")

# Holding buckets
print("\nHolding duration vs win rate:")
bins = [0, 3, 5, 10, 15, 20, 100]
labels = ["1-3j", "4-5j", "6-10j", "11-15j", "16-20j", "21j+"]
t["bucket"] = pd.cut(t["holding_days"], bins=bins, labels=labels)
for b in labels:
    sub = t[t["bucket"] == b]
    if len(sub) > 0:
        wr = (sub["return_pct"] > 0).mean() * 100
        print(f"  {b}: n={len(sub):>4}  win_rate={wr:.1f}%  mean_ret={sub['return_pct'].mean():.2f}%")
