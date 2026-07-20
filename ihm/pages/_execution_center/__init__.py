"""ihm/pages/_execution_center.py — Phase 6.2 (Backlog L10) + Sprint S6 / S6.1 (A-016).

Préfill exécution (compte/swing) + ``_build_launch_options`` (tous les
panneaux de paramètres pipeline : execution, risk, ML, screener, selector,
signal aggregator, corporate actions, data integrity).

Sprint S6 + S6.1 — refactor `_build_launch_options` (A-016) :
    * Introduction de :class:`LaunchOptionsContext` (état partagé immuable
      entre helpers).
    * **Extraction complète** des 9 sous-blocs en helpers privés
      ``_render_*_block`` (S6 : 3 blocs ; S6.1 : 6 blocs restants) :

      - :func:`_render_execution_block` (BLOCK 1)
      - :func:`_render_risk_block` (BLOCK 2)
      - :func:`_render_model_factory_block` (BLOCK 3)
      - :func:`_render_selector_block` (BLOCK 4)
      - :func:`_render_event_sentiment_block` (BLOCK 5)
      - :func:`_render_signal_aggregator_block` (BLOCK 6)
      - :func:`_render_screener_block` (BLOCK 7)
      - :func:`_render_data_integrity_block` (BLOCK 8)
      - :func:`_render_corporate_actions_block` (BLOCK 8b)
      - :func:`_render_live_confirmation_block` (BLOCK 9)

    * Le corps de :func:`_build_launch_options` se limite désormais à
      l'orchestration : appel séquentiel des 10 helpers (l'ordre des
      widgets Streamlit est strictement préservé) puis assemblage du
      :class:`PipelineLaunchOptions`.
    * Chaque appel reste préfixé par sa bannière
      ``# === BLOCK <N>/9 : <thème> (extrait — _render_*_block) ===``
      pour faciliter la navigation / le grep.
    * Tests E2E ajoutés via ``streamlit.testing.v1.AppTest`` (cf.
      ``tests/test_ihm_pipeline_e2e.py`` et
      ``tests/test_ihm_execution_e2e.py``).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, SupportsFloat, SupportsIndex, SupportsInt, cast

import streamlit as st

from event_sentiment.db_io import EventSentimentRepository

from ihm.pages._alpha_scanner_diagnostics import (
    _render_alpha_scanner_dependency_threshold_editor,
)
from ihm.pages._shared import (
    ALPHA_SCANNER_PARAMS_CAPTION,
    ALPHA_SCANNER_PARAMS_TITLE,
    EARNINGS_CUSTOM_WINDOW_KEY,
    EXECUTION_DEFAULTS_ACCOUNT_KEY,
    SCREENER_PARAMS_CAPTION,
    SCREENER_PARAMS_TITLE,
    PipelineLaunchOptions,
    _to_optional_positive_int,
)
from ihm.services.account_defaults import (
    PipelineExecutionDefaults,
    get_pipeline_execution_defaults,
)
from ihm.services.capital_presets import (
    CapitalPreset,
    build_capital_preset_executability_summary,
    get_capital_preset_by_key,
    load_capital_presets,
    resolve_capital_preset_for_equity,
)
from ihm.services.fractional_trading_preferences import (
    FractionalTradingPreferences,
    load_persisted_fractional_trading_preferences,
    save_persisted_fractional_trading_preferences,
)
from ihm.services.pipeline_runner import (
    DEFAULT_DATA_INTEGRITY_EARNINGS_BATCH_SIZE,
    DEFAULT_DATA_INTEGRITY_EARNINGS_LOG_EVERY,
    DEFAULT_DATA_INTEGRITY_EARNINGS_RESUME,
    DEFAULT_DATA_INTEGRITY_FUNDAMENTALS_LOG_EVERY,
    DEFAULT_DATA_INTEGRITY_PROVIDER_SLEEP_SECONDS,
    DEFAULT_DATA_INTEGRITY_QUOTES_BATCH_SIZE,
    DEFAULT_EODHD_ENABLE_STOOQ_CROSS_CHECK,
    DEFAULT_EODHD_WRITE_COMMIT_EVERY_SYMBOLS,
    DEFAULT_EVENT_SENTIMENT_FINBERT_BATCH_SIZE,
    DEFAULT_EVENT_SENTIMENT_FEATURE_FLUSH_EVERY_N_BATCHES,
    DEFAULT_EVENT_SENTIMENT_PENDING_LIMIT,
    DEFAULT_EVENT_SENTIMENT_PENDING_MAX_BATCHES_PER_RUN,
    DEFAULT_CA_SKIP_EXISTING,
    DEFAULT_CA_BATCH_SIZE,
    DEFAULT_CA_USE_CUSTOM_WINDOW,
    DEFAULT_CA_WINDOW_LOOKBACK_DAYS,
    DEFAULT_EXEC_DEBUG,
    DEFAULT_EXEC_MAX_ENTRY_GAP_PCT,
    DEFAULT_EXEC_TAKE_PROFIT_PCT,
    DEFAULT_EXEC_MANUAL_BUY_SL_PCT,
    DEFAULT_EXEC_PROTECTION_TRANSITION_POLL_INTERVAL_SECONDS,
    DEFAULT_EXEC_PROTECTION_TRANSITION_TIMEOUT_SECONDS,
    DEFAULT_EXEC_SUBMISSION_WINDOW,
    DEFAULT_EXEC_TRAILING_STOP_PCT,
    DEFAULT_EXEC_TRAILING_PROFIT_PCT,
    DEFAULT_EXEC_TRAILING_R_MULTIPLE,
    DEFAULT_EXEC_TRAILING_TRIGGER,
    DEFAULT_ML_CALIBRATION_METHOD,
    DEFAULT_ML_CALIBRATION_MAX_ITER,
    DEFAULT_ML_CALIBRATION_MIN_SAMPLES,
    DEFAULT_ML_CANDIDATE_DECISION_THRESHOLDS,
    DEFAULT_ML_CANDIDATE_DOWN_THRESHOLDS,
    DEFAULT_ML_CANDIDATE_HORIZONS,
    DEFAULT_ML_CANDIDATE_UP_THRESHOLDS,
    DEFAULT_ML_CATBOOST_DEPTH,
    DEFAULT_ML_CATBOOST_ITERATIONS,
    DEFAULT_ML_CATBOOST_LEARNING_RATE,
    DEFAULT_ML_CROSS_SECTIONAL_MIN_UNIVERSE,
    DEFAULT_ML_DECISION_THRESHOLD,
    DEFAULT_ML_DEFAULT_CHAMPION,
    DEFAULT_ML_DEBUG_TRAIN,
    DEFAULT_ML_FEATURE_SET,
    DEFAULT_ML_FORECAST_HORIZON,
    DEFAULT_ML_HEARTBEAT_INTERVAL_SECONDS,
    DEFAULT_ML_HIDDEN_SIZE,
    DEFAULT_ML_INCLUDE_SCREENER_SCORES,
    DEFAULT_ML_INCLUDE_SHORT_SCORE,
    DEFAULT_ML_INCLUDE_MACRO_VIX,
    DEFAULT_ML_INCLUDE_MACRO_VXN,
    DEFAULT_ML_INCLUDE_MACRO_VIX3M,
    DEFAULT_ML_INCLUDE_MACRO_MOVE,
    DEFAULT_ML_ENABLE_LIGHTGBM,
    DEFAULT_ML_ENABLE_CATBOOST,
    DEFAULT_ML_ENABLE_GLOBAL_MODEL,
    DEFAULT_ML_ENABLE_GLOBAL_STACKING,
    DEFAULT_ML_ENABLE_GLOBAL_CHALLENGER,
    DEFAULT_ML_GLOBAL_MODEL_NAME,
    DEFAULT_ML_ENABLE_CROSS_SECTIONAL,
    DEFAULT_ML_SELECT_CHAMPION,
    DEFAULT_ML_OPTIMIZE_THRESHOLDS,
    DEFAULT_ML_OPTIMIZE_TARGET,
    DEFAULT_ML_LGBM_LEARNING_RATE,
    DEFAULT_ML_LGBM_MAX_DEPTH,
    DEFAULT_ML_LGBM_N_ESTIMATORS,
    DEFAULT_ML_TRAINING_START_DATE,
    DEFAULT_ML_TRAINING_END_DATE,
    DEFAULT_ML_LOG_LEVEL,
    DEFAULT_ML_MAX_ACTION_RATE,
    DEFAULT_ML_MAX_EPOCHS,
    DEFAULT_ML_MAX_WORKERS,
    DEFAULT_ML_MIN_ACTION_RATE,
    DEFAULT_ML_MIN_PRECISION_LONG,
    DEFAULT_ML_MIN_TRADES_FRACTION,
    DEFAULT_ML_ARTIFACTS_DIR,
    DEFAULT_ML_BATCH_SIZE,
    DEFAULT_ML_BENCHMARK_SYMBOL,
    DEFAULT_ML_SEQUENCE_LENGTH,
    DEFAULT_ML_TARGET_DOWN_THRESHOLD,
    DEFAULT_ML_TARGET_MODE,
    DEFAULT_ML_TARGET_UP_THRESHOLD,
    DEFAULT_ML_TERNARY_WEIGHT_SHORT,
    DEFAULT_ML_TERNARY_WEIGHT_FLAT,
    DEFAULT_ML_TERNARY_WEIGHT_LONG,
    DEFAULT_ML_TERNARY_THRESHOLD_SHORT,
    DEFAULT_ML_TERNARY_THRESHOLD_LONG,
    DEFAULT_ML_TERNARY_TOP2_MARGIN,
    DEFAULT_ML_WALKFORWARD,
    DEFAULT_ML_WATCHDOG_TIMEOUT_SECONDS,
    DEFAULT_ML_WF_MAX_SPLITS,
    DEFAULT_ML_WF_MIN_TRAIN_SIZE,
    DEFAULT_ML_WF_STEP_SIZE,
    DEFAULT_ML_WF_TEST_SIZE,
    DEFAULT_ML_WF_VAL_SIZE,
    DEFAULT_RISK_CORRELATION_LOOKBACK_DAYS,
    DEFAULT_RISK_CORRELATION_MIN_OVERLAP,
    DEFAULT_RISK_CORRELATION_THRESHOLD,
    DEFAULT_RISK_ENABLE_KELLY,
    DEFAULT_RISK_MIN_POSITION_NOTIONAL,
    DEFAULT_RISK_KELLY_FRACTION_MULTIPLIER,
    DEFAULT_RISK_LOG_LEVEL,
    DEFAULT_RISK_MAX_DAILY_LOSS_PCT,
    DEFAULT_RISK_MAX_POSITION_WEIGHT,
    DEFAULT_RISK_MAX_PORTFOLIO_DRAWDOWN_PCT,
    DEFAULT_RISK_MAX_POSITIONS,
    DEFAULT_RISK_MAX_SECTOR_WEIGHT,
    DEFAULT_RISK_MIN_ML_COVERAGE_RATIO,
    DEFAULT_RISK_PAYOFF_RATIO,
    DEFAULT_RISK_PER_TRADE_PCT,
    DEFAULT_RISK_PREDICTION_WEIGHT,
    DEFAULT_RISK_SCORE_WEIGHT,
    DEFAULT_RISK_TARGET_ANNUAL_VOL,
    DEFAULT_RISK_VOL_TARGET_LOOKBACK_DAYS,
    DEFAULT_SCREENER_BENCHMARK_SYMBOL,
    DEFAULT_SCREENER_CHUNK_SIZE,
    DEFAULT_SCREENER_ENABLE_TWO_PASS_LOADING,
    DEFAULT_SCREENER_FIRST_PASS_WINDOW_DAYS,
    DEFAULT_SCREENER_HISTORICAL_RANGE_LOOKBACK_DAYS,
    DEFAULT_SCREENER_LIQUIDITY_THRESHOLD_USD,
    DEFAULT_SCREENER_MIN_HISTORICAL_RANGE_SCORE,
    DEFAULT_SCREENER_MIN_RELATIVE_STRENGTH_INDEX,
    DEFAULT_SELECTOR_REQUIRE_ABOVE_MA200,
    DEFAULT_SIGNAL_AGGREGATOR_LOG_LEVEL,
    DEFAULT_SIGNAL_AGGREGATOR_LOOKBACK_DAYS,
    DEFAULT_SIGNAL_AGGREGATOR_MACRO_WEIGHT,
    DEFAULT_SIGNAL_AGGREGATOR_MIN_NEWS_COUNT,
    DEFAULT_SIGNAL_AGGREGATOR_SENTIMENT_WEIGHT,
    DEFAULT_SIGNAL_AGGREGATOR_TIME_DECAY_HALF_LIFE_DAYS,
    DEFAULT_SELECTOR_CHUNK_SIZE,
    DEFAULT_SELECTOR_EARNINGS_BLACKOUT_DAYS,
    DEFAULT_SELECTOR_LIQUIDITY_THRESHOLD,
    DEFAULT_SELECTOR_LOG_LEVEL,
    DEFAULT_SELECTOR_MAX_ANOMALY_COUNT,
    DEFAULT_SELECTOR_MAX_ATR_PCT_20,
    DEFAULT_SELECTOR_MAX_SPREAD_BPS,
    DEFAULT_SELECTOR_MAX_VOLATILITY_RATIO,
    DEFAULT_SELECTOR_MIN_ATR_PCT_20,
    DEFAULT_SELECTOR_MIN_BETA_126,
    DEFAULT_SELECTOR_MIN_CLOSE,
    DEFAULT_SELECTOR_MIN_HIGH_52W_PROXIMITY,
    DEFAULT_SELECTOR_MIN_MARKET_CAP,
    DEFAULT_SELECTOR_MIN_RELATIVE_STRENGTH_INDEX,
    DEFAULT_SELECTOR_MIN_WEEKLY_TREND_SCORE,
    DEFAULT_SELECTOR_SECTOR_CAP_RATIO,
    DEFAULT_SELECTOR_SELECTION_SIZE,
    DEFAULT_SELECTOR_SHORT_SELECTION_SIZE,
    is_gpu_available,
    RECOMMENDED_ML_DEBUG_TRAIN_HEARTBEAT_INTERVAL_SECONDS,
    RECOMMENDED_ML_DEBUG_TRAIN_LOG_LEVEL,
    RECOMMENDED_ML_DEBUG_TRAIN_MAX_EPOCHS,
    RECOMMENDED_ML_DEBUG_TRAIN_MAX_WORKERS,
    RECOMMENDED_ML_DEBUG_TRAIN_WALKFORWARD,
    RECOMMENDED_ML_DEBUG_TRAIN_WATCHDOG_TIMEOUT_SECONDS,
    RECOMMENDED_ML_DEBUG_RAPIDE_ACCELERATOR,
    RECOMMENDED_ML_DEBUG_TRAIN_DEBUG_TRAIN,
    RECOMMENDED_ML_DEBUG_GPU_ACCELERATOR,
    RECOMMENDED_ML_DEBUG_GPU_DEBUG_TRAIN,
    RECOMMENDED_ML_DEBUG_GPU_HEARTBEAT_INTERVAL_SECONDS,
    RECOMMENDED_ML_DEBUG_GPU_LOG_LEVEL,
    RECOMMENDED_ML_DEBUG_GPU_MAX_EPOCHS,
    RECOMMENDED_ML_DEBUG_GPU_MAX_WORKERS,
    RECOMMENDED_ML_DEBUG_GPU_WALKFORWARD,
    RECOMMENDED_ML_DEBUG_GPU_WATCHDOG_TIMEOUT_SECONDS,
    RECOMMENDED_EVENT_SENTIMENT_FINBERT_BATCH_SIZE,
    RECOMMENDED_EVENT_SENTIMENT_PENDING_LIMIT,
    RECOMMENDED_EVENT_SENTIMENT_PENDING_MAX_BATCHES_PER_RUN,
    RECOMMENDED_ML_PROD_SWING_ACCELERATOR,
    RECOMMENDED_ML_PROD_SWING_DEBUG_TRAIN,
    RECOMMENDED_ML_PROD_SWING_HEARTBEAT_INTERVAL_SECONDS,
    RECOMMENDED_ML_PROD_SWING_LOG_LEVEL,
    RECOMMENDED_ML_PROD_SWING_MAX_EPOCHS,
    RECOMMENDED_ML_PROD_SWING_MAX_WORKERS,
    RECOMMENDED_ML_PROD_SWING_WALKFORWARD,
    RECOMMENDED_ML_PROD_SWING_WATCHDOG_TIMEOUT_SECONDS,
)
from ihm.services.ml_artifacts import list_ml_artifact_symbols  # noqa: F401  # re-export legacy
from ihm.services.queries import get_live_ml_first_diagnostic

__all__ = [
    "_apply_execution_prefills",
    "_apply_selected_ml_train_preset",
    "_apply_selected_capital_preset",
    "_build_ml_train_preset_summary",
    "_build_ml_train_preset_session_state_values",
    "_is_selected_ml_train_preset_dirty",
    "_build_parameter_rerun_guidance_rows",
    "_build_execution_prefill_caption",
    "_build_launch_options",
    # Sprint S19.1 — stubs d'API pour BLOCK 1 et BLOCK 3 (extraction
    # complète planifiée S19.1-bis ; cf. ``_render_pending.py``).
    "_render_execution_block",
    "_render_model_factory_block",
]


# Sprint S19.1 — exposition publique des stubs d'extraction (BLOCK 1 + 3).
from ihm.pages._execution_center._render_pending import (  # noqa: E402
    render_execution_block as _render_execution_block,
    render_model_factory_block as _render_model_factory_block,
)


EXECUTION_MODE_ACCOUNT_KEY = "pipeline_execution_mode_account_id"
DETECTED_BROKER_MODE_KEY = "pipeline_detected_broker_mode"
DETECTED_BROKER_MODE_ACCOUNT_KEY = "pipeline_detected_broker_mode_account_id"
DETECTED_ACCOUNT_TYPE_KEY = "pipeline_detected_account_type"
PIPELINE_ALLOW_FRACTIONAL_SHARES_KEY = "pipeline_allow_fractional_shares"
CAPITAL_PRESET_KEY = "pipeline_capital_preset"
CAPITAL_PRESET_APPLIED_SIGNATURE_KEY = "pipeline_capital_preset_applied_signature"
CAPITAL_PRESET_CUSTOM = "custom"
DETECTED_CAPITAL_PRESET_KEY = "pipeline_detected_capital_preset"
DETECTED_CAPITAL_PRESET_ACCOUNT_KEY = "pipeline_detected_capital_preset_account_id"
ML_TRAIN_PRESET_KEY = "pipeline_ml_train_preset"
ML_TRAIN_PRESET_APPLIED_SIGNATURE_KEY = "pipeline_ml_train_preset_applied_signature"
ML_TRAIN_PRESET_CUSTOM = "custom"
ML_TRAIN_PRESET_PROD_SWING = "prod_swing"
ML_TRAIN_PRESET_DEBUG_FAST = "debug_fast"
ML_TRAIN_PRESET_DEBUG_GPU = "debug_gpu"
ML_TRAIN_PRESET_DEBUG = "debug_train"
ML_TRAIN_PRESET_VERSION = "v1"
ML_TRAIN_PRESET_OPTIONS: tuple[str, ...] = (
    ML_TRAIN_PRESET_CUSTOM,
    ML_TRAIN_PRESET_PROD_SWING,
    ML_TRAIN_PRESET_DEBUG_FAST,
    ML_TRAIN_PRESET_DEBUG_GPU,
)

PARAMETER_RERUN_GUIDANCE_ROWS: tuple[tuple[str, str, str], ...] = (
    ("risk_*", "11 → 12", "Le sizing et les cibles changent, puis l'exécution consomme ces nouvelles cibles."),
    ("execution_*", "12", "Les règles d'envoi/compte/protections changent sans recalculer les cibles risk."),
    ("selector_*", "6 → 12", "Alpha Scanner reconstruit la shortlist finale, puis toutes les étapes aval doivent être rejouées."),
    ("screener_*", "3 → 12", "Le préfiltrage large change, donc tout l'aval du pipeline quotidien doit être recalculé."),
)


def _get_capital_presets() -> tuple[CapitalPreset, ...]:
    try:
        return load_capital_presets()
    except Exception:
        return ()


def _get_capital_preset_options() -> list[str]:
    return [CAPITAL_PRESET_CUSTOM, *[preset.key for preset in _get_capital_presets()]]


def _format_capital_preset_label(preset_key: str) -> str:
    if preset_key == CAPITAL_PRESET_CUSTOM:
        return "Personnalisé"
    preset = get_capital_preset_by_key(preset_key)
    return preset.label if preset is not None else preset_key


def _build_parameter_rerun_guidance_rows() -> tuple[dict[str, str], ...]:
    return tuple(
        {
            "Paramètres": family,
            "Relancer": rerun_steps,
            "Pourquoi": description,
        }
        for family, rerun_steps, description in PARAMETER_RERUN_GUIDANCE_ROWS
    )


def _normalize_ml_train_preset_key(preset_key: str | None) -> str:
    normalized = str(preset_key or ML_TRAIN_PRESET_CUSTOM).strip() or ML_TRAIN_PRESET_CUSTOM
    if normalized == ML_TRAIN_PRESET_DEBUG:
        return ML_TRAIN_PRESET_DEBUG_FAST
    if normalized in ML_TRAIN_PRESET_OPTIONS:
        return normalized
    return ML_TRAIN_PRESET_CUSTOM


def _coerce_session_date(value: object, *, default: date) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return date.fromisoformat(value.strip())
        except ValueError:
            return default
    return default


def _coerce_int(value: object, *, default: int | None) -> int:
    fallback = 0 if default is None else int(default)
    if value is None or value == "":
        return fallback
    try:
        return int(cast(str | bytes | bytearray | SupportsInt | SupportsIndex, value))
    except (TypeError, ValueError):
        return fallback


def _coerce_float(value: object, *, default: float | None) -> float:
    fallback = 0.0 if default is None else float(default)
    if value is None or value == "":
        return fallback
    try:
        return float(cast(str | SupportsFloat | SupportsIndex, value))
    except (TypeError, ValueError):
        return fallback


def _coerce_bool(value: object, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return bool(default)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off", ""}:
            return False
        return bool(default)
    if isinstance(value, (int, float)):
        return bool(value)
    return bool(default)


def _session_state_int(key: str, default: int | None) -> int:
    return _coerce_int(st.session_state.get(key, default), default=default)


def _session_state_float(key: str, default: float | None) -> float:
    return _coerce_float(st.session_state.get(key, default), default=default)


def _session_state_bool(key: str, default: bool) -> bool:
    coerced = _coerce_bool(st.session_state.get(key, default), default=default)
    # Les widgets Streamlit avec `key=` exigent un type cohérent en session.
    if key in st.session_state and not isinstance(st.session_state.get(key), bool):
        st.session_state[key] = coerced
    return coerced


def _ensure_normalized_ml_train_preset_session_state(session_state: dict[str, object]) -> str:
    raw_value = cast(str | None, session_state.get(ML_TRAIN_PRESET_KEY))
    normalized = _normalize_ml_train_preset_key(raw_value)
    if raw_value != normalized:
        session_state[ML_TRAIN_PRESET_KEY] = normalized
    return normalized


def _format_ml_train_preset_label(preset_key: str) -> str:
    normalized = _normalize_ml_train_preset_key(preset_key)
    return {
        ML_TRAIN_PRESET_CUSTOM: "Personnalisé",
        ML_TRAIN_PRESET_PROD_SWING: "Prod swing",
        ML_TRAIN_PRESET_DEBUG_FAST: "Debug rapide",
        ML_TRAIN_PRESET_DEBUG_GPU: "Debug GPU",
    }.get(normalized, normalized)


def _build_ml_train_preset_session_state_values(preset_key: str) -> dict[str, object]:
    normalized = _normalize_ml_train_preset_key(preset_key)
    if normalized == ML_TRAIN_PRESET_PROD_SWING:
        return {
            "pipeline_ml_accelerator": RECOMMENDED_ML_PROD_SWING_ACCELERATOR,
            "pipeline_ml_log_level": RECOMMENDED_ML_PROD_SWING_LOG_LEVEL,
            "pipeline_ml_debug_train": RECOMMENDED_ML_PROD_SWING_DEBUG_TRAIN,
            "pipeline_ml_max_workers": RECOMMENDED_ML_PROD_SWING_MAX_WORKERS,
            "pipeline_ml_walkforward": RECOMMENDED_ML_PROD_SWING_WALKFORWARD,
            "pipeline_ml_max_epochs": RECOMMENDED_ML_PROD_SWING_MAX_EPOCHS,
            "pipeline_ml_heartbeat_interval_seconds": RECOMMENDED_ML_PROD_SWING_HEARTBEAT_INTERVAL_SECONDS,
            "pipeline_ml_watchdog_timeout_seconds": RECOMMENDED_ML_PROD_SWING_WATCHDOG_TIMEOUT_SECONDS,
        }
    if normalized == ML_TRAIN_PRESET_DEBUG_FAST:
        return {
            "pipeline_ml_accelerator": RECOMMENDED_ML_DEBUG_RAPIDE_ACCELERATOR,
            "pipeline_ml_log_level": RECOMMENDED_ML_DEBUG_TRAIN_LOG_LEVEL,
            "pipeline_ml_debug_train": RECOMMENDED_ML_DEBUG_TRAIN_DEBUG_TRAIN,
            "pipeline_ml_max_workers": RECOMMENDED_ML_DEBUG_TRAIN_MAX_WORKERS,
            "pipeline_ml_walkforward": RECOMMENDED_ML_DEBUG_TRAIN_WALKFORWARD,
            "pipeline_ml_max_epochs": RECOMMENDED_ML_DEBUG_TRAIN_MAX_EPOCHS,
            "pipeline_ml_heartbeat_interval_seconds": RECOMMENDED_ML_DEBUG_TRAIN_HEARTBEAT_INTERVAL_SECONDS,
            "pipeline_ml_watchdog_timeout_seconds": RECOMMENDED_ML_DEBUG_TRAIN_WATCHDOG_TIMEOUT_SECONDS,
        }
    if normalized == ML_TRAIN_PRESET_DEBUG_GPU:
        return {
            "pipeline_ml_accelerator": RECOMMENDED_ML_DEBUG_GPU_ACCELERATOR,
            "pipeline_ml_log_level": RECOMMENDED_ML_DEBUG_GPU_LOG_LEVEL,
            "pipeline_ml_debug_train": RECOMMENDED_ML_DEBUG_GPU_DEBUG_TRAIN,
            "pipeline_ml_max_workers": RECOMMENDED_ML_DEBUG_GPU_MAX_WORKERS,
            "pipeline_ml_walkforward": RECOMMENDED_ML_DEBUG_GPU_WALKFORWARD,
            "pipeline_ml_max_epochs": RECOMMENDED_ML_DEBUG_GPU_MAX_EPOCHS,
            "pipeline_ml_heartbeat_interval_seconds": RECOMMENDED_ML_DEBUG_GPU_HEARTBEAT_INTERVAL_SECONDS,
            "pipeline_ml_watchdog_timeout_seconds": RECOMMENDED_ML_DEBUG_GPU_WATCHDOG_TIMEOUT_SECONDS,
        }
    return {}


def _build_ml_train_preset_summary(preset_key: str) -> str:
    normalized = _normalize_ml_train_preset_key(preset_key)
    expected_values = _build_ml_train_preset_session_state_values(normalized)
    if normalized == ML_TRAIN_PRESET_CUSTOM or not expected_values:
        return "🎛️ Preset ML manuel : aucun profil automatique n'est appliqué tant que tu restes en `Personnalisé`."

    accelerator = str(expected_values["pipeline_ml_accelerator"])
    log_level = str(expected_values["pipeline_ml_log_level"])
    debug_train = "on" if bool(expected_values["pipeline_ml_debug_train"]) else "off"
    walkforward = "on" if bool(expected_values["pipeline_ml_walkforward"]) else "off"
    max_workers = int(cast(int, expected_values["pipeline_ml_max_workers"]))
    max_epochs = int(cast(int, expected_values["pipeline_ml_max_epochs"]))
    heartbeat_seconds = float(cast(float, expected_values["pipeline_ml_heartbeat_interval_seconds"]))
    watchdog_seconds = int(cast(int, expected_values["pipeline_ml_watchdog_timeout_seconds"]))
    return (
        f"🧭 Preset ML actif : `{_format_ml_train_preset_label(normalized)}` · accélérateur `{accelerator}` · logs `{log_level}` "
        f"· debug `{debug_train}` · walk-forward `{walkforward}` · workers `{max_workers}` · epochs `{max_epochs}` "
        f"· heartbeat `{int(heartbeat_seconds)}` s · watchdog `{watchdog_seconds}` s"
    )


def _is_selected_ml_train_preset_dirty(session_state: dict[str, object]) -> bool:
    selected_key = _normalize_ml_train_preset_key(cast(str | None, session_state.get(ML_TRAIN_PRESET_KEY)))
    expected_values = _build_ml_train_preset_session_state_values(selected_key)
    if selected_key == ML_TRAIN_PRESET_CUSTOM or not expected_values:
        return False
    return any(session_state.get(session_key) != expected_value for session_key, expected_value in expected_values.items())


def _apply_selected_ml_train_preset(*, force: bool = False) -> None:
    selected_key = _normalize_ml_train_preset_key(cast(str | None, st.session_state.get(ML_TRAIN_PRESET_KEY)))
    signature = f"{selected_key}|{ML_TRAIN_PRESET_VERSION}"
    last_signature = str(st.session_state.get(ML_TRAIN_PRESET_APPLIED_SIGNATURE_KEY, "") or "")
    if not force and signature == last_signature:
        return
    if selected_key == ML_TRAIN_PRESET_CUSTOM:
        st.session_state[ML_TRAIN_PRESET_APPLIED_SIGNATURE_KEY] = signature
        return

    for session_key, value in _build_ml_train_preset_session_state_values(selected_key).items():
        st.session_state[session_key] = value

    st.session_state[ML_TRAIN_PRESET_APPLIED_SIGNATURE_KEY] = signature


def _apply_selected_capital_preset(
    defaults: PipelineExecutionDefaults | None,
    *,
    selected_account_id: str | None,
) -> None:
    selected_key = str(st.session_state.get(CAPITAL_PRESET_KEY, CAPITAL_PRESET_CUSTOM) or CAPITAL_PRESET_CUSTOM)
    effective_equity = float(defaults.equity) if defaults is not None and defaults.equity is not None else None
    signature = f"{selected_key}|{str(selected_account_id or '').strip()}|{effective_equity if effective_equity is not None else 'none'}"
    last_signature = str(st.session_state.get(CAPITAL_PRESET_APPLIED_SIGNATURE_KEY, "") or "")
    if signature == last_signature:
        return
    if selected_key == CAPITAL_PRESET_CUSTOM:
        st.session_state[CAPITAL_PRESET_APPLIED_SIGNATURE_KEY] = signature
        return

    preset = get_capital_preset_by_key(selected_key)
    if preset is None:
        st.session_state[CAPITAL_PRESET_APPLIED_SIGNATURE_KEY] = f"{CAPITAL_PRESET_CUSTOM}|{str(selected_account_id or '').strip()}"
        return

    for session_key, value in preset.to_session_state_values(detected_equity=effective_equity).items():
        st.session_state[session_key] = value

    if defaults is not None and defaults.equity is not None and defaults.equity > 0:
        st.session_state["pipeline_risk_account_equity"] = float(defaults.equity)

    st.session_state[CAPITAL_PRESET_APPLIED_SIGNATURE_KEY] = signature


def _apply_execution_prefills(selected_account_id: str | None) -> PipelineExecutionDefaults | None:
    cleaned_account_id = (selected_account_id or "").strip() or None
    if cleaned_account_id is None:
        st.session_state.pop(DETECTED_BROKER_MODE_KEY, None)
        st.session_state.pop(DETECTED_BROKER_MODE_ACCOUNT_KEY, None)
        st.session_state.pop(DETECTED_ACCOUNT_TYPE_KEY, None)
        st.session_state.pop(DETECTED_CAPITAL_PRESET_KEY, None)
        st.session_state.pop(DETECTED_CAPITAL_PRESET_ACCOUNT_KEY, None)
        return None

    try:
        defaults = get_pipeline_execution_defaults(cleaned_account_id)
    except Exception:
        st.session_state.pop(DETECTED_BROKER_MODE_KEY, None)
        st.session_state.pop(DETECTED_BROKER_MODE_ACCOUNT_KEY, None)
        st.session_state.pop(DETECTED_ACCOUNT_TYPE_KEY, None)
        st.session_state.pop(DETECTED_CAPITAL_PRESET_KEY, None)
        st.session_state.pop(DETECTED_CAPITAL_PRESET_ACCOUNT_KEY, None)
        st.session_state[EXECUTION_DEFAULTS_ACCOUNT_KEY] = cleaned_account_id
        return None

    if defaults is None:
        st.session_state.pop(DETECTED_BROKER_MODE_KEY, None)
        st.session_state.pop(DETECTED_BROKER_MODE_ACCOUNT_KEY, None)
        st.session_state.pop(DETECTED_ACCOUNT_TYPE_KEY, None)
        st.session_state.pop(DETECTED_CAPITAL_PRESET_KEY, None)
        st.session_state.pop(DETECTED_CAPITAL_PRESET_ACCOUNT_KEY, None)
        st.session_state[EXECUTION_DEFAULTS_ACCOUNT_KEY] = cleaned_account_id
        return None

    account_changed = st.session_state.get(EXECUTION_DEFAULTS_ACCOUNT_KEY) != cleaned_account_id
    st.session_state[DETECTED_BROKER_MODE_KEY] = defaults.broker_mode
    st.session_state[DETECTED_BROKER_MODE_ACCOUNT_KEY] = cleaned_account_id
    if defaults.account_type in {"margin", "cash"}:
        st.session_state[DETECTED_ACCOUNT_TYPE_KEY] = defaults.account_type
    else:
        st.session_state.pop(DETECTED_ACCOUNT_TYPE_KEY, None)
    detected_capital_preset = resolve_capital_preset_for_equity(defaults.equity)
    if detected_capital_preset is not None:
        st.session_state[DETECTED_CAPITAL_PRESET_KEY] = detected_capital_preset.key
        st.session_state[DETECTED_CAPITAL_PRESET_ACCOUNT_KEY] = cleaned_account_id
        if account_changed or CAPITAL_PRESET_KEY not in st.session_state:
            st.session_state[CAPITAL_PRESET_KEY] = detected_capital_preset.key
    else:
        st.session_state.pop(DETECTED_CAPITAL_PRESET_KEY, None)
        st.session_state.pop(DETECTED_CAPITAL_PRESET_ACCOUNT_KEY, None)
        if account_changed:
            st.session_state[CAPITAL_PRESET_KEY] = CAPITAL_PRESET_CUSTOM
    if defaults.equity is not None and defaults.equity > 0 and (
        account_changed or "pipeline_risk_account_equity" not in st.session_state
    ):
        # Aligne l'étape 11 avec l'equity du compte broker sélectionné.
        # On ne force pas si l'utilisateur a déjà surchargé manuellement la
        # valeur sur le même compte pendant la session.
        st.session_state["pipeline_risk_account_equity"] = float(defaults.equity)
    if defaults.account_type in {"margin", "cash"} and (
        account_changed or "pipeline_execution_account_type" not in st.session_state
    ):
        st.session_state["pipeline_execution_account_type"] = defaults.account_type
    if defaults.swing_only is not None and (
        account_changed or "pipeline_execution_swing_only" not in st.session_state
    ):
        st.session_state["pipeline_execution_swing_only"] = defaults.swing_only
    if defaults.broker_mode in {"paper", "live"} and (
        account_changed or "pipeline_execution_mode" not in st.session_state
    ):
        st.session_state["pipeline_execution_mode"] = defaults.broker_mode
        st.session_state[EXECUTION_MODE_ACCOUNT_KEY] = cleaned_account_id

    st.session_state[EXECUTION_DEFAULTS_ACCOUNT_KEY] = cleaned_account_id
    return defaults


def _build_execution_prefill_caption(defaults: PipelineExecutionDefaults | None) -> str | None:
    if defaults is None:
        return None

    notes: list[str] = []
    if defaults.broker_mode in {"paper", "live"}:
        notes.append(f"mode broker détecté : `{defaults.broker_mode}`")
    if defaults.account_type:
        notes.append(f"type de compte prérempli via broker : `{defaults.account_type}`")
    if defaults.equity is not None:
        notes.append(f"equity broker ≈ `{defaults.equity:,.2f}`")
    notes.append("`swing only` reste manuel car ce choix ne se déduit pas fiablement du seul montant du compte")
    return " | ".join(notes)


# ──────────────────────────────────────────────────────────────────────────────
# Sprint S6 (A-016) — découpage thématique de `_build_launch_options`
# ──────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class LaunchOptionsContext:
    """État partagé immuable entre les helpers ``_render_*_block``.

    Exposé pour faciliter les tests E2E (cf.
    ``tests/test_ihm_pipeline_e2e.py``) et la seconde passe d'extraction
    (S6.1) des sous-blocs Execution / Risk / ML / Selector / Data Integrity
    / Corporate Actions.
    """

    selected_account_id: str | None
    execution_defaults: PipelineExecutionDefaults | None
    selected_capital_preset: CapitalPreset | None
    capital_preset_key: str


CONTEXTUAL_BACKLOG_ESTIMATE_STATE_KEY = "pipeline_contextual_backlog_estimate_state"


def _build_contextual_backlog_estimate_scope(
    *,
    min_relevance: float,
    start_date_iso: str | None,
    end_date_iso: str | None,
    symbols_csv: str | None,
    ingestion_source: str | None,
) -> dict[str, object]:
    return {
        "min_relevance": round(float(min_relevance), 6),
        "start_date_iso": str(start_date_iso or "").strip() or None,
        "end_date_iso": str(end_date_iso or "").strip() or None,
        "symbols_csv": str(symbols_csv or "").strip().upper() or None,
        "ingestion_source": str(ingestion_source or "").strip().lower() or None,
    }


def _load_contextual_backlog_preview(
    min_relevance: float,
    start_date_iso: str | None = None,
    end_date_iso: str | None = None,
    symbols_csv: str | None = None,
    ingestion_source: str | None = None,
) -> dict[str, object]:
    """Retourne un aperçu du backlog contextuel restant.

    Le compteur reflète le comportement actuel du backend contextuel : paires
    présentes dans ``news_ticker_map`` mais absentes de
    ``news_ticker_sentiment``, filtrées par ``relevance_score`` minimal.

    Les paramètres de scope permettent de restreindre le comptage aux mêmes
    dates/symboles/provider que le loader SQL contextuel principal.

    Note métier : quand ``min_relevance > 0``, seules les paires avec
    ``news_ticker_map.relevance_score`` effectivement calculé et supérieur ou
    égal au seuil sont comptées.
    """
    from datetime import date as _date

    start_date_obj: _date | None = None
    end_date_obj: _date | None = None
    if start_date_iso:
        try:
            start_date_obj = _date.fromisoformat(start_date_iso)
        except ValueError:
            pass
    if end_date_iso:
        try:
            end_date_obj = _date.fromisoformat(end_date_iso)
        except ValueError:
            pass
    symbols_list = [
        symbol.strip().upper()
        for symbol in str(symbols_csv or "").split(",")
        if symbol and symbol.strip()
    ]
    try:
        repository = EventSentimentRepository()
        pending_pairs = repository.count_pending_contextual_pairs(
            min_relevance=float(min_relevance),
            start_date=start_date_obj,
            end_date=end_date_obj,
            symbols=symbols_list or None,
            ingestion_source=str(ingestion_source or "").strip().lower() or None,
        )
    except Exception as exc:  # noqa: BLE001 — best effort UI
        return {"error": str(exc)}
    return {"pending_pairs": int(pending_pairs)}


def _render_event_sentiment_block() -> dict[str, Any]:
    """Sous-bloc « Paramètres Event Sentiment » de ``_build_launch_options``.

    Retourne les valeurs nettoyées (``start_utc``, ``end_utc``, ``symbols``)
    qui seront passées à :class:`PipelineLaunchOptions`.
    """
    st.markdown("#### Paramètres Étape 7 — Event Sentiment")
    st.caption(
        "Ces réglages alimentent désormais l'étape 7 canonique à scope mixte : import news large sur "
        "`stock_scores_all`, scoring FinBERT standard / `relevance_score` / contextuel sur les candidats, "
        "reconstruction des features ticker sur les candidats et des features secteur sur le scope large importé. "
        "Si le CSV est laissé vide, les sous-étapes ciblées utilisent la sélection classée de `stock_scores` ; "
        "pour un import ou un backfill manuel d'un autre univers, utilisez le panneau `7.bis` ci-dessous."
    )

    sentiment_col1, sentiment_col2, sentiment_col3 = st.columns(3)
    with sentiment_col1:
        sentiment_start_utc = str(
            st.text_input(
                "Event Sentiment — start UTC",
                value=str(st.session_state.get("pipeline_sentiment_start_utc", "")),
                key="pipeline_sentiment_start_utc",
                help="Exemple : 2026-01-01T00:00:00Z",
            )
        ).strip()
    with sentiment_col2:
        sentiment_end_utc = str(
            st.text_input(
                "Event Sentiment — end UTC",
                value=str(st.session_state.get("pipeline_sentiment_end_utc", "")),
                key="pipeline_sentiment_end_utc",
                help="Exemple : 2026-01-31T23:59:59Z",
            )
        ).strip()
    with sentiment_col3:
        sentiment_symbols = str(
            st.text_input(
                "Event Sentiment — symboles (CSV)",
                value=str(st.session_state.get("pipeline_sentiment_symbols", "")),
                key="pipeline_sentiment_symbols",
                help="Exemple : AAPL,MSFT,NVDA",
            )
        ).strip().upper()
    st.caption(
        "⚙️ `CSV` n'affecte que les sous-étapes ciblées candidats de l'étape 7 (standard / relevance / contextual / ticker). "
        "L'import brut canonique reste piloté sur `stock_scores_all` ; pour modifier l'univers d'import lui-même, passez par `7.bis`.")

    provider_col, relevance_mode_col = st.columns(2)
    _provider_options = ("eodhd", "alpaca", "finnhub")
    _current_provider = str(
        st.session_state.get("pipeline_sentiment_news_provider", "eodhd")
    ).strip().lower()
    if _current_provider not in _provider_options:
        _current_provider = "eodhd"
    with provider_col:
        sentiment_news_provider = str(
            st.selectbox(
                "Event Sentiment — source news",
                options=_provider_options,
                index=_provider_options.index(_current_provider),
                key="pipeline_sentiment_news_provider",
                help=(
                    "Provider news utilisé par `python -m event_sentiment`. "
                    "Défaut produit : EODHD (Financial News Feed). "
                    "Bascule possible vers Alpaca ou Finnhub sans migration "
                    "DB (les checkpoints sont séparés par source_name)."
                ),
            )
        )
    _relevance_options = ("provider_default", "strict", "scored")
    _current_relevance = str(
        st.session_state.get(
            "pipeline_sentiment_ticker_relevance_mode", "provider_default"
        )
    ).strip().lower()
    if _current_relevance not in _relevance_options:
        _current_relevance = "provider_default"
    with relevance_mode_col:
        sentiment_ticker_relevance_mode = str(
            st.selectbox(
                "Event Sentiment — mapping ticker",
                options=_relevance_options,
                index=_relevance_options.index(_current_relevance),
                key="pipeline_sentiment_ticker_relevance_mode",
                help=(
                    "'provider_default' : conserve tous les tickers tagués par le "
                    "provider (comportement historique). 'strict' : ne propage "
                    "le score qu'au 1er ticker (~= primary). "
                    "'scored' : calcule un score [0,1] de pertinence par paire "
                    "(article, ticker) et l'utilise comme poids dans les "
                    "agrégats journaliers downstream."
                ),
            )
        )

    sentiment_min_relevance_score = float(
        st.number_input(
            "Event Sentiment — seuil min relevance (mode 'scored')",
            min_value=0.0,
            max_value=1.0,
            step=0.05,
            value=_session_state_float("pipeline_sentiment_min_relevance_score", 0.0),
            key="pipeline_sentiment_min_relevance_score",
            help=(
                "Seuil [0.0, 1.0] sous lequel une paire (article, ticker) est "
                "écartée de news_ticker_map. 0.0 = aucun filtrage. Ignoré "
                "hors mode 'scored'."
            ),
        )
    )

    sentiment_scoring_mode = "standard_and_contextual"
    sentiment_enable_contextual_scoring = True
    st.session_state["pipeline_sentiment_scoring_mode"] = sentiment_scoring_mode
    st.session_state["pipeline_sentiment_enable_contextual_scoring"] = sentiment_enable_contextual_scoring
    st.info(
        "Le mode de scoring n'est plus configurable ici : l'étape 7 fusionnée exécute toujours la chaîne complète "
        "standard → relevance_score → agrégation journalière → contextuel. Pour rejouer uniquement une sous-étape, utilisez le panneau `News-Sentiement Traitement par étape`."
    )

    with st.expander("Performance FinBERT / backlog pending", expanded=False):
        st.caption(
            "Ces réglages pilotent le débit réel du backlog pending. "
            f"Défauts backend : limit `{DEFAULT_EVENT_SENTIMENT_PENDING_LIMIT}`, "
            f"batchs/process `{DEFAULT_EVENT_SENTIMENT_PENDING_MAX_BATCHES_PER_RUN}`, "
            f"batch FinBERT `{DEFAULT_EVENT_SENTIMENT_FINBERT_BATCH_SIZE}`. "
            f"Valeurs IHM recommandées : `{RECOMMENDED_EVENT_SENTIMENT_PENDING_LIMIT}` / "
            f"`{RECOMMENDED_EVENT_SENTIMENT_PENDING_MAX_BATCHES_PER_RUN}` / "
            f"`{RECOMMENDED_EVENT_SENTIMENT_FINBERT_BATCH_SIZE}`. En cas d'OOM GPU, le backend tente "
            "automatiquement `64 -> 32 -> 16` avant fallback CPU. "
            "Dans l'IHM, la valeur préremplie pour `Batchs pending / process Python` est désormais `0` "
            "afin que le scoring standard manuel et les wrappers drainent le backlog jusqu'au bout par défaut."
        )
        perf_col1, perf_col2, perf_col3 = st.columns(3)
        with perf_col1:
            sentiment_pending_limit = int(
                st.number_input(
                    "Articles pending / batch",
                    min_value=100,
                    max_value=100_000,
                    step=500,
                    value=_session_state_int(
                        "pipeline_sentiment_pending_limit",
                        RECOMMENDED_EVENT_SENTIMENT_PENDING_LIMIT,
                    ),
                    key="pipeline_sentiment_pending_limit",
                    help=(
                        "Nombre max d'articles pending scorés par sous-batch. "
                        "Plus haut = moins d'overhead, mais plus de RAM/VRAM consommée."
                    ),
                )
            )
        with perf_col2:
            sentiment_pending_max_batches_per_run = int(
                st.number_input(
                    "Batchs pending / process Python",
                    min_value=0,
                    max_value=100,
                    step=1,
                    value=_session_state_int(
                        "pipeline_sentiment_pending_max_batches_per_run",
                        0,
                    ),
                    key="pipeline_sentiment_pending_max_batches_per_run",
                    help=(
                        "Nombre de sous-batchs pending successifs traités dans le même process Python. "
                        "Augmenter pour réduire les redémarrages de process sur gros backlog. "
                        "`0` = aucun plafond : le process vide tout le backlog du scope demandé."
                    ),
                )
            )
        with perf_col3:
            sentiment_finbert_batch_size = int(
                st.number_input(
                    "Batch size FinBERT",
                    min_value=1,
                    max_value=256,
                    step=8,
                    value=_session_state_int(
                        "pipeline_sentiment_finbert_batch_size",
                        RECOMMENDED_EVENT_SENTIMENT_FINBERT_BATCH_SIZE,
                    ),
                    key="pipeline_sentiment_finbert_batch_size",
                    help=(
                        "Batch size GPU/CPU pour FinBERT standard et contextuel. "
                        "Le backend réduit automatiquement à 32 puis 16 en cas d'OOM GPU."
                    ),
                )
            )
        flush_col1, flush_col2 = st.columns(2)
        with flush_col1:
            sentiment_feature_flush_every_n_batches = int(
                st.number_input(
                    "Flush features tous les N sous-batchs (0 = final only)",
                    min_value=0,
                    max_value=100,
                    step=1,
                    value=_session_state_int(
                        "pipeline_sentiment_feature_flush_every_n_batches",
                        DEFAULT_EVENT_SENTIMENT_FEATURE_FLUSH_EVERY_N_BATCHES,
                    ),
                    key="pipeline_sentiment_feature_flush_every_n_batches",
                    help=(
                        "Si > 0, reconstruit et persiste les features ticker/secteur tous les N sous-batchs pending. "
                        "Permet de matérialiser plus tôt les agrégats sur gros backlogs."
                    ),
                )
            )
        with flush_col2:
            if sentiment_feature_flush_every_n_batches > 0:
                st.info(
                    f"Flush intermédiaire activé : persistance features toutes les `{sentiment_feature_flush_every_n_batches}` itérations pending."
                )
            else:
                st.caption("Flush final unique conservé : comportement historique du pipeline.")

    # Niveau 4 — re-scoring FinBERT contextualisé par couple (article, symbol).
    with st.expander("Étape 7 — Scoring contextuel FinBERT (Niveau 4)", expanded=False):
        st.caption(
            "Paramètres de la 5e sous-étape de l'étape 7 fusionnée. "
            "Le scoring contextuel Niveau 4 enrichit `news_ticker_sentiment` après le scoring standard, "
            "le calcul `relevance_score` et l'agrégation journalière. "
            "Le cap de paires contextuelles borne désormais **chaque lot interne** : si vous mettez `5000`, "
            "le backend charge/scorera `5000` couples `(article, symbole)` à la fois puis rebouclera automatiquement jusqu'à épuisement du backlog sur le scope demandé."
        )
        ctx_col1, ctx_col2 = st.columns(2)
        with ctx_col1:
            sentiment_contextual_min_relevance = float(
                st.number_input(
                    "Seuil min relevance (skip si <)",
                    min_value=0.0,
                    max_value=1.0,
                    step=0.05,
                    value=_session_state_float(
                        "pipeline_sentiment_contextual_min_relevance",
                        0.3,
                    ),
                    key="pipeline_sentiment_contextual_min_relevance",
                    help=(
                        "Ne tokenise FinBERT contextuel que si "
                        "relevance_score ≥ seuil (perf garde-fou). "
                        "Le relevance_score ayant été calculé par l'étape 7, ce filtre est désormais réel."
                    ),
                )
            )
        with ctx_col2:
            sentiment_contextual_max_pairs = int(
                st.number_input(
                    "Taille lot paires contextuelles",
                    min_value=100,
                    max_value=5000_000,
                    step=500,
                    value=_session_state_int(
                        "pipeline_sentiment_contextual_max_pairs",
                        50000,
                    ),
                    key="pipeline_sentiment_contextual_max_pairs",
                    help=(
                        "Nombre max de paires `(article, symbole)` chargées/scorées dans un lot contextuel. "
                        "Le pipeline reboucle ensuite automatiquement jusqu'à épuisement du backlog. "
                        "Ne pas mettre 'illimité' par défaut : sur gros historique cela chargerait trop de paires en mémoire en une seule fois."
                    ),
                )
            )

        # Paramètres batch et purge conservés pour l'étape 7 fusionnée + les outils de maintenance.
        backfill_relevance_rescore_all: bool = False
        batch_purge_col1, batch_purge_col2 = st.columns(2)
        with batch_purge_col1:
            backfill_relevance_batch_size = int(
                st.number_input(
                    "Batch size contextuel",
                    min_value=50,
                    max_value=10_000,
                    step=50,
                    value=_session_state_int("pipeline_backfill_relevance_batch_size", 500),
                    key="pipeline_backfill_relevance_batch_size",
                    help="Taille des lots de paires (article, symbole) envoyées à FinBERT à la fois.",
                )
            )
        with batch_purge_col2:
            backfill_relevance_purge_below = float(
                st.number_input(
                    "Purge below (0 = off)",
                    min_value=0.0,
                    max_value=1.0,
                    step=0.05,
                    value=_session_state_float("pipeline_backfill_relevance_purge_below", 0.0),
                    key="pipeline_backfill_relevance_purge_below",
                    help=(
                        "Si > 0 : DELETE des lignes `news_ticker_map` avec "
                        "`relevance_score < seuil` (FK CASCADE supprime aussi `news_ticker_sentiment` associé). "
                        "Appliqué dans l'étape 7 après le calcul du relevance_score."
                    ),
                )
            )
        # Filtre de dates pour le comptage du backlog contextuel
        st.caption(
            "Restreindre l'estimation du backlog au même scope que le scoring contextuel "
            "(filtre sur `news_raw.effective_trade_date`, symboles et provider). Laissez les deux champs vides pour un comptage global."
        )
        backlog_date_col1, backlog_date_col2 = st.columns(2)
        with backlog_date_col1:
            _backlog_start_default = cast(
                date | None,
                st.session_state.get("pipeline_contextual_backlog_start_date", None),
            )
            _backlog_start_picker = st.date_input(
                "Backlog contextuel — date de début",
                value=_backlog_start_default,
                key="pipeline_contextual_backlog_start_date",
                format="YYYY-MM-DD",
                help=(
                    "Date de début (incluse) pour filtrer les paires contextuelles "
                    "encore à traiter. Laissez vide pour ne pas filtrer en bas."
                ),
            )
        with backlog_date_col2:
            _backlog_end_default = cast(
                date | None,
                st.session_state.get("pipeline_contextual_backlog_end_date", None),
            )
            _backlog_end_picker = st.date_input(
                "Backlog contextuel — date de fin",
                value=_backlog_end_default,
                key="pipeline_contextual_backlog_end_date",
                format="YYYY-MM-DD",
                help=(
                    "Date de fin (incluse) pour filtrer les paires contextuelles "
                    "encore à traiter. Laissez vide pour ne pas filtrer en haut."
                ),
            )
        _backlog_start_iso: str | None = (
            _backlog_start_picker.isoformat()
            if isinstance(_backlog_start_picker, date)
            else None
        )
        _backlog_end_iso: str | None = (
            _backlog_end_picker.isoformat()
            if isinstance(_backlog_end_picker, date)
            else None
        )
        # Validation de cohérence des dates du filtre backlog
        _backlog_dates_valid = True
        if (
            _backlog_start_iso is not None
            and _backlog_end_iso is not None
            and _backlog_start_picker > _backlog_end_picker  # type: ignore[operator]
        ):
            st.error(
                "Plage de dates backlog invalide : la date de début doit être ≤ la date de fin. "
                "Les deux bornes seront ignorées pour l'estimation."
            )
            _backlog_dates_valid = False
            _backlog_start_iso = None
            _backlog_end_iso = None

        estimate_scope = _build_contextual_backlog_estimate_scope(
            min_relevance=float(sentiment_contextual_min_relevance),
            start_date_iso=_backlog_start_iso,
            end_date_iso=_backlog_end_iso,
            symbols_csv=sentiment_symbols,
            ingestion_source=sentiment_news_provider,
        )

        estimate_col1, estimate_col2 = st.columns([1, 3])
        with estimate_col1:
            estimate_clicked = st.button(
                "Estimer",
                key="pipeline_contextual_backlog_estimate_button",
                use_container_width=True,
                disabled=not _backlog_dates_valid,
            )
        with estimate_col2:
            st.caption(
                "Le calcul d'estimation est manuel pour éviter de bloquer l'IHM à chaque affichage. "
                "Il tient compte du provider, des symboles, des bornes de dates et du `Seuil min relevance`."
            )

        if estimate_clicked and _backlog_dates_valid:
            with st.spinner("Estimation du backlog contextuel en cours…"):
                st.session_state[CONTEXTUAL_BACKLOG_ESTIMATE_STATE_KEY] = {
                    "scope": estimate_scope,
                    "preview": _load_contextual_backlog_preview(
                        float(sentiment_contextual_min_relevance),
                        _backlog_start_iso,
                        _backlog_end_iso,
                        sentiment_symbols,
                        sentiment_news_provider,
                    ),
                }

        stored_estimate_state = st.session_state.get(CONTEXTUAL_BACKLOG_ESTIMATE_STATE_KEY)
        contextual_backlog_preview: dict[str, object] | None = None
        if isinstance(stored_estimate_state, dict) and stored_estimate_state.get("scope") == estimate_scope:
            stored_preview = stored_estimate_state.get("preview")
            if isinstance(stored_preview, dict):
                contextual_backlog_preview = stored_preview
        elif stored_estimate_state is None:
            st.info("Cliquez sur `Estimer` pour calculer le backlog contextuel sur le scope courant.")
        else:
            st.caption(
                "Les paramètres du scope courant diffèrent de la dernière estimation affichée. "
                "Cliquez sur `Estimer` pour recalculer avec les nouvelles valeurs."
            )

        if contextual_backlog_preview is not None and contextual_backlog_preview.get("error"):
            st.caption(
                "Impossible d'estimer le backlog contextuel restant : "
                f"{contextual_backlog_preview.get('error')}"
            )
        elif contextual_backlog_preview is not None:
            pending_contextual_pairs = _coerce_int(
                contextual_backlog_preview.get("pending_pairs"),
                default=0,
            )
            estimated_batches_needed = (
                (pending_contextual_pairs + max(int(sentiment_contextual_max_pairs), 1) - 1)
                // max(int(sentiment_contextual_max_pairs), 1)
                if pending_contextual_pairs > 0
                else 0
            )
            estimated_additional_batches = max(estimated_batches_needed - 1, 0)
            backlog_col1, backlog_col2 = st.columns(2)
            with backlog_col1:
                st.metric(
                    "Paires contextuelles encore à traiter",
                    f"{pending_contextual_pairs:,}".replace(",", " "),
                )
            with backlog_col2:
                st.metric(
                    "Lots internes estimés après le premier",
                    estimated_additional_batches,
                )
            _date_filter_suffix = ""
            if _backlog_start_iso or _backlog_end_iso:
                _parts = []
                if _backlog_start_iso:
                    _parts.append(f"du `{_backlog_start_iso}`")
                if _backlog_end_iso:
                    _parts.append(f"au `{_backlog_end_iso}`")
                _date_filter_suffix = f" · fenêtre {' '.join(_parts)}"
            st.caption(
                "Estimation manuelle alignée sur le backend contextuel actuel : backlog des paires absentes de `news_ticker_sentiment`, "
                f"filtré avec `relevance_score >= {float(sentiment_contextual_min_relevance):g}`{_date_filter_suffix}. "
                f"Avec des lots internes de `{int(sentiment_contextual_max_pairs)}` paires, cela représente ≈ `{estimated_batches_needed}` lot(s) contextuels successifs drainés automatiquement dans le même run."
            )

    return {
        "sentiment_start_utc": sentiment_start_utc,
        "sentiment_end_utc": sentiment_end_utc,
        "sentiment_symbols": sentiment_symbols,
        "sentiment_news_provider": sentiment_news_provider,
        "sentiment_ticker_relevance_mode": sentiment_ticker_relevance_mode,
        "sentiment_min_relevance_score": sentiment_min_relevance_score,
        "sentiment_scoring_mode": sentiment_scoring_mode,
        "sentiment_enable_contextual_scoring": sentiment_enable_contextual_scoring,
        "sentiment_contextual_min_relevance": sentiment_contextual_min_relevance,
        "sentiment_contextual_max_pairs": sentiment_contextual_max_pairs,
        "sentiment_pending_limit": sentiment_pending_limit,
        "sentiment_pending_max_batches_per_run": sentiment_pending_max_batches_per_run,
        "sentiment_feature_flush_every_n_batches": sentiment_feature_flush_every_n_batches,
        "sentiment_finbert_batch_size": sentiment_finbert_batch_size,
        "backfill_relevance_dry_run": False,
        "backfill_relevance_rescore_all": False,
        "backfill_relevance_batch_size": backfill_relevance_batch_size,
        "backfill_relevance_purge_below": backfill_relevance_purge_below,
    }


def _render_signal_aggregator_block() -> dict[str, Any]:
    """Sous-bloc « Paramètres Signal Aggregator » de ``_build_launch_options``."""
    st.markdown("#### Paramètres Signal Aggregator")
    st.caption(
        "Ces réglages reflètent les options réellement supportées par `python -m event_sentiment.signal_aggregator`. "
        "La `trade date` réutilise le champ global situé en haut du formulaire quand il est renseigné."
    )

    signal_agg_col1, signal_agg_col2, signal_agg_col3 = st.columns(3)
    with signal_agg_col1:
        signal_aggregator_all_symbols = st.checkbox(
            "Signal Aggregator — traiter tous les symboles",
            value=_session_state_bool("pipeline_signal_aggregator_all_symbols", False),
            key="pipeline_signal_aggregator_all_symbols",
        )
        signal_aggregator_log_level = cast(
            str,
            st.selectbox(
                "Signal Aggregator — niveau de log",
                options=["DEBUG", "INFO", "WARNING", "ERROR"],
                index=["DEBUG", "INFO", "WARNING", "ERROR"].index(
                    cast(str, st.session_state.get("pipeline_signal_aggregator_log_level", DEFAULT_SIGNAL_AGGREGATOR_LOG_LEVEL)).upper()
                    if str(st.session_state.get("pipeline_signal_aggregator_log_level", DEFAULT_SIGNAL_AGGREGATOR_LOG_LEVEL)).upper() in {"DEBUG", "INFO", "WARNING", "ERROR"}
                    else DEFAULT_SIGNAL_AGGREGATOR_LOG_LEVEL
                ),
                key="pipeline_signal_aggregator_log_level",
            ),
        )
    with signal_agg_col2:
        signal_aggregator_sentiment_weight = float(
            st.number_input(
                "Signal Aggregator — poids sentiment",
                min_value=0.0,
                max_value=1.0,
                value=_session_state_float(
                    "pipeline_signal_aggregator_sentiment_weight",
                    DEFAULT_SIGNAL_AGGREGATOR_SENTIMENT_WEIGHT,
                ),
                step=0.01,
                format="%.2f",
                key="pipeline_signal_aggregator_sentiment_weight",
            )
        )
        signal_aggregator_macro_weight = float(
            st.number_input(
                "Signal Aggregator — poids macro sectoriel",
                min_value=0.0,
                max_value=1.0,
                value=_session_state_float(
                    "pipeline_signal_aggregator_macro_weight",
                    DEFAULT_SIGNAL_AGGREGATOR_MACRO_WEIGHT,
                ),
                step=0.01,
                format="%.2f",
                key="pipeline_signal_aggregator_macro_weight",
            )
        )
    with signal_agg_col3:
        signal_aggregator_lookback_days = int(
            st.number_input(
                "Signal Aggregator — lookback (jours)",
                min_value=1,
                value=_session_state_int(
                    "pipeline_signal_aggregator_lookback_days",
                    DEFAULT_SIGNAL_AGGREGATOR_LOOKBACK_DAYS,
                ),
                step=1,
                key="pipeline_signal_aggregator_lookback_days",
            )
        )
        signal_aggregator_min_news_count = int(
            st.number_input(
                "Signal Aggregator — news mini",
                min_value=1,
                value=_session_state_int(
                    "pipeline_signal_aggregator_min_news_count",
                    DEFAULT_SIGNAL_AGGREGATOR_MIN_NEWS_COUNT,
                ),
                step=1,
                key="pipeline_signal_aggregator_min_news_count",
            )
        )

    signal_agg_decay_col1, signal_agg_decay_col2 = st.columns(2)
    with signal_agg_decay_col1:
        signal_aggregator_time_decay_half_life_days = float(
            st.number_input(
                "Signal Aggregator — demi-vie décroissance (jours)",
                min_value=0.1,
                value=_session_state_float(
                    "pipeline_signal_aggregator_time_decay_half_life_days",
                    DEFAULT_SIGNAL_AGGREGATOR_TIME_DECAY_HALF_LIFE_DAYS,
                ),
                step=0.1,
                format="%.2f",
                key="pipeline_signal_aggregator_time_decay_half_life_days",
            )
        )
    with signal_agg_decay_col2:
        derived_quant_weight = round(1.0 - signal_aggregator_sentiment_weight - signal_aggregator_macro_weight, 4)
        if derived_quant_weight < 0:
            st.error(
                "Configuration invalide côté Signal Aggregator : `poids sentiment + poids macro > 1.0`. "
                "Le backend rejettera ce lancement."
            )
        else:
            st.info(f"Poids quantitatif implicite côté backend : `{derived_quant_weight}`")

    return {
        "signal_aggregator_all_symbols": signal_aggregator_all_symbols,
        "signal_aggregator_log_level": signal_aggregator_log_level,
        "signal_aggregator_sentiment_weight": signal_aggregator_sentiment_weight,
        "signal_aggregator_macro_weight": signal_aggregator_macro_weight,
        "signal_aggregator_lookback_days": signal_aggregator_lookback_days,
        "signal_aggregator_min_news_count": signal_aggregator_min_news_count,
        "signal_aggregator_time_decay_half_life_days": signal_aggregator_time_decay_half_life_days,
    }


def _render_live_confirmation_block(execution_mode: str) -> bool:
    """Sous-bloc « Confirmation LIVE » de ``_build_launch_options``.

    Affiche le checkbox de confirmation LIVE quand
    ``execution_mode == "live"`` et retourne ``True`` sinon (mode paper /
    simulate ⇒ aucune confirmation requise).
    """
    if execution_mode != "live":
        return True
    st.warning("Mode LIVE sélectionné : cette action peut envoyer de vrais ordres chez le broker.")
    st.caption(
        "S8 — le mode live exige désormais un token d'approbation opérateur et écrit/valide un "
        "run plan immuable côté backend."
    )
    approval_token = str(
        st.text_input(
            "Token d'approbation live",
            value=str(st.session_state.get("pipeline_execution_live_approval_token", "")),
            key="pipeline_execution_live_approval_token",
            type="password",
            help=(
                "Comparé côté backend à `ALPHA_TRADE_LIVE_APPROVAL_TOKEN`. Obligatoire pour tout run live."
            ),
        )
    ).strip()
    st.text_input(
        "Fichier run plan immuable (optionnel)",
        value=str(st.session_state.get("pipeline_execution_run_plan_file", "")),
        key="pipeline_execution_run_plan_file",
        help=(
            "Si renseigné, le backend vérifie que le contenu du fichier correspond exactement aux paramètres du run. "
            "Si laissé vide, un plan horodaté est créé automatiquement dans `artifacts/execution_run_plans/`."
        ),
    )
    if not approval_token:
        st.error("Le token d'approbation live est requis pour déverrouiller le lancement.")
    return bool(
        st.checkbox(
            "Je confirme explicitement le lancement en LIVE",
            value=_session_state_bool("pipeline_live_confirmed", False),
            key="pipeline_live_confirmed",
        )
    ) and bool(approval_token)


def _render_screener_block() -> dict[str, Any]:
    """Sous-bloc « Paramètres Screener » de ``_build_launch_options``."""
    st.markdown(SCREENER_PARAMS_TITLE)
    st.caption(SCREENER_PARAMS_CAPTION)
    st.caption(
        "Ces réglages reflètent les options réellement disponibles côté `screener.stock_screener`. "
        "`0` sur `max workers` signifie : auto (`os.cpu_count()`)."
    )

    screener_col1, screener_col2, screener_col3 = st.columns(3)
    with screener_col1:
        screener_chunk_size = int(
            st.number_input(
                "Screener — taille de chunk",
                min_value=1,
                value=_session_state_int(
                    "pipeline_screener_chunk_size",
                    DEFAULT_SCREENER_CHUNK_SIZE,
                ),
                step=50,
                key="pipeline_screener_chunk_size",
            )
        )
        screener_max_workers = int(
            st.number_input(
                "Screener — max workers (0 = auto)",
                min_value=0,
                value=_session_state_int("pipeline_screener_max_workers", 0),
                step=1,
                key="pipeline_screener_max_workers",
            )
        )
        screener_benchmark_symbol = str(
            st.text_input(
                "Screener — benchmark",
                value=str(st.session_state.get("pipeline_screener_benchmark_symbol", DEFAULT_SCREENER_BENCHMARK_SYMBOL)),
                key="pipeline_screener_benchmark_symbol",
            )
        ).strip().upper()
    with screener_col2:
        screener_liquidity_threshold_usd = float(
            st.number_input(
                "Screener — liquidité mini (USD)",
                min_value=0.0,
                value=_session_state_float(
                    "pipeline_screener_liquidity_threshold_usd",
                    DEFAULT_SCREENER_LIQUIDITY_THRESHOLD_USD,
                ),
                step=1_000_000.0,
                format="%.2f",
                key="pipeline_screener_liquidity_threshold_usd",
            )
        )
        screener_min_relative_strength_index = float(
            st.number_input(
                "Screener — RS mini vs benchmark",
                min_value=0.01,
                value=_session_state_float(
                    "pipeline_screener_min_relative_strength_index",
                    DEFAULT_SCREENER_MIN_RELATIVE_STRENGTH_INDEX,
                ),
                step=1.0,
                format="%.2f",
                key="pipeline_screener_min_relative_strength_index",
            )
        )
        screener_enable_two_pass_loading = st.checkbox(
            "Screener — activer le chargement en 2 passes",
            value=_session_state_bool("pipeline_screener_enable_two_pass_loading", DEFAULT_SCREENER_ENABLE_TWO_PASS_LOADING),
            key="pipeline_screener_enable_two_pass_loading",
        )
    with screener_col3:
        screener_historical_range_lookback_days = int(
            st.number_input(
                "Screener — fenêtre range historique (jours)",
                min_value=2,
                value=_session_state_int(
                    "pipeline_screener_historical_range_lookback_days",
                    DEFAULT_SCREENER_HISTORICAL_RANGE_LOOKBACK_DAYS,
                ),
                step=21,
                key="pipeline_screener_historical_range_lookback_days",
            )
        )
        screener_min_historical_range_score = float(
            st.number_input(
                "Screener — score mini range historique",
                min_value=0.0,
                max_value=100.0,
                value=_session_state_float(
                    "pipeline_screener_min_historical_range_score",
                    DEFAULT_SCREENER_MIN_HISTORICAL_RANGE_SCORE,
                ),
                step=1.0,
                format="%.2f",
                key="pipeline_screener_min_historical_range_score",
            )
        )
        screener_first_pass_window_days = int(
            st.number_input(
                "Screener — fenêtre passe 1 (jours)",
                min_value=252,
                value=_session_state_int(
                    "pipeline_screener_first_pass_window_days",
                    DEFAULT_SCREENER_FIRST_PASS_WINDOW_DAYS,
                ),
                step=21,
                key="pipeline_screener_first_pass_window_days",
            )
        )
    return {
        "screener_chunk_size": screener_chunk_size,
        "screener_max_workers": screener_max_workers,
        "screener_benchmark_symbol": screener_benchmark_symbol,
        "screener_liquidity_threshold_usd": screener_liquidity_threshold_usd,
        "screener_min_relative_strength_index": screener_min_relative_strength_index,
        "screener_enable_two_pass_loading": screener_enable_two_pass_loading,
        "screener_historical_range_lookback_days": screener_historical_range_lookback_days,
        "screener_min_historical_range_score": screener_min_historical_range_score,
        "screener_first_pass_window_days": screener_first_pass_window_days,
    }


def _render_risk_block(selected_capital_preset: CapitalPreset | None) -> dict[str, Any]:
    """Sous-bloc « Paramètres Risk Management » de ``_build_launch_options``.

    Retourne les valeurs ``risk_*`` consommées par
    :class:`PipelineLaunchOptions` (sizing, conviction, contraintes
    portefeuille, Kelly avancé, shadow compare, log level).
    """
    st.markdown("#### Paramètres Risk Management (`python -m risk_management`)")
    st.caption(
        "Pilote le sizing et les contraintes du portefeuille cible. "
        "Défauts swing : 1 % risque/trade, 15 positions max, 8 % max/ligne, conviction = 40 % score + 60 % ML. "
        "Les garde-fous live P1 (drawdown breaker, vol targeting, gate ML) se règlent aussi ici."
    )
    if selected_capital_preset is not None:
        st.caption(f"Panier capital actif pour Risk / Execution / Selector : `{selected_capital_preset.label}`.")

    risk_col1, risk_col2, risk_col3, risk_col4 = st.columns(4)
    with risk_col1:
        risk_per_trade_pct = float(
            st.number_input(
                "Risk — risque par trade (fraction)",
                min_value=0.001,
                max_value=0.10,
                value=_session_state_float(
                    "pipeline_risk_per_trade_pct",
                    DEFAULT_RISK_PER_TRADE_PCT,
                ),
                step=0.001,
                format="%.4f",
                key="pipeline_risk_per_trade_pct",
                help="Ex. 0.01 = 1 % du capital risqué par trade (distance prix → stop).",
            )
        )
        risk_max_positions = int(
            st.number_input(
                "Risk — positions max",
                min_value=1,
                max_value=100,
                value=_session_state_int(
                    "pipeline_risk_max_positions",
                    DEFAULT_RISK_MAX_POSITIONS,
                ),
                step=1,
                key="pipeline_risk_max_positions",
            )
        )
    with risk_col2:
        risk_max_position_weight = float(
            st.number_input(
                "Risk — poids max par position",
                min_value=0.01,
                max_value=1.0,
                value=_session_state_float(
                    "pipeline_risk_max_position_weight",
                    DEFAULT_RISK_MAX_POSITION_WEIGHT,
                ),
                step=0.01,
                format="%.2f",
                key="pipeline_risk_max_position_weight",
            )
        )
        risk_max_sector_weight = float(
            st.number_input(
                "Risk — poids max par secteur",
                min_value=0.05,
                max_value=1.0,
                value=_session_state_float(
                    "pipeline_risk_max_sector_weight",
                    DEFAULT_RISK_MAX_SECTOR_WEIGHT,
                ),
                step=0.05,
                format="%.2f",
                key="pipeline_risk_max_sector_weight",
            )
        )
        risk_min_position_notional = float(
            st.number_input(
                "Risk — ticket minimum ($)",
                min_value=0.0,
                value=_session_state_float(
                    "pipeline_risk_min_position_notional",
                    DEFAULT_RISK_MIN_POSITION_NOTIONAL,
                ),
                step=10.0,
                format="%.2f",
                key="pipeline_risk_min_position_notional",
                help="Montant notionnel minimum par position. Pour un petit compte, réduis cette valeur pour éviter les rejets systématiques.",
            )
        )
    with risk_col3:
        risk_score_weight = float(
            st.number_input(
                "Risk — poids score (conviction)",
                min_value=0.0,
                max_value=1.0,
                value=_session_state_float(
                    "pipeline_risk_score_weight",
                    DEFAULT_RISK_SCORE_WEIGHT,
                ),
                step=0.05,
                format="%.2f",
                key="pipeline_risk_score_weight",
            )
        )
        risk_prediction_weight = float(
            st.number_input(
                "Risk — poids ML predict (conviction)",
                min_value=0.0,
                max_value=1.0,
                value=_session_state_float(
                    "pipeline_risk_prediction_weight",
                    DEFAULT_RISK_PREDICTION_WEIGHT,
                ),
                step=0.05,
                format="%.2f",
                key="pipeline_risk_prediction_weight",
            )
        )
    with risk_col4:
        risk_correlation_threshold = float(
            st.number_input(
                "Risk — corrélation max",
                min_value=0.0,
                max_value=1.0,
                value=_session_state_float(
                    "pipeline_risk_correlation_threshold",
                    DEFAULT_RISK_CORRELATION_THRESHOLD,
                ),
                step=0.05,
                format="%.2f",
                key="pipeline_risk_correlation_threshold",
            )
        )
        risk_correlation_lookback_days = int(
            st.number_input(
                "Risk — lookback corrélation (jours)",
                min_value=10,
                max_value=252,
                value=_session_state_int(
                    "pipeline_risk_correlation_lookback_days",
                    DEFAULT_RISK_CORRELATION_LOOKBACK_DAYS,
                ),
                step=10,
                key="pipeline_risk_correlation_lookback_days",
            )
        )

    with st.expander("Risk — Kelly sizing & options avancées", expanded=False):
        risk_adv_col1, risk_adv_col2, risk_adv_col3 = st.columns(3)
        with risk_adv_col1:
            risk_enable_kelly = st.checkbox(
                "Activer Kelly sizing",
                value=_session_state_bool("pipeline_risk_enable_kelly", DEFAULT_RISK_ENABLE_KELLY),
                key="pipeline_risk_enable_kelly",
            )
            risk_dry_run = st.checkbox(
                "Dry run (n'écrit pas en DB)",
                value=_session_state_bool("pipeline_risk_dry_run", False),
                key="pipeline_risk_dry_run",
            )
        with risk_adv_col2:
            risk_payoff_ratio = float(
                st.number_input(
                    "Risk — payoff ratio assumé",
                    min_value=0.5,
                    value=_session_state_float(
                        "pipeline_risk_payoff_ratio",
                        DEFAULT_RISK_PAYOFF_RATIO,
                    ),
                    step=0.1,
                    format="%.2f",
                    key="pipeline_risk_payoff_ratio",
                )
            )
            risk_kelly_fraction_multiplier = float(
                st.number_input(
                    "Risk — multiplicateur Kelly fraction",
                    min_value=0.05,
                    max_value=1.0,
                    value=_session_state_float(
                        "pipeline_risk_kelly_fraction_multiplier",
                        DEFAULT_RISK_KELLY_FRACTION_MULTIPLIER,
                    ),
                    step=0.05,
                    format="%.2f",
                    key="pipeline_risk_kelly_fraction_multiplier",
                )
            )
        with risk_adv_col3:
            risk_correlation_min_overlap = int(
                st.number_input(
                    "Risk — min overlap corrélation",
                    min_value=10,
                    max_value=200,
                    value=_session_state_int(
                        "pipeline_risk_correlation_min_overlap",
                        DEFAULT_RISK_CORRELATION_MIN_OVERLAP,
                    ),
                    step=5,
                    key="pipeline_risk_correlation_min_overlap",
                )
            )
            risk_log_level = cast(
                str,
                st.selectbox(
                    "Risk — niveau de log",
                    options=["DEBUG", "INFO", "WARNING", "ERROR"],
                    index=["DEBUG", "INFO", "WARNING", "ERROR"].index(
                        cast(str, st.session_state.get("pipeline_risk_log_level", DEFAULT_RISK_LOG_LEVEL)).upper()
                        if str(st.session_state.get("pipeline_risk_log_level", DEFAULT_RISK_LOG_LEVEL)).upper() in {"DEBUG", "INFO", "WARNING", "ERROR"}
                        else DEFAULT_RISK_LOG_LEVEL
                    ),
                    key="pipeline_risk_log_level",
                ),
            )
            risk_enable_shadow_compare = st.checkbox(
                "Activer shadow compare",
                value=_session_state_bool("pipeline_risk_enable_shadow_compare", False),
                key="pipeline_risk_enable_shadow_compare",
                help="Compare le portefeuille courant avec le dernier run risk du même trade_date, ou avec un run explicite ci-dessous.",
            )
            risk_shadow_compare_run_id = cast(
                str,
                st.text_input(
                    "Risk — run_id shadow compare (optionnel)",
                    value=str(st.session_state.get("pipeline_risk_shadow_compare_run_id", "") or ""),
                    key="pipeline_risk_shadow_compare_run_id",
                    help="Laisser vide pour comparer avec le dernier run risk persisté du même jour/compte.",
                ),
            ).strip() or None

        st.markdown("##### Garde-fous live P1")
        st.caption(
            "Ces réglages se modifient directement depuis la page Pipeline > Paramètres Risk Management > "
            "Kelly sizing & options avancées. Un preset capital peut les préremplir automatiquement."
        )
        guard_col1, guard_col2, guard_col3 = st.columns(3)
        with guard_col1:
            risk_max_portfolio_drawdown_pct = float(
                st.number_input(
                    "Risk — DD max portefeuille",
                    min_value=0.01,
                    max_value=0.50,
                    value=_session_state_float(
                        "pipeline_risk_max_portfolio_drawdown_pct",
                        DEFAULT_RISK_MAX_PORTFOLIO_DRAWDOWN_PCT,
                    ),
                    step=0.01,
                    format="%.2f",
                    key="pipeline_risk_max_portfolio_drawdown_pct",
                    help="Seuil live du circuit breaker portefeuille. Ex. 0.12 = blocage des nouvelles cibles dès 12 % de drawdown.",
                )
            )
            risk_max_daily_loss_pct = float(
                st.number_input(
                    "Risk — perte journalière max",
                    min_value=0.005,
                    max_value=0.20,
                    value=_session_state_float(
                        "pipeline_risk_max_daily_loss_pct",
                        DEFAULT_RISK_MAX_DAILY_LOSS_PCT,
                    ),
                    step=0.005,
                    format="%.3f",
                    key="pipeline_risk_max_daily_loss_pct",
                    help="Complément intraday du circuit breaker live. Ex. 0.025 = arrêt au-delà de 2.5 % de perte journalière.",
                )
            )
        with guard_col2:
            risk_target_annual_vol = float(
                st.number_input(
                    "Risk — target annual vol (0 = off)",
                    min_value=0.0,
                    max_value=1.0,
                    value=_session_state_float(
                        "pipeline_risk_target_annual_vol",
                        DEFAULT_RISK_TARGET_ANNUAL_VOL,
                    ),
                    step=0.01,
                    format="%.2f",
                    key="pipeline_risk_target_annual_vol",
                    help="Vol targeting live via proxy SPY. 0 désactive la réduction automatique d'exposition.",
                )
            )
            risk_vol_target_lookback_days = int(
                st.number_input(
                    "Risk — lookback vol target (jours)",
                    min_value=20,
                    max_value=252,
                    value=_session_state_int(
                        "pipeline_risk_vol_target_lookback_days",
                        DEFAULT_RISK_VOL_TARGET_LOOKBACK_DAYS,
                    ),
                    step=5,
                    key="pipeline_risk_vol_target_lookback_days",
                    help="Fenêtre de vol réalisée utilisée par le vol targeting live.",
                )
            )
        with guard_col3:
            risk_min_ml_coverage_ratio = float(
                st.number_input(
                    "Risk — min ML coverage ratio (0 = off)",
                    min_value=0.0,
                    max_value=1.0,
                    value=_session_state_float(
                        "pipeline_risk_min_ml_coverage_ratio",
                        DEFAULT_RISK_MIN_ML_COVERAGE_RATIO,
                    ),
                    step=0.05,
                    format="%.2f",
                    key="pipeline_risk_min_ml_coverage_ratio",
                    help="Gate dur live : si la couverture ML du jour est sous ce seuil, l'étape risk échoue avant publication des cibles.",
                )
            )

    conviction_total = round(risk_score_weight + risk_prediction_weight, 4)
    if abs(conviction_total - 1.0) > 0.001:
        st.warning(f"⚠️ Risk : poids score + poids ML = {conviction_total} (≠ 1.0). Le backend pourrait normaliser.")

    return {
        "risk_per_trade_pct": risk_per_trade_pct,
        "risk_max_positions": risk_max_positions,
        "risk_max_position_weight": risk_max_position_weight,
        "risk_max_sector_weight": risk_max_sector_weight,
        "risk_min_position_notional": risk_min_position_notional,
        "risk_score_weight": risk_score_weight,
        "risk_prediction_weight": risk_prediction_weight,
        "risk_correlation_threshold": risk_correlation_threshold,
        "risk_correlation_lookback_days": risk_correlation_lookback_days,
        "risk_enable_kelly": risk_enable_kelly,
        "risk_enable_shadow_compare": risk_enable_shadow_compare,
        "risk_shadow_compare_run_id": risk_shadow_compare_run_id,
        "risk_max_portfolio_drawdown_pct": risk_max_portfolio_drawdown_pct,
        "risk_max_daily_loss_pct": risk_max_daily_loss_pct,
        "risk_target_annual_vol": risk_target_annual_vol,
        "risk_vol_target_lookback_days": risk_vol_target_lookback_days,
        "risk_min_ml_coverage_ratio": risk_min_ml_coverage_ratio,
        "risk_dry_run": risk_dry_run,
        "risk_payoff_ratio": risk_payoff_ratio,
        "risk_kelly_fraction_multiplier": risk_kelly_fraction_multiplier,
        "risk_correlation_min_overlap": risk_correlation_min_overlap,
        "risk_log_level": risk_log_level,
    }


def _render_selector_block() -> dict[str, Any]:
    """Sous-bloc « Paramètres Alpha Scanner » de ``_build_launch_options``.

    Inclut le rappel de profil partagé strict, l'éditeur de seuils de
    dépendance (:func:`_render_alpha_scanner_dependency_threshold_editor`),
    puis l'ensemble des paramètres opérationnels exposés par
    ``selector.alpha_scanner``.

    Retourne un ``dict`` contenant les 19 valeurs ``selector_*``
    consommées par :class:`PipelineLaunchOptions`.
    """
    st.caption(
        "Alpha Scanner part du profil partagé strict (`STRICT_SWING_CASH_FILTERS`) depuis l'IHM. "
        "Les paramètres ci-dessous permettent de reproduire explicitement — et si besoin de surcharger — les seuils backend réellement supportés par `selector.alpha_scanner`."
    )
    _render_alpha_scanner_dependency_threshold_editor()

    st.markdown(ALPHA_SCANNER_PARAMS_TITLE)
    st.caption(ALPHA_SCANNER_PARAMS_CAPTION)
    st.caption(
        "Ces réglages reflètent les options opérationnelles réellement disponibles côté `selector.alpha_scanner`. "
        "`0` sur `max workers` signifie : auto. Le preset strict reste la base implicite côté backend."
    )

    selector_col1, selector_col2, selector_col3, selector_col4 = st.columns(4)
    with selector_col1:
        selector_chunk_size = int(
            st.number_input(
                "Alpha Scanner — taille de chunk",
                min_value=1,
                value=_session_state_int(
                    "pipeline_selector_chunk_size",
                    DEFAULT_SELECTOR_CHUNK_SIZE,
                ),
                step=50,
                key="pipeline_selector_chunk_size",
            )
        )
        selector_selection_size = int(
            st.number_input(
                "Alpha Scanner — taille de sélection finale",
                min_value=1,
                value=_session_state_int(
                    "pipeline_selector_selection_size",
                    DEFAULT_SELECTOR_SELECTION_SIZE,
                ),
                step=5,
                key="pipeline_selector_selection_size",
            )
        )
        selector_short_selection_size = int(
            st.number_input(
                "Alpha Scanner — candidats short",
                min_value=0,
                value=_session_state_int(
                    "pipeline_selector_short_selection_size",
                    DEFAULT_SELECTOR_SHORT_SELECTION_SIZE,
                ),
                step=5,
                key="pipeline_selector_short_selection_size",
                help="Nombre de candidats short selectionnes par short_score. 0 = desactive.",
            )
        )
        selector_max_workers = int(
            st.number_input(
                "Alpha Scanner — max workers (0 = auto)",
                min_value=0,
                value=_session_state_int("pipeline_selector_max_workers", 0),
                step=1,
                key="pipeline_selector_max_workers",
            )
        )
        selector_log_level = cast(
            str,
            st.selectbox(
                "Alpha Scanner — niveau de log",
                options=["DEBUG", "INFO", "WARNING", "ERROR"],
                index=["DEBUG", "INFO", "WARNING", "ERROR"].index(
                    cast(str, st.session_state.get("pipeline_selector_log_level", DEFAULT_SELECTOR_LOG_LEVEL)).upper()
                    if str(st.session_state.get("pipeline_selector_log_level", DEFAULT_SELECTOR_LOG_LEVEL)).upper() in {"DEBUG", "INFO", "WARNING", "ERROR"}
                    else DEFAULT_SELECTOR_LOG_LEVEL
                ),
                key="pipeline_selector_log_level",
            ),
        )
    with selector_col2:
        selector_liquidity_threshold = float(
            st.number_input(
                "Alpha Scanner — liquidité mini",
                min_value=0.0,
                value=_session_state_float(
                    "pipeline_selector_liquidity_threshold",
                    DEFAULT_SELECTOR_LIQUIDITY_THRESHOLD,
                ),
                step=1_000_000.0,
                format="%.2f",
                key="pipeline_selector_liquidity_threshold",
            )
        )
        selector_min_close = float(
            st.number_input(
                "Alpha Scanner — prix mini",
                min_value=0.01,
                value=_session_state_float(
                    "pipeline_selector_min_close",
                    DEFAULT_SELECTOR_MIN_CLOSE,
                ),
                step=1.0,
                format="%.2f",
                key="pipeline_selector_min_close",
            )
        )
        selector_max_volatility_ratio = float(
            st.number_input(
                "Alpha Scanner — volatilité relative max",
                min_value=0.01,
                value=_session_state_float(
                    "pipeline_selector_max_volatility_ratio",
                    DEFAULT_SELECTOR_MAX_VOLATILITY_RATIO,
                ),
                step=0.05,
                format="%.2f",
                key="pipeline_selector_max_volatility_ratio",
            )
        )
        selector_min_relative_strength_index = float(
            st.number_input(
                "Alpha Scanner — RS mini",
                min_value=0.01,
                value=_session_state_float(
                    "pipeline_selector_min_relative_strength_index",
                    DEFAULT_SELECTOR_MIN_RELATIVE_STRENGTH_INDEX,
                ),
                step=1.0,
                format="%.2f",
                key="pipeline_selector_min_relative_strength_index",
            )
        )
    with selector_col3:
        selector_min_high_52w_proximity = float(
            st.number_input(
                "Alpha Scanner — proximité min du high 52w",
                min_value=0.01,
                max_value=1.0,
                value=_session_state_float(
                    "pipeline_selector_min_high_52w_proximity",
                    DEFAULT_SELECTOR_MIN_HIGH_52W_PROXIMITY,
                ),
                step=0.01,
                format="%.2f",
                key="pipeline_selector_min_high_52w_proximity",
            )
        )
        selector_min_weekly_trend_score = float(
            st.number_input(
                "Alpha Scanner — weekly trend mini",
                min_value=0.0,
                max_value=1.0,
                value=_session_state_float(
                    "pipeline_selector_min_weekly_trend_score",
                    DEFAULT_SELECTOR_MIN_WEEKLY_TREND_SCORE,
                ),
                step=0.05,
                format="%.2f",
                key="pipeline_selector_min_weekly_trend_score",
            )
        )
        selector_min_atr_pct_20 = float(
            st.number_input(
                "Alpha Scanner — ATR%20 min",
                min_value=0.0,
                value=_session_state_float(
                    "pipeline_selector_min_atr_pct_20",
                    DEFAULT_SELECTOR_MIN_ATR_PCT_20,
                ),
                step=0.005,
                format="%.4f",
                key="pipeline_selector_min_atr_pct_20",
            )
        )
        selector_max_atr_pct_20 = float(
            st.number_input(
                "Alpha Scanner — ATR%20 max",
                min_value=0.0,
                value=_session_state_float(
                    "pipeline_selector_max_atr_pct_20",
                    DEFAULT_SELECTOR_MAX_ATR_PCT_20,
                ),
                step=0.005,
                format="%.4f",
                key="pipeline_selector_max_atr_pct_20",
            )
        )
    with selector_col4:
        selector_min_market_cap = float(
            st.number_input(
                "Alpha Scanner — market cap mini",
                min_value=0.0,
                value=_session_state_float(
                    "pipeline_selector_min_market_cap",
                    DEFAULT_SELECTOR_MIN_MARKET_CAP,
                ),
                step=100_000_000.0,
                format="%.2f",
                key="pipeline_selector_min_market_cap",
            )
        )
        selector_min_beta_126 = float(
            st.number_input(
                "Alpha Scanner — beta 126 mini",
                min_value=0.0,
                value=_session_state_float(
                    "pipeline_selector_min_beta_126",
                    DEFAULT_SELECTOR_MIN_BETA_126,
                ),
                step=0.1,
                format="%.2f",
                key="pipeline_selector_min_beta_126",
            )
        )
        selector_max_spread_bps = float(
            st.number_input(
                "Alpha Scanner — spread max (bps)",
                min_value=0.0,
                value=_session_state_float(
                    "pipeline_selector_max_spread_bps",
                    DEFAULT_SELECTOR_MAX_SPREAD_BPS,
                ),
                step=1.0,
                format="%.2f",
                key="pipeline_selector_max_spread_bps",
            )
        )
        selector_earnings_blackout_days = int(
            st.number_input(
                "Alpha Scanner — earnings blackout (jours)",
                min_value=0,
                value=_session_state_int(
                    "pipeline_selector_earnings_blackout_days",
                    DEFAULT_SELECTOR_EARNINGS_BLACKOUT_DAYS,
                ),
                step=1,
                key="pipeline_selector_earnings_blackout_days",
            )
        )

    selector_adv_col1, selector_adv_col2 = st.columns(2)
    with selector_adv_col1:
        selector_max_anomaly_count = int(
            st.number_input(
                "Alpha Scanner — anomalies max",
                min_value=0,
                value=_session_state_int(
                    "pipeline_selector_max_anomaly_count",
                    DEFAULT_SELECTOR_MAX_ANOMALY_COUNT,
                ),
                step=1,
                key="pipeline_selector_max_anomaly_count",
            )
        )
        selector_require_above_ma200 = st.checkbox(
            "Alpha Scanner — exiger close > MA200 (Minervini stage 2)",
            value=_session_state_bool("pipeline_selector_require_above_ma200", DEFAULT_SELECTOR_REQUIRE_ABOVE_MA200),
            key="pipeline_selector_require_above_ma200",
            help="Défaut swing : True. Filtre anti-baissière standard trend-following.",
        )
    with selector_adv_col2:
        selector_sector_cap_ratio = float(
            st.number_input(
                "Alpha Scanner — cap sectoriel",
                min_value=0.01,
                max_value=1.0,
                value=_session_state_float(
                    "pipeline_selector_sector_cap_ratio",
                    DEFAULT_SELECTOR_SECTOR_CAP_RATIO,
                ),
                step=0.01,
                format="%.2f",
                key="pipeline_selector_sector_cap_ratio",
            )
        )

    return {
        "selector_chunk_size": selector_chunk_size,
        "selector_selection_size": selector_selection_size,
        "selector_short_selection_size": selector_short_selection_size,
        "selector_max_workers": selector_max_workers,
        "selector_log_level": selector_log_level,
        "selector_liquidity_threshold": selector_liquidity_threshold,
        "selector_min_close": selector_min_close,
        "selector_max_volatility_ratio": selector_max_volatility_ratio,
        "selector_min_relative_strength_index": selector_min_relative_strength_index,
        "selector_min_high_52w_proximity": selector_min_high_52w_proximity,
        "selector_min_weekly_trend_score": selector_min_weekly_trend_score,
        "selector_min_atr_pct_20": selector_min_atr_pct_20,
        "selector_max_atr_pct_20": selector_max_atr_pct_20,
        "selector_min_market_cap": selector_min_market_cap,
        "selector_min_beta_126": selector_min_beta_126,
        "selector_max_spread_bps": selector_max_spread_bps,
        "selector_earnings_blackout_days": selector_earnings_blackout_days,
        "selector_max_anomaly_count": selector_max_anomaly_count,
        "selector_require_above_ma200": selector_require_above_ma200,
        "selector_sector_cap_ratio": selector_sector_cap_ratio,
    }


def _render_data_integrity_block() -> dict[str, Any]:
    """Sous-bloc « Paramètres Data Integrity » de ``_build_launch_options``.

    Couvre les options ``dataIntegrityEngine`` quotes / earnings /
    fondamentaux / EODHD write + la fenêtre custom earnings optionnelle.
    Retourne les valeurs ``data_integrity_*``, ``eodhd_*`` et
    ``effective_earnings_from_date`` / ``effective_earnings_to_date``.
    """
    st.markdown("#### Paramètres Data Integrity")
    st.caption(
        "Ces réglages reflètent les options réellement disponibles côté `dataIntegrityEngine` pour les étapes quotes, earnings et fondamentaux. "
        "`0` sur un champ `limit` signifie : univers complet éligible."
    )

    di_col1, di_col2, di_col3 = st.columns(3)
    with di_col1:
        data_integrity_quotes_limit = int(
            st.number_input(
                "Latest Quotes — limite optionnelle",
                min_value=0,
                value=_session_state_int("pipeline_data_integrity_quotes_limit", 0),
                step=50,
                key="pipeline_data_integrity_quotes_limit",
            )
        )
        data_integrity_quotes_batch_size = int(
            st.number_input(
                "Latest Quotes — taille de batch",
                min_value=1,
                value=_session_state_int(
                    "pipeline_data_integrity_quotes_batch_size",
                    DEFAULT_DATA_INTEGRITY_QUOTES_BATCH_SIZE,
                ),
                step=25,
                key="pipeline_data_integrity_quotes_batch_size",
            )
        )
        data_integrity_earnings_limit = int(
            st.number_input(
                "Earnings — limite optionnelle",
                min_value=0,
                value=_session_state_int("pipeline_data_integrity_earnings_limit", 0),
                step=25,
                key="pipeline_data_integrity_earnings_limit",
            )
        )
        data_integrity_earnings_batch_size = int(
            st.number_input(
                "Earnings — taille de batch (symboles)",
                min_value=25,
                max_value=100,
                value=_session_state_int(
                    "pipeline_data_integrity_earnings_batch_size",
                    DEFAULT_DATA_INTEGRITY_EARNINGS_BATCH_SIZE,
                ),
                step=25,
                key="pipeline_data_integrity_earnings_batch_size",
                help="Chaque batch est fetch + upsert + commit avant de passer au suivant. Intervalle supporté : 25 à 100 symboles.",
            )
        )
    with di_col2:
        data_integrity_earnings_sleep_seconds = float(
            st.number_input(
                "Earnings — pause Finnhub (s)",
                min_value=0.0,
                value=_session_state_float(
                    "pipeline_data_integrity_earnings_sleep_seconds",
                    DEFAULT_DATA_INTEGRITY_PROVIDER_SLEEP_SECONDS,
                ),
                step=0.1,
                format="%.2f",
                key="pipeline_data_integrity_earnings_sleep_seconds",
            )
        )
        data_integrity_earnings_log_every = int(
            st.number_input(
                "Earnings — journaliser tous les N symboles",
                min_value=0,
                value=_session_state_int(
                    "pipeline_data_integrity_earnings_log_every",
                    DEFAULT_DATA_INTEGRITY_EARNINGS_LOG_EVERY,
                ),
                step=5,
                key="pipeline_data_integrity_earnings_log_every",
                help="0 désactive les logs de progression Finnhub. Défaut : 25, soit environ un log toutes les ~30s avec la pause par défaut.",
            )
        )
        data_integrity_fundamentals_limit = int(
            st.number_input(
                "Fondamentaux — limite optionnelle",
                min_value=0,
                value=_session_state_int("pipeline_data_integrity_fundamentals_limit", 0),
                step=25,
                key="pipeline_data_integrity_fundamentals_limit",
            )
        )
        fundamentals_provider_options = ("yahoo_finance", "eodhd", "finnhub")
        current_fundamentals_provider = str(
            st.session_state.get("pipeline_data_integrity_fundamentals_provider", "yahoo_finance")
        ).strip().lower()
        if current_fundamentals_provider not in fundamentals_provider_options:
            current_fundamentals_provider = "yahoo_finance"
        data_integrity_fundamentals_provider = cast(
            str,
            st.selectbox(
                "Fondamentaux — source provider",
                options=list(fundamentals_provider_options),
                index=fundamentals_provider_options.index(current_fundamentals_provider),
                key="pipeline_data_integrity_fundamentals_provider",
                help=(
                    "Provider utilisé par l'étape B2 pour récupérer `sector` et `market_cap`. "
                    "Défaut recommandé : Yahoo Finance via `yfinance`. Si l'endpoint `fundamentals` EODHD est refusé par le compte courant (401/403), "
                    "le backend bascule automatiquement vers Finnhub pour éviter un run B2 en erreur sur tout l'univers."
                ),
            ),
        )
        data_integrity_fundamentals_sleep_seconds = float(
            st.number_input(
	            "Fondamentaux — pause provider (s)",
                min_value=0.0,
                value=_session_state_float(
                    "pipeline_data_integrity_fundamentals_sleep_seconds",
                    DEFAULT_DATA_INTEGRITY_PROVIDER_SLEEP_SECONDS,
                ),
                step=0.1,
                format="%.2f",
                key="pipeline_data_integrity_fundamentals_sleep_seconds",
            )
        )
    with di_col3:
        eodhd_write_commit_every_symbols = int(
            st.number_input(
                "Import Bars EODHD — commit intermédiaire tous les N symboles",
                min_value=0,
                value=_session_state_int(
                    "pipeline_eodhd_write_commit_every_symbols",
                    DEFAULT_EODHD_WRITE_COMMIT_EVERY_SYMBOLS,
                ),
                step=25,
                key="pipeline_eodhd_write_commit_every_symbols",
                help="0 = commit final unique en fin de run. Toute valeur > 0 active des sauvegardes intermédiaires par batch de symboles quand `bars_provider=eodhd`.",
            )
        )
        eodhd_enable_stooq_cross_check = st.checkbox(
            "Import Bars EODHD — activer le cross-check Stooq après import",
            value=_session_state_bool("pipeline_eodhd_enable_stooq_cross_check", DEFAULT_EODHD_ENABLE_STOOQ_CROSS_CHECK),
            key="pipeline_eodhd_enable_stooq_cross_check",
            help=(
                "Décoché par défaut pour éviter qu'un workflow quotidien reste bloqué longtemps après le `final_flush`. "
                "Si coché, l'étape 1 lance aussi l'audit best-effort Stooq pour comparer EODHD à une source indépendante."
            ),
        )
        data_integrity_fundamentals_log_every = int(
            st.number_input(
                "Fondamentaux — journaliser tous les N symboles",
                min_value=1,
                value=_session_state_int(
                    "pipeline_data_integrity_fundamentals_log_every",
                    DEFAULT_DATA_INTEGRITY_FUNDAMENTALS_LOG_EVERY,
                ),
                step=5,
                key="pipeline_data_integrity_fundamentals_log_every",
            )
        )
        data_integrity_fundamentals_overwrite_existing = st.checkbox(
            "Fondamentaux — écraser les valeurs existantes sector / market cap",
            value=_session_state_bool("pipeline_data_integrity_fundamentals_overwrite_existing", False),
            key="pipeline_data_integrity_fundamentals_overwrite_existing",
            help=(
                "Décoché par défaut : B2 complète seulement les champs manquants (et rafraîchit les market caps périmées côté backend). "
                "Coché : B2 peut aussi remplacer les valeurs déjà présentes sur les symboles ciblés."
            ),
        )
        data_integrity_earnings_resume = st.checkbox(
            "Earnings — reprendre depuis le bookmark local",
            value=_session_state_bool("pipeline_data_integrity_earnings_resume", DEFAULT_DATA_INTEGRITY_EARNINGS_RESUME),
            key="pipeline_data_integrity_earnings_resume",
            help="Si activé, les symboles déjà commités sont sautés au redémarrage ; sinon le run repart du début et ignore le bookmark existant.",
        )
        data_integrity_earnings_custom_window = st.checkbox(
            "Earnings — utiliser une fenêtre de dates personnalisée",
            value=_session_state_bool(EARNINGS_CUSTOM_WINDOW_KEY, False),
            key=EARNINGS_CUSTOM_WINDOW_KEY,
        )

    effective_earnings_from_date: str | None = None
    effective_earnings_to_date: str | None = None
    if data_integrity_earnings_custom_window:
        earnings_date_col1, earnings_date_col2 = st.columns(2)
        with earnings_date_col1:
            earnings_from_date_value = cast(
                date,
                st.date_input(
                    "Earnings — date de début",
                    value=cast(date, st.session_state.get("pipeline_data_integrity_earnings_from_date", date.today() - timedelta(days=7))),
                    key="pipeline_data_integrity_earnings_from_date",
                    format="YYYY-MM-DD",
                ),
            )
        with earnings_date_col2:
            earnings_to_date_value = cast(
                date,
                st.date_input(
                    "Earnings — date de fin",
                    value=cast(date, st.session_state.get("pipeline_data_integrity_earnings_to_date", date.today() + timedelta(days=30))),
                    key="pipeline_data_integrity_earnings_to_date",
                    format="YYYY-MM-DD",
                ),
            )
        if earnings_from_date_value <= earnings_to_date_value:
            effective_earnings_from_date = earnings_from_date_value.isoformat()
            effective_earnings_to_date = earnings_to_date_value.isoformat()
        else:
            st.error("Fenêtre earnings invalide : la date de début doit être antérieure ou égale à la date de fin. La fenêtre custom sera ignorée.")
    else:
        st.caption("Sans fenêtre personnalisée, `sync_earnings_calendar` conserve sa plage backend par défaut : J-7 → J+30.")

    return {
        "data_integrity_quotes_limit": data_integrity_quotes_limit,
        "data_integrity_quotes_batch_size": data_integrity_quotes_batch_size,
        "data_integrity_earnings_limit": data_integrity_earnings_limit,
        "data_integrity_earnings_batch_size": data_integrity_earnings_batch_size,
        "data_integrity_earnings_sleep_seconds": data_integrity_earnings_sleep_seconds,
        "data_integrity_earnings_log_every": data_integrity_earnings_log_every,
        "data_integrity_fundamentals_limit": data_integrity_fundamentals_limit,
        "data_integrity_fundamentals_provider": data_integrity_fundamentals_provider,
        "data_integrity_fundamentals_overwrite_existing": data_integrity_fundamentals_overwrite_existing,
        "data_integrity_fundamentals_sleep_seconds": data_integrity_fundamentals_sleep_seconds,
        "eodhd_write_commit_every_symbols": eodhd_write_commit_every_symbols,
        "eodhd_enable_stooq_cross_check": eodhd_enable_stooq_cross_check,
        "data_integrity_fundamentals_log_every": data_integrity_fundamentals_log_every,
        "data_integrity_earnings_resume": data_integrity_earnings_resume,
        "effective_earnings_from_date": effective_earnings_from_date,
        "effective_earnings_to_date": effective_earnings_to_date,
    }


def _render_corporate_actions_block(trade_date: str) -> dict[str, Any]:
    """Sous-bloc « Paramètres Corporate Actions + Backfill EODHD » de
    ``_build_launch_options``.

    Le paramètre ``trade_date`` (string ISO) sert à pré-calculer la
    fenêtre custom CA (`J-N → trade_date`). Retourne les valeurs
    ``corporate_actions_*`` + ``eodhd_backfill_*``.
    """
    st.markdown("#### Paramètres Corporate Actions")
    ca_col1, ca_col2, ca_col3 = st.columns([1, 1, 3])
    with ca_col1:
        corporate_actions_skip_existing = st.checkbox(
            "CA Sync — skip existing",
            value=_session_state_bool("pipeline_corporate_actions_skip_existing", DEFAULT_CA_SKIP_EXISTING),
            key="pipeline_corporate_actions_skip_existing",
            help="Si coché, ignore les symboles déjà présents dans corporate_actions_events (perf, mais peut rater de nouveaux events).",
        )
    with ca_col2:
        corporate_actions_batch_size = int(
            st.number_input(
                "CA Sync — batch size",
                min_value=1,
                max_value=200,
                value=_session_state_int(
                    "pipeline_corporate_actions_batch_size",
                    DEFAULT_CA_BATCH_SIZE,
                ),
                step=5,
                key="pipeline_corporate_actions_batch_size",
                help="Taille des lots de symboles par appel provider (`--batch-size`). Défaut 25.",
            )
        )
    with ca_col3:
        st.caption(
            "`apply` utilise `as-of = trade_date` global. Sans `skip-existing` (défaut), tous les symboles du portefeuille sont re-interrogés "
            "à chaque sync — recommandé en quotidien pour ne rien manquer."
        )

    # Fenêtre custom CA — défaut : J-7 → trade_date (vs défaut backend −10 ans)
    ca_use_custom_window = st.checkbox(
        "CA Sync — restreindre la fenêtre temporelle",
        value=_session_state_bool("pipeline_corporate_actions_use_custom_window", DEFAULT_CA_USE_CUSTOM_WINDOW),
        key="pipeline_corporate_actions_use_custom_window",
        help="Si coché, envoie `--start` / `--end` au lieu du défaut backend (−10 ans). Recommandé en swing quotidien : J-7 → J.",
    )
    ca_start_date_value: str | None = None
    ca_end_date_value: str | None = None
    if ca_use_custom_window:
        try:
            effective_trade_date_obj = date.fromisoformat(trade_date) if trade_date else date.today()
        except ValueError:
            effective_trade_date_obj = date.today()
        ca_default_start = effective_trade_date_obj - timedelta(days=DEFAULT_CA_WINDOW_LOOKBACK_DAYS)
        ca_default_end = effective_trade_date_obj
        ca_win_col1, ca_win_col2 = st.columns(2)
        with ca_win_col1:
            ca_start_picker = cast(
                date,
                st.date_input(
                    "CA Sync — date début",
                    value=cast(date, st.session_state.get("pipeline_corporate_actions_start_date", ca_default_start)),
                    key="pipeline_corporate_actions_start_date",
                    format="YYYY-MM-DD",
                ),
            )
        with ca_win_col2:
            ca_end_picker = cast(
                date,
                st.date_input(
                    "CA Sync — date fin",
                    value=cast(date, st.session_state.get("pipeline_corporate_actions_end_date", ca_default_end)),
                    key="pipeline_corporate_actions_end_date",
                    format="YYYY-MM-DD",
                ),
            )
        if ca_start_picker <= ca_end_picker:
            ca_start_date_value = ca_start_picker.isoformat()
            ca_end_date_value = ca_end_picker.isoformat()
        else:
            st.error("Fenêtre CA invalide : la date de début doit être antérieure ou égale à la date de fin. La fenêtre custom sera ignorée.")
    else:
        st.caption(
            "Sans fenêtre custom, `corporate_actions sync` conserve le défaut backend `−10 ans → aujourd'hui`. "
            "À activer après le 1er sync pour éviter de re-balayer un long historique chaque jour."
        )

    st.markdown("#### Paramètres Backfill historique EODHD (B3)")
    st.caption(
        "Ces réglages pilotent `python -m dataIntegrityEngine.backfill_eodhd_history`. "
        "Par défaut, l'IHM lance B3 en `write` pour persister dans `stock_bars` / `stock_bars_daily`. "
        "Si tu décoches le mode écriture, le script reste en `dry-run` : il interroge EODHD pour estimer le volume attendu, "
        "mais n'insère aucune ligne en base."
    )
    st.caption(
        "Mode write : la DB prime sur le bookmark ; symboles déjà frais (J-7) sautés automatiquement."
    )
    bf_col1, bf_col2, bf_col3 = st.columns([1, 2, 2])
    with bf_col1:
        eodhd_backfill_years = int(
            st.number_input(
                "B3 — profondeur historique (années)",
                min_value=1,
                max_value=30,
                value=_session_state_int("pipeline_eodhd_backfill_years", 30),
                step=1,
                key="pipeline_eodhd_backfill_years",
                help="30 ans par défaut (profondeur historique maximale EODHD pour robustesse ML/backtest). Coût quota EODHD identique quelle que soit la profondeur (1 appel par symbole).",
            )
        )
        eodhd_backfill_resume = st.checkbox(
            "B3 — reprendre via bookmark",
            value=_session_state_bool("pipeline_eodhd_backfill_resume", True),
            key="pipeline_eodhd_backfill_resume",
            help="Si coché, relit `artifacts/eodhd_cache/backfill_state.json` et saute les symboles déjà terminés.",
        )
    with bf_col2:
        eodhd_backfill_symbols = str(
            st.text_input(
                "B3 — symboles (CSV, optionnel)",
                value=str(st.session_state.get("pipeline_eodhd_backfill_symbols", "")),
                key="pipeline_eodhd_backfill_symbols",
                help="Laisser vide = univers complet éligible depuis `stock_metadata`. Exemple : AAPL,MSFT,NVDA",
            )
        ).strip().upper()
    with bf_col3:
        eodhd_backfill_write = st.checkbox(
            "B3 — mode écriture (insère en base)",
            value=_session_state_bool("pipeline_eodhd_backfill_write", True),
            key="pipeline_eodhd_backfill_write",
            help="Coché par défaut = ajoute `--write` et persiste dans `stock_bars` / `stock_bars_daily`. Décoché = dry-run sans insert DB.",
        )
        if eodhd_backfill_write:
            st.success("B3 sera lancé en mode `write` et insérera dans les tables.")
        else:
            st.warning("B3 sera lancé en mode `dry-run` : appels API réels, mais 0 insert DB.")

    return {
        "corporate_actions_skip_existing": corporate_actions_skip_existing,
        "corporate_actions_batch_size": corporate_actions_batch_size,
        "ca_use_custom_window": ca_use_custom_window,
        "ca_start_date_value": ca_start_date_value,
        "ca_end_date_value": ca_end_date_value,
        "eodhd_backfill_years": eodhd_backfill_years,
        "eodhd_backfill_resume": eodhd_backfill_resume,
        "eodhd_backfill_symbols": eodhd_backfill_symbols,
        "eodhd_backfill_write": eodhd_backfill_write,
    }


def _build_launch_options() -> tuple[PipelineLaunchOptions, bool]:
    selected_account_id = cast(str | None, st.session_state.get("selected_account_id"))
    execution_defaults = _apply_execution_prefills(selected_account_id)
    fractional_prefs = load_persisted_fractional_trading_preferences()
    if PIPELINE_ALLOW_FRACTIONAL_SHARES_KEY not in st.session_state:
        st.session_state[PIPELINE_ALLOW_FRACTIONAL_SHARES_KEY] = bool(fractional_prefs.pipeline_live_enabled)

    with st.expander("⚙️ Paramètres d'exécution", expanded=False):
        live_ml_diagnostic = get_live_ml_first_diagnostic()
        if live_ml_diagnostic.get("status") == "available":
            diagnostic_col1, diagnostic_col2, diagnostic_col3, diagnostic_col4 = st.columns(4)
            diagnostic_col1.metric("Univers PIT", str(live_ml_diagnostic.get("universe_run_id") or "—"))
            diagnostic_col2.metric("Couverture ML", f"{float(live_ml_diagnostic.get('coverage_pct') or 0):.1f}%")
            diagnostic_col3.metric("Champion servi", str(live_ml_diagnostic.get("served_champion") or "—"))
            diagnostic_col4.metric("Grade univers", str(live_ml_diagnostic.get("data_quality_grade") or "unknown"))
        else:
            st.warning(str(live_ml_diagnostic.get("reason") or "Diagnostic live ML-first indisponible."))
        # === BLOCK 1/9 : Execution (capital preset, dates, equity, mode, RTH, account/swing, fenêtre + trailing + debug) — inline (extraction prévue S6.1) ===
        st.caption(
            "Les pipelines sont lancés en arrière-plan depuis l'IHM. Ils héritent de la configuration DB active et, "
            "pour les étapes concernées, du compte Alpaca sélectionné dans la sidebar."
        )

        if selected_account_id:
            st.info(f"Compte Alpaca actuellement sélectionné : `{selected_account_id}`")
        else:
            st.info("Aucun compte Alpaca explicitement sélectionné — le compte par défaut sera utilisé si nécessaire.")

        capital_preset_options = _get_capital_preset_options()
        capital_preset_key = cast(
            str,
            st.selectbox(
                "Preset capital — Risk / Execution / Selector",
                options=capital_preset_options,
                index=capital_preset_options.index(
                    cast(str, st.session_state.get(CAPITAL_PRESET_KEY, CAPITAL_PRESET_CUSTOM))
                    if st.session_state.get(CAPITAL_PRESET_KEY, CAPITAL_PRESET_CUSTOM) in capital_preset_options
                    else CAPITAL_PRESET_CUSTOM
                ),
                format_func=_format_capital_preset_label,
                key=CAPITAL_PRESET_KEY,
                help=(
                    "Choisis un panier de capital pour préremplir automatiquement les paramètres Risk, "
                    "Execution et Alpha Scanner. Les champs restent éditables manuellement ensuite."
                ),
            ),
        )
        _apply_selected_capital_preset(execution_defaults, selected_account_id=selected_account_id)
        selected_capital_preset = get_capital_preset_by_key(capital_preset_key)
        detected_capital_preset = resolve_capital_preset_for_equity(execution_defaults.equity if execution_defaults is not None else None)
        if capital_preset_key == CAPITAL_PRESET_CUSTOM:
            if detected_capital_preset is not None and execution_defaults is not None and execution_defaults.equity is not None:
                st.info(
                    "🧺 Preset capital manuel actif — panier recommandé pour ce compte : "
                    f"`{detected_capital_preset.label}` (equity broker détectée ≈ `{execution_defaults.equity:,.2f}` $)."
                )
            else:
                st.info("🧺 Preset capital manuel actif — aucun panier automatique n'est appliqué tant que tu restes en `Personnalisé`.")
        elif selected_capital_preset is not None and execution_defaults is not None and execution_defaults.equity is not None:
            if detected_capital_preset is not None and detected_capital_preset.key == selected_capital_preset.key:
                st.success(
                    "🧺 Panier capital appliqué automatiquement : "
                    f"`{selected_capital_preset.label}` pour l'equity broker détectée ≈ `{execution_defaults.equity:,.2f}` $."
                )
            elif detected_capital_preset is not None:
                st.warning(
                    "🧺 Panier capital forcé manuellement : "
                    f"`{selected_capital_preset.label}`. Le panier recommandé pour l'equity détectée ≈ `{execution_defaults.equity:,.2f}` $ "
                    f"serait `{detected_capital_preset.label}`."
                )
            else:
                st.info(
                    "🧺 Panier capital appliqué : "
                    f"`{selected_capital_preset.label}` (equity broker détectée ≈ `{execution_defaults.equity:,.2f}` $)."
                )
        elif selected_capital_preset is not None:
            st.info(f"🧺 Panier capital appliqué : `{selected_capital_preset.label}`.")
        if selected_capital_preset is not None:
            st.caption(selected_capital_preset.description)
            executability_summary = build_capital_preset_executability_summary(
                selected_capital_preset,
                detected_equity=execution_defaults.equity if execution_defaults is not None else None,
            )
            st.caption(
                "Exécutabilité preset — "
                f"ticket mini `{executability_summary['min_position_notional']:,.0f} $`, "
                f"live DD `{executability_summary['recommended_live_max_portfolio_dd_pct']:.0%}`, "
                f"live vol target `{executability_summary['recommended_live_target_annual_vol']:.0%}` / `{executability_summary['recommended_live_vol_target_lookback_days']}`j, "
                f"live ML coverage `{executability_summary['recommended_live_min_ml_coverage_ratio']:.0%}`, "
                f"stress backtest `{executability_summary['recommended_commission_bps_stress']:.0f}+{executability_summary['recommended_slippage_bps_stress']:.0f} bps`, "
                f"settlement cash `T+{executability_summary['cash_settlement_days']}`, "
                f"ML gate `{executability_summary['ml_gate_policy']}`."
            )
            warning_lines = [str(value) for value in executability_summary.get("warnings", []) if str(value).strip()]
            if warning_lines:
                st.info(" ; ".join(warning_lines))
        st.markdown("🔁 **Impact des réglages sur les relances**")
        st.table(_build_parameter_rerun_guidance_rows())

        col1, col2, col3 = st.columns(3)
        with col1:
            # Pré-remplit avec la date du jour pour garantir la cohérence inter-étapes
            # quand on lance les pipelines un par un (notamment si l'exécution
            # déborde sur le lendemain). L'utilisateur peut écraser pour rejouer
            # un PIT historique.
            if "pipeline_trade_date" not in st.session_state:
                st.session_state["pipeline_trade_date"] = date.today().isoformat()
            trade_date = st.text_input(
                "Trade date / as-of (YYYY-MM-DD)",
                key="pipeline_trade_date",
                help=(
                    "Date logique partagée par toutes les étapes (Screener, Alpha Scanner, "
                    "Signal Aggregator, ML Predict, Risk, Execution, Corporate Actions Apply). "
                    "Pré-rempli avec la date du jour ; modifiez pour rejouer un PIT historique."
                ),
            )
            force_trade_date_to_latest_snapshot = st.checkbox(
                "Forcer trade_date sur le snapshot le plus récent",
                value=_session_state_bool("pipeline_force_trade_date_to_latest_snapshot", True),
                key="pipeline_force_trade_date_to_latest_snapshot",
                help=(
                    "Si coché (défaut), au lancement, trade_date est remplacé par MAX(snapshot_date) "
                    "<= trade_date avec une sélection classée dans stock_scores_history. Permet de continuer un "
                    "workflow démarré la veille même après réouverture de la session Streamlit (qui "
                    "réinitialise trade_date à la date du jour). Décochez pour utiliser strictement la "
                    "date saisie."
                ),
            )
        with col2:
            risk_account_equity = st.number_input(
                "Equity pour le module Risk",
                min_value=0.0,
                value=_session_state_float("pipeline_risk_account_equity", 100_000.0),
                step=1_000.0,
                format="%.2f",
                key="pipeline_risk_account_equity",
            )
        with col3:
            execution_mode = cast(
                str,
                st.selectbox(
                    "Mode Execution",
                    options=["simulate", "paper", "live"],
                    index=["simulate", "paper", "live"].index(
                        cast(str, st.session_state.get("pipeline_execution_mode", "simulate"))
                        if st.session_state.get("pipeline_execution_mode", "simulate") in {"simulate", "paper", "live"}
                        else "simulate"
                    ),
                    key="pipeline_execution_mode",
                ),
            )

            # === BLOCK 9/9 : Confirmation LIVE (extrait — _render_live_confirmation_block) ===
            live_confirmed = _render_live_confirmation_block(execution_mode)

        col4, col5, col6 = st.columns(3)
        with col4:
            execution_run_id = st.text_input(
                "Execution — risk_run_id optionnel",
                key="pipeline_execution_run_id",
                help="Laissez vide pour exécuter sur le dernier run disponible.",
            )
        execution_live_approval_token = str(
            st.session_state.get("pipeline_execution_live_approval_token", "")
        ).strip() or None
        execution_run_plan_file = str(
            st.session_state.get("pipeline_execution_run_plan_file", "")
        ).strip() or None
        with col5:
            allow_outside_rth = st.checkbox(
                "Execution hors RTH (file d'attente pour l'ouverture)",
                value=_session_state_bool("pipeline_allow_outside_rth", False),
                key="pipeline_allow_outside_rth",
                help="Soumet les ordres meme si le marche est ferme. En paper/live, ils restent en attente et seront traites a l'ouverture suivante.",
            )
        with col6:
            auto_rebalance = st.checkbox(
                "Auto rebalance",
                value=_session_state_bool("pipeline_auto_rebalance", False),
                key="pipeline_auto_rebalance",
            )

        allow_fractional_shares = st.toggle(
            "Execution/Risk — autoriser les quantités fractionnaires",
            value=_session_state_bool(
                PIPELINE_ALLOW_FRACTIONAL_SHARES_KEY,
                bool(fractional_prefs.pipeline_live_enabled),
            ),
            key=PIPELINE_ALLOW_FRACTIONAL_SHARES_KEY,
            help=(
                "Active la propagation du mode fractionnaire vers les étapes `risk_management` et `execution`. "
                "Valeur persistée côté serveur dans `artifacts/ihm_preferences/fractional_trading.json`."
            ),
        )
        if bool(allow_fractional_shares) != bool(fractional_prefs.pipeline_live_enabled):
            save_persisted_fractional_trading_preferences(
                FractionalTradingPreferences(
                    backtest_enabled=bool(fractional_prefs.backtest_enabled),
                    pipeline_live_enabled=bool(allow_fractional_shares),
                )
            )
        if allow_fractional_shares:
            st.success(
                "🧮 Mode fractionnaire pipeline activé — les commandes IHM transmettront `--allow-fractional-shares` à `risk_management` et `run_execution.py`."
            )
        else:
            st.warning(
                "🧮 Mode fractionnaire pipeline désactivé — les runs IHM resteront en quantités entières tant que ce switch est coupé."
            )

        exec_col1, exec_col2 = st.columns(2)
        st.warning(
            "⚠️ différence potentiellement forte entre margin et cash\n\n"
            "- `margin` utilise le buying power broker ; `cash` se limite au cash settled / non-marginable buying power.\n"
            "- À equity identique, cela peut changer fortement le nombre d'ordres soumis et la capacité de rebalancing.\n"
            "- Résultat : les fills, les exits armés (TP/TS) et donc les performances observées peuvent diverger fortement entre `margin` et `cash`."
        )
        prefill_caption = _build_execution_prefill_caption(execution_defaults)
        if prefill_caption:
            st.caption(prefill_caption)
        with exec_col1:
            execution_account_type = cast(
                str,
                st.selectbox(
                    "Execution — type de compte",
                    options=["margin", "cash"],
                    index=["margin", "cash"].index(
                        cast(str, st.session_state.get("pipeline_execution_account_type", "cash"))
                        if st.session_state.get("pipeline_execution_account_type", "cash") in {"margin", "cash"}
                        else "cash"
                    ),
                    key="pipeline_execution_account_type",
                    help="Défaut swing : `cash`. `margin` utilise le buying power ; `cash` utilise uniquement le cash settled disponible.",
                ),
            )
        with exec_col2:
            execution_swing_only_default = _session_state_bool(
                "pipeline_execution_swing_only",
                False,
            )
            execution_swing_only = st.checkbox(
                "Execution — swing only",
                value=execution_swing_only_default,
                key="pipeline_execution_swing_only",
                help="Depuis le 2026-06-04 (FINRA), la règle PDT est supprimée : le day trading intraday est libre. "
                "Défaut : False (décoché). Si coché, le moteur diffère l'armement des sorties le jour même du fill.",
            )

        constraint_notes = [
            f"Type de compte : `{execution_account_type}`",
            f"Swing only : `{bool(execution_swing_only)}`",
        ]
        if execution_account_type == "cash":
            constraint_notes.append("En `cash`, le moteur se base sur le cash settled / non-marginable buying power.")
        else:
            constraint_notes.append("En `margin`, le moteur se base sur le buying power broker.")
        if execution_swing_only:
            constraint_notes.append("Les children TP/TS sont différés le jour même du fill.")
        st.info(" | ".join(constraint_notes))
        if execution_swing_only:
            st.warning(
                "⚠️ **SWING ONLY** est coché. Depuis le 4 juin 2026, la FINRA a **supprimé la règle PDT** : "
                "le day trading intraday est autorisé sans restriction. Tous les presets de capital utilisent "
                "`swing_only=False`. Décochez cette option sauf restriction volontaire explicite."
            )

        # ──────────────────────────────────────────────────────────────────
        # Stratégie de protection (sortie) — P1 cf. audit_ihm_pipeline_options.md
        # ──────────────────────────────────────────────────────────────────
        st.markdown("#### Stratégie de protection — sortie (`run_execution.py`)")
        st.caption(
            "Pilote le take-profit, le trailing stop broker-side, la fenêtre de soumission hors RTH et le déclencheur du trailing stop dynamique. "
            "Le stop initial n'est pas saisi ici : il est calculé automatiquement par le step 11 Risk (`stop_price_initial` / `risk_per_share`, basé sur l'ATR). "
            "Défauts swing : TP `+8 %`, trailing stop `5 %`, fenêtre `both` (post_close + pre_open), trigger `multiple_r` à 1.0R."
        )
        prot_col1, prot_col2, prot_col_msl, prot_col3, prot_col4, prot_col5 = st.columns(6)
        with prot_col1:
            execution_take_profit_pct_percent_default = _session_state_float(
                "pipeline_execution_take_profit_pct_percent",
                _session_state_float(
                    "pipeline_execution_take_profit_pct",
                    DEFAULT_EXEC_TAKE_PROFIT_PCT,
                )
                * 100.0,
            )
            execution_take_profit_pct_percent = float(
                st.number_input(
                    "Take-profit cible (%)",
                    min_value=0.1,
                    max_value=50.0,
                    value=execution_take_profit_pct_percent_default,
                    step=0.5,
                    format="%.2f",
                    key="pipeline_execution_take_profit_pct_percent",
                    help="Exemple : `8.0` = +8 %. Le TP effectif garde la logique risk-based du moteur (`max` entre la règle % et la cible métier basée sur le risque).",
                )
            )
            execution_take_profit_pct = float(
                execution_take_profit_pct_percent / 100.0
            )
            st.session_state["pipeline_execution_take_profit_pct"] = execution_take_profit_pct
        with prot_col2:
            execution_trailing_stop_pct_percent_default = _session_state_float(
                "pipeline_execution_trailing_stop_pct_percent",
                _session_state_float(
                    "pipeline_execution_trailing_stop_pct",
                    DEFAULT_EXEC_TRAILING_STOP_PCT,
                )
                * 100.0,
            )
            execution_trailing_stop_pct_percent = float(
                st.number_input(
                    "Trailing stop (%)",
                    min_value=0.1,
                    max_value=50.0,
                    value=execution_trailing_stop_pct_percent_default,
                    step=0.5,
                    format="%.2f",
                    key="pipeline_execution_trailing_stop_pct_percent",
                    help="Exemple : `5.0` = trailing stop à 5 %. Ce pourcentage est utilisé pour le trailing broker-side / fallback si le calcul risk-based ne le remplace pas.",
                )
            )
            execution_trailing_stop_pct = float(execution_trailing_stop_pct_percent / 100.0)
            st.session_state["pipeline_execution_trailing_stop_pct"] = execution_trailing_stop_pct
        with prot_col_msl:
            # Sprint 2026-05 — SL dédié aux achats manuels orphelins (Q8 du
            # FAQ opérateur). N'affecte PAS les achats Alpha Trade qui
            # conservent leur stop ATR / risk-based.
            execution_manual_buy_sl_pct_percent_default = _session_state_float(
                "pipeline_execution_manual_buy_stop_loss_pct_percent",
                _session_state_float(
                    "pipeline_execution_manual_buy_stop_loss_pct",
                    DEFAULT_EXEC_MANUAL_BUY_SL_PCT,
                )
                * 100.0,
            )
            execution_manual_buy_sl_pct_percent = float(
                st.number_input(
                    "Stop-loss achat manuel (%)",
                    min_value=0.1,
                    max_value=50.0,
                    value=execution_manual_buy_sl_pct_percent_default,
                    step=0.5,
                    format="%.2f",
                    key="pipeline_execution_manual_buy_stop_loss_pct_percent",
                    help=(
                        "⚠️ Ce SL est dédié à l'achat manuel UNIQUEMENT — c.-à-d. "
                        "aux positions ouvertes hors Alpha Trade (site / app "
                        "Alpaca, API tierce). Le watcher de protections les "
                        "adopte (`adopted_entry`) puis arme automatiquement "
                        "TP + SL avec ce pourcentage sous le prix d'entrée. "
                        "Les achats normaux d'Alpha Trade gardent leur stop "
                        "ATR / risk-based calculé par le selector."
                    ),
                )
            )
            execution_manual_buy_stop_loss_pct = float(
                execution_manual_buy_sl_pct_percent / 100.0
            )
            st.session_state["pipeline_execution_manual_buy_stop_loss_pct"] = execution_manual_buy_stop_loss_pct
        with prot_col3:
            execution_submission_window = cast(
                str,
                st.selectbox(
                    "Execution — fenêtre de soumission",
                    options=["post_close", "pre_open", "both"],
                    index=["post_close", "pre_open", "both"].index(
                        cast(str, st.session_state.get("pipeline_execution_submission_window", DEFAULT_EXEC_SUBMISSION_WINDOW))
                        if st.session_state.get("pipeline_execution_submission_window", DEFAULT_EXEC_SUBMISSION_WINDOW) in {"post_close", "pre_open", "both"}
                        else DEFAULT_EXEC_SUBMISSION_WINDOW
                    ),
                    key="pipeline_execution_submission_window",
                    help="`both` : essaie post-close puis bascule sur pre-open si la fenêtre post-close est passée.",
                ),
            )
        with prot_col4:
            execution_trailing_trigger = cast(
                str,
                st.selectbox(
                    "Trigger d'activation du trailing",
                    options=["multiple_r", "profit_pct"],
                    index=["multiple_r", "profit_pct"].index(
                        cast(str, st.session_state.get("pipeline_execution_trailing_trigger", DEFAULT_EXEC_TRAILING_TRIGGER))
                        if st.session_state.get("pipeline_execution_trailing_trigger", DEFAULT_EXEC_TRAILING_TRIGGER) in {"multiple_r", "profit_pct"}
                        else DEFAULT_EXEC_TRAILING_TRIGGER
                    ),
                    key="pipeline_execution_trailing_trigger",
                    help="`multiple_r` : armer le trailing après N×R atteint. `profit_pct` : armer après X% de profit.",
                ),
            )
        with prot_col5:
            if execution_trailing_trigger == "multiple_r":
                execution_trailing_r_multiple = float(
                    st.number_input(
                        "Multiple de R pour activation",
                        min_value=0.1,
                        value=_session_state_float(
                            "pipeline_execution_trailing_r_multiple",
                            DEFAULT_EXEC_TRAILING_R_MULTIPLE,
                        ),
                        step=0.1,
                        format="%.2f",
                        key="pipeline_execution_trailing_r_multiple",
                    )
                )
                execution_trailing_profit_pct = _session_state_float(
                    "pipeline_execution_trailing_profit_pct",
                    DEFAULT_EXEC_TRAILING_PROFIT_PCT,
                )
            else:
                execution_trailing_profit_pct = float(
                    st.number_input(
                        "Profit % pour activation",
                        min_value=0.001,
                        value=_session_state_float(
                            "pipeline_execution_trailing_profit_pct",
                            DEFAULT_EXEC_TRAILING_PROFIT_PCT,
                        ),
                        step=0.005,
                        format="%.4f",
                        key="pipeline_execution_trailing_profit_pct",
                    )
                )
                execution_trailing_r_multiple = _session_state_float(
                    "pipeline_execution_trailing_r_multiple",
                    DEFAULT_EXEC_TRAILING_R_MULTIPLE,
                )

        with st.expander("Execution — transition trigger avancé & debug", expanded=False):
            st.caption(
                "Pilote `--max-entry-gap-pct`, `--protection-transition-timeout-seconds` / "
                "`--protection-transition-poll-interval-seconds` et `--debug` côté `run_execution.py`. "
                "Défauts swing : gap filter désactivé (0), 120 s / 5 s, debug désactivé."
            )
            adv_exec_col1, adv_exec_col2, adv_exec_col3, adv_exec_col4 = st.columns(4)
            with adv_exec_col1:
                execution_max_entry_gap_pct = float(
                    st.number_input(
                        "Gap d'entrée max (fraction)",
                        min_value=0.0,
                        max_value=1.0,
                        value=_session_state_float(
                            "pipeline_execution_max_entry_gap_pct",
                            DEFAULT_EXEC_MAX_ENTRY_GAP_PCT,
                        ),
                        step=0.005,
                        format="%.4f",
                        key="pipeline_execution_max_entry_gap_pct",
                        help="Ex. 0.03 = bloque une entrée si le dernier prix marché est à plus de 3% du close précédent. 0 = désactivé.",
                    )
                )
            with adv_exec_col2:
                execution_protection_transition_timeout_seconds = int(
                    st.number_input(
                        "Transition — timeout (s)",
                        min_value=0,
                        max_value=3600,
                        value=_session_state_int(
                            "pipeline_execution_protection_transition_timeout_seconds",
                            DEFAULT_EXEC_PROTECTION_TRANSITION_TIMEOUT_SECONDS,
                        ),
                        step=10,
                        key="pipeline_execution_protection_transition_timeout_seconds",
                        help="0 = ne pas envoyer le flag (laisse le défaut backend).",
                    )
                )
            with adv_exec_col3:
                execution_protection_transition_poll_interval_seconds = float(
                    st.number_input(
                        "Transition — poll interval (s)",
                        min_value=0.0,
                        max_value=120.0,
                        value=_session_state_float(
                            "pipeline_execution_protection_transition_poll_interval_seconds",
                            DEFAULT_EXEC_PROTECTION_TRANSITION_POLL_INTERVAL_SECONDS,
                        ),
                        step=0.5,
                        format="%.2f",
                        key="pipeline_execution_protection_transition_poll_interval_seconds",
                        help="0 = ne pas envoyer le flag (laisse le défaut backend).",
                    )
                )
            with adv_exec_col4:
                execution_debug = st.checkbox(
                    "Execution — `--debug` (logs DEBUG)",
                    value=_session_state_bool("pipeline_execution_debug", DEFAULT_EXEC_DEBUG),
                    key="pipeline_execution_debug",
                )

        # ──────────────────────────────────────────────────────────────────
        # Paramètres Risk Management — P1 cf. audit_ihm_pipeline_options.md
        # ──────────────────────────────────────────────────────────────────
        # === BLOCK 2/9 : Risk Management + Kelly sizing (extrait — _render_risk_block) ===
        _risk_vars = _render_risk_block(selected_capital_preset)
        risk_per_trade_pct = _risk_vars["risk_per_trade_pct"]
        risk_max_positions = _risk_vars["risk_max_positions"]
        risk_max_position_weight = _risk_vars["risk_max_position_weight"]
        risk_max_sector_weight = _risk_vars["risk_max_sector_weight"]
        risk_min_position_notional = _risk_vars["risk_min_position_notional"]
        risk_score_weight = _risk_vars["risk_score_weight"]
        risk_prediction_weight = _risk_vars["risk_prediction_weight"]
        risk_correlation_threshold = _risk_vars["risk_correlation_threshold"]
        risk_correlation_lookback_days = _risk_vars["risk_correlation_lookback_days"]
        risk_enable_kelly = _risk_vars["risk_enable_kelly"]
        risk_max_portfolio_drawdown_pct = _risk_vars["risk_max_portfolio_drawdown_pct"]
        risk_max_daily_loss_pct = _risk_vars["risk_max_daily_loss_pct"]
        risk_target_annual_vol = _risk_vars["risk_target_annual_vol"]
        risk_vol_target_lookback_days = _risk_vars["risk_vol_target_lookback_days"]
        risk_min_ml_coverage_ratio = _risk_vars["risk_min_ml_coverage_ratio"]
        risk_dry_run = _risk_vars["risk_dry_run"]
        risk_payoff_ratio = _risk_vars["risk_payoff_ratio"]
        risk_kelly_fraction_multiplier = _risk_vars["risk_kelly_fraction_multiplier"]
        risk_correlation_min_overlap = _risk_vars["risk_correlation_min_overlap"]
        risk_log_level = _risk_vars["risk_log_level"]

        # === BLOCK 3/9 : Model Factory (preset + cible swing + walk-forward + hyperparams + grilles candidate) — inline (extraction prévue S6.1) ===
        st.markdown("#### Paramètres Model Factory")
        st.caption(
            "Ces options pilotent directement `python -m modelFactory --mode train`. "
            "L'objectif est d'aligner l'IHM sur la gouvernance multi-modèles réellement disponible côté backend."
        )
        normalized_ml_train_preset = _ensure_normalized_ml_train_preset_session_state(cast(dict[str, object], st.session_state))
        _apply_selected_ml_train_preset()
        ml_train_preset = cast(
            str,
            st.selectbox(
                "Preset ML Train",
                options=list(ML_TRAIN_PRESET_OPTIONS),
                index=list(ML_TRAIN_PRESET_OPTIONS).index(normalized_ml_train_preset),
                key=ML_TRAIN_PRESET_KEY,
                format_func=_format_ml_train_preset_label,
                help=(
                    "Préremplit automatiquement un profil ML adapté au contexte : prod swing, debug rapide CPU ou debug GPU. "
                    "Les champs restent modifiables ensuite."
                ),
            ),
        )
        ml_train_preset_dirty = _is_selected_ml_train_preset_dirty(cast(dict[str, object], st.session_state))
        ml_train_preset_status = "🟡 preset modifié manuellement" if ml_train_preset_dirty else "🟢 preset aligné"
        st.caption(f"{_build_ml_train_preset_summary(ml_train_preset)} — {ml_train_preset_status}.")
        if ml_train_preset != ML_TRAIN_PRESET_CUSTOM:
            ml_preset_action_col1, ml_preset_action_col2 = st.columns([1, 3])
            with ml_preset_action_col1:
                st.button(
                    "↩️ Reset vers preset",
                    key="pipeline_ml_train_reset_to_preset",
                    use_container_width=True,
                    help="Réapplique volontairement toutes les valeurs recommandées du preset ML sélectionné.",
                    on_click=_apply_selected_ml_train_preset,
                    kwargs={"force": True},
                )
            with ml_preset_action_col2:
                if ml_train_preset_dirty:
                    st.caption("Des champs ML ont été modifiés depuis l'application initiale du preset ; ce bouton écrasera ces surcharges manuelles.")
                else:
                    st.caption("Tu peux réappliquer explicitement ce preset à tout moment si tu veux revenir aux valeurs recommandées.")

        ml_col1, ml_col2 = st.columns([2, 3])
        with ml_col1:
            ml_accelerator = cast(
                str,
                st.selectbox(
                    "Accélérateur ML",
                    options=["auto", "cpu", "gpu"],
                    index=["auto", "cpu", "gpu"].index(
                        cast(str, st.session_state.get("pipeline_ml_accelerator", "auto"))
                        if st.session_state.get("pipeline_ml_accelerator", "auto") in {"auto", "cpu", "gpu"}
                        else "auto"
                    ),
                    key="pipeline_ml_accelerator",
                    help="Appliqué aux étapes ML Train et ML Predict. 'auto' utilise le GPU si CUDA est disponible, sinon CPU.",
                ),
            )
        with ml_col2:
            gpu_detected = is_gpu_available()
            if gpu_detected:
                st.success("GPU CUDA détecté dans l'environnement de l'IHM : les jobs ML peuvent être lancés en mode `auto` ou `gpu`.")
            else:
                st.info("Aucun GPU CUDA détecté dans l'environnement de l'IHM : le mode `auto` retombera sur CPU.")

        ml_scope_col1, ml_scope_col2 = st.columns(2)
        with ml_scope_col1:
            ml_training_start_date = cast(
                date,
                st.date_input(
                    "Date de début du training ML",
                    value=_coerce_session_date(
                        st.session_state.get("pipeline_ml_training_start_date", DEFAULT_ML_TRAINING_START_DATE),
                        default=date(2018, 1, 1),
                    ),
                    key="pipeline_ml_training_start_date",
                    format="YYYY-MM-DD",
                    help="Date minimale des barres daily transmises au backend Model Factory. Le défaut `2018-01-01` permet de cadrer le training sur l'historique récent utile.",
                ),
            )
        with ml_scope_col2:
            ml_training_end_date = cast(
                date,
                st.date_input(
                    "Date de fin du training ML",
                    value=_coerce_session_date(
                        st.session_state.get("pipeline_ml_training_end_date", DEFAULT_ML_TRAINING_END_DATE),
                        default=date.today(),
                    ),
                    key="pipeline_ml_training_end_date",
                    format="YYYY-MM-DD",
                    help="Date maximale incluse pour borner le training ML ciblé et les prédictions historiques ML Predict.",
                ),
            )

        st.caption("Chaque lancement ML Train crée une campagne complète et isolée.")
        ml_train_symbol_source = "tradable-universe"
        ml_predict_symbol_source = "tradable-universe"
        ml_opt_col1, ml_opt_col2, ml_opt_col3 = st.columns(3)
        with ml_opt_col1:
            ml_include_sentiment = st.checkbox(
                "Inclure les features sentiment",
                value=_session_state_bool("pipeline_ml_include_sentiment", False),
                key="pipeline_ml_include_sentiment",
                help="Ajoute `--include-sentiment` à `ml_train`.",
            )
            ml_include_screener_scores = st.checkbox(
                "Inclure les scores du screener (trend, VCP, final_score…)",
                value=_session_state_bool("pipeline_ml_include_screener_scores", DEFAULT_ML_INCLUDE_SCREENER_SCORES),
                key="pipeline_ml_include_screener_scores",
                help="Ajoute `--include-screener-scores` pour enrichir le dataset ML avec les scores PIT-safe du screener (trend_score, vcp_score, final_score, market_cap, beta, etc.).",
            )
            ml_include_short_score = st.checkbox(
                "Inclure le short_score dédié (score baissier)",
                value=_session_state_bool("pipeline_ml_include_short_score", DEFAULT_ML_INCLUDE_SHORT_SCORE),
                key="pipeline_ml_include_short_score",
                help="Ajoute `--include-short-score` pour intégrer le score baissier composite (trend+RSI+SMA) comme feature ML indépendante.",
            )
            ml_enable_lightgbm = st.checkbox(
                "Entraîner aussi LightGBM (challenger)",
                value=_session_state_bool("pipeline_ml_enable_lightgbm", DEFAULT_ML_ENABLE_LIGHTGBM),
                key="pipeline_ml_enable_lightgbm",
                help="Ajoute `--compare-lightgbm`. LightGBM excelle sur données tabulaires peu profondes.",
            )
            ml_enable_catboost = st.checkbox(
                "Entraîner aussi CatBoost (challenger)",
                value=_session_state_bool("pipeline_ml_enable_catboost", DEFAULT_ML_ENABLE_CATBOOST),
                key="pipeline_ml_enable_catboost",
                help="Ajoute `--enable-catboost`. CatBoost gère bien les features catégorielles et le faible volume de données.",
            )
        with ml_opt_col2:
            ml_include_macro_vix = st.checkbox(
                "📊 VIX/VIX9D (volatilité S&P 500)",
                value=_session_state_bool("pipeline_ml_include_macro_vix", False),
                key="pipeline_ml_include_macro_vix",
                help="Ajoute `--include-macro-vix`. Nécessite un backfill préalable de `stock_macro_indicators_daily`.",
            )
            ml_include_macro_vxn = st.checkbox(
                "📊 VXN (volatilité NASDAQ-100)",
                value=_session_state_bool("pipeline_ml_include_macro_vxn", False),
                key="pipeline_ml_include_macro_vxn",
                help="Ajoute `--include-macro-vxn`. Utile pour les valeurs Tech.",
            )
            ml_include_macro_vix3m = st.checkbox(
                "📊 VIX3M + ratio (term structure)",
                value=_session_state_bool("pipeline_ml_include_macro_vix3m", False),
                key="pipeline_ml_include_macro_vix3m",
                help="Ajoute `--include-macro-vix3m`. Ratio VIX/VIX3M : détecte la backwardation (panique court terme).",
            )
            ml_include_macro_move = st.checkbox(
                "📊 MOVE (volatilité obligataire)",
                value=_session_state_bool("pipeline_ml_include_macro_move", False),
                key="pipeline_ml_include_macro_move",
                help="Ajoute `--include-macro-move`. Indice ICE BofA MOVE : volatilité des bons du Trésor US.",
            )
        with ml_opt_col3:
            ml_select_champion = st.checkbox(
                "Activer la sélection automatique du champion",
                value=_session_state_bool("pipeline_ml_select_champion", True),
                key="pipeline_ml_select_champion",
                help="Ajoute `--select-champion` et permet de servir automatiquement le meilleur modèle éligible.",
            )
            ml_optimize_thresholds = st.checkbox(
                "Optimiser le seuil de décision (pour le mode binaire)",
                value=_session_state_bool("pipeline_ml_optimize_thresholds", False),
                key="pipeline_ml_optimize_thresholds",
                help="Ajoute `--optimize-thresholds` pour sélectionner le meilleur `decision_threshold` sur validation.",
            )
        with ml_opt_col3:
            # ── Approche 2 : 3 checkboxes hiérarchiques ──
            ml_enable_global_model = st.checkbox(
                "Entraîner aussi un modèle global multi-symboles",
                value=_session_state_bool("pipeline_ml_enable_global_model", False),
                key="pipeline_ml_enable_global_model",
                help="Ajoute `--enable-global-model`. Entraîne un modèle tabulaire (CatBoost/LightGBM) sur tous les symboles en walk-forward pour produire `global_pred_long` PIT-safe.",
            )
            st.caption("Les deux options ci-dessous nécessitent que le modèle global soit activé.")
            ml_enable_global_stacking = st.checkbox(
                "📥 Utiliser la prédiction globale comme feature (Stacking)",
                value=_session_state_bool("pipeline_ml_enable_global_stacking", False),
                key="pipeline_ml_enable_global_stacking",
                disabled=not ml_enable_global_model,
                help="Ajoute `--enable-global-stacking`. Injecte `global_pred_long` comme feature dans les modèles per-symbol (LSTM/LGBM/CatBoost). Le modèle apprend à pondérer le signal transverse.",
            )
            ml_enable_global_challenger = st.checkbox(
                "🏆 Inclure le modèle global dans la sélection champion",
                value=_session_state_bool("pipeline_ml_enable_global_challenger", False),
                key="pipeline_ml_enable_global_challenger",
                disabled=not ml_enable_global_model,
                help="Ajoute `--enable-global-challenger`. Le Global Model devient un 4ème challenger avec métriques walk-forward comparables (wf.f1_macro).",
            )
            ml_global_model_name = cast(
                str,
                st.selectbox(
                    "Backend du modèle global",
                    options=["catboost", "lightgbm"],
                    index=["catboost", "lightgbm"].index(
                        cast(str, st.session_state.get("pipeline_ml_global_model_name", "catboost"))
                        if st.session_state.get("pipeline_ml_global_model_name", "catboost") in {"catboost", "lightgbm"}
                        else "catboost"
                    ),
                    key="pipeline_ml_global_model_name",
                    disabled=not ml_enable_global_model,
                ),
            )
            # Checkbox unique : active à la fois les rangs percentiles ET les features sectorielles
            ml_enable_cross_sectional = st.checkbox(
                "🌐 Features cross-sectionnelles & sectorielles (rangs percentiles + momentum intra-secteur)",
                value=_session_state_bool("pipeline_ml_enable_cross_sectional", DEFAULT_ML_ENABLE_CROSS_SECTIONAL),
                key="pipeline_ml_enable_cross_sectional",
                help="Ajoute `--enable-cross-sectional`. Calcule les rangs percentiles PIT-safe ET les features sectorielles dynamiques (momentum, volatilité, alpha intra-secteur GICS).",
            )

        ml_adv_col1, ml_adv_col2 = st.columns(2)
        with ml_adv_col1:
            ml_optimize_target = st.checkbox(
                "Optimiser l'horizon / la target swing",
                value=_session_state_bool("pipeline_ml_optimize_target", False),
                key="pipeline_ml_optimize_target",
                help="Ajoute `--optimize-target`.",
            )
        with ml_adv_col2:
            st.info(
                "`ML Predict` n'entraîne rien : il réutilise le `selected_model` présent dans les artefacts symbole. "
                "Si `ml_train` a activé les challengers et la sélection champion, l'inférence quotidienne suivra automatiquement ce routage."
            )

        # ──────────────────────────────────────────────────────────────────
        # ML — Cible swing cash + horizon + walk-forward (P1)
        # ──────────────────────────────────────────────────────────────────
        st.markdown("##### Cible swing & horizon")
        ml_target_col1, ml_target_col2, ml_target_col3 = st.columns(3)
        with ml_target_col1:
            ml_target_mode = cast(
                str,
                st.selectbox(
                    "Mode de cible",
                    options=["binary", "swing_cash", "ternary"],
                    index=["binary", "swing_cash", "ternary"].index(
                        cast(str, st.session_state.get("pipeline_ml_target_mode", DEFAULT_ML_TARGET_MODE))
                        if st.session_state.get("pipeline_ml_target_mode", DEFAULT_ML_TARGET_MODE) in {"binary", "swing_cash", "ternary"}
                        else DEFAULT_ML_TARGET_MODE
                    ),
                    key="pipeline_ml_target_mode",
                    help="`swing_cash` = cible asymétrique up/down. `ternary` = long/flat/short (ML Sprint 1).",
                ),
            )
            ml_forecast_horizon = int(
                st.number_input(
                    "Horizon de prédiction (jours)",
                    min_value=1,
                    max_value=30,
                    value=_session_state_int(
                        "pipeline_ml_forecast_horizon",
                        DEFAULT_ML_FORECAST_HORIZON,
                    ),
                    step=1,
                    key="pipeline_ml_forecast_horizon",
                    help="Défaut swing : 5 jours. Ajustable 3-15 selon style.",
                )
            )
        with ml_target_col2:
            ml_target_up_threshold = float(
                st.number_input(
                    "Seuil cible UP",
                    min_value=0.0,
                    max_value=0.20,
                    value=_session_state_float(
                        "pipeline_ml_target_up_threshold",
                        DEFAULT_ML_TARGET_UP_THRESHOLD,
                    ),
                    step=0.005,
                    format="%.4f",
                    key="pipeline_ml_target_up_threshold",
                    help="Ex. 0.02 = +2 % sur l'horizon pour étiqueter long.",
                )
            )
            ml_target_down_threshold = float(
                st.number_input(
                    "Seuil cible DOWN",
                    min_value=-0.20,
                    max_value=0.0,
                    value=_session_state_float(
                        "pipeline_ml_target_down_threshold",
                        DEFAULT_ML_TARGET_DOWN_THRESHOLD,
                    ),
                    step=0.005,
                    format="%.4f",
                    key="pipeline_ml_target_down_threshold",
                )
            )
        with ml_target_col3:
            ml_decision_threshold = float(
                st.number_input(
                    "Seuil de décision",
                    min_value=0.0,
                    max_value=1.0,
                    value=_session_state_float(
                        "pipeline_ml_decision_threshold",
                        DEFAULT_ML_DECISION_THRESHOLD,
                    ),
                    step=0.01,
                    format="%.2f",
                    key="pipeline_ml_decision_threshold",
                )
            )
            ml_calibration_method = cast(
                str,
                st.selectbox(
                    "Méthode de calibration",
                    options=["none", "platt"],
                    index=["none", "platt"].index(
                        cast(str, st.session_state.get("pipeline_ml_calibration_method", DEFAULT_ML_CALIBRATION_METHOD))
                        if st.session_state.get("pipeline_ml_calibration_method", DEFAULT_ML_CALIBRATION_METHOD) in {"none", "platt"}
                        else DEFAULT_ML_CALIBRATION_METHOD
                    ),
                    key="pipeline_ml_calibration_method",
                ),
            )

        st.markdown("##### Poids ternaires (short / flat / long)")
        _tw_col1, _tw_col2, _tw_col3 = st.columns(3)
        with _tw_col1:
            ml_ternary_weight_short = float(
                st.number_input(
                    "Poids short",
                    min_value=0.1,
                    max_value=5.0,
                    value=_session_state_float("pipeline_ml_ternary_weight_short", DEFAULT_ML_TERNARY_WEIGHT_SHORT),
                    step=0.05,
                    format="%.1f",
                    key="pipeline_ml_ternary_weight_short",
                    help="Poids de la classe short dans la CrossEntropyLoss ternaire (défaut: 1.0).",
                )
            )
        with _tw_col2:
            ml_ternary_weight_flat = float(
                st.number_input(
                    "Poids flat",
                    min_value=0.1,
                    max_value=5.0,
                    value=_session_state_float("pipeline_ml_ternary_weight_flat", DEFAULT_ML_TERNARY_WEIGHT_FLAT),
                    step=0.05,
                    format="%.1f",
                    key="pipeline_ml_ternary_weight_flat",
                    help="Poids de la classe flat dans la CrossEntropyLoss ternaire (défaut: 1.5).",
                )
            )
        with _tw_col3:
            ml_ternary_weight_long = float(
                st.number_input(
                    "Poids long",
                    min_value=0.1,
                    max_value=5.0,
                    value=_session_state_float("pipeline_ml_ternary_weight_long", DEFAULT_ML_TERNARY_WEIGHT_LONG),
                    step=0.05,
                    format="%.1f",
                    key="pipeline_ml_ternary_weight_long",
                    help="Poids de la classe long dans la CrossEntropyLoss ternaire (défaut: 1.0).",
                )
            )

        st.markdown("##### Seuils de décision ternaire (short / long / marge)")
        _td_col1, _td_col2, _td_col3 = st.columns(3)
        with _td_col1:
            ml_ternary_threshold_short = float(
                st.number_input(
                    "Seuil short",
                    min_value=0.10,
                    max_value=0.90,
                    value=_session_state_float("pipeline_ml_ternary_threshold_short", DEFAULT_ML_TERNARY_THRESHOLD_SHORT),
                    step=0.05,
                    format="%.2f",
                    key="pipeline_ml_ternary_threshold_short",
                    help="p_short minimum pour autoriser un signal short (défaut: 0.45). Baisser pour réduire le flat.",
                )
            )
        with _td_col2:
            ml_ternary_threshold_long = float(
                st.number_input(
                    "Seuil long",
                    min_value=0.10,
                    max_value=0.90,
                    value=_session_state_float("pipeline_ml_ternary_threshold_long", DEFAULT_ML_TERNARY_THRESHOLD_LONG),
                    step=0.05,
                    format="%.2f",
                    key="pipeline_ml_ternary_threshold_long",
                    help="p_long minimum pour autoriser un signal long (défaut: 0.45). Baisser pour réduire le flat.",
                )
            )
        with _td_col3:
            ml_ternary_top2_margin = float(
                st.number_input(
                    "Marge top-2",
                    min_value=0.00,
                    max_value=0.50,
                    value=_session_state_float("pipeline_ml_ternary_top2_margin", DEFAULT_ML_TERNARY_TOP2_MARGIN),
                    step=0.01,
                    format="%.2f",
                    key="pipeline_ml_ternary_top2_margin",
                    help="Écart minimum entre la 1ère et 2ème proba (défaut: 0.05). 0 = pas de marge exigée.",
                )
            )

        st.markdown("##### Walk-forward")
        ml_wf_col1, ml_wf_col2 = st.columns([1, 4])
        with ml_wf_col1:
            ml_walkforward = st.checkbox(
                "Activer walk-forward",
                value=_session_state_bool("pipeline_ml_walkforward", DEFAULT_ML_WALKFORWARD),
                key="pipeline_ml_walkforward",
                help="Activé par défaut en swing prod (cf. audit_global). Désactiver uniquement pour debug rapide.",
            )
        with ml_wf_col2:
            if ml_walkforward:
                wf_subcol1, wf_subcol2, wf_subcol3, wf_subcol4, wf_subcol5 = st.columns(5)
                with wf_subcol1:
                    ml_wf_min_train_size = int(
                        st.number_input(
                            "wf min train",
                            min_value=60,
                            value=_session_state_int(
                                "pipeline_ml_wf_min_train_size",
                                DEFAULT_ML_WF_MIN_TRAIN_SIZE,
                            ),
                            step=21,
                            key="pipeline_ml_wf_min_train_size",
                        )
                    )
                with wf_subcol2:
                    ml_wf_val_size = int(
                        st.number_input(
                            "wf val",
                            min_value=10,
                            value=_session_state_int(
                                "pipeline_ml_wf_val_size",
                                DEFAULT_ML_WF_VAL_SIZE,
                            ),
                            step=21,
                            key="pipeline_ml_wf_val_size",
                        )
                    )
                with wf_subcol3:
                    ml_wf_test_size = int(
                        st.number_input(
                            "wf test",
                            min_value=10,
                            value=_session_state_int(
                                "pipeline_ml_wf_test_size",
                                DEFAULT_ML_WF_TEST_SIZE,
                            ),
                            step=21,
                            key="pipeline_ml_wf_test_size",
                        )
                    )
                with wf_subcol4:
                    ml_wf_step_size = int(
                        st.number_input(
                            "wf step",
                            min_value=10,
                            value=_session_state_int(
                                "pipeline_ml_wf_step_size",
                                DEFAULT_ML_WF_STEP_SIZE,
                            ),
                            step=21,
                            key="pipeline_ml_wf_step_size",
                        )
                    )
                with wf_subcol5:
                    ml_wf_max_splits = int(
                        st.number_input(
                            "wf max splits",
                            min_value=1,
                            max_value=20,
                            value=_session_state_int(
                                "pipeline_ml_wf_max_splits",
                                DEFAULT_ML_WF_MAX_SPLITS,
                            ),
                            step=1,
                            key="pipeline_ml_wf_max_splits",
                        )
                    )
            else:
                ml_wf_min_train_size = int(st.session_state.get("pipeline_ml_wf_min_train_size", DEFAULT_ML_WF_MIN_TRAIN_SIZE))
                ml_wf_val_size = int(st.session_state.get("pipeline_ml_wf_val_size", DEFAULT_ML_WF_VAL_SIZE))
                ml_wf_test_size = int(st.session_state.get("pipeline_ml_wf_test_size", DEFAULT_ML_WF_TEST_SIZE))
                ml_wf_step_size = int(st.session_state.get("pipeline_ml_wf_step_size", DEFAULT_ML_WF_STEP_SIZE))
                ml_wf_max_splits = int(st.session_state.get("pipeline_ml_wf_max_splits", DEFAULT_ML_WF_MAX_SPLITS))

        with st.expander("ML — Hyperparams & seuils d'optimisation (avancé)", expanded=False):
            ml_hp_col1, ml_hp_col2, ml_hp_col3 = st.columns(3)
            with ml_hp_col1:
                ml_max_workers = int(
                    st.number_input(
                        "ML — max workers",
                        min_value=1,
                        max_value=32,
                        value=_session_state_int(
                            "pipeline_ml_max_workers",
                            DEFAULT_ML_MAX_WORKERS,
                        ),
                        step=1,
                        key="pipeline_ml_max_workers",
                    )
                )
                ml_max_epochs = int(
                    st.number_input(
                        "ML — max epochs (LSTM)",
                        min_value=5,
                        max_value=500,
                        value=_session_state_int(
                            "pipeline_ml_max_epochs",
                            DEFAULT_ML_MAX_EPOCHS,
                        ),
                        step=5,
                        key="pipeline_ml_max_epochs",
                    )
                )
                ml_feature_set = cast(
                    str,
                    st.selectbox(
                        "ML — feature set",
                        options=["v1", "expert"],
                        index=["v1", "expert"].index(
                            cast(str, st.session_state.get("pipeline_ml_feature_set", DEFAULT_ML_FEATURE_SET))
                            if st.session_state.get("pipeline_ml_feature_set", DEFAULT_ML_FEATURE_SET) in {"v1", "expert"}
                            else DEFAULT_ML_FEATURE_SET
                        ),
                        key="pipeline_ml_feature_set",
                    ),
                )
            with ml_hp_col2:
                ml_min_action_rate = float(
                    st.number_input(
                        "ML — taux d'action min",
                        min_value=0.0,
                        max_value=1.0,
                        value=_session_state_float(
                            "pipeline_ml_min_action_rate",
                            DEFAULT_ML_MIN_ACTION_RATE,
                        ),
                        step=0.01,
                        format="%.3f",
                        key="pipeline_ml_min_action_rate",
                    )
                )
                ml_max_action_rate = float(
                    st.number_input(
                        "ML — taux d'action max",
                        min_value=0.0,
                        max_value=1.0,
                        value=_session_state_float(
                            "pipeline_ml_max_action_rate",
                            DEFAULT_ML_MAX_ACTION_RATE,
                        ),
                        step=0.05,
                        format="%.3f",
                        key="pipeline_ml_max_action_rate",
                    )
                )
                ml_min_precision_long = float(
                    st.number_input(
                        "ML — précision min (long)",
                        min_value=0.0,
                        max_value=1.0,
                        value=_session_state_float(
                            "pipeline_ml_min_precision_long",
                            DEFAULT_ML_MIN_PRECISION_LONG,
                        ),
                        step=0.01,
                        format="%.3f",
                        key="pipeline_ml_min_precision_long",
                    )
                )
            with ml_hp_col3:
                ml_log_level = cast(
                    str,
                    st.selectbox(
                        "ML — niveau de log",
                        options=["DEBUG", "INFO", "WARNING", "ERROR"],
                        index=["DEBUG", "INFO", "WARNING", "ERROR"].index(
                            cast(str, st.session_state.get("pipeline_ml_log_level", DEFAULT_ML_LOG_LEVEL)).upper()
                            if str(st.session_state.get("pipeline_ml_log_level", DEFAULT_ML_LOG_LEVEL)).upper() in {"DEBUG", "INFO", "WARNING", "ERROR"}
                            else DEFAULT_ML_LOG_LEVEL
                        ),
                        key="pipeline_ml_log_level",
                    ),
                )
                ml_debug_train = st.checkbox(
                    "ML — mode debug train",
                    value=_session_state_bool("pipeline_ml_debug_train", DEFAULT_ML_DEBUG_TRAIN),
                    key="pipeline_ml_debug_train",
                    help="Active des logs ML plus détaillés et force un ordonnancement plus déterministe côté orchestrateur.",
                )
                ml_heartbeat_interval_seconds = float(
                    st.number_input(
                        "ML — heartbeat interval (s)",
                        min_value=5.0,
                        max_value=3600.0,
                        value=_session_state_float(
                            "pipeline_ml_heartbeat_interval_seconds",
                            DEFAULT_ML_HEARTBEAT_INTERVAL_SECONDS,
                        ),
                        step=5.0,
                        format="%.0f",
                        key="pipeline_ml_heartbeat_interval_seconds",
                        help="Heartbeat structuré consommé par l'IHM pour distinguer un run vivant mais silencieux d'un run figé. Ce n'est pas le timeout.",
                    )
                )
                ml_watchdog_timeout_seconds = int(
                    st.number_input(
                        "ML — watchdog timeout (s)",
                        min_value=0,
                        max_value=86400,
                        value=_session_state_int(
                            "pipeline_ml_watchdog_timeout_seconds",
                            DEFAULT_ML_WATCHDOG_TIMEOUT_SECONDS,
                        ),
                        step=30,
                        key="pipeline_ml_watchdog_timeout_seconds",
                        help="0 = surveillance seule. >0 = timeout si le dernier heartbeat structuré devient trop ancien. Ex. 300 = 5 min depuis le dernier heartbeat frais.",
                    )
                )

        # ──────────────────────────────────────────────────────────────────
        # ML — Hyperparams avancés (architecture, boosters, grilles candidate)
        # cf. audit_ihm_pipeline_options.md — alignement complet CLI modelFactory
        # ──────────────────────────────────────────────────────────────────
        with st.expander("ML — Hyperparams avancés (architecture, boosters, grilles)", expanded=False):
            st.caption(
                "Expose les paramètres `--sequence-length / --batch-size / --hidden-size`, "
                "`--artifacts-dir / --benchmark-symbol`, hyperparams LightGBM & CatBoost et les grilles "
                "`--candidate-*` consommées par `--optimize-target` / `--optimize-thresholds`."
            )
            ml_arch_col1, ml_arch_col2, ml_arch_col3 = st.columns(3)
            with ml_arch_col1:
                ml_sequence_length = int(
                    st.number_input(
                        "LSTM — sequence length",
                        min_value=5,
                        max_value=400,
                        value=_session_state_int(
                            "pipeline_ml_sequence_length",
                            DEFAULT_ML_SEQUENCE_LENGTH,
                        ),
                        step=5,
                        key="pipeline_ml_sequence_length",
                        help="Longueur de la fenêtre LSTM en jours. Défaut backend : 60.",
                    )
                )
                ml_batch_size = int(
                    st.number_input(
                        "LSTM — batch size",
                        min_value=4,
                        max_value=4096,
                        value=_session_state_int(
                            "pipeline_ml_batch_size",
                            DEFAULT_ML_BATCH_SIZE,
                        ),
                        step=8,
                        key="pipeline_ml_batch_size",
                    )
                )
                ml_hidden_size = int(
                    st.number_input(
                        "LSTM — hidden size",
                        min_value=8,
                        max_value=1024,
                        value=_session_state_int(
                            "pipeline_ml_hidden_size",
                            DEFAULT_ML_HIDDEN_SIZE,
                        ),
                        step=8,
                        key="pipeline_ml_hidden_size",
                    )
                )
            with ml_arch_col2:
                ml_artifacts_dir = cast(
                    str,
                    st.text_input(
                        "Répertoire d'artefacts ML",
                        value=str(st.session_state.get("pipeline_ml_artifacts_dir", DEFAULT_ML_ARTIFACTS_DIR)),
                        key="pipeline_ml_artifacts_dir",
                        help="Racine partagée entre `ml_train` et `ml_predict` : laissez `artifacts/models`. Chaque campagne est créée sous cette racine et se choisit séparément pour la prédiction.",
                    ),
                )
                ml_benchmark_symbol = cast(
                    str,
                    st.text_input(
                        "Symbole benchmark",
                        value=str(st.session_state.get("pipeline_ml_benchmark_symbol", DEFAULT_ML_BENCHMARK_SYMBOL)),
                        key="pipeline_ml_benchmark_symbol",
                        help="Utilisé pour les features relatives. Défaut : SPY.",
                    ),
                )
                ml_default_champion = cast(
                    str,
                    st.selectbox(
                        "Champion par défaut",
                        options=["lstm_attention", "lightgbm", "catboost", "global_model"],
                        index=["lstm_attention", "lightgbm", "catboost", "global_model"].index(
                            cast(str, st.session_state.get("pipeline_ml_default_champion", DEFAULT_ML_DEFAULT_CHAMPION))
                            if st.session_state.get("pipeline_ml_default_champion", DEFAULT_ML_DEFAULT_CHAMPION) in {"lstm_attention", "lightgbm", "catboost", "global_model"}
                            else DEFAULT_ML_DEFAULT_CHAMPION
                        ),
                        key="pipeline_ml_default_champion",
                        help="Modèle servi quand la sélection champion est désactivée ou ambiguë.",
                    ),
                )
                ml_cross_sectional_min_universe = int(
                    st.number_input(
                        "Cross-sectional — taille mini univers/date",
                        min_value=2,
                        max_value=500,
                        value=_session_state_int(
                            "pipeline_ml_cross_sectional_min_universe",
                            DEFAULT_ML_CROSS_SECTIONAL_MIN_UNIVERSE,
                        ),
                        step=1,
                        key="pipeline_ml_cross_sectional_min_universe",
                    )
                )
            with ml_arch_col3:
                ml_calibration_min_samples = int(
                    st.number_input(
                        "Calibration — min samples",
                        min_value=8,
                        max_value=10_000,
                        value=_session_state_int(
                            "pipeline_ml_calibration_min_samples",
                            DEFAULT_ML_CALIBRATION_MIN_SAMPLES,
                        ),
                        step=8,
                        key="pipeline_ml_calibration_min_samples",
                    )
                )
                ml_calibration_max_iter = int(
                    st.number_input(
                        "Calibration — max iter",
                        min_value=10,
                        max_value=10_000,
                        value=_session_state_int(
                            "pipeline_ml_calibration_max_iter",
                            DEFAULT_ML_CALIBRATION_MAX_ITER,
                        ),
                        step=10,
                        key="pipeline_ml_calibration_max_iter",
                    )
                )

            st.markdown("##### LightGBM (challenger local)")
            lgbm_col1, lgbm_col2, lgbm_col3 = st.columns(3)
            with lgbm_col1:
                ml_lgbm_max_depth = int(
                    st.number_input(
                        "LightGBM — max depth",
                        min_value=1,
                        max_value=32,
                        value=_session_state_int(
                            "pipeline_ml_lgbm_max_depth",
                            DEFAULT_ML_LGBM_MAX_DEPTH,
                        ),
                        step=1,
                        key="pipeline_ml_lgbm_max_depth",
                    )
                )
            with lgbm_col2:
                ml_lgbm_n_estimators = int(
                    st.number_input(
                        "LightGBM — n estimators",
                        min_value=10,
                        max_value=5000,
                        value=_session_state_int(
                            "pipeline_ml_lgbm_n_estimators",
                            DEFAULT_ML_LGBM_N_ESTIMATORS,
                        ),
                        step=10,
                        key="pipeline_ml_lgbm_n_estimators",
                    )
                )
            with lgbm_col3:
                ml_lgbm_learning_rate = float(
                    st.number_input(
                        "LightGBM — learning rate",
                        min_value=0.001,
                        max_value=1.0,
                        value=_session_state_float(
                            "pipeline_ml_lgbm_learning_rate",
                            DEFAULT_ML_LGBM_LEARNING_RATE,
                        ),
                        step=0.005,
                        format="%.4f",
                        key="pipeline_ml_lgbm_learning_rate",
                    )
                )

            st.markdown("##### CatBoost (challenger local)")
            cat_col1, cat_col2, cat_col3 = st.columns(3)
            with cat_col1:
                ml_catboost_depth = int(
                    st.number_input(
                        "CatBoost — depth",
                        min_value=1,
                        max_value=16,
                        value=_session_state_int(
                            "pipeline_ml_catboost_depth",
                            DEFAULT_ML_CATBOOST_DEPTH,
                        ),
                        step=1,
                        key="pipeline_ml_catboost_depth",
                    )
                )
            with cat_col2:
                ml_catboost_iterations = int(
                    st.number_input(
                        "CatBoost — iterations",
                        min_value=10,
                        max_value=5000,
                        value=_session_state_int(
                            "pipeline_ml_catboost_iterations",
                            DEFAULT_ML_CATBOOST_ITERATIONS,
                        ),
                        step=10,
                        key="pipeline_ml_catboost_iterations",
                    )
                )
            with cat_col3:
                ml_catboost_learning_rate = float(
                    st.number_input(
                        "CatBoost — learning rate",
                        min_value=0.001,
                        max_value=1.0,
                        value=_session_state_float(
                            "pipeline_ml_catboost_learning_rate",
                            DEFAULT_ML_CATBOOST_LEARNING_RATE,
                        ),
                        step=0.005,
                        format="%.4f",
                        key="pipeline_ml_catboost_learning_rate",
                    )
                )

            st.markdown("##### Grilles candidate (utilisées si `--optimize-target` / `--optimize-thresholds`)")
            st.caption(
                "Défauts swing 2-10 j : horizons {3,5,7,10}, up {1.5%, 2%, 3%}, down {-1%, -1.5%}, "
                "decision {0.55, 0.60, 0.65}."
            )
            grid_col1, grid_col2 = st.columns(2)
            with grid_col1:
                ml_candidate_horizons_selection = cast(
                    list[int],
                    st.multiselect(
                        "candidate-horizons (jours)",
                        options=[2, 3, 4, 5, 6, 7, 10, 12, 15],
                        default=list(st.session_state.get("pipeline_ml_candidate_horizons", list(DEFAULT_ML_CANDIDATE_HORIZONS))),
                        key="pipeline_ml_candidate_horizons",
                    ),
                )
                ml_candidate_decision_thresholds_selection = cast(
                    list[float],
                    st.multiselect(
                        "candidate-decision-thresholds",
                        options=[0.50, 0.52, 0.55, 0.58, 0.60, 0.62, 0.65, 0.70],
                        default=list(st.session_state.get("pipeline_ml_candidate_decision_thresholds", list(DEFAULT_ML_CANDIDATE_DECISION_THRESHOLDS))),
                        key="pipeline_ml_candidate_decision_thresholds",
                    ),
                )
                ml_min_trades_fraction = float(
                    st.number_input(
                        "min-trades-fraction (optimize-target)",
                        min_value=0.0,
                        max_value=1.0,
                        value=_session_state_float(
                            "pipeline_ml_min_trades_fraction",
                            DEFAULT_ML_MIN_TRADES_FRACTION,
                        ),
                        step=0.01,
                        format="%.3f",
                        key="pipeline_ml_min_trades_fraction",
                    )
                )
            with grid_col2:
                ml_candidate_up_thresholds_selection = cast(
                    list[float],
                    st.multiselect(
                        "candidate-up-thresholds",
                        options=[0.005, 0.01, 0.015, 0.02, 0.025, 0.03, 0.04, 0.05],
                        default=list(st.session_state.get("pipeline_ml_candidate_up_thresholds", list(DEFAULT_ML_CANDIDATE_UP_THRESHOLDS))),
                        key="pipeline_ml_candidate_up_thresholds",
                    ),
                )
                ml_candidate_down_thresholds_selection = cast(
                    list[float],
                    st.multiselect(
                        "candidate-down-thresholds",
                        options=[-0.005, -0.01, -0.015, -0.02, -0.03],
                        default=list(st.session_state.get("pipeline_ml_candidate_down_thresholds", list(DEFAULT_ML_CANDIDATE_DOWN_THRESHOLDS))),
                        key="pipeline_ml_candidate_down_thresholds",
                    ),
                )

        # === BLOCK 4/8 : Event Sentiment (extrait — _render_event_sentiment_block) ===
        _sentiment_vars = _render_event_sentiment_block()
        sentiment_start_utc = _sentiment_vars["sentiment_start_utc"]
        sentiment_end_utc = _sentiment_vars["sentiment_end_utc"]
        sentiment_symbols = _sentiment_vars["sentiment_symbols"]
        sentiment_news_provider = _sentiment_vars["sentiment_news_provider"]
        sentiment_ticker_relevance_mode = _sentiment_vars["sentiment_ticker_relevance_mode"]
        sentiment_min_relevance_score = _sentiment_vars["sentiment_min_relevance_score"]
        sentiment_scoring_mode = _sentiment_vars["sentiment_scoring_mode"]
        sentiment_enable_contextual_scoring = _sentiment_vars["sentiment_enable_contextual_scoring"]
        sentiment_contextual_min_relevance = _sentiment_vars["sentiment_contextual_min_relevance"]
        sentiment_contextual_max_pairs = _sentiment_vars["sentiment_contextual_max_pairs"]
        sentiment_pending_limit = _sentiment_vars["sentiment_pending_limit"]
        sentiment_pending_max_batches_per_run = _sentiment_vars[
            "sentiment_pending_max_batches_per_run"
        ]
        sentiment_feature_flush_every_n_batches = _sentiment_vars[
            "sentiment_feature_flush_every_n_batches"
        ]
        sentiment_finbert_batch_size = _sentiment_vars["sentiment_finbert_batch_size"]
        backfill_relevance_dry_run = _sentiment_vars["backfill_relevance_dry_run"]
        backfill_relevance_rescore_all = _sentiment_vars["backfill_relevance_rescore_all"]
        backfill_relevance_batch_size = _sentiment_vars["backfill_relevance_batch_size"]
        backfill_relevance_purge_below = _sentiment_vars["backfill_relevance_purge_below"]

        # === BLOCK 6/9 : Signal Aggregator (extrait — _render_signal_aggregator_block) ===
        _signal_agg_vars = _render_signal_aggregator_block()
        signal_aggregator_all_symbols = _signal_agg_vars["signal_aggregator_all_symbols"]
        signal_aggregator_log_level = _signal_agg_vars["signal_aggregator_log_level"]
        signal_aggregator_sentiment_weight = _signal_agg_vars["signal_aggregator_sentiment_weight"]
        signal_aggregator_macro_weight = _signal_agg_vars["signal_aggregator_macro_weight"]
        signal_aggregator_lookback_days = _signal_agg_vars["signal_aggregator_lookback_days"]
        signal_aggregator_min_news_count = _signal_agg_vars["signal_aggregator_min_news_count"]
        signal_aggregator_time_decay_half_life_days = _signal_agg_vars["signal_aggregator_time_decay_half_life_days"]

        # === BLOCK 7/9 : Screener (extrait — _render_screener_block) ===
        _screener_vars = _render_screener_block()
        screener_chunk_size = _screener_vars["screener_chunk_size"]
        screener_max_workers = _screener_vars["screener_max_workers"]
        screener_benchmark_symbol = _screener_vars["screener_benchmark_symbol"]
        screener_liquidity_threshold_usd = _screener_vars["screener_liquidity_threshold_usd"]
        screener_min_relative_strength_index = _screener_vars["screener_min_relative_strength_index"]
        screener_enable_two_pass_loading = _screener_vars["screener_enable_two_pass_loading"]
        screener_historical_range_lookback_days = _screener_vars["screener_historical_range_lookback_days"]
        screener_min_historical_range_score = _screener_vars["screener_min_historical_range_score"]
        screener_first_pass_window_days = _screener_vars["screener_first_pass_window_days"]

        # === BLOCK 8/9 : Data Integrity (extrait — _render_data_integrity_block) ===
        _di_vars = _render_data_integrity_block()
        data_integrity_quotes_limit = _di_vars["data_integrity_quotes_limit"]
        data_integrity_quotes_batch_size = _di_vars["data_integrity_quotes_batch_size"]
        data_integrity_earnings_limit = _di_vars["data_integrity_earnings_limit"]
        data_integrity_earnings_batch_size = _di_vars["data_integrity_earnings_batch_size"]
        data_integrity_earnings_sleep_seconds = _di_vars["data_integrity_earnings_sleep_seconds"]
        data_integrity_earnings_log_every = _di_vars["data_integrity_earnings_log_every"]
        data_integrity_fundamentals_limit = _di_vars["data_integrity_fundamentals_limit"]
        data_integrity_fundamentals_provider = _di_vars["data_integrity_fundamentals_provider"]
        data_integrity_fundamentals_overwrite_existing = _di_vars["data_integrity_fundamentals_overwrite_existing"]
        data_integrity_fundamentals_sleep_seconds = _di_vars["data_integrity_fundamentals_sleep_seconds"]
        eodhd_write_commit_every_symbols = _di_vars["eodhd_write_commit_every_symbols"]
        eodhd_enable_stooq_cross_check = _di_vars["eodhd_enable_stooq_cross_check"]
        data_integrity_fundamentals_log_every = _di_vars["data_integrity_fundamentals_log_every"]
        data_integrity_earnings_resume = _di_vars["data_integrity_earnings_resume"]
        effective_earnings_from_date = _di_vars["effective_earnings_from_date"]
        effective_earnings_to_date = _di_vars["effective_earnings_to_date"]

        # === BLOCK 8b/9 : Corporate Actions + Backfill EODHD historique (extrait — _render_corporate_actions_block) ===
        _ca_vars = _render_corporate_actions_block(trade_date or "")
        corporate_actions_skip_existing = _ca_vars["corporate_actions_skip_existing"]
        corporate_actions_batch_size = _ca_vars["corporate_actions_batch_size"]
        ca_use_custom_window = _ca_vars["ca_use_custom_window"]
        ca_start_date_value = _ca_vars["ca_start_date_value"]
        ca_end_date_value = _ca_vars["ca_end_date_value"]
        eodhd_backfill_years = _ca_vars["eodhd_backfill_years"]
        eodhd_backfill_resume = _ca_vars["eodhd_backfill_resume"]
        eodhd_backfill_symbols = _ca_vars["eodhd_backfill_symbols"]
        eodhd_backfill_write = _ca_vars["eodhd_backfill_write"]


    return (
        PipelineLaunchOptions(
            account_id=selected_account_id,
            trade_date=trade_date,
            force_trade_date_to_latest_snapshot=bool(force_trade_date_to_latest_snapshot),
            risk_account_equity=float(cast(float, risk_account_equity)),
            execution_mode=cast(Any, execution_mode),
            execution_run_id=execution_run_id,
            execution_live_approval_token=execution_live_approval_token,
            execution_run_plan_file=execution_run_plan_file,
            allow_fractional_shares=bool(allow_fractional_shares),
            allow_outside_rth=bool(allow_outside_rth),
            auto_rebalance=bool(auto_rebalance),
            execution_account_type=cast(Any, execution_account_type),
            execution_swing_only=bool(execution_swing_only),
            execution_submission_window=cast(Any, execution_submission_window),
            execution_take_profit_pct=float(execution_take_profit_pct),
            execution_trailing_stop_pct=float(execution_trailing_stop_pct),
            execution_max_entry_gap_pct=float(execution_max_entry_gap_pct),
            execution_manual_buy_stop_loss_pct=float(execution_manual_buy_stop_loss_pct),
            execution_trailing_trigger=cast(Any, execution_trailing_trigger),
            execution_trailing_r_multiple=float(execution_trailing_r_multiple),
            execution_trailing_profit_pct=float(execution_trailing_profit_pct),
            execution_protection_transition_timeout_seconds=int(execution_protection_transition_timeout_seconds),
            execution_protection_transition_poll_interval_seconds=float(execution_protection_transition_poll_interval_seconds),
            execution_debug=bool(execution_debug),
            ml_accelerator=cast(Any, ml_accelerator),
            ml_include_sentiment=bool(ml_include_sentiment),
            ml_include_screener_scores=bool(ml_include_screener_scores),
            ml_include_short_score=bool(ml_include_short_score),
            ml_include_macro_vix=bool(ml_include_macro_vix),
            ml_include_macro_vxn=bool(ml_include_macro_vxn),
            ml_include_macro_vix3m=bool(ml_include_macro_vix3m),
            ml_include_macro_move=bool(ml_include_macro_move),
            # ML challengers & advanced (widgets IHM câblés)
            ml_enable_lightgbm=bool(ml_enable_lightgbm),
            ml_enable_catboost=bool(ml_enable_catboost),
            ml_enable_global_model=bool(ml_enable_global_model),
            ml_enable_global_stacking=bool(ml_enable_global_stacking),
            ml_enable_global_challenger=bool(ml_enable_global_challenger),
            ml_global_model_name=cast(Any, ml_global_model_name),
            ml_enable_cross_sectional=bool(ml_enable_cross_sectional),
            ml_select_champion=bool(ml_select_champion),
            ml_optimize_thresholds=bool(ml_optimize_thresholds),
            ml_optimize_target=bool(ml_optimize_target),
            ml_target_mode=cast(Any, ml_target_mode),
            ml_forecast_horizon=int(ml_forecast_horizon),
            ml_target_up_threshold=float(ml_target_up_threshold),
            ml_target_down_threshold=float(ml_target_down_threshold),
            ml_ternary_weight_short=float(ml_ternary_weight_short),
            ml_ternary_weight_flat=float(ml_ternary_weight_flat),
            ml_ternary_weight_long=float(ml_ternary_weight_long),
            ml_ternary_threshold_short=float(ml_ternary_threshold_short),
            ml_ternary_threshold_long=float(ml_ternary_threshold_long),
            ml_ternary_top2_margin=float(ml_ternary_top2_margin),
            ml_decision_threshold=float(ml_decision_threshold),
            ml_calibration_method=cast(Any, ml_calibration_method),
            ml_feature_set=cast(Any, ml_feature_set),
            ml_max_workers=int(ml_max_workers),
            ml_max_epochs=int(ml_max_epochs),
            ml_walkforward=bool(ml_walkforward),
            ml_wf_min_train_size=int(ml_wf_min_train_size),
            ml_wf_val_size=int(ml_wf_val_size),
            ml_wf_test_size=int(ml_wf_test_size),
            ml_wf_step_size=int(ml_wf_step_size),
            ml_wf_max_splits=int(ml_wf_max_splits),
            ml_log_level=str(ml_log_level).upper(),
            ml_debug_train=bool(ml_debug_train),
            ml_heartbeat_interval_seconds=float(ml_heartbeat_interval_seconds),
            ml_watchdog_timeout_seconds=int(ml_watchdog_timeout_seconds),
            ml_min_action_rate=float(ml_min_action_rate),
            ml_max_action_rate=float(ml_max_action_rate),
            ml_min_precision_long=float(ml_min_precision_long),
            ml_sequence_length=int(ml_sequence_length),
            ml_batch_size=int(ml_batch_size),
            ml_hidden_size=int(ml_hidden_size),
            ml_training_start_date=ml_training_start_date.isoformat(),
            ml_training_end_date=ml_training_end_date.isoformat(),
            ml_train_symbol_source=cast(Any, ml_train_symbol_source),
            ml_predict_symbol_source=cast(Any, ml_predict_symbol_source),
            ml_artifacts_dir=str(ml_artifacts_dir or DEFAULT_ML_ARTIFACTS_DIR).strip() or DEFAULT_ML_ARTIFACTS_DIR,
            ml_benchmark_symbol=str(ml_benchmark_symbol or DEFAULT_ML_BENCHMARK_SYMBOL).strip().upper() or DEFAULT_ML_BENCHMARK_SYMBOL,
            ml_default_champion=cast(Any, ml_default_champion),
            ml_cross_sectional_min_universe=int(ml_cross_sectional_min_universe),
            ml_calibration_min_samples=int(ml_calibration_min_samples),
            ml_calibration_max_iter=int(ml_calibration_max_iter),
            ml_lgbm_max_depth=int(ml_lgbm_max_depth),
            ml_lgbm_n_estimators=int(ml_lgbm_n_estimators),
            ml_lgbm_learning_rate=float(ml_lgbm_learning_rate),
            ml_catboost_depth=int(ml_catboost_depth),
            ml_catboost_iterations=int(ml_catboost_iterations),
            ml_catboost_learning_rate=float(ml_catboost_learning_rate),
            ml_candidate_horizons=tuple(sorted({int(v) for v in ml_candidate_horizons_selection})) or DEFAULT_ML_CANDIDATE_HORIZONS,
            ml_candidate_up_thresholds=tuple(sorted({float(v) for v in ml_candidate_up_thresholds_selection})) or DEFAULT_ML_CANDIDATE_UP_THRESHOLDS,
            ml_candidate_down_thresholds=tuple(sorted({float(v) for v in ml_candidate_down_thresholds_selection})) or DEFAULT_ML_CANDIDATE_DOWN_THRESHOLDS,
            ml_candidate_decision_thresholds=tuple(sorted({float(v) for v in ml_candidate_decision_thresholds_selection})) or DEFAULT_ML_CANDIDATE_DECISION_THRESHOLDS,
            ml_min_trades_fraction=float(ml_min_trades_fraction),
            risk_per_trade_pct=float(risk_per_trade_pct),
            risk_max_positions=int(risk_max_positions),
            risk_max_position_weight=float(risk_max_position_weight),
            risk_max_sector_weight=float(risk_max_sector_weight),
            risk_min_position_notional=float(risk_min_position_notional),
            risk_score_weight=float(risk_score_weight),
            risk_prediction_weight=float(risk_prediction_weight),
            risk_correlation_threshold=float(risk_correlation_threshold),
            risk_correlation_lookback_days=int(risk_correlation_lookback_days),
            risk_correlation_min_overlap=int(risk_correlation_min_overlap),
            risk_enable_kelly=bool(risk_enable_kelly),
            risk_max_portfolio_drawdown_pct=float(risk_max_portfolio_drawdown_pct),
            risk_max_daily_loss_pct=float(risk_max_daily_loss_pct),
            risk_target_annual_vol=float(risk_target_annual_vol),
            risk_vol_target_lookback_days=int(risk_vol_target_lookback_days),
            risk_min_ml_coverage_ratio=float(risk_min_ml_coverage_ratio),
            risk_payoff_ratio=float(risk_payoff_ratio),
            risk_kelly_fraction_multiplier=float(risk_kelly_fraction_multiplier),
            risk_dry_run=bool(risk_dry_run),
            risk_log_level=str(risk_log_level).upper(),
            sentiment_start_utc=sentiment_start_utc or None,
            sentiment_end_utc=sentiment_end_utc or None,
            sentiment_symbols=sentiment_symbols or None,
            sentiment_news_provider=cast(Any, sentiment_news_provider or "eodhd"),
            sentiment_ticker_relevance_mode=cast(Any, sentiment_ticker_relevance_mode or "provider_default"),
            sentiment_min_relevance_score=float(sentiment_min_relevance_score) if sentiment_min_relevance_score else None,
            sentiment_scoring_mode=cast(Any, sentiment_scoring_mode or "standard_only"),
            sentiment_enable_contextual_scoring=bool(sentiment_enable_contextual_scoring),
            sentiment_contextual_min_relevance=(
                float(sentiment_contextual_min_relevance)
                if sentiment_contextual_min_relevance is not None
                else None
            ),
            sentiment_contextual_max_pairs=(
                int(sentiment_contextual_max_pairs)
                if sentiment_contextual_max_pairs
                else None
            ),
            sentiment_pending_limit=(
                int(sentiment_pending_limit)
                if sentiment_pending_limit
                else None
            ),
            sentiment_pending_max_batches_per_run=(
                int(sentiment_pending_max_batches_per_run)
                if sentiment_pending_max_batches_per_run is not None
                else None
            ),
            sentiment_feature_flush_every_n_batches=(
                int(sentiment_feature_flush_every_n_batches)
                if sentiment_feature_flush_every_n_batches is not None
                else None
            ),
            sentiment_finbert_batch_size=(
                int(sentiment_finbert_batch_size)
                if sentiment_finbert_batch_size
                else None
            ),
            backfill_relevance_dry_run=bool(backfill_relevance_dry_run),
            backfill_relevance_rescore_all=bool(backfill_relevance_rescore_all),
            backfill_relevance_batch_size=int(backfill_relevance_batch_size or 500),
            backfill_relevance_purge_below=(
                float(backfill_relevance_purge_below)
                if backfill_relevance_purge_below
                else None
            ),
            backfill_relevance_contextual_min_relevance=(
                float(sentiment_contextual_min_relevance)
                if sentiment_contextual_min_relevance is not None
                else 0.0
            ),
            backfill_relevance_contextual_max_pairs=(
                int(sentiment_contextual_max_pairs)
                if sentiment_contextual_max_pairs
                else None
            ),
            signal_aggregator_all_symbols=bool(signal_aggregator_all_symbols),
            signal_aggregator_sentiment_weight=float(signal_aggregator_sentiment_weight),
            signal_aggregator_macro_weight=float(signal_aggregator_macro_weight),
            signal_aggregator_lookback_days=int(signal_aggregator_lookback_days),
            signal_aggregator_min_news_count=int(signal_aggregator_min_news_count),
            signal_aggregator_time_decay_half_life_days=float(signal_aggregator_time_decay_half_life_days),
            signal_aggregator_log_level=str(signal_aggregator_log_level).upper(),
            screener_chunk_size=int(screener_chunk_size),
            screener_max_workers=_to_optional_positive_int(screener_max_workers),
            screener_benchmark_symbol=screener_benchmark_symbol or DEFAULT_SCREENER_BENCHMARK_SYMBOL,
            screener_liquidity_threshold_usd=float(screener_liquidity_threshold_usd),
            screener_min_relative_strength_index=float(screener_min_relative_strength_index),
            screener_historical_range_lookback_days=int(screener_historical_range_lookback_days),
            screener_min_historical_range_score=float(screener_min_historical_range_score),
            screener_first_pass_window_days=int(screener_first_pass_window_days),
            screener_enable_two_pass_loading=bool(screener_enable_two_pass_loading),
            data_integrity_quotes_limit=_to_optional_positive_int(data_integrity_quotes_limit),
            data_integrity_quotes_batch_size=int(data_integrity_quotes_batch_size),
            data_integrity_earnings_from_date=effective_earnings_from_date,
            data_integrity_earnings_to_date=effective_earnings_to_date,
            data_integrity_earnings_limit=_to_optional_positive_int(data_integrity_earnings_limit),
            data_integrity_earnings_sleep_seconds=float(data_integrity_earnings_sleep_seconds),
            data_integrity_earnings_log_every=int(data_integrity_earnings_log_every),
            data_integrity_earnings_batch_size=int(data_integrity_earnings_batch_size),
            data_integrity_earnings_resume=bool(data_integrity_earnings_resume),
            data_integrity_fundamentals_limit=_to_optional_positive_int(data_integrity_fundamentals_limit),
            data_integrity_fundamentals_provider=cast(Any, data_integrity_fundamentals_provider or "yahoo_finance"),
            data_integrity_fundamentals_overwrite_existing=bool(data_integrity_fundamentals_overwrite_existing),
            data_integrity_fundamentals_sleep_seconds=float(data_integrity_fundamentals_sleep_seconds),
            data_integrity_fundamentals_log_every=int(data_integrity_fundamentals_log_every),
            eodhd_write_commit_every_symbols=int(eodhd_write_commit_every_symbols),
            eodhd_enable_stooq_cross_check=bool(eodhd_enable_stooq_cross_check),
            corporate_actions_skip_existing=bool(corporate_actions_skip_existing),
            corporate_actions_use_custom_window=bool(ca_use_custom_window),
            corporate_actions_start_date=ca_start_date_value,
            corporate_actions_end_date=ca_end_date_value,
            corporate_actions_batch_size=int(corporate_actions_batch_size),
            eodhd_backfill_years=int(eodhd_backfill_years),
            eodhd_backfill_symbols=eodhd_backfill_symbols or None,
            eodhd_backfill_resume=bool(eodhd_backfill_resume),
            eodhd_backfill_write=bool(eodhd_backfill_write),
        ),
        live_confirmed,
    )
