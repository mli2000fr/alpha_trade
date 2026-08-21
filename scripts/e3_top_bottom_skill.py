"""E3 — Décomposer Oracle Extreme en TOP-skill et BOTTOM-skill par période et par feature.

Question centrale : qu'est-ce qui différencie les BOTTOM10 capturés en 2022-24
des BOTTOM10 ratés en 2025-26H1 ?

Pour chaque période (2022/2023/2024/2025/2026H1), on reconstruit le TOP10 Oracle
(pred_top = top 10% de proba_extreme par date) et on croise avec la vérité :
  - TOP_capturé = pred_top & true_top10   ; TOP_raté = !pred_top & true_top10
  - BOTTOM_capturé = pred_top & true_bottom10 ; BOTTOM_raté = !pred_top & true_bottom10
Pour chaque groupe, on calcule la médiane des features O1 clés.

Hypothèse à tester : les BOTTOM ratés récents ressemblent davantage aux winners
(momentum positif, vol élevée) dans l'espace de features pré-trade.

Contrôle : violence des BOTTOM (abs return) par année — les crashes deviennent-ils
plus violents mais moins prévisibles ?
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

DATA = Path("artifacts/models/oracle/e2_feature_dataset.parquet")
OOS = Path("artifacts/models/oracle/oracle-wf-20260819034014/oos_predictions.parquet")
OUT = Path("artifacts/models/oracle/e3_top_bottom_skill.md")

PERIODS = ["2022", "2023", "2024", "2025", "2026H1"]
FEATURES = ["momentum_20", "relative_strength_20", "rolling_volatility_20",
            "market_volatility_20", "market_return_20", "range_position_20", "rsi_14",
            "volume_ratio_20", "drawdown_20", "distance_high_20", "distance_low_20",
            "global_rank_20", "atr_14_norm", "high_low_position_20", "return_20d"]


def main() -> None:
    ds = pd.read_parquet(DATA)
    oos = pd.read_parquet(OOS)
    ds["date"] = pd.to_datetime(ds["date"]).dt.normalize()
    oos["date"] = pd.to_datetime(oos["date"]).dt.normalize()
    m = ds.merge(oos[["date", "symbol", "proba_extreme"]], on=["date", "symbol"], how="inner")
    m["period"] = np.where(m["date"].dt.year < 2026, m["date"].dt.year.astype(str), "2026H1")
    m["period2"] = np.where(m["date"].dt.year < 2025, "2022-24", "2025-26H1")

    # vérité TOP10 / BOTTOM10 cross-sectionnelle
    m["true_top"] = (m["oracle_pct_rank"] >= 0.90).astype(int)
    m["true_bottom"] = (m["oracle_pct_rank"] <= 0.10).astype(int)
    m["true_extreme"] = m["oracle_extreme10"]

    # prédiction TOP10 Oracle (top 10% de proba_extreme par date)
    m["oracle_rank"] = m.groupby("date")["proba_extreme"].rank(pct=True)
    m["pred_top"] = (m["oracle_rank"] >= 0.90).astype(int)

    # groupes
    m["grp"] = np.select(
        [
            (m["pred_top"] == 1) & (m["true_top"] == 1),
            (m["pred_top"] == 0) & (m["true_top"] == 1),
            (m["pred_top"] == 1) & (m["true_bottom"] == 1),
            (m["pred_top"] == 0) & (m["true_bottom"] == 1),
        ],
        ["TOP_capture", "TOP_rate", "BOTTOM_capture", "BOTTOM_rate"],
        default="other",
    )

    md: list[str] = [
        "# E3 — TOP-skill vs BOTTOM-skill Oracle Extreme (par période et par feature)",
        "",
        "Groupes : TOP_capture = pred_top & vrai TOP10 ; TOP_rate = vrai TOP10 raté ; "
        "BOTTOM_capture = pred_top & vrai BOTTOM10 ; BOTTOM_rate = vrai BOTTOM10 raté.",
        "Features = médiane par groupe (features O1 réellement utilisées).",
        "",
    ]

    # ── 1. Comptages par période ──
    md.append("## 1. Comptages TOP/BOTTOM capturés vs ratés par période")
    md.append("")
    md.append("| période | TOP_cap | TOP_rate | BOTTOM_cap | BOTTOM_rate | rec_TOP% | rec_BOTTOM% |")
    md.append("|---|---|---|---|---|---|---|")
    print("=== 1. Comptages ===")
    for p in PERIODS:
        sub = m[m["period"] == p]
        tc = int((sub["grp"] == "TOP_capture").sum())
        tr = int((sub["grp"] == "TOP_rate").sum())
        bc = int((sub["grp"] == "BOTTOM_capture").sum())
        br = int((sub["grp"] == "BOTTOM_rate").sum())
        rec_t = tc / (tc + tr) * 100 if tc + tr else float("nan")
        rec_b = bc / (bc + br) * 100 if bc + br else float("nan")
        md.append(f"| {p} | {tc:,} | {tr:,} | {bc:,} | {br:,} | {rec_t:.1f} | {rec_b:.1f} |")
        print(f"  {p}: TOP cap={tc:,} raté={tr:,} (rec {rec_t:.1f}%) | BOT cap={bc:,} raté={br:,} (rec {rec_b:.1f}%)")

    # ── 2. Violence des BOTTOM (contrôle) ──
    md.append("")
    md.append("## 2. Contrôle : violence des BOTTOM10 par année (abs return)")
    md.append("")
    md.append("| période | BOTTOM med_abs% | BOTTOM mean% | TOP med_abs% | TOP mean% |")
    md.append("|---|---|---|---|")
    print("\n=== 2. Violence BOTTOM/TOP par année ===")
    for p in PERIODS:
        sub = m[m["period"] == p]
        b = sub[sub["true_bottom"] == 1]["future_return"]
        t = sub[sub["true_top"] == 1]["future_return"]
        md.append(f"| {p} | {b.abs().median()*100:.1f} | {b.mean()*100:.1f} | "
                  f"{t.abs().median()*100:.1f} | {t.mean()*100:.1f} |")
        print(f"  {p}: BOT med_abs={b.abs().median()*100:.1f}% mean={b.mean()*100:.1f}% | "
              f"TOP med_abs={t.abs().median()*100:.1f}% mean={t.mean()*100:.1f}%")

    # ── 3. Features par groupe (période 2-groupes) : CAPTURÉS vs RATÉS ──
    md.append("")
    md.append("## 3. Features (médianes) : BOTTOM capturés vs ratés, TOP capturés vs ratés")
    md.append("")
    md.append("| période | groupe | " + " | ".join(FEATURES) + " |")
    md.append("|" + "---|" * (len(FEATURES) + 2) + "|")
    print("\n=== 3. Features par groupe ===")
    for p in PERIODS:
        sub = m[m["period"] == p]
        for grp in ["TOP_capture", "TOP_rate", "BOTTOM_capture", "BOTTOM_rate"]:
            g = sub[sub["grp"] == grp]
            if len(g) < 10:
                continue
            vals = [f"{g[f].median():.4f}" if g[f].notna().any() else "-" for f in FEATURES]
            md.append(f"| {p} | {grp} | " + " | ".join(vals) + " |")
            print(f"  {p} {grp}: " + "  ".join(f"{f}={g[f].median():.4f}" for f in FEATURES[:6]))

    # ── 4. QUESTION CENTRALE : BOTTOM capturés 2022-24 vs BOTTOM ratés 2025-26H1 ──
    md.append("")
    md.append("## 4. QUESTION CENTRALE : BOTTOM capturés 2022-24 vs BOTTOM ratés 2025-26H1")
    md.append("")
    md.append("| feature | BOT_cap_2224 | BOT_rate_2526 | diff |")
    md.append("|---|---|---|---|")
    print("\n=== 4. QUESTION CENTRALE ===")
    bc_old = m[(m["period2"] == "2022-24") & (m["grp"] == "BOTTOM_capture")]
    br_new = m[(m["period2"] == "2025-26H1") & (m["grp"] == "BOTTOM_rate")]
    md.append(f"| N | {len(bc_old):,} | {len(br_new):,} | |")
    for f in FEATURES:
        a = bc_old[f].median() if bc_old[f].notna().any() else float("nan")
        b = br_new[f].median() if br_new[f].notna().any() else float("nan")
        md.append(f"| {f} | {a:.4f} | {b:.4f} | {b-a:+.4f} |")
        print(f"  {f:<28} BOT_cap_2224={a:+.4f}  BOT_rate_2526={b:+.4f}  diff={b-a:+.4f}")

    # ── 5. Focus : ressemblent-ils aux winners ? ──
    md.append("")
    md.append("## 5. Les BOTTOM ratés 2025-26 ressemblent-ils aux TOP ?")
    md.append("")
    md.append("| feature | TOP_cap_2526 | BOTTOM_rate_2526 | écart |")
    md.append("|---|---|---|---|")
    print("\n=== 5. BOTTOM ratés vs TOP capturés (2025-26H1) ===")
    tc_new = m[(m["period2"] == "2025-26H1") & (m["grp"] == "TOP_capture")]
    for f in FEATURES:
        a = tc_new[f].median() if tc_new[f].notna().any() else float("nan")
        b = br_new[f].median() if br_new[f].notna().any() else float("nan")
        md.append(f"| {f} | {a:.4f} | {b:.4f} | {a-b:+.4f} |")
        print(f"  {f:<28} TOP_cap={a:+.4f}  BOT_rate={b:+.4f}  écart={a-b:+.4f}")

    OUT.write_text("\n".join(md), encoding="utf-8")
    print("\nrapport:", OUT)


if __name__ == "__main__":
    main()
