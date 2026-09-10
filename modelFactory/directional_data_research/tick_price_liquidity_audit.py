"""Audit exploratoire prix/spread/liquidité depuis des ticks déjà collectés."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu, spearmanr
from sklearn.metrics import roc_auc_score

from modelFactory.oracle_ablation_amplitude_compare import prepare_labels

UTC = timezone.utc
DIRECTION_FEATURES = ["return_30m", "return_5m", "close_vs_vwap_30m", "close_location_30m"]
AMPLITUDE_FEATURES = ["realized_vol_30m", "range_30m", "median_spread_bps", "log_trade_count", "log_quote_count"]


def event_features(trades: pd.DataFrame, quotes: pd.DataFrame) -> dict[str, Any]:
    if trades.empty or quotes.empty:
        return {
            "feature_status": "insufficient", "trade_count": int(len(trades)),
            "quote_count": int(len(quotes)),
        }
    t = trades.copy()
    q = quotes.copy()
    t["ts"] = pd.to_datetime(pd.to_numeric(t["sip_timestamp"], errors="coerce"), unit="ns", utc=True)
    q["ts"] = pd.to_datetime(pd.to_numeric(q["sip_timestamp"], errors="coerce"), unit="ns", utc=True)
    for name in ("price", "size"):
        t[name] = pd.to_numeric(t[name], errors="coerce")
    for name in ("bid_price", "ask_price"):
        q[name] = pd.to_numeric(q[name], errors="coerce")
    t = t.dropna(subset=["ts", "price", "size"]).query("price > 0 and size > 0").sort_values("ts")
    q = q.dropna(subset=["ts", "bid_price", "ask_price"])
    q = q[(q["bid_price"] > 0) & (q["ask_price"] >= q["bid_price"])].sort_values("ts")
    if len(t) < 2 or q.empty:
        return {"feature_status": "insufficient", "trade_count": len(t), "quote_count": len(q)}
    first_price, last_price = float(t.iloc[0]["price"]), float(t.iloc[-1]["price"])
    start_late = t["ts"].max() - pd.Timedelta(minutes=5)
    late = t[t["ts"] >= start_late]
    late_first = float(late.iloc[0]["price"])
    total_size = float(t["size"].sum())
    vwap = float((t["price"] * t["size"]).sum() / total_size)
    low, high = float(t["price"].min()), float(t["price"].max())
    log_returns = np.log(t["price"]).diff().dropna()
    mid = (q["bid_price"] + q["ask_price"]) / 2.0
    spread_bps = (q["ask_price"] - q["bid_price"]) / mid.replace(0, np.nan) * 10_000.0
    return {
        "feature_status": "complete", "trade_count": int(len(t)), "quote_count": int(len(q)),
        "return_30m": last_price / first_price - 1.0,
        "return_5m": last_price / late_first - 1.0,
        "close_vs_vwap_30m": last_price / vwap - 1.0,
        "close_location_30m": ((last_price - low) / (high - low) - 0.5) * 2.0 if high > low else 0.0,
        "realized_vol_30m": float(np.sqrt(np.square(log_returns).sum())),
        "range_30m": high / low - 1.0,
        "median_spread_bps": float(spread_bps.median()),
        "log_trade_count": float(np.log1p(len(t))),
        "log_quote_count": float(np.log1p(len(q))),
    }


def build_features(trades: pd.DataFrame, quotes: pd.DataFrame) -> pd.DataFrame:
    rows = []
    quote_groups = {key: group for key, group in quotes.groupby("event_id", sort=False)}
    for event_id, group in trades.groupby("event_id", sort=False):
        q = quote_groups.get(event_id, pd.DataFrame())
        rows.append({
            "event_id": event_id, "date": pd.to_datetime(group["event_date"].iloc[0]).normalize(),
            "symbol": str(group["symbol"].iloc[0]), **event_features(group, q),
        })
    return pd.DataFrame(rows)


def _semester_rows(data: pd.DataFrame, feature: str, target: str) -> tuple[list[dict[str, Any]], float]:
    rows = []
    for semester, group in data.groupby("semester", sort=True):
        auc = None
        if group[target].nunique() == 2:
            auc = float(roc_auc_score(group[target], group[feature]))
        rows.append({"semester": semester, "rows": int(len(group)), "auc": auc})
    values = [row["auc"] for row in rows if row["auc"] is not None]
    return rows, float(np.mean(np.asarray(values) > 0.5)) if values else 0.0


def evaluate(features: pd.DataFrame, labels: pd.DataFrame) -> dict[str, Any]:
    data = features.merge(labels, on=["date", "symbol"], how="inner", validate="one_to_one")
    data = data[data["feature_status"].eq("complete")].copy()
    data["semester"] = data["date"].dt.year.astype(str) + "H" + np.where(data["date"].dt.month.le(6), "1", "2")
    tail = data[data["future_return"].ge(0.03) | data["future_return"].le(-0.03)].copy()
    tail["is_long_tail"] = tail["future_return"].ge(0.03).astype(int)
    total_tests = len(DIRECTION_FEATURES) + len(AMPLITUDE_FEATURES)
    direction: dict[str, Any] = {}
    for name in DIRECTION_FEATURES:
        valid = tail.dropna(subset=[name])
        auc = float(roc_auc_score(valid["is_long_tail"], valid[name]))
        positive = valid.loc[valid["is_long_tail"].eq(1), name]
        negative = valid.loc[valid["is_long_tail"].eq(0), name]
        p_value = float(mannwhitneyu(positive, negative, alternative="greater").pvalue)
        rho, rho_p = spearmanr(data[name], data["future_return"], nan_policy="omit")
        semesters, stable = _semester_rows(valid, name, "is_long_tail")
        gates = {
            "rows_ge_150": len(valid) >= 150, "auc_ge_053": auc >= 0.53,
            "spearman_ge_003": float(rho) >= 0.03, "positive_semester_ratio_ge_070": stable >= 0.70,
            "bonferroni_p_lt_005": min(1.0, p_value * total_tests) < 0.05,
        }
        gates["all_passed"] = all(gates.values())
        direction[name] = {
            "rows": int(len(valid)), "auc": auc, "spearman_future_return": float(rho),
            "spearman_p_value": float(rho_p), "p_value": p_value,
            "bonferroni_p_value": min(1.0, p_value * total_tests),
            "positive_semester_ratio": stable, "semesters": semesters, "gates": gates,
        }
    amplitude: dict[str, Any] = {}
    for name in AMPLITUDE_FEATURES:
        valid = data.dropna(subset=[name, "oracle_extreme10"])
        valid = valid[valid["oracle_extreme10"].isin([0, 1])]
        auc = float(roc_auc_score(valid["oracle_extreme10"], valid[name]))
        positive = valid.loc[valid["oracle_extreme10"].eq(1), name]
        negative = valid.loc[valid["oracle_extreme10"].eq(0), name]
        p_value = float(mannwhitneyu(positive, negative, alternative="greater").pvalue)
        rho, rho_p = spearmanr(valid[name], valid["abs_future_return"], nan_policy="omit")
        semesters, stable = _semester_rows(valid, name, "oracle_extreme10")
        gates = {
            "rows_ge_150": len(valid) >= 150, "auc_ge_053": auc >= 0.53,
            "spearman_ge_003": float(rho) >= 0.03, "positive_semester_ratio_ge_070": stable >= 0.70,
            "bonferroni_p_lt_005": min(1.0, p_value * total_tests) < 0.05,
        }
        gates["all_passed"] = all(gates.values())
        amplitude[name] = {
            "rows": int(len(valid)), "auc": auc, "spearman_abs_future_return": float(rho),
            "spearman_p_value": float(rho_p), "p_value": p_value,
            "bonferroni_p_value": min(1.0, p_value * total_tests),
            "positive_semester_ratio": stable, "semesters": semesters, "gates": gates,
        }
    return {
        "rows_with_labels": int(len(data)), "tail_rows": int(len(tail)), "total_tests": total_tests,
        "direction": direction, "amplitude": amplitude,
        "direction_discovery": any(v["gates"]["all_passed"] for v in direction.values()),
        "amplitude_discovery": any(v["gates"]["all_passed"] for v in amplitude.values()),
        "confirmation_required": True,
    }


def run(args: argparse.Namespace) -> Path:
    source = Path(args.source)
    output = args.output or source.parent / f"tick-price-liquidity-{datetime.now(UTC):%Y%m%d%H%M%S}"
    output.mkdir(parents=True, exist_ok=False)
    trades = pd.read_parquet(source / "trades.parquet")
    quotes = pd.read_parquet(source / "quotes.parquet")
    features = build_features(trades, quotes)
    features.to_parquet(output / "features.parquet", index=False)
    labels = prepare_labels(Path(args.labels_path), args.start_date, args.end_date)
    labeled = features.merge(labels, on=["date", "symbol"], how="inner", validate="one_to_one")
    labeled.to_parquet(output / "labeled_features.parquet", index=False)
    evaluation = evaluate(features, labels)
    report = {
        "schema_version": 1, "experiment": "tick_price_liquidity_discovery",
        "status": "completed", "research_only": True, "serving_ready": False,
        "source": str(source), "selection_uses_future_outcome": False,
        "features_complete": int(features["feature_status"].eq("complete").sum()),
        "evaluation": evaluation,
        "decision_rule": "Découverte seulement; tout passage exige un échantillon indépendant.",
    }
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--labels-path", required=True)
    parser.add_argument("--start-date", default="2022-03-07")
    parser.add_argument("--end-date", default="2025-06-30")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    path = run(args)
    print(json.dumps({"output": str(path), "report": str(path / "report.json")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
