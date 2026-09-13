"""E16: reconstruct a point-in-time tradable universe and replay E12/E15.

Research-only module.  It never writes ``tradable_universe_*`` and never
changes serving/backtesting.  The primary reconstruction deliberately uses
only facts observable from market bars at J.  Non-PIT current metadata is used
solely to classify the instrument (equity versus collective product), never to
infer historical tradability.
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
from sqlalchemy import text
from sqlalchemy.engine import Engine

from common.instrument_policy import excluded_collective_instrument_reason
from database.connection import get_sqlalchemy_engine
from modelFactory.data_loader import load_universe_bars
from modelFactory.oracle_lifecycle_structural_audit import (
    CONTRACTS,
    E15Config,
    _period_delta,
    build_contract_outcomes,
    paired_delta,
    portfolio_delta,
    schedule_contract_capacity,
    semester_comparison,
    summarize_contract,
)
from modelFactory.oracle_monetization_bridge import (
    E12Config,
    build_fixed_h20_events,
    deduplicate_non_overlapping,
    filter_by_membership,
    replay_lifecycle_with_dynamic_capacity,
    select_with_capacity,
    summarize_returns,
)
from modelFactory.oracle_rolling_lifecycle import prepare_bars

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class E16Config:
    min_history_sessions: int = 252
    min_close: float = 10.0
    min_avg_volume_20d: float = 50_000.0
    min_adv_usd_20d: float = 10_000_000.0
    max_positions: int = 8
    bootstrap_samples: int = 2_000
    confirmation_start: str = "2023-01-01"

    def __post_init__(self) -> None:
        if self.min_history_sessions < 20:
            raise ValueError("min_history_sessions doit être >= 20.")
        if min(self.min_close, self.min_avg_volume_20d, self.min_adv_usd_20d) <= 0:
            raise ValueError("Les seuils de liquidité E16 doivent être positifs.")


def load_instrument_reference(engine: Engine, symbols: list[str]) -> pd.DataFrame:
    if not symbols:
        return pd.DataFrame(columns=["symbol", "company_name", "asset_class"])
    chunks: list[pd.DataFrame] = []
    for offset in range(0, len(symbols), 500):
        chunk = symbols[offset : offset + 500]
        params = {f"s{i}": symbol for i, symbol in enumerate(chunk)}
        placeholders = ",".join(f":s{i}" for i in range(len(chunk)))
        with engine.connect() as connection:
            chunks.append(pd.read_sql(text(
                "SELECT symbol, company_name, asset_class FROM stock_metadata "
                f"WHERE symbol IN ({placeholders})"
            ), connection, params=params))
    return pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame()


def classify_instruments(metadata: pd.DataFrame) -> pd.DataFrame:
    """Build a conservative static instrument-identity reference.

    ``asset_class`` and company names have no historical ``available_at`` in
    the current schema.  Consequently this layer is disclosed as static and
    cannot by itself earn the strict-PIT label.
    """
    if metadata.empty:
        return pd.DataFrame(columns=["symbol", "instrument_eligible", "instrument_reason"])
    frame = metadata.copy()
    frame["symbol"] = frame["symbol"].astype(str).str.strip().str.upper()

    def reason(row: pd.Series) -> str:
        named = excluded_collective_instrument_reason(row.get("company_name"))
        if named:
            return named
        asset_class = str(row.get("asset_class") or "").strip().lower()
        if asset_class and asset_class != "us_equity":
            return f"excluded_asset_class_{asset_class}"
        return "eligible_equity"

    frame["instrument_reason"] = frame.apply(reason, axis=1)
    frame["instrument_eligible"] = frame["instrument_reason"].eq("eligible_equity")
    return frame[["symbol", "instrument_eligible", "instrument_reason"]].drop_duplicates("symbol")


def reconstruct_bar_pit_panel(
    bars: pd.DataFrame,
    event_keys: pd.DataFrame,
    instruments: pd.DataFrame,
    config: E16Config,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Reconstruct eligibility using trailing data only, then restrict to events."""
    required = {"symbol", "date", "close", "volume"}
    if missing := required - set(bars.columns):
        raise ValueError(f"Barres incomplètes pour E16: {sorted(missing)}")
    keys = event_keys[["date", "symbol"]].copy()
    keys["date"] = pd.to_datetime(keys["date"], errors="coerce").dt.normalize()
    keys["symbol"] = keys["symbol"].astype(str).str.strip().str.upper()
    keys = keys.dropna().drop_duplicates()

    panel = bars.copy()
    panel["date"] = pd.to_datetime(panel["date"], errors="coerce").dt.normalize()
    panel["symbol"] = panel["symbol"].astype(str).str.strip().str.upper()
    panel["close_pit"] = pd.to_numeric(
        panel.get("adj_close", panel["close"]), errors="coerce"
    ).fillna(pd.to_numeric(panel["close"], errors="coerce"))
    panel["volume_pit"] = pd.to_numeric(panel["volume"], errors="coerce")
    filled = panel.get("is_filled", pd.Series(False, index=panel.index))
    panel["valid_bar"] = (
        panel["close_pit"].gt(0)
        & panel["volume_pit"].gt(0)
        & ~filled.fillna(False).astype(bool)
    )
    panel = panel.sort_values(["symbol", "date"]).drop_duplicates(
        ["symbol", "date"], keep="last"
    )
    grouped = panel.groupby("symbol", sort=False)
    panel["history_sessions"] = grouped["valid_bar"].cumsum()
    valid_volume = panel["volume_pit"].where(panel["valid_bar"])
    valid_dollar_volume = (panel["close_pit"] * panel["volume_pit"]).where(panel["valid_bar"])
    panel["avg_volume_20d"] = valid_volume.groupby(panel["symbol"]).transform(
        lambda values: values.rolling(20, min_periods=20).mean()
    )
    panel["adv_usd_20d"] = valid_dollar_volume.groupby(panel["symbol"]).transform(
        lambda values: values.rolling(20, min_periods=20).mean()
    )
    panel = keys.merge(
        panel[[
            "date", "symbol", "valid_bar", "history_sessions", "close_pit",
            "avg_volume_20d", "adv_usd_20d",
        ]], on=["date", "symbol"], how="left", validate="one_to_one",
    )
    panel = panel.merge(instruments, on="symbol", how="left", validate="many_to_one")
    panel["instrument_eligible"] = panel["instrument_eligible"].fillna(False).astype(bool)
    panel["instrument_reason"] = panel["instrument_reason"].fillna("instrument_metadata_missing")
    checks = {
        "bar_exact_j": panel["valid_bar"].fillna(False),
        "history": panel["history_sessions"].ge(config.min_history_sessions),
        "price": panel["close_pit"].ge(config.min_close),
        "volume20": panel["avg_volume_20d"].ge(config.min_avg_volume_20d),
        "adv20": panel["adv_usd_20d"].ge(config.min_adv_usd_20d),
        "instrument": panel["instrument_eligible"],
    }
    eligible = pd.Series(True, index=panel.index)
    reason = pd.Series("tradable_bar_pit", index=panel.index, dtype="object")
    ordered = (
        ("bar_exact_j", "bar_missing_or_invalid"),
        ("history", "insufficient_history"),
        ("price", "price_below_minimum"),
        ("volume20", "volume20_below_minimum"),
        ("adv20", "adv20_below_minimum"),
        ("instrument", "instrument_ineligible"),
    )
    for key, rejection in ordered:
        failed = eligible & ~checks[key].fillna(False)
        reason.loc[failed] = rejection
        eligible &= checks[key].fillna(False)
    panel["is_tradable"] = eligible
    panel["reason"] = reason
    membership = panel.loc[panel["is_tradable"], ["date", "symbol"]].copy()
    date_has_observation = panel.groupby("date")["valid_bar"].any()
    diagnostics = {
        "event_rows": int(len(panel)),
        "event_rows_evaluable": int(panel["valid_bar"].fillna(False).sum()),
        "event_evaluable_ratio": float(panel["valid_bar"].fillna(False).mean()),
        "event_rows_tradable": int(panel["is_tradable"].sum()),
        "event_tradable_ratio": float(panel["is_tradable"].mean()),
        "requested_dates": int(panel["date"].nunique()),
        "covered_dates": int(date_has_observation.sum()),
        "session_coverage_ratio": float(date_has_observation.mean()),
        "tradable_dates": int(membership["date"].nunique()),
        "tradable_symbols": int(membership["symbol"].nunique()),
        "rejection_reasons": panel.loc[~panel["is_tradable"], "reason"].value_counts().to_dict(),
        "instrument_reasons": panel["instrument_reason"].value_counts().to_dict(),
        "no_post_j_data": True,
    }
    return membership, panel, diagnostics


def audit_legacy_snapshots(engine: Engine, start: pd.Timestamp, end: pd.Timestamp) -> dict[str, Any]:
    query = text("""
        SELECT r.data_quality_grade, r.is_canonical, r.snapshot_date,
               r.universe_run_id, r.rows_expected, r.rows_written,
               h.history_days, h.bars_available, h.close_price, h.adv_usd,
               h.spread_bps, h.market_cap, h.atr_pct_20, h.earnings_blackout
        FROM tradable_universe_runs r
        JOIN tradable_universe_history h ON h.universe_run_id=r.universe_run_id
        WHERE r.status='completed' AND r.rows_expected=r.rows_written
          AND r.snapshot_date BETWEEN :start AND :end
    """)
    with engine.connect() as connection:
        frame = pd.read_sql(query, connection, params={"start": start.date(), "end": end.date()})
    if frame.empty:
        return {"rows": 0, "strict_contract_reconstructable": False}
    full = frame[frame["data_quality_grade"].astype(str).str.lower().eq("full")]
    canonical_full = full[full["is_canonical"].astype(bool)]
    fields = [
        "history_days", "bars_available", "close_price", "adv_usd",
        "spread_bps", "market_cap", "atr_pct_20", "earnings_blackout",
    ]
    return {
        "rows": int(len(frame)),
        "full_dates_any_canonical_state": int(full["snapshot_date"].nunique()),
        "full_dates_currently_canonical": int(canonical_full["snapshot_date"].nunique()),
        "full_rows": int(len(full)),
        "full_field_coverage": {
            field: float(full[field].notna().mean()) if len(full) else 0.0 for field in fields
        },
        "strict_contract_reconstructable": bool(
            len(full) and all(full[field].notna().all() for field in fields)
        ),
        "finding": "degraded publications superseded many immutable full runs; legacy full rows also lack current mandatory evidence fields",
    }


def _e12_replay(
    events: pd.DataFrame, membership: pd.DataFrame, prepared: pd.DataFrame, config: E16Config,
) -> tuple[dict[str, Any], pd.DataFrame]:
    lifecycle_config = E12Config(
        max_positions=config.max_positions, bootstrap_samples=config.bootstrap_samples
    )
    eligible = filter_by_membership(events, membership)
    fixed = select_with_capacity(eligible, lifecycle_config, policy="oracle_score")
    lifecycle, rejected = replay_lifecycle_with_dynamic_capacity(
        eligible, prepared, lifecycle_config, policy="oracle_score"
    )
    return {
        "eligible_non_overlapping_events": int(len(eligible)),
        "fixed_h20_capacity8": summarize_returns(fixed, config=lifecycle_config),
        "prod_lifecycle_dynamic_capacity8": summarize_returns(lifecycle, config=lifecycle_config),
        "prod_lifecycle_rejections": int(len(rejected)),
    }, lifecycle


def _e15_replay(
    events: pd.DataFrame, membership: pd.DataFrame, prepared: pd.DataFrame, config: E16Config,
) -> tuple[dict[str, Any], dict[str, pd.DataFrame]]:
    lifecycle_config = E12Config(
        max_positions=config.max_positions, bootstrap_samples=config.bootstrap_samples
    )
    audit_config = E15Config(
        max_positions=config.max_positions,
        bootstrap_samples=config.bootstrap_samples,
        confirmation_start=config.confirmation_start,
    )
    eligible = filter_by_membership(events, membership)
    outcomes, rejected = build_contract_outcomes(eligible, prepared, CONTRACTS, lifecycle_config)
    portfolios = {
        contract.name: schedule_contract_capacity(outcomes[contract.name], config.max_positions)
        for contract in CONTRACTS
    }
    baseline_events = outcomes["prod"]
    baseline_portfolio = portfolios["prod"]
    reports: dict[str, Any] = {}
    for contract in CONTRACTS:
        name = contract.name
        panel = outcomes[name]
        portfolio = portfolios[name]
        reports[name] = {
            "contract": asdict(contract),
            "event_summary": summarize_contract(panel, audit_config),
            "portfolio_summary": summarize_contract(portfolio, audit_config),
            "paired_event_delta": paired_delta(baseline_events, panel, audit_config),
            "portfolio_delta": portfolio_delta(baseline_portfolio, portfolio, audit_config),
            "semester_stability": semester_comparison(baseline_portfolio, portfolio),
            "confirmation_daily_delta": _period_delta(
                baseline_portfolio, portfolio, start=config.confirmation_start
            ),
        }
    return {"entry_rejections": int(len(rejected)), "contracts": reports}, portfolios


def run(*, oracle_gate_path: Path, output_root: Path, config: E16Config) -> Path:
    if oracle_gate_path.name != "_oracle_oof_gate.parquet" or not oracle_gate_path.is_file():
        raise ValueError("E16 exige _oracle_oof_gate.parquet.")
    oracle = pd.read_parquet(oracle_gate_path)
    eligible_oracle = oracle[
        oracle["directional_oracle_eligible"].fillna(False)
        & oracle["directional_oracle_oof_available"].fillna(False)
    ].copy()
    eligible_oracle["date"] = pd.to_datetime(eligible_oracle["date"]).dt.normalize()
    eligible_oracle["symbol"] = eligible_oracle["symbol"].astype(str).str.upper()
    symbols = sorted(eligible_oracle["symbol"].unique())
    engine = get_sqlalchemy_engine()
    start = eligible_oracle["date"].min() - pd.offsets.BDay(config.min_history_sessions + 40)
    end = eligible_oracle["date"].max() + pd.offsets.BDay(25)
    bars = load_universe_bars(engine, symbols, start_date=start.date(), end_date=end.date())
    instruments = classify_instruments(load_instrument_reference(engine, symbols))
    membership, audit_panel, reconstruction = reconstruct_bar_pit_panel(
        bars, eligible_oracle[["date", "symbol"]], instruments, config
    )
    lifecycle_config = E12Config(
        max_positions=config.max_positions, bootstrap_samples=config.bootstrap_samples
    )
    events = deduplicate_non_overlapping(
        build_fixed_h20_events(oracle, bars, lifecycle_config)
    )
    prepared = prepare_bars(bars)
    e12, _ = _e12_replay(events, membership, prepared, config)
    e15, portfolios = _e15_replay(events, membership, prepared, config)
    legacy = audit_legacy_snapshots(
        engine, eligible_oracle["date"].min(), eligible_oracle["date"].max()
    )
    no_tp = e15["contracts"]["prod_no_tp"]
    prod = e15["contracts"]["prod"]
    no_tp_portfolio = no_tp["portfolio_summary"]
    prod_portfolio = prod["portfolio_summary"]
    gates = {
        "session_coverage_at_least_95pct": reconstruction["session_coverage_ratio"] >= 0.95,
        "oracle_events_evaluable_at_least_90pct": reconstruction["event_evaluable_ratio"] >= 0.90,
        "non_equity_policy_applied": True,
        "no_post_j_data": reconstruction["no_post_j_data"],
        "strict_prod_contract_reconstructable": legacy["strict_contract_reconstructable"],
        "prod_no_tp_positive_since_2023": no_tp["confirmation_daily_delta"] > 0,
        "prod_no_tp_portfolio_ci95_above_zero": no_tp["portfolio_delta"]["ci95_low"] > 0,
        "prod_no_tp_q05_not_worse": no_tp_portfolio.get("q05", -np.inf) >= prod_portfolio.get("q05", np.inf),
        "prod_no_tp_q01_not_worse": no_tp_portfolio.get("q01", -np.inf) >= prod_portfolio.get("q01", np.inf),
    }
    gates["promotion_authorized"] = all(gates.values())
    verdict = "GO_EXACT_BACKTEST" if gates["promotion_authorized"] else "NO_GO_OR_BLOCKED"

    run_id = f"oracle-tradable-pit-reconstruction-{datetime.now(UTC):%Y%m%d%H%M%S}"
    output = output_root / run_id
    output.mkdir(parents=True, exist_ok=False)
    membership.to_parquet(output / "bar_pit_membership.parquet", index=False)
    audit_panel.to_parquet(output / "bar_pit_event_audit.parquet", index=False)
    for name, portfolio in portfolios.items():
        portfolio.to_csv(output / f"portfolio_{name}.csv", index=False)
    report = {
        "schema_version": 1,
        "experiment": "E16_TRADABLE_UNIVERSE_PIT_RECONSTRUCTION",
        "status": "complete",
        "research_only": True,
        "generated_at": datetime.now(UTC).isoformat(),
        "run_id": run_id,
        "input": str(oracle_gate_path),
        "config": asdict(config),
        "contracts": {
            "bar_pit": "exact J bar; trailing history/volume/ADV; no synthetic bar; static instrument identity",
            "not_imputed": ["historical market cap", "spread when unavailable", "earnings when unavailable"],
            "warning": "bar_pit is a certified market-data sensitivity, not the complete production tradability contract",
        },
        "reconstruction": reconstruction,
        "legacy_snapshot_audit": legacy,
        "e12_replay": e12,
        "e15_replay": e15,
        "gates": gates,
        "verdict": verdict,
    }
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    LOGGER.info("E16 terminé: %s verdict=%s", output, verdict)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--oracle-gate", type=Path, required=True)
    parser.add_argument(
        "--output-root", type=Path,
        default=Path("artifacts/research/oracle_tradable_pit_reconstruction"),
    )
    parser.add_argument("--bootstrap-samples", type=int, default=2_000)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    output = run(
        oracle_gate_path=args.oracle_gate,
        output_root=args.output_root,
        config=E16Config(bootstrap_samples=args.bootstrap_samples),
    )
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    print(f"E16 terminé: {output}")
    print(report["verdict"])


if __name__ == "__main__":
    main()
