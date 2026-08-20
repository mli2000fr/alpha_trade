"""E5-E — Comparaison des états PIT entre semestres '4x13 mauvais' et '4x13 bon'.

Semestres 4x13 mauvais (Δ Ret < 0 marqué) : 2022H1 (-9.2), 2024H1 (-20.7)
Semestres 4x13 bon (Δ Ret > 0) : 2022H2 (+10.5), 2023H1 (+1.8), 2025H1 (+8.4),
                                2025H2 (+14.7), 2026H1 (+1.2)

Question : y a-t-il un état PIT (SPY trend/vol, ATR, momentum) commun aux deux
semestres mauvais, absent des bons ? Si non → pas de règle conditionnelle justifiable.
"""
import numpy as np
import pandas as pd

df = pd.read_parquet("artifacts/models/oracle/e5e_delta_by_trade.parquet")
df["entry_date"] = pd.to_datetime(df["entry_date"])
df["period"] = df["period"].astype(str)

# assigner chaque trade à un semestre
df["sem"] = df.apply(
    lambda r: f"{r['entry_date'].year} H1" if r["entry_date"].month <= 6 else f"{r['entry_date'].year} H2",
    axis=1,
)

# semestres des cohortes matchées (uniquement trades communs)
print("Cohortes matchées par semestre :")
print(df.groupby("sem")["delta"].agg(["mean", "sum", "count"]))

FEATS = ["spy_ret_5", "spy_ret_20", "spy_ret_60", "spy_sma50_gap", "spy_vol20",
         "atr_pct_20", "mom_20", "mom_60", "vol20", "ret_5"]

BAD = {"2022 H1", "2024 H1"}
GOOD = {"2022 H2", "2023 H1", "2025 H1", "2025 H2", "2026 H1"}

print("\n=== Moyennes features PIT par semestre (cohortes matchées) ===")
hdr = f"{'sem':9}" + "".join(f"{f:>12}" for f in FEATS)
print(hdr)
for sem in ["2022 H1", "2022 H2", "2023 H1", "2024 H1", "2025 H1", "2025 H2", "2026 H1"]:
    sub = df[df["sem"] == sem]
    if not len(sub):
        print(f"{sem:9}  (aucune cohorte matchée)")
        continue
    row = f"{sem:9}" + "".join(f"{sub[f].mean():12.4f}" if sub[f].notna().any() else f"{'n/a':>12}" for f in FEATS)
    print(row)

print("\n=== Comparaison BAD (2022H1+2024H1) vs GOOD (autres) ===")
for f in FEATS:
    b = df[df["sem"].isin(BAD)][f].dropna()
    g = df[df["sem"].isin(GOOD)][f].dropna()
    if len(b) and len(g):
        print(f"  {f:14}: BAD mean={b.mean():.4f} n={len(b):3d} | GOOD mean={g.mean():.4f} n={len(g):3d} | diff={b.mean()-g.mean():+.4f}")

# focus : les semestres BAD tombent-ils dans des buckets extrêmes de features ?
print("\n=== Distribution des semestres BAD vs GOOD sur SPY ret20 & vol20 (quartiles) ===")
dfv = df.dropna(subset=["spy_ret_20", "spy_vol20"])
try:
    dfv["retq"] = pd.qcut(dfv["spy_ret_20"], 4, labels=["Q1","Q2","Q3","Q4"], duplicates="drop")
    dfv["volq"] = pd.qcut(dfv["spy_vol20"], 4, labels=["Q1","Q2","Q3","Q4"], duplicates="drop")
except Exception:
    dfv["retq"] = pd.cut(dfv["spy_ret_20"], 4, labels=["Q1","Q2","Q3","Q4"])
    dfv["volq"] = pd.cut(dfv["spy_vol20"], 4, labels=["Q1","Q2","Q3","Q4"])
print(f"{'cellule':16} {'BAD n':>6} {'GOOD n':>7} {'BAD meanΔ':>10} {'GOOD meanΔ':>11}")
for (rq, vq), g in dfv.groupby(["retq", "volq"]):
    b = g[g["sem"].isin(BAD)]
    go = g[g["sem"].isin(GOOD)]
    print(f"{f'{rq}/{vq}':16} {len(b):>6} {len(go):>7} {b['delta'].mean() if len(b) else float('nan'):>10.1f} {go['delta'].mean() if len(go) else float('nan'):>11.1f}")
