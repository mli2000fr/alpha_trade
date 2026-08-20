"""E2-A + E2-B — Dégradation temporelle Oracle Extreme (partie 1 : ML + target).

Utilise UNIQUEMENT le parquet OOS gelé oracle-wf-20260819034014 (aucun retraining).

E2-A — ML drift par période (année + trimestre) :
  AUC, AP (PR-AUC), P@5/P@10/P@20, recall@10, Brier, distribution proba_extreme
  (P10/P25/P50/P75/P90/P95/P99) + lift vs prévalence.
  Le découpage trimestriel détecte une éventuelle DATE DE RUPTURE (vs dérive lisse).

E2-B — Target change : la prévalence reste ~20%, mais la NATURE économique des
  extrêmes change-t-elle ? abs(future_return) des vrais TOP10 / BOTTOM10 / union,
  écart D9/D10 vs D1/D2 par période.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from modelFactory.oracle.train import roc_auc

RUN = Path("artifacts/models/oracle/oracle-wf-20260819034014/oos_predictions.parquet")
K_VALUES = [0.05, 0.10, 0.15, 0.20]
YEARS = ["2022", "2023", "2024", "2025", "2026H1"]
QUARTERS = ["2024Q1", "2024Q2", "2024Q3", "2024Q4",
            "2025Q1", "2025Q2", "2025Q3", "2025Q4",
            "2026Q1", "2026Q2"]


def _avg_precision(df: pd.DataFrame, score_col: str, target_col: str, k: float) -> float:
    precs = []
    for _, g in df.groupby("date"):
        g = g.dropna(subset=[score_col, target_col])
        if len(g) < 20:
            continue
        n_top = max(1, int(np.ceil(len(g) * k)))
        top = g.nlargest(n_top, score_col)
        precs.append(float(top[target_col].mean()))
    return float(np.mean(precs)) if precs else float("nan")


def _avg_recall(df: pd.DataFrame, score_col: str, target_col: str, k: float) -> float:
    recs = []
    for _, g in df.groupby("date"):
        g = g.dropna(subset=[score_col, target_col])
        if len(g) < 20:
            continue
        n_top = max(1, int(np.ceil(len(g) * k)))
        top = g.nlargest(n_top, score_col)
        n_ext = int(g[target_col].sum())
        recs.append(float(top[target_col].sum() / n_ext) if n_ext > 0 else np.nan)
    return float(np.nanmean(recs)) if recs else float("nan")


def _average_precision_ap(y: np.ndarray, s: np.ndarray) -> float | None:
    """PR-AUC (Average Precision) — baseline : prévalence."""
    y = np.asarray(y, dtype=float)
    s = np.asarray(s, dtype=float)
    m = np.isfinite(s) & np.isfinite(y)
    y, s = y[m], s[m]
    if len(y) < 30 or len(np.unique(y)) < 2:
        return None
    order = np.argsort(-s)
    y = y[order]
    tp = np.cumsum(y)
    fp = np.cumsum(1 - y)
    prec = tp / (tp + fp + 1e-9)
    rec = tp / tp[-1] if tp[-1] > 0 else np.zeros_like(tp)
    # AP = somme sur les changements de recall
    ap = float(np.sum(prec * np.diff(np.concatenate([[0.0], rec]))))
    return ap


def _brier(y: np.ndarray, s: np.ndarray) -> float:
    m = np.isfinite(s) & np.isfinite(y)
    return float(np.mean((s[m] - y[m]) ** 2))


def _proba_quantiles(s: pd.Series) -> dict[str, float]:
    s = s.dropna()
    if s.empty:
        return {p: float("nan") for p in [10, 25, 50, 75, 90, 95, 99]}
    q = s.quantile([0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99])
    return {int(k * 100): float(v) for k, v in q.items()}


def _period_col(d: pd.Series) -> pd.Series:
    y = d.dt.year
    q = d.dt.quarter
    return np.where(y < 2026, y.astype(str), "2026H1")


def _quarter_col(d: pd.Series) -> pd.Series:
    return d.dt.year.astype(str) + "Q" + d.dt.quarter.astype(str)


def ml_row(df: pd.DataFrame) -> dict:
    y = df["oracle_extreme10"].to_numpy()
    s = df["proba_extreme"].to_numpy()
    prev = df["oracle_extreme10"].mean()
    row = {
        "N": int(len(df)),
        "prevalence": prev,
        "AUC": roc_auc(y, s),
        "AP": _average_precision_ap(y, s),
        "Brier": _brier(y, s),
    }
    for k in K_VALUES:
        row[f"P@{int(k*100)}"] = _avg_precision(df, "proba_extreme", "oracle_extreme10", k)
        row[f"lift@{int(k*100)}"] = row[f"P@{int(k*100)}"] / prev if prev else float("nan")
    row["recall@10"] = _avg_recall(df, "proba_extreme", "oracle_extreme10", 0.10)
    row["B25_P@10"] = _avg_precision(df, "global_rank_20", "oracle_extreme10", 0.10)
    q = _proba_quantiles(df["proba_extreme"])
    for k, v in q.items():
        row[f"proba_p{k}"] = v
    return row


def target_row(df: pd.DataFrame) -> dict:
    ext = df[df["oracle_extreme10"] == 1]
    top = df[df["oracle_pct_rank"] >= 0.90] if "oracle_pct_rank" in df.columns else pd.DataFrame()
    bot = df[df["oracle_pct_rank"] <= 0.10] if "oracle_pct_rank" in df.columns else pd.DataFrame()
    row = {
        "N": int(len(df)),
        "prev": df["oracle_extreme10"].mean(),
        "ext_med_abs": ext["future_return"].abs().median() if not ext.empty else float("nan"),
        "ext_mean_abs": ext["future_return"].abs().mean() if not ext.empty else float("nan"),
    }
    if not top.empty and not bot.empty:
        row["top10_med_abs"] = top["future_return"].abs().median()
        row["bot10_med_abs"] = bot["future_return"].abs().median()
        row["top10_mean"] = top["future_return"].mean()
        row["bot10_mean"] = bot["future_return"].mean()
        # écart D9/D10 et D1/D2 via decile
        if "oracle_decile" in df.columns:
            dec = df.dropna(subset=["oracle_decile"])
            dec = dec[dec["oracle_decile"].isin([1, 2, 9, 10])]
            g = dec.groupby("oracle_decile")["future_return"].mean()
            row["D10_mean"] = g.get(10, float("nan"))
            row["D9_mean"] = g.get(9, float("nan"))
            row["D2_mean"] = g.get(2, float("nan"))
            row["D1_mean"] = g.get(1, float("nan"))
            row["gap_D9_D10"] = row["D10_mean"] - row["D9_mean"]
            row["gap_D1_D2"] = row["D1_mean"] - row["D2_mean"]
    return row


def main() -> None:
    df = pd.read_parquet(RUN)
    df["period"] = _period_col(df["date"])
    df["quarter"] = _quarter_col(df["date"])
    df["oracle_pct_rank"] = df.groupby("date")["future_return"].rank(pct=True)
    df["oracle_decile"] = np.ceil(df["oracle_pct_rank"] * 10).clip(1, 10).astype(int)

    # ═════════ E2-A : ML drift par année ═════════
    print("=" * 100)
    print("E2-A — ML drift par période (année)")
    print("=" * 100)
    rows = {p: ml_row(df[df["period"] == p]) for p in YEARS}
    rows["ALL"] = ml_row(df)
    hdr = (f"{'per':<6}{'N':>8}{'prev%':>7}{'AUC':>6}{'AP':>6}{'P@5':>6}{'P@10':>6}{'P@20':>6}"
           f"{'rec@10':>7}{'Brier':>7}{'B25@10':>7}{'p50':>6}{'p90':>6}{'p95':>6}{'p99':>6}")
    print(hdr)
    for p in YEARS + ["ALL"]:
        r = rows[p]
        print(f"{p:<6}{r['N']:>8,}{r['prevalence']*100:>7.1f}{r['AUC']:>6.3f}"
              f"{r['AP']:>6.3f}{r['P@5']*100:>6.1f}{r['P@10']*100:>6.1f}{r['P@20']*100:>6.1f}"
              f"{r['recall@10']*100:>7.1f}{r['Brier']:>7.4f}{r['B25_P@10']*100:>7.1f}"
              f"{r['proba_p50']:>6.3f}{r['proba_p90']:>6.3f}{r['proba_p95']:>6.3f}{r['proba_p99']:>6.3f}")

    # ═════════ E2-A : par trimestre (détection de rupture) ═════════
    print("\n" + "=" * 100)
    print("E2-A — AUC / P@10 / N par trimestre (détection de rupture)")
    print("=" * 100)
    print(f"{'quarter':<8}{'N':>8}{'prev%':>7}{'AUC':>7}{'P@10':>7}{'rec@10':>7}{'Brier':>7}{'B25@10':>7}")
    for q in QUARTERS:
        sub = df[df["quarter"] == q]
        if sub.empty:
            continue
        r = ml_row(sub)
        print(f"{q:<8}{r['N']:>8,}{r['prevalence']*100:>7.1f}{r['AUC']:>7.3f}"
              f"{r['P@10']*100:>7.1f}{r['recall@10']*100:>7.1f}{r['Brier']:>7.4f}{r['B25_P@10']*100:>7.1f}")

    # ═════════ E2-B : target change ═════════
    print("\n" + "=" * 100)
    print("E2-B — Nature économique des extrêmes par période")
    print("=" * 100)
    trows = {p: target_row(df[df["period"] == p]) for p in YEARS}
    trows["ALL"] = target_row(df)
    thdr = (f"{'per':<6}{'prev%':>7}{'ext_med_abs':>12}{'ext_mean_abs':>12}{'top_med_abs':>12}"
            f"{'bot_med_abs':>12}{'D10':>8}{'D9':>8}{'gap910':>8}{'D2':>8}{'D1':>8}{'gap12':>8}")
    print(thdr)
    for p in YEARS + ["ALL"]:
        r = trows[p]
        print(f"{p:<6}{r['prev']*100:>7.1f}{r['ext_med_abs']*100:>12.1f}{r['ext_mean_abs']*100:>12.1f}"
              f"{r['top10_med_abs']*100:>12.1f}{r['bot10_med_abs']*100:>12.1f}"
              f"{r.get('D10_mean', float('nan'))*100:>8.1f}{r.get('D9_mean', float('nan'))*100:>8.1f}"
              f"{r.get('gap_D9_D10', float('nan'))*100:>8.1f}{r.get('D2_mean', float('nan'))*100:>8.1f}"
              f"{r.get('D1_mean', float('nan'))*100:>8.1f}{r.get('gap_D1_D2', float('nan'))*100:>8.1f}")

    # ── Rapport Markdown détaillé (UTF-8) ──
    md: list[str] = [
        "# E2-A/B — Dégradation temporelle Oracle Extreme : tableaux détaillés",
        "",
        "Run gelé : `oracle-wf-20260819034014` (326 273 lignes OOS, 2022-01-03 -> 2026-05-29).",
        "",
        "## E2-A — ML drift par période",
        "",
        "| période | N | prev% | AUC | AP | P@5 | P@10 | P@15 | P@20 | recall@10 | Brier | B25_P@10 | p50 | p75 | p90 | p95 | p99 |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    qcols = ["N", "prevalence", "AUC", "AP", "P@5", "P@10", "P@15", "P@20",
             "recall@10", "Brier", "B25_P@10", "proba_p50", "proba_p75", "proba_p90", "proba_p95", "proba_p99"]
    for p in YEARS + ["ALL"]:
        r = rows[p]
        cells = [
            p,
            f"{r['N']:,}",
            f"{r['prevalence']*100:.1f}",
            f"{r['AUC']:.3f}",
            f"{r['AP']:.3f}",
            f"{r['P@5']*100:.1f}",
            f"{r['P@10']*100:.1f}",
            f"{r['P@15']*100:.1f}",
            f"{r['P@20']*100:.1f}",
            f"{r['recall@10']*100:.1f}",
            f"{r['Brier']:.4f}",
            f"{r['B25_P@10']*100:.1f}",
            f"{r['proba_p50']:.3f}",
            f"{r['proba_p75']:.3f}",
            f"{r['proba_p90']:.3f}",
            f"{r['proba_p95']:.3f}",
            f"{r['proba_p99']:.3f}",
        ]
        md.append("| " + " | ".join(cells) + " |")

    md.append("")
    md.append("## E2-A — Par trimestre (détection de rupture)")
    md.append("")
    md.append("| trimestre | N | prev% | AUC | P@10 | recall@10 | Brier | B25_P@10 |")
    md.append("|---|---|---|---|---|---|---|---|")
    for q in QUARTERS:
        sub = df[df["quarter"] == q]
        if sub.empty:
            continue
        r = ml_row(sub)
        md.append(f"| {q} | {r['N']:,} | {r['prevalence']*100:.1f} | {r['AUC']:.3f} | "
                  f"{r['P@10']*100:.1f} | {r['recall@10']*100:.1f} | {r['Brier']:.4f} | "
                  f"{r['B25_P@10']*100:.1f} |")

    md.append("")
    md.append("## E2-A — Distribution de proba_extreme par période")
    md.append("")
    md.append("| période | p10 | p25 | p50 | p75 | p90 | p95 | p99 |")
    md.append("|---|---|---|---|---|---|---|---|")
    for p in YEARS + ["ALL"]:
        r = rows[p]
        md.append(f"| {p} | {r['proba_p10']:.3f} | {r['proba_p25']:.3f} | {r['proba_p50']:.3f} | "
                  f"{r['proba_p75']:.3f} | {r['proba_p90']:.3f} | {r['proba_p95']:.3f} | "
                  f"{r['proba_p99']:.3f} |")

    md.append("")
    md.append("## E2-B — Nature économique des extrêmes par période")
    md.append("")
    md.append("| période | prev% | ext_med_abs% | ext_mean_abs% | top10_med_abs% | bot10_med_abs% | D10% | D9% | gap_D9_D10 | D2% | D1% | gap_D1_D2 |")
    md.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for p in YEARS + ["ALL"]:
        r = trows[p]
        md.append(f"| {p} | {r['prev']*100:.1f} | {r['ext_med_abs']*100:.1f} | {r['ext_mean_abs']*100:.1f} | "
                  f"{r['top10_med_abs']*100:.1f} | {r['bot10_med_abs']*100:.1f} | "
                  f"{r.get('D10_mean', float('nan'))*100:.1f} | {r.get('D9_mean', float('nan'))*100:.1f} | "
                  f"{r.get('gap_D9_D10', float('nan'))*100:.1f} | {r.get('D2_mean', float('nan'))*100:.1f} | "
                  f"{r.get('D1_mean', float('nan'))*100:.1f} | {r.get('gap_D1_D2', float('nan'))*100:.1f} |")

    from pathlib import Path
    out_path = Path("artifacts/models/oracle/e2_ml_target_detailed.md")
    out_path.write_text("\n".join(md), encoding="utf-8")
    print("\nrapport détaillé:", out_path)


if __name__ == "__main__":
    main()
