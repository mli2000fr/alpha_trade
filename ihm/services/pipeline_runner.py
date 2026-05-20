"""Services d'orchestration légère des pipelines depuis l'IHM Streamlit."""
from __future__ import annotations

import os
import queue
import re
import subprocess
import sys
import threading
import time
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Callable, Literal

from event_sentiment.config import EventSentimentConfig
from event_sentiment.signal_aggregator import SentimentBoostConfig
from screener.models import ScreenerConfig
from selector.strict_filter_profiles import STRICT_SWING_CASH_FILTERS

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCREENER_CONFIG = ScreenerConfig.strict_swing_cash()


def _resolve_bars_provider_for_ihm() -> str:
    """Lit ``market_data.bars_provider`` (Phase 6 plan_eodhd.md §5.6).

    Retourne ``'alpaca'`` (défaut) ou ``'eodhd'``. Échec config -> ``'alpaca'``
    pour préserver le comportement historique de l'IHM.
    """
    try:
        from common.config_loader import load_config
        cfg = load_config() or {}
    except Exception:
        return "alpaca"
    return str(((cfg.get("market_data") or {}).get("bars_provider", "alpaca"))).lower()
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
DEFAULT_EVENT_SENTIMENT_PENDING_LIMIT = DEFAULT_EVENT_SENTIMENT_CONFIG.sentiment_pending_limit
DEFAULT_EVENT_SENTIMENT_PENDING_MAX_BATCHES_PER_RUN = (
    DEFAULT_EVENT_SENTIMENT_CONFIG.sentiment_pending_max_batches_per_run
)
DEFAULT_EVENT_SENTIMENT_FINBERT_BATCH_SIZE = DEFAULT_EVENT_SENTIMENT_CONFIG.finbert_batch_size
DEFAULT_EVENT_SENTIMENT_FEATURE_FLUSH_EVERY_N_BATCHES = (
    DEFAULT_EVENT_SENTIMENT_CONFIG.feature_flush_every_n_pending_batches
)
RECOMMENDED_EVENT_SENTIMENT_PENDING_LIMIT = 20000
RECOMMENDED_EVENT_SENTIMENT_PENDING_MAX_BATCHES_PER_RUN = 30
RECOMMENDED_EVENT_SENTIMENT_FINBERT_BATCH_SIZE = 64
DEFAULT_SIGNAL_AGGREGATOR_CONFIG = SentimentBoostConfig()
DEFAULT_SIGNAL_AGGREGATOR_SENTIMENT_WEIGHT = DEFAULT_SIGNAL_AGGREGATOR_CONFIG.sentiment_weight
DEFAULT_SIGNAL_AGGREGATOR_MACRO_WEIGHT = DEFAULT_SIGNAL_AGGREGATOR_CONFIG.macro_sector_weight
DEFAULT_SIGNAL_AGGREGATOR_LOOKBACK_DAYS = DEFAULT_SIGNAL_AGGREGATOR_CONFIG.lookback_days
DEFAULT_SIGNAL_AGGREGATOR_MIN_NEWS_COUNT = DEFAULT_SIGNAL_AGGREGATOR_CONFIG.min_news_count
DEFAULT_SIGNAL_AGGREGATOR_TIME_DECAY_HALF_LIFE_DAYS = DEFAULT_SIGNAL_AGGREGATOR_CONFIG.time_decay_half_life_days
DEFAULT_SIGNAL_AGGREGATOR_LOG_LEVEL = "INFO"
DEFAULT_DATA_INTEGRITY_QUOTES_BATCH_SIZE = 200
DEFAULT_DATA_INTEGRITY_PROVIDER_SLEEP_SECONDS = 1.1
DEFAULT_DATA_INTEGRITY_EARNINGS_LOG_EVERY = 25
DEFAULT_DATA_INTEGRITY_EARNINGS_BATCH_SIZE = 50
DEFAULT_DATA_INTEGRITY_EARNINGS_RESUME = True
DEFAULT_DATA_INTEGRITY_FUNDAMENTALS_LOG_EVERY = 50
DEFAULT_EODHD_WRITE_COMMIT_EVERY_SYMBOLS = 100
DEFAULT_EODHD_ENABLE_STOOQ_CROSS_CHECK = False

# --- Défauts swing trade (cf. prompt/refactor/audit_ihm_pipeline_options.md) ---
# Risk management — sizing prudent compte cash 100k$
DEFAULT_RISK_PER_TRADE_PCT = 0.01            # 1 % du capital risqué par trade
DEFAULT_RISK_MAX_POSITIONS = 15              # 15 positions max (vs 20 backend)
DEFAULT_RISK_MAX_POSITION_WEIGHT = 0.08      # 8 % max par ligne
DEFAULT_RISK_MAX_SECTOR_WEIGHT = 0.30        # 30 % max par secteur
DEFAULT_RISK_MIN_POSITION_NOTIONAL = 500.0   # ticket minimum en dollars
DEFAULT_RISK_SCORE_WEIGHT = 0.40             # poids final_score dans la conviction
DEFAULT_RISK_PREDICTION_WEIGHT = 0.60        # poids ML predict dans la conviction
DEFAULT_RISK_CORRELATION_THRESHOLD = 0.80
DEFAULT_RISK_CORRELATION_LOOKBACK_DAYS = 60
DEFAULT_RISK_CORRELATION_MIN_OVERLAP = 40
DEFAULT_RISK_ENABLE_KELLY = False
DEFAULT_RISK_PAYOFF_RATIO = 1.5
DEFAULT_RISK_KELLY_FRACTION_MULTIPLIER = 0.25
DEFAULT_RISK_LOG_LEVEL = "INFO"
# Execution — swing cash batch
DEFAULT_EXEC_SUBMISSION_WINDOW = "both"      # post_close + pre_open (batch quotidien)
DEFAULT_EXEC_TAKE_PROFIT_PCT = 0.08
DEFAULT_EXEC_TRAILING_STOP_PCT = 0.05
# Sprint 2026-05 — SL dédié aux achats manuels orphelins adoptés par le watcher.
DEFAULT_EXEC_MANUAL_BUY_SL_PCT = 0.05
DEFAULT_EXEC_TRAILING_TRIGGER = "multiple_r"
DEFAULT_EXEC_TRAILING_R_MULTIPLE = 1.0
DEFAULT_EXEC_TRAILING_PROFIT_PCT = 0.03
# ML train — cible swing cash + walk-forward
DEFAULT_ML_TARGET_MODE = "swing_cash"
DEFAULT_ML_FORECAST_HORIZON = 5              # 5 jours = horizon swing typique
DEFAULT_ML_TARGET_UP_THRESHOLD = 0.02        # +2 % cible long
DEFAULT_ML_TARGET_DOWN_THRESHOLD = -0.01
DEFAULT_ML_DECISION_THRESHOLD = 0.55
DEFAULT_ML_CALIBRATION_METHOD = "platt"
DEFAULT_ML_FEATURE_SET = "v1"
DEFAULT_ML_MAX_WORKERS = 4
DEFAULT_ML_MAX_EPOCHS = 50
DEFAULT_ML_WALKFORWARD = True                # walk-forward activé par défaut en swing prod
DEFAULT_ML_WF_MIN_TRAIN_SIZE = 504
DEFAULT_ML_WF_VAL_SIZE = 126
DEFAULT_ML_WF_TEST_SIZE = 126
DEFAULT_ML_WF_STEP_SIZE = 126
DEFAULT_ML_WF_MAX_SPLITS = 3
DEFAULT_ML_LOG_LEVEL = "INFO"
DEFAULT_ML_DEBUG_TRAIN = False
DEFAULT_ML_HEARTBEAT_INTERVAL_SECONDS = 60.0
DEFAULT_ML_WATCHDOG_TIMEOUT_SECONDS = 0
RECOMMENDED_ML_PROD_SWING_ACCELERATOR = "auto"
RECOMMENDED_ML_PROD_SWING_LOG_LEVEL = DEFAULT_ML_LOG_LEVEL
RECOMMENDED_ML_PROD_SWING_DEBUG_TRAIN = DEFAULT_ML_DEBUG_TRAIN
RECOMMENDED_ML_PROD_SWING_MAX_WORKERS = DEFAULT_ML_MAX_WORKERS
RECOMMENDED_ML_PROD_SWING_WALKFORWARD = DEFAULT_ML_WALKFORWARD
RECOMMENDED_ML_PROD_SWING_MAX_EPOCHS = DEFAULT_ML_MAX_EPOCHS
RECOMMENDED_ML_PROD_SWING_HEARTBEAT_INTERVAL_SECONDS = DEFAULT_ML_HEARTBEAT_INTERVAL_SECONDS
RECOMMENDED_ML_PROD_SWING_WATCHDOG_TIMEOUT_SECONDS = DEFAULT_ML_WATCHDOG_TIMEOUT_SECONDS
RECOMMENDED_ML_DEBUG_RAPIDE_ACCELERATOR = "cpu"
RECOMMENDED_ML_DEBUG_TRAIN_LOG_LEVEL = "DEBUG"
RECOMMENDED_ML_DEBUG_TRAIN_DEBUG_TRAIN = True
RECOMMENDED_ML_DEBUG_TRAIN_MAX_WORKERS = 1
RECOMMENDED_ML_DEBUG_TRAIN_WALKFORWARD = False
RECOMMENDED_ML_DEBUG_TRAIN_MAX_EPOCHS = 10
RECOMMENDED_ML_DEBUG_TRAIN_HEARTBEAT_INTERVAL_SECONDS = 30.0
RECOMMENDED_ML_DEBUG_TRAIN_WATCHDOG_TIMEOUT_SECONDS = 300
RECOMMENDED_ML_DEBUG_GPU_ACCELERATOR = "gpu"
RECOMMENDED_ML_DEBUG_GPU_LOG_LEVEL = RECOMMENDED_ML_DEBUG_TRAIN_LOG_LEVEL
RECOMMENDED_ML_DEBUG_GPU_DEBUG_TRAIN = RECOMMENDED_ML_DEBUG_TRAIN_DEBUG_TRAIN
RECOMMENDED_ML_DEBUG_GPU_MAX_WORKERS = RECOMMENDED_ML_DEBUG_TRAIN_MAX_WORKERS
RECOMMENDED_ML_DEBUG_GPU_WALKFORWARD = RECOMMENDED_ML_DEBUG_TRAIN_WALKFORWARD
RECOMMENDED_ML_DEBUG_GPU_MAX_EPOCHS = RECOMMENDED_ML_DEBUG_TRAIN_MAX_EPOCHS
RECOMMENDED_ML_DEBUG_GPU_HEARTBEAT_INTERVAL_SECONDS = RECOMMENDED_ML_DEBUG_TRAIN_HEARTBEAT_INTERVAL_SECONDS
RECOMMENDED_ML_DEBUG_GPU_WATCHDOG_TIMEOUT_SECONDS = RECOMMENDED_ML_DEBUG_TRAIN_WATCHDOG_TIMEOUT_SECONDS
DEFAULT_ML_MIN_ACTION_RATE = 0.03
DEFAULT_ML_MAX_ACTION_RATE = 0.20            # plus prudent que 0.35 backend
DEFAULT_ML_MIN_PRECISION_LONG = 0.55         # plus exigeant que 0.52 backend
# ML — hyperparams avancés (alignés CLI modelFactory)
DEFAULT_ML_SEQUENCE_LENGTH = 60
DEFAULT_ML_BATCH_SIZE = 64
DEFAULT_ML_HIDDEN_SIZE = 128
DEFAULT_ML_ARTIFACTS_DIR = "artifacts/models"
DEFAULT_ML_BENCHMARK_SYMBOL = "SPY"
DEFAULT_ML_DEFAULT_CHAMPION = "lstm_attention"
DEFAULT_ML_MODE = "rebuild-missing"
DEFAULT_ML_TRAINING_START_DATE = "2020-01-01"
DEFAULT_ML_INCLUDE_SELECTOR_CONTEXT = False
DEFAULT_ML_SELECTOR_UNIVERSE_SIGNAL_MODES: tuple[str, ...] = ()
DEFAULT_ML_SELECTOR_UNIVERSE_MAX_CANDIDATE_RANK: int | None = None
DEFAULT_ML_SELECTOR_UNIVERSE_EXCLUDE_EARNINGS_BLACKOUT = False
DEFAULT_ML_CROSS_SECTIONAL_MIN_UNIVERSE = 20
DEFAULT_ML_CALIBRATION_MIN_SAMPLES = 64
DEFAULT_ML_CALIBRATION_MAX_ITER = 100
DEFAULT_ML_LGBM_MAX_DEPTH = 4
DEFAULT_ML_LGBM_N_ESTIMATORS = 200
DEFAULT_ML_LGBM_LEARNING_RATE = 0.05
DEFAULT_ML_CATBOOST_DEPTH = 6
DEFAULT_ML_CATBOOST_ITERATIONS = 300
DEFAULT_ML_CATBOOST_LEARNING_RATE = 0.03
# ML — grilles candidate (resserrées swing 2-10 j)
DEFAULT_ML_CANDIDATE_HORIZONS: tuple[int, ...] = (3, 5, 7, 10)
DEFAULT_ML_CANDIDATE_UP_THRESHOLDS: tuple[float, ...] = (0.015, 0.02, 0.03)
DEFAULT_ML_CANDIDATE_DOWN_THRESHOLDS: tuple[float, ...] = (-0.01, -0.015)
DEFAULT_ML_CANDIDATE_DECISION_THRESHOLDS: tuple[float, ...] = (0.55, 0.60, 0.65)
DEFAULT_ML_MIN_TRADES_FRACTION = 0.15
# Execution — protection transition (timeout/poll trigger trailing)
DEFAULT_EXEC_PROTECTION_TRANSITION_TIMEOUT_SECONDS = 120
DEFAULT_EXEC_PROTECTION_TRANSITION_POLL_INTERVAL_SECONDS = 5.0
DEFAULT_EXEC_DEBUG = False
# Selector — alpha scanner stage 2
DEFAULT_SELECTOR_REQUIRE_ABOVE_MA200 = True
# Corporate actions sync — fenêtre custom + batching (cf. audit_ihm_pipeline_options)
DEFAULT_CA_SKIP_EXISTING = False
DEFAULT_CA_USE_CUSTOM_WINDOW = False
DEFAULT_CA_WINDOW_LOOKBACK_DAYS = 7  # J-7 → trade_date par défaut quand custom-window activé
DEFAULT_CA_BATCH_SIZE = 25

AccountUsage = Literal["none", "alpaca"]
MLAccelerator = Literal["auto", "cpu", "gpu"]
MLGlobalModelName = Literal["catboost", "lightgbm"]
MLChampionMetric = Literal["selection_score", "business_score", "auc"]
MLTargetMode = Literal["binary", "swing_cash"]
MLFeatureSet = Literal["v1", "expert"]
MLCalibrationMethod = Literal["none", "platt"]
MLDefaultChampion = Literal["lstm_attention", "lightgbm", "catboost", "global_model"]
MLMode = Literal["rebuild-all", "rebuild-missing", "refresh-stale"]
MLTrainSymbolSource = Literal["candidates", "stock_bars_daily"]
NewsImportSymbolSource = Literal[
    "stock_scores",
    "stock_scores_history",
    "stock_scores_all",
    "candidates",
    "stock_bars_daily",
]
ExecutionSubmissionWindow = Literal["post_close", "pre_open", "both"]
ExecutionTrailingTrigger = Literal["multiple_r", "profit_pct"]
PipelineExecutionStatus = Literal["starting", "running", "completed", "failed", "timeout"]
WorkflowStartStep = Literal["1", "3"]
SentimentScoringMode = Literal["standard_only", "contextual_only", "standard_and_contextual"]
FundamentalsProvider = Literal["yahoo_finance", "eodhd", "finnhub"]


@dataclass(frozen=True, slots=True)
class PipelineLaunchOptions:
    """Options saisies dans l'IHM pour lancer une étape du pipeline."""

    account_id: str | None = None
    trade_date: str | None = None
    # Si True, écrase ``trade_date`` au lancement par le snapshot_date le plus
    # récent <= trade_date présent dans ``stock_scores_history`` (avec
    # is_candidate=1). Permet de continuer un workflow démarré la veille même
    # après réouverture de la session Streamlit (qui ré-initialise trade_date à
    # date.today()). Décochez pour forcer la date du jour.
    force_trade_date_to_latest_snapshot: bool = True
    risk_account_equity: float = 100_000.0
    execution_mode: Literal["simulate", "paper", "live"] = "simulate"
    execution_run_id: str | None = None
    allow_outside_rth: bool = False
    auto_rebalance: bool = False
    # Défauts swing cash : compte cash + PDT off + swing only (cf. audit_ihm_pipeline_options.md P1)
    execution_account_type: Literal["margin", "cash"] = "cash"
    execution_pdt_rule: Literal["auto", "off"] = "off"
    execution_swing_only: bool = True
    # Stratégie de protection (sortie) — P1
    execution_submission_window: ExecutionSubmissionWindow = "both"
    execution_take_profit_pct: float = DEFAULT_EXEC_TAKE_PROFIT_PCT
    execution_trailing_stop_pct: float = DEFAULT_EXEC_TRAILING_STOP_PCT
    # SL dédié aux achats manuels orphelins (cf. watcher) — propagé uniquement
    # à ``run_execution_protection_watch.py`` via ``build_watcher_command``.
    execution_manual_buy_stop_loss_pct: float = DEFAULT_EXEC_MANUAL_BUY_SL_PCT
    execution_trailing_trigger: ExecutionTrailingTrigger = "multiple_r"
    execution_trailing_r_multiple: float = DEFAULT_EXEC_TRAILING_R_MULTIPLE
    execution_trailing_profit_pct: float = DEFAULT_EXEC_TRAILING_PROFIT_PCT
    # Execution — transition trigger trailing (avancé) + debug
    execution_protection_transition_timeout_seconds: int = DEFAULT_EXEC_PROTECTION_TRANSITION_TIMEOUT_SECONDS
    execution_protection_transition_poll_interval_seconds: float = DEFAULT_EXEC_PROTECTION_TRANSITION_POLL_INTERVAL_SECONDS
    execution_debug: bool = DEFAULT_EXEC_DEBUG
    ml_accelerator: MLAccelerator = "auto"
    ml_include_sentiment: bool = True
    ml_include_selector_context: bool = DEFAULT_ML_INCLUDE_SELECTOR_CONTEXT
    ml_enable_lightgbm: bool = True
    ml_enable_catboost: bool = True
    ml_enable_global_model: bool = False
    ml_global_model_name: MLGlobalModelName = "catboost"
    ml_enable_cross_sectional: bool = False
    ml_select_champion: bool = True
    ml_champion_selection_metric: MLChampionMetric = "selection_score"
    ml_optimize_thresholds: bool = True
    ml_optimize_target: bool = False
    # ML — cible swing cash + horizon + walk-forward (P1)
    ml_target_mode: MLTargetMode = DEFAULT_ML_TARGET_MODE  # type: ignore[assignment]
    ml_forecast_horizon: int = DEFAULT_ML_FORECAST_HORIZON
    ml_target_up_threshold: float = DEFAULT_ML_TARGET_UP_THRESHOLD
    ml_target_down_threshold: float = DEFAULT_ML_TARGET_DOWN_THRESHOLD
    ml_decision_threshold: float = DEFAULT_ML_DECISION_THRESHOLD
    ml_calibration_method: MLCalibrationMethod = DEFAULT_ML_CALIBRATION_METHOD  # type: ignore[assignment]
    ml_feature_set: MLFeatureSet = DEFAULT_ML_FEATURE_SET  # type: ignore[assignment]
    ml_max_workers: int = DEFAULT_ML_MAX_WORKERS
    ml_max_epochs: int = DEFAULT_ML_MAX_EPOCHS
    ml_walkforward: bool = DEFAULT_ML_WALKFORWARD
    ml_wf_min_train_size: int = DEFAULT_ML_WF_MIN_TRAIN_SIZE
    ml_wf_val_size: int = DEFAULT_ML_WF_VAL_SIZE
    ml_wf_test_size: int = DEFAULT_ML_WF_TEST_SIZE
    ml_wf_step_size: int = DEFAULT_ML_WF_STEP_SIZE
    ml_wf_max_splits: int = DEFAULT_ML_WF_MAX_SPLITS
    ml_log_level: str = DEFAULT_ML_LOG_LEVEL
    ml_debug_train: bool = DEFAULT_ML_DEBUG_TRAIN
    ml_heartbeat_interval_seconds: float = DEFAULT_ML_HEARTBEAT_INTERVAL_SECONDS
    ml_watchdog_timeout_seconds: int = DEFAULT_ML_WATCHDOG_TIMEOUT_SECONDS
    ml_min_action_rate: float = DEFAULT_ML_MIN_ACTION_RATE
    ml_max_action_rate: float = DEFAULT_ML_MAX_ACTION_RATE
    ml_min_precision_long: float = DEFAULT_ML_MIN_PRECISION_LONG
    # ML — hyperparams avancés (architecture, boosters, grilles candidate)
    ml_sequence_length: int = DEFAULT_ML_SEQUENCE_LENGTH
    ml_batch_size: int = DEFAULT_ML_BATCH_SIZE
    ml_hidden_size: int = DEFAULT_ML_HIDDEN_SIZE
    ml_mode: MLMode = DEFAULT_ML_MODE
    ml_training_start_date: str = DEFAULT_ML_TRAINING_START_DATE
    ml_train_symbol_source: MLTrainSymbolSource = "candidates"
    ml_selector_universe_signal_modes: tuple[str, ...] = DEFAULT_ML_SELECTOR_UNIVERSE_SIGNAL_MODES
    ml_selector_universe_max_candidate_rank: int | None = DEFAULT_ML_SELECTOR_UNIVERSE_MAX_CANDIDATE_RANK
    ml_selector_universe_exclude_earnings_blackout: bool = DEFAULT_ML_SELECTOR_UNIVERSE_EXCLUDE_EARNINGS_BLACKOUT
    ml_artifacts_dir: str = DEFAULT_ML_ARTIFACTS_DIR
    ml_benchmark_symbol: str = DEFAULT_ML_BENCHMARK_SYMBOL
    ml_default_champion: MLDefaultChampion = DEFAULT_ML_DEFAULT_CHAMPION  # type: ignore[assignment]
    ml_cross_sectional_min_universe: int = DEFAULT_ML_CROSS_SECTIONAL_MIN_UNIVERSE
    ml_calibration_min_samples: int = DEFAULT_ML_CALIBRATION_MIN_SAMPLES
    ml_calibration_max_iter: int = DEFAULT_ML_CALIBRATION_MAX_ITER
    ml_lgbm_max_depth: int = DEFAULT_ML_LGBM_MAX_DEPTH
    ml_lgbm_n_estimators: int = DEFAULT_ML_LGBM_N_ESTIMATORS
    ml_lgbm_learning_rate: float = DEFAULT_ML_LGBM_LEARNING_RATE
    ml_catboost_depth: int = DEFAULT_ML_CATBOOST_DEPTH
    ml_catboost_iterations: int = DEFAULT_ML_CATBOOST_ITERATIONS
    ml_catboost_learning_rate: float = DEFAULT_ML_CATBOOST_LEARNING_RATE
    ml_candidate_horizons: tuple[int, ...] = DEFAULT_ML_CANDIDATE_HORIZONS
    ml_candidate_up_thresholds: tuple[float, ...] = DEFAULT_ML_CANDIDATE_UP_THRESHOLDS
    ml_candidate_down_thresholds: tuple[float, ...] = DEFAULT_ML_CANDIDATE_DOWN_THRESHOLDS
    ml_candidate_decision_thresholds: tuple[float, ...] = DEFAULT_ML_CANDIDATE_DECISION_THRESHOLDS
    ml_min_trades_fraction: float = DEFAULT_ML_MIN_TRADES_FRACTION
    # Risk management — P1 sizing + P2 conviction/correlation/kelly
    risk_per_trade_pct: float = DEFAULT_RISK_PER_TRADE_PCT
    risk_max_positions: int = DEFAULT_RISK_MAX_POSITIONS
    risk_max_position_weight: float = DEFAULT_RISK_MAX_POSITION_WEIGHT
    risk_max_sector_weight: float = DEFAULT_RISK_MAX_SECTOR_WEIGHT
    risk_min_position_notional: float = DEFAULT_RISK_MIN_POSITION_NOTIONAL
    risk_score_weight: float = DEFAULT_RISK_SCORE_WEIGHT
    risk_prediction_weight: float = DEFAULT_RISK_PREDICTION_WEIGHT
    risk_correlation_threshold: float = DEFAULT_RISK_CORRELATION_THRESHOLD
    risk_correlation_lookback_days: int = DEFAULT_RISK_CORRELATION_LOOKBACK_DAYS
    risk_correlation_min_overlap: int = DEFAULT_RISK_CORRELATION_MIN_OVERLAP
    risk_enable_kelly: bool = DEFAULT_RISK_ENABLE_KELLY
    risk_payoff_ratio: float = DEFAULT_RISK_PAYOFF_RATIO
    risk_kelly_fraction_multiplier: float = DEFAULT_RISK_KELLY_FRACTION_MULTIPLIER
    risk_dry_run: bool = False
    risk_log_level: str = DEFAULT_RISK_LOG_LEVEL
    news_import_start_date: str | None = None
    news_import_end_date: str | None = None
    news_import_symbols: str | None = None
    news_import_symbol_source: NewsImportSymbolSource = "stock_scores_all"
    news_import_max_symbols: int | None = None
    news_import_resume_from_checkpoint: bool = True
    sentiment_start_utc: str | None = None
    sentiment_end_utc: str | None = None
    sentiment_symbols: str | None = None
    sentiment_news_provider: Literal["alpaca", "finnhub", "eodhd"] = "eodhd"
    sentiment_ticker_relevance_mode: Literal["provider_default", "strict", "scored"] = "provider_default"
    sentiment_min_relevance_score: float | None = None
    sentiment_scoring_mode: SentimentScoringMode = "standard_only"
    sentiment_enable_contextual_scoring: bool = False
    sentiment_contextual_min_relevance: float | None = None
    sentiment_contextual_max_pairs: int | None = None
    sentiment_pending_limit: int | None = None
    sentiment_pending_max_batches_per_run: int | None = None
    sentiment_feature_flush_every_n_batches: int | None = None
    sentiment_finbert_batch_size: int | None = None
    # === Relevance backfill (step 7bis) ==================================
    backfill_relevance_dry_run: bool = False
    backfill_relevance_rescore_all: bool = False
    backfill_relevance_purge_below: float | None = None
    backfill_relevance_batch_size: int = 500
    backfill_relevance_contextual_min_relevance: float = 0.0
    backfill_relevance_contextual_max_pairs: int | None = None
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
    selector_require_above_ma200: bool = DEFAULT_SELECTOR_REQUIRE_ABOVE_MA200
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
    data_integrity_earnings_log_every: int = DEFAULT_DATA_INTEGRITY_EARNINGS_LOG_EVERY
    data_integrity_earnings_batch_size: int = DEFAULT_DATA_INTEGRITY_EARNINGS_BATCH_SIZE
    data_integrity_earnings_resume: bool = DEFAULT_DATA_INTEGRITY_EARNINGS_RESUME
    data_integrity_fundamentals_limit: int | None = None
    data_integrity_fundamentals_provider: FundamentalsProvider = "yahoo_finance"
    data_integrity_fundamentals_overwrite_existing: bool = False
    data_integrity_fundamentals_sleep_seconds: float = DEFAULT_DATA_INTEGRITY_PROVIDER_SLEEP_SECONDS
    data_integrity_fundamentals_log_every: int = DEFAULT_DATA_INTEGRITY_FUNDAMENTALS_LOG_EVERY
    eodhd_write_commit_every_symbols: int = DEFAULT_EODHD_WRITE_COMMIT_EVERY_SYMBOLS
    eodhd_enable_stooq_cross_check: bool = DEFAULT_EODHD_ENABLE_STOOQ_CROSS_CHECK
    corporate_actions_skip_existing: bool = DEFAULT_CA_SKIP_EXISTING
    # Corporate actions sync — fenêtre custom + batching
    corporate_actions_use_custom_window: bool = DEFAULT_CA_USE_CUSTOM_WINDOW
    corporate_actions_start_date: str | None = None
    corporate_actions_end_date: str | None = None
    corporate_actions_batch_size: int = DEFAULT_CA_BATCH_SIZE
    # EODHD backfill historique (Phase 5 plan_eodhd.md §6) — étape auxiliaire B3
    eodhd_backfill_years: int = 30
    eodhd_backfill_symbols: str | None = None
    eodhd_backfill_resume: bool = True
    eodhd_backfill_write: bool = True


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


def parse_pipeline_step_number(step_num: str) -> int | None:
    """Extrait la composante numérique principale d'un identifiant d'étape.

    Exemples : ``"7" -> 7``, ``"7bis" -> 7``, ``"B1" -> None``.
    """

    normalized = str(step_num).strip()
    match = re.match(r"^(\d+)", normalized)
    if match is None:
        return None
    return int(match.group(1))


def is_canonical_pipeline_step_number(step_num: str, *, min_step: int = 1, max_step: int = 12) -> bool:
    """Retourne ``True`` pour les étapes coeur strictement numériques du workflow."""

    normalized = str(step_num).strip()
    if not normalized.isdigit():
        return False
    value = int(normalized)
    return min_step <= value <= max_step


def is_workflow_core_step_number(step_num: str, *, min_step: int = 1, max_step: int = 12) -> bool:
    """Retourne ``True`` pour les étapes coeur strictement numériques du workflow quotidien."""

    normalized = str(step_num).strip().lower()
    return is_canonical_pipeline_step_number(normalized, min_step=min_step, max_step=max_step)


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
        name="Import Bars + rattrapage auto (Alpaca / EODHD)",
        desc="Ingestion OHLCV daily incrémentale avec rattrapage automatique des jours manquants "
             "depuis la dernière barre connue par symbole jusqu'à la date de marché courante. "
             "Provider sélectionné automatiquement via `market_data.bars_provider` (alpaca | eodhd). "
             "En mode EODHD, route vers `dataIntegrityEngine.import_eodhd_bar --write`.",
        tables="stock_bars, stock_bars_daily",
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
        desc=(
            "Import news brut sur `stock_scores_all` → scoring FinBERT standard + `relevance_score` + "
            "scoring contextuel sur les candidats (ou override CSV) → reconstruction des features journalières "
            "avec `ticker_daily_sentiment_features` filtré candidats et `sector_daily_sentiment_features` "
            "sur le scope large importé."
        ),
        tables=(
            "news_raw, news_ticker_map, news_sentiment, news_ticker_sentiment, "
            "macro_event_audit, ticker_daily_sentiment_features, sector_daily_sentiment_features, "
            "news_ingestion_checkpoint"
        ),
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
        desc="Recupere dividendes/splits pour les symboles detenus en portefeuille. Provider selectionne automatiquement via market_data.bars_provider (alpaca ou eodhd) ; Yahoo cross-check toujours appele. (Phase 6 EODHD)",
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
        desc="Enrichit `stock_metadata` avec `sector` et `market_cap` via Yahoo Finance, EODHD ou Finnhub (défaut Yahoo Finance / `yfinance`), avec option d'écrasement des valeurs existantes. Si l'endpoint fundamentals EODHD est refusé par le compte (401/403), le backend bascule automatiquement vers Finnhub pour terminer le run.",
        tables="stock_metadata",
        deps="import_alpaca_assets (recommandé) ou univers déjà chargé",
    ),
    PipelineStepDefinition(
        key="eodhd_backfill_history",
        num="B3",
        name="Backfill historique EODHD",
        desc="One-shot : remplit `stock_bars` + `stock_bars_daily` avec l'historique long "
             "EODHD (5 ans par défaut, jusqu'à 30 ans pour ML). Bookmark idempotent dans "
             "`artifacts/eodhd_cache/backfill_state.json`. Coût ~1 call/symbole. "
             "Depuis l'IHM, le mode par défaut est `write` pour persister directement dans la base ; "
             "il reste possible de repasser en dry-run en décochant `B3 — mode écriture`. "
             "Utile au démarrage initial post-cutover `bars_provider=eodhd`.",
        tables="stock_bars, stock_bars_daily",
        deps="import_alpaca_assets (univers requis)",
    ),
)


def get_pipeline_steps() -> tuple[PipelineStepDefinition, ...]:
    return PIPELINE_STEPS


def get_pipeline_workflow_steps(
    *,
    start_step: WorkflowStartStep = "1",
    include_ml_train: bool = True,
    include_corporate_actions_sync: bool = False,
    include_corporate_actions_apply: bool = False,
    selected_step_keys: tuple[str, ...] | None = None,
) -> tuple[PipelineStepDefinition, ...]:
    normalized_start = "3" if start_step == "3" else "1"
    include_sync = include_corporate_actions_sync or include_corporate_actions_apply
    normalized_selected_step_keys = (
        {str(step_key).strip() for step_key in selected_step_keys if str(step_key).strip()}
        if selected_step_keys is not None
        else None
    )

    selected_steps: list[PipelineStepDefinition] = []
    for step in PIPELINE_STEPS:
        if not is_workflow_core_step_number(step.num):
            continue
        step_num = parse_pipeline_step_number(step.num)
        if normalized_selected_step_keys is not None:
            if step.key not in normalized_selected_step_keys:
                continue
        else:
            if step_num is None or step_num < int(normalized_start):
                continue
            if step.key == "ml_train" and not include_ml_train:
                continue
        selected_steps.append(step)

    if include_sync:
        selected_steps.append(next(step for step in PIPELINE_STEPS if step.key == "corporate_actions_sync"))
    if include_corporate_actions_apply:
        selected_steps.append(next(step for step in PIPELINE_STEPS if step.key == "corporate_actions_apply"))

    return tuple(selected_steps)


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


def _with_default_sentiment_pending_max_batches(
    options: PipelineLaunchOptions,
    *,
    default_value: int = 0,
) -> PipelineLaunchOptions:
    """Applique un défaut IHM/wrapper pour `--sentiment-pending-max-batches`.

    On ne touche pas aux appels où l'utilisateur a explicitement fourni une
    valeur. En revanche, pour le scoring standard manuel et les wrappers auto,
    on veut un comportement implicite « drainer jusqu'au bout » même si la
    valeur n'a pas été renseignée côté appelant.
    """

    if options.sentiment_pending_max_batches_per_run is not None:
        return options
    return replace(options, sentiment_pending_max_batches_per_run=int(default_value))


def _build_powershell_file_command(script_path: Path, arguments: list[str] | None = None) -> list[str]:
    return [
        "powershell.exe" if os.name == "nt" else "pwsh",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path),
        *(arguments or []),
    ]


def _extend_event_sentiment_cli_common_args(
    command: list[str],
    options: PipelineLaunchOptions,
    *,
    include_contextual_scoring: bool,
) -> None:
    """Ajoute les flags supportés par les CLIs Python Event Sentiment."""

    scoring_mode = _resolve_event_sentiment_scoring_mode(options)

    news_provider = options.sentiment_news_provider or "eodhd"
    command.extend(["--news-provider", news_provider])

    if (
        options.sentiment_ticker_relevance_mode
        and options.sentiment_ticker_relevance_mode != "provider_default"
    ):
        command.extend([
            "--ticker-relevance-mode",
            options.sentiment_ticker_relevance_mode,
        ])

    if (
        options.sentiment_ticker_relevance_mode == "scored"
        and options.sentiment_min_relevance_score is not None
        and options.sentiment_min_relevance_score > 0.0
    ):
        command.extend([
            "--min-relevance-score",
            f"{float(options.sentiment_min_relevance_score):g}",
        ])

    if include_contextual_scoring and scoring_mode == "contextual_only":
        command.extend(["--scoring-mode", "contextual_only"])
    elif include_contextual_scoring and scoring_mode == "standard_and_contextual":
        command.append("--enable-contextual-scoring")

    if include_contextual_scoring and scoring_mode != "standard_only":
        if (
            options.sentiment_contextual_min_relevance is not None
            and options.sentiment_contextual_min_relevance > 0.0
        ):
            command.extend([
                "--contextual-min-relevance",
                f"{float(options.sentiment_contextual_min_relevance):g}",
            ])
        if (
            options.sentiment_contextual_max_pairs is not None
            and options.sentiment_contextual_max_pairs > 0
        ):
            command.extend([
                "--contextual-max-pairs",
                str(int(options.sentiment_contextual_max_pairs)),
            ])

def _extend_event_sentiment_runtime_args(
    command: list[str],
    options: PipelineLaunchOptions,
    *,
    include_feature_flush: bool = True,
) -> None:
    """Ajoute les réglages de débit/runtime communs au CLI principal Event Sentiment."""

    if options.sentiment_pending_limit is not None and options.sentiment_pending_limit > 0:
        command.extend([
            "--sentiment-pending-limit",
            str(int(options.sentiment_pending_limit)),
        ])
    if options.sentiment_pending_max_batches_per_run is not None:
        command.extend([
            "--sentiment-pending-max-batches",
            str(int(options.sentiment_pending_max_batches_per_run)),
        ])
    if (
        include_feature_flush
        and
        options.sentiment_feature_flush_every_n_batches is not None
        and options.sentiment_feature_flush_every_n_batches > 0
    ):
        command.extend([
            "--feature-flush-every-n-batches",
            str(int(options.sentiment_feature_flush_every_n_batches)),
        ])
    if options.sentiment_finbert_batch_size is not None and options.sentiment_finbert_batch_size > 0:
        command.extend([
            "--finbert-batch-size",
            str(int(options.sentiment_finbert_batch_size)),
        ])


def _extend_event_sentiment_scope_args(
    command: list[str],
    *,
    start_utc: str | None,
    end_utc: str | None,
    symbols: str | None,
) -> None:
    if start_utc:
        command.extend(["--start-utc", start_utc])
    if end_utc:
        command.extend(["--end-utc", end_utc])
    if symbols:
        command.extend(["--symbols", symbols])


def _extend_relevance_backfill_scope_args(
    command: list[str],
    *,
    start_utc: str | None,
    end_utc: str | None,
    symbols: str | None,
    symbol_source: str | None = None,
    max_symbols: int | None = None,
) -> None:
    if start_utc:
        command.extend(["--start-date", str(start_utc)[:10]])
    if end_utc:
        command.extend(["--end-date", str(end_utc)[:10]])
    if symbols:
        command.extend(["--symbols", symbols])
    elif symbol_source:
        command.extend(["--symbol-source", symbol_source])
    if max_symbols is not None and max_symbols > 0:
        command.extend(["--max-symbols", str(int(max_symbols))])


def _build_sentiment_standard_command(
    options: PipelineLaunchOptions,
    *,
    sentiment_start_utc: str | None,
    sentiment_end_utc: str | None,
    sentiment_symbols: str | None,
    sentiment_symbol_source: str | None = None,
    sentiment_max_symbols: int | None = None,
    skip_ingestion: bool,
) -> list[str]:
    effective_options = _with_default_sentiment_pending_max_batches(options)
    command = [sys.executable, "-u", "-m", "event_sentiment"]
    if skip_ingestion:
        command.append("--skip-ingestion")
    command.extend(["--skip-features", "--scoring-mode", "standard_only"])
    _extend_event_sentiment_cli_common_args(
        command,
        effective_options,
        include_contextual_scoring=False,
    )
    _extend_event_sentiment_runtime_args(command, effective_options, include_feature_flush=False)
    _extend_event_sentiment_scope_args(
        command,
        start_utc=sentiment_start_utc,
        end_utc=sentiment_end_utc,
        symbols=None,
    )
    _extend_event_sentiment_symbol_scope_args(
        command,
        symbols=sentiment_symbols,
        symbol_source=str(sentiment_symbol_source or ""),
        max_symbols=sentiment_max_symbols,
    )
    return command


def _build_sentiment_relevance_backfill_command(
    options: PipelineLaunchOptions,
    *,
    sentiment_start_utc: str | None,
    sentiment_end_utc: str | None,
    sentiment_symbols: str | None,
    sentiment_symbol_source: str | None = None,
    sentiment_max_symbols: int | None = None,
) -> list[str]:
    command = [
        sys.executable, "-u", "-m", "event_sentiment.relevance_backfill",
        "--news-provider", str(options.sentiment_news_provider or "eodhd"),
        "--batch-size", str(int(options.backfill_relevance_batch_size or 500)),
    ]
    _extend_relevance_backfill_scope_args(
        command,
        start_utc=sentiment_start_utc,
        end_utc=sentiment_end_utc,
        symbols=sentiment_symbols,
        symbol_source=sentiment_symbol_source,
        max_symbols=sentiment_max_symbols,
    )
    if options.backfill_relevance_rescore_all:
        command.append("--rescore-all")
    if (
        options.backfill_relevance_purge_below is not None
        and options.backfill_relevance_purge_below > 0.0
    ):
        command.extend(["--purge-below", f"{float(options.backfill_relevance_purge_below):g}"])
    return command


def _build_sentiment_history_backfill_command(
    *,
    sentiment_start_utc: str | None,
    sentiment_end_utc: str | None,
    ticker_symbols: str | None = None,
    ticker_symbol_source: str | None = None,
    ticker_max_symbols: int | None = None,
    ingestion_source: str | None = None,
) -> list[str]:
    command = [sys.executable, "-u", "-m", "event_sentiment.history_backfill"]
    if sentiment_start_utc:
        command.extend(["--start-date", str(sentiment_start_utc)[:10]])
    if sentiment_end_utc:
        command.extend(["--end-date", str(sentiment_end_utc)[:10]])
    if ingestion_source:
        command.extend(["--ingestion-source", ingestion_source])
    if ticker_symbols:
        command.extend(["--ticker-symbols", ticker_symbols])
    elif ticker_symbol_source:
        command.extend(["--ticker-symbol-source", ticker_symbol_source])
    if ticker_max_symbols is not None and ticker_max_symbols > 0:
        command.extend(["--ticker-max-symbols", str(int(ticker_max_symbols))])
    return command


def _build_sentiment_contextual_command(
    options: PipelineLaunchOptions,
    *,
    sentiment_start_utc: str | None,
    sentiment_end_utc: str | None,
    sentiment_symbols: str | None,
    sentiment_symbol_source: str | None = None,
    sentiment_max_symbols: int | None = None,
) -> list[str]:
    command = [
        sys.executable,
        "-u",
        "-m",
        "event_sentiment",
        "--skip-ingestion",
        "--skip-features",
        "--scoring-mode",
        "contextual_only",
    ]
    _extend_event_sentiment_cli_common_args(
        command,
        options,
        include_contextual_scoring=True,
    )
    if (
        "--contextual-min-relevance" not in command
        and options.sentiment_contextual_min_relevance is not None
        and options.sentiment_contextual_min_relevance > 0.0
    ):
        command.extend([
            "--contextual-min-relevance",
            f"{float(options.sentiment_contextual_min_relevance):g}",
        ])
    if (
        "--contextual-max-pairs" not in command
        and options.sentiment_contextual_max_pairs is not None
        and options.sentiment_contextual_max_pairs > 0
    ):
        command.extend([
            "--contextual-max-pairs",
            str(int(options.sentiment_contextual_max_pairs)),
        ])
    _extend_event_sentiment_runtime_args(command, options, include_feature_flush=False)
    _extend_event_sentiment_scope_args(
        command,
        start_utc=sentiment_start_utc,
        end_utc=sentiment_end_utc,
        symbols=None,
    )
    _extend_event_sentiment_symbol_scope_args(
        command,
        symbols=sentiment_symbols,
        symbol_source=str(sentiment_symbol_source or ""),
        max_symbols=sentiment_max_symbols,
    )
    return command


def _build_import_news_command(
    options: PipelineLaunchOptions,
    *,
    import_start_date: str | None,
    import_end_date: str | None,
    import_symbols: str | None,
    import_symbol_source: str,
    import_max_symbols: int | None,
    resume_from_checkpoint: bool,
    force_symbol_source: bool = False,
) -> list[str]:
    command = [
        sys.executable,
        "-u",
        str(PROJECT_ROOT / "event_sentiment" / "importe_news.py"),
    ]
    if import_start_date:
        command.extend(["--start-date", import_start_date])
    if import_end_date:
        command.extend(["--end-date", import_end_date])
    _extend_event_sentiment_cli_common_args(
        command,
        options,
        include_contextual_scoring=False,
    )
    if force_symbol_source and not import_symbols and import_symbol_source:
        command.extend(["--symbol-source", import_symbol_source])
        if import_max_symbols is not None and import_max_symbols > 0:
            command.extend(["--max-symbols", str(int(import_max_symbols))])
        if resume_from_checkpoint:
            command.append("--resume-checkpoints")
    else:
        _extend_import_news_cli_args(
            command,
            symbols=import_symbols,
            symbol_source=import_symbol_source,
            max_symbols=import_max_symbols,
            resume_from_checkpoint=resume_from_checkpoint,
        )
    return command


def _extend_event_sentiment_powershell_args(
    command_args: list[str],
    options: PipelineLaunchOptions,
    *,
    include_contextual_scoring: bool,
) -> None:
    """Ajoute les paramètres Event Sentiment pour les wrappers PowerShell."""

    scoring_mode = _resolve_event_sentiment_scoring_mode(options)

    news_provider = options.sentiment_news_provider or "eodhd"
    command_args.extend(["-NewsProvider", news_provider])

    if (
        options.sentiment_ticker_relevance_mode
        and options.sentiment_ticker_relevance_mode != "provider_default"
    ):
        command_args.extend([
            "-TickerRelevanceMode",
            options.sentiment_ticker_relevance_mode,
        ])

    if (
        options.sentiment_ticker_relevance_mode == "scored"
        and options.sentiment_min_relevance_score is not None
        and options.sentiment_min_relevance_score > 0.0
    ):
        command_args.extend([
            "-MinRelevanceScore",
            f"{float(options.sentiment_min_relevance_score):g}",
        ])

    if include_contextual_scoring and scoring_mode == "contextual_only":
        command_args.extend(["-ScoringMode", "contextual_only"])
    elif include_contextual_scoring and scoring_mode == "standard_and_contextual":
        command_args.append("-EnableContextualScoring")

    if include_contextual_scoring and scoring_mode != "standard_only":
        if (
            options.sentiment_contextual_min_relevance is not None
            and options.sentiment_contextual_min_relevance > 0.0
        ):
            command_args.extend([
                "-ContextualMinRelevance",
                f"{float(options.sentiment_contextual_min_relevance):g}",
            ])
        if (
            options.sentiment_contextual_max_pairs is not None
            and options.sentiment_contextual_max_pairs > 0
        ):
            command_args.extend([
                "-ContextualMaxPairs",
                str(int(options.sentiment_contextual_max_pairs)),
            ])

    if options.sentiment_pending_limit is not None and options.sentiment_pending_limit > 0:
        command_args.extend([
            "-SentimentPendingLimit",
            str(int(options.sentiment_pending_limit)),
        ])
    if options.sentiment_pending_max_batches_per_run is not None:
        command_args.extend([
            "-SentimentPendingMaxBatches",
            str(int(options.sentiment_pending_max_batches_per_run)),
        ])
    if (
        options.sentiment_feature_flush_every_n_batches is not None
        and options.sentiment_feature_flush_every_n_batches > 0
    ):
        command_args.extend([
            "-FeatureFlushEveryNBatches",
            str(int(options.sentiment_feature_flush_every_n_batches)),
        ])
    if options.sentiment_finbert_batch_size is not None and options.sentiment_finbert_batch_size > 0:
        command_args.extend([
            "-FinBertBatchSize",
            str(int(options.sentiment_finbert_batch_size)),
        ])


def _resolve_event_sentiment_scoring_mode(options: PipelineLaunchOptions) -> SentimentScoringMode:
    if options.sentiment_enable_contextual_scoring:
        if options.sentiment_scoring_mode == "contextual_only":
            return "contextual_only"
        return "standard_and_contextual"
    if options.sentiment_scoring_mode in {"standard_only", "contextual_only", "standard_and_contextual"}:
        return options.sentiment_scoring_mode
    return "standard_only"


def _extend_import_news_cli_args(
    command: list[str],
    *,
    symbols: str | None,
    symbol_source: str,
    max_symbols: int | None,
    resume_from_checkpoint: bool = False,
) -> None:
    if symbols:
        command.extend(["--symbols", symbols])
    elif symbol_source and symbol_source != "stock_scores_all":
        command.extend(["--symbol-source", symbol_source])

    if max_symbols is not None and max_symbols > 0:
        command.extend(["--max-symbols", str(int(max_symbols))])

    if resume_from_checkpoint:
        command.append("--resume-checkpoints")


def _extend_import_news_powershell_args(
    command_args: list[str],
    *,
    symbols: str | None,
    symbol_source: str,
    max_symbols: int | None,
    resume_from_checkpoint: bool = False,
) -> None:
    if symbols:
        command_args.extend(["-Symbols", symbols])
    elif symbol_source and symbol_source != "stock_scores_all":
        command_args.extend(["-SymbolSource", symbol_source])

    if max_symbols is not None and max_symbols > 0:
        command_args.extend(["-MaxSymbols", str(int(max_symbols))])

    if resume_from_checkpoint:
        command_args.append("-ResumeCheckpoints")


def _extend_event_sentiment_symbol_scope_args(
    command: list[str],
    *,
    symbols: str | None,
    symbol_source: str,
    max_symbols: int | None,
) -> None:
    if symbols:
        command.extend(["--symbols", symbols])
    elif symbol_source:
        command.extend(["--symbol-source", symbol_source])

    if max_symbols is not None and max_symbols > 0:
        command.extend(["--max-symbols", str(int(max_symbols))])


def _extend_relevance_backfill_powershell_args(
    command_args: list[str],
    options: PipelineLaunchOptions,
) -> None:
    """Ajoute les paramètres ``relevance_backfill`` pour le wrapper PowerShell auto."""

    command_args.extend([
        "-RelevanceBackfillBatchSize",
        str(int(options.backfill_relevance_batch_size or 500)),
    ])

    if options.backfill_relevance_dry_run:
        command_args.append("-RelevanceBackfillDryRun")

    if options.backfill_relevance_rescore_all:
        command_args.append("-RelevanceBackfillRescoreAll")

    if (
        options.backfill_relevance_purge_below is not None
        and options.backfill_relevance_purge_below > 0.0
    ):
        command_args.extend([
            "-RelevanceBackfillPurgeBelow",
            f"{float(options.backfill_relevance_purge_below):g}",
        ])

    # Paramètres contextuels toujours transmis au PS1 (le script décide s'il les utilise).
    if options.backfill_relevance_contextual_min_relevance > 0.0:
        command_args.extend([
            "-RelevanceBackfillContextualMinRelevance",
            f"{float(options.backfill_relevance_contextual_min_relevance):g}",
        ])

    if (
        options.backfill_relevance_contextual_max_pairs is not None
        and options.backfill_relevance_contextual_max_pairs > 0
    ):
        command_args.extend([
            "-RelevanceBackfillContextualMaxPairs",
            str(int(options.backfill_relevance_contextual_max_pairs)),
        ])



def _build_import_news_pending_loop_command(
    options: PipelineLaunchOptions,
    *,
    news_import_start_date: str | None,
    news_import_end_date: str | None,
    news_import_symbols: str | None,
    news_import_symbol_source: str,
    news_import_max_symbols: int | None,
    skip_import: bool = False,
) -> list[str]:
    effective_options = _with_default_sentiment_pending_max_batches(options)
    if news_import_start_date is None:
        raise ValueError("La date de début est obligatoire pour le pipeline auto news.")
    script_path = PROJECT_ROOT / "scripts" / "windows" / "import_news_and_score_pending.ps1"
    command_args = [
        "-ProjectRoot",
        str(PROJECT_ROOT),
        "-PythonExe",
        sys.executable,
        "-StartDate",
        news_import_start_date,
    ]
    if news_import_end_date:
        command_args.extend(["-EndDate", news_import_end_date])
    _extend_event_sentiment_powershell_args(
        command_args,
        effective_options,
        include_contextual_scoring=True,
    )
    _extend_import_news_powershell_args(
        command_args,
        symbols=news_import_symbols,
        symbol_source=news_import_symbol_source,
        max_symbols=news_import_max_symbols,
        resume_from_checkpoint=bool(options.news_import_resume_from_checkpoint),
    )
    _extend_relevance_backfill_powershell_args(command_args, effective_options)
    if skip_import:
        command_args.append("-SkipImport")
    return _build_powershell_file_command(script_path, command_args)


def is_gpu_available() -> bool:
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:
        return False


def _build_chained_ps_commands(
    steps: list[tuple[str, list[str]]],
    title: str | None = None,
) -> list[str]:
    """Chaîne N commandes Python via PowerShell inline avec labels de progression.

    Chaque étape n'est lancée que si la précédente a réussi (exit=0).
    Un Write-Host affiche le label de chaque étape avant son exécution.
    Si ``title`` est fourni, un bandeau jaune est affiché avant les étapes.
    """

    def _quote(arg: str) -> str:
        if " " in arg or '"' in arg or "'" in arg:
            escaped = arg.replace('"', '\\"')
            return f'"{escaped}"'
        return arg

    project_root_escaped = str(PROJECT_ROOT).replace("'", "''")
    total = len(steps)
    parts: list[str] = [
        f"Push-Location '{project_root_escaped}'",
        "$ec = 0",
    ]
    if title:
        safe_title = title.replace("'", "''")
        divider = "=" * 60
        parts.append(
            f"Write-Host '{divider}' -ForegroundColor Yellow; "
            f"Write-Host '  {safe_title}' -ForegroundColor Yellow; "
            f"Write-Host '{divider}' -ForegroundColor Yellow"
        )
    for i, (label, cmd) in enumerate(steps, 1):
        cmd_str = " ".join(_quote(a) for a in cmd)
        safe_label = label.replace("'", "''")
        parts.append(
            f"if ($ec -eq 0) {{"
            f" Write-Host '[{i}/{total}] {safe_label}' -ForegroundColor Cyan;"
            f" & {cmd_str};"
            f" $ec = $LASTEXITCODE"
            f" }}"
        )
    parts.extend(["Pop-Location", "exit $ec"])
    ps_script = "; ".join(parts)
    return ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script]


def build_pipeline_command(step_key: str, options: PipelineLaunchOptions) -> list[str]:
    """Construit la commande subprocess correspondant à une étape."""
    trade_date = _normalize_trade_date(options.trade_date)
    run_id = _normalize_run_id(options.execution_run_id)
    account_id = (options.account_id or "").strip() or None
    news_import_start_date = _normalize_optional_date(options.news_import_start_date)
    news_import_end_date = _normalize_optional_date(options.news_import_end_date)
    news_import_symbols = _normalize_symbol_list(options.news_import_symbols)
    news_import_symbol_source = (
        options.news_import_symbol_source
        if options.news_import_symbol_source in {
            "stock_scores",
            "stock_scores_history",
            "stock_scores_all",
            "candidates",
            "stock_bars_daily",
        }
        else "stock_scores_all"
    )
    news_import_max_symbols = (
        int(options.news_import_max_symbols)
        if options.news_import_max_symbols is not None and int(options.news_import_max_symbols) > 0
        else None
    )
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

    ca_start_date = _normalize_optional_date(options.corporate_actions_start_date)
    ca_end_date = _normalize_optional_date(options.corporate_actions_end_date)
    ml_benchmark_symbol = _normalize_symbol(options.ml_benchmark_symbol, DEFAULT_ML_BENCHMARK_SYMBOL)
    ml_artifacts_dir = (options.ml_artifacts_dir or "").strip() or DEFAULT_ML_ARTIFACTS_DIR
    ml_symbol_source = "stock-bars-daily" if options.ml_train_symbol_source == "stock_bars_daily" else "candidates"
    ml_selector_signal_modes = [
        str(value).strip().lower()
        for value in (options.ml_selector_universe_signal_modes or ())
        if str(value).strip()
    ]

    if step_key == "import_alpaca_assets":
        return [sys.executable, "-u", "-m", "dataIntegrityEngine.import_alpaca_assets"]

    if step_key == "import_alpaca_bar":
        # Phase 6 EODHD : route dynamiquement vers le bon module selon
        # ``market_data.bars_provider`` (alpaca | eodhd). Garde la même clé
        # ``import_alpaca_bar`` pour ne pas casser l'historique IHM.
        provider = _resolve_bars_provider_for_ihm()
        if provider == "eodhd":
            command = [sys.executable, "-u", "-m", "dataIntegrityEngine.import_eodhd_bar", "--write"]
            if options.eodhd_write_commit_every_symbols > 0:
                command.extend(["--commit-every-symbols", str(int(options.eodhd_write_commit_every_symbols))])
            if not options.eodhd_enable_stooq_cross_check:
                command.append("--no-stooq-cross-check")
            return command
        return [sys.executable, "-u", "-m", "dataIntegrityEngine.import_alpaca_bar"]

    if step_key == "update_sector":
        fundamentals_provider = (
            options.data_integrity_fundamentals_provider
            if options.data_integrity_fundamentals_provider in {"yahoo_finance", "eodhd", "finnhub"}
            else "yahoo_finance"
        )
        command = [
            sys.executable,
            "-u",
            "-m",
            "dataIntegrityEngine.update_sector",
            "--provider",
            fundamentals_provider,
            "--sleep-seconds",
            str(options.data_integrity_fundamentals_sleep_seconds),
            "--log-every",
            str(options.data_integrity_fundamentals_log_every),
        ]
        if fundamentals_limit is not None:
            command.extend(["--limit", str(fundamentals_limit)])
        if options.data_integrity_fundamentals_overwrite_existing:
            command.append("--overwrite-existing")
        return command

    if step_key == "eodhd_backfill_history":
        # Phase 5 plan_eodhd.md §6 : backfill historique long via EODHD /eod
        command = [
            sys.executable, "-u", "-m",
            "dataIntegrityEngine.backfill_eodhd_history",
            "--years", str(int(options.eodhd_backfill_years or 30)),
        ]
        if options.eodhd_backfill_write:
            command.append("--write")
        # Reprise sur bookmark par défaut ; --no-resume pour forcer
        if options.eodhd_backfill_resume:
            command.append("--resume")
        else:
            command.append("--no-resume")
        if options.eodhd_backfill_symbols:
            symbols = [s.strip().upper() for s in options.eodhd_backfill_symbols.split(",") if s.strip()]
            if symbols:
                command.append("--symbols")
                command.extend(symbols)
        return command

    if step_key == "corporate_actions_sync":
        # --portfolio-only : sync uniquement les symboles détenus en portefeuille
        # pas de --skip-existing : on re-interroge Alpaca à chaque fois pour ne rater aucun nouvel événement
        command = [sys.executable, "-u", "-m", "corporate_actions", "sync", "--portfolio-only"]
        if options.corporate_actions_skip_existing:
            command.append("--skip-existing")
        if options.corporate_actions_batch_size and options.corporate_actions_batch_size > 0:
            command.extend(["--batch-size", str(options.corporate_actions_batch_size)])
        if options.corporate_actions_use_custom_window:
            if ca_start_date:
                command.extend(["--start", ca_start_date])
            if ca_end_date:
                command.extend(["--end", ca_end_date])
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
        if trade_date:
            command.extend(["--trade-date", trade_date])
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
            "--log-every",
            str(options.data_integrity_earnings_log_every),
            "--batch-size",
            str(options.data_integrity_earnings_batch_size),
        ]
        if earnings_from_date:
            command.extend(["--from-date", earnings_from_date])
        if earnings_to_date:
            command.extend(["--to-date", earnings_to_date])
        if earnings_limit is not None:
            command.extend(["--limit", str(earnings_limit)])
        command.append("--resume" if options.data_integrity_earnings_resume else "--no-resume")
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
        if options.selector_require_above_ma200:
            command.append("--require-above-ma200")
        if trade_date:
            command.extend(["--trade-date", trade_date])
        return command

    if step_key == "sentiment_pipeline":
        candidate_scope_symbols = sentiment_symbols
        candidate_scope_symbol_source = None if candidate_scope_symbols else "candidates"
        import_start_date = str(sentiment_start_utc)[:10] if sentiment_start_utc else None
        import_end_date = str(sentiment_end_utc)[:10] if sentiment_end_utc else None
        cmd0 = _build_import_news_command(
            options,
            import_start_date=import_start_date,
            import_end_date=import_end_date,
            import_symbols=None,
            import_symbol_source="stock_scores_all",
            import_max_symbols=None,
            resume_from_checkpoint=bool(options.news_import_resume_from_checkpoint),
            force_symbol_source=True,
        )
        cmd1 = _build_sentiment_standard_command(
            options,
            sentiment_start_utc=sentiment_start_utc,
            sentiment_end_utc=sentiment_end_utc,
            sentiment_symbols=candidate_scope_symbols,
            sentiment_symbol_source=candidate_scope_symbol_source,
            skip_ingestion=True,
        )
        cmd2 = _build_sentiment_relevance_backfill_command(
            options,
            sentiment_start_utc=sentiment_start_utc,
            sentiment_end_utc=sentiment_end_utc,
            sentiment_symbols=candidate_scope_symbols,
            sentiment_symbol_source=candidate_scope_symbol_source,
        )
        cmd3 = _build_sentiment_history_backfill_command(
            sentiment_start_utc=sentiment_start_utc,
            sentiment_end_utc=sentiment_end_utc,
            ticker_symbols=candidate_scope_symbols,
            ticker_symbol_source=candidate_scope_symbol_source,
            ingestion_source=options.sentiment_news_provider,
        )
        cmd4 = _build_sentiment_contextual_command(
            options,
            sentiment_start_utc=sentiment_start_utc,
            sentiment_end_utc=sentiment_end_utc,
            sentiment_symbols=candidate_scope_symbols,
            sentiment_symbol_source=candidate_scope_symbol_source,
        )

        return _build_chained_ps_commands(
            [
                ("Import news brut (scope large stock_scores_all)", cmd0),
                ("Calcul relevance_score (scope candidats / override CSV)", cmd2),
                ("Scoring FinBERT standard (scope candidats / override CSV)", cmd1),
                ("Scoring FinBERT contextuel (scope candidats / override CSV)", cmd4),
                ("Agregation features : ticker=candidats, secteur=scope large importe", cmd3),
            ],
            title="ETAPE 7 — Sentiment Pipeline",
        )

    if step_key == "relevance_backfill":
        # Outil de maintenance : scoring FinBERT contextuel uniquement.
        # --contextual-only  → pas de recalcul relevance_score (appartient à l'étape 7).
        # --rescore-contextual → active systématiquement la Phase 2 FinBERT contextuel.
        contextual_cmd = [
            sys.executable,
            "-u",
            "-m",
            "event_sentiment.relevance_backfill",
            "--news-provider",
            str(options.sentiment_news_provider or "eodhd"),
            "--contextual-only",    # ne touche pas relevance_score
            "--rescore-contextual", # Phase 2 FinBERT toujours active
            "--batch-size",
            str(int(options.backfill_relevance_batch_size or 500)),
        ]
        if sentiment_start_utc:
            contextual_cmd.extend(["--start-date", str(sentiment_start_utc)[:10]])
        if sentiment_end_utc:
            contextual_cmd.extend(["--end-date", str(sentiment_end_utc)[:10]])
        if sentiment_symbols:
            contextual_cmd.extend(["--symbols", sentiment_symbols])
        if (
            options.backfill_relevance_purge_below is not None
            and options.backfill_relevance_purge_below > 0.0
        ):
            contextual_cmd.extend([
                "--purge-below",
                f"{float(options.backfill_relevance_purge_below):g}",
            ])
        if options.backfill_relevance_contextual_min_relevance > 0.0:
            contextual_cmd.extend([
                "--contextual-min-relevance",
                f"{float(options.backfill_relevance_contextual_min_relevance):g}",
            ])
        if (
            options.backfill_relevance_contextual_max_pairs is not None
            and options.backfill_relevance_contextual_max_pairs > 0
        ):
            contextual_cmd.extend([
                "--contextual-max-pairs",
                str(int(options.backfill_relevance_contextual_max_pairs)),
            ])
        return _build_chained_ps_commands(
            [("Scoring FinBERT contextuel (Niveau 4 — news_ticker_sentiment)", contextual_cmd)],
            title="MAINTENANCE — Contextual FinBERT",
        )

    if step_key == "score_sentiment_only":
        if news_import_start_date is None:
            raise ValueError("La date de début est obligatoire pour scorer le sentiment sur le scope manuel sentiment.")
        command = [sys.executable, "-u", "-m", "event_sentiment", "--skip-ingestion"]
        _extend_event_sentiment_cli_common_args(
            command,
            options,
            include_contextual_scoring=True,
        )
        _extend_event_sentiment_runtime_args(command, options, include_feature_flush=True)
        command.extend(["--start-utc", f"{news_import_start_date}T00:00:00Z"])
        if news_import_end_date:
            command.extend(["--end-utc", f"{news_import_end_date}T23:59:59Z"])
        _extend_event_sentiment_symbol_scope_args(
            command,
            symbols=news_import_symbols,
            symbol_source=news_import_symbol_source,
            max_symbols=news_import_max_symbols,
        )
        return command

    if step_key == "sentiment_standard_scoring":
        if news_import_start_date is None:
            raise ValueError("La date de début est obligatoire pour le scoring FinBERT standard manuel.")
        return _build_sentiment_standard_command(
            options,
            sentiment_start_utc=f"{news_import_start_date}T00:00:00Z",
            sentiment_end_utc=f"{news_import_end_date}T23:59:59Z" if news_import_end_date else None,
            sentiment_symbols=news_import_symbols,
            sentiment_symbol_source=None if news_import_symbols else news_import_symbol_source,
            sentiment_max_symbols=news_import_max_symbols,
            skip_ingestion=True,
        )

    if step_key == "sentiment_relevance_backfill":
        if news_import_start_date is None:
            raise ValueError("La date de début est obligatoire pour le calcul manuel de relevance_score.")
        command = _build_sentiment_relevance_backfill_command(
            options,
            sentiment_start_utc=f"{news_import_start_date}T00:00:00Z",
            sentiment_end_utc=f"{news_import_end_date}T23:59:59Z" if news_import_end_date else None,
            sentiment_symbols=news_import_symbols,
        )
        if not news_import_symbols:
            _extend_relevance_backfill_scope_args(
                command,
                start_utc=None,
                end_utc=None,
                symbols=None,
                symbol_source=news_import_symbol_source,
                max_symbols=news_import_max_symbols,
            )
        return command

    if step_key == "sentiment_contextual_scoring":
        if news_import_start_date is None:
            raise ValueError("La date de début est obligatoire pour le scoring FinBERT contextuel manuel.")
        command = _build_sentiment_contextual_command(
            options,
            sentiment_start_utc=f"{news_import_start_date}T00:00:00Z",
            sentiment_end_utc=f"{news_import_end_date}T23:59:59Z" if news_import_end_date else None,
            sentiment_symbols=None,
        )
        _extend_event_sentiment_symbol_scope_args(
            command,
            symbols=news_import_symbols,
            symbol_source=news_import_symbol_source,
            max_symbols=news_import_max_symbols,
        )
        return command

    if step_key == "rebuild_daily_sentiment_features_only":
        rebuild_start_date = news_import_start_date or (str(sentiment_start_utc)[:10] if sentiment_start_utc else None)
        rebuild_end_date = news_import_end_date or (str(sentiment_end_utc)[:10] if sentiment_end_utc else None)
        if rebuild_start_date is None:
            raise ValueError("La date de début est obligatoire pour reconstruire les features journalières sentiment.")
        return _build_sentiment_history_backfill_command(
            sentiment_start_utc=f"{rebuild_start_date}T00:00:00Z",
            sentiment_end_utc=f"{rebuild_end_date}T23:59:59Z" if rebuild_end_date else None,
            ticker_symbols=news_import_symbols,
            ticker_symbol_source=None if news_import_symbols else news_import_symbol_source,
            ticker_max_symbols=news_import_max_symbols,
            ingestion_source=options.sentiment_news_provider,
        )

    if step_key == "import_news":
        if news_import_start_date is None:
            raise ValueError("La date de début est obligatoire pour l'import des news.")
        command = _build_import_news_command(
            options,
            import_start_date=news_import_start_date,
            import_end_date=news_import_end_date,
            import_symbols=news_import_symbols,
            import_symbol_source=news_import_symbol_source,
            import_max_symbols=news_import_max_symbols,
            resume_from_checkpoint=bool(options.news_import_resume_from_checkpoint),
        )
        return command

    if step_key == "import_news_pending_loop":
        return _build_import_news_pending_loop_command(
            options,
            news_import_start_date=news_import_start_date,
            news_import_end_date=news_import_end_date,
            news_import_symbols=news_import_symbols,
            news_import_symbol_source=news_import_symbol_source,
            news_import_max_symbols=news_import_max_symbols,
        )

    if step_key == "score_history_relevance_backfill_auto":
        return _build_import_news_pending_loop_command(
            options,
            news_import_start_date=news_import_start_date,
            news_import_end_date=news_import_end_date,
            news_import_symbols=news_import_symbols,
            news_import_symbol_source=news_import_symbol_source,
            news_import_max_symbols=news_import_max_symbols,
            skip_import=True,
        )

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
            "--target-mode",
            options.ml_target_mode,
            "--forecast-horizon",
            str(options.ml_forecast_horizon),
            "--target-up-threshold",
            str(options.ml_target_up_threshold),
            "--target-down-threshold",
            str(options.ml_target_down_threshold),
            "--decision-threshold",
            str(options.ml_decision_threshold),
            "--calibration-method",
            options.ml_calibration_method,
            "--calibration-min-samples",
            str(options.ml_calibration_min_samples),
            "--calibration-max-iter",
            str(options.ml_calibration_max_iter),
            "--feature-set",
            options.ml_feature_set,
            "--benchmark-symbol",
            ml_benchmark_symbol,
            "--sequence-length",
            str(options.ml_sequence_length),
            "--batch-size",
            str(options.ml_batch_size),
            "--hidden-size",
            str(options.ml_hidden_size),
            "--ml-mode",
            options.ml_mode,
            "--training-start-date",
            options.ml_training_start_date,
            "--symbol-source",
            ml_symbol_source,
            "--artifacts-dir",
            ml_artifacts_dir,
            "--max-workers",
            str(options.ml_max_workers),
            "--max-epochs",
            str(options.ml_max_epochs),
            "--cross-sectional-min-universe",
            str(options.ml_cross_sectional_min_universe),
            "--lgbm-max-depth",
            str(options.ml_lgbm_max_depth),
            "--lgbm-n-estimators",
            str(options.ml_lgbm_n_estimators),
            "--lgbm-learning-rate",
            str(options.ml_lgbm_learning_rate),
            "--catboost-depth",
            str(options.ml_catboost_depth),
            "--catboost-iterations",
            str(options.ml_catboost_iterations),
            "--catboost-learning-rate",
            str(options.ml_catboost_learning_rate),
            "--default-champion",
            options.ml_default_champion,
            "--heartbeat-interval-seconds",
            str(options.ml_heartbeat_interval_seconds),
            "--log-level",
            str(options.ml_log_level or DEFAULT_ML_LOG_LEVEL).upper(),
        ]
        if options.ml_watchdog_timeout_seconds and options.ml_watchdog_timeout_seconds > 0:
            command.extend(["--watchdog-timeout-seconds", str(int(options.ml_watchdog_timeout_seconds))])
        if options.ml_include_sentiment:
            command.append("--include-sentiment")
        if options.ml_include_selector_context:
            command.append("--include-selector-context")
        if options.ml_debug_train:
            command.append("--debug-train")
        if options.ml_enable_lightgbm:
            command.append("--compare-lightgbm")
        if options.ml_enable_catboost:
            command.append("--enable-catboost")
        if options.ml_enable_global_model:
            command.extend(["--enable-global-model", "--global-model-name", options.ml_global_model_name])
        if ml_selector_signal_modes:
            command.append("--selector-universe-signal-modes")
            command.extend(ml_selector_signal_modes)
        if (
            options.ml_selector_universe_max_candidate_rank is not None
            and int(options.ml_selector_universe_max_candidate_rank) > 0
        ):
            command.extend([
                "--selector-universe-max-candidate-rank",
                str(int(options.ml_selector_universe_max_candidate_rank)),
            ])
        if options.ml_selector_universe_exclude_earnings_blackout:
            command.append("--selector-universe-exclude-earnings-blackout")
        if options.ml_enable_cross_sectional:
            command.append("--enable-cross-sectional")
        if options.ml_select_champion:
            command.extend(["--select-champion", "--champion-selection-metric", options.ml_champion_selection_metric])
        if options.ml_optimize_thresholds:
            command.extend([
                "--optimize-thresholds",
                "--min-action-rate",
                str(options.ml_min_action_rate),
                "--max-action-rate",
                str(options.ml_max_action_rate),
                "--min-precision-long",
                str(options.ml_min_precision_long),
            ])
            if options.ml_candidate_decision_thresholds:
                command.append("--candidate-decision-thresholds")
                command.extend(str(v) for v in options.ml_candidate_decision_thresholds)
        if options.ml_optimize_target:
            command.append("--optimize-target")
            command.extend(["--min-trades-fraction", str(options.ml_min_trades_fraction)])
            if options.ml_candidate_horizons:
                command.append("--candidate-horizons")
                command.extend(str(v) for v in options.ml_candidate_horizons)
            if options.ml_candidate_up_thresholds:
                command.append("--candidate-up-thresholds")
                command.extend(str(v) for v in options.ml_candidate_up_thresholds)
            if options.ml_candidate_down_thresholds:
                command.append("--candidate-down-thresholds")
                command.extend(str(v) for v in options.ml_candidate_down_thresholds)
        if options.ml_walkforward:
            command.extend([
                "--walkforward",
                "--wf-min-train-size",
                str(options.ml_wf_min_train_size),
                "--wf-val-size",
                str(options.ml_wf_val_size),
                "--wf-test-size",
                str(options.ml_wf_test_size),
                "--wf-step-size",
                str(options.ml_wf_step_size),
                "--wf-max-splits",
                str(options.ml_wf_max_splits),
            ])
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
            "--artifacts-dir",
            ml_artifacts_dir,
            "--log-level",
            str(options.ml_log_level or DEFAULT_ML_LOG_LEVEL).upper(),
        ]

    if step_key == "risk_management":
        command = [
            sys.executable,
            "-u",
            "-m",
            "risk_management",
            "--account-equity",
            str(options.risk_account_equity),
            "--risk-per-trade-pct",
            str(options.risk_per_trade_pct),
            "--max-positions",
            str(options.risk_max_positions),
            "--max-position-weight",
            str(options.risk_max_position_weight),
            "--max-sector-weight",
            str(options.risk_max_sector_weight),
            "--min-position-notional",
            str(options.risk_min_position_notional),
            "--score-weight",
            str(options.risk_score_weight),
            "--prediction-weight",
            str(options.risk_prediction_weight),
            "--correlation-threshold",
            str(options.risk_correlation_threshold),
            "--correlation-lookback-days",
            str(options.risk_correlation_lookback_days),
            "--correlation-min-overlap",
            str(options.risk_correlation_min_overlap),
            "--assumed-payoff-ratio",
            str(options.risk_payoff_ratio),
            "--kelly-fraction-multiplier",
            str(options.risk_kelly_fraction_multiplier),
            "--log-level",
            str(options.risk_log_level or DEFAULT_RISK_LOG_LEVEL).upper(),
        ]
        if options.risk_enable_kelly:
            command.append("--enable-kelly-sizing")
        if options.risk_dry_run:
            command.append("--dry-run")
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
        if options.execution_debug:
            command.append("--debug")
        if options.allow_outside_rth:
            command.append("--allow-outside-rth")
        if options.auto_rebalance:
            command.append("--auto-rebalance")
        command.extend(["--account-type", options.execution_account_type])
        command.extend(["--pdt-rule", options.execution_pdt_rule])
        # --swing-only utilise BooleanOptionalAction côté backend (cf. run_execution.py)
        command.append("--swing-only" if options.execution_swing_only else "--no-swing-only")
        # Stratégie de protection (P1) — toujours transmise pour reproductibilité
        command.extend(["--submission-window", options.execution_submission_window])
        command.extend(["--profit-taker-pct", str(options.execution_take_profit_pct)])
        command.extend(["--trailing-stop-pct", str(options.execution_trailing_stop_pct)])
        command.extend(["--trailing-activation-trigger", options.execution_trailing_trigger])
        if options.execution_trailing_trigger == "multiple_r":
            command.extend(["--trailing-activation-r-multiple", str(options.execution_trailing_r_multiple)])
        else:
            command.extend(["--trailing-activation-profit-pct", str(options.execution_trailing_profit_pct)])
        # Transition trigger trailing (P2 avancé)
        if options.execution_protection_transition_timeout_seconds and options.execution_protection_transition_timeout_seconds > 0:
            command.extend([
                "--protection-transition-timeout-seconds",
                str(int(options.execution_protection_transition_timeout_seconds)),
            ])
        if options.execution_protection_transition_poll_interval_seconds and options.execution_protection_transition_poll_interval_seconds > 0:
            command.extend([
                "--protection-transition-poll-interval-seconds",
                str(options.execution_protection_transition_poll_interval_seconds),
            ])
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

