import json
from pathlib import Path
import pandas as pd

# 1. params du run atrfix vs benchmark
for name in ["ihm2526_p14_atrfix", "ihm2526_ctl", "cmp_b25_h20_2026_prodparity_repro_h20cfg_m8",
             "oos2026_p14_h20risk", "ihm2526_p14_h20risk"]:
    rp = Path("artifacts/backtesting") / name / "report.json"
    if not rp.exists():
        print(f"### {name} : absent")
        continue
    j = json.loads(rp.read_text(encoding="utf-8"))
    p = j.get("params", {})
    s = j.get("summary", {})
    print(f"\n### {name}")
    print(f"  period: {p.get('start')} -> {p.get('end')}  max_pos: {p.get('max_positions')}")
    print(f"  ret={s.get('total_return_pct'):.2f}%  PF={s.get('profit_factor'):.3f}  DD={s.get('max_drawdown_pct'):.2f}%  trades={s.get('total_trades')}  win={s.get('win_rate_pct'):.1f}%")
    print(f"  L={s.get('long_pnl_total'):.0f} S={s.get('short_pnl_total'):.0f} net={s.get('pnl_net'):.0f}")
    # TP params
    for k in ["tp_atr_multiple", "tp_max_pct", "atr_risk_stop_multiple", "trailing_pct_long_override",
              "best_horizon", "engine_mode"]:
        if k in p:
            print(f"  {k} = {p[k]}")
    # TP rejoués
    tal = Path("artifacts/backtesting") / name / "trade_audit_log.csv"
    if tal.exists():
        df = pd.read_csv(tal)
        tr = df[df["pnl"].notna()]
        tp = (tr["replay_take_profit_price"] / tr["entry_price"] - 1) * 100
        tp = tp.where(tr["side"] == "buy", -tp)
        print(f"  TP distance stats: mean={tp.mean():.2f}% min={tp.min():.2f}% med={tp.median():.2f}% max={tp.max():.2f}%  N={len(tr)}")
        print(f"  exits: {tr['replay_exit_reason'].value_counts().to_dict()}")
