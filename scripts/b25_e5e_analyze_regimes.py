"""E5-E — Analyse ΔPnL(4x13 − 3x7) par régime PIT, avec validation multi-périodes.

Question : existe-t-il un état PIT (connu à l'entrée) où 4×13 est systématiquement
inférieur à 3×7, et cet état apparaît-il ailleurs qu'en 2024H1 ?

Gate anti-overfit : un pattern n'est retenu que s'il est visible DANS PLUSIEURS
périodes (pas seulement 2024H1 = TP serré / tout le reste = TP large).
"""
import numpy as np
import pandas as pd

df = pd.read_parquet("artifacts/models/oracle/e5e_delta_by_trade.parquet")
df["delta"] = df["delta"].astype(float)

PERIOD_LABEL = {"2022": "2022", "2023": "2023 H1", "2024": "2024 H1", "2025": "2025", "2026": "2026 H1"}
PERIODS = ["2022", "2023", "2024", "2025", "2026"]


def table(metric_col, label, n_buckets=3, reverse=False):
    """Découpe une métrique en n_buckets et montre Δ mean par bucket × période."""
    print(f"\n{'=' * 100}")
    print(f"ΔPnL(4x13−3x7) par {label} (buckets de {metric_col})")
    print(f"{'=' * 100}")
    df_valid = df.dropna(subset=[metric_col])
    if df_valid.empty:
        print("  pas de données")
        return
    try:
        df_valid["bucket"] = pd.qcut(df_valid[metric_col], n_buckets, labels=False, duplicates="drop")
    except Exception:
        df_valid["bucket"] = pd.cut(df_valid[metric_col], n_buckets, labels=False)
    # vue globale
    piv = df_valid.groupby("bucket")["delta"].agg(["mean", "sum", "count", lambda s: (s < 0).mean()])
    piv.columns = ["mean", "sum", "n", "pct_neg"]
    print(f"{'bucket':>6} {'mean':>9} {'sum':>10} {'n':>5} {'pct_neg':>8}   range {metric_col}")
    for b in sorted(piv.index):
        lo = df_valid.loc[df_valid["bucket"] == b, metric_col].min()
        hi = df_valid.loc[df_valid["bucket"] == b, metric_col].max()
        r = piv.loc[b]
        print(f"{b:>6} {r['mean']:>9.1f} {r['sum']:>10.0f} {r['n']:>5.0f} {r['pct_neg']:>8.1%}   [{lo:.4f}, {hi:.4f}]")
    # vue par période dans le bucket le plus bas et le plus haut
    print(f"\n  Détail par période — bucket {label} MIN et MAX :")
    for b in sorted(piv.index):
        if b not in (sorted(piv.index)[0], sorted(piv.index)[-1]):
            continue
        sub = df_valid[df_valid["bucket"] == b]
        print(f"  [{label} bucket {b}]")
        for p in PERIODS:
            sp = sub[sub["period"] == p]
            if len(sp):
                print(f"    {PERIOD_LABEL[p]:8}: n={len(sp):3d} mean={sp['delta'].mean():8.1f} sum={sp['delta'].sum():9.0f} pct_neg={ (sp['delta']<0).mean():.0%}")
    return piv


# ── 1. SPY trend ──
table("spy_ret_20", "SPY retour 20j")
table("spy_above_sma50", "SPY > SMA50", n_buckets=2)
table("spy_vol20", "SPY vol 20j")
table("spy_sma50_gap", "SPY gap SMA50")

# ── 2. Titre ──
table("atr_pct_20", "ATR% titre 20j")
table("mom_20", "momentum titre 20j")
table("above_sma50", "titre > SMA50", n_buckets=2)

# ── 3. Interaction SPY trend × vol ──
print(f"\n{'=' * 100}")
print("Interaction SPY retour20 × SPY vol20 (quartiles)")
print(f"{'=' * 100}")
dfv = df.dropna(subset=["spy_ret_20", "spy_vol20"])
try:
    dfv["ret_b"] = pd.qcut(dfv["spy_ret_20"], 2, labels=["ret_faible", "ret_fort"], duplicates="drop")
    dfv["vol_b"] = pd.qcut(dfv["spy_vol20"], 2, labels=["vol_faible", "vol_forte"], duplicates="drop")
except Exception:
    dfv["ret_b"] = pd.cut(dfv["spy_ret_20"], 2, labels=["ret_faible", "ret_fort"])
    dfv["vol_b"] = pd.cut(dfv["spy_vol20"], 2, labels=["vol_faible", "vol_forte"])
for (r, v), g in dfv.groupby(["ret_b", "vol_b"]):
    print(f"  SPY {r}/{v}: n={len(g):3d} mean={g['delta'].mean():8.1f} sum={g['delta'].sum():9.0f} pct_neg={(g['delta']<0).mean():.0%}")
    # par période
    for p in PERIODS:
        sp = g[g["period"] == p]
        if len(sp):
            print(f"      {PERIOD_LABEL[p]:8}: n={len(sp):3d} mean={sp['delta'].mean():8.1f} pct_neg={(sp['delta']<0).mean():.0%}")
