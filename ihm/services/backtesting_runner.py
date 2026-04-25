"""Services de construction des commandes backtesting pour l'IHM Streamlit."""
from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from typing import Literal

from ihm.services.pipeline_runner import PROJECT_ROOT, build_subprocess_env

BacktestingCommandKind = Literal["run", "backfill-scores-history", "diagnose-screener", "recommend-screener"]


@dataclass(frozen=True, slots=True)
class BacktestRunOptions:
    """Options de la commande `python -m backtesting run`."""

    start: str
    end: str | None = None
    equity: float = 100_000.0
    tp: float = 0.08
    ts: float = 0.05
    max_positions: int = 20
    fees: float = 0.001
    account_type: Literal["margin", "cash"] = "margin"
    pdt_rule: Literal["auto", "off"] = "auto"
    swing_only: bool = False
    sentiment_lookback: int = 365
    no_save: bool = False
    ml_mode: Literal["auto", "off", "rebuild-missing"] = "auto"
    sentiment_mode: Literal["auto", "off", "rebuild-missing"] = "auto"
    artifacts_dir: str = "artifacts/models"
    output_dir: str | None = None


@dataclass(frozen=True, slots=True)
class BackfillScoresHistoryOptions:
    """Options de la commande `python -m backtesting backfill-scores-history`."""

    start: str
    end: str | None = None
    overwrite_existing: bool = False
    limit_days: int | None = None
    chunk_size: int = 500
    selection_size: int = 100
    screener_workers: int | None = None


@dataclass(frozen=True, slots=True)
class DiagnoseScreenerOptions:
    """Options de la commande `python -m backtesting diagnose-screener`."""

    start: str
    end: str | None = None
    limit_days: int | None = None
    mode: Literal["oat", "grid"] = "oat"
    chunk_size: int = 500
    selection_size: int = 100
    max_positions: int = 20
    screener_workers: int | None = None
    max_scenarios: int = 64
    rs_values: str = "100,102,105"
    range_lookback_values: str = "252,504,756"
    historical_range_score_values: str = "65,70,75"
    liquidity_threshold_values: str = "5000000,10000000,20000000"
    output_dir: str = "artifacts/screener_diagnostics"


@dataclass(frozen=True, slots=True)
class RecommendScreenerOptions:
    """Options de la commande `python -m backtesting recommend-screener`."""

    input_dir: str = "artifacts/screener_diagnostics"
    summary_csv: str | None = None
    daily_csv: str | None = None
    output_dir: str | None = None
    baseline_name: str | None = None
    target_horizon: int = 20


def build_backtesting_command(
    kind: BacktestingCommandKind,
    options: BacktestRunOptions | BackfillScoresHistoryOptions | DiagnoseScreenerOptions | RecommendScreenerOptions,
) -> list[str]:
    """Construit la commande subprocess correspondant au backtesting."""
    command = [sys.executable, "-u", "-m", "backtesting", kind]

    if kind == "run":
        if not isinstance(options, BacktestRunOptions):
            raise TypeError("options doit être une instance de BacktestRunOptions pour kind='run'.")
        command.extend(["--start", options.start])
        if options.end:
            command.extend(["--end", options.end])
        command.extend([
            "--equity", str(options.equity),
            "--tp", str(options.tp),
            "--ts", str(options.ts),
            "--max-positions", str(options.max_positions),
            "--fees", str(options.fees),
            "--account-type", options.account_type,
            "--pdt-rule", options.pdt_rule,
            "--sentiment-lookback", str(options.sentiment_lookback),
            "--ml-mode", options.ml_mode,
            "--sentiment-mode", options.sentiment_mode,
            "--artifacts-dir", options.artifacts_dir,
        ])
        if options.swing_only:
            command.append("--swing-only")
        if options.output_dir:
            command.extend(["--output-dir", options.output_dir])
        if options.no_save:
            command.append("--no-save")
        return command

    if kind == "backfill-scores-history":
        if not isinstance(options, BackfillScoresHistoryOptions):
            raise TypeError(
                "options doit être une instance de BackfillScoresHistoryOptions pour kind='backfill-scores-history'."
            )
        command.extend(["--start", options.start])
        if options.end:
            command.extend(["--end", options.end])
        if options.overwrite_existing:
            command.append("--overwrite-existing")
        if options.limit_days is not None:
            command.extend(["--limit-days", str(options.limit_days)])
        command.extend([
            "--chunk-size", str(options.chunk_size),
            "--selection-size", str(options.selection_size),
        ])
        if options.screener_workers is not None:
            command.extend(["--screener-workers", str(options.screener_workers)])
        return command

    if kind == "diagnose-screener":
        if not isinstance(options, DiagnoseScreenerOptions):
            raise TypeError(
                "options doit être une instance de DiagnoseScreenerOptions pour kind='diagnose-screener'."
            )
        command.extend(["--start", options.start])
        if options.end:
            command.extend(["--end", options.end])
        if options.limit_days is not None:
            command.extend(["--limit-days", str(options.limit_days)])
        command.extend([
            "--mode", options.mode,
            "--chunk-size", str(options.chunk_size),
            "--selection-size", str(options.selection_size),
            "--max-positions", str(options.max_positions),
            "--max-scenarios", str(options.max_scenarios),
            "--rs-values", options.rs_values,
            "--range-lookback-values", options.range_lookback_values,
            "--historical-range-score-values", options.historical_range_score_values,
            "--liquidity-threshold-values", options.liquidity_threshold_values,
            "--output-dir", options.output_dir,
        ])
        if options.screener_workers is not None:
            command.extend(["--screener-workers", str(options.screener_workers)])
        return command

    if kind == "recommend-screener":
        if not isinstance(options, RecommendScreenerOptions):
            raise TypeError(
                "options doit être une instance de RecommendScreenerOptions pour kind='recommend-screener'."
            )
        command.extend(["--input-dir", options.input_dir])
        if options.summary_csv:
            command.extend(["--summary-csv", options.summary_csv])
        if options.daily_csv:
            command.extend(["--daily-csv", options.daily_csv])
        if options.output_dir:
            command.extend(["--output-dir", options.output_dir])
        if options.baseline_name:
            command.extend(["--baseline-name", options.baseline_name])
        command.extend(["--target-horizon", str(options.target_horizon)])
        return command

    raise KeyError(f"Commande backtesting inconnue : {kind}")


def format_command_for_display(command: list[str]) -> str:
    return subprocess.list2cmdline(command)


__all__ = [
    "PROJECT_ROOT",
    "build_subprocess_env",
    "BacktestingCommandKind",
    "BacktestRunOptions",
    "BackfillScoresHistoryOptions",
    "DiagnoseScreenerOptions",
    "RecommendScreenerOptions",
    "build_backtesting_command",
    "format_command_for_display",
]

