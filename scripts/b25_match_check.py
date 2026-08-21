import pandas as pd

tr = pd.read_csv("artifacts/benchmarks/OOS2026_B25_P14_m8_v1/trades.csv")
match = tr[tr["legacy_trade_match"] == True]  # noqa: E712
print("=== 2026 : legacy_trade_match=True ===")
print("n:", len(match))
print("side:", match["side"].value_counts().to_dict())
print("exit_reason:", match["exit_reason"].value_counts().to_dict())
print("win rate:", (match["return_pct"] > 0).mean() * 100)
print("pnl total:", match["pnl"].sum())
print("pnl long:", match.loc[match["side"] == "buy", "pnl"].sum())
print("pnl short:", match.loc[match["side"] == "sell", "pnl"].sum())
print("return_pct describe:", match["return_pct"].describe().to_dict())
print()
print("=== tous closed ===")
closed = tr[tr["trade_status"] == "closed"]
print("n closed:", len(closed))
print("pnl sum:", closed["pnl"].sum())
