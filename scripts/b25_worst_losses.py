import pandas as pd
from pathlib import Path

d = Path("artifacts/backtesting")
for r in ["cmp_b25_h20_2025_prodparity_p23_m8",
          "cmp_b25_h20_2026_prodparity_p23_m8"]:
    df = pd.read_csv(d / r / "trade_audit_log.csv")
    tr = df[df["pnl"].notna()].copy()
    tr["entry_date"] = pd.to_datetime(tr["entry_date"])
    tr["replay_exit_date"] = pd.to_datetime(tr["replay_exit_date"], errors="coerce")
    tr["watcher_transition_effective_date"] = pd.to_datetime(tr["watcher_transition_effective_date"], errors="coerce")
    tr["delay_act"] = (tr["watcher_transition_effective_date"] - tr["entry_date"]).dt.days
    tr["holding_days_"] = (tr["replay_exit_date"] - tr["entry_date"]).dt.days

    print(f"=== {r} : 15 pires pertes ===")
    cols = ["symbol", "side", "entry_date", "replay_exit_date", "holding_days_", "delay_act",
            "entry_price", "replay_exit_price", "exit_price", "replay_exit_reason",
            "replay_trailing_stop_pct", "replay_initial_stop_price", "return_pct", "pnl"]
    worst = tr.nsmallest(15, "return_pct")[cols]
    print(worst.to_string(index=False))
    print("\n  # exit_reason parmi pires 15:", worst["replay_exit_reason"].value_counts().to_dict())
    print()
