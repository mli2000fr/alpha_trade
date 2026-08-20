import pandas as pd
from pathlib import Path

d = Path("artifacts/backtesting")
for r in ["cmp_b25_h20_2025_prodparity_p23_m8",
          "cmp_b25_h20_2026_prodparity_p23_m8"]:
    df = pd.read_csv(d / r / "trade_audit_log.csv")
    tr = df[df["pnl"].notna()].copy()
    print(f"=== {r} ===")
    for side, lab in [("buy", "LONG "), ("sell", "SHORT")]:
        sub = tr[tr["side"] == side]
        losses = sub[sub["return_pct"] < 0]
        ts_loss = losses[losses["replay_exit_reason"] == "trailing_stop"]
        print(f"  {lab}: N={len(sub)}  mean_ret={sub['return_pct'].mean():.2f}%  "
              f"pertes N={len(losses)} mean={losses['return_pct'].mean():.2f}%  "
              f"min={losses['return_pct'].min():.2f}%  "
              f"pertes TS mean={ts_loss['return_pct'].mean():.2f}% (N={len(ts_loss)})")
        print(f"       ts_pct: min={sub['replay_trailing_stop_pct'].min():.4f} med={sub['replay_trailing_stop_pct'].median():.4f} max={sub['replay_trailing_stop_pct'].max():.4f}")
    # pires pertes long (trailing 7% fixe) - pourquoi depassent 7%?
    print("  pires LONGS (ret<0):")
    wl = tr[(tr["side"]=="buy") & (tr["return_pct"]<0)].nsmallest(5, "return_pct")[["symbol","entry_price","replay_exit_price","replay_exit_reason","return_pct","holding_days_"] if "holding_days_" in tr.columns else ["symbol","entry_price","replay_exit_price","replay_exit_reason","return_pct"]]
    print(wl.to_string(index=False))
    print()
