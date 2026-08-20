"""E5-E — Devenir H20 des trades MFE [7-10%] par semestre (3x7).

Question clé : la bande [7-10%] — en 2024H1/2022H1 les gains se retournent (H20<0,
protection utile) alors qu'en 2025/2026 ils continuent (H20>0, protection coûteuse) ?
C'est ce qui distingue les régimes où 3x7 protège vraiment de ceux où il coûte.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "f:/projets")

ROOT = Path("artifacts/backtesting")
CACHE = "artifacts/backtest_cache/39587735630f_ohlcv_2017-10-26_2026-06-30.parquet"

RUNS_37 = {
    "2022": "cmp_b25_h20_2022_postfix_tp_m8",
    "2023h1": "cmp_b25_h20_2023h1_postfix_tp_m8",
    "2024h1": "cmp_b25_h20_2024h1_postfix_tp_m8",
    "2025": "cmp_b25_h20_2025_postfix_tp_m8",
    "2026h1": "cmp_b25_h20_2026_postfix_tp_m8",
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


def main():
    print("=== Trades 3×7 MFE [7-10%] : devenir H20 par semestre ===")
    print(f"{'sem':9} {'n':>4} {'H20 moy':>8} {'%H20<0':>8} {'%H20>13':>8} {'pnl_sum':>9} {'pct pnl_total':>13}")
    for win, name in RUNS_37.items():
        df = pd.read_csv(ROOT / name / "trade_audit_log.csv")
        df = df[df["replay_exit_reason"].notna() & df["entry_date"].notna()].copy()
        df["entry_date"] = pd.to_datetime(df["entry_date"])
        df["sem"] = df["entry_date"].dt.year.astype(int).astype(str) + " H" + (df["entry_date"].dt.month > 6).map({True: "2", False: "1"})
        lc = [lifecycle(r) for _, r in df.iterrows()]
        df["mfe"] = [x["mfe"] if x else np.nan for x in lc]
        df["ret_h20"] = [x["ret_h20"] if x else np.nan for x in lc]
        for sem, g in df.groupby("sem"):
            band = g[(g["mfe"] >= 7.0) & (g["mfe"] < 10.0)]
            if not len(band):
                continue
            total_pnl = g["pnl"].sum()
            print(f"{sem:9} {len(band):4d} {band['ret_h20'].mean():8.2f} {(band['ret_h20']<0).mean():8.1%} "
                  f"{(band['ret_h20']>13).mean():8.1%} {band['pnl'].sum():9.0f} "
                  f"{band['pnl'].sum()/total_pnl*100 if total_pnl else 0:12.1f}%")

    print("\n=== Répartition : % de trades 3x7 MFE>=7% qui finissent H20<0 par semestre ===")
    print(f"{'sem':9} {'n(MFE>=7)':>10} {'%H20<0':>8}")
    for win, name in RUNS_37.items():
        df = pd.read_csv(ROOT / name / "trade_audit_log.csv")
        df = df[df["replay_exit_reason"].notna() & df["entry_date"].notna()].copy()
        df["entry_date"] = pd.to_datetime(df["entry_date"])
        df["sem"] = df["entry_date"].dt.year.astype(int).astype(str) + " H" + (df["entry_date"].dt.month > 6).map({True: "2", False: "1"})
        lc = [lifecycle(r) for _, r in df.iterrows()]
        df["mfe"] = [x["mfe"] if x else np.nan for x in lc]
        df["ret_h20"] = [x["ret_h20"] if x else np.nan for x in lc]
        for sem, g in df.groupby("sem"):
            big = g[g["mfe"] >= 7.0]
            if not len(big):
                continue
            print(f"{sem:9} {len(big):10d} {(big['ret_h20']<0).mean():8.1%}")


if __name__ == "__main__":
    main()
