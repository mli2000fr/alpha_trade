import pandas as pd
import numpy as np

def analyze(label, df, is_2025=False):
    """Analyse des 'inversions' : buy (pred TOP) ou sell (pred BOTTOM) sortis par stop en perte."""
    print(f"\n{'='*70}")
    print(f"=== {label} ===")
    print(f"n trades: {len(df)} | buy: {int((df['side']=='buy').sum())} | sell: {int((df['side']=='sell').sum())}")

    # colonnes normalisées
    df = df.copy()
    if is_2025:
        df["return_pct"] = df["return_pct"]
        df["holding_days"] = df["holding_days"]
    else:
        df["return_pct"] = df["return_pct"]
        df["holding_days"] = df["holding_days"]

    # stops = trailing_stop / initial_stop / time_stop (sorties mécaniques)
    stop_reasons = ["trailing_stop", "initial_stop", "stop_loss", "time_stop"]
    df["is_stop"] = df["exit_reason"].isin(stop_reasons)
    df["is_loss"] = df["return_pct"] < 0
    df["is_win"] = df["return_pct"] > 0

    # INVERSION : buy sorti par stop en perte (le TOP a baissé) ; sell sorti par stop en perte (le BOTTOM a monté)
    inv = df[df["is_stop"] & df["is_loss"]].copy()
    print(f"\n--- INVERSIONS (stop + perte) ---")
    print(f"n inversions: {len(inv)} / {len(df)} = {len(inv)/len(df)*100:.1f}% des trades")
    if len(inv):
        print(f"  buy (TOP->BOTTOM): {int((inv['side']=='buy').sum())} | sell (BOTTOM->TOP): {int((inv['side']=='sell').sum())}")
        print(f"  perte moyenne: {inv['return_pct'].mean():.2f}% | médiane: {inv['return_pct'].median():.2f}%")
        print(f"  pnl moyen: {inv['pnl'].mean():.2f}")
        print(f"  délai moyen (holding_days): {inv['holding_days'].mean():.1f}j | médiane: {inv['holding_days'].median():.1f}j")

        # par tranche de perte
        print(f"\n  --- par tranche de perte ---")
        bins = [-100, -10, -7.5, -5, -2.5, 0]
        labels = ["<-10%", "-10/-7.5", "-7.5/-5", "-5/-2.5", "-2.5/0"]
        inv2 = inv.copy()
        inv2["tranche"] = pd.cut(inv2["return_pct"], bins=bins, labels=labels)
        g = inv2.groupby("tranche", observed=True)
        for tr, sub in g:
            if len(sub):
                print(f"    {tr}: n={len(sub)} | perte moy {sub['return_pct'].mean():.2f}% | délai moy {sub['holding_days'].mean():.1f}j")
    else:
        print("  (aucune)")

    # pertes totales (long et short)
    losses = df[df["is_loss"]]
    print(f"\n--- PERTES TOTALES ---")
    print(f"n pertes: {len(losses)} ({len(losses)/len(df)*100:.1f}% des trades) | perte moy: {losses['return_pct'].mean():.2f}%")
    loss_long = losses[losses["side"] == "buy"]
    loss_short = losses[losses["side"] == "sell"]
    print(f"  pertes long: n={len(loss_long)} pnl_sum={loss_long['pnl'].sum():.2f} perte_moy={loss_long['return_pct'].mean():.2f}%")
    print(f"  pertes short: n={len(loss_short)} pnl_sum={loss_short['pnl'].sum():.2f} perte_moy={loss_short['return_pct'].mean():.2f}%")

    # part des inversions dans les pertes
    total_loss_pnl = losses["pnl"].sum()  # négatif
    inv_loss_pnl = inv["pnl"].sum()  # négatif
    if total_loss_pnl < 0:
        print(f"\n--- PART DES INVERSIONS DANS LES PERTES ---")
        print(f"  pertes totales (pnl): {total_loss_pnl:.2f}")
        print(f"  pertes des inversions (pnl): {inv_loss_pnl:.2f}")
        print(f"  part inversions / pertes totales: {inv_loss_pnl/total_loss_pnl*100:.1f}%")
        # par côté
        inv_long = inv[inv["side"] == "buy"]
        inv_short = inv[inv["side"] == "sell"]
        for label2, sub in [("long", inv_long), ("short", inv_short)]:
            if len(sub):
                print(f"    inversions {label2}: pnl={sub['pnl'].sum():.2f} | part pertes {label2}="
                      f"{sub['pnl'].sum()/loss_long['pnl'].sum()*100:.1f}%" if label2=="long" and loss_long['pnl'].sum()<0
                      else f"    inversions {label2}: pnl={sub['pnl'].sum():.2f}")
    return inv


# ===== 2026 (77 trades officiels) =====
tr26 = pd.read_csv("artifacts/benchmarks/OOS2026_B25_P14_m8_v1/trades.csv")
match26 = tr26[tr26["legacy_trade_match"] == True].copy()  # noqa: E712
inv26 = analyze("B25 OOS 2026 (77 trades officiels)", match26)

# ===== 2025 (119 trades) =====
tr25 = pd.read_csv("artifacts/backtesting/b25_2025_rankw/trades.csv")
inv25 = analyze("B25 OOS 2025 rankw (119 trades)", tr25, is_2025=True)
