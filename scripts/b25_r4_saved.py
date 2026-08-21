"""R4 — Analyse sauvés/détériorés par variante (vs baseline 0R).
Pour chaque trade : baseline_ret vs variante_ret -> classe.
+ impact P&L net de chaque groupe + couts (commission 1bp + slippage 2bp RT).
"""
import pandas as pd
import numpy as np
from pathlib import Path

ROOT = Path("artifacts/backtesting")
CACHE = {
    "cmp_b25_h20_2025_prodparity_p23_m8": "artifacts/backtest_cache/a4060dc97e3f_ohlcv_2025-01-02_2025-12-31.parquet",
    "cmp_b25_h20_2026_prodparity_p23_m8": "artifacts/backtest_cache/2a7cecd22ad4_ohlcv_2026-01-02_2026-05-31.parquet",
}
VARIANTS = {"trail_1R": 1.0, "trail_2R": 2.0, "no_trailing": None}
COMM_BPS, SLIP_BPS = 1.0, 2.0

def load_ohlcv(path):
    df = pd.read_parquet(path, columns=["symbol", "trade_date", "open", "high", "low", "close"])
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    df["symbol"] = df["symbol"].astype(str).str.upper()
    df = df.sort_values(["symbol", "trade_date"]).reset_index(drop=True)
    return {sym: g.reset_index(drop=True) for sym, g in df.groupby("symbol", sort=False)}

def replay_trade(side, entry, entry_date, g, ts_pct, init_stop, tp_price, risk_per_share,
                 act_r=None, time_stop_days=20, min_tp_progress=0.5, near_zero=0.005):
    rows = g[g["trade_date"] >= entry_date].head(time_stop_days + 3)
    if len(rows) == 0:
        return None, None, "no_data", 0.0
    peak = entry; trough = entry
    for i, (_, row) in enumerate(rows.iterrows()):
        o, h, l, c = row["open"], row["high"], row["low"], row["close"]
        ts_level = (peak * (1 - ts_pct)) if side == "buy" else (trough * (1 + ts_pct))
        if act_r is None:
            armed = False
        elif act_r == 0:
            armed = i >= 1
        else:
            if side == "buy":
                armed = (max(peak, h) >= entry + act_r * risk_per_share) if risk_per_share else False
            else:
                armed = (min(trough, l) <= entry - act_r * risk_per_share) if risk_per_share else False
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
            if i + 1 >= time_stop_days:
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
    idx = load_ohlcv(cpath)

    # baseline ret
    base_rows = []
    for _, t in tr.iterrows():
        g = idx.get(t["symbol"])
        if g is None:
            continue
        risk = abs(t["entry_price"] - t["replay_initial_stop_price"]) if pd.notna(t["replay_initial_stop_price"]) else None
        d, px, reason, ret = replay_trade(t["side"], t["entry_price"], t["entry_date"], g,
                                          t["replay_trailing_stop_pct"], t["replay_initial_stop_price"],
                                          t["replay_take_profit_price"], risk, act_r=0.0)
        base_rows.append({"symbol": t["symbol"], "side": t["side"], "entry_date": t["entry_date"],
                          "entry_price": t["entry_price"], "base_ret": ret, "o_ret": t["return_pct"]})
    base = pd.DataFrame(base_rows)

    print(f"\n{'='*100}\n### {year} : R4 sauvés/détériorés (vs baseline 0R)\n{'='*100}")
    for vname, act_r in VARIANTS.items():
        rows = []
        for _, t in tr.iterrows():
            g = idx.get(t["symbol"])
            if g is None:
                continue
            risk = abs(t["entry_price"] - t["replay_initial_stop_price"]) if pd.notna(t["replay_initial_stop_price"]) else None
            d, px, reason, ret = replay_trade(t["side"], t["entry_price"], t["entry_date"], g,
                                              t["replay_trailing_stop_pct"], t["replay_initial_stop_price"],
                                              t["replay_take_profit_price"], risk, act_r=act_r)
            rows.append({"symbol": t["symbol"], "side": t["side"], "entry_date": t["entry_date"],
                         "entry_price": t["entry_price"], "var_ret": ret})
        var = pd.DataFrame(rows)
        m = base.merge(var, on=["symbol", "side", "entry_date", "entry_price"])
        m["base_pnl"] = m["o_ret"] / 100  # ~approximation normalisee (per unit)
        # classes
        bl = m["base_ret"]
        vr = m["var_ret"]
        saved = (bl < 0) & (vr > 0)          # perdant -> gagnant
        red = (bl < 0) & (vr < 0) & (vr > bl) # perte reduite
        reduced_win = (bl > 0) & (vr > 0) & (vr < bl)  # gain reduit
        worsened = (bl > 0) & (vr < 0)       # gagnant -> perdant
        loss_worse = (bl < 0) & (vr < bl)    # perte aggravee
        gain_better = (bl > 0) & (vr > bl)   # gain ameliore
        def impact(mask):
            return (m.loc[mask, "var_ret"].sum() - m.loc[mask, "base_ret"].sum())
        print(f"\n  --- {vname} ---")
        print(f"    trades N={len(m)}")
        print(f"    perdant->gagnant : {saved.sum():>3}  impact {impact(saved):+8.1f} pts")
        print(f"    perte reduite    : {red.sum():>3}  impact {impact(red):+8.1f} pts")
        print(f"    perte aggravee   : {loss_worse.sum():>3}  impact {impact(loss_worse):+8.1f} pts")
        print(f"    gain ameliore    : {gain_better.sum():>3}  impact {impact(gain_better):+8.1f} pts")
        print(f"    gain reduit      : {reduced_win.sum():>3}  impact {impact(reduced_win):+8.1f} pts")
        print(f"    gagnant->perdant : {worsened.sum():>3}  impact {impact(worsened):+8.1f} pts")
        print(f"    delta net (var-base) = {m['var_ret'].sum() - m['base_ret'].sum():+.2f} pts")
        # couts : meme nombre de trades, cout RT fixe par trade
        notional_avg = 5000.0  # approx : position moyenne ~5k (sizing equal weight)
        cost_rt = (COMM_BPS + SLIP_BPS) / 1e4 * 2 * notional_avg  # entree+sortie
        print(f"    couts estimes/trade (comm 1bps+slip 2bps RT, ~5k notional) = {cost_rt:.2f}$")
