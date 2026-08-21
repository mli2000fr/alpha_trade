"""E5-A — Trade lifecycle post-fix (2025 + 2026).
Pour chaque trade : side, entry/exit, return, exit_reason, duree, TP dist, stop dist,
MFE/MAE avant sortie, MFE apres sortie H5/H10/H20, rendement titre H20 depuis entree,
TP touche, post-sortie. Groupes : TP gagnants / trailing gagnants / trailing perdants / autres.
Chiffre cle : TP realise vs return H20 (alpha abandonne vs protection TP).
AUCUNE OPTIMISATION.
"""
import pandas as pd
import numpy as np
from pathlib import Path

ROOT = Path("artifacts/backtesting")
CACHE = "artifacts/backtest_cache/85712967191d_ohlcv_2025-01-01_2026-06-20.parquet"
RUNS = [("2025 POST-FIX", "cmp_b25_h20_2025_postfix_tp_m8"),
        ("2026 POST-FIX", "cmp_b25_h20_2026_postfix_tp_m8")]

# ---- load OHLCV indexé par (symbol) -> DataFrame trié par date ----
ohlcv = pd.read_parquet(CACHE, columns=["symbol", "trade_date", "open", "high", "low", "close"])
ohlcv["trade_date"] = pd.to_datetime(ohlcv["trade_date"])
ohlcv["symbol"] = ohlcv["symbol"].astype(str).str.upper()
ohlcv = ohlcv.sort_values(["symbol", "trade_date"]).reset_index(drop=True)
idx = {sym: g.reset_index(drop=True) for sym, g in ohlcv.groupby("symbol", sort=False)}
print(f"cache: {len(ohlcv):,} rows | {len(idx)} symbols")

def dir_ret(side, entry, price):
    """Return directionnel (LONG: price/entry-1 ; SHORT: entry/price-1)."""
    return (price / entry - 1) * 100 if side == "buy" else (entry / price - 1) * 100

def trade_lifecycle(t):
    side = t["side"]
    entry = t["entry_price"]
    entry_d = pd.Timestamp(t["entry_date"])
    exit_d = pd.Timestamp(t["replay_exit_date"])
    g = idx.get(t["symbol"])
    if g is None:
        return None
    # jours de la vie du trade (>= entry, <= exit)
    life = g[(g["trade_date"] >= entry_d) & (g["trade_date"] <= exit_d)]
    if len(life) == 0:
        return None
    # MFE/MAE avant sortie (directionnel)
    if side == "buy":
        mfe = (life["high"] / entry - 1).max() * 100
        mae = (life["low"] / entry - 1).min() * 100
    else:
        mfe = (entry / life["low"] - 1).max() * 100
        mae = (entry / life["high"] - 1).min() * 100
    # jours apres sortie (strictement > exit)
    post = g[g["trade_date"] > exit_d].reset_index(drop=True)
    # rendements H5/H10/H20 depuis l'entree (close a J+H)
    ret = {}
    for h in (5, 10, 20):
        row = g[g["trade_date"] >= entry_d].head(h + 1)
        if len(row) == h + 1:
            ret[f"ret_h{h}"] = dir_ret(side, entry, row.iloc[h]["close"])
        else:
            ret[f"ret_h{h}"] = np.nan
    # MFE apres sortie sur H5/H10/H20 jours ouverts apres l'exit
    for h in (5, 10, 20):
        w = post.head(h)
        if len(w) == h:
            if side == "buy":
                ret[f"mfe_post_h{h}"] = (w["high"] / entry - 1).max() * 100
            else:
                ret[f"mfe_post_h{h}"] = (entry / w["low"] - 1).max() * 100
        else:
            ret[f"mfe_post_h{h}"] = np.nan
    return {
        "symbol": t["symbol"], "side": side, "entry_date": entry_d, "exit_date": exit_d,
        "ret": t["return_pct"], "pnl": t["pnl"], "exit_reason": t["replay_exit_reason"],
        "holding_days": (exit_d - entry_d).days,
        "tp_dist": abs(t["replay_take_profit_price"] / entry - 1) * 100,
        "stop_dist": abs(t["entry_price"] - t["replay_initial_stop_price"]) / entry * 100,
        "mfe": mfe, "mae": mae,
        "ret_h5": ret["ret_h5"], "ret_h10": ret["ret_h10"], "ret_h20": ret["ret_h20"],
        "mfe_post_h5": ret["mfe_post_h5"], "mfe_post_h10": ret["mfe_post_h10"], "mfe_post_h20": ret["mfe_post_h20"],
    }

print("=" * 100)
print("E5-A — TRADE LIFECYCLE (post-fix TP)")
print("=" * 100)
all_rows = []
for label, name in RUNS:
    df = pd.read_csv(ROOT / name / "trade_audit_log.csv")
    tr = df[df["pnl"].notna()].copy()
    tr["entry_date"] = pd.to_datetime(tr["entry_date"])
    tr["replay_exit_date"] = pd.to_datetime(tr["replay_exit_date"], errors="coerce")
    rows = []
    for _, t in tr.iterrows():
        r = trade_lifecycle(t)
        if r:
            r["year"] = label[:4]
            rows.append(r)
    rdf = pd.DataFrame(rows)
    rdf.to_parquet(f"artifacts/models/oracle/e5_lifecycle_{label[:4]}_postfix.parquet")
    all_rows.append(rdf)
    print(f"\n### {label} : {len(rdf)} trades -> e5_lifecycle_{label[:4]}_postfix.parquet")

df_all = pd.concat(all_rows, ignore_index=True)
print(f"\ntotal: {len(df_all)} trades")
print("\n=== colonnes ===")
print(list(df_all.columns))
