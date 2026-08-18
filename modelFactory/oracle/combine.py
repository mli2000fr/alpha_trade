"""modelFactory/oracle/combine.py — Combinaison + calibration (S5).

Combine ``global_rank_20`` (B25) et ``P(top10)`` (Oracle TOP) en un score ajusté
(spec §15) et sélectionne la combinaison **uniquement sur les folds WF de
sélection**, avant de la **geler** pour l'OOS final (spec §16, discipline OOS).

Méthodes de combinaison :
- ``baseline`` : ``long_score = global_rank_20`` ;
- ``mult``     : ``global_rank_20 × P_top`` ;
- ``weighted`` : ``α·global_rank_20 + (1−α)·P_top`` (α cherché sur grid).

Calibration de ``P_top`` :
- ``identity`` (baseline, aucune) ;
- ``rank`` (percentile-rank intra-date, non paramétrique) ;
- ``isotonic`` (PAV — nécessite un set de fit, implémentée + testée).

Usage :
    python -m modelFactory.oracle.combine --oos-path artifacts/models/oracle/<run_id>/oos_predictions.parquet
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from modelFactory.oracle.train import decile_monotonicity, precision_recall_at_top_pct

LOGGER = logging.getLogger(__name__)

CALIBRATION_METHODS = ["identity", "rank"]
# Folds de sélection (choix de α/calibration) vs folds OOS final (gelés).
DEFAULT_SELECTION_FOLDS = ["2022-01-01", "2023-01-01", "2024-01-01"]
DEFAULT_FINAL_FOLDS = ["2025-01-01", "2026-01-01"]
DEFAULT_ALPHA_GRID = (0.0, 0.25, 0.5, 0.75, 1.0)


def combine_scores(
    global_rank: np.ndarray,
    p_top: np.ndarray,
    *,
    method: str = "weighted",
    alpha: float = 0.5,
) -> np.ndarray:
    """Combine le rang B25 et P(top10) en un score ajusté (spec §15)."""
    rank = np.asarray(global_rank, dtype=float)
    p = np.asarray(p_top, dtype=float)
    if method == "baseline":
        return rank
    if method == "p_top":
        return p
    if method == "mult":
        return rank * p
    if method == "weighted":
        return alpha * rank + (1.0 - alpha) * p
    raise ValueError(f"combine_scores: méthode inconnue {method}")


def isotonic_regression(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Régression isotonique non-décroissante (Pool Adjacent Violators).

    Retourne ``(x_sorted, fitted)`` où ``fitted`` est monotone non-décroissant.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if len(x) == 0:
        return x, y
    order = np.argsort(x, kind="mergesort")
    xs = x[order]
    ys = y[order]

    sums = ys.copy()
    counts = np.ones(len(ys), dtype=int)
    active = len(ys)
    i = 0
    while i < active - 1:
        if sums[i] / counts[i] <= sums[i + 1] / counts[i + 1]:
            i += 1
        else:
            sums[i] += sums[i + 1]
            counts[i] += counts[i + 1]
            sums = np.delete(sums, i + 1)
            counts = np.delete(counts, i + 1)
            active -= 1
            if i > 0:
                i -= 1

    fitted = np.empty(len(xs), dtype=float)
    pos = 0
    for b in range(active):
        c = int(counts[b])
        fitted[pos:pos + c] = sums[b] / counts[b]
        pos += c
    return xs, fitted


def calibrate_p_top(
    df: pd.DataFrame,
    *,
    method: str = "identity",
    fit_x: np.ndarray | None = None,
    fit_y: np.ndarray | None = None,
) -> pd.Series:
    """Calibration de ``proba_top`` (spec §16)."""
    proba = df["proba_top"].astype(float)
    if method == "identity":
        return proba
    if method == "rank":
        return df.groupby("date")["proba_top"].rank(pct=True).astype(float)
    if method == "isotonic":
        if fit_x is None or fit_y is None:
            raise ValueError("isotonic nécessite fit_x/fit_y (set de calibration)")
        x_sorted, fitted = isotonic_regression(np.asarray(fit_x, dtype=float), np.asarray(fit_y, dtype=float))
        return pd.Series(np.interp(proba.to_numpy(), x_sorted, fitted), index=df.index)
    raise ValueError(f"calibrate_p_top: méthode inconnue {method}")


def _evaluate_on_folds(
    oos_df: pd.DataFrame,
    score: pd.Series,
    folds: list[str],
) -> dict[str, Any]:
    sub = oos_df[oos_df["fold_start"].isin(folds)].copy()
    sub["_score"] = score.loc[sub.index]
    pr = precision_recall_at_top_pct(sub, "_score")
    mono, _ = decile_monotonicity(sub, "_score")
    return {"precision": pr["precision"], "recall": pr["recall"], "mono": mono, "n_dates": pr["n_dates"]}


def run_combination_search(
    oos_df: pd.DataFrame,
    *,
    selection_folds: list[str],
    final_folds: list[str],
    alpha_grid: tuple[float, ...] = DEFAULT_ALPHA_GRID,
) -> dict[str, Any]:
    """Cherche la meilleure combinaison sur les folds de sélection, la gèle,
    puis l'évalue sur les folds OOS final (jamais utilisés pour le réglage)."""
    baseline = {
        "sel": _evaluate_on_folds(oos_df, oos_df["global_rank_20"], selection_folds),
        "fin": _evaluate_on_folds(oos_df, oos_df["global_rank_20"], final_folds),
    }

    candidates: list[dict[str, Any]] = []
    for cal in CALIBRATION_METHODS:
        p_cal = calibrate_p_top(oos_df, method=cal)
        for method in ("mult", "weighted"):
            alphas = alpha_grid if method == "weighted" else (1.0,)
            for alpha in alphas:
                score = pd.Series(
                    combine_scores(oos_df["global_rank_20"].to_numpy(), p_cal.to_numpy(),
                                   method=method, alpha=alpha),
                    index=oos_df.index,
                )
                candidates.append({
                    "method": method,
                    "calibration": cal,
                    "alpha": alpha,
                    "sel": _evaluate_on_folds(oos_df, score, selection_folds),
                    "fin": _evaluate_on_folds(oos_df, score, final_folds),
                })

    best = max(candidates, key=lambda c: c["sel"]["precision"])
    return {
        "baseline": baseline,
        "best": {k: best[k] for k in ("method", "calibration", "alpha")},
        "best_sel": best["sel"],
        "best_final": best["fin"],
        "candidates": [
            {k: c[k] for k in ("method", "calibration", "alpha")} | {"sel_precision": c["sel"]["precision"], "fin_precision": c["fin"]["precision"]}
            for c in candidates
        ],
    }


def format_report(report: dict[str, Any]) -> str:
    """Rapport lisible."""
    lines = ["=== COMBINAISON + CALIBRATION (S5) ==="]
    b = report["baseline"]
    lines.append(
        f"baseline global_rank_20 : selection precision={b['sel']['precision']:.4f} "
        f"final OOS precision={b['fin']['precision']:.4f}"
    )
    best = report["best"]
    lines.append(
        f"best (gelé) : {best['method']} / {best['calibration']} / α={best['alpha']}"
    )
    lines.append(
        f"  selection precision={report['best_sel']['precision']:.4f} "
        f"→ final OOS precision={report['best_final']['precision']:.4f} "
        f"mono={report['best_final']['mono']:.4f}"
    )
    lines.append("candidates (top 10 par precision de sélection) :")
    for c in sorted(report["candidates"], key=lambda c: c["sel_precision"], reverse=True)[:10]:
        lines.append(
            f"  {c['method']:8s} {c['calibration']:9s} α={c['alpha']:4} "
            f"sel={c['sel_precision']:.4f} fin={c['fin_precision']:.4f}"
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Combinaison + calibration Oracle (S5).")
    parser.add_argument("--oos-path", required=True, help="Chemin du parquet OOS (sortie S4).")
    parser.add_argument("--selection-folds", nargs="*", default=DEFAULT_SELECTION_FOLDS)
    parser.add_argument("--final-folds", nargs="*", default=DEFAULT_FINAL_FOLDS)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    oos = pd.read_parquet(args.oos_path)
    if "fold_start" not in oos.columns:
        raise SystemExit("Le parquet OOS doit contenir la colonne 'fold_start' (sortie S4).")

    report = run_combination_search(
        oos,
        selection_folds=list(args.selection_folds),
        final_folds=list(args.final_folds),
    )
    print(format_report(report))


if __name__ == "__main__":
    main()
