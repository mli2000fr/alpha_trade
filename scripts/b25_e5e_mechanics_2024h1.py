"""E5-E — Mécanique 2024H1 : pourquoi 4×13 (et no-TP) s'effondrent quand 3×7 gagne.

Hypothèse économique à tester : « les titres donnent rapidement +5/+7 %, puis rendent
tout » (whipsaw). Analyse PURE, aucun backtest paramétrique.

Comparaison 3×7 vs 4×13 sur 2024H1 (runs existants) :
- Combien de trades touchent TP 3×7 (7%) puis se retournent (H20 final < TP) ?
- MFE après le TP 3×7 (alpha laissé sur la table vs protection) ;
- H20 final des trades sortis au TP 3×7 ;
- Combien auraient fini trailing-loss avec 4×13 (TP 13%) ?
- LONG vs SHORT, secteurs, durée avant retournement.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "f:/projets")

ROOT = Path("artifacts/backtesting")
CACHE = "artifacts/backtest_cache/39587735630f_ohlcv_2017-10-26_2026-06-30.parquet"
RUN_37 = "cmp_b25_h20_2024h1_postfix_tp_m8"
RUN_413 = "cmp_b25_h20_2024h1_tp4x13_m8"

# OHLCV indexé par symbol
ohlcv = pd.read_parquet(CACHE, columns=["symbol", "trade_date", "open", "high", "low", "close"])
ohlcv["trade_date"] = pd.to_datetime(ohlcv["trade_date"])
ohlcv["symbol"] = ohlcv["symbol"].astype(str).str.upper()
ohlcv = ohlcv.sort_values(["symbol", "trade_date"]).reset_index(drop=True)
idx = {sym: g.reset_index(drop=True) for sym, g in ohlcv.groupby("symbol", sort=False)}
print(f"cache: {len(ohlcv):,} rows | {len(idx)} symbols | SPY in cache: {'SPY' in idx}")


def dir_ret(side, entry, price):
    return (price / entry - 1) * 100 if side == "buy" else (entry / price - 1) * 100


def lifecycle(t):
    """MFE/MAE, ret H20 depuis entrée, ret H5/H10 après sortie."""
    side = str(t.get("side", "buy")).strip().lower()
    entry = float(t["entry_price"])
    entry_d = pd.Timestamp(t["entry_date"])
    exit_d = pd.Timestamp(t["replay_exit_date"]) if not pd.isna(t.get("replay_exit_date")) else pd.Timestamp(t["exit_date"])
    g = idx.get(t["symbol"])
    if g is None:
        return None
    life = g[(g["trade_date"] >= entry_d) & (g["trade_date"] <= exit_d)]
    if len(life) == 0:
        return None
    if side in ("buy", "long", "l"):
        mfe = (life["high"] / entry - 1).max() * 100
        mae = (life["low"] / entry - 1).min() * 100
    else:
        mfe = (entry / life["low"] - 1).max() * 100
        mae = (entry / life["high"] - 1).min() * 100
    post = g[g["trade_date"] > exit_d].reset_index(drop=True)
    ret = {}
    row = g[g["trade_date"] >= entry_d].head(21)
    if len(row) == 21:
        ret["ret_h20"] = dir_ret(side, entry, row.iloc[20]["close"])
    else:
        ret["ret_h20"] = np.nan
    for h in (5, 10):
        w = post.head(h)
        if len(w) == h:
            ret[f"post_h{h}"] = dir_ret(side, exit_d_price if False else float(t["replay_exit_price"]), w.iloc[h - 1]["close"])
        else:
            ret[f"post_h{h}"] = np.nan
    return {"mfe": mfe, "mae": mae, **ret}


def load(variant):
    name = RUN_37 if variant == "3x7" else RUN_413
    df = pd.read_csv(ROOT / name / "trade_audit_log.csv")
    df = df[df["replay_exit_reason"].notna()].copy()
    return df


def main():
    a = load("3x7")  # 353 closed
    b = load("4x13")  # 300 closed
    print(f"3×7 closed={len(a)} | 4×13 closed={len(b)}")

    # Ajouter lifecycle aux deux
    for df in (a, b):
        lc = [lifecycle(r) for _, r in df.iterrows()]
        df["mfe"] = [x["mfe"] if x else np.nan for x in lc]
        df["mae"] = [x["mae"] if x else np.nan for x in lc]
        df["ret_h20"] = [x["ret_h20"] if x else np.nan for x in lc]
        df["post_h5"] = [x["post_h5"] if x else np.nan for x in lc]
        df["post_h10"] = [x["post_h10"] if x else np.nan for x in lc]

    # 1. Trades sortis au TP 3×7 : combien ont un H20 final < 0 (retournement) ?
    tp37 = a[a["replay_exit_reason"].astype(str).str.contains("take_profit", case=False, na=False)].copy()
    print(f"\n=== 1. Trades sortis au TP 3×7 ({len(tp37)}) ===")
    print(f"   ret moyen réalisé (return_pct): {tp37['return_pct'].mean():.2f}%")
    print(f"   MFE moyen: {tp37['mfe'].mean():.2f}%")
    print(f"   H20 final moyen: {tp37['ret_h20'].mean():.2f}%")
    print(f"   % avec H20 < 0 (retournement complet): {(tp37['ret_h20'] < 0).mean():.1%}")
    print(f"   % avec H20 < ret réalisé (rend tout): {(tp37['ret_h20'] < tp37['return_pct']).mean():.1%}")
    print(f"   % avec H20 > ret réalisé ×1.5 (alpha abandonné): {(tp37['ret_h20'] > tp37['return_pct'] * 1.5).mean():.1%}")
    # par side
    for side in ("buy", "sell"):
        sp = tp37[tp37["side"] == side]
        if len(sp):
            print(f"   [{side}] n={len(sp)} ret={sp['return_pct'].mean():.2f}% H20={sp['ret_h20'].mean():.2f}% "
                  f"MFE={sp['mfe'].mean():.2f}% %H20<0={(sp['ret_h20'] < 0).mean():.1%}")

    # 2. Combien de trades ont touché un MFE >= 7% puis H20 < 0 (a donné +7 puis tout rendu) ?
    print(f"\n=== 2. MFE >= 7% mais H20 < 0 (a donné +7% puis tout rendu) ===")
    a["gave_then_reversed"] = (a["mfe"] >= 7.0) & (a["ret_h20"] < 0)
    print(f"   total trades: {len(a)}")
    print(f"   trades MFE>=7% et H20<0: {a['gave_then_reversed'].sum()} ({(a['gave_then_reversed']).mean():.1%})")
    gtr = a[a["gave_then_reversed"]]
    if len(gtr):
        print(f"   MFE moyen de ces trades: {gtr['mfe'].mean():.2f}% | H20 moyen: {gtr['ret_h20'].mean():.2f}%")
        print(f"   par side: {gtr.groupby('side').size().to_dict()}")
        print(f"   secteurs top: {gtr['sector'].value_counts().head(6).to_dict()}")
        print(f"   durée moyenne avant sortie: {gtr['holding_days'].mean():.1f}j")

    # 3. Exit reasons 3×7 vs 4×13
    print(f"\n=== 3. Exit reasons ===")
    for lbl, df in (("3×7", a), ("4×13", b)):
        print(f"   {lbl}: {df['replay_exit_reason'].value_counts().to_dict()}")

    # 4. PnL par raison de sortie
    print(f"\n=== 4. PnL moyen par raison de sortie ===")
    for lbl, df in (("3×7", a), ("4×13", b)):
        g = df.groupby("replay_exit_reason")["pnl"].agg(["mean", "sum", "count"])
        print(f"   {lbl}:")
        for reason, r in g.iterrows():
            print(f"      {reason:20}: mean={r['mean']:8.1f} sum={r['sum']:9.0f} n={r['count']}")

    # 5. LONG vs SHORT global
    print(f"\n=== 5. PnL LONG vs SHORT ===")
    for lbl, df in (("3×7", a), ("4×13", b)):
        g = df.groupby("side")["pnl"].agg(["mean", "sum", "count"])
        print(f"   {lbl}: {g.to_dict('index')}")


if __name__ == "__main__":
    main()
