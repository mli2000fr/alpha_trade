"""E20-A — audit PIT de disponibilité de la fenêtre d'ouverture après Oracle.

Ce module est strictement read-only : il ne construit ni signal directionnel,
ni modèle, ni ligne de serving. Il mesure si la matière nécessaire à E20-B/C
existe réellement sur les événements Oracle TOP20 OOF.
"""
from __future__ import annotations

import argparse
import json
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from database.connection import get_sqlalchemy_engine

LOGGER = logging.getLogger(__name__)
NY = ZoneInfo("America/New_York")


@dataclass(frozen=True, slots=True)
class E20AConfig:
    provider: str = "alpaca"
    feed: str = "sip"
    adjustment_mode: str = "raw"
    minimum_rule_dates: int = 126
    minimum_rule_events: int = 5_000
    minimum_model_dates: int = 378
    minimum_model_events: int = 20_000
    minimum_semesters: int = 4
    minimum_any_open_coverage: float = 0.70
    minimum_30m_coverage: float = 0.60
    minimum_30m_bars: int = 24
    maximum_invalid_availability_ratio: float = 0.0


def load_oracle_events(path: Path) -> pd.DataFrame:
    columns = [
        "date", "symbol", "directional_oracle_proba_extreme",
        "directional_oracle_extreme_pct", "directional_oracle_eligible",
        "directional_oracle_oof_available",
    ]
    frame = pd.read_parquet(path, columns=columns)
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["symbol"] = frame["symbol"].astype(str).str.strip().str.upper()
    frame = frame[
        frame["directional_oracle_eligible"].fillna(False)
        & frame["directional_oracle_oof_available"].fillna(False)
    ].dropna(subset=["date", "symbol"])
    return frame.sort_values(["date", "symbol"]).drop_duplicates(
        ["date", "symbol"], keep="last"
    ).reset_index(drop=True)


def attach_next_oracle_session(events: pd.DataFrame) -> pd.DataFrame:
    """Mappe J vers la prochaine séance observée dans l'artefact OOF."""
    result = events.copy()
    sessions = pd.Series(sorted(result["date"].dropna().unique()))
    next_by_date = dict(zip(sessions.iloc[:-1], sessions.iloc[1:], strict=True))
    result["target_session"] = result["date"].map(next_by_date)
    return result.dropna(subset=["target_session"]).reset_index(drop=True)


def table_summary(engine: Engine) -> dict[str, Any]:
    inspector = inspect(engine)
    if not inspector.has_table("stock_opening_window_bars"):
        return {"exists": False, "rows": 0, "symbols": 0, "session_dates": 0}
    with engine.connect() as connection:
        row = connection.execute(text("""
            SELECT COUNT(*) AS rows_count, COUNT(DISTINCT symbol) AS symbols,
                   COUNT(DISTINCT DATE(bar_timestamp)) AS session_dates,
                   MIN(bar_timestamp) AS min_bar_timestamp,
                   MAX(bar_timestamp) AS max_bar_timestamp,
                   SUM(available_at < bar_timestamp) AS invalid_availability_rows
            FROM stock_opening_window_bars
        """)).mappings().one()
        providers = [dict(item) for item in connection.execute(text("""
            SELECT provider, feed, adjustment_mode, session_name,
                   COUNT(*) AS rows_count, COUNT(DISTINCT symbol) AS symbols,
                   COUNT(DISTINCT DATE(bar_timestamp)) AS session_dates,
                   MIN(bar_timestamp) AS min_bar_timestamp,
                   MAX(bar_timestamp) AS max_bar_timestamp
            FROM stock_opening_window_bars
            GROUP BY provider, feed, adjustment_mode, session_name
            ORDER BY rows_count DESC
        """)).mappings()]
    return {"exists": True, **dict(row), "by_contract": providers}


def load_opening_rows(
    engine: Engine, *, start_session: pd.Timestamp, end_session: pd.Timestamp,
    config: E20AConfig,
) -> pd.DataFrame:
    start_local = pd.Timestamp(start_session).tz_localize(NY)
    end_local = (pd.Timestamp(end_session) + pd.Timedelta(days=1)).tz_localize(NY)
    params = {
        "provider": config.provider, "feed": config.feed,
        "adjustment": config.adjustment_mode,
        "start": start_local.tz_convert("UTC").tz_localize(None).to_pydatetime(),
        "end": end_local.tz_convert("UTC").tz_localize(None).to_pydatetime(),
    }
    query = text("""
        SELECT symbol, bar_timestamp, available_at, session_name,
               minute_volume, trade_count, open, high, low, close, vwap
        FROM stock_opening_window_bars
        WHERE provider=:provider AND feed=:feed AND adjustment_mode=:adjustment
          AND bar_timestamp >= :start AND bar_timestamp < :end
        ORDER BY bar_timestamp, symbol
    """)
    with engine.connect() as connection:
        frame = pd.read_sql(query, connection, params=params)
    if frame.empty:
        return frame
    frame["symbol"] = frame["symbol"].astype(str).str.strip().str.upper()
    utc = pd.to_datetime(frame["bar_timestamp"], errors="coerce", utc=True)
    local = utc.dt.tz_convert(NY)
    frame["session_date"] = local.dt.tz_localize(None).dt.normalize()
    frame["minute_of_day"] = local.dt.hour * 60 + local.dt.minute
    frame["bar_timestamp"] = utc.dt.tz_localize(None)
    frame["available_at"] = pd.to_datetime(frame["available_at"], errors="coerce")
    frame["invalid_availability"] = frame["available_at"].lt(frame["bar_timestamp"])
    return frame


def build_symbol_session_coverage(rows: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "session_date", "symbol", "bars_total", "bars_pre", "bars_open",
        "bars_15m", "bars_30m", "bars_60m", "has_pre", "has_open",
        "has_15m", "has_30m", "has_60m", "volume_total", "trades_total",
        "invalid_availability_rows",
    ]
    if rows.empty:
        return pd.DataFrame(columns=columns)
    work = rows.copy()
    minute = work["minute_of_day"]
    work["is_pre"] = minute.lt(570)
    work["is_open"] = minute.between(570, 630, inclusive="both")
    work["is_15m"] = minute.between(570, 584, inclusive="both")
    work["is_30m"] = minute.between(570, 599, inclusive="both")
    work["is_60m"] = minute.between(570, 629, inclusive="both")
    for name in ("minute_volume", "trade_count"):
        work[name] = pd.to_numeric(work[name], errors="coerce").fillna(0)
    grouped = work.groupby(["session_date", "symbol"], as_index=False).agg(
        bars_total=("bar_timestamp", "nunique"),
        bars_pre=("is_pre", "sum"), bars_open=("is_open", "sum"),
        bars_15m=("is_15m", "sum"), bars_30m=("is_30m", "sum"),
        bars_60m=("is_60m", "sum"), volume_total=("minute_volume", "sum"),
        trades_total=("trade_count", "sum"),
        invalid_availability_rows=("invalid_availability", "sum"),
    )
    for suffix in ("pre", "open", "15m", "30m", "60m"):
        grouped[f"has_{suffix}"] = grouped[f"bars_{suffix}"].gt(0)
    return grouped[columns]


def _semester(values: pd.Series) -> pd.Series:
    dates = pd.to_datetime(values)
    return dates.dt.year.astype(str) + "H" + np.where(dates.dt.month.le(6), "1", "2")


def build_report(
    *, events: pd.DataFrame, coverage: pd.DataFrame,
    global_summary: dict[str, Any], recent_runs: list[dict[str, Any]],
    oracle_path: Path, config: E20AConfig,
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    joined = events.merge(
        coverage, left_on=["target_session", "symbol"],
        right_on=["session_date", "symbol"], how="left", validate="one_to_one",
    )
    boolean_columns = ["has_pre", "has_open", "has_15m", "has_30m", "has_60m"]
    for column in boolean_columns:
        # ``eq(True)`` transforme explicitement les valeurs absentes de la
        # jointure en False sans dépendre du downcast implicite de pandas.
        joined[column] = joined[column].eq(True)
    for column in ["bars_total", "bars_pre", "bars_open", "bars_15m", "bars_30m",
                   "bars_60m", "volume_total", "trades_total",
                   "invalid_availability_rows"]:
        joined[column] = pd.to_numeric(joined[column], errors="coerce").fillna(0)
    joined["complete_30m"] = joined["bars_30m"].ge(config.minimum_30m_bars)
    joined["semester"] = _semester(joined["target_session"])
    observed = joined[joined["has_open"]]
    invalid_rows = float(coverage["invalid_availability_rows"].sum()) if len(coverage) else 0.0
    total_rows = float(coverage["bars_total"].sum()) if len(coverage) else 0.0
    invalid_ratio = invalid_rows / total_rows if total_rows else 0.0
    ratios = {
        column: float(joined[column].mean()) if len(joined) else 0.0
        for column in [*boolean_columns, "complete_30m"]
    }
    overlap_dates = int(observed["target_session"].nunique()) if len(observed) else 0
    overlap_events = int(len(observed))
    overlap_semesters = int(observed["semester"].nunique()) if len(observed) else 0
    rules_gates = {
        "minimum_dates": overlap_dates >= config.minimum_rule_dates,
        "minimum_events": overlap_events >= config.minimum_rule_events,
        "open_coverage": ratios["has_open"] >= config.minimum_any_open_coverage,
        "complete_30m_coverage": ratios["complete_30m"] >= config.minimum_30m_coverage,
        "pit_availability": invalid_ratio <= config.maximum_invalid_availability_ratio,
        "contract_present": any(
            str(row.get("provider")) == config.provider
            and str(row.get("feed")) == config.feed
            and str(row.get("adjustment_mode")) == config.adjustment_mode
            for row in global_summary.get("by_contract", [])
        ),
    }
    model_gates = {
        **rules_gates,
        "minimum_dates": overlap_dates >= config.minimum_model_dates,
        "minimum_events": overlap_events >= config.minimum_model_events,
        "minimum_semesters": overlap_semesters >= config.minimum_semesters,
    }
    rules_ready, model_ready = all(rules_gates.values()), all(model_gates.values())
    if model_ready:
        verdict = "DATA_READY_FOR_RULES_AND_MODEL"
    elif rules_ready:
        verdict = "DATA_READY_FOR_RULES_ONLY"
    elif int(global_summary.get("rows_count") or 0) == 0:
        verdict = "BLOCKED_NO_OPENING_WINDOW_DATA"
    elif overlap_events == 0:
        verdict = "BLOCKED_NO_ORACLE_OVERLAP"
    else:
        verdict = "BLOCKED_INSUFFICIENT_COVERAGE"
    by_session = joined.groupby("target_session", as_index=False).agg(
        oracle_events=("symbol", "size"), covered_open=("has_open", "sum"),
        covered_30m=("complete_30m", "sum"), covered_pre=("has_pre", "sum"),
        median_30m_bars=("bars_30m", "median"),
    ) if len(joined) else pd.DataFrame()
    if len(by_session):
        by_session["open_coverage"] = by_session["covered_open"] / by_session["oracle_events"]
        by_session["complete_30m_coverage"] = by_session["covered_30m"] / by_session["oracle_events"]
    by_symbol = joined.groupby("symbol", as_index=False).agg(
        oracle_events=("target_session", "size"), covered_open=("has_open", "sum"),
        covered_30m=("complete_30m", "sum"), covered_pre=("has_pre", "sum"),
    ) if len(joined) else pd.DataFrame()
    if len(by_symbol):
        by_symbol["open_coverage"] = by_symbol["covered_open"] / by_symbol["oracle_events"]
        by_symbol["complete_30m_coverage"] = by_symbol["covered_30m"] / by_symbol["oracle_events"]
    report = {
        "schema_version": 1,
        "experiment": "E20A_ORACLE_OPENING_WINDOW_PIT_AVAILABILITY",
        "status": "complete", "research_only": True,
        "production_change": False, "directional_policy_tested": False,
        "model_trained": False, "generated_at": datetime.now(UTC).isoformat(),
        "config": asdict(config),
        "oracle": {
            "artifact": str(oracle_path), "top20_events": int(len(events)),
            "signal_dates": int(events["date"].nunique()) if len(events) else 0,
            "symbols": int(events["symbol"].nunique()) if len(events) else 0,
            "min_signal_date": events["date"].min() if len(events) else None,
            "max_signal_date": events["date"].max() if len(events) else None,
            "min_target_session": events["target_session"].min() if len(events) else None,
            "max_target_session": events["target_session"].max() if len(events) else None,
        },
        "opening_window_table": global_summary,
        "recent_collection_runs": recent_runs,
        "oracle_overlap": {
            "events_with_any_open": overlap_events, "dates_with_any_open": overlap_dates,
            "semesters_with_any_open": overlap_semesters,
            "coverage_ratios": ratios,
            "invalid_pit_availability_rows": int(invalid_rows),
            "invalid_pit_availability_ratio": invalid_ratio,
        },
        "gates": {"rules": rules_gates, "model": model_gates},
        "rules_experiment_authorized": rules_ready,
        "model_experiment_authorized": model_ready,
        "verdict": verdict,
        "next_action": (
            "ouvrir E20-B règles simples pré-enregistrées"
            if rules_ready else
            "obtenir des fenêtres d'ouverture sur les mêmes dates que des scores "
            "Oracle OOF/shadow (backfill historique validé ou collecte prospective "
            "conjointe); ne pas ouvrir E20-B/C"
        ),
    }
    return report, by_session, by_symbol


def load_recent_runs(engine: Engine) -> list[dict[str, Any]]:
    if not inspect(engine).has_table("pit_collection_runs"):
        return []
    with engine.connect() as connection:
        return [dict(row) for row in connection.execute(text("""
            SELECT run_id, status, started_at, finished_at, requested_count,
                   received_count, persisted_count, failed_count, warning_count,
                   error_message, details_json
            FROM pit_collection_runs
            WHERE batch_name='oracle_opening_window_sync'
            ORDER BY started_at DESC LIMIT 10
        """)).mappings()]


def run(*, oracle_path: Path, output_root: Path, config: E20AConfig) -> Path:
    events = attach_next_oracle_session(load_oracle_events(oracle_path))
    engine = get_sqlalchemy_engine()
    global_summary = table_summary(engine)
    if events.empty or not global_summary.get("rows_count"):
        rows = pd.DataFrame()
    else:
        rows = load_opening_rows(
            engine, start_session=events["target_session"].min(),
            end_session=events["target_session"].max(), config=config,
        )
    coverage = build_symbol_session_coverage(rows)
    report, by_session, by_symbol = build_report(
        events=events, coverage=coverage, global_summary=global_summary,
        recent_runs=load_recent_runs(engine), oracle_path=oracle_path, config=config,
    )
    output = output_root / f"e20a-opening-availability-{datetime.now(UTC):%Y%m%d%H%M%S}"
    output.mkdir(parents=True, exist_ok=False)
    coverage.to_parquet(output / "opening_symbol_session_coverage.parquet", index=False)
    by_session.to_csv(output / "oracle_coverage_by_session.csv", index=False)
    by_symbol.to_csv(output / "oracle_coverage_by_symbol.csv", index=False)
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    LOGGER.info("E20-A terminé: %s verdict=%s", output, report["verdict"])
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--oracle-path", type=Path,
        default=Path(
            "artifacts/models/model-factory-20260909051302-323684/"
            "_oracle_oof_gate.parquet"
        ),
    )
    parser.add_argument(
        "--output-root", type=Path,
        default=Path("artifacts/research/oracle_opening_window_availability"),
    )
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    output = run(
        oracle_path=args.oracle_path, output_root=args.output_root, config=E20AConfig(),
    )
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    print(f"E20-A terminé: {output}")
    print(report["verdict"])


if __name__ == "__main__":
    main()
