"""Verif : les shorts post-fix prennent-ils vraiment des TOP au lieu de BOTTOM ?
1. Coverage des symboles shorts dans le pool e2 (toutes dates confondues).
2. Rank de quelques shorts concrets dans le pool (autour de la date d'entree).
3. Distribution du rank du pool lui-meme par decile.
"""
import pandas as pd
import numpy as np
from pathlib import Path

ROOT = Path("artifacts/backtesting")
DATA = pd.read_parquet("artifacts/models/oracle/e2_feature_dataset.parquet",
                       columns=["date", "symbol", "global_rank_20", "oracle_extreme10",
                                "oracle_pct_rank", "future_return", "oracle_decile"])
DATA["date"] = pd.to_datetime(DATA["date"])
DATA["symbol"] = DATA["symbol"].astype(str).str.upper()

# 1. symbols shorts 2025 post-fix
df = pd.read_csv(ROOT / "cmp_b25_h20_2025_postfix_tp_m8" / "trade_audit_log.csv")
tr = df[df["pnl"].notna()].copy()
tr["entry_date"] = pd.to_datetime(tr["entry_date"])
tr["symbol"] = tr["symbol"].astype(str).str.upper()
shorts = tr[tr["side"] == "sell"]
short_syms = set(shorts["symbol"])
pool_syms = set(DATA["symbol"])
inter = short_syms & pool_syms
print(f"symbols SHORT 2025: {len(short_syms)}  | dans pool e2 (toutes dates): {len(inter)} ({len(inter)/len(short_syms)*100:.0f}%)")
print(f"symbols shorts absents du pool: {sorted(short_syms - pool_syms)[:20]}")

# 2. rank des shorts concrets (fusion par date exacte vs date +/- 1)
print("\n=== rank des 10 premiers shorts (fusion date exacte) ===")
cnt = 0
for _, t in shorts.head(10).iterrows():
    row = DATA[(DATA["symbol"] == t["symbol"]) & (DATA["date"] == t["entry_date"])]
    if len(row):
        r = row.iloc[0]
        print(f"  {t['symbol']:6} entry={t['entry_date'].date()} side=sell pnl={t['pnl']:.0f} "
              f"rank20={r['global_rank_20']:.1f} ext={r['oracle_extreme10']} fr={r['future_return']*100:.2f}%")
        cnt += 1
    else:
        print(f"  {t['symbol']:6} entry={t['entry_date'].date()} -> PAS dans pool ce jour")

# 3. Distribution global_rank_20 dans le pool par annee (pour reference)
DATA["year"] = DATA["date"].dt.year
print("\n=== distribution global_rank_20 du pool (2025) ===")
p25 = DATA[DATA["year"] == 2025]
print(p25["global_rank_20"].describe().to_string())
print("  valeurs uniques (head):", sorted(p25["global_rank_20"].unique())[:15])

# 4. ranks possibles : est-ce que rank 0 = top ou bottom ?
# on compare avec oracle_pct_rank (0-100, haut = top?)
print("\n=== corrélation global_rank_20 vs oracle_pct_rank (2025) ===")
s = p25[["global_rank_20", "oracle_pct_rank"]].dropna()
print(s.corr().to_string())
