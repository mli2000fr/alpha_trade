import pandas as pd
import numpy as np

# Labels Oracle depuis le dataset O1
o1 = pd.read_parquet("artifacts/models/oracle/e2_feature_dataset.parquet",
                     columns=["date", "symbol", "oracle_pct_rank", "oracle_extreme10", "future_return"])
o1["date"] = pd.to_datetime(o1["date"]).dt.normalize()
o1["symbol"] = o1["symbol"].astype(str).str.upper()
o1["true_top"] = (o1["oracle_pct_rank"] >= 0.90).astype(int)
o1["true_bottom"] = (o1["oracle_pct_rank"] <= 0.10).astype(int)
o1 = o1.drop_duplicates(["date", "symbol"])
print("labels O1:", len(o1), "| true_top:", int(o1["true_top"].sum()), "| true_bottom:", int(o1["true_bottom"].sum()))


def analyze(label, df):
    print(f"\n{'='*72}")
    print(f"=== {label} ===")
    df = df.copy()
    df["signal_date"] = pd.to_datetime(df["signal_date"]).dt.normalize()
    df["symbol"] = df["symbol"].astype(str).str.upper()
    print(f"n trades: {len(df)} | buy: {int((df['side']=='buy').sum())} | sell: {int((df['side']=='sell').sum())}")

    # join labels Oracle au signal_date
    df = df.merge(o1[["date", "symbol", "true_top", "true_bottom", "oracle_extreme10", "future_return"]],
                  left_on=["signal_date", "symbol"], right_on=["date", "symbol"], how="left")
    matched = df["true_top"].notna().sum()
    print(f"labels Oracle matchés: {matched}/{len(df)}")

    stop_reasons = ["trailing_stop", "initial_stop", "stop_loss", "time_stop"]
    df["is_stop"] = df["exit_reason"].isin(stop_reasons)
    df["is_loss"] = df["return_pct"] < 0

    # VRAIES INVERSIONS Oracle :
    #  - buy prédit TOP mais oracle BOTTOM, sorti par stop
    #  - sell prédit BOTTOM mais oracle TOP, sorti par stop
    buy_inv = (df["side"] == "buy") & (df["true_bottom"] == 1) & df["is_stop"] & df["is_loss"]
    sell_inv = (df["side"] == "sell") & (df["true_top"] == 1) & df["is_stop"] & df["is_loss"]
    inv = df[buy_inv | sell_inv].copy()
    inv["inv_type"] = np.where(inv["side"] == "buy", "buy/TOP->oracleBOTTOM", "sell/BOTTOM->oracleTOP")

    print(f"\n--- VRAIES INVERSIONS (croisement Oracle + stop + perte) ---")
    print(f"n: {len(inv)} / {len(df)} = {len(inv)/len(df)*100:.1f}% des trades")
    if len(inv):
        print(inv["inv_type"].value_counts().to_string())
        print(f"perte moyenne: {inv['return_pct'].mean():.2f}% | médiane: {inv['return_pct'].median():.2f}%")
        print(f"pnl moyen: {inv['pnl'].mean():.2f}")
        print(f"délai moyen: {inv['holding_days'].mean():.1f}j | médiane: {inv['holding_days'].median():.1f}j")
        # par tranche
        bins = [-100, -10, -7.5, -5, -2.5, 0]
        labels = ["<-10%", "-10/-7.5", "-7.5/-5", "-5/-2.5", "-2.5/0"]
        inv2 = inv.copy()
        inv2["tranche"] = pd.cut(inv2["return_pct"], bins=bins, labels=labels)
        for tr, sub in inv2.groupby("tranche", observed=True):
            if len(sub):
                print(f"    {tr}: n={len(sub)} | perte moy {sub['return_pct'].mean():.2f}% | délai moy {sub['holding_days'].mean():.1f}j")

    # part dans les pertes
    losses = df[df["is_loss"]]
    print(f"\n--- part des inversions dans les pertes ---")
    if len(losses) and len(inv):
        print(f"  pertes totales pnl: {losses['pnl'].sum():.2f} | inversions pnl: {inv['pnl'].sum():.2f} | part: {inv['pnl'].sum()/losses['pnl'].sum()*100:.1f}%")
        for typ, sub in inv.groupby("inv_type"):
            side = "long" if "buy" in typ else "short"
            ls = losses[losses["side"] == ("buy" if "buy" in typ else "sell")]
            print(f"    {typ}: pnl={sub['pnl'].sum():.2f} | part pertes {side}={sub['pnl'].sum()/ls['pnl'].sum()*100:.1f}%" if len(ls) and ls['pnl'].sum()<0 else f"    {typ}: pnl={sub['pnl'].sum():.2f}")

    # stats de référence : Oracle a-t-il détecté ces inversions ?
    print(f"\n--- oracle_extreme10 sur ces trades (pool Extreme) ---")
    print(f"  tous trades: extreme={int((df['oracle_extreme10']==1).sum())}/{len(df)}")
    if len(inv):
        print(f"  inversions: extreme={int((inv['oracle_extreme10']==1).sum())}/{len(inv)}")
    return inv


# ===== 2026 =====
tr26 = pd.read_csv("artifacts/benchmarks/OOS2026_B25_P14_m8_v1/trades.csv")
match26 = tr26[tr26["legacy_trade_match"] == True].copy()  # noqa: E712
inv26 = analyze("B25 OOS 2026 (77 trades officiels) — croisement Oracle", match26)

# ===== 2025 =====
tr25 = pd.read_csv("artifacts/backtesting/b25_2025_rankw/trades.csv")
inv25 = analyze("B25 OOS 2025 rankw (119 trades) — croisement Oracle", tr25)
