"""Diagnostic TOP/BOTTOM v2 — convention correcte.
global_rank_20 >= 0.90 = TOP (LONG), <= 0.10 = BOTTOM (SHORT).
Jointure sur signal_date (le trade est sélectionné la veille de l'entrée).
oracle_pct_rank = rank observé (>=0.90 top réel, <=0.10 bottom réel).
"""
import pandas as pd
import numpy as np
from pathlib import Path

ROOT = Path("artifacts/backtesting")
DATA = pd.read_parquet("artifacts/models/oracle/e2_feature_dataset.parquet",
                       columns=["date", "symbol", "global_rank_20", "oracle_extreme10",
                                "oracle_pct_rank", "future_return"])
DATA["date"] = pd.to_datetime(DATA["date"])
DATA["symbol"] = DATA["symbol"].astype(str).str.upper()

def analyze(label, name):
    df = pd.read_csv(ROOT / name / "trade_audit_log.csv")
    tr = df[df["pnl"].notna()].copy()
    tr["symbol"] = tr["symbol"].astype(str).str.upper()
    tr["signal_date"] = pd.to_datetime(tr["signal_date"], errors="coerce")
    tr["entry_date"] = pd.to_datetime(tr["entry_date"])
    # join sur signal_date (préféré) sinon entry_date
    m = tr.merge(DATA, left_on=["symbol", "signal_date"], right_on=["symbol", "date"], how="left")
    miss_sig = m["global_rank_20"].isna().sum()
    if miss_sig > 0:
        # retry entry_date pour les manquants
        m2 = tr.merge(DATA, left_on=["symbol", "entry_date"], right_on=["symbol", "date"], how="left")
        m.loc[m["global_rank_20"].isna(), ["global_rank_20", "oracle_extreme10", "oracle_pct_rank", "future_return"]] = \
            m2.loc[m["global_rank_20"].isna(), ["global_rank_20", "oracle_extreme10", "oracle_pct_rank", "future_return"]].values
    print(f"\n{'='*100}\n### {label} : N={len(tr)}  (match rank: {m['global_rank_20'].notna().sum()})\n{'='*100}")
    for side, lab, want in [("buy", "LONG ", "TOP(rank>=0.90)"), ("sell", "SHORT", "BOTTOM(rank<=0.10)")]:
        sub = m[m["side"] == side]
        if len(sub) == 0:
            continue
        r = sub["global_rank_20"].dropna()
        ob = sub["oracle_pct_rank"].dropna()
        print(f"\n  {lab}: N={len(sub)}  PnL={sub['pnl'].sum():.0f}")
        print(f"    global_rank_20 (ML): mean={r.mean():.3f}  med={r.median():.3f}  [{want}]")
        if side == "buy":
            print(f"    LONG: rank>=0.90 (top10% ML): {(r>=0.90).mean()*100:.0f}%   rank>=0.75: {(r>=0.75).mean()*100:.0f}%")
            print(f"    oracle_pct_rank>=0.90 (top10% RÉEL): {(ob>=0.90).mean()*100:.0f}%")
        else:
            print(f"    SHORT: rank<=0.10 (bottom10% ML): {(r<=0.10).mean()*100:.0f}%   rank<=0.25: {(r<=0.25).mean()*100:.0f}%")
            print(f"    oracle_pct_rank<=0.10 (bottom10% RÉEL): {(ob<=0.10).mean()*100:.0f}%")
        fr = sub["future_return"].dropna()
        print(f"    future_return réel H20: mean={fr.mean()*100:.2f}%  (LONG attend>0, SHORT attend<0)")

analyze("2025 POST-FIX", "cmp_b25_h20_2025_postfix_tp_m8")
analyze("2026 POST-FIX", "cmp_b25_h20_2026_postfix_tp_m8")
