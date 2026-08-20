import pandas as pd
import numpy as np
from pathlib import Path

d = Path("artifacts/backtesting")
r = "cmp_b25_h20_2025_prodparity_p23_m8"
df = pd.read_csv(d / r / "trade_audit_log.csv")
tr = df[df["pnl"].notna()].copy()
tr["entry_date"] = pd.to_datetime(tr["entry_date"])
tr["replay_exit_date"] = pd.to_datetime(tr["replay_exit_date"], errors="coerce")

cache = pd.read_parquet("artifacts/backtest_cache/a4060dc97e3f_ohlcv_2025-01-02_2025-12-31.parquet",
                        columns=["symbol", "trade_date", "open", "high", "low", "close"])
cache["trade_date"] = pd.to_datetime(cache["trade_date"])
cache["symbol"] = cache["symbol"].astype(str).str.upper()
cache = cache.sort_values(["symbol", "trade_date"])

# Sélectionner 10 trades représentatifs : 5 longs trailing 7%, 3 shorts trailing risk-based, 2 initial stop / J0-J1
sel_syms = ["TTD", "FLYW", "FMC", "GME", "DV",   # longs
            "OPLN", "HAS", "KN",                 # shorts risk-based
            "SMCI", "MD"]                        # longs divers
sel = tr[tr["symbol"].isin(sel_syms)].head(10).copy()

def trailing_level_long(peak, pct): return peak * (1 - pct)
def trailing_level_short(trough, pct): return trough * (1 + pct)

for _, t in sel.iterrows():
    sym = t["symbol"]
    side = t["side"]
    entry = t["entry_price"]
    entry_d = t["entry_date"]
    ed = t["replay_exit_date"]
    rows = cache[(cache["symbol"] == sym) & (cache["trade_date"] >= entry_d) &
                 (cache["trade_date"] <= ed)].sort_values("trade_date")
    print(f"\n=== {sym} {side}  entry={entry:.4f} {entry_d.date()}  exit={t['replay_exit_price']:.4f} {ed.date() if pd.notna(ed) else '?'}  reason={t['replay_exit_reason']}  ret={t['return_pct']:.2f}%  ts_pct={t['replay_trailing_stop_pct']:.4f}")
    print(f"    init_stop={t['replay_initial_stop_price']:.4f}  act_price={t['replay_trailing_activation_price']:.4f}  delay_act={t['delay_act'] if 'delay_act' in tr.columns else '?'}")
    peak = entry
    trough = entry
    for _, row in rows.iterrows():
        o, h, l, c = row["open"], row["high"], row["low"], row["close"]
        new_peak = max(peak, h)
        new_trough = min(trough, l)
        ts = trailing_level_long(new_peak, t["replay_trailing_stop_pct"]) if side == "buy" else trailing_level_short(new_trough, t["replay_trailing_stop_pct"])
        trig = None
        if side == "buy" and l <= ts: trig = "TS"
        if side == "sell" and h >= ts: trig = "TS"
        is_exit_day = (row["trade_date"].normalize() == pd.Timestamp(t["replay_exit_date"]).normalize()) if pd.notna(ed) else False
        mark = " <== EXIT" if is_exit_day else ""
        print(f"    {row['trade_date'].date()}  O={o:.4f} H={h:.4f} L={l:.4f} C={c:.4f}  peak={new_peak:.4f}  TS={ts:.4f}  trig={trig}{mark}")
        peak, trough = new_peak, new_trough
