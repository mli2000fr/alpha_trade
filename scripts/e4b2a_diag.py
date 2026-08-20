"""E4-B2A — Diagnostic short sale volume conditionnel à Oracle Extreme (UP vs DOWN).

Sans modèle. Population = pool Oracle Extreme (oracle_extreme10=1) restreint aux
400 symboles de trade (config/ticket_recherche.txt). Target future_return_H20 :
UP (>0) vs DOWN (<0). Diagnostic secondaire : BOTTOM ratés vs TOP capturés.

AUC (Mann-Whitney), mean/median UP vs DOWN, Cohen d, p, permutation null,
stabilité par période 2022/2023/2024/2025/2026H1/ALL.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu

FEAT = Path("artifacts/models/oracle/e4b2a_short_volume_features.parquet")
DATA = Path("artifacts/models/oracle/e2_feature_dataset.parquet")
OOS = Path("artifacts/models/oracle/oracle-wf-20260819034014/oos_predictions.parquet")
TICKET = Path("config/ticket_recherche.txt")
OUT = Path("artifacts/models/oracle/e4b2a_short_volume_diag.md")

PERIODS = ["2022", "2023", "2024", "2025", "2026H1", "ALL"]
DIAG_FEATS = ["short_volume_ratio_1d", "short_volume_ratio_5d", "short_volume_ratio_20d",
              "short_volume_zscore_20", "short_volume_zscore_60",
              "short_pressure_change_5d", "short_pressure_change_20d", "short_ratio_trend_10d",
              "short_share", "ret5_x_short_ratio", "rel_short_pressure_sector"]


def _auc(y, s):
    m = np.isfinite(s) & np.isfinite(y)
    y, s = y[m], s[m]
    if len(y) < 10 or len(np.unique(y)) < 2 or np.all(s == s[0]):
        return float("nan")
    try:
        u, _ = mannwhitneyu(s[y == 1], s[y == 0], alternative="two-sided")
        return float(u / (np.sum(y == 1) * np.sum(y == 0)))
    except ValueError:
        return float("nan")


def _pval(y, s):
    m = np.isfinite(s) & np.isfinite(y)
    y, s = y[m], s[m]
    if len(y) < 10 or len(np.unique(y)) < 2 or np.all(s == s[0]):
        return float("nan")
    try:
        _, p = mannwhitneyu(s[y == 1], s[y == 0], alternative="two-sided")
        return float(p)
    except ValueError:
        return float("nan")


def _cohen_d(a, b):
    a = a.dropna().to_numpy(dtype=float)
    b = b.dropna().to_numpy(dtype=float)
    if len(a) < 10 or len(b) < 10:
        return float("nan")
    sp = np.sqrt(((len(a) - 1) * a.std(ddof=1) ** 2 + (len(b) - 1) * b.std(ddof=1) ** 2) / (len(a) + len(b) - 2))
    if sp < 1e-12:
        return float("nan")
    return float((a.mean() - b.mean()) / sp)


def main() -> None:
    ticket = sorted({s.strip().upper() for s in TICKET.read_text(encoding="utf-8").split(",") if s.strip()})
    sv = pd.read_parquet(FEAT)
    for c in ("date",):
        sv[c] = pd.to_datetime(sv[c]).dt.normalize()
    sv["symbol"] = sv["symbol"].astype(str).str.upper()

    ds = pd.read_parquet(DATA)
    oos = pd.read_parquet(OOS)
    for c in ("date",):
        ds[c] = pd.to_datetime(ds[c]).dt.normalize()
        oos[c] = pd.to_datetime(oos[c]).dt.normalize()
    m = ds.merge(oos[["date", "symbol", "proba_extreme"]], on=["date", "symbol"], how="inner")
    m["true_top"] = (m["oracle_pct_rank"] >= 0.90).astype(int)
    m["true_bottom"] = (m["oracle_pct_rank"] <= 0.10).astype(int)
    m["oracle_rank"] = m.groupby("date")["proba_extreme"].rank(pct=True)
    m["pred_top"] = (m["oracle_rank"] >= 0.90).astype(int)
    m["grp"] = np.select(
        [(m["pred_top"] == 1) & (m["true_top"] == 1),
         (m["pred_top"] == 0) & (m["true_bottom"] == 1),
         (m["pred_top"] == 1) & (m["true_bottom"] == 1)],
        ["TOP_capture", "BOTTOM_rate", "BOTTOM_capture"], default="other")
    m["period"] = np.where(m["date"].dt.year < 2026, m["date"].dt.year.astype(str), "2026H1")
    extreme = m[(m["oracle_extreme10"] == 1) & m["symbol"].isin(set(ticket))].copy()
    extreme["up"] = (extreme["future_return"] > 0).astype(int)
    extreme = extreme[extreme["future_return"] != 0].copy()
    print(f"pool Extreme 400: {len(extreme):,} | UP={int((extreme['up']==1).sum()):,} DOWN={int((extreme['up']==0).sum()):,}")

    # join features (merge sur date+symbol, PIT : features calculées à la date D)
    full = extreme.merge(sv, on=["date", "symbol"], how="left")
    print(f"couverture features: " + " ".join(
        f"{f}={full[f].notna().mean()*100:.0f}%" for f in DIAG_FEATS))

    md: list[str] = [
        "# E4-B2A — Diagnostic short sale volume (FINRA) conditionnel à Oracle Extreme",
        "",
        f"Population : pool Oracle Extreme restreint aux {len(ticket)} symboles de trade. "
        f"N={len(full):,} (UP {int((full['up']==1).sum()):,} / DOWN {int((full['up']==0).sum()):,}).",
        "Source : FINRA Daily Short Sale Volume (CNMSshvol), PIT. Attention : volume short quotidien",
        "= activite TRF/ADF/ORF reportee, PAS le short interest, PAS consolide avec tous les exchanges.",
        "AUC = Mann-Whitney U normalise (UP=1). Strictement PIT.",
        "",
    ]

    # 1. UP/DOWN par période
    for per in PERIODS:
        sub = full if per == "ALL" else full[full["period"] == per]
        if sub.empty:
            continue
        md.append(f"## UP/DOWN {per} (N={len(sub):,}, UP={int((sub['up']==1).sum()):,}, "
                  f"DOWN={int((sub['up']==0).sum()):,})")
        md.append("")
        md.append("| feature | AUC | mean UP | mean DOWN | median UP | median DOWN | d | p | N | cov% |")
        md.append("|---|---|---|---|---|---|---|---|---|---|")
        for f in DIAG_FEATS:
            s2 = sub[["up", f]].dropna()
            if len(s2) < 20:
                md.append(f"| {f} | - | - | - | - | - | - | - | {len(s2)} | 0 |")
                continue
            y = s2["up"].to_numpy()
            s = s2[f].to_numpy()
            up_v = s2.loc[s2["up"] == 1, f]
            dn_v = s2.loc[s2["up"] == 0, f]
            md.append(
                f"| {f} | {_auc(y, s):.3f} | {up_v.mean():.4f} | {dn_v.mean():.4f} | "
                f"{up_v.median():.4f} | {dn_v.median():.4f} | {_cohen_d(up_v, dn_v):+.3f} | "
                f"{_pval(y, s):.2e} | {len(s2):,} | {len(s2)/len(sub)*100:.0f} |"
            )

    # 2. Secondaire : BOTTOM ratés vs TOP capturés par période
    md.append("")
    md.append("## Secondaire : BOTTOM ratés vs TOP capturés — par période")
    md.append("")
    for per in PERIODS:
        sub = full if per == "ALL" else full[full["period"] == per]
        sub = sub[sub["grp"].isin(["BOTTOM_rate", "TOP_capture"])]
        if sub.empty:
            continue
        md.append(f"### {per} (N={len(sub):,}, BOTTOM_rate={int((sub['grp']=='BOTTOM_rate').sum()):,}, "
                  f"TOP_capture={int((sub['grp']=='TOP_capture').sum()):,})")
        md.append("")
        md.append("| feature | AUC(BOTTOM=1) | mean BOTTOM | mean TOP | median BOTTOM | median TOP | d | N |")
        md.append("|---|---|---|---|---|---|---|---|")
        for f in DIAG_FEATS:
            s2 = sub[["grp", f]].dropna()
            if len(s2) < 20:
                md.append(f"| {f} | - | - | - | - | - | - | {len(s2)} |")
                continue
            y = (s2["grp"] == "BOTTOM_rate").astype(int).to_numpy()
            s = s2[f].to_numpy()
            br = s2.loc[s2["grp"] == "BOTTOM_rate", f]
            tc = s2.loc[s2["grp"] == "TOP_capture", f]
            md.append(
                f"| {f} | {_auc(y, s):.3f} | {br.mean():.4f} | {tc.mean():.4f} | "
                f"{br.median():.4f} | {tc.median():.4f} | {_cohen_d(br, tc):+.3f} | {len(s2):,} |"
            )

    # 3. Permutation null (UP/DOWN ALL)
    md.append("")
    md.append("## Permutation null (AUC sous labels permutés, 200 répliques, UP/DOWN ALL)")
    md.append("")
    md.append("| feature | AUC observé | p25 null | p50 null | p95 null | p99 null | p_perm (|AUC|>0.03) |")
    md.append("|---|---|---|---|---|---|---|")
    rng = np.random.default_rng(42)
    for f in DIAG_FEATS:
        s2 = full[["up", f]].dropna()
        if len(s2) < 1000:
            md.append(f"| {f} | - | - | - | - | - | - |")
            continue
        y0 = s2["up"].to_numpy()
        s0 = s2[f].to_numpy()
        obs = _auc(y0, s0)
        n = min(len(y0), 6000)
        idx = rng.choice(len(y0), n, replace=False)
        ys, ss = y0[idx], s0[idx]
        null = np.array([_auc(ys[rng.permutation(n)], ss) for _ in range(200)])
        null = null[np.isfinite(null)]
        if len(null) < 50:
            md.append(f"| {f} | {obs:.3f} | - | - | - | - | - |")
            continue
        p_perm = float(np.mean(np.abs(null - 0.5) >= abs(obs - 0.5)))
        md.append(
            f"| {f} | {obs:.3f} | {np.percentile(null,25):.3f} | {np.percentile(null,50):.3f} | "
            f"{np.percentile(null,95):.3f} | {np.percentile(null,99):.3f} | {p_perm:.3f} |"
        )

    OUT.write_text("\n".join(md), encoding="utf-8")
    print("\nrapport:", OUT)


if __name__ == "__main__":
    main()
