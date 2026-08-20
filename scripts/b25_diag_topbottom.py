"""Diagnostic TOP/BOTTOM des nouveaux trades post-fix vs pool Oracle Extreme.
Croise trades (date,symbol) avec e2_feature_dataset (global_rank_20, oracle_extreme10, oracle_decile).
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
print(f"pool oracle: {len(DATA):,} rows | {DATA['date'].min().date()} -> {DATA['date'].max().date()}")

# build index date->symbol->rank
pool = DATA.set_index(["date", "symbol"])[["global_rank_20", "oracle_extreme10", "oracle_pct_rank", "future_return", "oracle_decile"]]

RUNS = [("2025 POST-FIX", "cmp_b25_h20_2025_postfix_tp_m8"),
        ("2026 POST-FIX", "cmp_b25_h20_2026_postfix_tp_m8")]

for label, name in RUNS:
    df = pd.read_csv(ROOT / name / "trade_audit_log.csv")
    tr = df[df["pnl"].notna()].copy()
    tr["entry_date"] = pd.to_datetime(tr["entry_date"])
    tr["symbol"] = tr["symbol"].astype(str).str.upper()
    # croiser sur le jour d'entree (entry_date)
    tr = tr.merge(pool.reset_index(), left_on=["symbol", "entry_date"], right_on=["symbol", "date"], how="left")
    print(f"\n{'='*100}\n### {label} : N={len(tr)}  (avec rank oracle: {tr['global_rank_20'].notna().sum()})\n{'='*100}")
    for side, lab in [("buy", "LONG "), ("sell", "SHORT")]:
        sub = tr[tr["side"] == side]
        if len(sub) == 0:
            continue
        # top10% = rank <= 10% du jour ; bottom10% = rank >= 90%
        # oracle_extreme10 = dans le pool extreme ce jour (0/1)
        in_ext = sub["oracle_extreme10"].fillna(0).astype(int)
        # pour LONG on veut TOP (rank bas), pour SHORT on veut BOTTOM (rank haut)
        print(f"\n  {lab}: N={len(sub)}  PnL={sub['pnl'].sum():.0f}")
        print(f"    dans pool Oracle Extreme: {in_ext.sum()} ({in_ext.mean()*100:.0f}%)")
        r = sub["global_rank_20"].dropna()
        if len(r):
            print(f"    global_rank_20: mean={r.mean():.1f}  med={r.median():.1f}  (0=top, 100=bottom)")
            if side == "buy":
                print(f"    LONG: rank<=10 (top10%): {(r<=10).mean()*100:.0f}%   rank<=25: {(r<=25).mean()*100:.0f}%")
            else:
                print(f"    SHORT: rank>=90 (bottom10%): {(r>=90).mean()*100:.0f}%   rank>=75: {(r>=75).mean()*100:.0f}%")
        # return des trades vs future_return oracle
        fr = sub["future_return"].dropna()
        if len(fr):
            print(f"    future_return moyen (pool oracle): {fr.mean()*100:.2f}%  (signe attendu: LONG>0, SHORT<0)")
