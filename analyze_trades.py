import pandas as pd

df = pd.read_csv(r"F:\projets\artifacts\backtesting\trades.csv")
df["notional"] = df["quantity"].abs() * df["entry_price"]
df["entry_fee_pct"] = (df["entry_cost"] - df["notional"]) / df["notional"] * 100
df["exit_fee_pct"] = (abs(df["proceeds"]) - df["notional"]) / df["notional"] * 100

print("Trades:", len(df))
print("Entry fee pct stats:")
print(df["entry_fee_pct"].describe().to_string())
print()
print("Exit fee pct stats:")
print(df["exit_fee_pct"].describe().to_string())
print()
print("Worst 10 entry fees:")
print(df.nlargest(10, "entry_fee_pct")[["symbol", "entry_date", "entry_price", "notional", "entry_cost", "entry_fee_pct"]].to_string())
print()
print("Worst 10 exit fees:")
print(df.nlargest(10, "exit_fee_pct")[["symbol", "exit_date", "exit_price", "notional", "proceeds", "exit_fee_pct"]].to_string())
print()
print("Symbols traded:", df["symbol"].nunique())
print("Sample of traded symbols:", sorted(df["symbol"].unique())[:30])
