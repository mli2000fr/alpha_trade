"""R3 — Contrefactuel trailing sur TOUS les trades 2025 et 2026.
Etape 1 : valider engine_replay (intrabar, activation watcher, fill au niveau)
          contre les sorties officielles replay_exit_* du moteur.
Etape 2 : variantes 0R / +1R / +2R / no-trailing.
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
    idx = {}
    for sym, g in df.groupby("symbol", sort=False):
        idx[sym] = g.reset_index(drop=True)
    return df, idx

def replay_trade(side, entry, entry_date, symbol, rows, ts_pct, init_stop, tp_price,
                 act_r=0.0, risk_per_share=None, time_stop_days=20):
    """Rejoue la sortie avec la mecanique moteur.
    act_r: multiples de R pour l'activation du trailing (0=immediat a J+1).
    Retourne (exit_date, exit_price, reason, ret_pct).
    """
    peak = entry
    trough = entry
    armed = False  # trailing actif ? (P14 watcher : active a J+1)
    for i, (_, row) in enumerate(rows.iterrows()):
        o, h, l, c = row["open"], row["high"], row["low"], row["close"]
        # update peak/trough (avant resolution)
        new_peak = max(peak, h)
        new_trough = min(trough, l)
        # activation trailing par R multiple
        if not armed and act_r >= 0 and risk_per_share and risk_per_share > 0:
            if side == "buy":
                if new_peak >= entry + act_r * risk_per_share:
                    armed = True
            else:
                if new_trough <= entry - act_r * risk_per_share:
                    armed = True
        elif not armed and act_r == 0:
            # P14 : activation immediate (watcher active a J+1)
            armed = i >= 1
        # resolutions
        ts_level = (new_peak * (1 - ts_pct)) if side == "buy" else (new_trough * (1 + ts_pct))
        # TP
        if side == "buy":
            hit_tp = h >= tp_price
            hit_ts = armed and l <= ts_level
            hit_init = (not armed) and init_stop is not None and l <= init_stop
        else:
            hit_tp = l <= tp_price
            hit_ts = armed and h >= ts_level
            hit_init = (not armed) and init_stop is not None and h >= init_stop
        if hit_init:
            px = init_stop
            ret = (px / entry - 1) * 100 if side == "buy" else (entry / px - 1) * 100
            return row["trade_date"], px, "initial_stop", ret
        if hit_tp and hit_ts:
            px = tp_price  # conservative -> trailing gagne
            ret = (px / entry - 1) * 100 if side == "buy" else (entry / px - 1) * 100
            return row["trade_date"], px, "trailing_stop", ret
        if hit_ts:
            px = ts_level
            ret = (px / entry - 1) * 100 if side == "buy" else (entry / px - 1) * 100
            return row["trade_date"], px, "trailing_stop", ret
        if hit_tp:
            px = tp_price
            ret = (px / entry - 1) * 100 if side == "buy" else (entry / px - 1) * 100
            return row["trade_date"], px, "take_profit", ret
        # time stop
        if i + 1 >= time_stop_days:
            px = c
            ret = (px / entry - 1) * 100 if side == "buy" else (entry / px - 1) * 100
            return row["trade_date"], px, "time_stop", ret
        peak, trough = new_peak, new_trough
    # fin de fenetre sans sortie
    last = rows.iloc[-1]
    px = last["close"]
    ret = (px / entry - 1) * 100 if side == "buy" else (entry / px - 1) * 100
    return last["trade_date"], px, "end_of_data", ret

# ---- Etape 1 : validation ----
print("=" * 100)
print("ETAPE 1 : VALIDATION engine_replay (0R) vs sortie officielle")
print("=" * 100)
for r, cpath in CACHE.items():
    df = pd.read_csv(ROOT / r / "trade_audit_log.csv")
    tr = df[df["pnl"].notna()].copy()
    tr["entry_date"] = pd.to_datetime(tr["entry_date"])
    tr["replay_exit_date"] = pd.to_datetime(tr["replay_exit_date"], errors="coerce")
    cache, idx = load_ohlcv(cpath)
    diffs = []
    for _, t in tr.iterrows():
        g = idx.get(t["symbol"])
        if g is None:
            continue
        rows = g[g["trade_date"] > t["entry_date"]].head(25)
        side = t["side"]
        risk = abs(t["entry_price"] - t["replay_initial_stop_price"]) if pd.notna(t["replay_initial_stop_price"]) else None
        ts_pct = t["replay_trailing_stop_pct"] if pd.notna(t["replay_trailing_stop_pct"]) else 0.07
        tp_price = t["replay_take_profit_price"] if pd.notna(t["replay_take_profit_price"]) else t["entry_price"] * (1.07 if side == "buy" else 0.93)
        d, px, reason, ret = replay_trade(side, t["entry_price"], t["entry_date"], t["symbol"], rows,
                                          ts_pct, t["replay_initial_stop_price"] if pd.notna(t["replay_initial_stop_price"]) else None,
                                          tp_price, act_r=0.0, risk_per_share=risk)
        official = t["return_pct"]
        diffs.append({"sym": t["symbol"], "side": side, "official": official, "engine": ret,
                      "diff": ret - official, "o_reason": t["replay_exit_reason"], "e_reason": reason})
    ddf = pd.DataFrame(diffs)
    n_ok = (ddf["diff"].abs() < 0.5).sum()
    print(f"\n### {r} : N={len(ddf)}  |diff|<0.5% : {n_ok} ({n_ok/len(ddf)*100:.0f}%)")
    print(f"  diff mean={ddf['diff'].mean():.2f}%  median={ddf['diff'].median():.2f}%  "
          f"|diff| mean={ddf['diff'].abs().mean():.2f}%")
    print(f"  official mean ret={ddf['official'].mean():.2f}%  engine mean ret={ddf['engine'].mean():.2f}%")
    print("  pires divergences (|diff| top 8):")
    print(ddf.reindex(ddf["diff"].abs().sort_values(ascending=False).index).head(8)[
        ["sym", "side", "official", "engine", "diff", "o_reason", "e_reason"]].to_string(index=False))
