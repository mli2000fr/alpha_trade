"""R3 — Contrefactuel causal sur TOUS les trades (2025 + 2026).
Matrice FIXEE a l'avance :
  - baseline P14 (0R) : trailing arme a J+1 (watcher)
  - +1R / +2R        : trailing ne s'arme qu'apres gain de 1R/2R (risk_per_share)
  - no-trailing      : jamais arme -> seuls TP / initial_stop / time_stop sortent

Pour chaque trade : nouveau_ret via replay mecanique validee (92-94%).
PnL re-evalue = pnl_officiel * (nouveau_ret / ret_officiel) pour garder le sizing.
Equite cumulee -> Return / PF / Sharpe / MaxDD / win / expectancy / N / duree / L/S.
"""
import pandas as pd
import numpy as np
from pathlib import Path

ROOT = Path("artifacts/backtesting")
CACHE = {
    "cmp_b25_h20_2025_prodparity_p23_m8": "artifacts/backtest_cache/a4060dc97e3f_ohlcv_2025-01-02_2025-12-31.parquet",
    "cmp_b25_h20_2026_prodparity_p23_m8": "artifacts/backtest_cache/2a7cecd22ad4_ohlcv_2026-01-02_2026-05-31.parquet",
}
VARIANTS = {"baseline_0R": 0.0, "trail_1R": 1.0, "trail_2R": 2.0, "no_trailing": None}

def load_ohlcv(path):
    df = pd.read_parquet(path, columns=["symbol", "trade_date", "open", "high", "low", "close"])
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    df["symbol"] = df["symbol"].astype(str).str.upper()
    df = df.sort_values(["symbol", "trade_date"]).reset_index(drop=True)
    return {sym: g.reset_index(drop=True) for sym, g in df.groupby("symbol", sort=False)}

def replay_trade(side, entry, entry_date, g, ts_pct, init_stop, tp_price, risk_per_share,
                 act_r=None, time_stop_days=20, min_tp_progress=0.5, near_zero=0.005,
                 max_window=90):
    """Replay mecanique moteur. act_r: 0.0=J+1, 1.0/2.0=R-multiple, None=jamais arme.
    Le moteur continue au-dela de 20j si la progression vers le TP est bonne.
    """
    rows = g[g["trade_date"] >= entry_date].head(max_window)
    if len(rows) == 0:
        return None, None, "no_data", 0.0
    peak = entry
    trough = entry
    for i, (_, row) in enumerate(rows.iterrows()):
        o, h, l, c = row["open"], row["high"], row["low"], row["close"]
        ts_level = (peak * (1 - ts_pct)) if side == "buy" else (trough * (1 + ts_pct))
        # activation
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
            # time stop : seulement a partir de J20, et seulement si progression TP insuffisante
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

def load_trades(r):
    df = pd.read_csv(ROOT / r / "trade_audit_log.csv")
    tr = df[df["pnl"].notna()].copy()
    tr["entry_date"] = pd.to_datetime(tr["entry_date"])
    tr["replay_exit_date"] = pd.to_datetime(tr["replay_exit_date"], errors="coerce")
    return tr

def run_counterfactual(r, idx, variant_act):
    tr = load_trades(r)
    out = []
    for _, t in tr.iterrows():
        g = idx.get(t["symbol"])
        if g is None:
            continue
        side = t["side"]
        entry = t["entry_price"]
        ts_pct = t["replay_trailing_stop_pct"]
        tp_price = t["replay_take_profit_price"]
        init_stop = t["replay_initial_stop_price"]
        risk = abs(entry - init_stop) if pd.notna(init_stop) else None
        d, px, reason, ret = replay_trade(side, entry, t["entry_date"], g, ts_pct,
                                          init_stop, tp_price, risk, act_r=variant_act)
        if d is None:
            continue
        # re-evaluer le PnL en gardant le sizing officiel (proportionnel au ret)
        official_ret = t["return_pct"]
        pnl = t["pnl"] * (ret / official_ret) if official_ret != 0 else t["pnl"]
        out.append({
            "symbol": t["symbol"], "side": side, "entry_date": t["entry_date"],
            "exit_date": d, "ret": ret, "pnl": pnl, "reason": reason,
            "official_ret": official_ret, "official_pnl": t["pnl"],
            "holding_days": (pd.Timestamp(d) - t["entry_date"]).days,
        })
    return pd.DataFrame(out)

def metrics(df, initial=100000.0):
    """Calcule les metriques agregees depuis la sequence chronologique de pnl."""
    if len(df) == 0:
        return {}
    df = df.sort_values("entry_date").reset_index(drop=True)
    eq = initial + df["pnl"].cumsum()
    total_ret = (eq.iloc[-1] / initial - 1) * 100
    # PF
    wins = df[df["pnl"] > 0]["pnl"].sum()
    losses = -df[df["pnl"] < 0]["pnl"].sum()
    pf = wins / losses if losses > 0 else float("inf")
    # MaxDD sur eq
    peak = eq.cummax()
    dd = (eq - peak) / peak
    maxdd = dd.min() * 100
    # Sharpe journalier approx (sur jours calendaires distincts)
    eq_by_day = eq.copy()
    rets = df["pnl"] / initial
    sharpe = (rets.mean() / rets.std() * np.sqrt(252)) if rets.std() > 0 else 0.0
    return {
        "N": len(df), "total_return_pct": total_ret, "profit_factor": pf,
        "max_dd_pct": maxdd, "sharpe": sharpe,
        "win_rate_pct": (df["pnl"] > 0).mean() * 100,
        "expectancy": df["pnl"].mean(),
        "avg_days": df["holding_days"].mean(),
        "long_pnl": df[df["side"] == "buy"]["pnl"].sum(),
        "short_pnl": df[df["side"] == "sell"]["pnl"].sum(),
        "pnl_net": df["pnl"].sum(),
    }

# ---- Boucle principale ----
all_results = {}
for r, cpath in CACHE.items():
    year = "2025" if "2025" in r else "2026"
    idx = load_ohlcv(cpath)
    print(f"\n{'='*110}\n### {year}\n{'='*110}")
    header = (f"{'variante':14} {'N':>4} {'Return%':>9} {'PF':>6} {'MaxDD%':>7} "
              f"{'Sharpe':>7} {'Win%':>6} {'Expect':>8} {'Jrs':>5} {'L_pnl':>9} {'S_pnl':>9} {'Net':>9}")
    print(header)
    print("-" * 110)
    for vname, act_r in VARIANTS.items():
        df = run_counterfactual(r, idx, act_r)
        m = metrics(df)
        all_results[(year, vname)] = (df, m)
        print(f"{vname:14} {m['N']:>4} {m['total_return_pct']:>9.2f} {m['profit_factor']:>6.2f} "
              f"{m['max_dd_pct']:>7.2f} {m['sharpe']:>7.2f} {m['win_rate_pct']:>6.1f} "
              f"{m['expectancy']:>8.0f} {m['avg_days']:>5.0f} {m['long_pnl']:>9.0f} "
              f"{m['short_pnl']:>9.0f} {m['pnl_net']:>9.0f}")
