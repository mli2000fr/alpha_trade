"""Compare frozen 2025 ATR/Oracle selections with native realized H20 labels."""
import argparse
import hashlib
import json
import logging
from pathlib import Path

import pandas as pd

from database.connection import get_sqlalchemy_engine
from modelFactory.oracle.build_labels import build_labels
from modelFactory.oracle.extreme_gate import compute_extreme_gate


def compare(panel: pd.DataFrame, labels: pd.DataFrame, atr: str) -> dict:
    if panel.duplicated(["date", "symbol"]).any() or labels.duplicated(["prediction_date", "symbol"]).any():
        raise ValueError("Duplicate labels or predictions")
    # Freeze gates before joining future labels: invalid targets cannot alter ranks.
    frozen = compute_extreme_gate(panel.dropna(subset=[atr, "proba_extreme"]))
    frozen["atr_top20"] = frozen.groupby("date")[atr].rank(pct=True).ge(.8)
    selected = frozen.merge(labels.rename(columns={"prediction_date": "date"}),
                            on=["date", "symbol"], how="left", validate="one_to_one")
    masks = {"ALL": pd.Series(True, index=selected.index), "ATR_TOP20": selected.atr_top20,
             "ORACLE_TOP20": selected.extreme_gate,
             "INTERSECTION": selected.atr_top20 & selected.extreme_gate,
             "ORACLE_NOT_ATR": selected.extreme_gate & ~selected.atr_top20,
             "ATR_NOT_ORACLE": selected.atr_top20 & ~selected.extreme_gate}
    results = {}
    for name, mask in masks.items():
        cohort = selected[mask]
        valid = cohort[cohort.target_quality_valid.eq(1) & cohort.oracle_decile.notna()]
        counts = valid.oracle_decile.value_counts().reindex(range(1, 11), fill_value=0)
        denominator = len(valid)
        tails = int(valid.oracle_decile.isin([1, 10]).sum())
        results[name] = {"selected": len(cohort), "share_of_universe": len(cohort)/len(selected),
                         "valid_realized_labels": denominator, "unknown_or_invalid_labels": len(cohort)-denominator,
                         "decile_counts": {str(k): int(v) for k, v in counts.items()},
                         "decile_percent": {str(k): 100*int(v)/denominator if denominator else None for k, v in counts.items()},
                         "d1_or_d10_percent": 100*tails/denominator if denominator else None,
                         "native_extreme_label_percent": 100*float(valid.oracle_extreme10.mean()) if denominator else None}
    return results


def compare_sentiment_at_j(windows: pd.DataFrame, labels: pd.DataFrame) -> dict:
    """Frozen ATR20 intersection: positive and negative news groups may overlap."""
    if windows.duplicated(["date", "symbol"]).any() or labels.duplicated(["prediction_date", "symbol"]).any():
        raise ValueError("Duplicate labels or predictions")
    intersection = windows[windows.intersection].copy()
    data = intersection.merge(labels.rename(columns={"prediction_date": "date"}),
                              on=["date", "symbol"], how="left", validate="one_to_one")
    valid = data[data.target_quality_valid.eq(1) & data.oracle_decile.notna()]
    masks = {"BASE_INTERSECTION": pd.Series(True, index=valid.index),
             "POSITIVE_AT_J": valid.positive_lag0,
             "NEGATIVE_AT_J": valid.negative_lag0,
             "BOTH_AT_J": valid.positive_lag0 & valid.negative_lag0,
             "POSITIVE_ONLY_AT_J": valid.positive_lag0 & ~valid.negative_lag0,
             "NEGATIVE_ONLY_AT_J": valid.negative_lag0 & ~valid.positive_lag0}
    result = {"intersection_selected": len(data), "invalid_or_unknown_labels": len(data)-len(valid), "groups": {}}
    base_counts = valid.oracle_decile.value_counts()
    for name, mask in masks.items():
        cohort = valid[mask]
        counts = cohort.oracle_decile.value_counts().reindex(range(1, 11), fill_value=0)
        result["groups"][name] = {
            "selected": len(cohort), "symbols": int(cohort.symbol.nunique()),
            "share_of_valid_intersection_pct": 100*len(cohort)/len(valid) if len(valid) else None,
            "decile_counts": {str(k): int(v) for k, v in counts.items()},
            "decile_percent": {str(k): 100*int(v)/len(cohort) if len(cohort) else None for k, v in counts.items()},
            "coverage_of_intersection_decile_pct": {
                str(k): 100*int(v)/int(base_counts.get(k, 0)) if base_counts.get(k, 0) else None for k, v in counts.items()}}
    return result


def run(panel_path: Path, output: Path):
    output.mkdir(parents=True, exist_ok=False)
    panel = pd.read_parquet(panel_path)
    symbols = sorted(panel.symbol.unique())
    engine = get_sqlalchemy_engine()
    label_path = output / "native_realized_labels.parquet"
    status = build_labels("model-factory-20261003082853-e98332", horizon=20,
                          start_date="2025-01-01", end_date="2025-12-31", engine=engine,
                          dry_run=True, symbols=symbols, output_parquet=str(label_path),
                          progress_callback=lambda n, total, message: logging.info("%s %s/%s", message, n, total))
    if status.get("status") != "dry_run" or not label_path.exists():
        raise ValueError(f"Native label reconstruction failed: {status}")
    labels = pd.read_parquet(label_path)
    labels["prediction_date"] = pd.to_datetime(labels.prediction_date)
    report = {"status": "COMPLETED_RECONSTRUCTED_NATIVE_LABELS_RESEARCH", "label_build": status,
              "panel_sha256": hashlib.sha256(panel_path.read_bytes()).hexdigest(),
              "labels_sha256": hashlib.sha256(label_path.read_bytes()).hexdigest(),
              "comparisons": {atr: compare(panel, labels, atr) for atr in ("atr_14_norm", "atr20_pct")},
              "notes": ["Native adjusted H20 returns, source/identity/price-break guards, cross-sectional rank method=max",
                        "Deciles ranked in the entire eligible daily universe, never within the selected intersection",
                        "Selection fixed before target-quality filtering; unknown targets remain in selection counts",
                        "D1 is bottom 10%; D10 is top 10%; not equivalent to simply negative/positive return",
                        "Native extreme flag uses >=90th percentile, so boundary ties can differ from D1+D10",
                        "Current static universe and revised historical prices: not a new PIT certification"],
              "sql_writes": False}
    (output / "report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    run(args.panel, args.output)
