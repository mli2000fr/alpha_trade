"""E4-B2A — robustesse du signal short volume (pool Oracle Extreme 400).

1) Quintiles de short_volume_ratio_20d -> taux UP (UP/DOWN) par quintile et par annee.
   Si AUC~0.5 mais que les extrêmes portent un signal directionnel, on le voit ici.
2) Biais liquidité/taille : corrélation short_ratio avec short_share / total_volume.
3) BOTTOM rate vs TOP capture : le signal survit-il au contrôle par taille (total_volume) ?
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

FEAT = Path("artifacts/models/oracle/e4b2a_short_volume_features.parquet")
DATA = Path("artifacts/models/oracle/e2_feature_dataset.parquet")
OOS = Path("artifacts/models/oracle/oracle-wf-20260819034014/oos_predictions.parquet")
TICKET = Path("config/ticket_recherche.txt")
OUT = Path("artifacts/models/oracle/e4b2a_short_volume_robustesse.md")


def main() -> None:
    ticket = sorted({s.strip().upper() for s in TICKET.read_text(encoding="utf-8").split(",") if s.strip()})
    sv = pd.read_parquet(FEAT)
    sv["date"] = pd.to_datetime(sv["date"]).dt.normalize()
    sv["symbol"] = sv["symbol"].astype(str).str.upper()
    # volume total pour le contrôle de taille
    raw = pd.read_parquet("artifacts/finra_short_volume/short_sale_volume_400.parquet")
    raw["date"] = pd.to_datetime(raw["date"]).dt.normalize()
    raw["symbol"] = raw["symbol"].astype(str).str.upper()
    raw = raw.rename(columns={"total_volume": "finra_total_volume"})
    sv = sv.merge(raw[["date", "symbol", "finra_total_volume"]], on=["date", "symbol"], how="left")

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

    md: list[str] = ["# E4-B2A — Robustesse du signal short volume (Oracle Extreme 400)", ""]

    # 1) Quintiles ratio_20d -> taux UP
    md.append("## 1. Quintiles de short_volume_ratio_20d -> taux UP (par annee)")
    md.append("")
    md.append("| annee | Q1 (bas short) | Q2 | Q3 | Q4 | Q5 (haut short) | Q5-Q1 |")
    md.append("|---|---|---|---|---|---|---|")
    for per in ["2022", "2023", "2024", "2025", "2026H1", "ALL"]:
        sub = full if per == "ALL" else full[full["period"] == per]
        sub = sub[["up", "short_volume_ratio_20d"]].dropna()
        if len(sub) < 500:
            continue
        q = pd.qcut(sub["short_volume_ratio_20d"], 5, labels=False, duplicates="drop")
        rate = sub.assign(q=q).groupby("q")["up"].mean()
        cells = [f"{rate.get(i, float('nan'))*100:.1f}%" for i in range(int(rate.index.min()), int(rate.index.max()) + 1)]
        if len(cells) == 5:
            diff = (rate.iloc[-1] - rate.iloc[0]) * 100
            md.append(f"| {per} | " + " | ".join(cells) + f" | {diff:+.1f} |")
    md.append("")

    # 2) Corrélations (biais liquidité)
    md.append("## 2. Biais liquidite : correlations (ALL)")
    md.append("")
    s2 = full[["short_volume_ratio_20d", "short_share", "finra_total_volume", "up"]].dropna()
    md.append(f"| paire | corr (Spearman) |")
    md.append("|---|---|")
    import scipy.stats as st
    for a, b in [("short_volume_ratio_20d", "short_share"),
                 ("short_volume_ratio_20d", "finra_total_volume"),
                 ("short_share", "finra_total_volume"),
                 ("short_volume_ratio_20d", "up"),
                 ("short_share", "up")]:
        rho, _ = st.spearmanr(s2[a], s2[b])
        md.append(f"| {a} vs {b} | {rho:+.3f} |")
    md.append("")

    # 3) BOTTOM rate vs TOP capture : contrôler par quintile de taille
    md.append("## 3. BOTTOM rate vs TOP capture — ratio_20d par quintile de taille (ALL)")
    md.append("")
    g = full[full["grp"].isin(["BOTTOM_rate", "TOP_capture"])][
        ["grp", "short_volume_ratio_20d", "finra_total_volume"]].dropna().copy()
    g["size_q"] = pd.qcut(g["finra_total_volume"], 5, labels=False, duplicates="drop")
    md.append("| taille Q | AUC(BOTTOM=1) | mean BOTTOM | mean TOP | d | N |")
    md.append("|---|---|---|---|---|---|")
    from scipy.stats import mannwhitneyu
    for i in range(int(g["size_q"].min()), int(g["size_q"].max()) + 1):
        sg = g[g["size_q"] == i]
        if len(sg) < 50:
            continue
        y = (sg["grp"] == "BOTTOM_rate").to_numpy()
        s = sg["short_volume_ratio_20d"].to_numpy()
        u, _ = mannwhitneyu(s[y == 1], s[y == 0], alternative="two-sided")
        auc = u / (np.sum(y == 1) * np.sum(y == 0))
        a = sg.loc[sg["grp"] == "BOTTOM_rate", "short_volume_ratio_20d"].dropna().to_numpy()
        b = sg.loc[sg["grp"] == "TOP_capture", "short_volume_ratio_20d"].dropna().to_numpy()
        sp = np.sqrt(((len(a) - 1) * a.std(ddof=1) ** 2 + (len(b) - 1) * b.std(ddof=1) ** 2) / (len(a) + len(b) - 2))
        d = (a.mean() - b.mean()) / sp if sp > 1e-12 else float("nan")
        md.append(f"| {i} | {auc:.3f} | {a.mean():.4f} | {b.mean():.4f} | {d:+.3f} | {len(sg):,} |")
    md.append("")
    md.append("NOTE: si l'AUC reste >0.54 dans chaque tranche de taille, le signal")
    md.append("BOTTOM-vs-TOP n'est pas un pur artefact de taille.")

    OUT.write_text("\n".join(md), encoding="utf-8")
    print("rapport robustesse:", OUT)


if __name__ == "__main__":
    main()
