"""Verif production : que devient une position > 20 jours ouvrés ?
- a-t-elle un ordre de sortie travaillant (TP/trailing) -> time_stop correctement saute ?
- ou est-elle bloquee sans protection (bug potentiel) ?
Analyse depuis les runs production-parity (exit_lifecycle_replay = replay des exits reels).
"""
import pandas as pd
import numpy as np
from pathlib import Path

ROOT = Path("artifacts/backtesting")
RUNS = ["cmp_b25_h20_2025_prodparity_p23_m8", "cmp_b25_h20_2026_prodparity_p23_m8"]

for r in RUNS:
    year = "2025" if "2025" in r else "2026"
    df = pd.read_csv(ROOT / r / "trade_audit_log.csv")
    tr = df[df["pnl"].notna()].copy()
    tr["entry_date"] = pd.to_datetime(tr["entry_date"])
    tr["replay_exit_date"] = pd.to_datetime(tr["replay_exit_date"], errors="coerce")
    # jours ouvrés approx via business days
    d0 = pd.to_datetime(tr["entry_date"]).dt.date.to_numpy(dtype="datetime64[D]")
    d1 = pd.to_datetime(tr["replay_exit_date"]).dt.date.to_numpy(dtype="datetime64[D]")
    tr["biz_days"] = np.busday_count(d0, d1)

    print(f"\n{'='*100}\n### {year} : positions longues (>= 20 jours ouvrés)\n{'='*100}")
    long_held = tr[tr["biz_days"] >= 20].copy()
    print(f"trades >= 20j ouvrés : {len(long_held)} / {len(tr)}  (max biz={tr['biz_days'].max()})")
    if len(long_held):
        print("\nrepartition exit_reason:")
        print(long_held["replay_exit_reason"].value_counts().to_string())
        print(f"\nreturn de ces positions : mean={long_held['return_pct'].mean():.2f}%  "
              f"median={long_held['return_pct'].median():.2f}%  "
              f"negatif={(long_held['return_pct']<0).sum()}  positifs={(long_held['return_pct']>0).sum()}")
        print("\nles 12 plus longues:")
        cols = ["symbol", "side", "entry_date", "replay_exit_date", "biz_days", "return_pct",
                "replay_exit_reason", "replay_trailing_stop_pct"]
        print(long_held.nlargest(12, "biz_days")[cols].to_string(index=False))
        # time_stop present ?
        print("\n# exits time_stop:", tr["replay_exit_reason"].eq("time_stop").sum())
        # positions >= 20j en PERTE -> suspect (aucun time_stop, perte qui dure)
        losers_long = long_held[long_held["return_pct"] < 0]
        print(f"\npositions >=20j EN PERTE (time_stop aurait dû couper ?): {len(losers_long)}")
        if len(losers_long):
            print(losers_long[["symbol", "side", "entry_date", "replay_exit_date", "biz_days", "return_pct", "replay_exit_reason"]].to_string(index=False))
