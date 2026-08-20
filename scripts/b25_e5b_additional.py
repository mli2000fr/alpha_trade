"""E5-B — Trades additionnels post-fix vs pre-fix.
Le TP serré libere les slots plus tot -> de nouvelles entrees apparaissent.
Compare les entrees uniques (symbol, entry_date, side) pre-fix vs post-fix.
Mesure PnL/WR/PF des trades additionnels (post-fix sans equivalent pre-fix).
"""
import pandas as pd
import numpy as np
from pathlib import Path

ROOT = Path("artifacts/backtesting")

def load_tr(name):
    df = pd.read_csv(ROOT / name / "trade_audit_log.csv")
    tr = df[df["pnl"].notna()].copy()
    tr["entry_date"] = pd.to_datetime(tr["entry_date"])
    tr["symbol"] = tr["symbol"].astype(str).str.upper()
    return tr

for year in ("2025", "2026"):
    pre = load_tr(f"cmp_b25_h20_{year}_prodparity_p23_m8")
    post = load_tr(f"cmp_b25_h20_{year}_postfix_tp_m8")
    print(f"\n{'='*110}\n### {year} : pre-fix N={len(pre)}  post-fix N={len(post)}  (+{len(post)-len(pre)})\n{'='*110}")

    # cles d'entree uniques (symbol, entry_date, side)
    pre_key = set(zip(pre["symbol"], pre["entry_date"], pre["side"]))
    post_key = set(zip(post["symbol"], post["entry_date"], post["side"]))

    # additionnels : entree post-fix sans equivalent pre-fix
    post["is_new"] = ~list(zip(post["symbol"], post["entry_date"], post["side"])).__iter__.__self__ if False else [k not in pre_key for k in zip(post["symbol"], post["entry_date"], post["side"])]

    new = post[post["is_new"]]
    old = post[~post["is_new"]]
    print(f"  trades post-fix ADDITIONNELS (nouvelle entree) : {len(new)}  ({len(new)/len(post)*100:.0f}%)")
    print(f"  trades post-fix COMMUNS (deja presents pre-fix) : {len(old)}")

    def stats(df_, lab):
        if len(df_) == 0:
            print(f"  {lab}: 0")
            return
        wins = df_[df_["pnl"] > 0]["pnl"].sum()
        losses = -df_[df_["pnl"] < 0]["pnl"].sum()
        pf = wins / losses if losses > 0 else float("inf")
        dur = (pd.to_datetime(df_["replay_exit_date"]) - df_["entry_date"]).dt.days.mean()
        print(f"  {lab}: N={len(df_)}  PnL={df_['pnl'].sum():>9.0f}  WR={(df_['pnl']>0).mean()*100:.1f}%  "
              f"PF={pf:.2f}  mean_ret={df_['return_pct'].mean():.2f}%  dur={dur:.1f}j")
        print(f"      L={df_[df_['side']=='buy']['pnl'].sum():.0f}  S={df_[df_['side']=='sell']['pnl'].sum():.0f}  "
              f"exit={df_['replay_exit_reason'].value_counts().to_dict()}")
    stats(new, "ADDITIONNELS (nouveaux)")
    stats(old, "COMMUNS")
    print(f"\n  PnL total post-fix = {post['pnl'].sum():.0f}  (= additionnels {new['pnl'].sum():.0f} + communs {old['pnl'].sum():.0f})")
