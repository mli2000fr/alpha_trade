"""Diagnostics Oracle TOP — exploitation des prédictions WF causales EXISTANTES (aucun entraînement).

Source : artifacts/models/oracle/oracle-wf-20260818021140/oos_predictions.parquet
(Oracle TOP P(top10) H20, WF causal, 2022-2026 ; colonnes proba_top, global_rank_20,
future_return, oracle_top10, date, symbol, fold_start).

4 diagnostics demandés (opérateur 2026-08-19) :
  1. Distribution des vrais déciles du TOP10 prédit (Oracle / B25 / aléatoire 10%)
  2. Distribution CUMULATIVE du TOP10 prédit : vrais TOP10/20/30/50 + BOTTOM20/10
     (met en évidence la contamination TOP->BOTTOM)
  3. Rendement futur réel (H20) par quantile de P_top (moyenne + médiane, monotonicité)
  4. Stabilité temporelle : les 3 tableaux sur 2022/2023/2024/2025/2026H1/ALL
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PARQUET = ROOT / "artifacts" / "models" / "oracle" / "oracle-wf-20260818021140" / "oos_predictions.parquet"
OUT = ROOT / "artifacts" / "oracle_top_diagnostics.md"


def _load() -> pd.DataFrame:
    df = pd.read_parquet(PARQUET)
    df["date"] = pd.to_datetime(df["date"])
    df["year"] = df["date"].dt.year
    df["period"] = np.where(df["year"] < 2026, df["year"].astype(str), "2026H1")
    # rangs par date
    df["oracle_rank"] = df.groupby("date")["proba_top"].rank(pct=True)
    df["b25_rank"] = df.groupby("date")["global_rank_20"].rank(pct=True)
    df["true_rank"] = df.groupby("date")["future_return"].rank(pct=True)
    df["true_decile"] = (df["true_rank"] * 10).clip(0, 9).astype(int) + 1
    return df


# ── Diag 1 — distribution des vrais déciles du TOP10 prédit ────────────────
def diag1(sub: pd.DataFrame, rank_col: str) -> pd.DataFrame:
    top = sub[sub[rank_col] >= 0.9]
    dist = top["true_decile"].value_counts().sort_index()
    out = pd.DataFrame({"decile": range(1, 11)})
    out["n"] = out["decile"].map(dist).fillna(0).astype(int)
    out["pct"] = out["n"] / len(top) if len(top) else 0.0
    return out


# ── Diag 2 — cumulative du TOP10 prédit (contamination) ────────────────────
def diag2(sub: pd.DataFrame, rank_col: str) -> dict:
    top = sub[sub[rank_col] >= 0.9]
    n = len(top)
    if n == 0:
        return {}
    tr = top["true_rank"]
    return {
        "n": n,
        "top10": float((tr >= 0.90).mean()),
        "top20": float((tr >= 0.80).mean()),
        "top30": float((tr >= 0.70).mean()),
        "top50": float((tr >= 0.50).mean()),
        "bot20": float((tr <= 0.20).mean()),
        "bot10": float((tr <= 0.10).mean()),
    }


# ── Diag 3 — forward return par quantile de P_top ──────────────────────────
def diag3(sub: pd.DataFrame) -> pd.DataFrame:
    s = sub.copy()
    s["ptop_decile"] = (s["oracle_rank"] * 10).clip(0, 9).astype(int) + 1
    g = s.groupby("ptop_decile")["future_return"].agg(["mean", "median", "count"])
    return g.reset_index()


def _fmt_pct(x) -> str:
    return "-" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x*100:.1f}%"


def _fmt(x, nd: int = 4) -> str:
    return "-" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:+.{nd}f}"


def main() -> None:
    df = _load()
    periods = ["2022", "2023", "2024", "2025", "2026H1", "ALL"]
    md: list[str] = [
        "# Oracle TOP — 4 diagnostics (prédictions WF causales existantes, aucun entraînement)",
        "",
        f"Source : `{PARQUET.name}` | {len(df):,} obs | H20 | 39 symboles-univers global.",
        "",
        "## 1. Distribution des vrais déciles du TOP10 prédit",
        "",
        "Lecture : sur 100 titres mis dans le TOP10 prédit, combien retombent réellement dans chaque vrai décile D1..D10 ? "
        "(aléatoire attendu = 10 % partout)",
        "",
    ]
    for period in periods:
        sub = df if period == "ALL" else df[df["period"] == period]
        md.append(f"### {period}")
        md.append("")
        md.append("| vrai décile | Oracle TOP10 | B25 TOP10 | aléatoire |")
        md.append("|---|---|---|---|")
        o = diag1(sub, "oracle_rank").set_index("decile")
        b = diag1(sub, "b25_rank").set_index("decile")
        for d in range(1, 11):
            md.append(f"| D{d} | {o.loc[d,'pct']*100:.1f}% | {b.loc[d,'pct']*100:.1f}% | 10.0% |")
        md.append("")

    # ── Diag 2 — cumulative + contamination ──
    md.append("## 2. Distribution CUMULATIVE du TOP10 prédit (contamination TOP->BOTTOM)")
    md.append("")
    md.append("| période | modèle | n | vrai TOP10 | vrai TOP20 | vrai TOP30 | vrai TOP50 | vrai BOTTOM20 | **vrai BOTTOM10** |")
    md.append("|---|---|---|---|---|---|---|---|---|")
    for period in periods:
        sub = df if period == "ALL" else df[df["period"] == period]
        o = diag2(sub, "oracle_rank")
        b = diag2(sub, "b25_rank")
        for name, d in (("Oracle", o), ("B25", b)):
            md.append(
                f"| {period} | {name} | {d.get('n','-')} | {_fmt_pct(d.get('top10'))} | "
                f"{_fmt_pct(d.get('top20'))} | {_fmt_pct(d.get('top30'))} | {_fmt_pct(d.get('top50'))} | "
                f"{_fmt_pct(d.get('bot20'))} | **{_fmt_pct(d.get('bot10'))}** |"
            )
    md.append("| — | aléatoire (attendu) | — | 10.0% | 20.0% | 30.0% | 50.0% | 20.0% | **10.0%** |")
    md.append("")
    md.append("> Interprétation : si `vrai BOTTOM10` est proche de `vrai TOP10`, Oracle est un "
              "**détecteur d'extrêmes sans discrimination de signe** (amplitude, pas direction).")
    md.append("")

    # ── Diag 3 — forward return par quantile de P_top ──
    md.append("## 3. Rendement futur réel (H20) par quantile de P_top")
    md.append("")
    md.append("| période | Q1 (bas) | Q2 | Q3 | Q4 | Q5 | Q6 | Q7 | Q8 | Q9 | Q10 (haut) | Spearman(P_top, ret) |")
    md.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for period in periods:
        sub = df if period == "ALL" else df[df["period"] == period]
        g = diag3(sub).set_index("ptop_decile")
        means = [g.loc[d, "mean"] for d in range(1, 11)]
        sp = sub[["oracle_rank", "future_return"]].corr(method="spearman").iloc[0, 1]
        md.append(f"| {period} | " + " | ".join(_fmt(m) for m in means) + f" | {sp:+.3f} |")
    md.append("")
    md.append("| période | médiane Q1 | médiane Q10 | écart Q10−Q1 (médianes) |")
    md.append("|---|---|---|---|")
    for period in periods:
        sub = df if period == "ALL" else df[df["period"] == period]
        g = diag3(sub).set_index("ptop_decile")
        md.append(f"| {period} | {_fmt(g.loc[1,'median'])} | {_fmt(g.loc[10,'median'])} | "
                  f"{_fmt(g.loc[10,'median']-g.loc[1,'median'])} |")
    md.append("")

    # ── Diag 4 — résumé stabilité (synthèse des diag 1/2 par période) ──
    md.append("## 4. Stabilité temporelle — résumé")
    md.append("")
    md.append("| période | Oracle TOP10 capture | Oracle BOTTOM10 (contamination) | Oracle TOP20 | Oracle TOP30 | B25 TOP10 capture |")
    md.append("|---|---|---|---|---|---|")
    for period in periods:
        sub = df if period == "ALL" else df[df["period"] == period]
        o = diag2(sub, "oracle_rank")
        b = diag2(sub, "b25_rank")
        md.append(
            f"| {period} | {_fmt_pct(o.get('top10'))} | **{_fmt_pct(o.get('bot10'))}** | "
            f"{_fmt_pct(o.get('top20'))} | {_fmt_pct(o.get('top30'))} | {_fmt_pct(b.get('top10'))} |"
        )
    md.append("")

    OUT.write_text("\n".join(md), encoding="utf-8")
    print("Rapport écrit:", OUT)
    # Print minimal ASCII résumé sur console
    print("\n--- RESUME (Diag2 ALL + contamination par an) ---")
    for period in periods:
        sub = df if period == "ALL" else df[df["period"] == period]
        o = diag2(sub, "oracle_rank")
        b = diag2(sub, "b25_rank")
        print(
            f"{period:6s} | Oracle TOP10={o.get('top10',0)*100:5.1f}% BOTTOM10={o.get('bot10',0)*100:5.1f}% "
            f"TOP20={o.get('top20',0)*100:5.1f}% TOP30={o.get('top30',0)*100:5.1f}% "
            f"| B25 TOP10={b.get('top10',0)*100:5.1f}% BOTTOM10={b.get('bot10',0)*100:5.1f}%"
        )


if __name__ == "__main__":
    main()
