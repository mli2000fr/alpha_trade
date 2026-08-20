"""R2 — Audit mécanique du trailing. Compare pour 10 trades :
moteur officiel (fill intrabar au niveau trailing, activation J+1, ts_pct côté)
vs replay naïf précédent (close-based, activation immédiate, 7% partout).
"""
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

# 10 trades représentatifs (mix longs/shorts, trailing + initial stop)
sel = tr[tr["symbol"].isin(["TTD", "FLYW", "FMC", "GME", "DV", "OPLN", "HAS", "KN", "SMCI", "MD"])].head(10).copy()

def engine_replay(t, rows):
    """Reproduction EXACTE du moteur : trailing actif a partir de J+1 (delay_act),
    peak/trough tracking, fill au niveau trailing le jour ou low/high le touche."""
    side = t["side"]
    entry = t["entry_price"]
    ts_pct = t["replay_trailing_stop_pct"]
    init_stop = t["replay_initial_stop_price"]
    act_date = t.get("watcher_transition_effective_date")
    act_date = pd.to_datetime(act_date) if pd.notna(act_date) else None
    peak = entry
    trough = entry
    for _, row in rows.iterrows():
        o, h, l, c = row["open"], row["high"], row["low"], row["close"]
        # trailing armé ?
        armed = act_date is not None and row["trade_date"].normalize() >= pd.Timestamp(act_date).normalize()
        ts_level = (peak * (1 - ts_pct)) if side == "buy" else (trough * (1 + ts_pct))
        # initial stop le jour J0 (avant armement)
        if not armed and init_stop and pd.notna(init_stop):
            if side == "buy" and l <= init_stop:
                return row["trade_date"], init_stop, "initial_stop(J0)", (init_stop/entry - 1)*100
            if side == "sell" and h >= init_stop:
                return row["trade_date"], init_stop, "initial_stop(J0)", (entry/init_stop - 1)*100
        # trailing
        if armed:
            if side == "buy" and l <= ts_level:
                return row["trade_date"], ts_level, "trailing_stop", (ts_level/entry - 1)*100
            if side == "sell" and h >= ts_level:
                return row["trade_date"], ts_level, "trailing_stop", (entry/ts_level - 1)*100
        # time stop 20j -> close
        # (approx)
        peak = max(peak, h)
        trough = min(trough, l)
    last = rows.iloc[-1]
    ret = (last["close"]/entry - 1)*100 if side == "buy" else (entry/last["close"] - 1)*100
    return last["trade_date"], last["close"], "time_stop", ret

def naive_replay(t, rows):
    """Replay naif precedent : close-based, activation immediate, 7% partout."""
    side = t["side"]
    entry = t["entry_price"]
    peak = entry
    trough = entry
    for i, (_, row) in enumerate(rows.iterrows()):
        peak = max(peak, row["high"])
        trough = min(trough, row["low"])
        if side == "buy" and row["close"] <= peak * 0.93:
            return row["trade_date"], row["close"], "trailing(close)", (row["close"]/entry - 1)*100
        if side == "sell" and row["close"] >= trough * 1.07:
            return row["trade_date"], row["close"], "trailing(close)", (entry/row["close"] - 1)*100
        if i >= 19:
            ret = (row["close"]/entry - 1)*100 if side == "buy" else (entry/row["close"] - 1)*100
            return row["trade_date"], row["close"], "time_stop", ret
    return None, None, None, None

print(f"{'sym':6} {'side':5} {'entry':>8} {'MOTEUR':>12} {'fill':>8} {'ret%':>7} | {'NAIF':>12} {'fill':>8} {'ret%':>7} | {'ecart':>7}")
print("-"*95)
rows_out = []
for _, t in sel.iterrows():
    ed = t["replay_exit_date"]
    rows = cache[(cache["symbol"] == t["symbol"]) & (cache["trade_date"] >= t["entry_date"]) &
                 (cache["trade_date"] <= ed)].sort_values("trade_date")
    if len(rows) == 0:
        continue
    em_date, em_price, em_reason, em_ret = engine_replay(t, rows)
    nm_date, nm_price, nm_reason, nm_ret = naive_replay(t, rows)
    actual = t["return_pct"]
    nm_price_s = f"{nm_price:.4f}" if nm_price is not None else "-"
    nm_ret_s = f"{nm_ret:.2f}" if nm_ret is not None else "-"
    ecart = f"{em_ret - nm_ret:.2f}" if nm_ret is not None else "-"
    print(f"{t['symbol']:6} {t['side']:5} {t['entry_price']:8.4f} {em_reason:>12} {em_price:8.4f} {em_ret:7.2f} | {nm_reason or '-':>12} {nm_price_s:>8} {nm_ret_s:>7} | {ecart:>7}")
    rows_out.append({"symbol": t["symbol"], "side": t["side"], "actual_ret": actual,
                     "engine_ret": em_ret, "naive_ret": nm_ret, "engine_reason": em_reason, "naive_reason": nm_reason})

rdf = pd.DataFrame(rows_out)
print("\n=== moyenne des retours ===")
print(f"actual:  {rdf['actual_ret'].mean():.2f}%")
print(f"engine:  {rdf['engine_ret'].mean():.2f}%")
print(f"naive:   {rdf['naive_ret'].mean():.2f}%")
