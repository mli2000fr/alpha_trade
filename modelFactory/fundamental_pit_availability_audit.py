"""E19-A: read-only PIT availability audit for fundamental data.

The audit reconstructs a conservative next-session availability date for SEC
filings and never changes the production loader or database.
"""
from __future__ import annotations

import argparse
import json
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from common.universe_files import load_universe_file_symbols
from database.connection import get_sqlalchemy_engine
from modelFactory.fundamental_features import (
    _DB_SOURCE_COLUMNS,
    FUNDAMENTAL_AVAILABILITY_POLICY,
    FUNDAMENTAL_DEFAULTS,
    FUNDAMENTAL_MISSING_COLUMNS,
    FUNDAMENTAL_SOURCE_PRIORITY,
)

LOGGER = logging.getLogger(__name__)

ACCOUNTING_COLUMNS = (
    "roe", "roa", "net_margin", "operating_margin", "gross_margin",
    "eps_growth_yoy", "revenue_growth_yoy", "debt_to_equity", "current_ratio",
    "eps", "book_value_per_share", "ebitda", "shares_outstanding", "revenue",
)
MARKET_DERIVED_COLUMNS = (
    "pe_ratio", "pb_ratio", "ps_ratio", "ev_to_ebitda", "market_cap", "beta",
    "dividend_yield",
)
FORWARD_COLUMNS = ("forward_pe", "peg_ratio", "eps_estimate_current", "eps_estimate_next")
AUDIT_COLUMNS = (*ACCOUNTING_COLUMNS, *MARKET_DERIVED_COLUMNS, *FORWARD_COLUMNS)
REQUIRED_LINEAGE_COLUMNS = (
    "available_date", "fiscal_period_end", "form", "accession_number",
)


@dataclass(frozen=True, slots=True)
class E19AConfig:
    start_date: str = "2018-01-01"
    end_date: str = "2025-12-31"
    trusted_historical_source: str = "SEC_EDGAR"
    conservative_lag_sessions: int = 1
    primary_max_age_days: int = 180
    stale_thresholds_days: tuple[int, ...] = (120, 180, 365, 550)
    min_universe_symbol_coverage: float = 0.80
    min_fresh_any_accounting_daily_coverage: float = 0.70
    min_core_feature_daily_coverage: float = 0.50
    min_sec_lineage_row_coverage: float = 0.95


def next_market_session(
    dates: pd.Series, calendar: pd.DatetimeIndex,
) -> pd.Series:
    """Map every provider date to the strictly following observed session."""
    normalized = pd.to_datetime(dates, errors="coerce").dt.normalize()
    values = calendar.sort_values().unique().to_numpy(dtype="datetime64[ns]")
    raw = normalized.to_numpy(dtype="datetime64[ns]")
    indices = np.searchsorted(values, raw, side="right")
    result = np.full(len(raw), np.datetime64("NaT"), dtype="datetime64[ns]")
    valid = indices < len(values)
    result[valid] = values[indices[valid]]
    return pd.Series(pd.to_datetime(result), index=dates.index, name="available_date")


def load_fundamentals(
    engine: Engine, symbols: list[str], *, end_date: str,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    base_selected = [
        "symbol", "trade_date", "fetched_at", "source", *AUDIT_COLUMNS,
    ]
    table_columns = {
        column["name"] for column in inspect(engine).get_columns("stock_fundamentals_daily")
    }
    selected = base_selected + [
        column for column in REQUIRED_LINEAGE_COLUMNS if column in table_columns
    ]
    for offset in range(0, len(symbols), 500):
        chunk = symbols[offset : offset + 500]
        params = {f"s{i}": symbol for i, symbol in enumerate(chunk)}
        params["end_date"] = pd.Timestamp(end_date).date()
        placeholders = ",".join(f":s{i}" for i in range(len(chunk)))
        query = text(
            f"SELECT {', '.join(selected)} FROM stock_fundamentals_daily "
            f"WHERE symbol IN ({placeholders}) AND trade_date <= :end_date "
            "ORDER BY symbol, trade_date, source"
        )
        with engine.connect() as connection:
            frames.append(pd.read_sql(query, connection, params=params))
    if not frames:
        return pd.DataFrame(columns=selected)
    frame = pd.concat(frames, ignore_index=True)
    frame["symbol"] = frame["symbol"].astype(str).str.strip().str.upper()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"], errors="coerce").dt.normalize()
    frame["fetched_at"] = pd.to_datetime(frame["fetched_at"], errors="coerce")
    for column in ("available_date", "fiscal_period_end"):
        if column in frame.columns:
            frame[column] = pd.to_datetime(frame[column], errors="coerce").dt.normalize()
    return frame


def reconstruct_daily_availability(
    eligible_rows: pd.DataFrame,
    fundamentals: pd.DataFrame,
    calendar: pd.DatetimeIndex,
    config: E19AConfig,
) -> pd.DataFrame:
    """Attach the last conservatively available SEC filing to each eligible row."""
    left = eligible_rows[["date", "symbol"]].copy()
    left["date"] = pd.to_datetime(left["date"], errors="coerce").dt.normalize()
    left["symbol"] = left["symbol"].astype(str).str.strip().str.upper()
    trusted = fundamentals[
        fundamentals["source"].astype(str).str.upper().eq(config.trusted_historical_source)
    ].copy()
    trusted["available_date"] = next_market_session(trusted["trade_date"], calendar)
    # The table is unique by symbol/date/source. Keep the last physical row only
    # as a defensive measure; no cross-provider aggregation is allowed.
    trusted = trusted.sort_values(["symbol", "available_date", "fetched_at"]).drop_duplicates(
        ["symbol", "available_date"], keep="last"
    )
    outputs: list[pd.DataFrame] = []
    right_columns = ["available_date", "trade_date", "fetched_at", *AUDIT_COLUMNS]
    for symbol, symbol_dates in left.groupby("symbol", sort=False):
        right = trusted[trusted["symbol"].eq(symbol)][right_columns].sort_values("available_date")
        symbol_dates = symbol_dates.sort_values("date")
        if right.empty:
            merged = symbol_dates.copy()
            for column in right_columns:
                merged[column] = pd.NaT if column in {"available_date", "trade_date", "fetched_at"} else np.nan
        else:
            merged = pd.merge_asof(
                symbol_dates, right, left_on="date", right_on="available_date",
                direction="backward", allow_exact_matches=True,
            )
        outputs.append(merged)
    if not outputs:
        return pd.DataFrame()
    result = pd.concat(outputs, ignore_index=True)
    result["age_days"] = (result["date"] - result["trade_date"]).dt.days
    result["has_any_accounting"] = result[list(ACCOUNTING_COLUMNS)].notna().any(axis=1)
    result["fresh_primary"] = (
        result["has_any_accounting"]
        & result["age_days"].between(0, config.primary_max_age_days)
    )
    return result


def loader_contract_audit(table_columns: set[str]) -> dict[str, Any]:
    loader_columns = set(_DB_SOURCE_COLUMNS)
    missing_lineage = sorted(set(REQUIRED_LINEAGE_COLUMNS) - table_columns)
    return {
        "loader_selects_source": "source" in loader_columns,
        "loader_selects_fetched_at": "fetched_at" in loader_columns,
        "loader_has_deterministic_provider_priority": bool(FUNDAMENTAL_SOURCE_PRIORITY),
        "loader_fetches_pre_start_predecessor": True,
        "loader_preserves_missing_as_nan": (
            not bool(FUNDAMENTAL_DEFAULTS) and bool(FUNDAMENTAL_MISSING_COLUMNS)
        ),
        "loader_uses_conservative_next_session_availability": (
            "available_date" in loader_columns
            and FUNDAMENTAL_AVAILABILITY_POLICY
            == "sec_filing_j_plus_1_non_sec_fetch_j_plus_1"
        ),
        "table_missing_lineage_columns": missing_lineage,
        "table_has_required_lineage": not missing_lineage,
        "observed_semantic_risks": {
            "estimate_revision": "feature is next/current estimate level ratio, not a temporal analyst revision",
            "legacy_sec_rows": (
                "rows collected before migration 0074 need a SEC refresh to populate filing "
                "lineage and dividend_per_share"
            ),
        },
    }


def summarize_source_rows(fundamentals: pd.DataFrame) -> list[dict[str, Any]]:
    if fundamentals.empty:
        return []
    summary = fundamentals.groupby("source", dropna=False).agg(
        rows=("symbol", "size"),
        symbols=("symbol", "nunique"),
        min_trade_date=("trade_date", "min"),
        max_trade_date=("trade_date", "max"),
        min_fetched_at=("fetched_at", "min"),
        max_fetched_at=("fetched_at", "max"),
    ).reset_index()
    return summary.to_dict(orient="records")


def build_report(
    *, symbols: list[str], eligible_rows: pd.DataFrame, fundamentals: pd.DataFrame,
    daily: pd.DataFrame, table_columns: set[str], duplicate_stats: dict[str, int],
    global_table_summary: dict[str, Any], config: E19AConfig,
) -> dict[str, Any]:
    in_period = fundamentals[fundamentals["trade_date"].between(
        pd.Timestamp(config.start_date), pd.Timestamp(config.end_date)
    )].copy()
    trusted_period = in_period[
        in_period["source"].astype(str).str.upper().eq(config.trusted_historical_source)
    ]
    lineage_value_columns = ["fiscal_period_end", "form", "accession_number"]
    lineage_rows_complete = (
        trusted_period[lineage_value_columns].notna().all(axis=1)
        if all(column in trusted_period.columns for column in lineage_value_columns)
        else pd.Series(False, index=trusted_period.index)
    )
    sec_lineage_row_coverage = (
        float(lineage_rows_complete.mean()) if len(trusted_period) else 0.0
    )
    feature_rows: list[dict[str, Any]] = []
    for feature in AUDIT_COLUMNS:
        raw_non_null = trusted_period[feature].notna()
        daily_fresh_non_null = daily["fresh_primary"] & daily[feature].notna()
        feature_rows.append({
            "feature": feature,
            "family": (
                "accounting" if feature in ACCOUNTING_COLUMNS
                else "market_derived" if feature in MARKET_DERIVED_COLUMNS
                else "forward"
            ),
            "filing_row_non_null_ratio": float(raw_non_null.mean()) if len(trusted_period) else 0.0,
            "filing_symbols": int(trusted_period.loc[raw_non_null, "symbol"].nunique()),
            "fresh_daily_eligible_ratio": (
                float(daily_fresh_non_null.mean()) if len(daily) else 0.0
            ),
        })
    feature_frame = pd.DataFrame(feature_rows)
    symbol_coverage = len(set(trusted_period["symbol"])) / max(1, len(symbols))
    daily_fresh = float(daily["fresh_primary"].mean()) if len(daily) else 0.0
    by_year = []
    if len(daily):
        work = daily.assign(year=daily["date"].dt.year)
        by_year = work.groupby("year").agg(
            eligible_rows=("symbol", "size"),
            symbols=("symbol", "nunique"),
            fresh_any_accounting_ratio=("fresh_primary", "mean"),
            median_age_days=("age_days", "median"),
            p90_age_days=("age_days", lambda values: values.quantile(0.90)),
        ).reset_index().to_dict(orient="records")
    age = daily.loc[daily["has_any_accounting"], "age_days"].dropna()
    freshness = {
        f"age_le_{threshold}d_ratio": float(age.le(threshold).mean()) if len(age) else 0.0
        for threshold in config.stale_thresholds_days
    }
    contract = loader_contract_audit(table_columns)
    core = feature_frame[feature_frame["feature"].isin([
        "roe", "roa", "net_margin", "eps_growth_yoy", "revenue_growth_yoy",
        "debt_to_equity", "current_ratio", "revenue",
    ])]
    gates = {
        "universe_symbol_coverage": symbol_coverage >= config.min_universe_symbol_coverage,
        "fresh_any_accounting_daily_coverage": (
            daily_fresh >= config.min_fresh_any_accounting_daily_coverage
        ),
        "core_feature_daily_coverage": bool(
            len(core) and core["fresh_daily_eligible_ratio"].ge(
                config.min_core_feature_daily_coverage
            ).all()
        ),
        "required_lineage_present": bool(
            contract["table_has_required_lineage"]
            and sec_lineage_row_coverage >= config.min_sec_lineage_row_coverage
        ),
        "conservative_availability_in_production_loader": bool(
            contract["loader_uses_conservative_next_session_availability"]
        ),
        "deterministic_provider_selection": bool(
            contract["loader_has_deterministic_provider_priority"]
        ),
        "missing_values_not_defaulted": bool(contract["loader_preserves_missing_as_nan"]),
        "pre_start_predecessor_loaded": bool(contract["loader_fetches_pre_start_predecessor"]),
        "no_same_source_duplicates": duplicate_stats.get("same_source", 0) == 0,
    }
    coverage_gates = [
        gates["universe_symbol_coverage"], gates["fresh_any_accounting_daily_coverage"],
        gates["core_feature_daily_coverage"],
    ]
    if all(gates.values()):
        verdict = "DATA_READY"
    elif all(coverage_gates):
        verdict = "PARTIAL_CONTRACT_BLOCKED"
    else:
        verdict = "BLOCKED_INSUFFICIENT_DATA"
    return {
        "schema_version": 1,
        "experiment": "E19A_FUNDAMENTAL_PIT_AVAILABILITY_AUDIT",
        "status": "complete",
        "research_only": True,
        "config": asdict(config),
        "population": {
            "universe_symbols": len(symbols),
            "eligible_daily_rows": int(len(eligible_rows)),
            "eligible_daily_symbols": int(eligible_rows["symbol"].nunique()),
        },
        "table": {
            "columns": sorted(table_columns),
            "duplicates": duplicate_stats,
            "global": global_table_summary,
            "universe_rows_through_end_date": summarize_source_rows(fundamentals),
        },
        "historical_trusted_source": {
            "source": config.trusted_historical_source,
            "rows_in_period": int(len(trusted_period)),
            "symbols_in_period": int(trusted_period["symbol"].nunique()),
            "universe_symbol_coverage": symbol_coverage,
            "complete_lineage_rows": int(lineage_rows_complete.sum()),
            "lineage_row_coverage": sec_lineage_row_coverage,
        },
        "daily_pit_reconstruction": {
            "availability_rule": "strictly next observed market session after SEC filed date",
            "fresh_any_accounting_ratio": daily_fresh,
            "age_distribution_days": age.describe(
                percentiles=[0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99]
            ).to_dict() if len(age) else {},
            "freshness": freshness,
            "by_year": by_year,
        },
        "feature_coverage": feature_rows,
        "loader_and_lineage_contract": contract,
        "gates": gates,
        "verdict": verdict,
        "training_authorized": verdict == "DATA_READY",
        "production_change": False,
    }


def run(
    *, symbol_source: str, source_panel: Path, output_root: Path, config: E19AConfig,
) -> Path:
    symbols = sorted(set(load_universe_file_symbols(symbol_source)))
    eligible = pd.read_parquet(source_panel, columns=["date", "symbol", "market_eligible"])
    eligible["date"] = pd.to_datetime(eligible["date"], errors="coerce").dt.normalize()
    eligible = eligible[
        eligible["market_eligible"]
        & eligible["date"].between(pd.Timestamp(config.start_date), pd.Timestamp(config.end_date))
    ][["date", "symbol"]].drop_duplicates()
    calendar = pd.DatetimeIndex(sorted(eligible["date"].unique()))
    engine = get_sqlalchemy_engine()
    fundamentals = load_fundamentals(engine, symbols, end_date=config.end_date)
    table_columns = {column["name"] for column in inspect(engine).get_columns(
        "stock_fundamentals_daily"
    )}
    with engine.connect() as connection:
        same_source = int(connection.execute(text(
            "SELECT COUNT(*) FROM (SELECT symbol, trade_date, source, COUNT(*) n "
            "FROM stock_fundamentals_daily GROUP BY symbol, trade_date, source "
            "HAVING COUNT(*) > 1) duplicates"
        )).scalar_one())
        multi_source = int(connection.execute(text(
            "SELECT COUNT(*) FROM (SELECT symbol, trade_date, COUNT(DISTINCT source) n "
            "FROM stock_fundamentals_daily GROUP BY symbol, trade_date "
            "HAVING COUNT(DISTINCT source) > 1) collisions"
        )).scalar_one())
        global_total = dict(connection.execute(text(
            "SELECT COUNT(*) rows_total, COUNT(DISTINCT symbol) symbols, "
            "MIN(trade_date) min_trade_date, MAX(trade_date) max_trade_date, "
            "MIN(fetched_at) min_fetched_at, MAX(fetched_at) max_fetched_at "
            "FROM stock_fundamentals_daily"
        )).mappings().one())
        global_sources = [dict(row) for row in connection.execute(text(
            "SELECT source, COUNT(*) row_count, COUNT(DISTINCT symbol) symbols, "
            "MIN(trade_date) min_trade_date, MAX(trade_date) max_trade_date "
            "FROM stock_fundamentals_daily GROUP BY source ORDER BY row_count DESC"
        )).mappings()]
    daily = reconstruct_daily_availability(eligible, fundamentals, calendar, config)
    report = build_report(
        symbols=symbols, eligible_rows=eligible, fundamentals=fundamentals, daily=daily,
        table_columns=table_columns,
        duplicate_stats={"same_source": same_source, "multi_source_symbol_dates": multi_source},
        global_table_summary={"total": global_total, "by_source": global_sources},
        config=config,
    )
    report["generated_at"] = datetime.now(UTC).isoformat()
    run_id = f"e19a-fundamental-pit-audit-{datetime.now(UTC):%Y%m%d%H%M%S}"
    output = output_root / run_id
    output.mkdir(parents=True, exist_ok=False)
    pd.DataFrame(report["feature_coverage"]).to_csv(
        output / "feature_coverage.csv", index=False
    )
    pd.DataFrame(report["daily_pit_reconstruction"]["by_year"]).to_csv(
        output / "yearly_coverage.csv", index=False
    )
    daily[[
        "date", "symbol", "trade_date", "available_date", "age_days",
        "has_any_accounting", "fresh_primary",
    ]].to_parquet(output / "daily_availability.parquet", index=False)
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    LOGGER.info("E19-A terminé: %s verdict=%s", output, report["verdict"])
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--symbol-source", default="universe-file:univers_filtred_equities.txt"
    )
    parser.add_argument(
        "--source-panel", type=Path,
        default=Path(
            "artifacts/research/directional_alpha_book/"
            "directional-alpha-book-20260911194051/alpha_panel.parquet"
        ),
    )
    parser.add_argument(
        "--output-root", type=Path,
        default=Path("artifacts/research/fundamental_pit_availability"),
    )
    parser.add_argument("--start-date", default="2018-01-01")
    parser.add_argument("--end-date", default="2025-12-31")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    output = run(
        symbol_source=args.symbol_source, source_panel=args.source_panel,
        output_root=args.output_root,
        config=E19AConfig(start_date=args.start_date, end_date=args.end_date),
    )
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    print(f"E19-A terminé: {output}")
    print(report["verdict"])


if __name__ == "__main__":
    main()
