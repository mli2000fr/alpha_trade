"""Services d'orchestration légère des pipelines depuis l'IHM Streamlit."""
from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Literal

from event_sentiment.config import EventSentimentConfig
from event_sentiment.signal_aggregator import SentimentBoostConfig
from screener.models import ScreenerConfig
from selector.strict_filter_profiles import STRICT_SWING_CASH_FILTERS

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCREENER_CONFIG = ScreenerConfig()
DEFAULT_SCREENER_CHUNK_SIZE = DEFAULT_SCREENER_CONFIG.chunk_size
DEFAULT_SCREENER_BENCHMARK_SYMBOL = DEFAULT_SCREENER_CONFIG.benchmark_symbol
DEFAULT_SCREENER_LIQUIDITY_THRESHOLD_USD = DEFAULT_SCREENER_CONFIG.liquidity_threshold_usd
DEFAULT_SCREENER_MIN_RELATIVE_STRENGTH_INDEX = DEFAULT_SCREENER_CONFIG.min_relative_strength_index
DEFAULT_SCREENER_HISTORICAL_RANGE_LOOKBACK_DAYS = DEFAULT_SCREENER_CONFIG.historical_range_lookback_days
DEFAULT_SCREENER_MIN_HISTORICAL_RANGE_SCORE = DEFAULT_SCREENER_CONFIG.min_historical_range_score
DEFAULT_SCREENER_FIRST_PASS_WINDOW_DAYS = DEFAULT_SCREENER_CONFIG.first_pass_window_days
DEFAULT_SCREENER_ENABLE_TWO_PASS_LOADING = DEFAULT_SCREENER_CONFIG.enable_two_pass_loading
DEFAULT_SELECTOR_CHUNK_SIZE = 500
DEFAULT_SELECTOR_SELECTION_SIZE = 50
DEFAULT_SELECTOR_MAX_ANOMALY_COUNT = 20
DEFAULT_SELECTOR_SECTOR_CAP_RATIO = 0.30
DEFAULT_SELECTOR_LOG_LEVEL = "INFO"
DEFAULT_SELECTOR_LIQUIDITY_THRESHOLD = STRICT_SWING_CASH_FILTERS.min_avg_dollar_volume_20d
DEFAULT_SELECTOR_MIN_CLOSE = STRICT_SWING_CASH_FILTERS.min_close
DEFAULT_SELECTOR_MAX_VOLATILITY_RATIO = STRICT_SWING_CASH_FILTERS.max_volatility_ratio
DEFAULT_SELECTOR_MIN_RELATIVE_STRENGTH_INDEX = STRICT_SWING_CASH_FILTERS.min_relative_strength_index
DEFAULT_SELECTOR_MIN_HIGH_52W_PROXIMITY = STRICT_SWING_CASH_FILTERS.min_high_52w_proximity
DEFAULT_SELECTOR_MIN_WEEKLY_TREND_SCORE = STRICT_SWING_CASH_FILTERS.min_weekly_trend_score
DEFAULT_SELECTOR_MIN_ATR_PCT_20 = STRICT_SWING_CASH_FILTERS.min_atr_pct_20
DEFAULT_SELECTOR_MAX_ATR_PCT_20 = STRICT_SWING_CASH_FILTERS.max_atr_pct_20
DEFAULT_SELECTOR_MIN_MARKET_CAP = STRICT_SWING_CASH_FILTERS.min_market_cap
DEFAULT_SELECTOR_MIN_BETA_126 = STRICT_SWING_CASH_FILTERS.min_beta_126
DEFAULT_SELECTOR_MAX_SPREAD_BPS = STRICT_SWING_CASH_FILTERS.max_spread_bps
DEFAULT_SELECTOR_EARNINGS_BLACKOUT_DAYS = STRICT_SWING_CASH_FILTERS.earnings_blackout_days
DEFAULT_EVENT_SENTIMENT_CONFIG = EventSentimentConfig()
DEFAULT_SIGNAL_AGGREGATOR_CONFIG = SentimentBoostConfig()
DEFAULT_SIGNAL_AGGREGATOR_SENTIMENT_WEIGHT = DEFAULT_SIGNAL_AGGREGATOR_CONFIG.sentiment_weight
DEFAULT_SIGNAL_AGGREGATOR_MACRO_WEIGHT = DEFAULT_SIGNAL_AGGREGATOR_CONFIG.macro_sector_weight
DEFAULT_SIGNAL_AGGREGATOR_LOOKBACK_DAYS = DEFAULT_SIGNAL_AGGREGATOR_CONFIG.lookback_days
DEFAULT_SIGNAL_AGGREGATOR_MIN_NEWS_COUNT = DEFAULT_SIGNAL_AGGREGATOR_CONFIG.min_news_count
DEFAULT_SIGNAL_AGGREGATOR_TIME_DECAY_HALF_LIFE_DAYS = DEFAULT_SIGNAL_AGGREGATOR_CONFIG.time_decay_half_life_days
DEFAULT_SIGNAL_AGGREGATOR_LOG_LEVEL = "INFO"
DEFAULT_DATA_INTEGRITY_QUOTES_BATCH_SIZE = 200
DEFAULT_DATA_INTEGRITY_PROVIDER_SLEEP_SECONDS = 1.1
DEFAULT_DATA_INTEGRITY_FUNDAMENTALS_LOG_EVERY = 50

AccountUsage = Literal["none", "alpaca"]
MLAccelerator = Literal["auto", "cpu", "gpu"]
MLGlobalModelName = Literal["catboost", "lightgbm"]
MLChampionMetric = Literal["selection_score", "business_score", "auc"]
PipelineExecutionStatus = Literal["starting", "running", "completed", "failed", "timeout"]


@dataclass(frozen=True, slots=True)
class PipelineLaunchOptions:
    """Options saisies dans l'IHM pour lancer une étape du pipeline."""

    account_id: str | None = None
    trade_date: str | None = None
    risk_account_equity: float = 100_000.0
    execution_mode: Literal["simulate", "paper", "live"] = "simulate"
    execution_run_id: str | None = None
    allow_outside_rth: bool = False
    auto_rebalance: bool = False
    execution_account_type: Literal["margin", "cash"] = "margin"
    execution_pdt_rule: Literal["auto", "off"] = "auto"
    execution_swing_only: bool = False
    ml_accelerator: MLAccelerator = "auto"
    ml_include_sentiment: bool = True
    ml_enable_lightgbm: bool = True
    ml_enable_catboost: bool = True
    ml_enable_global_model: bool = False
    ml_global_model_name: MLGlobalModelName = "catboost"
    ml_enable_cross_sectional: bool = False
    ml_select_champion: bool = True
    ml_champion_selection_metric: MLChampionMetric = "selection_score"
    ml_optimize_thresholds: bool = True
    ml_optimize_target: bool = False
    news_import_start_date: str | None = None
    news_import_end_date: str | None = None
    sentiment_start_utc: str | None = None
    sentiment_end_utc: str | None = None
    sentiment_symbols: str | None = None
    screener_chunk_size: int = DEFAULT_SCREENER_CHUNK_SIZE
    screener_max_workers: int | None = None
    screener_benchmark_symbol: str = DEFAULT_SCREENER_BENCHMARK_SYMBOL
    screener_liquidity_threshold_usd: float = DEFAULT_SCREENER_LIQUIDITY_THRESHOLD_USD
    screener_min_relative_strength_index: float = DEFAULT_SCREENER_MIN_RELATIVE_STRENGTH_INDEX
    screener_historical_range_lookback_days: int = DEFAULT_SCREENER_HISTORICAL_RANGE_LOOKBACK_DAYS
    screener_min_historical_range_score: float = DEFAULT_SCREENER_MIN_HISTORICAL_RANGE_SCORE
    screener_first_pass_window_days: int = DEFAULT_SCREENER_FIRST_PASS_WINDOW_DAYS
    screener_enable_two_pass_loading: bool = DEFAULT_SCREENER_ENABLE_TWO_PASS_LOADING
    selector_chunk_size: int = DEFAULT_SELECTOR_CHUNK_SIZE
    selector_selection_size: int = DEFAULT_SELECTOR_SELECTION_SIZE
    selector_max_workers: int | None = None
    selector_liquidity_threshold: float = float(DEFAULT_SELECTOR_LIQUIDITY_THRESHOLD)
    selector_min_close: float = float(DEFAULT_SELECTOR_MIN_CLOSE)
    selector_max_volatility_ratio: float = float(DEFAULT_SELECTOR_MAX_VOLATILITY_RATIO)
    selector_min_relative_strength_index: float = float(DEFAULT_SELECTOR_MIN_RELATIVE_STRENGTH_INDEX or 100.0)
    selector_min_high_52w_proximity: float = float(DEFAULT_SELECTOR_MIN_HIGH_52W_PROXIMITY or 0.75)
    selector_min_weekly_trend_score: float = float(DEFAULT_SELECTOR_MIN_WEEKLY_TREND_SCORE or 1.0)
    selector_min_atr_pct_20: float = float(DEFAULT_SELECTOR_MIN_ATR_PCT_20 or 0.015)
    selector_max_atr_pct_20: float = float(DEFAULT_SELECTOR_MAX_ATR_PCT_20 or 0.06)
    selector_min_market_cap: float = float(DEFAULT_SELECTOR_MIN_MARKET_CAP or 2_000_000_000.0)
    selector_min_beta_126: float = float(DEFAULT_SELECTOR_MIN_BETA_126 or 1.0)
    selector_max_spread_bps: float = float(DEFAULT_SELECTOR_MAX_SPREAD_BPS or 25.0)
    selector_earnings_blackout_days: int = int(DEFAULT_SELECTOR_EARNINGS_BLACKOUT_DAYS or 3)
    selector_max_anomaly_count: int = DEFAULT_SELECTOR_MAX_ANOMALY_COUNT
    selector_sector_cap_ratio: float = DEFAULT_SELECTOR_SECTOR_CAP_RATIO
    selector_log_level: str = DEFAULT_SELECTOR_LOG_LEVEL
    signal_aggregator_all_symbols: bool = False
    signal_aggregator_sentiment_weight: float = DEFAULT_SIGNAL_AGGREGATOR_SENTIMENT_WEIGHT
    signal_aggregator_macro_weight: float = DEFAULT_SIGNAL_AGGREGATOR_MACRO_WEIGHT
    signal_aggregator_lookback_days: int = DEFAULT_SIGNAL_AGGREGATOR_LOOKBACK_DAYS
    signal_aggregator_min_news_count: int = DEFAULT_SIGNAL_AGGREGATOR_MIN_NEWS_COUNT
    signal_aggregator_time_decay_half_life_days: float = DEFAULT_SIGNAL_AGGREGATOR_TIME_DECAY_HALF_LIFE_DAYS
    signal_aggregator_log_level: str = DEFAULT_SIGNAL_AGGREGATOR_LOG_LEVEL
    data_integrity_quotes_limit: int | None = None
    data_integrity_quotes_batch_size: int = DEFAULT_DATA_INTEGRITY_QUOTES_BATCH_SIZE
    data_integrity_earnings_from_date: str | None = None
    data_integrity_earnings_to_date: str | None = None
    data_integrity_earnings_limit: int | None = None
    data_integrity_earnings_sleep_seconds: float = DEFAULT_DATA_INTEGRITY_PROVIDER_SLEEP_SECONDS
    data_integrity_fundamentals_limit: int | None = None
    data_integrity_fundamentals_sleep_seconds: float = DEFAULT_DATA_INTEGRITY_PROVIDER_SLEEP_SECONDS
    data_integrity_fundamentals_log_every: int = DEFAULT_DATA_INTEGRITY_FUNDAMENTALS_LOG_EVERY


@dataclass(frozen=True, slots=True)
class PipelineStepDefinition:
    """Description d'une étape affichée dans la page Pipeline."""

    key: str
    num: str
    name: str
    desc: str
    tables: str
    deps: str
    account_usage: AccountUsage = "none"


@dataclass(frozen=True, slots=True)
class PipelineRunResult:
    """Résultat d'exécution d'une étape lancée depuis l'IHM."""

    step_key: str
    command: list[str]
    command_display: str
    returncode: int
    stdout: str
    stderr: str
    duration_seconds: float
    executed_at: str
    account_id: str | None = None

    def to_state(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class PipelineLiveSnapshot:
    """État live d'un sous-processus exécuté depuis l'IHM."""

    step_key: str
    command_display: str
    status: PipelineExecutionStatus
    stdout: str
    stderr: str
    duration_seconds: float
    executed_at: str
    account_id: str | None = None
    returncode: int | None = None
    stdout_lines: int = 0
    stderr_lines: int = 0


PIPELINE_STEPS: tuple[PipelineStepDefinition, ...] = (
    PipelineStepDefinition(
        key="import_alpaca_bar",
        num="1",
        name="Import Alpaca Bar",
        desc="Ingestion des barres OHLCV journalières depuis Alpaca Market Data.",
        tables="stock_bars",
        deps="—",
    ),
    PipelineStepDefinition(
        key="data_sanitizer_daily",
        num="2",
        name="Data Sanitizer Daily",
        desc="Nettoyage, alignement calendrier, détection d'anomalies sur les barres brutes.",
        tables="stock_bars_daily, cleaning_audit_latest, cleaning_audit_runs",
        deps="import_alpaca_bar",
    ),
    PipelineStepDefinition(
        key="stock_screener",
        num="3",
        name="Stock Screener",
        desc="Scores de base : liquidité 30j, force relative 6m vs SPY, range 10 ans.",
        tables="stock_scores",
        deps="data_sanitizer_daily",
    ),
    PipelineStepDefinition(
        key="sync_latest_quotes",
        num="4",
        name="Sync Latest Quotes",
        desc="Snapshot des dernières quotes Alpaca pour alimenter `stock_quote_snapshots` et le filtre de spread.",
        tables="stock_quote_snapshots",
        deps="stock_screener",
    ),
    PipelineStepDefinition(
        key="sync_earnings_calendar",
        num="5",
        name="Sync Earnings Calendar",
        desc="Synchronisation du calendrier earnings Finnhub pour alimenter `stock_earnings_calendar` et le blackout résultats.",
        tables="stock_earnings_calendar",
        deps="sync_latest_quotes",
    ),
    PipelineStepDefinition(
        key="alpha_scanner",
        num="6",
        name="Alpha Scanner",
        desc="Scoring avancé Minervini/VCP + neutralisation sectorielle + sélection Top N.",
        tables="stock_scores (update)",
        deps="sync_earnings_calendar",
    ),
    PipelineStepDefinition(
        key="sentiment_pipeline",
        num="7",
        name="Sentiment Pipeline",
        desc="Ingestion news → scoring FinBERT → features ticker/secteur journalières.",
        tables="ticker_daily_sentiment_features, sector_daily_sentiment_features",
        deps="alpha_scanner",
    ),
    PipelineStepDefinition(
        key="signal_aggregator",
        num="8",
        name="Signal Aggregator",
        desc="Fusion quant (75%) + sentiment ticker (15%) + macro sectoriel (10%) → final_score_sentiment.",
        tables="stock_scores (update final_score_sentiment)",
        deps="sentiment_pipeline",
    ),
    PipelineStepDefinition(
        key="ml_train",
        num="9",
        name="ML Train (Model Factory)",
        desc="Entraînement `modelFactory` par symbole candidat : LSTM+Attention, challengers locaux LightGBM/CatBoost, modèle global optionnel et sélection éventuelle du champion servi.",
        tables="model_registry, model_training_run, model_metrics, model_governance",
        deps="signal_aggregator (is_candidate=1)",
    ),
    PipelineStepDefinition(
        key="ml_predict",
        num="10",
        name="ML Predict",
        desc="Inférence `modelFactory` sur le champion sélectionné par symbole (LSTM, LightGBM, CatBoost ou global_model selon les artefacts disponibles). Quotidien, alimente le score de conviction du risk.",
        tables="model_predictions",
        deps="ml_train (modèle entraîné requis)",
    ),
    PipelineStepDefinition(
        key="risk_management",
        num="11",
        name="Risk Management",
        desc="Sizing ATR/Kelly, contraintes portefeuille, circuit breaker → portefeuille cible. Utilise les prédictions ML pour le score de conviction.",
        tables="risk_decisions, portfolio_targets",
        deps="ml_predict, signal_aggregator",
        account_usage="alpaca",
    ),
    PipelineStepDefinition(
        key="execution",
        num="12",
        name="Execution",
        desc="Run overnight canonique : snapshot des targets, requests, ordres broker, fills observés, reconstruction positions/lots, réconciliation actionnable et TCA. Photographie aussi l'état broker du compte.",
        tables="execution_runs, execution_targets_snapshot, execution_order_requests, execution_broker_orders, execution_broker_fills, execution_positions, execution_position_lots, execution_reconciliation_results, execution_events, broker_positions_snapshots, broker_account_snapshots",
        deps="run_risk",
        account_usage="alpaca",
    ),
    PipelineStepDefinition(
        key="corporate_actions_sync",
        num="13",
        name="Corporate Actions Sync",
        desc="Récupère les dividendes/splits depuis Alpaca uniquement pour les symboles détenus en portefeuille (après exécution du jour).",
        tables="corporate_actions_events",
        deps="execution (broker_positions_snapshots requis)",
        account_usage="alpaca",
    ),
    PipelineStepDefinition(
        key="corporate_actions_apply",
        num="14",
        name="Corporate Actions Apply",
        desc="Application des dividendes/splits sur les positions existantes. Se fait APRÈS la sync et l'exécution.",
        tables="corporate_actions_applications, portfolio_cash_ledger",
        deps="corporate_actions_sync",
        account_usage="alpaca",
    ),
)

PIPELINE_AUXILIARY_STEPS: tuple[PipelineStepDefinition, ...] = (
    PipelineStepDefinition(
        key="import_alpaca_assets",
        num="B1",
        name="Import univers Alpaca",
        desc="Bootstrap / rafraîchissement de l'univers `stock_metadata` depuis Alpaca.",
        tables="stock_metadata",
        deps="—",
    ),
    PipelineStepDefinition(
        key="update_sector",
        num="B2",
        name="Mise à jour fondamentaux",
        desc="Enrichit `stock_metadata` avec `sector` et `market_cap` via Finnhub pour les symboles encore incomplets.",
        tables="stock_metadata",
        deps="import_alpaca_assets (recommandé) ou univers déjà chargé",
    ),
)


def get_pipeline_steps() -> tuple[PipelineStepDefinition, ...]:
    return PIPELINE_STEPS


def get_pipeline_auxiliary_steps() -> tuple[PipelineStepDefinition, ...]:
    return PIPELINE_AUXILIARY_STEPS


def _normalize_trade_date(value: str | None) -> str | None:
    cleaned = (value or "").strip()
    return cleaned or None


def _normalize_run_id(value: str | None) -> str | None:
    cleaned = (value or "").strip()
    return cleaned or None


def _normalize_optional_date(value: str | None) -> str | None:
    cleaned = (value or "").strip()
    return cleaned or None


def _normalize_symbol(value: str | None, default: str) -> str:
    cleaned = (value or "").strip().upper()
    return cleaned or default


def _normalize_symbol_list(value: str | None) -> str | None:
    normalized = sorted({part.strip().upper() for part in (value or "").split(",") if part and part.strip()})
    return ",".join(normalized) if normalized else None


def is_gpu_available() -> bool:
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:
        return False


def build_pipeline_command(step_key: str, options: PipelineLaunchOptions) -> list[str]:
    """Construit la commande subprocess correspondant à une étape."""
    trade_date = _normalize_trade_date(options.trade_date)
    run_id = _normalize_run_id(options.execution_run_id)
    account_id = (options.account_id or "").strip() or None
    news_import_start_date = _normalize_optional_date(options.news_import_start_date)
    news_import_end_date = _normalize_optional_date(options.news_import_end_date)
    sentiment_start_utc = _normalize_optional_date(options.sentiment_start_utc)
    sentiment_end_utc = _normalize_optional_date(options.sentiment_end_utc)
    sentiment_symbols = _normalize_symbol_list(options.sentiment_symbols)
    earnings_from_date = _normalize_optional_date(options.data_integrity_earnings_from_date)
    earnings_to_date = _normalize_optional_date(options.data_integrity_earnings_to_date)
    screener_max_workers = options.screener_max_workers if options.screener_max_workers and options.screener_max_workers > 0 else None
    screener_benchmark_symbol = _normalize_symbol(options.screener_benchmark_symbol, DEFAULT_SCREENER_BENCHMARK_SYMBOL)
    selector_max_workers = options.selector_max_workers if options.selector_max_workers and options.selector_max_workers > 0 else None
    quotes_limit = options.data_integrity_quotes_limit if options.data_integrity_quotes_limit and options.data_integrity_quotes_limit > 0 else None
    earnings_limit = options.data_integrity_earnings_limit if options.data_integrity_earnings_limit and options.data_integrity_earnings_limit > 0 else None
    fundamentals_limit = options.data_integrity_fundamentals_limit if options.data_integrity_fundamentals_limit and options.data_integrity_fundamentals_limit > 0 else None

    if step_key == "import_alpaca_assets":
        return [sys.executable, "-u", "-m", "dataIntegrityEngine.import_alpaca_assets"]

    if step_key == "import_alpaca_bar":
        return [sys.executable, "-u", "-m", "dataIntegrityEngine.import_alpaca_bar"]

    if step_key == "update_sector":
        command = [
            sys.executable,
            "-u",
            "-m",
            "dataIntegrityEngine.update_sector",
            "--sleep-seconds",
            str(options.data_integrity_fundamentals_sleep_seconds),
            "--log-every",
            str(options.data_integrity_fundamentals_log_every),
        ]
        if fundamentals_limit is not None:
            command.extend(["--limit", str(fundamentals_limit)])
        return command

    if step_key == "corporate_actions_sync":
        # --portfolio-only : sync uniquement les symboles détenus en portefeuille
        # pas de --skip-existing : on re-interroge Alpaca à chaque fois pour ne rater aucun nouvel événement
        command = [sys.executable, "-u", "-m", "corporate_actions", "sync", "--portfolio-only"]
        if account_id:
            command.extend(["--account", account_id])
        return command

    if step_key == "data_sanitizer_daily":
        return [sys.executable, "-u", "-m", "dataIntegrityEngine.data_sanitizer_daily"]

    if step_key == "stock_screener":
        command = [
            sys.executable,
            "-u",
            "-m",
            "screener.stock_screener",
            "--chunk-size",
            str(options.screener_chunk_size),
            "--benchmark",
            screener_benchmark_symbol,
            "--liquidity-threshold-usd",
            str(options.screener_liquidity_threshold_usd),
            "--min-relative-strength-index",
            str(options.screener_min_relative_strength_index),
            "--historical-range-lookback-days",
            str(options.screener_historical_range_lookback_days),
            "--min-historical-range-score",
            str(options.screener_min_historical_range_score),
            "--first-pass-window-days",
            str(options.screener_first_pass_window_days),
        ]
        if screener_max_workers is not None:
            command.extend(["--max-workers", str(screener_max_workers)])
        if not options.screener_enable_two_pass_loading:
            command.append("--disable-two-pass-loading")
        return command

    if step_key == "sync_latest_quotes":
        command = [
            sys.executable,
            "-u",
            "-m",
            "dataIntegrityEngine.sync_latest_quotes",
            "--batch-size",
            str(options.data_integrity_quotes_batch_size),
        ]
        if quotes_limit is not None:
            command.extend(["--limit", str(quotes_limit)])
        return command

    if step_key == "sync_earnings_calendar":
        command = [
            sys.executable,
            "-u",
            "-m",
            "dataIntegrityEngine.sync_earnings_calendar",
            "--sleep-seconds",
            str(options.data_integrity_earnings_sleep_seconds),
        ]
        if earnings_from_date:
            command.extend(["--from-date", earnings_from_date])
        if earnings_to_date:
            command.extend(["--to-date", earnings_to_date])
        if earnings_limit is not None:
            command.extend(["--limit", str(earnings_limit)])
        return command

    if step_key == "alpha_scanner":
        command = [
            sys.executable,
            "-u",
            "-m",
            "selector.alpha_scanner",
            "--chunk-size",
            str(options.selector_chunk_size),
            "--selection-size",
            str(options.selector_selection_size),
            "--liquidity-threshold",
            str(options.selector_liquidity_threshold),
            "--min-close",
            str(options.selector_min_close),
            "--max-volatility-ratio",
            str(options.selector_max_volatility_ratio),
            "--min-relative-strength-index",
            str(options.selector_min_relative_strength_index),
            "--min-high-52w-proximity",
            str(options.selector_min_high_52w_proximity),
            "--min-weekly-trend-score",
            str(options.selector_min_weekly_trend_score),
            "--min-atr-pct-20",
            str(options.selector_min_atr_pct_20),
            "--max-atr-pct-20",
            str(options.selector_max_atr_pct_20),
            "--min-market-cap",
            str(options.selector_min_market_cap),
            "--min-beta-126",
            str(options.selector_min_beta_126),
            "--max-spread-bps",
            str(options.selector_max_spread_bps),
            "--earnings-blackout-days",
            str(options.selector_earnings_blackout_days),
            "--max-anomaly-count",
            str(options.selector_max_anomaly_count),
            "--sector-cap-ratio",
            str(options.selector_sector_cap_ratio),
            "--log-level",
            str(options.selector_log_level or DEFAULT_SELECTOR_LOG_LEVEL).upper(),
        ]
        if selector_max_workers is not None:
            command.extend(["--max-workers", str(selector_max_workers)])
        return command

    if step_key == "sentiment_pipeline":
        command = [sys.executable, "-u", "-m", "event_sentiment"]
        if sentiment_start_utc:
            command.extend(["--start-utc", sentiment_start_utc])
        if sentiment_end_utc:
            command.extend(["--end-utc", sentiment_end_utc])
        if sentiment_symbols:
            command.extend(["--symbols", sentiment_symbols])
        return command

    if step_key == "import_news":
        if news_import_start_date is None:
            raise ValueError("La date de début est obligatoire pour l'import des news.")
        command = [
            sys.executable,
            "-u",
            str(PROJECT_ROOT / "event_sentiment" / "importe_news.py"),
            "--start-date",
            news_import_start_date,
        ]
        if news_import_end_date:
            command.extend(["--end-date", news_import_end_date])
        return command

    if step_key == "signal_aggregator":
        command = [
            sys.executable,
            "-u",
            "-m",
            "event_sentiment.signal_aggregator",
            "--sentiment-weight",
            str(options.signal_aggregator_sentiment_weight),
            "--macro-weight",
            str(options.signal_aggregator_macro_weight),
            "--lookback-days",
            str(options.signal_aggregator_lookback_days),
            "--min-news-count",
            str(options.signal_aggregator_min_news_count),
            "--time-decay-half-life-days",
            str(options.signal_aggregator_time_decay_half_life_days),
            "--log-level",
            str(options.signal_aggregator_log_level or DEFAULT_SIGNAL_AGGREGATOR_LOG_LEVEL).upper(),
        ]
        if trade_date:
            command.extend(["--trade-date", trade_date])
        if options.signal_aggregator_all_symbols:
            command.append("--all-symbols")
        return command

    if step_key == "ml_train":
        command = [
            sys.executable,
            "-u",
            "-m",
            "modelFactory",
            "--mode",
            "train",
            "--accelerator",
            options.ml_accelerator,
        ]
        if options.ml_include_sentiment:
            command.append("--include-sentiment")
        if options.ml_enable_lightgbm:
            command.append("--compare-lightgbm")
        if options.ml_enable_catboost:
            command.append("--enable-catboost")
        if options.ml_enable_global_model:
            command.extend(["--enable-global-model", "--global-model-name", options.ml_global_model_name])
        if options.ml_enable_cross_sectional:
            command.append("--enable-cross-sectional")
        if options.ml_select_champion:
            command.extend(["--select-champion", "--champion-selection-metric", options.ml_champion_selection_metric])
        if options.ml_optimize_thresholds:
            command.append("--optimize-thresholds")
        if options.ml_optimize_target:
            command.append("--optimize-target")
        return command

    if step_key == "ml_predict":
        return [
            sys.executable,
            "-u",
            "-m",
            "modelFactory",
            "--mode",
            "predict",
            "--accelerator",
            options.ml_accelerator,
        ]

    if step_key == "risk_management":
        command = [
            sys.executable,
            "-u",
            "-m",
            "risk_management",
            "--account-equity",
            str(options.risk_account_equity),
        ]
        if trade_date:
            command.extend(["--trade-date", trade_date])
        if account_id:
            command.extend(["--account", account_id])
        return command

    if step_key == "execution":
        command = [sys.executable, "-u", str(PROJECT_ROOT / "run_execution.py"), options.execution_mode]
        if trade_date:
            command.extend(["--date", trade_date])
        if run_id:
            command.extend(["--run-id", run_id])
        if options.allow_outside_rth:
            command.append("--allow-outside-rth")
        if options.auto_rebalance:
            command.append("--auto-rebalance")
        command.extend(["--account-type", options.execution_account_type])
        command.extend(["--pdt-rule", options.execution_pdt_rule])
        if options.execution_swing_only:
            command.append("--swing-only")
        if account_id:
            command.extend(["--account", account_id])
        return command

    if step_key == "corporate_actions_apply":
        command = [sys.executable, "-u", "-m", "corporate_actions", "apply"]
        if trade_date:
            command.extend(["--as-of", trade_date])
        if account_id:
            command.extend(["--account", account_id])
        return command

    raise KeyError(f"Étape de pipeline inconnue : {step_key}")


def format_command_for_display(command: list[str]) -> str:
    return subprocess.list2cmdline(command)


def build_subprocess_env(
    db_config: dict[str, str | None] | None = None,
    base_env: dict[str, str] | None = None,
) -> dict[str, str]:
    """Construit l'environnement d'un sous-processus déclenché depuis l'IHM."""
    env = dict(base_env or os.environ)

    pythonpath_entries = [str(PROJECT_ROOT)]
    existing_pythonpath = env.get("PYTHONPATH")
    if existing_pythonpath:
        pythonpath_entries.append(existing_pythonpath)
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_entries)
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")

    if db_config:
        host = db_config.get("host")
        name = db_config.get("name")
        user = db_config.get("user")
        password = db_config.get("password")
        if host:
            env["DB_HOST"] = str(host)
        if name:
            env["DB_NAME"] = str(name)
        if user:
            env["LOGIN_DB"] = str(user)
        if password:
            env["PASSWORD_DB"] = str(password)

    return env


def _build_live_snapshot(
    *,
    step_key: str,
    command_display: str,
    status: PipelineExecutionStatus,
    stdout_lines: list[str],
    stderr_lines: list[str],
    started_at: datetime,
    started_perf: float,
    account_id: str | None,
    returncode: int | None = None,
) -> PipelineLiveSnapshot:
    return PipelineLiveSnapshot(
        step_key=step_key,
        command_display=command_display,
        status=status,
        stdout="".join(stdout_lines),
        stderr="".join(stderr_lines),
        duration_seconds=round(time.perf_counter() - started_perf, 2),
        executed_at=started_at.isoformat(timespec="seconds"),
        account_id=account_id,
        returncode=returncode,
        stdout_lines=len(stdout_lines),
        stderr_lines=len(stderr_lines),
    )


def _stream_subprocess(
    command: list[str],
    *,
    step_key: str,
    account_id: str | None,
    env: dict[str, str],
    cwd: Path,
    timeout_seconds: int | None = None,
    on_update: Callable[[PipelineLiveSnapshot], None] | None = None,
) -> PipelineRunResult:
    command_display = format_command_for_display(command)
    started_at = datetime.now()
    started_perf = time.perf_counter()
    stdout_lines: list[str] = []
    stderr_lines: list[str] = []
    events: queue.Queue[tuple[str, str]] = queue.Queue()

    process = subprocess.Popen(
        command,
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    def _reader(stream: subprocess.PIPE | None, stream_name: str) -> None:  # type: ignore[type-arg]
        if stream is None:
            return
        try:
            for line in iter(stream.readline, ""):
                events.put((stream_name, line))
        finally:
            stream.close()

    stdout_thread = threading.Thread(target=_reader, args=(process.stdout, "stdout"), daemon=True)
    stderr_thread = threading.Thread(target=_reader, args=(process.stderr, "stderr"), daemon=True)
    stdout_thread.start()
    stderr_thread.start()

    if on_update is not None:
        on_update(
            _build_live_snapshot(
                step_key=step_key,
                command_display=command_display,
                status="starting",
                stdout_lines=stdout_lines,
                stderr_lines=stderr_lines,
                started_at=started_at,
                started_perf=started_perf,
                account_id=account_id,
            )
        )

    timed_out = False
    last_push = 0.0

    while True:
        drained = False
        while True:
            try:
                stream_name, line = events.get_nowait()
            except queue.Empty:
                break
            drained = True
            if stream_name == "stdout":
                stdout_lines.append(line)
            else:
                stderr_lines.append(line)

        elapsed = time.perf_counter() - started_perf
        current_returncode = process.poll()

        if timeout_seconds is not None and elapsed > timeout_seconds and current_returncode is None:
            process.kill()
            timed_out = True
            stderr_lines.append("\nTimeout d'exécution dépassé.\n")
            current_returncode = -2

        if on_update is not None and (drained or (time.perf_counter() - last_push) >= 0.5):
            live_status: PipelineExecutionStatus = "timeout" if timed_out else "running"
            if current_returncode is not None and not timed_out:
                live_status = "completed" if current_returncode == 0 else "failed"
            on_update(
                _build_live_snapshot(
                    step_key=step_key,
                    command_display=command_display,
                    status=live_status,
                    stdout_lines=stdout_lines,
                    stderr_lines=stderr_lines,
                    started_at=started_at,
                    started_perf=started_perf,
                    account_id=account_id,
                    returncode=current_returncode,
                )
            )
            last_push = time.perf_counter()

        if current_returncode is not None and events.empty() and not stdout_thread.is_alive() and not stderr_thread.is_alive():
            break

        time.sleep(0.1)

    process.wait()
    final_returncode = -2 if timed_out else process.returncode

    if on_update is not None:
        final_status: PipelineExecutionStatus
        if timed_out:
            final_status = "timeout"
        else:
            final_status = "completed" if final_returncode == 0 else "failed"
        on_update(
            _build_live_snapshot(
                step_key=step_key,
                command_display=command_display,
                status=final_status,
                stdout_lines=stdout_lines,
                stderr_lines=stderr_lines,
                started_at=started_at,
                started_perf=started_perf,
                account_id=account_id,
                returncode=final_returncode,
            )
        )

    return PipelineRunResult(
        step_key=step_key,
        command=command,
        command_display=command_display,
        returncode=final_returncode,
        stdout="".join(stdout_lines),
        stderr="".join(stderr_lines),
        duration_seconds=round(time.perf_counter() - started_perf, 2),
        executed_at=started_at.isoformat(timespec="seconds"),
        account_id=account_id,
    )


def run_pipeline_step(
    step_key: str,
    options: PipelineLaunchOptions,
    *,
    db_config: dict[str, str | None] | None = None,
    timeout_seconds: int | None = None,
    on_update: Callable[[PipelineLiveSnapshot], None] | None = None,
) -> PipelineRunResult:
    """Exécute une étape de pipeline et capture stdout/stderr."""
    command = build_pipeline_command(step_key, options)
    env = build_subprocess_env(db_config=db_config)
    try:
        return _stream_subprocess(
            command,
            step_key=step_key,
            account_id=options.account_id,
            env=env,
            cwd=PROJECT_ROOT,
            timeout_seconds=timeout_seconds,
            on_update=on_update,
        )
    except Exception as exc:
        return PipelineRunResult(
            step_key=step_key,
            command=command,
            command_display=format_command_for_display(command),
            returncode=-1,
            stdout="",
            stderr=str(exc),
            duration_seconds=0.0,
            executed_at=datetime.now().isoformat(timespec="seconds"),
            account_id=options.account_id,
        )

