"""Exploratory D1/D10 univariate audit, frozen 2025 ATR/Oracle intersection."""
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata
from sqlalchemy import text

from database.connection import get_sqlalchemy_engine
from modelFactory.features import get_feature_columns
from modelFactory.oracle.dataset import build_feature_matrix
from scripts.research.us_intersection_sentiment_deciles import ROOT

OUTPUT = ROOT / "feature-separation-20261004-v1"


def auc(y, x):
    y = np.asarray(y, dtype=bool)
    x = np.asarray(x, dtype=float)
    n1, n0 = int(y.sum()), int((~y).sum())
    if not n1 or not n0:
        return None
    ranks = rankdata(x, method="average")
    return float((ranks[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def describe(data, feature, daily_rank=None):
    values = pd.to_numeric(data[feature], errors="coerce").replace([np.inf, -np.inf], np.nan)
    valid = values.notna()
    x = values[valid].to_numpy()
    y = data.loc[valid, "oracle_decile"].eq(10).to_numpy()
    result = {"feature": feature, "valid": int(valid.sum()), "coverage": float(valid.mean()),
              "unique": int(values.nunique()), "auc_raw": auc(y, x)}
    if not y.any() or y.all() or values.nunique() < 2:
        result["status"] = "UNAVAILABLE_OR_CONSTANT"
        return result
    low, high = x[~y], x[y]
    pooled = np.sqrt((np.var(low) + np.var(high))/2)
    result.update(mean_d1=float(low.mean()), mean_d10=float(high.mean()),
                  median_d1=float(np.median(low)), median_d10=float(np.median(high)),
                  mean_difference=float(high.mean()-low.mean()),
                  median_difference=float(np.median(high)-np.median(low)),
                  standardized_mean_difference=float((high.mean()-low.mean())/pooled) if pooled else None)
    # Must be computed across ALL frozen candidates before future-label filtering.
    if daily_rank is None:
        raise ValueError("Daily ranks across pre-label candidates required")
    day_rank = daily_rank.reindex(data.index)
    result["auc_daily_rank"] = auc(y, day_rank[valid])
    halves = {}
    for name, mask in [("H1", data.date.lt("2025-07-01")), ("H2", data.date.ge("2025-07-01"))]:
        mask &= valid
        halves[name] = {"valid": int(mask.sum()),
                        "auc": auc(data.loc[mask, "oracle_decile"].eq(10), day_rank[mask]),
                        "auc_raw": auc(data.loc[mask, "oracle_decile"].eq(10), values[mask])}
    result["halves"] = halves
    h1 = halves["H1"]["auc"]
    direction = 1 if h1 is not None and h1 >= .5 else -1
    result["direction_frozen_h1"] = direction
    result["h2_auc_h1_direction"] = (halves["H2"]["auc"] if direction == 1 else 1-halves["H2"]["auc"]) if halves["H2"]["auc"] is not None else None
    monthly = []
    for month, ids in data.groupby(data.date.dt.to_period("M")).groups.items():
        ids = [i for i in ids if valid.loc[i]]
        a = auc(data.loc[ids, "oracle_decile"].eq(10), day_rank.loc[ids])
        monthly.append({"month": str(month), "valid": len(ids), "auc_h1_direction": a if direction == 1 or a is None else 1-a})
    result["monthly"] = monthly
    result["months_above_05"] = sum(m["auc_h1_direction"] is not None and m["auc_h1_direction"] > .5 for m in monthly)
    result["status"] = "EXPLORATORY_NOT_PIT_CERTIFIED"
    return result


def main():
    OUTPUT.mkdir(parents=True, exist_ok=False)
    def progress(phase, **kwargs):
        logging.info("%s %s", phase, kwargs)
        (OUTPUT / "progress.json").write_text(json.dumps({"phase": phase, **kwargs}), encoding="utf-8")
    windows = pd.read_parquet(ROOT / "audit-20261004-v1/symbol_day_windows.parquet")
    labels = pd.read_parquet(ROOT / "intersection-realized-20261004-v1/native_realized_labels.parquet")
    labels["prediction_date"] = pd.to_datetime(labels.prediction_date)
    symbols = sorted(windows.symbol.unique())
    options = {"feature_set": "expert", "enable_cross_sectional_ranks": True,
               **{f"include_{family}": True for family in ["sentiment", "screener_scores", "short_score",
                  "macro_vix", "macro_vxn", "macro_vix3m", "macro_move", "fundamentals", "factors",
                  "macro_regime", "score_components", "volume_features"]}}
    engine = get_sqlalchemy_engine()
    with engine.connect() as conn:
        if conn.execute(text("SELECT DATABASE()")).scalar() != "alpha_trade":
            raise ValueError("US database required")
    progress("FEATURE_BUILD", symbols=len(symbols), options=options)
    frame = build_feature_matrix(engine, symbols, start_date="2025-01-01", end_date="2025-12-31", generator_options=options)
    frame["date"] = pd.to_datetime(frame.date)
    if frame.duplicated(["date", "symbol"]).any():
        raise ValueError("Duplicate features")
    frame = frame[frame.date.between("2025-01-01", "2025-12-31")].copy()
    allowed = get_feature_columns(**{k: v for k, v in options.items() if k != "enable_cross_sectional_ranks"})
    allowed += [c for c in frame if c.endswith("_xs_rank")] + ["drawdown_20", "high_low_position_20"]
    allowed = list(dict.fromkeys(allowed))
    available = [c for c in allowed if c in frame]
    frame = frame[["date", "symbol"] + available]
    frame.to_parquet(OUTPUT / "features.parquet", index=False)
    selected = windows[windows.intersection][["date", "symbol"]].merge(frame, on=["date", "symbol"], how="left", validate="one_to_one")
    selected = selected.merge(labels[["prediction_date", "symbol", "oracle_decile", "target_quality_valid"]].rename(columns={"prediction_date": "date"}), on=["date", "symbol"], validate="one_to_one")
    data = selected[selected.target_quality_valid.eq(1) & selected.oracle_decile.isin([1, 10])]
    progress("UNIVARIATE_AUDIT", candidates=len(selected), extremes=len(data), features=len(available))
    results = []
    for index, column in enumerate(available):
        daily_rank = selected[column].groupby(selected.date).rank(pct=True)
        results.append(describe(data, column, daily_rank))
        if index % 20 == 0:
            progress("UNIVARIATE_AUDIT", done=index+1, total=len(available))
    ranked = sorted([r for r in results if r.get("h2_auc_h1_direction") is not None and r["coverage"] >= .9],
                    key=lambda r: r["h2_auc_h1_direction"], reverse=True)
    report = {"status": "COMPLETED_EXPLORATORY", "year": 2025, "intersection": len(selected),
              "d1": int(data.oracle_decile.eq(1).sum()), "d10": int(data.oracle_decile.eq(10).sum()),
              "feature_count": len(available), "absent_columns": [c for c in allowed if c not in frame],
              "options": options, "features": results, "top20_h2_exploratory": ranked[:20],
              "notes": ["No new fit or SQL writes; frozen original ATR/Oracle selection",
                        "All local feature families supported by native Oracle dataset requested; sector/stacking not calculated by this builder",
                        "Native generator may fill unavailable features: non-null is not source/PIT certification",
                        "H1 determines orientation only; H2 feature ranking is exploratory, NOT untouched confirmation",
                        "No multiple-testing significance or clustered confidence intervals; overlapping H20 labels",
                        "Within-date ranks remove date levels but do not neutralize sector or symbol effects",
                        "Sentiment creation dates after 2025; historical availability not certified"]}
    (OUTPUT / "report.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    progress("COMPLETED", features=len(available))
    print(json.dumps({"output": str(OUTPUT), "top10": [{k:r[k] for k in ("feature", "auc_raw", "auc_daily_rank", "h2_auc_h1_direction", "months_above_05")} for r in ranked[:10]]}))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
