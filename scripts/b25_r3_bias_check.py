import pandas as pd
import numpy as np
from pathlib import Path

ROOT = Path("artifacts/backtesting")
# comparer somme PnL officiel vs baseline replay pour 2026
r = "cmp_b25_h20_2026_prodparity_p23_m8"
df = pd.read_csv(ROOT / r / "trade_audit_log.csv")
tr = df[df["pnl"].notna()].copy()
print("=== 2026 officiel ===")
print("sum pnl:", tr["pnl"].sum())
print("sum pnl long:", tr[tr["side"]=="buy"]["pnl"].sum())
print("sum pnl short:", tr[tr["side"]=="sell"]["pnl"].sum())
print("N:", len(tr))
# top trades par pnl
print(tr.nlargest(8, "pnl")[["symbol","side","entry_date","replay_exit_date","pnl","return_pct","replay_exit_reason","holding_days"] if "holding_days" in tr.columns else ["symbol","side","entry_date","replay_exit_date","pnl","return_pct","replay_exit_reason"]].to_string(index=False))
print()
# sorties
print(tr["replay_exit_reason"].value_counts().to_dict())
print("holding_days stats:", tr["holding_days"].describe().to_dict() if "holding_days" in tr.columns else "N/A")
print("replay_exit_date range:", pd.to_datetime(tr["replay_exit_date"]).min(), "->", pd.to_datetime(tr["replay_exit_date"]).max())
