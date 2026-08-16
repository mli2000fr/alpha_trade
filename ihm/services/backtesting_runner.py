"""Services de construction des commandes backtesting pour l'IHM Streamlit."""
from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from typing import Literal

from core.ml_selection_contract import MLFirstSelectionContract, SelectionCapacity
from ihm.services.pipeline_runner import PROJECT_ROOT, build_subprocess_env

BacktestingCommandKind = Literal[
    "run",
    "backfill-scores-history",
    "diagnose-screener",
    "recommend-screener",
    "calibrate-sentiment-weights",
    "calibrate-conviction-weights",
    "walk-forward-sentiment",
    "walk-forward-conviction",
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
    atr_ts: float = 0.0
    ts_long: float | None = None
    ts_short: float | None = None
    atr_risk_stop_multiple: float = 0.0
    tp_atr_multiple: float = 0.0
    tp_max_pct: float = 0.0
    use_canonical_costs: bool = False
    margin_interest_rate: float = 0.0
    use_live_protection_logic: bool = True
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
    ml_batch_id: str | None = None
    cascade_batch_id: str | None = None
    batch_diagnostics_batch_id: str | None = None
    score_column: Literal["auto", "final_score_walk_forward", "final_score_sentiment", "final_score"] = "auto"
    walk_forward_artifacts_dir: str | None = None
    disable_walk_forward: bool = False
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
    sizing_mode: Literal["equal_weight", "conviction_weighted", "rank_weighted"] = "equal_weight"
    sizing_min_weight_pct: float = 0.005
    sizing_max_weight_pct: float = 0.20
    # P2-1 inc.3 — multiplicateurs sectoriels (JSON {secteur: facteur} ou @fichier)
    sector_multipliers_json: str | None = None
    regime_filter: bool = False
    regime_sma_window: int = 200
    regime_bear_threshold: float = -0.02
    max_sector_exposure_pct: float = 0.0
    max_portfolio_dd_pct: float = 0.0
    dd_recovery_pct: float = 0.92
    target_annual_vol: float | None = None
    min_ml_coverage_ratio: float | None = None
    # Conviction/Kelly calibration (opt-in, Phase 2 only)
    conviction_calibration_mode: Literal["off", "auto", "pinned"] = "off"
    conviction_calibration_run_id: str | None = None

    @property
    def ml_first_selection_contract(self) -> MLFirstSelectionContract:
        """Contrat cible partagé, sans modifier encore la commande CLI."""
        return MLFirstSelectionContract(
            capacity=SelectionCapacity(
                max_positions=self.max_positions,
                max_long_positions=self.max_positions,
                max_short_positions=min(2, self.max_positions),
            )
        )


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
    universe_only: bool = False
    symbol_source: str | None = "ticket-recherche"


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
    capital_preset_key: str | None = None


@dataclass(frozen=True, slots=True)
class RecommendScreenerOptions:
    """Options de la commande `python -m backtesting recommend-screener`."""

    input_dir: str = "artifacts/screener_diagnostics"
    summary_csv: str | None = None
    daily_csv: str | None = None
    output_dir: str | None = None
    baseline_name: str | None = None
    target_horizon: int = 20
    capital_preset_key: str | None = None


@dataclass(frozen=True, slots=True)
class CalibrateSentimentWeightsOptions:
    """Options de `python -m backtesting calibrate-sentiment-weights` (Sprint S26)."""

    start: str
    end: str
    top_n: int = 20
    horizons: str = "5,10,20"
    output_dir: str = "artifacts/sentiment_calibration"
    all_symbols: bool = False
    capital_preset_key: str | None = None
    symbol_source: str | None = None


@dataclass(frozen=True, slots=True)
class CalibrateConvictionWeightsOptions:
    """Options de `python -m backtesting calibrate-conviction-weights` (P2 2026-06-25)."""

    start: str
    end: str
    top_n: int = 20
    horizons: str = "5,10,20"
    output_dir: str = "artifacts/conviction_calibration"
    scope: str = "all"  # "conviction", "kelly", "all"
    backtest_kelly: bool = False  # Sprint 3
    top_n_long: int | None = None
    top_n_short: int | None = None


@dataclass(frozen=True, slots=True)
class WalkForwardConvictionOptions:
    """Options de `python -m backtesting walk-forward-conviction` (Sprint 4)."""

    start: str
    end: str
    top_n: int = 20
    horizons: str = "5,10,20"
    min_train_days: int = 252
    test_days: int = 63
    step_days: int | None = None
    output_dir: str = "artifacts/walk_forward_conviction"
    backtest_kelly: bool = False
    # Sprint 5/6 — market-neutral + grilles symétriques
    symmetric_grid: str | None = None
    top_n_long: int | None = None
    top_n_short: int | None = None
    enforce_net_exposure: bool = False
    net_exposure_target: float = 0.0


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
    atr_ts: float = 2.0
    fees: float = 0.001
    output_dir: str = "artifacts/sentiment_walk_forward"
    all_symbols: bool = False
    capital_preset_key: str | None = None
    symbol_source: str | None = None


def build_backtesting_command(
    kind: BacktestingCommandKind,
    options: BacktestRunOptions
    | BackfillScoresHistoryOptions
    | DiagnoseScreenerOptions
    | RecommendScreenerOptions
    | CalibrateSentimentWeightsOptions
    | CalibrateConvictionWeightsOptions
    | WalkForwardConvictionOptions
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
        if options.ml_batch_id:
            command.extend(["--ml-batch-id", options.ml_batch_id])
        if options.cascade_batch_id:
            command.extend(["--cascade-batch-id", options.cascade_batch_id])
        if options.batch_diagnostics_batch_id:
            command.extend(["--batch-diagnostics-batch-id", options.batch_diagnostics_batch_id])
        if options.use_live_protection_logic:
            command.append("--use-live-protection-logic")
        else:
            command.extend([
                "--use-fixed-protection-logic",
                "--tp", str(options.tp),
                "--ts", str(options.ts),
            ])
        # P1 — ATR trailing stop (indépendant du mode de protection)
        if options.atr_ts and float(options.atr_ts) > 0:
            command.extend(["--atr-ts", str(options.atr_ts)])
        # P2-4 — trailing par côté (plancher) + fidélité live du stop ATR
        if options.ts_long is not None:
            command.extend(["--ts-long", str(options.ts_long)])
        if options.ts_short is not None:
            command.extend(["--ts-short", str(options.ts_short)])
        if options.atr_risk_stop_multiple and float(options.atr_risk_stop_multiple) > 0:
            command.extend(["--atr-risk-stop-multiple", str(options.atr_risk_stop_multiple)])
        # P2-4 — TP de production + coûts canoniques
        if options.tp_atr_multiple and float(options.tp_atr_multiple) > 0:
            command.extend(["--tp-atr-multiple", str(options.tp_atr_multiple)])
        if options.tp_max_pct and float(options.tp_max_pct) > 0:
            command.extend(["--tp-max-pct", str(options.tp_max_pct)])
        if options.use_canonical_costs:
            # Fix 2026-08-14 : sans flags explicites, les défauts CLI
            # (commission 12 bps + slippage 20 bps) étaient appliqués au
            # P&L legacy. On fixe les valeurs du modèle canonique (1+2 bps)
            # pour que le rapport CLI reflète les coûts réels appliqués.
            command.extend([
                "--use-canonical-costs",
                "--commission-bps", "1",
                "--slippage-bps", "2",
            ])
        if options.margin_interest_rate and float(options.margin_interest_rate) > 0:
            command.extend(["--margin-interest-rate", str(options.margin_interest_rate)])
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
        if options.disable_walk_forward:
            # Passe un répertoire inexistant pour empêcher l'auto-découverte
            # dans resilience._apply_walk_forward_overlay.
            command.extend(["--walk-forward-artifacts-dir", "__none__/skip_walk_forward"])
        elif options.walk_forward_artifacts_dir:
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
        if (not options.use_live_protection_logic) and options.initial_stop_pct:
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
        if options.sector_multipliers_json:
            command.extend(["--sector-multipliers-json", options.sector_multipliers_json])
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
        if options.conviction_calibration_mode != "off":
            command.extend(["--conviction-calibration-mode", options.conviction_calibration_mode])
            if options.conviction_calibration_run_id:
                command.extend(["--conviction-calibration-run-id", options.conviction_calibration_run_id])
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
        if options.universe_only:
            command.append("--universe-only")
        if options.symbol_source:
            command.extend(["--symbol-source", options.symbol_source])
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
        if options.capital_preset_key:
            command.extend(["--capital-preset-key", options.capital_preset_key])
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
        if options.capital_preset_key:
            command.extend(["--capital-preset-key", options.capital_preset_key])
        if options.symbol_source:
            command.extend(["--symbol-source", options.symbol_source])
        return command

    if kind == "calibrate-conviction-weights":
        if not isinstance(options, CalibrateConvictionWeightsOptions):
            raise TypeError(
                "options doit être une instance de CalibrateConvictionWeightsOptions "
                "pour kind='calibrate-conviction-weights'."
            )
        command.extend([
            "--start", options.start,
            "--end", options.end,
            "--top-n", str(options.top_n),
            "--horizons", options.horizons,
            "--output-dir", options.output_dir,
            "--scope", options.scope,
        ])
        if options.backtest_kelly:
            command.append("--backtest-kelly")
        if options.top_n_long is not None:
            command.extend(["--top-n-long", str(options.top_n_long)])
        if options.top_n_short is not None:
            command.extend(["--top-n-short", str(options.top_n_short)])
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
            "--atr-ts", str(options.atr_ts),
            "--fees", str(options.fees),
            "--output-dir", options.output_dir,
        ])
        if options.step_days is not None:
            command.extend(["--step-days", str(options.step_days)])
        if options.all_symbols:
            command.append("--all-symbols")
        if options.capital_preset_key:
            command.extend(["--capital-preset-key", options.capital_preset_key])
        if options.symbol_source:
            command.extend(["--symbol-source", options.symbol_source])
        return command

    if kind == "walk-forward-conviction":
        if not isinstance(options, WalkForwardConvictionOptions):
            raise TypeError(
                "options doit être une instance de WalkForwardConvictionOptions "
                "pour kind='walk-forward-conviction'."
            )
        command.extend([
            "--start", options.start,
            "--end", options.end,
            "--top-n", str(options.top_n),
            "--horizons", options.horizons,
            "--min-train-days", str(options.min_train_days),
            "--test-days", str(options.test_days),
            "--output-dir", options.output_dir,
        ])
        if options.step_days is not None:
            command.extend(["--step-days", str(options.step_days)])
        if options.backtest_kelly:
            command.append("--backtest-kelly")
        # Sprint 5/6 — market-neutral + grilles
        if options.symmetric_grid:
            command.extend(["--symmetric-grid", options.symmetric_grid])
        if options.top_n_long is not None:
            command.extend(["--top-n-long", str(options.top_n_long)])
        if options.top_n_short is not None:
            command.extend(["--top-n-short", str(options.top_n_short)])
        if options.enforce_net_exposure:
            command.append("--enforce-net-exposure")
            command.extend(["--net-exposure-target", str(options.net_exposure_target)])
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
    "CalibrateConvictionWeightsOptions",
    "WalkForwardSentimentOptions",
    "WalkForwardConvictionOptions",
    "build_backtesting_command",
    "format_command_for_display",
]

