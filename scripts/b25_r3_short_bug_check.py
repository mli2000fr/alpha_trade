"""Controle : le bug de fenetre 20j touchait-il aussi les SHORT ?
Compare replay SHORT avec ancienne fenetre (23j) vs nouvelle (90j) vs officiel.
"""
import pandas as pd
import numpy as np
from pathlib import Path

ROOT = Path("artifacts/backtesting")
CACHE = {
    "cmp_b25_h20_2025_prodparity_p23_m8": "artifacts/backtest_cache/a4060dc97e3f_ohlcv_2025-01-02_2025-12-31.parquet",
    "cmp_b25_h20_2026_prodparity_p23_m8": "artifacts/backtest_cache/2a7cecd22ad4_ohlcv_2026-01-02_2026-05-31.parquet",
}

def load_ohlcv(path):
    df = pd.read_parquet(path, columns=["symbol", "trade_date", "open", "high", "low", "close"])
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    df["symbol"] = df["symbol"].astype(str).str.upper()
    df = df.sort_values(["symbol", "trade_date"]).reset_index(drop=True)
    return {sym: g.reset_index(drop=True) for sym, g in df.groupby("symbol", sort=False)}

def replay_trade(side, entry, entry_date, g, ts_pct, init_stop, tp_price, act_date,
                 window):
    rows = g[g["trade_date"] >= entry_date].head(window)
    if len(rows) == 0:
        return None, None, "no_data", 0.0
    peak = entry; trough = entry
    for i, (_, row) in enumerate(rows.iterrows()):
        o, h, l, c = row["open"], row["high"], row["low"], row["close"]
        ts_level = (peak * (1 - ts_pct)) if side == "buy" else (trough * (1 + ts_pct))
        armed = row["trade_date"].normalize() >= pd.Timestamp(act_date).normalize()
        hit_init = (not armed) and init_stop is not None and (
            (side == "buy" and l <= init_stop) or (side == "sell" and h >= init_stop))
        hit_tp = (side == "buy" and h >= tp_price) or (side == "sell" and l <= tp_price)
        hit_ts = armed and ((side == "buy" and l <= ts_level) or (side == "sell" and h >= ts_level))
        if hit_init and (hit_ts or (init_stop >= ts_level if side == "buy" else init_stop <= ts_level)):
            px, reason = init_stop, "initial_stop"
        elif hit_tp and hit_ts:
            px, reason = ts_level, "trailing_stop"
        elif hit_ts:
            px, reason = ts_level, "trailing_stop"
        elif hit_tp:
            px, reason = tp_price, "take_profit"
        elif hit_init:
            px, reason = init_stop, "initial_stop"
        else:
            if i + 1 >= 20:
                if side == "buy":
                    obj_move = max(tp_price - entry, 0.0); cur_move = max(c - entry, 0.0)
                else:
                    obj_move = max(entry - tp_price, 0.0); cur_move = max(entry - c, 0.0)
                tp_progress = (cur_move / obj_move) if obj_move > 0 else 0.0
                close_ret = (c / entry - 1) * 100 if side == "buy" else (entry / c - 1) * 100
                if tp_progress < 0.5 or abs(close_ret) <= 0.005 * 100:
                    px, reason = c, "time_stop"
                else:
                    peak = max(peak, h); trough = min(trough, l)
                    continue
            else:
                peak = max(peak, h); trough = min(trough, l)
                continue
        ret = (px / entry - 1) * 100 if side == "buy" else (entry / px - 1) * 100
        return row["trade_date"], px, reason, ret
    last = rows.iloc[-1]
    px = last["close"]
    ret = (px / entry - 1) * 100 if side == "buy" else (entry / px - 1) * 100
    return last["trade_date"], px, "end_of_data", ret

for r, cpath in CACHE.items():
    year = "2025" if "2025" in r else "2026"
    df = pd.read_csv(ROOT / r / "trade_audit_log.csv")
    tr = df[df["pnl"].notna()].copy()
    tr["entry_date"] = pd.to_datetime(tr["entry_date"])
    tr["watcher_transition_effective_date"] = pd.to_datetime(tr["watcher_transition_effective_date"], errors="coerce")
    idx = load_ohlcv(cpath)

    shorts = tr[tr["side"] == "sell"].copy()
    print(f"\n{'='*96}\n### {year} : SHORT take_profit officiels  (N shorts={len(shorts)}, TP officiels={shorts['replay_exit_reason'].eq('take_profit').sum()})\n{'='*96}")
    rows = []
    for _, t in shorts.iterrows():
        g = idx.get(t["symbol"])
        if g is None:
            continue
        d23, p23, r23, ret23 = replay_trade(t["side"], t["entry_price"], t["entry_date"], g,
                                            t["replay_trailing_stop_pct"], t["replay_initial_stop_price"],
                                            t["replay_take_profit_price"], t["watcher_transition_effective_date"], 23)
        d90, p90, r90, ret90 = replay_trade(t["side"], t["entry_price"], t["entry_date"], g,
                                            t["replay_trailing_stop_pct"], t["replay_initial_stop_price"],
                                            t["replay_take_profit_price"], t["watcher_transition_effective_date"], 90)
        rows.append({"symbol": t["symbol"], "entry_date": t["entry_date"].date(),
                     "o_ret": t["return_pct"], "o_reason": t["replay_exit_reason"],
                     "ret23": ret23, "r23": r23, "ret90": ret90, "r90": r90,
                     "diff23": ret23 - t["return_pct"], "diff90": ret90 - t["return_pct"]})
    sdf = pd.DataFrame(rows)
    ok23 = (sdf["diff23"].abs() < 0.5).mean() * 100
    ok90 = (sdf["diff90"].abs() < 0.5).mean() * 100
    print(f"SHORT match rate (<0.5%):  ancienne fenetre 23j = {ok23:.0f}%   nouvelle fenetre 90j = {ok90:.0f}%")
    print("\nSHORT ameliore par le fix (|diff90| < |diff23|) etait TP officiel:")
    improved = sdf[(sdf["diff90"].abs() < sdf["diff23"].abs())]
    print(improved[["symbol", "entry_date", "o_ret", "o_reason", "ret23", "r23", "ret90", "r90"]].head(15).to_string(index=False))
    print("\nSHORT encore en divergence apres fix (|diff90|>=0.5):")
    still = sdf[sdf["diff90"].abs() >= 0.5]
    print(still.sort_values("diff90", key=abs, ascending=False).head(12)[["symbol", "entry_date", "o_ret", "o_reason", "ret90", "r90"]].to_string(index=False))
