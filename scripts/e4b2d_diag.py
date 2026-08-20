"""E4-B2D — Diagnostic fundamentals conditionnel à Oracle Extreme (UP vs DOWN).

Audit LÉGER : univarié, même gate que E4-B2A/B2B/B2C. Population = pool Oracle
Extreme (oracle_extreme10=1) restreint aux 400 symboles. Target future_return_H20
UP (>0) vs DOWN (<0). PIT strict via merge_asof backward sur trade_date.
forward_pe est exclu (colonne vide).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu

FEAT = Path("artifacts/models/oracle/e4b2d_fundamentals_features.parquet")
DATA = Path("artifacts/models/oracle/e2_feature_dataset.parquet")
OOS = Path("artifacts/models/oracle/oracle-wf-20260819034014/oos_predictions.parquet")
TICKET = Path("config/ticket_recherche.txt")
OUT = Path("artifacts/models/oracle/e4b2d_fundamentals_diag.md")

PERIODS = ["2022", "2023", "2024", "2025", "2026H1", "ALL"]
DIAG_FEATS = ["fund_pe_ratio", "fund_pb_ratio", "fund_ps_ratio",
              "fund_eps_growth_yoy", "fund_revenue_growth_yoy", "fund_net_margin",
              "fund_roe", "fund_debt_to_equity", "fund_dividend_yield",
              "fund_market_cap_log", "fund_beta"]


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
    sv["date"] = pd.to_datetime(sv["date"]).dt.normalize()
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

    full = extreme.merge(sv, on=["date", "symbol"], how="left")
    print("couverture: " + " ".join(f"{f}={full[f].notna().mean()*100:.0f}%" for f in DIAG_FEATS))

    md: list[str] = [
        "# E4-B2D — Diagnostic fundamentals conditionnel à Oracle Extreme (audit léger)",
        "",
        f"Population : pool Oracle Extreme restreint aux {len(ticket)} symboles de trade. "
        f"N={len(full):,} (UP {int((full['up']==1).sum()):,} / DOWN {int((full['up']==0).sum()):,}).",
        "Source : stock_fundamentals_daily (~18 valeurs trimestrielles/symbole). PIT strict (merge_asof backward).",
        "forward_pe exclu (colonne vide). AUC = Mann-Whitney U normalisé (UP=1).",
        "",
    ]
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

    md.append("")
    md.append("## Secondaire : BOTTOM ratés vs TOP capturés (ALL)")
    md.append("")
    sub = full[full["grp"].isin(["BOTTOM_rate", "TOP_capture"])]
    md.append(f"### ALL (N={len(sub):,}, BOTTOM_rate={int((sub['grp']=='BOTTOM_rate').sum()):,}, "
              f"TOP_capture={int((sub['grp']=='TOP_capture').sum()):,})")
    md.append("")
    md.append("| feature | AUC(BOTTOM=1) | mean BOTTOM | mean TOP | d | N |")
    md.append("|---|---|---|---|---|---|")
    for f in DIAG_FEATS:
        s2 = sub[["grp", f]].dropna()
        if len(s2) < 20:
            md.append(f"| {f} | - | - | - | - | {len(s2)} |")
            continue
        y = (s2["grp"] == "BOTTOM_rate").astype(int).to_numpy()
        s = s2[f].to_numpy()
        br = s2.loc[s2["grp"] == "BOTTOM_rate", f]
        tc = s2.loc[s2["grp"] == "TOP_capture", f]
        md.append(f"| {f} | {_auc(y, s):.3f} | {br.mean():.4f} | {tc.mean():.4f} | "
                  f"{_cohen_d(br, tc):+.3f} | {len(s2):,} |")

    OUT.write_text("\n".join(md), encoding="utf-8")
    print("\nrapport:", OUT)


if __name__ == "__main__":
    main()
