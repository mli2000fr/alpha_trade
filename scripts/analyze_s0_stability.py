# -*- coding: utf-8 -*-
"""Complement: stabilite IC par split pour TOUS les champions + mismatch F1/IC."""
import json, glob, os, math
import numpy as np
import pandas as pd

BATCH = r"artifacts\models\model-factory-20260814165502-f62322"
files = glob.glob(os.path.join(BATCH, "*", "metrics.json"))
MODELS = ("catboost", "lightgbm", "lstm_attention")

rows = []
for f in files:
    sym = os.path.basename(os.path.dirname(f))
    d = json.load(open(f, encoding="utf-8"))
    champ = (d.get("champion") or {}).get("model_name")
    if champ not in MODELS:
        continue
    c = d.get("challengers", {}).get(champ)
    if not isinstance(c, dict) or not isinstance(c.get("walk_forward"), dict):
        continue
    splits = c["walk_forward"].get("splits", [])
    ics = [s["ic"] for s in splits if isinstance(s.get("ic"), (int, float))]
    f1s = [s["f1_macro"] for s in splits if isinstance(s.get("f1_macro"), (int, float))]
    if not ics or not f1s:
        continue
    r = {"symbol": sym, "champion": champ}
    r["ic"] = float(np.mean(ics)); r["ic_std"] = float(np.std(ics))
    r["ic_neg"] = sum(1 for x in ics if x < 0); r["n"] = len(ics)
    r["ic_last3_pos"] = sum(1 for x in ics[-3:] if x > 0)
    r["f1"] = float(np.mean(f1s)); r["f1_std"] = float(np.std(f1s))
    r["ic_min"] = min(ics); r["ic_max"] = max(ics)
    rows.append(r)

df = pd.DataFrame(rows)
print(f"symboles analyses: {len(df)}")

print("\n=== Stabilite IC par famille de champion ===")
print(df.groupby("champion").agg(n=("symbol", "size"), ic=("ic", "mean"), ic_std=("ic_std", "mean"),
      neg_splits=("ic_neg", "mean"), pct_pos_last3=("ic_last3_pos", lambda s: s.mean() / 3)).round(4).to_string())

print("\n=== IC negatif sur >=50% des splits (champion) ===")
print(df[df["ic_neg"] >= df["n"] / 2].shape[0], "symboles /", len(df))

print("\n=== IC > 0 sur 100% des splits (min 5 splits) ===")
sub = df[(df["ic_neg"] == 0) & (df["n"] >= 5)]
print(f"{len(sub)} symboles")
print(sub[['symbol', 'champion', 'ic', 'ic_std', 'f1', 'n']].round(4).to_string(index=False))

print("\n=== Mismatch F1/IC : f1 >= 0.35 mais IC < 0 (min 4 splits) ===")
print(df[(df["f1"] >= 0.35) & (df["ic"] < 0) & (df["n"] >= 4)][["symbol", "champion", "f1", "ic", "ic_std", "n"]].round(4).to_string(index=False))

print("\n=== Meilleurs compromis f1>=0.30 ET ic>=0.15 ===")
print(df[(df["f1"] >= 0.30) & (df["ic"] >= 0.15)][["symbol", "champion", "f1", "ic", "ic_std"]].sort_values("ic", ascending=False).round(4).to_string(index=False))

print("\n=== corr(f1, ic) et corr(f1_std, ic_std) ===")
print("corr(f1, ic) =", df["f1"].corr(df["ic"]).round(3))
print("corr(f1_std, ic_std) =", df["f1_std"].corr(df["ic_std"]).round(3))
print("\nic_std par quartile de ic:")
q = pd.qcut(df["ic"].rank(method="first"), 4, labels=["Q1", "Q2", "Q3", "Q4"])
print(df.groupby(q, observed=True).agg(n=("symbol", "size"), ic=("ic", "mean"), ic_std=("ic_std", "mean")).round(4).to_string())

print("\n=== Derniers 3 splits (2023-2025) : symboles 3/3 positifs, ic global >= 0, min 5 splits ===")
r = df[(df["ic_last3_pos"] == 3) & (df["ic"] >= 0) & (df["n"] >= 5)]
print(f"{len(r)} symboles")
print(r.nlargest(12, "ic")[["symbol", "champion", "f1", "ic", "ic_std"]].round(4).to_string(index=False))
