"""R3 v2 — replay corrige : trailing base sur PREVIOUS peak (J-1), activation a la
date watcher officielle. Validation vs sorties officielles.
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
    idx = {sym: g.reset_index(drop=True) for sym, g in df.groupby("symbol", sort=False)}
    return idx

def replay_trade(side, entry, entry_date, g, ts_pct, init_stop, tp_price,
                 act_date=None, act_r=None, risk_per_share=None, time_stop_days=20,
                 min_tp_progress=0.5, near_zero=0.005):
    """Replay moteur corrige : trailing base sur peak/trough de la VEILLE.
    act_date: date officielle d'activation (validation). Si None -> regle par act_r.
    Retourne (exit_date, exit_price, reason, ret_pct).
    """
    rows = g[g["trade_date"] >= entry_date].head(90)
    if len(rows) == 0:
        return None, None, "no_data", 0.0
    peak = entry   # peak accumule J-1 (avant jour courant)
    trough = entry
    for i, (_, row) in enumerate(rows.iterrows()):
        o, h, l, c = row["open"], row["high"], row["low"], row["close"]
        # trailing du jour J base sur peak/trough accumules AVANT ce jour
        ts_level = (peak * (1 - ts_pct)) if side == "buy" else (trough * (1 + ts_pct))
        # activation : date officielle OU regle R
        if act_date is not None:
            armed = row["trade_date"].normalize() >= pd.Timestamp(act_date).normalize()
        elif act_r is not None:
            if act_r == 0:
                armed = i >= 1  # watcher effective J+1
            else:
                # R-multiple : s'arme quand le prix a bouge de act_r * risk
                if side == "buy":
                    armed = (max(peak, h) >= entry + act_r * risk_per_share) if risk_per_share else False
                else:
                    armed = (min(trough, l) <= entry - act_r * risk_per_share) if risk_per_share else False
        else:
            armed = True
        # resolutions (meme ordre que resolve_intrabar_exit)
        hit_init = (not armed) and init_stop is not None and (
            (side == "buy" and l <= init_stop) or (side == "sell" and h >= init_stop))
        hit_tp = (side == "buy" and h >= tp_price) or (side == "sell" and l <= tp_price)
        hit_ts = armed and ((side == "buy" and l <= ts_level) or (side == "sell" and h >= ts_level))
        if hit_init and (hit_ts or (init_stop >= ts_level if side == "buy" else init_stop <= ts_level)):
            px = init_stop
            reason = "initial_stop"
        elif hit_tp and hit_ts:
            px = ts_level  # conservative -> TS gagne
            reason = "trailing_stop"
        elif hit_ts:
            px = ts_level
            reason = "trailing_stop"
        elif hit_tp:
            px = tp_price
            reason = "take_profit"
        elif hit_init:
            px = init_stop
            reason = "initial_stop"
        else:
            # time stop : le moteur ne sort a 20j que si progression TP insuffisante
            if i + 1 >= time_stop_days:
                if side == "buy":
                    obj_move = max(tp_price - entry, 0.0)
                    cur_move = max(c - entry, 0.0)
                else:
                    obj_move = max(entry - tp_price, 0.0)
                    cur_move = max(entry - c, 0.0)
                tp_progress = (cur_move / obj_move) if obj_move > 0 else 0.0
                close_ret = (c / entry - 1) * 100 if side == "buy" else (entry / c - 1) * 100
                if tp_progress < min_tp_progress or abs(close_ret) <= near_zero * 100:
                    px = c
                    reason = "time_stop"
                else:
                    peak = max(peak, h)
                    trough = min(trough, l)
                    continue
            else:
                peak = max(peak, h)
                trough = min(trough, l)
                continue
        ret = (px / entry - 1) * 100 if side == "buy" else (entry / px - 1) * 100
        return row["trade_date"], px, reason, ret
    last = rows.iloc[-1]
    px = last["close"]
    ret = (px / entry - 1) * 100 if side == "buy" else (entry / px - 1) * 100
    return last["trade_date"], px, "end_of_data", ret

print("=" * 100)
print("VALIDATION v2 (previous peak + date watcher officielle)")
print("=" * 100)
for r, cpath in CACHE.items():
    df = pd.read_csv(ROOT / r / "trade_audit_log.csv")
    tr = df[df["pnl"].notna()].copy()
    tr["entry_date"] = pd.to_datetime(tr["entry_date"])
    tr["watcher_transition_effective_date"] = pd.to_datetime(tr["watcher_transition_effective_date"], errors="coerce")
    idx = load_ohlcv(cpath)
    diffs = []
    for _, t in tr.iterrows():
        g = idx.get(t["symbol"])
        if g is None:
            continue
        side = t["side"]
        ts_pct = t["replay_trailing_stop_pct"]
        tp_price = t["replay_take_profit_price"]
        init_stop = t["replay_initial_stop_price"]
        act_date = t["watcher_transition_effective_date"]
        d, px, reason, ret = replay_trade(side, t["entry_price"], t["entry_date"], g,
                                          ts_pct, init_stop, tp_price, act_date=act_date)
        if d is None:
            continue
        diffs.append({"sym": t["symbol"], "side": side, "official": t["return_pct"], "engine": ret,
                      "diff": ret - t["return_pct"], "o_reason": t["replay_exit_reason"], "e_reason": reason})
    ddf = pd.DataFrame(diffs)
    n_ok = (ddf["diff"].abs() < 0.5).sum()
    print(f"\n### {r} : N={len(ddf)}  |diff|<0.5% : {n_ok} ({n_ok/len(ddf)*100:.0f}%)")
    print(f"  diff mean={ddf['diff'].mean():.2f}%  median={ddf['diff'].median():.2f}%  |diff| mean={ddf['diff'].abs().mean():.2f}%")
    print(f"  official mean={ddf['official'].mean():.2f}%  engine mean={ddf['engine'].mean():.2f}%")
    print("  divergences (|diff|>=0.5):")
    bad = ddf[ddf["diff"].abs() >= 0.5]
    print(bad.sort_values("diff", key=abs, ascending=False).head(10)[
        ["sym", "side", "official", "engine", "diff", "o_reason", "e_reason"]].to_string(index=False))
