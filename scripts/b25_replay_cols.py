import pandas as pd
from pathlib import Path

d = Path("artifacts/backtesting")
r = "cmp_b25_h20_2025_prodparity_p23_m8"
df = pd.read_csv(d / r / "trade_audit_log.csv")
tr = df[df["pnl"].notna()].copy()

# colonnes replay utiles
rc = [c for c in tr.columns if c.startswith("replay_") or c in
      ("entry_price", "entry_date", "exit_price", "exit_date", "exit_reason",
       "return_pct", "pnl", "side", "holding_days", "symbol")]
print("Colonnes replay dispo:", [c for c in tr.columns if c.startswith("replay_")])

print("\n=== Valeurs distinctes replay_trailing_activation_mode ===")
print(tr["replay_trailing_activation_mode"].value_counts(dropna=False).to_string())

print("\n=== replay_trailing_stop_pct distribution ===")
print(tr["replay_trailing_stop_pct"].describe().to_string())
print("\npar side:")
print(tr.groupby("side")["replay_trailing_stop_pct"].describe().to_string())

print("\n=== replay_initial_stop_price vs replay_trailing_activation_price (head) ===")
cols = ["symbol", "side", "entry_price", "replay_initial_stop_price",
        "replay_trailing_activation_price", "replay_trailing_stop_pct",
        "replay_exit_price", "exit_price", "replay_exit_reason", "return_pct"]
print(tr[cols].head(12).to_string(index=False))
