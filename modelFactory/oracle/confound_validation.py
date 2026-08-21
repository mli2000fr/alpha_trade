"""modelFactory/oracle/confound_validation.py — S6.6-C : validation confound-free de PE.

Le signal `pe_ratio` (AUC 0.70 sur cat10) doit survivre à un test sur le MÊME
sous-ensemble (candidats B25 TOP avec pe_ratio disponible), contre une **baseline
aléatoire**. On mesure le ratio :

    ratio = catastrophes évitées / vrais TOP sacrifiés

- rejet aléatoire : ratio attendu ≈ 1.0 (mécanique) ;
- rejet par PE (les plus chers) : ratio > 1 ⇔ le PE apporte réellement quelque chose.

Usage :
    python -m modelFactory.oracle.confound_validation --batch-id model-factory-20260811223551-ef2cd0
"""
from __future__ import annotations

import argparse
import json
import logging
from typing import Any

import numpy as np
import pandas as pd

from database.connection import get_sqlalchemy_engine
from modelFactory.oracle.catastrophic_detector import _build_dataset, _rejection_tradeoff
from modelFactory.oracle.config import resolve_oracle_batch_id
from modelFactory.oracle.dataset import TARGET_COL

LOGGER = logging.getLogger(__name__)

_FRACS = [0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30]
_SEEDS = 5


def _average_random_tradeoff(df: pd.DataFrame, cat_col: str, seeds: int) -> list[dict[str, Any]]:
    """Courbe de rejet aléatoire moyenne sur plusieurs graines."""
    acc: dict[float, list[dict[str, Any]]] = {f: [] for f in _FRACS}
    for seed in range(seeds):
        rng = np.random.default_rng(seed)
        rnd = df.assign(_rnd=rng.uniform(size=len(df)))
        for row in _rejection_tradeoff(rnd, "_rnd", cat_col):
            acc[row["reject_frac"]].append(row)
    rows = []
    for f in _FRACS:
        a = acc[f]
        rows.append({
            "reject_frac": f,
            "cat_kept_frac": float(np.mean([x["cat_kept_frac"] for x in a])),
            "top_kept_frac": float(np.mean([x["top_kept_frac"] for x in a])),
        })
    return rows


def run_confound_validation(batch_id: str, *, horizon: int = 20, start: str = "2022-01-01") -> dict[str, Any]:
    engine = get_sqlalchemy_engine()
    df = _build_dataset(engine, batch_id, horizon)
    df = df[(df["b25_top"]) & (df["pe_ratio"].notna()) & (df["date"] >= pd.Timestamp(start))].copy()
    df["cat10"] = (df["oracle_pct_rank"] < 0.10).astype(int)
    df["cat20"] = (df["oracle_pct_rank"] < 0.20).astype(int)
    LOGGER.info("B25 TOP ∩ pe_ratio dispo = %d candidats", len(df))

    baseline = {
        "n": int(len(df)),
        "cat10_pct": float(df["cat10"].mean()) * 100,
        "cat20_pct": float(df["cat20"].mean()) * 100,
        "true_top_pct": float((df[TARGET_COL] == 1).mean()) * 100,
    }

    def _ratio_table(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out = []
        for r in rows:
            cat_avoid = 1.0 - r["cat_kept_frac"] if r["cat_kept_frac"] is not None else None
            top_lost = 1.0 - r["top_kept_frac"] if r["top_kept_frac"] is not None else None
            ratio = (cat_avoid / top_lost) if (top_lost and top_lost > 0 and cat_avoid is not None) else None
            out.append({**r, "ratio": ratio})
        return out

    report: dict[str, Any] = {
        "status": "completed",
        "baseline": baseline,
        "cat10": {
            "pe": _ratio_table(_rejection_tradeoff(df, "pe_ratio", "cat10")),
            "random": _ratio_table(_average_random_tradeoff(df, "cat10", _SEEDS)),
        },
        "cat20": {
            "pe": _ratio_table(_rejection_tradeoff(df, "pe_ratio", "cat20")),
            "random": _ratio_table(_average_random_tradeoff(df, "cat20", _SEEDS)),
        },
    }
    return report


def _print_table(title: str, rows: list[dict[str, Any]]) -> str:
    lines = [f"  {title}"]
    lines.append(f"    {'rejet%':>6} {'cat_rest%':>9} {'TOP_rest%':>9} {'ratio':>7}")
    for r in rows:
        cat = r["cat_kept_frac"] * 100 if r["cat_kept_frac"] is not None else float('nan')
        top = r["top_kept_frac"] * 100 if r["top_kept_frac"] is not None else float('nan')
        ratio = r["ratio"] if r["ratio"] is not None else float('nan')
        lines.append(f"    {r['reject_frac']*100:>6.0f} {cat:>9.1f} {top:>9.1f} {ratio:>7.2f}")
    return "\n".join(lines)


def format_report(report: dict[str, Any]) -> str:
    if report.get("status") != "completed":
        return f"confound_validation: {report}"
    b = report["baseline"]
    lines = ["=== S6.6-C — VALIDATION CONFOUND-FREE de PE (B25 TOP ∩ pe_ratio dispo) ==="]
    lines.append(f"Baseline même sous-ensemble : n={b['n']} cat10={b['cat10_pct']:.1f}% cat20={b['cat20_pct']:.1f}% vraiTOP={b['true_top_pct']:.1f}%")
    for key in ("cat10", "cat20"):
        lines.append(f"\nCible {key} :")
        lines.append(_print_table("PE (rejeter les plus chers)", report[key]["pe"]))
        lines.append(_print_table("RANDOM (baseline)", report[key]["random"]))
    lines.append("\nLecture : ratio = catastrophes évitées / TOP sacrifiés. Random ≈ 1.0. PE > 1.0 ⇔ signal réel.")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validation confound-free de PE (S6.6-C).")
    parser.add_argument("--batch-id", default=None)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    batch_id = args.batch_id or resolve_oracle_batch_id()
    if not batch_id:
        raise SystemExit("Aucun batch_id résolu.")
    report = run_confound_validation(batch_id)
    import os
    out = "artifacts/models/oracle/confound_validation_report.json"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"→ rapport sauvegardé : {out}")
    print(format_report(report))


if __name__ == "__main__":
    main()
