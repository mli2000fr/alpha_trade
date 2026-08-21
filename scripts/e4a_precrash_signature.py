"""E4-A — Temporal Pre-Crash Signature.

Détermine à quel moment avant le mouvement H20 les futurs BOTTOM10 récents
(2025 + 2026H1) deviennent distinguables des futurs TOP10.

Strictement PIT, aucun entraînement, aucun tuning, aucun backtest.

Lags : D-60, D-40, D-20, D-10, D-5, D-3, D-1, D (D = date de prédiction H20).

Deux comparaisons complémentaires :
  1. BOTTOM ratés (BOTTOM_rate)  vs TOP capturés (TOP_capture)  -> cherche le SIGNE
  2. BOTTOM ratés (BOTTOM_rate)  vs BOTTOM capturés (BOTTOM_capture) -> pourquoi Oracle rate l'EXTREME

Pour chaque feature x lag x période : mean/median TOP vs BOTTOM, Cohen's d,
AUC univariée, orientation, N, coverage.

Verdict A/B/C/D :
  A = aucune séparation même à D-1/D ; B = séparation seulement D-1/D-3 (trop tardif pour H20) ;
  C = séparation D-5/D-10 (piste) ; D = séparation D-20+ (anomalie, info existante inexploitée).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from modelFactory.oracle.train import roc_auc

TIMELINE = Path("artifacts/models/oracle/e4a_timeline_features.parquet")
DATA = Path("artifacts/models/oracle/e2_feature_dataset.parquet")   # groupes TOP/BOTTOM capture/rate
OOS = Path("artifacts/models/oracle/oracle-wf-20260819034014/oos_predictions.parquet")
OUT = Path("artifacts/models/oracle/e4a_precrash_signature.md")

LAGS = [60, 40, 20, 10, 5, 3, 1, 0]
PERIODS = ["2025", "2026H1"]

# Familles principales (features présentes dans la timeline)
FEATURE_FAMILIES = {
    "momentum": ["momentum_5", "momentum_10", "momentum_20", "momentum_60"],
    "relative_strength": ["relative_strength_5", "relative_strength_20", "relative_strength_60"],
    "range_position": ["range_position_20", "range_position_50"],
    "drawdown": ["drawdown_20"],
    "rsi": ["rsi_5", "rsi_14", "rsi_21"],
    "volatility": ["rolling_volatility_10", "rolling_volatility_20", "rolling_volatility_60"],
    "atr": ["atr_14_norm", "atr20_pct"],
    "volume": ["volume_ratio_5", "volume_ratio_20", "volume_zscore_5d", "volume_zscore_20"],
    "gap": ["overnight_gap", "gap_fade"],
    "return": ["return_5d", "return_10d", "return_20d"],
    "global_rank": ["global_rank_20"],
}
# features réellement présentes dans la timeline
ALL_FEATS = [f for fam in FEATURE_FAMILIES.values() for f in fam]


def _cohen_d(a: pd.Series, b: pd.Series) -> float:
    a = a.dropna().to_numpy(dtype=float)
    b = b.dropna().to_numpy(dtype=float)
    if len(a) < 10 or len(b) < 10:
        return float("nan")
    na, nb = len(a), len(b)
    sp = np.sqrt(((na - 1) * a.std(ddof=1) ** 2 + (nb - 1) * b.std(ddof=1) ** 2) / (na + nb - 2))
    if sp < 1e-12:
        return float("nan")
    return float((a.mean() - b.mean()) / sp)


def _auc(y, s) -> float:
    y = np.asarray(y, dtype=float)
    s = np.asarray(s, dtype=float)
    m = np.isfinite(s) & np.isfinite(y)
    y, s = y[m], s[m]
    if len(y) < 20 or len(np.unique(y)) < 2 or np.all(s == s[0]):
        return float("nan")
    return roc_auc(y, s) or float("nan")


def main() -> None:
    tl = pd.read_parquet(TIMELINE)
    tl["date"] = pd.to_datetime(tl["date"]).dt.normalize()
    tl["symbol"] = tl["symbol"].astype(str)
    # garder les features O1 réellement dispo
    feats = [c for c in ALL_FEATS if c in tl.columns]
    print(f"timeline: {len(tl):,} lignes | {tl['date'].min().date()} -> {tl['date'].max().date()} | features={len(feats)}")
    tl = tl[["date", "symbol"] + feats].copy()

    # ── Population : groupes sur le dataset O1 restreint ──
    ds = pd.read_parquet(DATA)
    oos = pd.read_parquet(OOS)
    ds["date"] = pd.to_datetime(ds["date"]).dt.normalize()
    oos["date"] = pd.to_datetime(oos["date"]).dt.normalize()
    m = ds.merge(oos[["date", "symbol", "proba_extreme"]], on=["date", "symbol"], how="inner")
    m["true_top"] = (m["oracle_pct_rank"] >= 0.90).astype(int)
    m["true_bottom"] = (m["oracle_pct_rank"] <= 0.10).astype(int)
    m["oracle_rank"] = m.groupby("date")["proba_extreme"].rank(pct=True)
    m["pred_top"] = (m["oracle_rank"] >= 0.90).astype(int)
    m["grp"] = np.select(
        [(m["pred_top"] == 1) & (m["true_top"] == 1),
         (m["pred_top"] == 0) & (m["true_bottom"] == 1),
         (m["pred_top"] == 1) & (m["true_bottom"] == 1)],
        ["TOP_capture", "BOTTOM_rate", "BOTTOM_capture"],
        default="other",
    )
    m["period"] = np.where(m["date"].dt.year < 2026, m["date"].dt.year.astype(str), "2026H1")
    pop = m[m["period"].isin(PERIODS) & m["grp"].isin(["TOP_capture", "BOTTOM_rate", "BOTTOM_capture"])].copy()
    print(f"population: {len(pop):,} | TOP_capture={int((pop['grp']=='TOP_capture').sum()):,} "
          f"BOTTOM_rate={int((pop['grp']=='BOTTOM_rate').sum()):,} "
          f"BOTTOM_capture={int((pop['grp']=='BOTTOM_capture').sum()):,}")

    # ── Extraire les features aux lags depuis la timeline ──
    # merge_asof (direction=backward) : dernière ligne timeline <= (D - lag).
    # Strictement PIT : pas de lookahead, week-end -> dernière ouverture précédente.
    if "oracle_extreme10" not in pop.columns:
        pop["oracle_extreme10"] = np.nan
    tl_sorted = tl.sort_values("date")
    pop_feat = pop[["date", "symbol", "period", "grp", "oracle_extreme10"]].copy()
    for lag in LAGS:
        left = pop[["date", "symbol"]].copy()
        left["target_date"] = left["date"] - pd.Timedelta(days=lag)
        left["_orig_idx"] = np.arange(len(left))
        left = left.sort_values("target_date")
        merged = pd.merge_asof(
            left, tl_sorted,
            left_on="target_date", right_on="date",
            by="symbol", direction="backward",
        )
        merged = merged.set_index("_orig_idx").sort_index()
        for f in feats:
            pop_feat[f"{f}@{lag}"] = merged[f].to_numpy()
    print(f"pop_feat: {len(pop_feat):,} lignes | colonnes lag:", sum(1 for c in pop_feat.columns if "@" in c))

    md: list[str] = [
        "# E4-A — Temporal Pre-Crash Signature (BOTTOM ratés vs TOP capturés)",
        "",
        "Lags : D-60, D-40, D-20, D-10, D-5, D-3, D-1, D (D = date de prédiction H20).",
        "Strictement PIT. Population 2025 + 2026H1. Aucun entraînement/tuning.",
        "",
    ]

    # ── 1. Signe : BOTTOM_rate vs TOP_capture, AUC par feature x lag ──
    md.append("## 1. AUC univariée TOP vs BOTTOM (BOTTOM_rate vs TOP_capture) par feature x lag")
    md.append("")
    md.append("| feature | " + " | ".join(f"D-{lag}" if lag else "D" for lag in LAGS) + " |")
    md.append("|" + "---|" * (len(LAGS) + 1) + "|")
    print("\n=== 1. AUC (BOTTOM_rate vs TOP_capture) ===")
    best_rows: list[tuple] = []
    for f in feats:
        aucs = []
        for lag in LAGS:
            col = f"{f}@{lag}"
            if col not in pop_feat.columns:
                aucs.append("-")
                continue
            sub = pop_feat[["grp", col]].dropna()
            a = sub["grp"].map({"TOP_capture": 1, "BOTTOM_rate": 0})
            sub = sub.assign(y=a)
            aucs.append(f"{_auc(sub['y'], sub[col]):.3f}")
        md.append("| " + f + " | " + " | ".join(aucs) + " |")
        # score max par feature
        vals = [float(x) for x in aucs if x != "-"]
        if vals:
            best_rows.append((f, max(vals), LAGS[vals.index(max(vals))]))
    print("  (meilleure AUC par feature, lag optimal apparent)")
    for f, auc, lag in sorted(best_rows, key=lambda x: -x[1])[:15]:
        print(f"  {f:<32} AUC={auc:.3f} @ D-{lag if lag else 'D'}")

    # ── 2. Cohen's d par feature x lag ──
    md.append("")
    md.append("## 2. Cohen's d (TOP_capture - BOTTOM_rate) par feature x lag")
    md.append("")
    md.append("| feature | " + " | ".join(f"D-{lag}" if lag else "D" for lag in LAGS) + " |")
    md.append("|" + "---|" * (len(LAGS) + 1) + "|")
    for f in feats:
        ds_lag = []
        for lag in LAGS:
            col = f"{f}@{lag}"
            if col not in pop_feat.columns:
                ds_lag.append("-")
                continue
            t = pop_feat[pop_feat["grp"] == "TOP_capture"][col]
            b = pop_feat[pop_feat["grp"] == "BOTTOM_rate"][col]
            ds_lag.append(f"{_cohen_d(t, b):+.3f}")
        md.append("| " + f + " | " + " | ".join(ds_lag) + " |")

    # ── 3. Par période 2025 vs 2026H1 (AUC, feature x lag) ──
    md.append("")
    md.append("## 3. AUC par période (BOTTOM_rate vs TOP_capture) — 2025 puis 2026H1")
    md.append("")
    for per in PERIODS:
        subp = pop_feat[pop_feat["period"] == per]
        md.append(f"### {per} (N={len(subp):,})")
        md.append("")
        md.append("| feature | " + " | ".join(f"D-{lag}" if lag else "D" for lag in LAGS) + " |")
        md.append("|" + "---|" * (len(LAGS) + 1) + "|")
        for f in feats:
            aucs = []
            for lag in LAGS:
                col = f"{f}@{lag}"
                if col not in subp.columns:
                    aucs.append("-")
                    continue
                s2 = subp[["grp", col]].dropna()
                if len(s2) < 20:
                    aucs.append("-")
                    continue
                y = s2["grp"].map({"TOP_capture": 1, "BOTTOM_rate": 0})
                aucs.append(f"{_auc(y, s2[col]):.3f}")
            md.append("| " + f + " | " + " | ".join(aucs) + " |")

    # ── 4. Contrôle : BOTTOM_capture vs BOTTOM_rate (pourquoi Oracle rate l'extrême) ──
    md.append("")
    md.append("## 4. Contrôle : BOTTOM_capture vs BOTTOM_rate (AUC) par feature x lag")
    md.append("")
    md.append("| feature | " + " | ".join(f"D-{lag}" if lag else "D" for lag in LAGS) + " |")
    md.append("|" + "---|" * (len(LAGS) + 1) + "|")
    for f in feats:
        aucs = []
        for lag in LAGS:
            col = f"{f}@{lag}"
            if col not in pop_feat.columns:
                aucs.append("-")
                continue
            s2 = pop_feat[pop_feat["grp"].isin(["BOTTOM_capture", "BOTTOM_rate"])][["grp", col]].dropna()
            if len(s2) < 20:
                aucs.append("-")
                continue
            y = s2["grp"].map({"BOTTOM_capture": 1, "BOTTOM_rate": 0})
            aucs.append(f"{_auc(y, s2[col]):.3f}")
        md.append("| " + f + " | " + " | ".join(aucs) + " |")

    # ── 5. Trajectoire normalisée : delta vs D-60 (émergence temporelle) ──
    # AUC du DELTA (feature@lag - feature@D-60) pour le même titre.
    #  - AUC(delta) ~ 0.5 partout  -> separation = NIVEAU PERMANENT (pas de signature pre-crash)
    #  - AUC(delta) monte a D-10/D-5 -> l'evolution relative est informative (signature)
    md.append("")
    md.append("## 5. Trajectoire normalisee (delta vs D-60) — BOTTOM_rate vs TOP_capture")
    md.append("")
    md.append("AUC du delta `feature@lag - feature@D-60` (meme titre). 0.5 = separation")
    md.append("de niveau PERMANENT (aucune emergence temporelle). >0.55 a D-10/D-5 = piste.")
    md.append("")
    lags_sig = [l for l in LAGS if l != 60]
    md.append("| feature | " + " | ".join(f"D-{lag}" if lag else "D" for lag in lags_sig) + " |")
    md.append("|" + "---|" * (len(lags_sig) + 1) + "|")
    for f in feats:
        aucs = []
        for lag in lags_sig:
            col = f"{f}@{lag}"
            base = f"{f}@60"
            if col not in pop_feat.columns or base not in pop_feat.columns:
                aucs.append("-")
                continue
            s2 = pop_feat[pop_feat["grp"].isin(["TOP_capture", "BOTTOM_rate"])][["grp", col, base]].dropna()
            if len(s2) < 20:
                aucs.append("-")
                continue
            y = s2["grp"].map({"TOP_capture": 1, "BOTTOM_rate": 0})
            aucs.append(f"{_auc(y, s2[col] - s2[base]):.3f}")
        md.append("| " + f + " | " + " | ".join(aucs) + " |")

    # ── 6. Trajectoire normalisee (delta vs D-60) — BOTTOM_capture vs BOTTOM_rate ──
    md.append("")
    md.append("## 6. Trajectoire normalisee (delta vs D-60) — BOTTOM_capture vs BOTTOM_rate")
    md.append("")
    md.append("| feature | " + " | ".join(f"D-{lag}" if lag else "D" for lag in lags_sig) + " |")
    md.append("|" + "---|" * (len(lags_sig) + 1) + "|")
    for f in feats:
        aucs = []
        for lag in lags_sig:
            col = f"{f}@{lag}"
            base = f"{f}@60"
            if col not in pop_feat.columns or base not in pop_feat.columns:
                aucs.append("-")
                continue
            s2 = pop_feat[pop_feat["grp"].isin(["BOTTOM_capture", "BOTTOM_rate"])][["grp", col, base]].dropna()
            if len(s2) < 20:
                aucs.append("-")
                continue
            y = s2["grp"].map({"BOTTOM_capture": 1, "BOTTOM_rate": 0})
            aucs.append(f"{_auc(y, s2[col] - s2[base]):.3f}")
        md.append("| " + f + " | " + " | ".join(aucs) + " |")

    OUT.write_text("\n".join(md), encoding="utf-8")
    print("\nrapport:", OUT)


if __name__ == "__main__":
    main()
