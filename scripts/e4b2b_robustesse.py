"""E4-B2B — robustesse du signal short interest (pool Oracle Extreme 400).

1) Quintiles de short_interest_dtc et ratio_float -> taux UP par quintile/annee.
2) Biais taille : correlation SI_raw / ratio_float / dtc avec current_short_position.
3) BOTTOM rate vs TOP capture : le signal dtc survit-il au controle par taille ?
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import scipy.stats as st

FEAT = Path("artifacts/models/oracle/e4b2b_short_interest_features.parquet")
DATA = Path("artifacts/models/oracle/e2_feature_dataset.parquet")
OOS = Path("artifacts/models/oracle/oracle-wf-20260819034014/oos_predictions.parquet")
TICKET = Path("config/ticket_recherche.txt")
OUT = Path("artifacts/models/oracle/e4b2b_short_interest_robustesse.md")


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
    full = extreme.merge(sv, on=["date", "symbol"], how="left")

    md: list[str] = ["# E4-B2B — Robustesse du signal short interest (Oracle Extreme 400)", ""]

    # 1) quintiles
    md.append("## 1. Quintiles -> taux UP (par annee)")
    md.append("")
    md.append("| annee | Q1 | Q2 | Q3 | Q4 | Q5 | Q5-Q1 |")
    md.append("|---|---|---|---|---|---|---|")
    for feat in ["short_interest_dtc", "short_interest_ratio_float"]:
        md.append(f"### {feat}")
        md.append("")
        md.append("| annee | Q1 | Q2 | Q3 | Q4 | Q5 | Q5-Q1 |")
        md.append("|---|---|---|---|---|---|---|")
        for per in ["2022", "2023", "2024", "2025", "2026H1", "ALL"]:
            sub = full if per == "ALL" else full[full["period"] == per]
            sub = sub[["up", feat]].dropna()
            if len(sub) < 500:
                continue
            try:
                q = pd.qcut(sub[feat], 5, labels=False, duplicates="drop")
            except Exception:
                continue
            rate = sub.assign(q=q).groupby("q")["up"].mean()
            cells = [f"{rate.get(i, float('nan'))*100:.1f}%" for i in range(int(rate.index.min()), int(rate.index.max()) + 1)]
            if len(cells) == 5:
                diff = (rate.iloc[-1] - rate.iloc[0]) * 100
                md.append(f"| {per} | " + " | ".join(cells) + f" | {diff:+.1f} |")
        md.append("")

    # 2) correlations (biais taille)
    md.append("## 2. Biais taille : correlations (Spearman, ALL)")
    md.append("")
    s2 = full[["short_interest_raw", "short_interest_dtc", "short_interest_ratio_float",
               "short_interest_ratio_advol", "up"]].dropna()
    md.append("| paire | corr |")
    md.append("|---|---|")
    for a, b in [("short_interest_raw", "short_interest_dtc"),
                 ("short_interest_raw", "short_interest_ratio_float"),
                 ("short_interest_dtc", "short_interest_ratio_float"),
                 ("short_interest_raw", "up"),
                 ("short_interest_dtc", "up"),
                 ("short_interest_ratio_float", "up")]:
        rho, _ = st.spearmanr(s2[a], s2[b])
        md.append(f"| {a} vs {b} | {rho:+.3f} |")
    md.append("")

    # 3) BOTTOM/TOP dtc par quintile de SI_raw (taille)
    md.append("## 3. BOTTOM rate vs TOP capture — dtc par quintile de SI_raw (taille, ALL)")
    md.append("")
    g = full[full["grp"].isin(["BOTTOM_rate", "TOP_capture"])][
        ["grp", "short_interest_dtc", "short_interest_raw"]].dropna().copy()
    g["size_q"] = pd.qcut(g["short_interest_raw"], 5, labels=False, duplicates="drop")
    from scipy.stats import mannwhitneyu
    md.append("| taille Q | AUC(BOTTOM=1) | mean BOTTOM | mean TOP | d | N |")
    md.append("|---|---|---|---|---|---|")
    for i in range(int(g["size_q"].min()), int(g["size_q"].max()) + 1):
        sg = g[g["size_q"] == i]
        if len(sg) < 50:
            continue
        y = (sg["grp"] == "BOTTOM_rate").to_numpy()
        s = sg["short_interest_dtc"].to_numpy()
        u, _ = mannwhitneyu(s[y == 1], s[y == 0], alternative="two-sided")
        auc = u / (np.sum(y == 1) * np.sum(y == 0))
        a = sg.loc[sg["grp"] == "BOTTOM_rate", "short_interest_dtc"].to_numpy()
        b = sg.loc[sg["grp"] == "TOP_capture", "short_interest_dtc"].to_numpy()
        sp = np.sqrt(((len(a) - 1) * a.std(ddof=1) ** 2 + (len(b) - 1) * b.std(ddof=1) ** 2) / (len(a) + len(b) - 2))
        d = (a.mean() - b.mean()) / sp if sp > 1e-12 else float("nan")
        md.append(f"| {i} | {auc:.3f} | {a.mean():.3f} | {b.mean():.3f} | {d:+.3f} | {len(sg):,} |")
    md.append("")

    OUT.write_text("\n".join(md), encoding="utf-8")
    print("rapport robustesse:", OUT)


if __name__ == "__main__":
    main()
