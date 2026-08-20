"""E2-C — Feature drift des features O1 d'Oracle Extreme par année.

Compare chaque année (2023/2024/2025/2026H1) à la distribution d'entraînement
PRÉCÉDENTE (fenêtre glissante) :
- PSI (Population Stability Index) ;
- KS statistic (Kolmogorov-Smirnov sur les quantiles) ;
- évolution des quantiles (P10/P50/P90) ;
- missing-rate et couverture PIT.

Produit un TOP20 des features les plus driftées en 2025 et 2026H1.
ATTENTION : un drift de feature ne prouve PAS la cause de la baisse (cf. règle).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

DATA = Path("artifacts/models/oracle/e2_feature_dataset.parquet")
OUT = Path("artifacts/models/oracle/e2_feature_drift.md")

# Fenêtres : année test vs entraînement précédent (expansif)
WINDOWS = [
    ("2023", "2022"),
    ("2024", "2022-2023"),
    ("2025", "2022-2024"),
    ("2026H1", "2022-2025"),
]


def _psi(expected: pd.Series, actual: pd.Series, n_bins: int = 10) -> float:
    """PSI entre deux distributions (bins fixes sur l'union)."""
    e = expected.dropna()
    a = actual.dropna()
    if len(e) < 50 or len(a) < 50:
        return float("nan")
    lo, hi = np.quantile(pd.concat([e, a]), [0.01, 0.99])
    if not np.isfinite(lo) or not np.isfinite(hi) or lo >= hi:
        return float("nan")
    bins = np.linspace(lo, hi, n_bins + 1)
    hist_e, _ = np.histogram(e, bins=bins)
    hist_a, _ = np.histogram(a, bins=bins)
    p_e = hist_e / len(e)
    p_a = hist_a / len(a)
    # lissage pour éviter log(0)
    p_e = np.clip(p_e, 1e-6, None)
    p_a = np.clip(p_a, 1e-6, None)
    return float(np.sum((p_a - p_e) * np.log(p_a / p_e)))


def _ks_stat(expected: pd.Series, actual: pd.Series) -> float:
    """KS : max |ecdf_expected - ecdf_actual| (sur les valeurs, 2 échantillons)."""
    e = expected.dropna().to_numpy()
    a = actual.dropna().to_numpy()
    if len(e) < 50 or len(a) < 50:
        return float("nan")
    # ecdf empiriques sur un maillage commun de quantiles [1..99]
    qs = np.arange(1, 100) / 100.0
    qe = np.quantile(e, qs)
    qa = np.quantile(a, qs)
    # KS approx = max |F_e - F_a| évalué aux points de mesure ; on utilise
    # l'écart maximal entre les deux ecdf via les quantiles inversés :
    # max |quantile_e(p) - quantile_a(p)| / échelle médiane
    scale = max(float(np.median(e)), 1e-9)
    return float(np.max(np.abs(qe - qa) / scale))


def _quantile_shift(expected: pd.Series, actual: pd.Series, q: float = 0.50) -> float:
    e = expected.dropna()
    a = actual.dropna()
    if e.empty or a.empty:
        return float("nan")
    ve = np.quantile(e, q)
    va = np.quantile(a, q)
    scale = max(abs(ve), 1e-9)
    return float((va - ve) / scale)


def _year(d: pd.Series) -> pd.Series:
    y = d.dt.year
    return np.where(y < 2026, y.astype(str), "2026H1")


def main() -> None:
    df = pd.read_parquet(DATA)
    df["period"] = _year(df["date"])
    # features O1 = toutes les colonnes numériques sauf meta/labels/guard
    meta = {"date", "symbol", "oracle_available_date", TARGET_COL := "oracle_extreme10",
            "future_return", "oracle_decile", "oracle_pct_rank", "period"}
    feats = [c for c in df.columns if c not in meta and df[c].dtype.kind in "fi"]
    print(f"dataset: {len(df):,} | features O1: {len(feats)}")

    report: dict[str, pd.DataFrame] = {}
    for test_label, train_label in WINDOWS:
        test = df[df["period"] == test_label]
        # fenêtre d'entraînement précédente : cumul des années < test_label
        if train_label == "2022":
            train = df[df["period"] == "2022"]
        elif train_label == "2022-2023":
            train = df[df["period"].isin(["2022", "2023"])]
        elif train_label == "2022-2024":
            train = df[df["period"].isin(["2022", "2023", "2024"])]
        else:
            train = df[df["period"].isin(["2022", "2023", "2024", "2025"])]

        rows = []
        for f in feats:
            e = train[f]
            a = test[f]
            rows.append({
                "feature": f,
                "test_period": test_label,
                "n_train": int(train["date"].nunique()),
                "n_test": int(test["date"].nunique()),
                "missing_train": float(e.isna().mean()),
                "missing_test": float(a.isna().mean()),
                "psi": _psi(e, a),
                "ks": _ks_stat(e, a),
                "q10_shift": _quantile_shift(e, a, 0.10),
                "q50_shift": _quantile_shift(e, a, 0.50),
                "q90_shift": _quantile_shift(e, a, 0.90),
            })
        report[test_label] = pd.DataFrame(rows).sort_values("psi", ascending=False)

    # TOP20 2025 et 2026H1
    md = ["# E2-C — Feature drift Oracle Extreme (O1)", "",
          "Comparaison année test vs entraînement précédent (PSI / KS / quantiles / missing).",
          "⚠️ Un drift ne prouve PAS la cause (règle : ne pas conclure au seul motif d'un drift).", ""]
    for test_label in ["2025", "2026H1"]:
        r = report[test_label]
        top = r.head(20)
        md.append(f"## TOP20 drift {test_label}")
        md.append("")
        md.append("| # | feature | PSI | KS | q50 shift | missing_test |")
        md.append("|---|---|---|---|---|---|")
        for i, (_, row) in enumerate(top.iterrows(), 1):
            md.append(f"| {i} | {row['feature']} | {row['psi']:.4f} | {row['ks']:.4f} | "
                      f"{row['q50_shift']:+.3f} | {row['missing_test']*100:.1f}% |")
        md.append("")

    # résumé : nb de features avec PSI > seuils par période
    md.append("## Distribution des PSI")
    md.append("")
    md.append("| période | n_feats | PSI>0.10 | PSI>0.25 | PSI>0.50 |")
    md.append("|---|---|---|---|---|")
    for test_label in ["2023", "2024", "2025", "2026H1"]:
        r = report[test_label]
        md.append(f"| {test_label} | {len(r)} | {int((r['psi']>0.10).sum())} | "
                  f"{int((r['psi']>0.25).sum())} | {int((r['psi']>0.50).sum())} |")

    OUT.write_text("\n".join(md), encoding="utf-8")
    print("rapport:", OUT)
    for test_label in ["2025", "2026H1"]:
        r = report[test_label]
        print(f"\n=== TOP10 drift {test_label} ===")
        for _, row in r.head(10).iterrows():
            print(f"  {row['feature']:<34} PSI={row['psi']:6.3f} KS={row['ks']:6.3f} "
                  f"q50={row['q50_shift']:+6.3f} miss={row['missing_test']*100:5.1f}%")


if __name__ == "__main__":
    main()
