# -*- coding: utf-8 -*-
"""Echantillon stratifie de 40 symboles representatifs du batch S0.

Stratification:
- par champion (proportionnel aux effectifs reels)
- dans chaque groupe: 25% meilleurs IC, 50% IC moyens, 25% pires IC
- selection deterministe (indices regulierement espaces dans chaque bande)
"""
import os
import numpy as np
import pandas as pd

BATCH = r"artifacts\models\model-factory-20260814165502-f62322"
CSV = os.path.join(BATCH, "_per_symbol_analysis.csv")
df = pd.read_csv(CSV)
df = df[df["champ_ic"].notna()].copy()
df = df.sort_values(["champion", "champ_ic"], kind="stable").reset_index(drop=True)
print(f"population avec IC: {len(df)}")

# Allocation proportionnelle aux effectifs champions (total 40)
counts = df.groupby("champion").size()
total = counts.sum()
alloc = (counts / total * 40).round().astype(int)
# ajuster pour faire exactement 40
diff = 40 - alloc.sum()
alloc[alloc.idxmax()] += diff
print("allocation par champion:", alloc.to_dict())

def pick_band(group, n_band, band):
    """Selection d'indices regulierement espaces dans une bande triee par IC."""
    lo, hi = band
    sub = group.iloc[lo:hi]
    if n_band >= len(sub):
        idx = np.arange(len(sub))
    else:
        idx = np.linspace(0, len(sub) - 1, n_band).round().astype(int)
    out = sub.iloc[idx].copy()
    return out

picked = []
for champ, n in alloc.items():
    g = df[df["champion"] == champ].reset_index(drop=True)
    n_top = int(round(n * 0.25))
    n_bot = n_top
    n_mid = n - n_top - n_bot
    # bandes en quartiles: bottom = premier quart, top = dernier quart
    q = len(g) // 4
    picked.append(pick_band(g, n_bot, (0, q)).assign(band="pire"))
    picked.append(pick_band(g, n_mid, (q, len(g) - q)).assign(band="moyen"))
    picked.append(pick_band(g, n_top, (len(g) - q, len(g))).assign(band="meilleur"))

sample = pd.concat(picked).sort_values(["champion", "champ_ic"])
print(f"\n=== ECHANTILLON: {len(sample)} symboles ===")
print(sample.groupby(["champion", "band"]).size().to_string())

print("\n=== Comparaison population vs echantillon ===")
for name, d in (("population", df), ("echantillon", sample)):
    print(f"{name:12s} n={len(d):3d}  IC mean={d['champ_ic'].mean():.4f}  IC med={d['champ_ic'].median():.4f}  "
          f"IC min={d['champ_ic'].min():.4f}  IC max={d['champ_ic'].max():.4f}  F1 mean={d['champ_f1'].mean():.4f}")
print("\nChampions population:", (df.groupby("champion").size() / len(df)).round(3).to_dict())
print("Champions echantillon:", (sample.groupby("champion").size() / len(sample)).round(3).to_dict())

print("\n=== LISTE DES 40 ===")
cols = ["symbol", "champion", "band", "champ_ic", "champ_f1", "champ_dir"]
print(sample[cols].round(4).to_string(index=False))

out = os.path.join(BATCH, "_sample_40_representatif.csv")
sample[cols + ["champ_mse"]].round(6).to_csv(out, index=False)
print("\nCSV:", out)
