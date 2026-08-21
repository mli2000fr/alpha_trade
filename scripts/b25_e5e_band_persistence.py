"""E5-E — Persistance du mécanisme : la bande MFE [7-10%] (gains rapides rendus)
explique-t-elle le ΔPnL(4x13-3x7) sur tous les semestres ?
Si la bande [7-10%] est systématiquement mieux monétisée par 3x7 que 4x13 PARTOUT,
alors le mécanisme est persistant et 4x13 est structurellement mauvais sur ces
gains rapides — ce qui justifierait une lecture régime, pas un artefact 2024H1.
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


def load(key):
    name = RUNS[key[0]][key[1]]
    df = pd.read_csv(ROOT / name / "trade_audit_log.csv")
    df = df[df["replay_exit_reason"].notna() & df["entry_date"].notna()].copy()
    df["entry_date"] = pd.to_datetime(df["entry_date"])
    df["sem"] = df["entry_date"].dt.year.astype(int).astype(str) + " H" + (df["entry_date"].dt.month > 6).map({True: "2", False: "1"})
    lc = [lifecycle(r) for _, r in df.iterrows()]
    df["mfe"] = [x["mfe"] if x else np.nan for x in lc]
    df["ret_h20"] = [x["ret_h20"] if x else np.nan for x in lc]
    return df


def main():
    print("=== Bande MFE [7-10%] : pnl_sum 3x7 vs 4x13, par semestre ===")
    print(f"{'sem':9} {'3x7 n':>6} {'3x7 pnl':>10} {'4x13 n':>7} {'4x13 pnl':>10} {'Δ(4x13-3x7)':>12}")
    data = {}
    for win, pols in RUNS.items():
        for pol, name in pols.items():
            df = load((win, pol))
            for sem, g in df.groupby("sem"):
                band = g[(g["mfe"] >= 7.0) & (g["mfe"] < 10.0)]
                data.setdefault(sem, {})[pol] = {"n": len(band), "pnl": band["pnl"].sum()}
    print(f"{'sem':9} {'3x7 n':>6} {'3x7 pnl':>10} {'4x13 n':>7} {'4x13 pnl':>10} {'Δ(4x13-3x7)':>12}")
    for sem in sorted(data):
        r = data[sem]
        p37 = r.get("3x7", {}).get("pnl", 0)
        p413 = r.get("4x13", {}).get("pnl", 0)
        n37 = r.get("3x7", {}).get("n", 0)
        n413 = r.get("4x13", {}).get("n", 0)
        print(f"{sem:9} {n37:>6} {p37:>10.0f} {n413:>7} {p413:>10.0f} {p413-p37:>12.0f}")

    print("\n=== Bande MFE [10-13%] : pnl_sum 3x7 vs 4x13, par semestre ===")
    data = {}
    for win, pols in RUNS.items():
        for pol, name in pols.items():
            df = load((win, pol))
            for sem, g in df.groupby("sem"):
                band = g[(g["mfe"] >= 10.0) & (g["mfe"] < 13.0)]
                data.setdefault(sem, {})[pol] = {"n": len(band), "pnl": band["pnl"].sum()}
    print(f"{'sem':9} {'3x7 n':>6} {'3x7 pnl':>10} {'4x13 n':>7} {'4x13 pnl':>10} {'Δ(4x13-3x7)':>12}")
    for sem in sorted(data):
        r = data[sem]
        p37 = r.get("3x7", {}).get("pnl", 0)
        p413 = r.get("4x13", {}).get("pnl", 0)
        n37 = r.get("3x7", {}).get("n", 0)
        n413 = r.get("4x13", {}).get("n", 0)
        print(f"{sem:9} {n37:>6} {p37:>10.0f} {n413:>7} {p413:>10.0f} {p413-p37:>12.0f}")


if __name__ == "__main__":
    main()
