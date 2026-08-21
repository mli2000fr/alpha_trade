"""E5-E — Mécanique des trades : MFE>=7% puis H20<0 (donne +7% puis rend tout),
par semestre et par politique (3x7 vs 4x13). Teste l'hypothèse 'whipsaw' sur
les semestres mauvais (2022H1, 2024H1) vs bons.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "f:/projets")

ROOT = Path("artifacts/backtesting")
CACHE = "artifacts/backtest_cache/39587735630f_ohlcv_2017-10-26_2026-06-30.parquet"

RUNS = {
    "2022": {"3x7": "cmp_b25_h20_2022_postfix_tp_m8", "4x13": "cmp_b25_h20_2022_tp4x13_m8"},
    "2023h1": {"3x7": "cmp_b25_h20_2023h1_postfix_tp_m8", "4x13": "cmp_b25_h20_2023h1_tp4x13_m8"},
    "2024h1": {"3x7": "cmp_b25_h20_2024h1_postfix_tp_m8", "4x13": "cmp_b25_h20_2024h1_tp4x13_m8"},
    "2025": {"3x7": "cmp_b25_h20_2025_postfix_tp_m8", "4x13": "cmp_b25_h20_2025_tp4x13_m8"},
    "2026h1": {"3x7": "cmp_b25_h20_2026_postfix_tp_m8", "4x13": "cmp_b25_h20_2026_tp4x13_m8"},
}

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


def load(variant_key):
    name = RUNS[variant_key[0]][variant_key[1]]
    df = pd.read_csv(ROOT / name / "trade_audit_log.csv")
    # trades réels fermés : replay_exit_reason ET entry_date renseignés
    df = df[df["replay_exit_reason"].notna() & df["entry_date"].notna()].copy()
    df["entry_date"] = pd.to_datetime(df["entry_date"])
    return df


def main():
    print("=== Trades MFE>=7% et H20<0 (a donné +7% puis tout rendu), par semestre/politique ===")
    print(f"{'semestre':9} {'pol':4} {'N':>4} {'N(mfe7&h20<0)':>14} {'%':>6} {'MFE moy':>8} {'H20 moy':>8}")
    for key in [("2022", "3x7"), ("2022", "4x13"), ("2024h1", "3x7"), ("2024h1", "4x13"),
                ("2025", "3x7"), ("2025", "4x13"), ("2026h1", "3x7"), ("2026h1", "4x13"),
                ("2023h1", "3x7"), ("2023h1", "4x13")]:
        df = load(key)
        # assigner semestre
        df["sem"] = df["entry_date"].dt.year.astype(str) + " H" + (df["entry_date"].dt.month > 6).map({True: "2", False: "1"})
        # lifecycle
        lc = [lifecycle(r) for _, r in df.iterrows()]
        df["mfe"] = [x["mfe"] if x else np.nan for x in lc]
        df["ret_h20"] = [x["ret_h20"] if x else np.nan for x in lc]
        # stats par semestre (toutes les pol couvrent plusieurs semestres pour les runs complets)
        for sem, g in df.groupby("sem"):
            n = len(g)
            hit = g[(g["mfe"] >= 7.0) & (g["ret_h20"] < 0)]
            print(f"{sem:9} {key[1]:4} {n:4d} {len(hit):>14} {len(hit)/n*100:6.1f} "
                  f"{g['mfe'].mean():8.2f} {g['ret_h20'].mean():8.2f}")


if __name__ == "__main__":
    main()
