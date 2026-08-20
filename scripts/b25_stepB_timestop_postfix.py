"""Étape B — Time-stop parity test sur la BASELINE POST-FIX TP.
1. Valide le replay mécanique sur les runs post-fix (2025/2026).
2. Variante : time_stop actif J20 en parallèle du trailing (max_business_days=20,
   min_tp_progress_ratio=0.5, near_zero=0.005) — même signaux/coûts/sizing/intrabar.
3. Tableau : Return/PF/Sharpe/DD/N/time_stop exits/pertes évitées/winners coupés, L/S.
"""
import pandas as pd
import numpy as np
from pathlib import Path

ROOT = Path("artifacts/backtesting")
CACHE = {
    "cmp_b25_h20_2025_postfix_tp_m8": "artifacts/backtest_cache/a4060dc97e3f_ohlcv_2025-01-02_2025-12-31.parquet",
    "cmp_b25_h20_2026_postfix_tp_m8": "artifacts/backtest_cache/2a7cecd22ad4_ohlcv_2026-01-02_2026-05-31.parquet",
}
INITIAL = 100000.0

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
        armed = False
        if act_date is not None and pd.notna(act_date):
            armed = row["trade_date"].normalize() >= pd.Timestamp(act_date).normalize()
        else:
            armed = i >= 1
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

def run_variant(r, idx, time_stop_enabled):
    df = pd.read_csv(ROOT / r / "trade_audit_log.csv")
    tr = df[df["pnl"].notna()].copy()
    tr["entry_date"] = pd.to_datetime(tr["entry_date"])
    tr["watcher_transition_effective_date"] = pd.to_datetime(tr["watcher_transition_effective_date"], errors="coerce")
    out = []
    for _, t in tr.iterrows():
        g = idx.get(t["symbol"])
        if g is None:
            continue
        d, px, reason, ret = replay_trade(t["side"], t["entry_price"], t["entry_date"], g,
                                          t["replay_trailing_stop_pct"], t["replay_initial_stop_price"],
                                          t["replay_take_profit_price"], t["watcher_transition_effective_date"],
                                          time_stop_enabled)
        if d is None:
            continue
        official_ret = t["return_pct"]
        pnl = t["pnl"] * (ret / official_ret) if official_ret != 0 else t["pnl"]
        out.append({"symbol": t["symbol"], "side": t["side"], "entry_date": t["entry_date"],
                    "exit_date": d, "ret": ret, "pnl": pnl, "reason": reason,
                    "official_ret": official_ret, "official_pnl": t["pnl"],
                    "holding_days": (pd.Timestamp(d) - t["entry_date"]).days})
    return pd.DataFrame(out)

def daily_sharpe_maxdd(rows, initial=INITIAL):
    if len(rows) == 0:
        return 0.0, 0.0
    r = rows.copy()
    r["exit_date"] = pd.to_datetime(r["exit_date"])
    daily = r.groupby("exit_date")["pnl"].sum().sort_index()
    dates = pd.date_range(daily.index.min(), daily.index.max(), freq="B")
    eq = pd.Series(initial, index=dates)
    eq = eq.add(daily.reindex(dates).fillna(0.0).cumsum(), fill_value=0)
    rets = daily / initial
    sharpe = (rets.mean() / rets.std() * np.sqrt(252)) if rets.std() > 0 else 0.0
    peak = eq.cummax()
    maxdd = ((eq - peak) / peak).min() * 100
    return sharpe, maxdd

def metrics(df):
    if len(df) == 0:
        return {}
    eq_final = INITIAL + df["pnl"].sum()
    total_ret = (eq_final / INITIAL - 1) * 100
    wins = df[df["pnl"] > 0]["pnl"].sum()
    losses = -df[df["pnl"] < 0]["pnl"].sum()
    pf = wins / losses if losses > 0 else float("inf")
    sharpe, maxdd = daily_sharpe_maxdd(df)
    return {"N": len(df), "return_pct": total_ret, "pf": pf, "dd_pct": maxdd,
            "sharpe": sharpe, "win": (df["pnl"] > 0).mean() * 100,
            "ts_exits": df["reason"].eq("time_stop").sum(),
            "long_pnl": df[df["side"] == "buy"]["pnl"].sum(),
            "short_pnl": df[df["side"] == "sell"]["pnl"].sum(),
            "pnl_net": df["pnl"].sum(), "avg_days": df["holding_days"].mean()}

print("=" * 118)
print("ÉTAPE B — TIME-STOP PARITY TEST (baseline POST-FIX TP : ts OFF vs ts actif J20)")
print("=" * 118)
for r, cpath in CACHE.items():
    year = "2025" if "2025" in r else "2026"
    idx = load_ohlcv(cpath)
    base = run_variant(r, idx, time_stop_enabled=False)
    ts = run_variant(r, idx, time_stop_enabled=True)

    # validation baseline vs officiel
    mm = base.merge(ts[["symbol", "side", "entry_date", "ret", "pnl", "reason"]].rename(
        columns={"ret": "ts_ret", "pnl": "ts_pnl", "reason": "ts_reason"}),
        on=["symbol", "side", "entry_date"], suffixes=("_base", "_ts"))
    ok = (mm["ret"].sub(mm["official_ret"]).abs() < 0.5).mean() * 100

    mb, mt = metrics(base), metrics(ts)
    print(f"\n### {year}  (baseline replay vs officiel : match {ok:.0f}%)")
    print(f"  {'variante':18} {'N':>4} {'Ret%':>8} {'Sharpe':>7} {'PF':>6} {'DD%':>7} "
          f"{'Win%':>6} {'ts_exit':>7} {'Jrs':>5} {'L_pnl':>9} {'S_pnl':>9} {'net':>9}")
    print("  " + "-" * 112)
    for lab, m in (("baseline_tsOFF", mb), ("time_stop_J20", mt)):
        print(f"  {lab:18} {m['N']:>4} {m['return_pct']:>8.2f} {m['sharpe']:>7.2f} "
              f"{m['pf']:>6.2f} {m['dd_pct']:>7.2f} {m['win']:>6.1f} {m['ts_exits']:>7} "
              f"{m['avg_days']:>5.0f} {m['long_pnl']:>9.0f} {m['short_pnl']:>9.0f} {m['pnl_net']:>9.0f}")

    # pertes évitées / winners coupés
    fired = mm[mm["ts_reason"] == "time_stop"]
    if len(fired):
        winners_coupes = fired[fired["ts_pnl"] < fired["pnl"]]
        pertes_evitees = fired[fired["ts_pnl"] > fired["pnl"]]
        print(f"  --- time_stop coupe {len(fired)} positions ---")
        print(f"    winners coupés : {len(winners_coupes)}  impact {winners_coupes['ts_pnl'].sum()-winners_coupes['pnl'].sum():+9.0f}$")
        print(f"    pertes évitées : {len(pertes_evitees)}  impact {pertes_evitees['ts_pnl'].sum()-pertes_evitees['pnl'].sum():+9.0f}$")
        # positions >=20j
        long_held = fired[fired["holding_days"] >= 20]
        print(f"    positions >=20j coupées : {len(long_held)}")
        if len(winners_coupes):
            wc = winners_coupes.reindex(winners_coupes["pnl"].sub(winners_coupes["ts_pnl"]).sort_values(ascending=False).index).head(6)
            print("    winners coupés (détail) :")
            print("      " + wc[["symbol", "side", "entry_date", "ret", "ts_ret", "pnl", "ts_pnl"]].to_string(index=False).replace("\n", "\n      "))
