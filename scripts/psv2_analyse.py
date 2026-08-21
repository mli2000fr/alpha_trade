"""Campagne Per-Symbol Directional v2 — Analyse OOS 2025/2026 (F0/F1/F2/F3a/F3b).

Source : artifacts/per_symbol_v2/predictions_oos.parquet (généré par psv2_oos_predict.py).

Mesures par (run, arch, sous-période) :
  ic_mean    = moyenne par symbole du Spearman(score, future_return) — IC directionnel
  rank_ic    = moyenne par date du Spearman(score, future_return) cross-sectionnel
  dacc       = accord de signe poolé (sign(score) == sign(future_return))
  prec_long  = P(future>0 | score>0) ; prec_short = P(future<0 | score<0)
  f1_long / f1_short / f1_macro

Sous-périodes : 2025H1, 2025H2, 2026H1, ALL.
Deltas vs F0 (par arch × période). Rapports console + Markdown.
NB : LightGBM absent des runs F1/F2/F3a/F3b (--compare-lightgbm non passé) → analysé uniquement pour F0.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RUNS = ["f0", "f1", "f2", "f3a", "f3b"]
ARCHS = ["lstm_attention", "catboost", "lightgbm", "champion"]
PERIODS = ["2025H1", "2025H2", "2026H1", "ALL"]


def _period_of(d: pd.Timestamp) -> str:
    if d.year == 2025 and d.month <= 6:
        return "2025H1"
    if d.year == 2025:
        return "2025H2"
    if d.year == 2026:
        return "2026H1"
    return "ALL"


def _spearman(a, b):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    m = np.isfinite(a) & np.isfinite(b)
    a, b = a[m], b[m]
    if len(a) < 5 or np.all(a == a[0]) or np.all(b == b[0]):
        return float("nan")
    return float(pd.Series(a).corr(pd.Series(b), method="spearman"))


def _f1(y_true, y_pred_pos):
    tp = np.sum((y_pred_pos == 1) & (y_true == 1))
    fp = np.sum((y_pred_pos == 1) & (y_true != 1))
    fn = np.sum((y_pred_pos != 1) & (y_true == 1))
    p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    return 2 * p * r / (p + r) if (p + r) > 0 else 0.0


def metrics_for(df: pd.DataFrame) -> dict:
    if df.empty or "score" not in df.columns:
        return {"n": 0, "n_symbols": 0, "ic_mean": None, "ic_median": None,
                "rank_ic": None, "dacc": None, "prec_long": None, "prec_short": None,
                "f1_long": None, "f1_short": None, "f1_macro": None}
    # IC par symbole (Spearman)
    ics = [ic for _, g in df.groupby("symbol") if np.isfinite(ic := _spearman(g["score"], g["future_return"]))]
    # Rank IC cross-sectionnel (Spearman par date, moyenne des dates)
    rank_ics = []
    for _, g in df.groupby("date"):
        if g["symbol"].nunique() >= 5:
            r = _spearman(g["score"], g["future_return"])
            if np.isfinite(r):
                rank_ics.append(r)
    fr = df["future_return"].to_numpy(float)
    sc = df["score"].to_numpy(float)
    valid = np.isfinite(fr) & np.isfinite(sc)
    fr, sc = fr[valid], sc[valid]
    if len(fr) == 0:
        return {"n": 0, "n_symbols": 0, "ic_mean": None, "ic_median": None,
                "rank_ic": None, "dacc": None, "prec_long": None, "prec_short": None,
                "f1_long": None, "f1_short": None, "f1_macro": None}
    dacc = float(np.mean(np.sign(sc) == np.sign(fr)))
    long_mask = sc > 0
    short_mask = sc < 0
    prec_long = float(np.mean(fr[long_mask] > 0)) if long_mask.any() else None
    prec_short = float(np.mean(fr[short_mask] < 0)) if short_mask.any() else None
    y_long = (fr > 0).astype(int)
    y_short = (fr < 0).astype(int)
    pred_long = (sc > 0).astype(int)
    pred_short = (sc < 0).astype(int)
    f1_long = _f1(y_long, pred_long)
    f1_short = _f1(y_short, pred_short)
    return {
        "n": int(len(fr)),
        "n_symbols": int(df["symbol"].nunique()),
        "ic_mean": float(np.nanmean(ics)) if ics else None,
        "ic_median": float(np.nanmedian(ics)) if ics else None,
        "rank_ic": float(np.nanmean(rank_ics)) if rank_ics else None,
        "dacc": dacc,
        "prec_long": prec_long,
        "prec_short": prec_short,
        "f1_long": f1_long,
        "f1_short": f1_short,
        "f1_macro": (f1_long + f1_short) / 2.0,
    }


def main() -> None:
    df = pd.read_parquet(ROOT / "artifacts" / "per_symbol_v2" / "predictions_oos.parquet")
    df["date"] = pd.to_datetime(df["date"])
    df["period"] = df["date"].apply(_period_of)

    # archs réellement présents par run
    present = {r: sorted(df[df["run"] == r]["arch"].unique().tolist()) for r in RUNS}

    table: dict[tuple[str, str, str], dict] = {}
    for run in RUNS:
        for arch in ARCHS:
            sub = df[(df["run"] == run) & (df["arch"] == arch)]
            if sub.empty:
                continue
            for period in PERIODS:
                psub = sub[sub["period"] == period] if period != "ALL" else sub
                table[(run, arch, period)] = metrics_for(psub)

    out_dir = ROOT / "artifacts" / "per_symbol_v2"
    out_dir.mkdir(parents=True, exist_ok=True)

    md = [
        "# Per-Symbol Directional v2 — OOS 2025/2026 (39 symboles communs)",
        "",
        f"Architectures présentes par run : {json_dumps(present)}",
        "",
        "**NB** : LightGBM absent des runs F1/F2/F3a/F3b (flag `--compare-lightgbm` non passé) → la comparaison par architecture porte sur **LSTM + CatBoost** (+ champion).",
        "",
    ]
    print("=== Campagne OOS 2025/2026 — archs par run:", present)

    # Champion mix
    md.append("## Sélection champion par run")
    md.append("")
    md.append("| run | champion par symbole |")
    md.append("|---|---|")
    cmix = df[df["arch"] == "champion"].groupby("run")["symbol"].nunique()
    for run in RUNS:
        sub = df[(df["run"] == run) & (df["arch"] == "champion")]
        md.append(f"| {run} | {int(sub['symbol'].nunique())} symboles |")

    for arch in ["lstm_attention", "lightgbm", "catboost", "champion"]:
        md.append("")
        md.append(f"## {arch}")
        md.append("")
        md.append("| période | run | n | IC mean | Rank IC | dacc | prec L | prec S | F1 L | F1 S | F1 macro |")
        md.append("|---|---|---|---|---|---|---|---|---|---|---|")
        print(f"\n--- {arch} ---")
        print("période | run | n | IC mean | dacc | F1macro | dIC vs F0")
        for period in PERIODS:
            for run in RUNS:
                m = table.get((run, arch, period))
                if not m or m["n"] == 0:
                    continue
                f0 = table.get(("f0", arch, period))
                d_ic = (m["ic_mean"] - f0["ic_mean"]) if (f0 and f0["ic_mean"] is not None and m["ic_mean"] is not None) else None
                md.append("| %s | %s | %d | %s | %s | %s | %s | %s | %.3f | %.3f | %.3f |" % (
                    period, run, m["n"],
                    ("%.4f" % m["ic_mean"]) if m["ic_mean"] is not None else "-",
                    ("%.4f" % m["rank_ic"]) if m["rank_ic"] is not None else "-",
                    ("%.4f" % m["dacc"]) if m["dacc"] is not None else "-",
                    ("%.3f" % m["prec_long"]) if m["prec_long"] is not None else "-",
                    ("%.3f" % m["prec_short"]) if m["prec_short"] is not None else "-",
                    m["f1_long"], m["f1_short"], m["f1_macro"]))
                print("%s | %s | %d | %s | %s | %s | %s" % (
                    period, run, m["n"],
                    ("%.4f" % m["ic_mean"]) if m["ic_mean"] is not None else "-",
                    ("%.4f" % m["dacc"]) if m["dacc"] is not None else "-",
                    ("%.4f" % m["f1_macro"]) if m["f1_macro"] is not None else "-",
                    ("%+.4f" % d_ic) if d_ic is not None else "-"))

    # Résumé ΔIC vs F0 (toutes périodes, arch par arch)
    md.append("")
    md.append("## ΔIC vs F0 (IC mean run − IC mean F0), par arch × période")
    md.append("")
    md.append("| arch | période | F1 | F2 | F3a | F3b |")
    md.append("|---|---|---|---|---|---|")
    print("\n=== dIC vs F0 (LSTM / LightGBM / CatBoost / champion) ===")
    for arch in ["lstm_attention", "lightgbm", "catboost", "champion"]:
        for period in PERIODS:
            f0 = table.get(("f0", arch, period))
            cells = []
            for run in ["f1", "f2", "f3a", "f3b"]:
                m = table.get((run, arch, period))
                if f0 and m and m["ic_mean"] is not None and f0["ic_mean"] is not None:
                    cells.append("%+.4f" % (m["ic_mean"] - f0["ic_mean"]))
                else:
                    cells.append("-")
            md.append("| %s | %s | %s | %s | %s | %s |" % (arch, period, *cells))
            print(f"{arch} {period}: F1={cells[0]} F2={cells[1]} F3a={cells[2]} F3b={cells[3]}")

    report = ROOT / "artifacts" / "per_symbol_v2" / "rapport_campagne_oos.md"
    report.write_text("\n".join(md), encoding="utf-8")
    print("\nsaved:", report)


def json_dumps(obj) -> str:
    import json
    return json.dumps(obj)


if __name__ == "__main__":
    main()
