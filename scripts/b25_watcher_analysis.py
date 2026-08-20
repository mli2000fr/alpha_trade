import pandas as pd
from pathlib import Path

d = Path("artifacts/backtesting")
r = "cmp_b25_h20_2025_prodparity_p23_m8"
df = pd.read_csv(d / r / "trade_audit_log.csv")
tr = df[df["pnl"].notna()].copy()
tr["entry_date"] = pd.to_datetime(tr["entry_date"])
tr["replay_exit_date"] = pd.to_datetime(tr["replay_exit_date"], errors="coerce")

# Colonnes watcher dispo
wc = [c for c in tr.columns if "watcher" in c or "transition" in c or "trigger" in c or "activation" in c]
print("Colonnes watcher:", wc)

# Analyse watcher_transition_state
print("\nwatcher_transition_state:", tr["watcher_transition_state"].value_counts(dropna=False).to_dict())

# activation vs entry : est-ce que le trailing est actif des J0?
tr["watcher_trigger_date"] = pd.to_datetime(tr["watcher_trigger_date"], errors="coerce")
tr["watcher_transition_effective_date"] = pd.to_datetime(tr["watcher_transition_effective_date"], errors="coerce")
tr["delay_activation_days"] = (tr["watcher_transition_effective_date"] - tr["entry_date"]).dt.days
print("\ndelay activation (watcher effective - entry) stats:")
print(tr["delay_activation_days"].describe().to_string())
print("\nvalue_counts:", tr["delay_activation_days"].value_counts().sort_index().to_dict())

# initial stop vs entry : distance du stop initial
tr["init_stop_dist_pct"] = (tr["entry_price"] - tr["replay_initial_stop_price"]) / tr["entry_price"] * 100
tr.loc[tr["side"] == "sell", "init_stop_dist_pct"] = (tr["replay_initial_stop_price"] - tr["entry_price"]) / tr["entry_price"] * 100
print("\ninitial stop distance % (abs) stats:")
print(tr["init_stop_dist_pct"].abs().describe().to_string())
