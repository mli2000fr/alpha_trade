"""TS-EXP complement : positions 20-42j NON coupees par le time_stop (prolongation satisfaite)
-> futurs winners ou perdants qui continuent ? + detail pertes evitees.
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
                 time_stop_enabled, time_stop_days=20, min_tp_progress=0.5,
                 near_zero=0.005, max_window=90):
    rows = g[g["trade_date"] >= entry_date].head(max_window)
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
            if time_stop_enabled and i + 1 >= time_stop_days:
                if side == "buy":
                    obj_move = max(tp_price - entry, 0.0); cur_move = max(c - entry, 0.0)
                else:
                    obj_move = max(entry - tp_price, 0.0); cur_move = max(entry - c, 0.0)
                tp_progress = (cur_move / obj_move) if obj_move > 0 else 0.0
                close_ret = (c / entry - 1) * 100 if side == "buy" else (entry / c - 1) * 100
                if tp_progress < min_tp_progress or abs(close_ret) <= near_zero * 100:
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
    tr["replay_exit_date"] = pd.to_datetime(tr["replay_exit_date"], errors="coerce")
    tr["watcher_transition_effective_date"] = pd.to_datetime(tr["watcher_transition_effective_date"], errors="coerce")
    d0 = tr["entry_date"].dt.date.to_numpy(dtype="datetime64[D]")
    d1 = tr["replay_exit_date"].dt.date.to_numpy(dtype="datetime64[D]")
    tr["biz_days"] = np.busday_count(d0, d1)
    idx = load_ohlcv(cpath)

    # positions 20-42j de la baseline : quel aurait ete l'impact time_stop ?
    print(f"\n{'='*100}\n### {year} : positions >= 20j ouvrés (baseline production)\n{'='*100}")
    long_held = tr[tr["biz_days"] >= 20].copy()
    rows = []
    for _, t in long_held.iterrows():
        g = idx.get(t["symbol"])
        if g is None:
            continue
        d, px, reason, ret_ts = replay_trade(t["side"], t["entry_price"], t["entry_date"], g,
                                             t["replay_trailing_stop_pct"], t["replay_initial_stop_price"],
                                             t["replay_take_profit_price"], t["watcher_transition_effective_date"],
                                             time_stop_enabled=True)
        rows.append({"symbol": t["symbol"], "side": t["side"], "entry_date": t["entry_date"].date(),
                     "biz_days": t["biz_days"], "official_ret": t["return_pct"],
                     "official_reason": t["replay_exit_reason"], "ts_ret": ret_ts, "ts_reason": reason,
                     "ts_fired": reason == "time_stop"})
    lh = pd.DataFrame(rows)
    fired = lh[lh["ts_fired"]]
    kept = lh[~lh["ts_fired"]]
    print(f"  total >=20j : {len(lh)}   |  coupees par ts : {len(fired)}   |  prolongees : {len(kept)}")
    if len(kept):
        print(f"\n  PROLONGEES (tp_progress>=0.5 ou |ret|>0.5%) -> futur winner ou perdant ?")
        print("   ", kept[["symbol", "side", "biz_days", "official_ret", "official_reason", "ts_reason"]].to_string(index=False).replace("\n", "\n    "))
        n_win = (kept["official_ret"] > 0).sum()
        n_loss = (kept["official_ret"] < 0).sum()
        print(f"   -> parmi les prolongees : winners {n_win}, perdants {n_loss}")
        print(f"   -> PnL des prolongees (officiel) : {kept['official_ret'].sum():+.1f} pts")
    if len(fired):
        print(f"\n  COUPEES par time_stop (si actif) :")
        print("   ", fired[["symbol", "side", "biz_days", "official_ret", "official_reason", "ts_ret", "ts_reason"]].to_string(index=False).replace("\n", "\n    "))
        # gain/loss si coupe vs baseline
        win_sacr = fired[fired["official_ret"] > 0]
        loss_avoid = fired[fired["official_ret"] < 0]
        print(f"   -> winners sacrifiés (official_ret>0) : {len(win_sacr)}  pts officiels {win_sacr['official_ret'].sum():+.1f} -> pts ts {win_sacr['ts_ret'].sum():+.1f}")
        print(f"   -> pertes évitées (official_ret<0)     : {len(loss_avoid)}  pts officiels {loss_avoid['official_ret'].sum():+.1f} -> pts ts {loss_avoid['ts_ret'].sum():+.1f}")
