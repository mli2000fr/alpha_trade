"""Correct daily ranking scope of cached feature audit; no SQL or feature rebuild."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.us_feature_separation_audit import OUTPUT, describe
from scripts.research.us_intersection_sentiment_deciles import ROOT


def main():
    original = json.loads((OUTPUT / "report.json").read_text())
    frame = pd.read_parquet(OUTPUT / "features.parquet")
    windows = pd.read_parquet(ROOT / "audit-20261004-v1/symbol_day_windows.parquet")
    labels = pd.read_parquet(ROOT / "intersection-realized-20261004-v1/native_realized_labels.parquet")
    labels["prediction_date"] = pd.to_datetime(labels.prediction_date)
    pool = windows[windows.intersection][["date", "symbol"]].merge(frame, on=["date", "symbol"], how="left", validate="one_to_one")
    all_ranks = pool.drop(columns=["symbol", "date"]).groupby(pool.date).rank(pct=True)
    data = pool.merge(labels[["prediction_date", "symbol", "oracle_decile", "target_quality_valid"]].rename(columns={"prediction_date": "date"}), on=["date", "symbol"], validate="one_to_one")
    extremes = data[data.target_quality_valid.eq(1) & data.oracle_decile.isin([1, 10])]
    results = []
    for feature in all_ranks:
        result = describe(extremes, feature, all_ranks[feature])
        result["constant_within_every_date"] = bool(pool.groupby("date")[feature].nunique().le(1).all())
        if "monthly" in result:
            result["worst_month_auc"] = min(x["auc_h1_direction"] for x in result["monthly"] if x["auc_h1_direction"] is not None)
        results.append(result)
    eligible = [x for x in results if x.get("h2_auc_h1_direction") is not None
                and not x["constant_within_every_date"] and x["coverage"] >= .9]
    ranked = sorted(eligible, key=lambda x:x["h2_auc_h1_direction"], reverse=True)
    stable = sorted(eligible, key=lambda x:min(max(x["halves"]["H1"]["auc"], 1-x["halves"]["H1"]["auc"]), x["h2_auc_h1_direction"]), reverse=True)
    report = {**{k:v for k,v in original.items() if k not in ("features", "top20_h2_exploratory")},
              "status": "COMPLETED_REVIEWED_RANKS_PRE_LABEL", "features": results,
              "top20_h2_exploratory": ranked[:20], "top20_two_half_balance": stable[:20],
              "constant": [r["feature"] for r in results if r["unique"] < 2],
              "constant_per_date": [r["feature"] for r in results if r["constant_within_every_date"]],
              "correction": "Original within-extremes ranking superseded; all 67084 candidates ranked before labels; common-date constants excluded from shortlist"}
    # Correlation of selected candidates illustrates redundancy, not independent evidence.
    leaders = [r["feature"] for r in ranked[:10]]
    report["leader_spearman_correlations"] = extremes[leaders].corr(method="spearman").to_dict()
    dest = ROOT / "feature-separation-review-20261004-v1"
    dest.mkdir(parents=True, exist_ok=False)
    (dest / "report.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    print("REPORT", dest)
    print("CONSTANT", len(report["constant"]), "DATE_CONSTANT", len(report["constant_per_date"]))
    for name, values in [("TOP_H2", ranked[:20]), ("BALANCED", stable[:12])]:
        print(name)
        for r in values:
            print(r["feature"], "RAW", round(r["auc_raw"],4), "RANK", round(r["auc_daily_rank"],4),
                  "H1", round(r["halves"]["H1"]["auc"],4), "H2", round(r["h2_auc_h1_direction"],4),
                  "MONTHS", r["months_above_05"], "WORST", round(r["worst_month_auc"],4))


if __name__ == "__main__":
    main()
