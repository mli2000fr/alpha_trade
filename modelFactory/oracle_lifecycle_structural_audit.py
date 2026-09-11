"""E15: audit structurel research-only du lifecycle Oracle LONG H20.

Le plan factoriel est figé : quatre règles de trailing croisées avec TP PROD
activé ou absent. Aucun paramètre n'est optimisé sur les résultats.
"""
from __future__ import annotations

import argparse
import json
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd

from backtesting.microstructure import resolve_intrabar_exit, should_skip_entry_for_gap
from database.connection import get_sqlalchemy_engine
from modelFactory.data_loader import load_universe_bars
from modelFactory.multi_horizon_oracle_rolling import block_bootstrap_mean
from modelFactory.oracle_monetization_bridge import (
    E12Config,
    build_fixed_h20_events,
    deduplicate_non_overlapping,
    filter_by_membership,
    load_exact_tradable_membership,
)
from modelFactory.oracle_rolling_lifecycle import prepare_bars

LOGGER = logging.getLogger(__name__)
TrailingMode = Literal["prod_session2", "after_0_5r", "after_1r", "none"]


@dataclass(frozen=True, slots=True)
class LifecycleContract:
    name: str
    trailing_mode: TrailingMode
    tp_enabled: bool


CONTRACTS = (
    LifecycleContract("prod", "prod_session2", True),
    LifecycleContract("trail_after_0_5r_tp", "after_0_5r", True),
    LifecycleContract("trail_after_1r_tp", "after_1r", True),
    LifecycleContract("no_trailing_tp", "none", True),
    LifecycleContract("prod_no_tp", "prod_session2", False),
    LifecycleContract("trail_after_0_5r_no_tp", "after_0_5r", False),
    LifecycleContract("trail_after_1r_no_tp", "after_1r", False),
    LifecycleContract("no_trailing_no_tp", "none", False),
)


@dataclass(frozen=True, slots=True)
class E15Config:
    max_positions: int = 8
    primary_contract: str = "trail_after_0_5r_tp"
    bootstrap_samples: int = 2_000
    development_end: str = "2022-12-31"
    confirmation_start: str = "2023-01-01"

    def __post_init__(self) -> None:
        names = {contract.name for contract in CONTRACTS}
        if self.primary_contract not in names:
            raise ValueError("Contrat primaire E15 inconnu.")
        if self.max_positions < 1:
            raise ValueError("Capacité E15 invalide.")


def _activation_threshold_r(mode: TrailingMode) -> float | None:
    if mode == "after_0_5r":
        return 0.5
    if mode == "after_1r":
        return 1.0
    return None


def simulate_contract_long(
    symbol_bars: pd.DataFrame, *, signal_date: pd.Timestamp,
    contract: LifecycleContract, config: E12Config,
) -> dict[str, Any] | None:
    """Rejoue un contrat sans utiliser le high/low courant pour l'activer."""
    bars = symbol_bars.reset_index(drop=True)
    if bars.empty or "date" not in bars:
        return None
    matches = bars.index[bars["date"].gt(pd.Timestamp(signal_date).normalize())]
    if len(matches) < 1:
        return None
    entry_index = int(matches[0])
    if entry_index == 0 or entry_index + config.horizon >= len(bars):
        return None
    entry = bars.iloc[entry_index]
    entry_price = float(entry["px_open"])
    previous_close = float(entry["previous_close"])
    atr = float(entry["entry_atr20"])
    if not all(np.isfinite(value) and value > 0 for value in (entry_price, previous_close, atr)):
        return None
    if should_skip_entry_for_gap(
        previous_close, entry_price, max_gap_pct=config.max_entry_gap_pct
    ):
        return {
            "entry_date": pd.Timestamp(entry["date"]), "entry_price": entry_price,
            "exit_reason": "entry_gap_rejected",
        }
    atr_pct = atr / previous_close
    initial_risk = entry_price * config.initial_stop_atr_multiple * atr_pct
    initial_stop = entry_price - initial_risk
    trail_pct = config.trailing_atr_multiple * atr_pct
    take_profit = (
        entry_price * (1.0 + min(config.tp_atr_multiple * atr_pct, config.tp_max_pct))
        if contract.tp_enabled else np.inf
    )
    activation_r = _activation_threshold_r(contract.trailing_mode)
    previous_peak = entry_price
    mfe, mae = 0.0, 0.0
    activation_date: pd.Timestamp | None = None
    for holding_session in range(1, config.horizon + 1):
        row = bars.iloc[entry_index + holding_session - 1]
        if contract.trailing_mode == "prod_session2":
            trailing_active = holding_session >= 2
        elif contract.trailing_mode == "none":
            trailing_active = False
        else:
            trailing_active = (
                holding_session >= 2
                and previous_peak >= entry_price + float(activation_r) * initial_risk
            )
        if trailing_active and activation_date is None:
            activation_date = pd.Timestamp(row["date"])
        trailing_stop = previous_peak * (1.0 - trail_pct) if trailing_active else -np.inf
        resolution = resolve_intrabar_exit(
            day_high=float(row["px_high"]), day_low=float(row["px_low"]),
            take_profit_price=float(take_profit), trailing_stop_price=trailing_stop,
            initial_stop_price=None if trailing_active else initial_stop,
            priority="conservative", side="buy",
        )
        mfe = max(mfe, float(row["px_high"]) / entry_price - 1.0)
        mae = min(mae, float(row["px_low"]) / entry_price - 1.0)
        if resolution.triggered:
            exit_price = float(resolution.exit_price)
            return {
                "entry_date": pd.Timestamp(entry["date"]), "entry_price": entry_price,
                "exit_date": pd.Timestamp(row["date"]), "exit_price": exit_price,
                "exit_reason": resolution.exit_reason, "holding_sessions": holding_session,
                "activation_date": activation_date,
                "mfe": mfe, "mae": mae,
                "gross_return": exit_price / entry_price - 1.0,
                "net_return": exit_price / entry_price - 1.0 - config.round_trip_cost,
            }
        previous_peak = max(previous_peak, float(row["px_high"]))
    terminal = bars.iloc[entry_index + config.horizon]
    exit_price = float(terminal["px_open"])
    return {
        "entry_date": pd.Timestamp(entry["date"]), "entry_price": entry_price,
        "exit_date": pd.Timestamp(terminal["date"]), "exit_price": exit_price,
        "exit_reason": "fixed_h20", "holding_sessions": config.horizon,
        "activation_date": activation_date, "mfe": mfe, "mae": mae,
        "gross_return": exit_price / entry_price - 1.0,
        "net_return": exit_price / entry_price - 1.0 - config.round_trip_cost,
    }


def build_contract_outcomes(
    events: pd.DataFrame, prepared_bars: pd.DataFrame,
    contracts: tuple[LifecycleContract, ...], config: E12Config,
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    bars_by_symbol = dict(tuple(prepared_bars.groupby("symbol", sort=False)))
    outputs: dict[str, list[dict[str, Any]]] = {contract.name: [] for contract in contracts}
    rejected: list[dict[str, Any]] = []
    for candidate in events.itertuples(index=False):
        symbol_bars = bars_by_symbol.get(str(candidate.symbol), pd.DataFrame())
        identity = {
            "date": pd.Timestamp(candidate.date), "symbol": str(candidate.symbol),
            "fold": str(candidate.fold), "semester": str(candidate.semester),
            "directional_oracle_proba_extreme": float(
                candidate.directional_oracle_proba_extreme
            ),
            "fixed_h20_net_return": float(candidate.net_return),
        }
        for contract in contracts:
            outcome = simulate_contract_long(
                symbol_bars, signal_date=pd.Timestamp(candidate.date),
                contract=contract, config=config,
            )
            if outcome is None or outcome.get("exit_reason") == "entry_gap_rejected":
                if contract.name == "prod":
                    rejected.append({
                        **identity,
                        "reason": "missing_path" if outcome is None else "entry_gap_rejected",
                    })
                continue
            outputs[contract.name].append({**identity, **outcome})
    return {name: pd.DataFrame(rows) for name, rows in outputs.items()}, pd.DataFrame(rejected)


def schedule_contract_capacity(panel: pd.DataFrame, max_positions: int) -> pd.DataFrame:
    active: dict[str, pd.Timestamp] = {}
    selected: list[int] = []
    for _, group in panel.groupby("date", sort=True):
        entry_date = pd.Timestamp(group["entry_date"].min())
        active = {symbol: end for symbol, end in active.items() if end >= entry_date}
        slots = max_positions - len(active)
        if slots <= 0:
            continue
        candidates = group[~group["symbol"].isin(active)].sort_values(
            ["directional_oracle_proba_extreme", "symbol"], ascending=[False, True]
        )
        for row in candidates.head(slots).itertuples():
            selected.append(int(row.Index))
            active[str(row.symbol)] = pd.Timestamp(row.exit_date)
    return panel.loc[selected].sort_values(["entry_date", "symbol"]).reset_index(drop=True)


def summarize_contract(frame: pd.DataFrame, config: E15Config) -> dict[str, Any]:
    if frame.empty:
        return {"trades": 0}
    daily = frame.groupby("date")["net_return"].mean().sort_index()
    boot = E12Config(bootstrap_samples=config.bootstrap_samples).bootstrap_config()
    ci = block_bootstrap_mean(daily, boot)
    return {
        "trades": int(len(frame)), "dates": int(frame["date"].nunique()),
        "symbols": int(frame["symbol"].nunique()),
        "mean_net_return": float(frame["net_return"].mean()),
        "median_net_return": float(frame["net_return"].median()),
        "win_rate": float(frame["net_return"].gt(0).mean()),
        "q05": float(frame["net_return"].quantile(0.05)),
        "q01": float(frame["net_return"].quantile(0.01)),
        "mean_holding_sessions": float(frame["holding_sessions"].mean()),
        "daily_mean": float(daily.mean()), "daily_ci95_low": ci[0],
        "daily_ci95_high": ci[1],
        "exit_reasons": frame["exit_reason"].value_counts().to_dict(),
    }


def paired_delta(
    baseline: pd.DataFrame, candidate: pd.DataFrame, config: E15Config,
) -> dict[str, Any]:
    paired = baseline[["date", "symbol", "net_return"]].merge(
        candidate[["date", "symbol", "net_return"]], on=["date", "symbol"],
        suffixes=("_baseline", "_candidate"), validate="one_to_one",
    )
    paired["delta"] = paired["net_return_candidate"] - paired["net_return_baseline"]
    daily = paired.groupby("date")["delta"].mean().sort_index()
    ci = block_bootstrap_mean(
        daily, E12Config(bootstrap_samples=config.bootstrap_samples).bootstrap_config()
    )
    return {
        "paired_events": int(len(paired)), "mean_event_delta": float(paired["delta"].mean()),
        "daily_delta": float(daily.mean()), "ci95_low": ci[0], "ci95_high": ci[1],
    }


def portfolio_delta(
    baseline: pd.DataFrame, candidate: pd.DataFrame, config: E15Config,
) -> dict[str, float]:
    left = baseline.groupby("date")["net_return"].mean()
    right = candidate.groupby("date")["net_return"].mean()
    dates = left.index.union(right.index)
    delta = right.reindex(dates, fill_value=0.0) - left.reindex(dates, fill_value=0.0)
    ci = block_bootstrap_mean(
        delta.sort_index(),
        E12Config(bootstrap_samples=config.bootstrap_samples).bootstrap_config(),
    )
    return {"daily_delta": float(delta.mean()), "ci95_low": ci[0], "ci95_high": ci[1]}


def semester_comparison(
    baseline: pd.DataFrame, candidate: pd.DataFrame,
) -> list[dict[str, Any]]:
    rows = []
    semesters = sorted(set(baseline["semester"]) | set(candidate["semester"]))
    for semester in semesters:
        before = baseline[baseline["semester"].eq(semester)]["net_return"]
        after = candidate[candidate["semester"].eq(semester)]["net_return"]
        rows.append({
            "semester": semester, "baseline_trades": int(len(before)),
            "candidate_trades": int(len(after)),
            "baseline_mean": float(before.mean()) if len(before) else None,
            "candidate_mean": float(after.mean()) if len(after) else None,
            "lift": float(after.mean() - before.mean()) if len(before) and len(after) else None,
        })
    return rows


def _period_delta(
    baseline: pd.DataFrame, candidate: pd.DataFrame, *, start: str | None = None,
    end: str | None = None,
) -> float:
    left, right = baseline, candidate
    if start is not None:
        left = left[left["date"].ge(pd.Timestamp(start))]
        right = right[right["date"].ge(pd.Timestamp(start))]
    if end is not None:
        left = left[left["date"].le(pd.Timestamp(end))]
        right = right[right["date"].le(pd.Timestamp(end))]
    left_daily = left.groupby("date")["net_return"].mean()
    right_daily = right.groupby("date")["net_return"].mean()
    dates = left_daily.index.union(right_daily.index)
    if dates.empty:
        return float("nan")
    return float(
        (right_daily.reindex(dates, fill_value=0.0) - left_daily.reindex(dates, fill_value=0.0)).mean()
    )


def run(*, oracle_gate_path: Path, output_root: Path, config: E15Config) -> Path:
    lifecycle_config = E12Config(bootstrap_samples=config.bootstrap_samples)
    oracle = pd.read_parquet(oracle_gate_path)
    eligible = oracle[
        oracle["directional_oracle_eligible"].fillna(False)
        & oracle["directional_oracle_oof_available"].fillna(False)
    ]
    symbols = sorted(eligible["symbol"].astype(str).str.upper().unique())
    start = pd.Timestamp(eligible["date"].min()) - pd.offsets.BDay(40)
    end = pd.Timestamp(eligible["date"].max()) + pd.offsets.BDay(25)
    engine = get_sqlalchemy_engine()
    bars = load_universe_bars(engine, symbols, start_date=start.date(), end_date=end.date())
    events = deduplicate_non_overlapping(
        build_fixed_h20_events(oracle, bars, lifecycle_config)
    )
    prepared = prepare_bars(bars)
    outcomes, rejected = build_contract_outcomes(
        events, prepared, CONTRACTS, lifecycle_config
    )
    baseline_events = outcomes["prod"]
    baseline_portfolio = schedule_contract_capacity(baseline_events, config.max_positions)
    reports: dict[str, Any] = {}
    portfolios: dict[str, pd.DataFrame] = {}
    for contract in CONTRACTS:
        panel = outcomes[contract.name]
        portfolio = schedule_contract_capacity(panel, config.max_positions)
        portfolios[contract.name] = portfolio
        reports[contract.name] = {
            "contract": asdict(contract),
            "event_summary": summarize_contract(panel, config),
            "portfolio_summary": summarize_contract(portfolio, config),
            "paired_event_delta": paired_delta(baseline_events, panel, config),
            "portfolio_delta": portfolio_delta(baseline_portfolio, portfolio, config),
            "semester_stability": semester_comparison(baseline_portfolio, portfolio),
            "development_daily_delta": _period_delta(
                baseline_portfolio, portfolio, end=config.development_end
            ),
            "confirmation_daily_delta": _period_delta(
                baseline_portfolio, portfolio, start=config.confirmation_start
            ),
        }

    full_members, full_diag = load_exact_tradable_membership(
        engine, start_date=events["date"].min(), end_date=events["date"].max(),
        preset=lifecycle_config.capital_preset_key, quality="full",
    )
    degraded_members, degraded_diag = load_exact_tradable_membership(
        engine, start_date=events["date"].min(), end_date=events["date"].max(),
        preset=lifecycle_config.capital_preset_key, quality="any",
    )
    degraded_reports: dict[str, Any] = {}
    for name in (contract.name for contract in CONTRACTS):
        panel = filter_by_membership(outcomes[name], degraded_members)
        portfolio = schedule_contract_capacity(panel, config.max_positions) if len(panel) else panel
        degraded_reports[name] = summarize_contract(portfolio, config)

    primary = reports[config.primary_contract]
    primary_semesters = [
        row for row in primary["semester_stability"] if row["lift"] is not None
    ]
    baseline_summary = reports["prod"]["portfolio_summary"]
    primary_summary = primary["portfolio_summary"]
    gates = {
        "paired_event_delta_positive": primary["paired_event_delta"]["daily_delta"] > 0,
        "paired_event_ci95_above_zero": primary["paired_event_delta"]["ci95_low"] > 0,
        "portfolio_delta_positive": primary["portfolio_delta"]["daily_delta"] > 0,
        "portfolio_ci95_above_zero": primary["portfolio_delta"]["ci95_low"] > 0,
        "q05_not_worse": primary_summary["q05"] >= baseline_summary["q05"],
        "q01_not_worse": primary_summary["q01"] >= baseline_summary["q01"],
        "confirmation_delta_positive": primary["confirmation_daily_delta"] > 0,
        "positive_lift_semesters_70pct": (
            bool(primary_semesters)
            and sum(row["lift"] > 0 for row in primary_semesters) / len(primary_semesters) >= 0.70
        ),
        "strict_tradable_pit_available": full_diag["dates"] == events["date"].nunique(),
    }
    gates["promotion_authorized"] = all(gates.values())
    verdict = "GO_EXACT_BACKTEST" if gates["promotion_authorized"] else "NO_GO_OR_BLOCKED"

    run_id = f"oracle-lifecycle-audit-{datetime.now(UTC):%Y%m%d%H%M%S}"
    output = output_root / run_id
    output.mkdir(parents=True, exist_ok=False)
    for name, panel in outcomes.items():
        panel.to_parquet(output / f"events_{name}.parquet", index=False)
    for name, portfolio in portfolios.items():
        portfolio.to_csv(output / f"portfolio_{name}.csv", index=False)
    rejected.to_csv(output / "entry_rejections.csv", index=False)
    report = {
        "schema_version": 1, "experiment": "E15_ORACLE_LIFECYCLE_STRUCTURAL_AUDIT",
        "status": "complete", "research_only": True,
        "generated_at": datetime.now(UTC).isoformat(), "run_id": run_id,
        "input": str(oracle_gate_path), "config": asdict(config),
        "contract": {
            "side": "LONG only", "entry": "adjusted open J+1",
            "horizon": 20, "costs_round_trip_bps": 6,
            "stop": "2.5 ATR at close J", "trailing_distance": "2.5 ATR risk-based",
            "tp": "min(3 ATR, 7%) when enabled", "intrabar": "conservative",
            "activation": "previous completed-session peak only",
            "primary": config.primary_contract,
            "diagnostics_only": [
                contract.name for contract in CONTRACTS
                if contract.name not in {"prod", config.primary_contract}
            ],
        },
        "population": {
            "deduplicated_events": int(len(events)),
            "prod_outcomes": int(len(baseline_events)),
            "entry_rejections": int(len(rejected)),
        },
        "contracts": reports,
        "tradable_pit": {
            "full": full_diag, "degraded": degraded_diag,
            "degraded_portfolios": degraded_reports,
        },
        "gates": gates, "verdict": verdict,
    }
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    LOGGER.info("E15 terminé: %s verdict=%s", output, verdict)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--oracle-gate", type=Path, required=True)
    parser.add_argument(
        "--output-root", type=Path,
        default=Path("artifacts/research/oracle_lifecycle_structural_audit"),
    )
    parser.add_argument("--bootstrap-samples", type=int, default=2_000)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    output = run(
        oracle_gate_path=args.oracle_gate, output_root=args.output_root,
        config=E15Config(bootstrap_samples=args.bootstrap_samples),
    )
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    print(f"E15 terminé: {output}")
    print(report["verdict"])


if __name__ == "__main__":
    main()
