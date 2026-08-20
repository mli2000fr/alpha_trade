"""E5-E — Mécanisme exact 2024H1 : les trades montent-ils 7-13% (TP 3x7 mais pas
4x13) puis redescendent ? Comparaison de la distribution MFE / devenir par politique."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "f:/projets")

ROOT = Path("artifacts/backtesting")
CACHE = "artifacts/backtest_cache/39587735630f_ohlcv_2017-10-26_2026-06-30.parquet"

ohlcv = pd.read_parquet(CACHE, columns=["symbol", "trade_date", "open", "high", "low", "close"])
ohlcv["trade_date"] = pd.to_datetime(ohlcv["trade_date"])
ohlcv["symbol"] = ohlcv["symbol"].astype(str).str.upper()
ohlcv = ohlcv.sort_values(["symbol", "trade_date"]).reset_index(drop=True)
idx = {sym: g.reset_index(drop=True) for sym, g in ohlcv.groupby("symbol", sort=False)}


def dir_ret(side, entry, price):
    return (price / entry - 1) * 100 if side in ("buy", "long", "L") else (entry / price - 1) * 100


def lifecycle(t):
    side = str(t.get("side", "buy")).strip().lower()
    entry = float(t["entry_price"])
    entry_d = pd.Timestamp(t["entry_date"])
    exit_d = pd.Timestamp(t["replay_exit_date"])
    g = idx.get(t["symbol"])
    if g is None:
        return None
    life = g[(g["trade_date"] >= entry_d) & (g["trade_date"] <= exit_d)]
    if len(life) == 0:
        return None
    if side in ("buy", "long"):
        mfe = (life["high"] / entry - 1).max() * 100
    else:
        mfe = (entry / life["low"] - 1).max() * 100
    row = g[g["trade_date"] >= entry_d].head(21)
    ret_h20 = dir_ret(side, entry, row.iloc[20]["close"]) if len(row) == 21 else np.nan
    return {"mfe": mfe, "ret_h20": ret_h20}


def load(name):
    df = pd.read_csv(ROOT / name / "trade_audit_log.csv")
    df = df[df["replay_exit_reason"].notna() & df["entry_date"].notna()].copy()
    df["entry_date"] = pd.to_datetime(df["entry_date"])
    lc = [lifecycle(r) for _, r in df.iterrows()]
    df["mfe"] = [x["mfe"] if x else np.nan for x in lc]
    df["ret_h20"] = [x["ret_h20"] if x else np.nan for x in lc]
    return df


def analyze(name, label):
    df = load(name)
    print(f"\n=== {label} (n={len(df)}) ===")
    # Bands MFE
    print("Distribution MFE :")
    bands = [(0, 3), (3, 5), (5, 7), (7, 10), (10, 13), (13, 100)]
    for lo, hi in bands:
        sub = df[(df["mfe"] >= lo) & (df["mfe"] < hi)]
        if len(sub):
            print(f"   MFE [{lo}-{hi}%): n={len(sub):3d} ({len(sub)/len(df)*100:4.1f}%) "
                  f"H20_moy={sub['ret_h20'].mean():6.2f}% %H20<0={(sub['ret_h20']<0).mean():.0%} "
                  f"pnl_sum={sub['pnl'].sum():8.0f}")
    # Exit reasons par bande
    print("Exit reasons (take_profit vs trailing) :")
    print("   ", df["replay_exit_reason"].value_counts().to_dict())
    # TP touché ? MFE >= TP pct
    for tp, tplabel in [(7.0, "TP 7%"), (13.0, "TP 13%")]:
        sub = df[df["mfe"] >= tp]
        print(f"   {tplabel}: {len(sub)} trades ont atteint MFE>={tp}%, H20_moy={sub['ret_h20'].mean():.2f}%, pnl_sum={sub['pnl'].sum():.0f}")


analyze("cmp_b25_h20_2024h1_postfix_tp_m8", "2024H1 — 3×7")
analyze("cmp_b25_h20_2024h1_tp4x13_m8", "2024H1 — 4×13")
analyze("cmp_b25_h20_2022_postfix_tp_m8", "2022 — 3×7 (complet, contexte)")
analyze("cmp_b25_h20_2022_tp4x13_m8", "2022 — 4×13 (complet, contexte)")
