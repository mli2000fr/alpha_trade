"""Causal closing-quote microstructure audit inside the Oracle TOP20 pool.

The source is the last historical Alpaca/IEX quote observed during session J.
The decision cutoff is 16:00 America/New_York and the earliest tradable entry
is J+1. This module is diagnostic only: it does not train or promote a model.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import bindparam, text

from database.connection import get_sqlalchemy_engine
from modelFactory.directional_data_research.harness import (
    analyze_features,
    assemble_pool,
    format_report,
)
from modelFactory.global_direction.config import resolve_global_direction_batch_id
from modelFactory.oracle.train import get_universe_symbols

LOGGER = logging.getLogger(__name__)

RAW_FEATURES = [
    "spread_bps",
    "size_imbalance",
    "microprice_minus_mid_bps",
    "log_quoted_depth_usd",
    "bid_depth_share",
    "quote_mid_minus_close_bps",
    "quote_age_seconds",
]
FEATURE_COLUMNS = RAW_FEATURES + [
    f"{column}_z60" for column in RAW_FEATURES
] + [
    f"{column}_xs_rank" for column in RAW_FEATURES
]


def load_closing_quotes(
    engine: Any,
    symbols: list[str],
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """Load one stored quote per symbol/session with its same-session close."""
    if not symbols:
        return pd.DataFrame()
    quote_query = text(
        "SELECT symbol, quote_date, quote_timestamp, bid_price, ask_price, "
        "bid_size, ask_size, spread_bps FROM stock_quote_snapshots "
        "WHERE symbol IN :symbols AND quote_date BETWEEN :start AND :end"
    ).bindparams(bindparam("symbols", expanding=True))
    close_query = text(
        "SELECT symbol, `date`, close FROM stock_bars_daily "
        "WHERE symbol IN :symbols AND `date` BETWEEN :start AND :end"
    ).bindparams(bindparam("symbols", expanding=True))
    params = {"symbols": symbols, "start": start_date, "end": end_date}
    with engine.connect() as conn:
        quotes = pd.read_sql(quote_query, conn, params=params)
        closes = pd.read_sql(close_query, conn, params=params)
    if quotes.empty:
        return quotes
    quotes = quotes.rename(columns={"quote_date": "date"})
    quotes["date"] = pd.to_datetime(quotes["date"], errors="coerce").dt.normalize()
    quotes["symbol"] = quotes["symbol"].astype(str).str.upper()
    if not closes.empty:
        closes = closes.rename(columns={"date": "date"})
        closes["date"] = pd.to_datetime(closes["date"], errors="coerce").dt.normalize()
        closes["symbol"] = closes["symbol"].astype(str).str.upper()
        closes["close"] = pd.to_numeric(closes["close"], errors="coerce")
        closes = closes.drop_duplicates(["date", "symbol"], keep="last")
        quotes = quotes.merge(closes[["date", "symbol", "close"]], on=["date", "symbol"], how="left")
    else:
        quotes["close"] = np.nan
    return quotes.drop_duplicates(["date", "symbol"], keep="last")


def derive_closing_quote_features(raw: pd.DataFrame) -> pd.DataFrame:
    """Derive causal signed/unsigned features and explicit quote validity."""
    if raw.empty:
        return raw.copy()
    out = raw.copy().sort_values(["symbol", "date"]).reset_index(drop=True)
    numeric = ["bid_price", "ask_price", "bid_size", "ask_size", "spread_bps", "close"]
    for column in numeric:
        out[column] = pd.to_numeric(out.get(column), errors="coerce")

    timestamp_utc = pd.to_datetime(out["quote_timestamp"], errors="coerce", utc=True)
    timestamp_ny = timestamp_utc.dt.tz_convert("America/New_York")
    quote_seconds = (
        timestamp_ny.dt.hour * 3600
        + timestamp_ny.dt.minute * 60
        + timestamp_ny.dt.second
    )
    out["quote_age_seconds"] = 16 * 3600 - quote_seconds
    local_date = timestamp_ny.dt.tz_localize(None).dt.normalize()

    bid = out["bid_price"]
    ask = out["ask_price"]
    bid_size = out["bid_size"]
    ask_size = out["ask_size"]
    depth = bid_size + ask_size
    mid = (bid + ask) / 2.0
    valid = (
        bid.gt(0)
        & ask.ge(bid)
        & bid_size.ge(0)
        & ask_size.ge(0)
        & depth.gt(0)
        & out["quote_timestamp"].notna()
        & local_date.eq(out["date"])
        & out["quote_age_seconds"].between(0, 6.5 * 3600)
    )
    out["quote_valid"] = valid.astype(int)
    out["quote_near_close_15m"] = (valid & out["quote_age_seconds"].le(900)).astype(int)
    out["size_imbalance"] = (bid_size - ask_size) / depth.where(depth.gt(0))
    microprice = (ask * bid_size + bid * ask_size) / depth.where(depth.gt(0))
    out["microprice_minus_mid_bps"] = (microprice / mid.where(mid.gt(0)) - 1.0) * 10_000.0
    out["bid_depth_share"] = bid_size / depth.where(depth.gt(0))
    out["log_quoted_depth_usd"] = np.log1p((mid * depth).clip(lower=0))
    out["quote_mid_minus_close_bps"] = (
        mid / out["close"].where(out["close"].gt(0)) - 1.0
    ) * 10_000.0
    out.loc[~valid, RAW_FEATURES] = np.nan

    for column in RAW_FEATURES:
        grouped = out.groupby("symbol", sort=False)[column]
        prior_mean = grouped.transform(lambda values: values.shift(1).rolling(60, min_periods=20).mean())
        prior_std = grouped.transform(lambda values: values.shift(1).rolling(60, min_periods=20).std())
        out[f"{column}_z60"] = (out[column] - prior_mean) / prior_std.where(prior_std.gt(1e-12))
        out[f"{column}_xs_rank"] = out.groupby("date")[column].rank(pct=True)
    return out


def summarize_coverage(pool: pd.DataFrame, features: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Measure total and yearly causal coverage before any performance metric."""
    marker = features[["date", "symbol", "quote_valid", "quote_near_close_15m"]]
    merged = pool[["date", "symbol"]].merge(marker, on=["date", "symbol"], how="left")
    merged[["quote_valid", "quote_near_close_15m"]] = merged[
        ["quote_valid", "quote_near_close_15m"]
    ].fillna(0)
    merged["year"] = pd.to_datetime(merged["date"]).dt.year
    rows = []
    for year, group in [("ALL", merged), *list(merged.groupby("year"))]:
        rows.append({
            "year": str(year),
            "pool_rows": int(len(group)),
            "valid_quote_rows": int(group["quote_valid"].sum()),
            "near_close_15m_rows": int(group["quote_near_close_15m"].sum()),
            "valid_quote_coverage": float(group["quote_valid"].mean()) if len(group) else 0.0,
            "near_close_15m_coverage": float(group["quote_near_close_15m"].mean()) if len(group) else 0.0,
        })
    coverage = pd.DataFrame(rows)
    overall = coverage.iloc[0].to_dict() if not coverage.empty else {}
    return coverage, overall


def evaluate_gates(diagnostics: pd.DataFrame, coverage: pd.DataFrame) -> dict[str, Any]:
    """Pre-fixed discovery gates; passing authorizes validation, not production."""
    yearly = coverage[coverage["year"] != "ALL"]
    coverage_overall = float(coverage.iloc[0]["valid_quote_coverage"]) if not coverage.empty else 0.0
    coverage_min_year = float(yearly["valid_quote_coverage"].min()) if not yearly.empty else 0.0
    stable = diagnostics[
        (diagnostics["stabilite_signes_folds"] == "OUI")
        & (diagnostics["n_ic_folds"] >= 3)
        & (diagnostics["IC_decile"].abs() >= 0.02)
        & ((diagnostics["AUC_direction"] - 0.5).abs() >= 0.015)
    ] if not diagnostics.empty else diagnostics
    # Raw/cross-sectional quoted depth is primarily a liquidity/size control.
    # It may not count as microstructure alpha unless its within-symbol dynamic
    # z-score survives. Bid depth share, size imbalance and microprice are one
    # algebraic family and therefore count only once.
    def _family(feature: str) -> str | None:
        if feature.startswith("log_quoted_depth_usd"):
            return "depth_dynamic" if feature.endswith("_z60") else None
        if feature.startswith(("size_imbalance", "bid_depth_share", "microprice_minus_mid_bps")):
            return "book_imbalance"
        if feature.startswith("spread_bps"):
            return "spread"
        if feature.startswith("quote_mid_minus_close_bps"):
            return "quote_close_dislocation"
        if feature.startswith("quote_age_seconds"):
            return "quote_recency"
        return None

    stable = stable.copy()
    if not stable.empty:
        stable["independent_family"] = stable["feature"].map(_family)
        stable = stable.dropna(subset=["independent_family"])
    families = sorted(set(stable.get("independent_family", pd.Series(dtype=str))))
    return {
        "coverage_overall_ge_60pct": coverage_overall >= 0.60,
        "coverage_each_year_ge_40pct": coverage_min_year >= 0.40,
        "independent_directional_families_ge_2": len(families) >= 2,
        "stable_directional_features": stable["feature"].tolist() if not stable.empty else [],
        "stable_directional_families": families,
        "discovery_pass": bool(
            coverage_overall >= 0.60
            and coverage_min_year >= 0.40
            and len(families) >= 2
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit microstructure closing quote dans Oracle TOP20")
    parser.add_argument("--batch-id", default=None)
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2025-12-31")
    parser.add_argument("--horizon", type=int, default=20)
    parser.add_argument("--pool-pct", type=float, default=0.20)
    parser.add_argument("--oracle-run", default=None)
    parser.add_argument("--labels-parquet", type=Path, default=None)
    parser.add_argument("--oracle-pool-parquet", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--top-n", type=int, default=12)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    batch_id = args.batch_id or resolve_global_direction_batch_id()
    if not batch_id:
        raise SystemExit("Aucun batch_id résolu.")
    engine = get_sqlalchemy_engine()
    if args.labels_parquet is not None:
        label_symbols = pd.read_parquet(args.labels_parquet, columns=["symbol"])
        symbols = sorted(label_symbols["symbol"].dropna().astype(str).str.upper().unique())
    else:
        symbols = get_universe_symbols(engine, batch_id, args.horizon)
    pool = assemble_pool(
        engine, batch_id, start_date=args.start_date, end_date=args.end_date,
        horizon=args.horizon, pool_pct=args.pool_pct, oracle_run=args.oracle_run,
        labels_parquet=args.labels_parquet,
        oracle_pool_parquet=args.oracle_pool_parquet,
    )
    if pool.empty:
        raise SystemExit("Pool Oracle vide ou labels qualité non reconstruits.")
    raw = load_closing_quotes(engine, symbols, args.start_date, args.end_date)
    features = derive_closing_quote_features(raw)
    coverage, overall = summarize_coverage(pool, features)
    merged = pool.merge(features, on=["date", "symbol"], how="left")
    diagnostics = analyze_features(merged, FEATURE_COLUMNS)
    feature_coverage = {
        column: float(merged[column].notna().mean())
        for column in FEATURE_COLUMNS if column in merged
    }
    gates = evaluate_gates(diagnostics, coverage)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    output = args.output_dir or Path("artifacts/research/microstructure_directional") / f"closing-quote-{timestamp}-{batch_id[-6:]}"
    output.mkdir(parents=True, exist_ok=True)
    diagnostics.to_csv(output / "feature_diagnostics.csv", index=False)
    coverage.to_csv(output / "coverage_by_year.csv", index=False)
    report = {
        "status": "complete",
        "experiment": "closing_quote_microstructure",
        "batch_id": batch_id,
        "window": {"start": args.start_date, "end": args.end_date},
        "horizon": args.horizon,
        "pool_pct": args.pool_pct,
        "source": "stock_quote_snapshots / Alpaca IEX",
        "labels_source": str(args.labels_parquet) if args.labels_parquet else "database",
        "oracle_pool_source": str(args.oracle_pool_parquet) if args.oracle_pool_parquet else "OOF artifact resolver",
        "decision_cutoff": "16:00 America/New_York on J",
        "earliest_entry": "J+1",
        "pool_rows": int(len(pool)),
        "pool_dates": int(pool["date"].nunique()),
        "quote_rows_loaded": int(len(raw)),
        "coverage_overall": overall,
        "feature_coverage": feature_coverage,
        "gates": gates,
        "limitations": [
            "one last IEX quote per day, not NBBO/SIP",
            "no trades, aggressor side, order book, premarket or opening range",
            "diagnostic discovery only; no model promotion or backtest authorization",
        ],
    }
    (output / "report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    rendered = format_report(diagnostics, top_n=args.top_n)
    (output / "report.txt").write_text(rendered, encoding="utf-8")
    print(f"output={output}")
    print(json.dumps(gates, indent=2))
    print(rendered)


if __name__ == "__main__":
    main()
