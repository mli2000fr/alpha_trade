import pandas as pd
import numpy as np

tr = pd.read_csv("artifacts/backtesting/b25_2025_rankw/trades.csv")
ts = tr[tr["exit_reason"] == "trailing_stop"].copy()
ts["is_loss"] = ts["return_pct"] < 0
ts["entry_date"] = pd.to_datetime(ts["entry_date"])
ts["exit_date"] = pd.to_datetime(ts["exit_date"])

losses = ts[ts["is_loss"]].copy()

# Regardons le POTENTIEL de ces pertes: si le trade était resté ouvert (pas de trailing),
# aurait-il fini en gain au moment du time_stop (20j) ? 
# Approximation via le return_pct à la sortie réelle vs le max potentiel inconnu.
# On n'a pas les barres par trade directement, mais on peut estimer via le cache OHLCV.

# Vérifions si le cache OHLCV couvre 2025 pour rejouer
from pathlib import Path
import glob
cand = glob.glob("artifacts/backtest_cache/*2025*.parquet")
print("caches OHLCV avec 2025:", cand)
cand2 = glob.glob("artifacts/backtest_cache/*2019*.parquet")
print("nb caches totaux:", len(glob.glob("artifacts/backtest_cache/*.parquet")))

# Pour chaque perte trailing, calculer le return à la sortie ET estimer:
# si on avait attendu le time_stop (20j), le return aurait-il été meilleur?
# Proxy: comparer holding_days et return - les pertes courtes ont-elles des symboles
# qui ont ensuite rebondi? On regarde les pires pertes et leur contexte
print("\n=== pertes <=2j (candidates à l'erreur de stop trop serré) ===")
early = losses[losses["holding_days"] <= 2]
print(early[["symbol", "side", "entry_date", "exit_date", "holding_days", "return_pct", "pnl"]].sort_values("return_pct").to_string(index=False))
