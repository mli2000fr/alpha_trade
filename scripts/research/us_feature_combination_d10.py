"""Fixed equal-weight feature blocks; exploratory 2025, no SQL/fit."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.us_intersection_sentiment_deciles import ROOT


def build_scores(pool, news):
    data = pool.copy()
    for feature in ["momentum_120", "rolling_volatility_60", "atr20_pct"]:
        data[feature] = pd.to_numeric(data[feature], errors="coerce").replace([np.inf, -np.inf], np.nan)
    ranks = data[["momentum_120", "rolling_volatility_60", "atr20_pct"]].groupby(data.date).rank(pct=True)
    data["M"] = ranks.momentum_120.fillna(.5)
    data["V"] = (ranks.rolling_volatility_60.fillna(.5) + ranks.atr20_pct.fillna(.5))/2
    news = news.copy()
    news["date"] = pd.to_datetime(news.date)
    # Any archived missing article score invalidates the daily minimum.
    daily = news.groupby(["date", "symbol"]).positive_score.agg(["min", "count", "size"])
    daily.loc[daily["count"].ne(daily["size"]), "min"] = np.nan
    data = data.merge(daily[["min"]].rename(columns={"min": "positive_daily_min"}),
                      on=["date", "symbol"], how="left", validate="one_to_one")
    data["S"] = data.positive_daily_min.groupby(data.date).rank(pct=True).fillna(.5)
    for name, blocks in {"MV": ["M", "V"], "MS": ["M", "S"], "VS": ["V", "S"], "MVS": ["M", "V", "S"]}.items():
        data[name] = data[blocks].mean(axis=1)
    return data


def pick(data, policy, fraction):
    ordered = data.sort_values(["date", policy, "symbol"], ascending=[True, False, True])
    position = ordered.groupby("date").cumcount()
    size = ordered.groupby("date").symbol.transform("size")
    return ordered[position.lt(np.ceil(size * fraction))].copy()


def metrics(data):
    valid = data[data.target_quality_valid.eq(1) & data.oracle_decile.notna() & data.future_return.notna()]
    n = len(valid)
    returns = valid.future_return
    daily = valid.groupby("date").agg(ret=("future_return", "mean"))
    daily["d10"] = valid.oracle_decile.eq(10).groupby(valid.date).mean()
    daily["d1"] = valid.oracle_decile.eq(1).groupby(valid.date).mean()
    return {"selected": len(data), "valid": n, "unknown": len(data)-n,
            "symbols": int(data.symbol.nunique()), "dates": int(data.date.nunique()),
            "decile_counts": {str(k): int(valid.oracle_decile.eq(k).sum()) for k in range(1,11)},
            "d10_pct": float(100*valid.oracle_decile.eq(10).mean()) if n else None,
            "d1_pct": float(100*valid.oracle_decile.eq(1).mean()) if n else None,
            "mean_return_pct": float(100*returns.mean()) if n else None,
            "median_return_pct": float(100*returns.median()) if n else None,
            "positive_return_pct": float(100*returns.gt(0).mean()) if n else None,
            "daily_equal_mean_return_pct": float(100*daily.ret.mean()) if n else None,
            "daily_equal_d10_pct": float(100*daily.d10.mean()) if n else None,
            "daily_equal_d1_pct": float(100*daily.d1.mean()) if n else None}


def evaluate(selected):
    return {"overall": metrics(selected),
            "semesters": {name: metrics(selected[mask]) for name, mask in
                          [("H1", selected.date.lt("2025-07-01")), ("H2", selected.date.ge("2025-07-01"))]},
            "months": {str(month): metrics(group) for month, group in selected.groupby(selected.date.dt.to_period("M"))}}


def main():
    sources = {"features": ROOT / "feature-separation-20261004-v1/features.parquet",
               "windows": ROOT / "audit-20261004-v1/symbol_day_windows.parquet",
               "labels": ROOT / "intersection-realized-20261004-v1/native_realized_labels.parquet",
               "news": ROOT / "audit-20261004-v1/news_observations.parquet"}
    features, windows, labels, news = [pd.read_parquet(sources[k]) for k in ["features", "windows", "labels", "news"]]
    pool = windows[windows.intersection][["date", "symbol"]].merge(
        features[["date", "symbol", "momentum_120", "rolling_volatility_60", "atr20_pct"]],
        on=["date", "symbol"], how="left", validate="one_to_one")
    scored = build_scores(pool, news)
    # Freeze all selections before future labels are joined.
    policies = {f"{name}_TOP{int(fraction*100)}": pick(scored, name, fraction)
                for name in ["M", "V", "S", "MV", "MS", "VS", "MVS"] for fraction in [.1, .2]}
    labels = labels.rename(columns={"prediction_date": "date"})
    labels["date"] = pd.to_datetime(labels.date)
    def join(data):
        return data.merge(labels[["date", "symbol", "oracle_decile", "future_return", "target_quality_valid"]],
                          on=["date", "symbol"], how="left", validate="one_to_one")
    results = {name: evaluate(join(data)) for name, data in policies.items()}
    result = {"status": "COMPLETED_EXPLORATORY_NO_GO_DECISION", "baseline": evaluate(join(scored)),
              "policies": results, "sentiment_available": int(scored.positive_daily_min.notna().sum()),
              "sentiment_missing": int(scored.positive_daily_min.isna().sum()),
              "sources": {k: {"path": str(p), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for k,p in sources.items()},
              "notes": ["Fixed 7 policies, equal block weights, TOP10/TOP20, no tuning or fit",
                        "Candidates selected before future label join; scores ranked inside frozen ATR/Oracle pool",
                        "2025 feature selection already inspected: no untouched confirmation period",
                        "Scores using close J; returns close J to close J+20 are descriptive, not executable fills",
                        "Historical sentiment created after 2025: PIT noncertified; missing score set neutral, not eliminated",
                        "No costs, portfolio, annualization, clustered inference or multiple testing correction"],
              "sql_writes": False, "models_refit": False}
    output = ROOT / "combination-d10-20261004-v1"
    output.mkdir(parents=True, exist_ok=False)
    (output / "report.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    join(scored).to_parquet(output / "scored_panel.parquet", index=False)
    for name in ["BASE"] + list(results):
        item = result["baseline"] if name == "BASE" else results[name]
        m = item["overall"]
        print(name, "n",m["selected"],"D10",round(m["d10_pct"],2),"D1",round(m["d1_pct"],2),
              "RET",round(m["mean_return_pct"],2), "H1RET",round(item["semesters"]["H1"]["mean_return_pct"],2),
              "H2RET",round(item["semesters"]["H2"]["mean_return_pct"],2))


if __name__ == "__main__":
    main()
