"""TP check v2 : le replay_take_profit_price est-il bien le TP utilise pour sortir ?
Compare replay_exit_price vs replay_take_profit_price sur les exits take_profit.
"""
import pandas as pd
import numpy as np
from pathlib import Path

ROOT = Path("artifacts/backtesting")
for r in ["cmp_b25_h20_2025_prodparity_p23_m8",
          "cmp_b25_h20_2026_prodparity_p23_m8"]:
    year = "2025" if "2025" in r else "2026"
    df = pd.read_csv(ROOT / r / "trade_audit_log.csv")
    tr = df[df["pnl"].notna()].copy()
    tp_exits = tr[tr["replay_exit_reason"] == "take_profit"].copy()
    print(f"\n### {year} : exits take_profit = {len(tp_exits)}")
    if len(tp_exits):
        # le prix de sortie == TP ?
        tp_exits["exit_vs_tp"] = (tp_exits["replay_exit_price"] - tp_exits["replay_take_profit_price"]).abs()
        print("  match |exit - tp| < 0.01 :", (tp_exits["exit_vs_tp"] < 0.01).sum(), "/", len(tp_exits))
        print("  |exit - tp| stats :", tp_exits["exit_vs_tp"].describe().to_dict())
        print("\n  detail :")
        print(tp_exits[["symbol", "side", "entry_price", "replay_take_profit_price",
                        "replay_exit_price", "return_pct", "holding_days"]].to_string(index=False))
