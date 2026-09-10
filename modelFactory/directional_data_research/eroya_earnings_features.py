"""Evaluation PIT des surprises de résultats Eroya dans Oracle TOP20.

Le timestamp Eroya est souvent une date encodée à minuit. Pour éviter toute
fuite, estimation, EPS réalisé et surprise ne deviennent disponibles qu'au
premier jour ouvré suivant l'événement, quelle que soit l'heure fournie.
Ce module de recherche ne modifie ni modèle, ni table de production.
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd

from database.connection import get_sqlalchemy_engine
from modelFactory.directional_data_research.eroya_features import (
    analyze_complete_cases,
    assemble_bundle_pool_at_horizon,
    evaluate_policy_by_fold,
    find_collection,
    iter_payloads,
    merge_asof_by_symbol,
)
from modelFactory.directional_data_research.harness import assemble_pool, format_report
from modelFactory.global_direction.dataset import DECILE_COL, RETURN_COL

LOGGER = logging.getLogger(__name__)


def load_earnings_events(path: Path) -> pd.DataFrame:
    """Charge uniquement les résultats publiés et applique le délai PIT strict."""
    rows: list[dict[str, Any]] = []
    for requested, payload in iter_payloads(path):
        results = payload.get("results") or {}
        events = results.get("events") or [] if isinstance(results, dict) else []
        for row in events:
            if not isinstance(row, dict) or row.get("eventType") != "Earnings":
                continue
            rows.append({
                "symbol": requested,
                "event_timestamp": row.get("earningsDate"),
                "eps_estimate": row.get("epsEstimate"),
                "eps_actual": row.get("epsActual"),
                "surprise_pct": row.get("surprisePercent"),
            })
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    stamp = pd.to_datetime(frame["event_timestamp"], errors="coerce", utc=True)
    frame["event_date"] = stamp.dt.tz_convert("America/New_York").dt.tz_localize(None).dt.normalize()
    frame["available_date"] = frame["event_date"] + pd.offsets.BDay(1)
    for column in ("eps_estimate", "eps_actual", "surprise_pct"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["symbol", "event_date", "surprise_pct"])
    return frame.sort_values(["symbol", "available_date", "event_date"]).drop_duplicates(
        ["symbol", "event_date"], keep="last")


def build_earnings_features(pool: pd.DataFrame, events: pd.DataFrame,
                            *, max_age_days: int = 90) -> pd.DataFrame:
    """Associe à chaque candidat Oracle la dernière surprise connue."""
    if events.empty:
        return pool[["date", "symbol"]].copy()
    source = events[["symbol", "available_date", "event_date", "surprise_pct",
                     "eps_estimate", "eps_actual"]].copy()
    merged = merge_asof_by_symbol(
        pool, source, right_date="available_date", allow_exact=True,
        max_age_days=max_age_days)
    merged["eroya_earnings_days_since"] = (merged["date"] - merged["event_date"]).dt.days
    surprise = merged["surprise_pct"].clip(-200.0, 200.0)
    merged["eroya_earnings_surprise_pct"] = surprise
    merged["eroya_earnings_surprise_signed_log"] = np.sign(surprise) * np.log1p(surprise.abs())
    for days in (5, 20, 60):
        fresh = merged["eroya_earnings_days_since"].between(1, days)
        merged[f"eroya_earnings_surprise_{days}d"] = surprise.where(fresh)
    return merged[["date", "symbol", *[c for c in merged if c.startswith("eroya_")]]]


def evaluate_signed_rules(frame: pd.DataFrame) -> pd.DataFrame:
    """Mesure des règles lisibles, sans fabriquer de quantiles avec les absents."""
    rows: list[dict[str, Any]] = []
    groups = [("ALL", frame), *[(str(k), v) for k, v in frame.groupby("fold_start")]]
    for fold, part in groups:
        baseline_return = float(part[RETURN_COL].mean())
        baseline_long = float((part[DECILE_COL] >= 8).mean())
        baseline_short = float((part[DECILE_COL] <= 3).mean())
        for days in (5, 20, 60):
            column = f"eroya_earnings_surprise_{days}d"
            for threshold in (0.0, 5.0, 10.0, 25.0):
                masks = {
                    "LONG": part[column] >= threshold if threshold else part[column] > 0,
                    "SHORT": part[column] <= -threshold if threshold else part[column] < 0,
                }
                for side, mask in masks.items():
                    selected = part.loc[mask.fillna(False)]
                    if selected.empty:
                        continue
                    if side == "LONG":
                        precision = float((selected[DECILE_COL] >= 8).mean())
                        pnl = float(selected[RETURN_COL].mean())
                        lift = pnl - baseline_return
                        precision_lift = precision - baseline_long
                    else:
                        precision = float((selected[DECILE_COL] <= 3).mean())
                        pnl = float(-selected[RETURN_COL].mean())
                        lift = pnl + baseline_return
                        precision_lift = precision - baseline_short
                    rows.append({"fold": fold, "side": side, "window_days": days,
                                 "abs_surprise_threshold_pct": threshold,
                                 "n": len(selected), "coverage_ratio": len(selected) / len(part),
                                 "precision_d1d3_or_d8d10": precision,
                                 "precision_lift": precision_lift,
                                 "mean_realized_pnl": pnl, "pnl_lift": lift})
    return pd.DataFrame(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2025-12-31")
    parser.add_argument("--horizon", type=int, default=20)
    parser.add_argument("--oracle-run")
    parser.add_argument("--root", type=Path, default=Path("artifacts/research/eroya_directional"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    source = find_collection("earnings_dates", args.root)
    engine = get_sqlalchemy_engine()
    pool = assemble_pool(engine, args.batch_id, start_date=args.start_date,
                         end_date=args.end_date, horizon=args.horizon, oracle_run=args.oracle_run)
    if pool.empty:
        pool = assemble_bundle_pool_at_horizon(engine, args.batch_id,
                                               start_date=args.start_date,
                                               end_date=args.end_date,
                                               horizon=args.horizon)
    if pool.empty:
        raise SystemExit("Pool Oracle TOP20 vide.")
    events = load_earnings_events(source)
    features = build_earnings_features(pool, events)
    frame = pool.merge(features, on=["date", "symbol"], how="left")
    columns = [c for c in frame if c.startswith("eroya_earnings_") and c != "eroya_earnings_days_since"]
    separability = analyze_complete_cases(frame, columns)
    folds = evaluate_policy_by_fold(frame, columns)
    rules = evaluate_signed_rules(frame)
    output = args.output or args.root / (
        f"earnings-evaluation-{pd.Timestamp.utcnow():%Y%m%d%H%M%S%f}-h{args.horizon}-{args.batch_id[-6:]}")
    output.mkdir(parents=True, exist_ok=False)
    separability.to_csv(output / "earnings_separability.csv", index=False)
    folds.to_csv(output / "earnings_policy_by_fold.csv", index=False)
    rules.to_csv(output / "earnings_signed_rules.csv", index=False)
    frame[["date", "symbol", *[c for c in features if c.startswith("eroya_")]]].to_parquet(
        output / "earnings_features_oracle_top20.parquet", index=False)
    report = {"batch_id": args.batch_id, "horizon": args.horizon,
              "period": [args.start_date, args.end_date], "pool_rows": len(pool),
              "pool_symbols": int(pool["symbol"].nunique()), "earnings_events": len(events),
              "source": str(source.resolve()),
              "pit_contract": "all earnings fields available first business day after event"}
    (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(format_report(separability) if not separability.empty else "Aucun résultat.")
    print(f"Artefacts earnings Eroya : {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
