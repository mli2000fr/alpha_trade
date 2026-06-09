"""Services de construction des commandes backtesting pour l'IHM Streamlit."""
from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from typing import Literal

from ihm.services.pipeline_runner import PROJECT_ROOT, build_subprocess_env

BacktestingCommandKind = Literal[
    "run",
    "backfill-scores-history",
    "diagnose-screener",
    "recommend-screener",
    "calibrate-sentiment-weights",
    "walk-forward-sentiment",
]


@dataclass(frozen=True, slots=True)
class BacktestRunOptions:
    """Options de la commande `python -m backtesting run`."""

    start: str
    end: str | None = None
    equity: float = 100_000.0
    capital_preset_key: str | None = None
    tp: float = 0.08
    ts: float = 0.05
    max_positions: int = 20
    fees: float | None = None
    commission_bps: float | None = None
    slippage_bps: float | None = None
    account_type: Literal["margin", "cash"] = "margin"
    swing_only: bool = False
    allow_fractional_shares: bool = True
    sentiment_lookback: int = 365
    no_save: bool = False
    ml_mode: Literal["auto", "off", "rebuild-missing"] = "auto"
    sentiment_mode: Literal["auto", "off", "rebuild-missing"] = "auto"
    engine_mode: Literal["research", "pipeline"] = "research"
    scores_pit_mode: Literal["exact", "asof_latest"] = "exact"
    macro_pit_mode: Literal["yaml_default", "asof_inclusive", "j_minus_1_strict"] = "yaml_default"
    ml_pit_strategy: Literal["auto", "use-persisted", "rebuild-missing", "walk-forward-train-then-predict"] = "auto"
    phase2_mode: Literal["off", "risk", "risk_execution"] = "off"
    phase3_mode: Literal["off", "execution_replay"] = "off"
    phase4_mode: Literal["off", "protection_replay"] = "off"
    phase5_mode: Literal["off", "watcher_replay"] = "off"
    phase7_mode: Literal["off", "exit_lifecycle_replay"] = "off"
    allow_neutral_fallback_on_missing_macro_data: bool = False
    fidelity_baseline_id: str | None = None
    fidelity_baseline_catalog: str | None = None
    artifacts_dir: str = "artifacts/models"
    score_column: Literal["auto", "final_score_walk_forward", "final_score_sentiment", "final_score"] = "auto"
    walk_forward_artifacts_dir: str | None = None
    output_dir: str | None = None
    # Phase A (refactor) — reproductibilité + risk-free rate
    risk_free_rate: float = 0.0
    seed: int | None = None
    # Phase B (refactor) — micro-structure
    slippage_model: Literal["fixed", "linear", "sqrt"] = "fixed"
    slippage_base_bps: float = 0.0
    slippage_impact_coef: float = 0.0
    initial_stop_pct: float = 0.0
    max_entry_gap_pct: float = 0.0
    intrabar_priority: Literal["conservative", "tp_first", "ts_first", "random"] = "conservative"
    # Phase C (refactor) — risk overlays
    sizing_mode: Literal["equal_weight", "conviction_weighted"] = "equal_weight"
    sizing_min_weight_pct: float = 0.005
    sizing_max_weight_pct: float = 0.20
    regime_filter: bool = False
    regime_sma_window: int = 200
    regime_bear_threshold: float = -0.02
    max_sector_exposure_pct: float = 0.0
    max_portfolio_dd_pct: float = 0.0
    dd_recovery_pct: float = 0.95
    target_annual_vol: float | None = None
    min_ml_coverage_ratio: float | None = None


@dataclass(frozen=True, slots=True)
class BackfillScoresHistoryOptions:
    """Options de la commande `python -m backtesting backfill-scores-history`."""

    start: str
    end: str | None = None
    capital: float | None = None
    capital_preset_key: str | None = None
    overwrite_existing: bool = False
    limit_days: int | None = None
    chunk_size: int = 1000
    selection_size: int = 100
    screener_workers: int | None = 4


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


@dataclass(frozen=True, slots=True)
class CalibrateSentimentWeightsOptions:
    """Options de `python -m backtesting calibrate-sentiment-weights` (Sprint S26)."""

    start: str
    end: str
    top_n: int = 20
    horizons: str = "5,10,20"
    output_dir: str = "artifacts/sentiment_calibration"
    all_symbols: bool = False


@dataclass(frozen=True, slots=True)
class WalkForwardSentimentOptions:
    """Options de `python -m backtesting walk-forward-sentiment` (Sprint S26)."""

    start: str
    end: str
    top_n: int = 20
    horizons: str = "5,10,20"
    min_train_days: int = 252
    test_days: int = 63
    step_days: int | None = None
    max_positions: int = 20
    equity: float = 100_000.0
    tp: float = 0.08
    ts: float = 0.05
    fees: float = 0.001
    output_dir: str = "artifacts/sentiment_walk_forward"
    all_symbols: bool = False


def build_backtesting_command(
    kind: BacktestingCommandKind,
    options: BacktestRunOptions
    | BackfillScoresHistoryOptions
    | DiagnoseScreenerOptions
    | RecommendScreenerOptions
    | CalibrateSentimentWeightsOptions
    | WalkForwardSentimentOptions,
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
            "--account-type", options.account_type,
            "--sentiment-lookback", str(options.sentiment_lookback),
            "--ml-mode", options.ml_mode,
            "--sentiment-mode", options.sentiment_mode,
            "--engine-mode", options.engine_mode,
            "--scores-pit-mode", options.scores_pit_mode,
            "--macro-pit-mode", options.macro_pit_mode,
            "--ml-pit-strategy", options.ml_pit_strategy,
            "--phase2-mode", options.phase2_mode,
            "--phase3-mode", options.phase3_mode,
            "--phase4-mode", options.phase4_mode,
            "--phase5-mode", options.phase5_mode,
            "--phase7-mode", options.phase7_mode,
            "--artifacts-dir", options.artifacts_dir,
            "--score-column", options.score_column,
        ])
        if options.allow_fractional_shares:
            command.append("--allow-fractional-shares")
        if options.commission_bps is not None:
            command.extend(["--commission-bps", str(options.commission_bps)])
        if options.slippage_bps is not None:
            command.extend(["--slippage-bps", str(options.slippage_bps)])
        if options.commission_bps is None and options.slippage_bps is None and options.fees is not None:
            command.extend(["--fees", str(options.fees)])
        if options.allow_neutral_fallback_on_missing_macro_data:
            command.append("--allow-neutral-fallback-on-missing-macro-data")
        else:
            command.append("--fail-on-missing-macro-data")
        if options.capital_preset_key:
            command.extend(["--capital-preset-key", options.capital_preset_key])
        if options.walk_forward_artifacts_dir:
            command.extend(["--walk-forward-artifacts-dir", options.walk_forward_artifacts_dir])
        if options.fidelity_baseline_id:
            command.extend(["--fidelity-baseline-id", options.fidelity_baseline_id])
        if options.fidelity_baseline_catalog:
            command.extend(["--fidelity-baseline-catalog", options.fidelity_baseline_catalog])
        if options.swing_only:
            command.append("--swing-only")
        if options.output_dir:
            command.extend(["--output-dir", options.output_dir])
        if options.no_save:
            command.append("--no-save")
        # Phase A (refactor) — reproductibilité + risk-free rate.
        if options.risk_free_rate:
            command.extend(["--risk-free-rate", str(options.risk_free_rate)])
        if options.seed is not None:
            command.extend(["--seed", str(options.seed)])
        # Phase B (refactor) — micro-structure (n'émet que si non-default pour
        # garder les commandes courtes et compatibles avec les pipelines existants).
        if options.slippage_model != "fixed":
            command.extend(["--slippage-model", options.slippage_model])
        if options.slippage_base_bps:
            command.extend(["--slippage-base-bps", str(options.slippage_base_bps)])
        if options.slippage_impact_coef:
            command.extend(["--slippage-impact-coef", str(options.slippage_impact_coef)])
        if options.initial_stop_pct:
            command.extend(["--initial-stop-pct", str(options.initial_stop_pct)])
        if options.max_entry_gap_pct:
            command.extend(["--max-entry-gap-pct", str(options.max_entry_gap_pct)])
        if options.intrabar_priority != "conservative":
            command.extend(["--intrabar-priority", options.intrabar_priority])
        # Phase C (refactor) — risk overlays.
        if options.sizing_mode != "equal_weight":
            command.extend(["--sizing-mode", options.sizing_mode])
            command.extend(["--sizing-min-weight-pct", str(options.sizing_min_weight_pct)])
            command.extend(["--sizing-max-weight-pct", str(options.sizing_max_weight_pct)])
        if options.regime_filter:
            command.append("--regime-filter")
            command.extend(["--regime-sma-window", str(options.regime_sma_window)])
            command.extend(["--regime-bear-threshold", str(options.regime_bear_threshold)])
        if options.max_sector_exposure_pct:
            command.extend(["--max-sector-exposure-pct", str(options.max_sector_exposure_pct)])
        if options.max_portfolio_dd_pct:
            command.extend(["--max-portfolio-dd-pct", str(options.max_portfolio_dd_pct)])
            command.extend(["--dd-recovery-pct", str(options.dd_recovery_pct)])
        if options.target_annual_vol is not None:
            command.extend(["--target-annual-vol", str(options.target_annual_vol)])
        if options.min_ml_coverage_ratio is not None:
            command.extend(["--min-ml-coverage-ratio", str(options.min_ml_coverage_ratio)])
        return command

    if kind == "backfill-scores-history":
        if not isinstance(options, BackfillScoresHistoryOptions):
            raise TypeError(
                "options doit être une instance de BackfillScoresHistoryOptions pour kind='backfill-scores-history'."
            )
        command.extend(["--start", options.start])
        if options.end:
            command.extend(["--end", options.end])
        if options.capital is not None:
            command.extend(["--capital", str(options.capital)])
        if options.capital_preset_key:
            command.extend(["--capital-preset-key", options.capital_preset_key])
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

    if kind == "calibrate-sentiment-weights":
        if not isinstance(options, CalibrateSentimentWeightsOptions):
            raise TypeError(
                "options doit être une instance de CalibrateSentimentWeightsOptions pour kind='calibrate-sentiment-weights'."
            )
        command.extend([
            "--start", options.start,
            "--end", options.end,
            "--top-n", str(options.top_n),
            "--horizons", options.horizons,
            "--output-dir", options.output_dir,
        ])
        if options.all_symbols:
            command.append("--all-symbols")
        return command

    if kind == "walk-forward-sentiment":
        if not isinstance(options, WalkForwardSentimentOptions):
            raise TypeError(
                "options doit être une instance de WalkForwardSentimentOptions pour kind='walk-forward-sentiment'."
            )
        command.extend([
            "--start", options.start,
            "--end", options.end,
            "--top-n", str(options.top_n),
            "--horizons", options.horizons,
            "--min-train-days", str(options.min_train_days),
            "--test-days", str(options.test_days),
            "--max-positions", str(options.max_positions),
            "--equity", str(options.equity),
            "--tp", str(options.tp),
            "--ts", str(options.ts),
            "--fees", str(options.fees),
            "--output-dir", options.output_dir,
        ])
        if options.step_days is not None:
            command.extend(["--step-days", str(options.step_days)])
        if options.all_symbols:
            command.append("--all-symbols")
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
    "CalibrateSentimentWeightsOptions",
    "WalkForwardSentimentOptions",
    "build_backtesting_command",
    "format_command_for_display",
]

