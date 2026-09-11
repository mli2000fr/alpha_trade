"""E9-A: confirmation directionnelle causale après un signal Oracle Extreme."""
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

from database.connection import get_sqlalchemy_engine
from modelFactory.cross_sectional import _load_sector_mapping
from modelFactory.data_loader import load_benchmark_bars, load_universe_bars
from modelFactory.multi_horizon_oracle_rolling import RollingConfig, block_bootstrap_mean

LOGGER = logging.getLogger(__name__)
BASES = ("absolute", "spy_relative", "sector_relative")


@dataclass(frozen=True, slots=True)
class E9Config:
    delays: tuple[int, ...] = (1, 2, 3, 5)
    thresholds: tuple[float, ...] = (0.0, 0.0025, 0.005, 0.01, 0.02)
    default_threshold: float = 0.005
    minimum_training_events: int = 500
    minimum_training_coverage: float = 0.15
    minimum_policy_events: int = 500
    minimum_policy_coverage: float = 0.15
    commission_bps: float = 1.0
    slippage_bps: float = 2.0
    bootstrap_samples: int = 2_000
    bootstrap_block_sessions: int = 21
    bootstrap_seed: int = 20260911
    primary_delay: int = 2
    primary_basis: str = "absolute"

    def __post_init__(self) -> None:
        if not self.delays or min(self.delays) < 1:
            raise ValueError("Les délais doivent être positifs.")
        if not self.thresholds or min(self.thresholds) < 0:
            raise ValueError("Les seuils doivent être positifs ou nuls.")
        if self.primary_delay not in self.delays or self.primary_basis not in BASES:
            raise ValueError("Politique primaire absente du protocole.")
        if not 0 < self.minimum_training_coverage <= 1:
            raise ValueError("minimum_training_coverage invalide.")

    @property
    def round_trip_cost(self) -> float:
        return 2.0 * (self.commission_bps + self.slippage_bps) / 10_000.0


def prepare_price_panel(bars: pd.DataFrame, delays: tuple[int, ...]) -> pd.DataFrame:
    required = {"symbol", "date", "open", "close"}
    missing = required - set(bars.columns)
    if missing:
        raise ValueError(f"Barres incomplètes: {sorted(missing)}")
    frame = bars.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["symbol"] = frame["symbol"].astype(str).str.strip().str.upper()
    for column in ("open", "close", "adj_close"):
        if column in frame:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if "adj_close" in frame:
        factor = frame["adj_close"] / frame["close"].replace(0, np.nan)
        frame["px_close"] = frame["adj_close"].where(frame["adj_close"].gt(0), frame["close"])
        frame["px_open"] = (frame["open"] * factor).where(factor.gt(0), frame["open"])
    else:
        frame["px_close"], frame["px_open"] = frame["close"], frame["open"]
    frame = frame.dropna(subset=["date", "symbol", "px_open", "px_close"])
    frame = frame[frame["px_open"].gt(0) & frame["px_close"].gt(0)]
    frame = frame.sort_values(["symbol", "date"]).drop_duplicates(["symbol", "date"])
    grouped = frame.groupby("symbol", sort=False)
    frame["immediate_entry_open"] = grouped["px_open"].shift(-1)
    frame["terminal_exit_open"] = grouped["px_open"].shift(-21)
    frame["terminal_date"] = grouped["date"].shift(-21)
    for delay in delays:
        frame[f"reveal_date_d{delay}"] = grouped["date"].shift(-delay)
        frame[f"reveal_close_d{delay}"] = grouped["px_close"].shift(-delay)
        frame[f"delayed_entry_date_d{delay}"] = grouped["date"].shift(-(delay + 1))
        frame[f"delayed_entry_open_d{delay}"] = grouped["px_open"].shift(-(delay + 1))
        frame[f"signal_absolute_d{delay}"] = frame[f"reveal_close_d{delay}"] / frame["px_close"] - 1.0
    return frame.reset_index(drop=True)


def attach_confirmation_paths(oracle_events: pd.DataFrame, prices: pd.DataFrame,
                              benchmark_prices: pd.DataFrame, sector_map: dict[str, str],
                              config: E9Config) -> pd.DataFrame:
    required = {"date", "symbol", "mh0", "fold_h20"}
    missing = required - set(oracle_events.columns)
    if missing:
        raise ValueError(f"Artefact Oracle incomplet: {sorted(missing)}")
    events = oracle_events.loc[oracle_events["mh0"].fillna(False)].copy()
    events["date"] = pd.to_datetime(events["date"], errors="coerce").dt.normalize()
    events["symbol"] = events["symbol"].astype(str).str.upper()
    price_columns = ["date", "symbol", "px_close", "immediate_entry_open",
                     "terminal_exit_open", "terminal_date"]
    for delay in config.delays:
        price_columns += [f"reveal_date_d{delay}", f"reveal_close_d{delay}",
                          f"delayed_entry_date_d{delay}", f"delayed_entry_open_d{delay}",
                          f"signal_absolute_d{delay}"]
    # E9 recalcule tous les chemins avec une horloge unique depuis les barres.
    # Retirer les colonnes homonymes déjà présentes évite les suffixes pandas.
    events = events.drop(columns=[
        column for column in price_columns if column not in {"date", "symbol"}
    ], errors="ignore")
    events = events.merge(prices[price_columns], on=["date", "symbol"], how="left",
                          validate="one_to_one")
    benchmark = benchmark_prices[benchmark_prices["symbol"].eq("SPY")]
    benchmark_columns = ["date"] + [f"signal_absolute_d{d}" for d in config.delays]
    benchmark = benchmark[benchmark_columns].rename(columns={
        f"signal_absolute_d{d}": f"spy_signal_d{d}" for d in config.delays
    })
    events = events.merge(benchmark, on="date", how="left", validate="many_to_one")
    sector_source = prices[["date", "symbol"] + [f"signal_absolute_d{d}" for d in config.delays]].copy()
    sector_source["sector"] = sector_source["symbol"].map(sector_map)
    sector_medians = sector_source.dropna(subset=["sector"]).groupby(
        ["date", "sector"], as_index=False
    )[[f"signal_absolute_d{d}" for d in config.delays]].median().rename(columns={
        f"signal_absolute_d{d}": f"sector_signal_d{d}" for d in config.delays
    })
    events["sector"] = events["symbol"].map(sector_map)
    events = events.merge(sector_medians, on=["date", "sector"], how="left", validate="many_to_one")
    events["immediate_long_net"] = events["terminal_exit_open"] / events["immediate_entry_open"] - 1.0 - config.round_trip_cost
    for delay in config.delays:
        absolute = events[f"signal_absolute_d{delay}"]
        events[f"signal_spy_relative_d{delay}"] = absolute - events[f"spy_signal_d{delay}"]
        events[f"signal_sector_relative_d{delay}"] = absolute - events[f"sector_signal_d{delay}"]
        future = events["terminal_exit_open"] / events[f"delayed_entry_open_d{delay}"] - 1.0
        events[f"future_unsigned_d{delay}"] = future
        events[f"delayed_long_net_d{delay}"] = future - config.round_trip_cost
        events[f"perfect_direction_net_d{delay}"] = future.abs() - config.round_trip_cost
    return events.sort_values(["date", "symbol"]).reset_index(drop=True)


def _signal_column(basis: str, delay: int) -> str:
    if basis not in BASES:
        raise ValueError(f"Base inconnue: {basis}")
    return f"signal_{basis}_d{delay}"


def _policy_rows(frame: pd.DataFrame, *, basis: str, delay: int, threshold: float,
                 round_trip_cost: float) -> pd.DataFrame:
    signal_col = _signal_column(basis, delay)
    future_col = f"future_unsigned_d{delay}"
    part = frame.dropna(subset=[signal_col, future_col, f"delayed_entry_open_d{delay}",
                                "terminal_exit_open"]).copy()
    part = part[part[signal_col].abs().ge(threshold)]
    part["basis"], part["delay"], part["threshold"] = basis, delay, threshold
    part["direction"] = np.where(part[signal_col].gt(0), "LONG", "SHORT")
    part["directional_net"] = (
        np.where(part["direction"].eq("LONG"), part[future_col], -part[future_col])
        - round_trip_cost
    )
    return part


def select_threshold(history: pd.DataFrame, *, basis: str, delay: int,
                     config: E9Config) -> tuple[float, list[dict[str, Any]]]:
    signal_col = _signal_column(basis, delay)
    eligible = history.dropna(subset=[signal_col, f"future_unsigned_d{delay}"])
    diagnostics: list[dict[str, Any]] = []
    candidates: list[tuple[float, float]] = []
    for threshold in config.thresholds:
        rows = _policy_rows(eligible, basis=basis, delay=delay, threshold=threshold,
                            round_trip_cost=config.round_trip_cost)
        coverage = len(rows) / len(eligible) if len(eligible) else 0.0
        daily = rows.groupby("date")["directional_net"].mean()
        score = float(daily.mean()) if len(daily) else np.nan
        valid = len(rows) >= config.minimum_training_events and coverage >= config.minimum_training_coverage and np.isfinite(score)
        diagnostics.append({"threshold": threshold, "training_events": len(rows),
                            "training_coverage": coverage, "training_daily_mean": score,
                            "eligible": bool(valid)})
        if valid:
            candidates.append((score, threshold))
    if not candidates:
        return config.default_threshold, diagnostics
    candidates.sort(key=lambda item: (-item[0], item[1]))
    return candidates[0][1], diagnostics


def build_prequential_decisions(events: pd.DataFrame, config: E9Config) -> tuple[pd.DataFrame, pd.DataFrame]:
    fold_order = events.groupby("fold_h20")["date"].min().sort_values().index.astype(str).tolist()
    decisions, threshold_rows = [], []
    normalized_fold = events["fold_h20"].astype(str)
    for basis in BASES:
        for delay in config.delays:
            for fold_index, fold in enumerate(fold_order):
                test = events[normalized_fold.eq(fold)]
                history = events[normalized_fold.isin(set(fold_order[:fold_index]))]
                if len(history) < config.minimum_training_events:
                    threshold, diagnostics, source = config.default_threshold, [], "default_no_history"
                else:
                    threshold, diagnostics = select_threshold(history, basis=basis, delay=delay, config=config)
                    source = "prior_oof_folds"
                chosen = _policy_rows(test, basis=basis, delay=delay, threshold=threshold,
                                      round_trip_cost=config.round_trip_cost)
                chosen["evaluation_fold"], chosen["threshold_source"] = fold, source
                decisions.append(chosen)
                threshold_rows.append({"basis": basis, "delay": delay, "evaluation_fold": fold,
                                       "threshold": threshold, "threshold_source": source,
                                       "prior_folds": fold_index, "prior_events": len(history),
                                       "grid": diagnostics})
    return pd.concat(decisions, ignore_index=True), pd.DataFrame(threshold_rows)


def _semester(values: pd.Series) -> pd.Series:
    dates = pd.to_datetime(values)
    return dates.dt.year.astype(str) + "H" + np.where(dates.dt.month.le(6), "1", "2")


def summarize_policies(events: pd.DataFrame, decisions: pd.DataFrame,
                       config: E9Config) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    summaries, folds, semesters = [], [], []
    bootstrap = RollingConfig(bootstrap_samples=config.bootstrap_samples,
                              bootstrap_block_sessions=config.bootstrap_block_sessions,
                              bootstrap_seed=config.bootstrap_seed)
    for (basis, delay), group in decisions.groupby(["basis", "delay"], sort=False):
        signal_col = _signal_column(str(basis), int(delay))
        eligible = events.dropna(subset=[signal_col, f"future_unsigned_d{delay}"])
        group = group.copy()
        group["always_long_net"] = group[f"delayed_long_net_d{delay}"]
        group["paired_delta_vs_long"] = group["directional_net"] - group["always_long_net"]
        group["correct_direction"] = np.sign(group[signal_col]) == np.sign(group[f"future_unsigned_d{delay}"])
        daily = group.groupby("date")["directional_net"].mean().sort_index()
        delta_daily = group.groupby("date")["paired_delta_vs_long"].mean().sort_index()
        ci, delta_ci = block_bootstrap_mean(daily, bootstrap), block_bootstrap_mean(delta_daily, bootstrap)
        by_fold = group.groupby("evaluation_fold")["directional_net"].mean()
        group["semester"] = _semester(group["date"])
        by_semester = group.groupby("semester")["directional_net"].mean()
        policy = f"{basis}_d{delay}"
        summaries.append({"policy": policy, "basis": basis, "delay": int(delay),
                          "eligible_events": int(len(eligible)), "trades": int(len(group)),
                          "coverage": float(len(group) / len(eligible)) if len(eligible) else 0.0,
                          "long_share": float(group["direction"].eq("LONG").mean()),
                          "mean_directional_net": float(group["directional_net"].mean()),
                          "daily_mean_directional_net": float(daily.mean()),
                          "daily_mean_ci95_low": ci[0], "daily_mean_ci95_high": ci[1],
                          "direction_accuracy": float(group["correct_direction"].mean()),
                          "mean_always_long_net_same_events": float(group["always_long_net"].mean()),
                          "mean_delta_vs_long": float(group["paired_delta_vs_long"].mean()),
                          "paired_daily_delta_vs_long": float(delta_daily.mean()),
                          "paired_daily_delta_ci95_low": delta_ci[0],
                          "paired_daily_delta_ci95_high": delta_ci[1],
                          "positive_fold_ratio": float(by_fold.gt(0).mean()),
                          "positive_semester_ratio": float(by_semester.gt(0).mean())})
        for fold, values in group.groupby("evaluation_fold"):
            folds.append({"policy": policy, "fold": fold, "trades": len(values),
                          "mean_directional_net": values["directional_net"].mean(),
                          "direction_accuracy": values["correct_direction"].mean()})
        for semester, values in group.groupby("semester"):
            semesters.append({"policy": policy, "semester": semester, "trades": len(values),
                              "mean_directional_net": values["directional_net"].mean(),
                              "direction_accuracy": values["correct_direction"].mean()})
    return pd.DataFrame(summaries), pd.DataFrame(folds), pd.DataFrame(semesters)


def summarize_sides(decisions: pd.DataFrame, config: E9Config) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (basis, delay, direction), group in decisions.groupby(
        ["basis", "delay", "direction"], sort=False
    ):
        signal_col = _signal_column(str(basis), int(delay))
        future_col = f"future_unsigned_d{delay}"
        daily = group.groupby("date")["directional_net"].mean()
        rows.append({
            "policy": f"{basis}_d{delay}", "basis": basis, "delay": int(delay),
            "direction": direction, "trades": int(len(group)),
            "mean_directional_net": float(group["directional_net"].mean()),
            "daily_mean_directional_net": float(daily.mean()),
            "direction_accuracy": float(
                (np.sign(group[signal_col]) == np.sign(group[future_col])).mean()
            ),
            "mean_underlying_future_return": float(group[future_col].mean()),
            "round_trip_cost": config.round_trip_cost,
        })
    return pd.DataFrame(rows)


def evaluate_verdict(summary: pd.DataFrame, config: E9Config) -> dict[str, Any]:
    primary_name = f"{config.primary_basis}_d{config.primary_delay}"
    primary = summary[summary["policy"].eq(primary_name)].iloc[0].to_dict()
    def gates(row: dict[str, Any]) -> dict[str, bool]:
        return {"trades_ge_minimum": row["trades"] >= config.minimum_policy_events,
                "coverage_ge_minimum": row["coverage"] >= config.minimum_policy_coverage,
                "directional_net_positive": row["daily_mean_directional_net"] > 0,
                "delta_vs_long_positive": row["paired_daily_delta_vs_long"] > 0,
                "delta_ci95_above_zero": row["paired_daily_delta_ci95_low"] > 0,
                "positive_folds_ge_60pct": row["positive_fold_ratio"] >= 0.60,
                "positive_semesters_ge_60pct": row["positive_semester_ratio"] >= 0.60}
    primary_gates = gates(primary)
    secondary = []
    for row in summary.to_dict(orient="records"):
        if row["policy"] != primary_name and all(gates(row).values()):
            secondary.append({"policy": row["policy"], "gates": gates(row)})
    verdict = ("GO_RESEARCH_PRIMARY" if all(primary_gates.values()) else
               "GO_RESEARCH_SECONDARY_REQUIRES_INDEPENDENT_CONFIRMATION" if secondary else "NO_GO")
    return {"verdict": verdict, "primary_policy": primary_name,
            "primary_metrics": primary, "primary_gates": primary_gates,
            "secondary_gate_passers": secondary, "promotion_authorized": False,
            "next_step": "E9-B canonical lifecycle replay" if verdict == "GO_RESEARCH_PRIMARY" else
                         "freeze secondary then confirm" if secondary else "close post-signal confirmation"}


def run(*, phase1_artifact: Path, output_root: Path, config: E9Config) -> Path:
    source = phase1_artifact / "fixed_origin_events.parquet"
    if not source.is_file():
        raise ValueError(f"Artefact phase 1 absent: {source}")
    oracle_events = pd.read_parquet(source)
    symbols = sorted(oracle_events.loc[oracle_events["mh0"].fillna(False), "symbol"].unique())
    start = (pd.Timestamp(oracle_events["date"].min()) - pd.offsets.BDay(5)).date()
    end = (pd.Timestamp(oracle_events["terminal_date"].max()) + pd.offsets.BDay(2)).date()
    engine = get_sqlalchemy_engine()
    prices = prepare_price_panel(load_universe_bars(engine, symbols, start_date=start, end_date=end), config.delays)
    benchmark = prepare_price_panel(load_benchmark_bars(engine, "SPY", start_date=start, end_date=end), config.delays)
    events = attach_confirmation_paths(oracle_events, prices, benchmark, _load_sector_mapping(engine), config)
    decisions, thresholds = build_prequential_decisions(events, config)
    summary, folds, semesters = summarize_policies(events, decisions, config)
    sides = summarize_sides(decisions, config)
    decision = evaluate_verdict(summary, config)
    run_id = f"oracle-post-signal-confirmation-{datetime.now(UTC):%Y%m%d%H%M%S}"
    output = output_root / run_id
    output.mkdir(parents=True, exist_ok=False)
    events.to_parquet(output / "eligible_events.parquet", index=False)
    decisions.to_parquet(output / "prequential_decisions.parquet", index=False)
    thresholds.to_json(output / "threshold_history.jsonl", orient="records", lines=True, force_ascii=False)
    summary.to_csv(output / "policy_summary.csv", index=False)
    folds.to_csv(output / "policy_by_fold.csv", index=False)
    semesters.to_csv(output / "policy_by_semester.csv", index=False)
    sides.to_csv(output / "policy_by_side.csv", index=False)
    report = {"schema_version": 1, "run_id": run_id,
              "experiment": "E9_A_ORACLE_POST_SIGNAL_DIRECTION_CONFIRMATION",
              "status": "complete", "research_only": True,
              "generated_at": datetime.now(UTC).isoformat(),
              "source_phase1_artifact": str(phase1_artifact), "config": asdict(config),
              "coverage": {"oracle_top20_events": int(len(events)),
                           "dates": int(events["date"].nunique()),
                           "symbols": int(events["symbol"].nunique()),
                           "first_date": events["date"].min().date().isoformat(),
                           "last_date": events["date"].max().date().isoformat(),
                           "folds": int(events["fold_h20"].nunique()),
                           "sector_mapping_is_current_not_pit": True},
              "decision": decision}
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    LOGGER.info("E9-A terminé: %s verdict=%s", output, decision["verdict"])
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase1-artifact", type=Path, required=True)
    parser.add_argument("--output-root", type=Path,
                        default=Path("artifacts/research/oracle_post_signal_confirmation"))
    parser.add_argument("--bootstrap-samples", type=int, default=2_000)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    output = run(phase1_artifact=args.phase1_artifact, output_root=args.output_root,
                 config=E9Config(bootstrap_samples=args.bootstrap_samples))
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    print(f"E9-A terminé: {output}")
    print(report["decision"]["verdict"])


if __name__ == "__main__":
    main()
