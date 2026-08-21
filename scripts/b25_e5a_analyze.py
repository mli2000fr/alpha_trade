"""E5-A analyse — 4 groupes + TP realise vs H20 (alpha abandonne / protection TP)."""
import pandas as pd
import numpy as np

for year in ("2025", "2026"):
    df = pd.read_parquet(f"artifacts/models/oracle/e5_lifecycle_{year}_postfix.parquet")
    print(f"\n{'='*110}\n### {year} POST-FIX : {len(df)} trades\n{'='*110}")

    # ---- 4 groupes ----
    df["group"] = np.where(df["exit_reason"] == "take_profit", "TP_gagnants",
                   np.where((df["exit_reason"] == "trailing_stop") & (df["ret"] > 0), "trail_gagnants",
                   np.where((df["exit_reason"] == "trailing_stop") & (df["ret"] < 0), "trail_perdants",
                            "autres")))
    print("\n=== 4 GROUPES ===")
    for g in ["TP_gagnants", "trail_gagnants", "trail_perdants", "autres"]:
        sub = df[df["group"] == g]
        if len(sub) == 0:
            print(f"\n  {g}: 0")
            continue
        print(f"\n  {g}: N={len(sub)}  PnL={sub['pnl'].sum():>8.0f}  WR={(sub['pnl']>0).mean()*100:.0f}%  "
              f"mean_ret={sub['ret'].mean():.2f}%  med_ret={sub['ret'].median():.2f}%")
        print(f"     mfe_moy={sub['mfe'].mean():.1f}%  mae_moy={sub['mae'].mean():.1f}%  "
              f"durée={sub['holding_days'].mean():.1f}j  tp_dist={sub['tp_dist'].mean():.1f}%  stop={sub['stop_dist'].mean():.1f}%")
        if g == "trail_perdants":
            # erreur directionnelle ou bruit avant rebond ? -> ret_h20 signe
            h20 = sub["ret_h20"].dropna()
            print(f"     ret_h20: mean={h20.mean():.2f}%  -> rebond (h20>0)={(h20>0).mean()*100:.0f}%  "
                  f"vraie erreur (h20<0)={(h20<0).mean()*100:.0f}%")

    # ---- chiffre cle : TP realise vs H20 ----
    tp = df[df["exit_reason"] == "take_profit"].copy()
    print(f"\n=== CHIFFRE CLÉ : TP réalisé vs return H20 (N TP={len(tp)}) ===")
    if len(tp):
        tp["h20"] = tp["ret_h20"]
        h20_ok = tp.dropna(subset=["h20"])
        print(f"  (H20 dispo: {len(h20_ok)}/{len(tp)})")
        # alpha abandonne : h20 > ret (le titre aurait continué dans notre sens)
        abandon = h20_ok[h20_ok["h20"] > h20_ok["ret"]]
        # protection TP : h20 < ret (le TP a évité une perte / donné mieux)
        protect = h20_ok[h20_ok["h20"] < h20_ok["ret"]]
        print(f"  TP réalisé moyen      : {tp['ret'].mean():+.2f}%")
        if len(h20_ok):
            print(f"  H20 final moyen       : {h20_ok['h20'].mean():+.2f}%")
        print(f"  [WARN] alpha abandonne (H20>ret) : {len(abandon)} trades, delta moyen "
              f"{(abandon['h20']-abandon['ret']).mean():+.1f} pts, somme PnL abandonne ~{(abandon['pnl']*(abandon['h20']-abandon['ret'])/abandon['ret']).sum():.0f}$")
        print(f"  [OK] protection TP (H20<ret)    : {len(protect)} trades, delta moyen "
              f"{(protect['ret']-protect['h20']).mean():+.1f} pts")
        # exemples extremes
        if len(abandon):
            print("\n  Top alpha abandonné (TP coupé trop tôt) :")
            aa = abandon.reindex((abandon["h20"]-abandon["ret"]).sort_values(ascending=False).index).head(6)
            print("   " + aa[["symbol", "side", "ret", "h20", "mfe_post_h20", "holding_days"]].to_string(index=False).replace("\n", "\n   "))

    # ---- par side ----
    print(f"\n=== PAR SIDE ===")
    for side, lab in [("buy", "LONG"), ("sell", "SHORT")]:
        sub = df[df["side"] == side]
        if len(sub) == 0:
            continue
        print(f"  {lab}: N={len(sub)} PnL={sub['pnl'].sum():.0f} WR={(sub['pnl']>0).mean()*100:.0f}% "
              f"mfe={sub['mfe'].mean():.1f}% mae={sub['mae'].mean():.1f}% ret_h20={sub['ret_h20'].mean():.2f}%")
