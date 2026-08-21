"""S7-C — Métriques OOS 2025/2026 (IC, directional accuracy, F1) par run × arch × sous-période.

Sources : artifacts/s7_oos/predictions_oos.parquet (généré par s7_oos_predict.py).

Comparaisons (S7-C-A architecture contrôlée + S7-C-B champion) :
  IC      = moyenne par symbole du Spearman(score, future_return) sur la période
  dacc    = accord de signe poolé (sign(score) == sign(future_return))
  F1      = F1 directionnel 2 classes (long si score>0) poolé, + F1 short
Sous-périodes : 2025H1, 2025H2, 2026H1, ALL.
Deltas : DC-BL, DV-BL, DV-DC.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RUNS = ["bl", "dc", "dv"]
ARCHS = ["lstm_attention", "lightgbm", "catboost", "champion"]
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
    """Métriques sur un sous-dataframe (run, arch, période)."""
    if df.empty or "score" not in df.columns:
        return {"n": 0, "n_symbols": 0, "ic_mean": None, "ic_median": None,
                "dacc": None, "f1_long": None, "f1_short": None, "f1_macro": None}
    # IC par symbole
    ics = []
    for _, g in df.groupby("symbol"):
        ic = _spearman(g["score"], g["future_return"])
        if np.isfinite(ic):
            ics.append(ic)
    fr = df["future_return"].to_numpy(float)
    sc = df["score"].to_numpy(float)
    valid = np.isfinite(fr) & np.isfinite(sc)
    fr, sc = fr[valid], sc[valid]
    if len(fr) == 0:
        return {"n": 0, "n_symbols": 0, "ic_mean": None, "ic_median": None,
                "dacc": None, "f1_long": None, "f1_short": None, "f1_macro": None}
    dacc = float(np.mean(np.sign(sc) == np.sign(fr))) if len(fr) else None
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
        "dacc": dacc,
        "f1_long": f1_long,
        "f1_short": f1_short,
        "f1_macro": (f1_long + f1_short) / 2.0,
    }


def main() -> None:
    df = pd.read_parquet(ROOT / "artifacts" / "s7_oos" / "predictions_oos.parquet")
    df["date"] = pd.to_datetime(df["date"])
    df["period"] = df["date"].apply(_period_of)

    out_dir = ROOT / "artifacts" / "s7_oos"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Métriques par (run, arch, period)
    table = {}
    for run in RUNS:
        for arch in ARCHS:
            sub = df[(df["run"] == run) & (df["arch"] == arch)]
            for period in PERIODS:
                psub = sub[sub["period"] == period] if period != "ALL" else sub
                table[(run, arch, period)] = metrics_for(psub)

    # Deltas par (arch, period)
    deltas = {}
    for arch in ARCHS:
        for period in PERIODS:
            b = table[("bl", arch, period)]
            c = table[("dc", arch, period)]
            v = table[("dv", arch, period)]
            deltas[(arch, period)] = {
                "dc_minus_bl_ic": (c["ic_mean"] - b["ic_mean"]) if b["ic_mean"] is not None and c["ic_mean"] is not None else None,
                "dv_minus_bl_ic": (v["ic_mean"] - b["ic_mean"]) if b["ic_mean"] is not None and v["ic_mean"] is not None else None,
                "dv_minus_dc_ic": (v["ic_mean"] - c["ic_mean"]) if c["ic_mean"] is not None and v["ic_mean"] is not None else None,
                "dc_minus_bl_dacc": (c["dacc"] - b["dacc"]) if b["dacc"] is not None and c["dacc"] is not None else None,
                "dv_minus_bl_dacc": (v["dacc"] - b["dacc"]) if b["dacc"] is not None and v["dacc"] is not None else None,
                "dv_minus_dc_dacc": (v["dacc"] - c["dacc"]) if c["dacc"] is not None and v["dacc"] is not None else None,
            }

    # ---- Rapport console + MD ----
    md = ["# S7-C — OOS 2025/2026 (signal directionnel, 39 symboles)", ""]
    print("=== S7-C OOS 2025/2026 (39 symboles communs) ===")
    for arch in ARCHS:
        md.append(f"## {arch}")
        md.append("")
        md.append("| période | run | n | IC mean | dacc | F1 L | F1 S | F1 macro |")
        md.append("|---|---|---|---|---|---|---|---|")
        print(f"\n--- {arch} ---")
        for period in PERIODS:
            for run in RUNS:
                m = table[(run, arch, period)]
                md.append("| %s | %s | %d | %s | %s | %.3f | %.3f | %.3f |" % (
                    period, run, m["n"],
                    ("%.4f" % m["ic_mean"]) if m["ic_mean"] is not None else "-",
                    ("%.4f" % m["dacc"]) if m["dacc"] is not None else "-",
                    m["f1_long"], m["f1_short"], m["f1_macro"]))
            d = deltas[(arch, period)]
            md.append("| *delta* | DC-BL | | %s | %s | | | |" % (
                ("%+.4f" % d["dc_minus_bl_ic"]) if d["dc_minus_bl_ic"] is not None else "-",
                ("%+.4f" % d["dc_minus_bl_dacc"]) if d["dc_minus_bl_dacc"] is not None else "-"))
            md.append("| *delta* | DV-BL | | %s | %s | | | |" % (
                ("%+.4f" % d["dv_minus_bl_ic"]) if d["dv_minus_bl_ic"] is not None else "-",
                ("%+.4f" % d["dv_minus_bl_dacc"]) if d["dv_minus_bl_dacc"] is not None else "-"))
            md.append("")
            print(f"  {period}: " + " | ".join(
                "%s ic=%s dacc=%s" % (run,
                    ("%.4f" % table[(run, arch, period)]["ic_mean"]) if table[(run, arch, period)]["ic_mean"] is not None else "-",
                    ("%.4f" % table[(run, arch, period)]["dacc"]) if table[(run, arch, period)]["dacc"] is not None else "-")
                for run in RUNS))
            print("     DC-BL ic=%s dacc=%s | DV-BL ic=%s dacc=%s | DV-DC ic=%s dacc=%s" % (
                ("%+.4f" % d["dc_minus_bl_ic"]) if d["dc_minus_bl_ic"] is not None else "-",
                ("%+.4f" % d["dc_minus_bl_dacc"]) if d["dc_minus_bl_dacc"] is not None else "-",
                ("%+.4f" % d["dv_minus_bl_ic"]) if d["dv_minus_bl_ic"] is not None else "-",
                ("%+.4f" % d["dv_minus_bl_dacc"]) if d["dv_minus_bl_dacc"] is not None else "-",
                ("%+.4f" % d["dv_minus_dc_ic"]) if d["dv_minus_dc_ic"] is not None else "-",
                ("%+.4f" % d["dv_minus_dc_dacc"]) if d["dv_minus_dc_dacc"] is not None else "-"))

    report = {"table": {f"{r}|{a}|{p}": table[(r, a, p)] for r in RUNS for a in ARCHS for p in PERIODS},
              "deltas": {f"{a}|{p}": deltas[(a, p)] for a in ARCHS for p in PERIODS}}
    (out_dir / "rapport_s7c.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    (out_dir / "rapport_s7c.md").write_text("\n".join(md), encoding="utf-8")
    print("\n  ->", out_dir / "rapport_s7c.md")


if __name__ == "__main__":
    main()
