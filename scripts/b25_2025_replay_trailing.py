import pandas as pd
import numpy as np

tr = pd.read_csv("artifacts/backtesting/b25_2025_rankw/trades.csv")
cache = pd.read_parquet("artifacts/backtest_cache/a4060dc97e3f_ohlcv_2025-01-02_2025-12-31.parquet",
                        columns=["symbol", "trade_date", "open", "high", "low", "close"])
cache["trade_date"] = pd.to_datetime(cache["trade_date"])
cache["symbol"] = cache["symbol"].astype(str).str.upper()

ts = tr[tr["exit_reason"] == "trailing_stop"].copy()
ts["entry_date"] = pd.to_datetime(ts["entry_date"])
ts["exit_date"] = pd.to_datetime(ts["exit_date"])
ts["symbol"] = ts["symbol"].astype(str).str.upper()

# Replay d'un trade avec trailing 7% :
#  buy : trailing depuis le plus haut (high) ; sort si close < haut*(1-0.07)
#  sell: trailing depuis le plus bas (low) ; sort si close > bas*(1+0.07)
# Activation différée : trailing ne s'arme qu'une fois le trade en gain de X% (0/3/5%)
# Sinon, pas de sortie -> on attend jusqu'au time_stop (20j) et on prend close.

def replay_buy(entry_open, entry_date, symbol, activation_pct, max_days=20):
    days = cache[(cache["symbol"] == symbol) & (cache["trade_date"] > entry_date)].sort_values("trade_date").head(max_days)
    if len(days) == 0:
        return None, None
    peak = entry_open
    armed = False
    for i, (_, row) in enumerate(days.iterrows()):
        peak = max(peak, row["high"])
        if not armed and (row["close"] / entry_open - 1) >= activation_pct:
            armed = True
        if armed and row["close"] <= peak * (1 - 0.07):
            return row["trade_date"], row["close"]
        if i >= max_days - 1:
            return row["trade_date"], row["close"]
    return None, None

def replay_sell(entry_open, entry_date, symbol, activation_pct, max_days=20):
    days = cache[(cache["symbol"] == symbol) & (cache["trade_date"] > entry_date)].sort_values("trade_date").head(max_days)
    if len(days) == 0:
        return None, None
    trough = entry_open
    armed = False
    for i, (_, row) in enumerate(days.iterrows()):
        trough = min(trough, row["low"])
        if not armed and (1 - row["close"] / entry_open) >= activation_pct:
            armed = True
        if armed and row["close"] >= trough * (1 + 0.07):
            return row["trade_date"], row["close"]
        if i >= max_days - 1:
            return row["trade_date"], row["close"]
    return None, None

results = []
for _, t in ts.iterrows():
    entry_open = t["entry_price"]
    if t["side"] == "buy":
        ret0 = replay_buy(entry_open, t["entry_date"], t["symbol"], 0.0)
        ret3 = replay_buy(entry_open, t["entry_date"], t["symbol"], 0.03)
    else:
        ret0 = replay_sell(entry_open, t["entry_date"], t["symbol"], 0.0)
        ret3 = replay_sell(entry_open, t["entry_date"], t["symbol"], 0.03)
    results.append({
        "symbol": t["symbol"], "side": t["side"], "entry_date": t["entry_date"],
        "exit_date": t["exit_date"], "actual_return": t["return_pct"],
        "actual_pnl": t["pnl"],
        "sim0_ret": ret0[1] / entry_open - 1 if ret0[1] else None,
        "sim3_ret": ret3[1] / entry_open - 1 if ret3[1] else None,
        "sim0_days": (ret0[0] - t["entry_date"]).days if ret0[0] is not None else None,
    })
    # direction sell: return = (entree - sortie)/entree
    if t["side"] == "sell":
        results[-1]["sim0_ret"] = -results[-1]["sim0_ret"] if results[-1]["sim0_ret"] is not None else None
        results[-1]["sim3_ret"] = -results[-1]["sim3_ret"] if results[-1]["sim3_ret"] is not None else None

df = pd.DataFrame(results)
losses = df[df["actual_return"] < 0]
print(f"=== Replay trailing 7% sur les {len(losses)} pertes trailing ===")
print(f"pertes rejouées avec activation 0% : n retournables en gain = {(losses['sim0_ret'] > 0).sum()}")
print(f"pertes rejouées avec activation 3% : n retournables en gain = {(losses['sim3_ret'] > 0).sum()}")
print(f"sim0_ret moyen (si on avait gardé jusqu'au stop/20j): {losses['sim0_ret'].mean():.2f}%")
print(f"sim3_ret moyen: {losses['sim3_ret'].mean():.2f}%")
print(f"actual_return moyen: {losses['actual_return'].mean():.2f}%")
print()
print("=== Détail des pertes <=2j ===")
early = losses[losses["actual_return"] < -3]
print(early[["symbol", "side", "actual_return", "sim0_ret", "sim3_ret", "actual_pnl"]].head(20).to_string(index=False))
