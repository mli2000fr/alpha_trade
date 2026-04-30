"""ihm/pages/_execution_center.py — Phase 6.2 (Backlog L10).

Préfill exécution (compte/PDT/swing) + ``_build_launch_options`` (tous les
panneaux de paramètres pipeline : execution, risk, ML, screener, selector,
signal aggregator, corporate actions, data integrity).

Extrait de ``pipeline.py``. Le bloc ``_build_launch_options`` reste massif
(~1760 lignes) ; un découpage plus fin par sous-bloc est laissé en TODO 2e
passe (cf. backlog L10 — Further Considerations).
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, cast

import streamlit as st

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
    PDT_EQUITY_THRESHOLD,
    PipelineExecutionDefaults,
    get_pipeline_execution_defaults,
)
from ihm.services.pipeline_runner import (
    DEFAULT_DATA_INTEGRITY_EARNINGS_BATCH_SIZE,
    DEFAULT_DATA_INTEGRITY_EARNINGS_LOG_EVERY,
    DEFAULT_DATA_INTEGRITY_EARNINGS_RESUME,
    DEFAULT_DATA_INTEGRITY_FUNDAMENTALS_LOG_EVERY,
    DEFAULT_DATA_INTEGRITY_PROVIDER_SLEEP_SECONDS,
    DEFAULT_DATA_INTEGRITY_QUOTES_BATCH_SIZE,
    DEFAULT_CA_SKIP_EXISTING,
    DEFAULT_CA_BATCH_SIZE,
    DEFAULT_CA_USE_CUSTOM_WINDOW,
    DEFAULT_CA_WINDOW_LOOKBACK_DAYS,
    DEFAULT_EXEC_DEBUG,
    DEFAULT_EXEC_PROTECTION_TRANSITION_POLL_INTERVAL_SECONDS,
    DEFAULT_EXEC_PROTECTION_TRANSITION_TIMEOUT_SECONDS,
    DEFAULT_EXEC_SUBMISSION_WINDOW,
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
    DEFAULT_ML_FEATURE_SET,
    DEFAULT_ML_FORECAST_HORIZON,
    DEFAULT_ML_HIDDEN_SIZE,
    DEFAULT_ML_LGBM_LEARNING_RATE,
    DEFAULT_ML_LGBM_MAX_DEPTH,
    DEFAULT_ML_LGBM_N_ESTIMATORS,
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
    DEFAULT_ML_WALKFORWARD,
    DEFAULT_ML_WF_MAX_SPLITS,
    DEFAULT_ML_WF_MIN_TRAIN_SIZE,
    DEFAULT_ML_WF_STEP_SIZE,
    DEFAULT_ML_WF_TEST_SIZE,
    DEFAULT_ML_WF_VAL_SIZE,
    DEFAULT_RISK_CORRELATION_LOOKBACK_DAYS,
    DEFAULT_RISK_CORRELATION_MIN_OVERLAP,
    DEFAULT_RISK_CORRELATION_THRESHOLD,
    DEFAULT_RISK_ENABLE_KELLY,
    DEFAULT_RISK_KELLY_FRACTION_MULTIPLIER,
    DEFAULT_RISK_LOG_LEVEL,
    DEFAULT_RISK_MAX_POSITION_WEIGHT,
    DEFAULT_RISK_MAX_POSITIONS,
    DEFAULT_RISK_MAX_SECTOR_WEIGHT,
    DEFAULT_RISK_PAYOFF_RATIO,
    DEFAULT_RISK_PER_TRADE_PCT,
    DEFAULT_RISK_PREDICTION_WEIGHT,
    DEFAULT_RISK_SCORE_WEIGHT,
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
    is_gpu_available,
)
from ihm.services.ml_artifacts import list_ml_artifact_symbols  # noqa: F401  # re-export legacy

__all__ = [
    "_apply_execution_prefills",
    "_build_execution_prefill_caption",
    "_build_launch_options",
]


def _apply_execution_prefills(selected_account_id: str | None) -> PipelineExecutionDefaults | None:
    cleaned_account_id = (selected_account_id or "").strip() or None
    if cleaned_account_id is None:
        return None

    try:
        defaults = get_pipeline_execution_defaults(cleaned_account_id)
    except Exception:
        st.session_state[EXECUTION_DEFAULTS_ACCOUNT_KEY] = cleaned_account_id
        return None

    if defaults is None:
        st.session_state[EXECUTION_DEFAULTS_ACCOUNT_KEY] = cleaned_account_id
        return None

    account_changed = st.session_state.get(EXECUTION_DEFAULTS_ACCOUNT_KEY) != cleaned_account_id
    if defaults.account_type in {"margin", "cash"} and (
        account_changed or "pipeline_execution_account_type" not in st.session_state
    ):
        st.session_state["pipeline_execution_account_type"] = defaults.account_type
    if defaults.pdt_rule in {"auto", "off"} and (
        account_changed or "pipeline_execution_pdt_rule" not in st.session_state
    ):
        st.session_state["pipeline_execution_pdt_rule"] = defaults.pdt_rule
    if defaults.swing_only is not None and (
        account_changed or "pipeline_execution_swing_only" not in st.session_state
    ):
        st.session_state["pipeline_execution_swing_only"] = defaults.swing_only

    st.session_state[EXECUTION_DEFAULTS_ACCOUNT_KEY] = cleaned_account_id
    return defaults


def _build_execution_prefill_caption(defaults: PipelineExecutionDefaults | None) -> str | None:
    if defaults is None:
        return None

    notes: list[str] = []
    if defaults.account_type:
        notes.append(f"type de compte prérempli via broker : `{defaults.account_type}`")
    if defaults.pdt_rule:
        notes.append(f"règle PDT préremplie : `{defaults.pdt_rule}`")
    if defaults.equity is not None:
        notes.append(f"equity broker ≈ `{defaults.equity:,.2f}` (seuil PDT `{PDT_EQUITY_THRESHOLD:,.0f}`)")
    notes.append("`swing only` reste manuel car ce choix ne se déduit pas fiablement du seul montant du compte")
    return " | ".join(notes)


def _build_launch_options() -> tuple[PipelineLaunchOptions, bool]:
    selected_account_id = cast(str | None, st.session_state.get("selected_account_id"))
    execution_defaults = _apply_execution_prefills(selected_account_id)

    with st.expander("⚙️ Paramètres d'exécution", expanded=False):
        st.caption(
            "Les pipelines sont lancés en arrière-plan depuis l'IHM. Ils héritent de la configuration DB active et, "
            "pour les étapes concernées, du compte Alpaca sélectionné dans la sidebar."
        )

        if selected_account_id:
            st.info(f"Compte Alpaca actuellement sélectionné : `{selected_account_id}`")
        else:
            st.info("Aucun compte Alpaca explicitement sélectionné — le compte par défaut sera utilisé si nécessaire.")

        col1, col2, col3 = st.columns(3)
        with col1:
            trade_date = st.text_input(
                "Trade date / as-of (YYYY-MM-DD)",
                key="pipeline_trade_date",
                help="Utilisé par Signal Aggregator, ML Predict, Risk, Execution et Corporate Actions Apply.",
            )
        with col2:
            risk_account_equity = st.number_input(
                "Equity pour le module Risk",
                min_value=0.0,
                value=float(st.session_state.get("pipeline_risk_account_equity", 100_000.0)),
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

        col4, col5, col6 = st.columns(3)
        with col4:
            execution_run_id = st.text_input(
                "Execution — risk_run_id optionnel",
                key="pipeline_execution_run_id",
                help="Laissez vide pour exécuter sur le dernier run disponible.",
            )
        with col5:
            allow_outside_rth = st.checkbox(
                "Execution hors RTH (file d'attente pour l'ouverture)",
                value=bool(st.session_state.get("pipeline_allow_outside_rth", False)),
                key="pipeline_allow_outside_rth",
                help="Soumet les ordres meme si le marche est ferme. En paper/live, ils restent en attente et seront traites a l'ouverture suivante.",
            )
        with col6:
            auto_rebalance = st.checkbox(
                "Auto rebalance",
                value=bool(st.session_state.get("pipeline_auto_rebalance", False)),
                key="pipeline_auto_rebalance",
            )

        exec_col1, exec_col2, exec_col3 = st.columns(3)
        st.warning(
            "⚠️ différence potentiellement forte entre margin et cash\n\n"
            "- `margin` utilise le buying power broker ; `cash` se limite au cash settled / non-marginable buying power.\n"
            "- À equity identique, cela peut changer fortement le nombre d'ordres soumis et la capacité de rebalancing.\n"
            "- Sur un compte `margin` < 25k, la logique PDT peut différer les sorties le jour même ; `swing only` force aussi ce comportement.\n"
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
            execution_pdt_rule = cast(
                str,
                st.selectbox(
                    "Execution — règle PDT",
                    options=["auto", "off"],
                    index=["auto", "off"].index(
                        cast(str, st.session_state.get("pipeline_execution_pdt_rule", "off"))
                        if st.session_state.get("pipeline_execution_pdt_rule", "off") in {"auto", "off"}
                        else "off"
                    ),
                    key="pipeline_execution_pdt_rule",
                    help="Défaut swing cash : `off` (cohérent avec compte cash). `auto` applique la règle PDT sur un compte margin < 25k.",
                ),
            )
        with exec_col3:
            execution_swing_only = st.checkbox(
                "Execution — swing only",
                value=bool(st.session_state.get("pipeline_execution_swing_only", True)),
                key="pipeline_execution_swing_only",
                help="Défaut swing : True. Si coché, le moteur diffère l'armement des sorties le jour même du fill.",
            )

        effective_execution_pdt_rule = "off" if execution_account_type == "cash" else execution_pdt_rule
        constraint_notes = [
            f"Type de compte : `{execution_account_type}`",
            f"Règle PDT effective : `{effective_execution_pdt_rule}`",
            f"Swing only : `{bool(execution_swing_only)}`",
        ]
        if execution_account_type == "cash":
            constraint_notes.append("En `cash`, le moteur se base sur le cash settled / non-marginable buying power.")
        else:
            constraint_notes.append("En `margin`, le moteur se base sur le buying power broker.")
        if effective_execution_pdt_rule == "auto":
            constraint_notes.append("Si l'equity broker est < 25k, le quota de day trades peut différer les exits le jour même.")
        if execution_swing_only:
            constraint_notes.append("Les children TP/TS sont différés le jour même du fill.")
        st.info(" | ".join(constraint_notes))

        # ──────────────────────────────────────────────────────────────────
        # Stratégie de protection (sortie) — P1 cf. audit_ihm_pipeline_options.md
        # ──────────────────────────────────────────────────────────────────
        st.markdown("#### Stratégie de protection — sortie (`run_execution.py`)")
        st.caption(
            "Pilote la fenêtre de soumission hors RTH et le déclencheur du trailing stop dynamique. "
            "Défauts swing : fenêtre `both` (post_close + pre_open), trigger `multiple_r` à 1.0R."
        )
        prot_col1, prot_col2, prot_col3 = st.columns(3)
        with prot_col1:
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
        with prot_col2:
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
        with prot_col3:
            if execution_trailing_trigger == "multiple_r":
                execution_trailing_r_multiple = float(
                    st.number_input(
                        "Multiple de R pour activation",
                        min_value=0.1,
                        value=float(st.session_state.get("pipeline_execution_trailing_r_multiple", DEFAULT_EXEC_TRAILING_R_MULTIPLE)),
                        step=0.1,
                        format="%.2f",
                        key="pipeline_execution_trailing_r_multiple",
                    )
                )
                execution_trailing_profit_pct = float(st.session_state.get("pipeline_execution_trailing_profit_pct", DEFAULT_EXEC_TRAILING_PROFIT_PCT))
            else:
                execution_trailing_profit_pct = float(
                    st.number_input(
                        "Profit % pour activation",
                        min_value=0.001,
                        value=float(st.session_state.get("pipeline_execution_trailing_profit_pct", DEFAULT_EXEC_TRAILING_PROFIT_PCT)),
                        step=0.005,
                        format="%.4f",
                        key="pipeline_execution_trailing_profit_pct",
                    )
                )
                execution_trailing_r_multiple = float(st.session_state.get("pipeline_execution_trailing_r_multiple", DEFAULT_EXEC_TRAILING_R_MULTIPLE))

        with st.expander("Execution — transition trigger avancé & debug", expanded=False):
            st.caption(
                "Pilote `--protection-transition-timeout-seconds` / `--protection-transition-poll-interval-seconds` "
                "et `--debug` côté `run_execution.py`. Défauts swing : 120 s / 5 s, debug désactivé."
            )
            adv_exec_col1, adv_exec_col2, adv_exec_col3 = st.columns(3)
            with adv_exec_col1:
                execution_protection_transition_timeout_seconds = int(
                    st.number_input(
                        "Transition — timeout (s)",
                        min_value=0,
                        max_value=3600,
                        value=int(st.session_state.get(
                            "pipeline_execution_protection_transition_timeout_seconds",
                            DEFAULT_EXEC_PROTECTION_TRANSITION_TIMEOUT_SECONDS,
                        )),
                        step=10,
                        key="pipeline_execution_protection_transition_timeout_seconds",
                        help="0 = ne pas envoyer le flag (laisse le défaut backend).",
                    )
                )
            with adv_exec_col2:
                execution_protection_transition_poll_interval_seconds = float(
                    st.number_input(
                        "Transition — poll interval (s)",
                        min_value=0.0,
                        max_value=120.0,
                        value=float(st.session_state.get(
                            "pipeline_execution_protection_transition_poll_interval_seconds",
                            DEFAULT_EXEC_PROTECTION_TRANSITION_POLL_INTERVAL_SECONDS,
                        )),
                        step=0.5,
                        format="%.2f",
                        key="pipeline_execution_protection_transition_poll_interval_seconds",
                        help="0 = ne pas envoyer le flag (laisse le défaut backend).",
                    )
                )
            with adv_exec_col3:
                execution_debug = st.checkbox(
                    "Execution — `--debug` (logs DEBUG)",
                    value=bool(st.session_state.get("pipeline_execution_debug", DEFAULT_EXEC_DEBUG)),
                    key="pipeline_execution_debug",
                )

        # ──────────────────────────────────────────────────────────────────
        # Paramètres Risk Management — P1 cf. audit_ihm_pipeline_options.md
        # ──────────────────────────────────────────────────────────────────
        st.markdown("#### Paramètres Risk Management (`python -m risk_management`)")
        st.caption(
            "Pilote le sizing et les contraintes du portefeuille cible. "
            "Défauts swing : 1 % risque/trade, 15 positions max, 8 % max/ligne, conviction = 40 % score + 60 % ML."
        )
        risk_col1, risk_col2, risk_col3, risk_col4 = st.columns(4)
        with risk_col1:
            risk_per_trade_pct = float(
                st.number_input(
                    "Risk — risque par trade (fraction)",
                    min_value=0.001,
                    max_value=0.10,
                    value=float(st.session_state.get("pipeline_risk_per_trade_pct", DEFAULT_RISK_PER_TRADE_PCT)),
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
                    value=int(st.session_state.get("pipeline_risk_max_positions", DEFAULT_RISK_MAX_POSITIONS)),
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
                    value=float(st.session_state.get("pipeline_risk_max_position_weight", DEFAULT_RISK_MAX_POSITION_WEIGHT)),
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
                    value=float(st.session_state.get("pipeline_risk_max_sector_weight", DEFAULT_RISK_MAX_SECTOR_WEIGHT)),
                    step=0.05,
                    format="%.2f",
                    key="pipeline_risk_max_sector_weight",
                )
            )
        with risk_col3:
            risk_score_weight = float(
                st.number_input(
                    "Risk — poids score (conviction)",
                    min_value=0.0,
                    max_value=1.0,
                    value=float(st.session_state.get("pipeline_risk_score_weight", DEFAULT_RISK_SCORE_WEIGHT)),
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
                    value=float(st.session_state.get("pipeline_risk_prediction_weight", DEFAULT_RISK_PREDICTION_WEIGHT)),
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
                    value=float(st.session_state.get("pipeline_risk_correlation_threshold", DEFAULT_RISK_CORRELATION_THRESHOLD)),
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
                    value=int(st.session_state.get("pipeline_risk_correlation_lookback_days", DEFAULT_RISK_CORRELATION_LOOKBACK_DAYS)),
                    step=10,
                    key="pipeline_risk_correlation_lookback_days",
                )
            )

        with st.expander("Risk — Kelly sizing & options avancées", expanded=False):
            risk_adv_col1, risk_adv_col2, risk_adv_col3 = st.columns(3)
            with risk_adv_col1:
                risk_enable_kelly = st.checkbox(
                    "Activer Kelly sizing",
                    value=bool(st.session_state.get("pipeline_risk_enable_kelly", DEFAULT_RISK_ENABLE_KELLY)),
                    key="pipeline_risk_enable_kelly",
                )
                risk_dry_run = st.checkbox(
                    "Dry run (n'écrit pas en DB)",
                    value=bool(st.session_state.get("pipeline_risk_dry_run", False)),
                    key="pipeline_risk_dry_run",
                )
            with risk_adv_col2:
                risk_payoff_ratio = float(
                    st.number_input(
                        "Risk — payoff ratio assumé",
                        min_value=0.5,
                        value=float(st.session_state.get("pipeline_risk_payoff_ratio", DEFAULT_RISK_PAYOFF_RATIO)),
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
                        value=float(st.session_state.get("pipeline_risk_kelly_fraction_multiplier", DEFAULT_RISK_KELLY_FRACTION_MULTIPLIER)),
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
                        value=int(st.session_state.get("pipeline_risk_correlation_min_overlap", DEFAULT_RISK_CORRELATION_MIN_OVERLAP)),
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

        conviction_total = round(risk_score_weight + risk_prediction_weight, 4)
        if abs(conviction_total - 1.0) > 0.001:
            st.warning(f"⚠️ Risk : poids score + poids ML = {conviction_total} (≠ 1.0). Le backend pourrait normaliser.")

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

        st.markdown("#### Paramètres Model Factory")
        st.caption(
            "Ces options pilotent directement `python -m modelFactory --mode train`. "
            "L'objectif est d'aligner l'IHM sur la gouvernance multi-modèles réellement disponible côté backend."
        )

        ml_opt_col1, ml_opt_col2, ml_opt_col3 = st.columns(3)
        with ml_opt_col1:
            ml_include_sentiment = st.checkbox(
                "Inclure les features sentiment",
                value=bool(st.session_state.get("pipeline_ml_include_sentiment", True)),
                key="pipeline_ml_include_sentiment",
                help="Ajoute `--include-sentiment` à `ml_train`.",
            )
            ml_enable_lightgbm = st.checkbox(
                "Comparer LightGBM local",
                value=bool(st.session_state.get("pipeline_ml_enable_lightgbm", True)),
                key="pipeline_ml_enable_lightgbm",
                help="Ajoute `--compare-lightgbm`.",
            )
            ml_enable_catboost = st.checkbox(
                "Comparer CatBoost local",
                value=bool(st.session_state.get("pipeline_ml_enable_catboost", True)),
                key="pipeline_ml_enable_catboost",
                help="Ajoute `--enable-catboost`.",
            )
        with ml_opt_col2:
            ml_select_champion = st.checkbox(
                "Activer la sélection automatique du champion",
                value=bool(st.session_state.get("pipeline_ml_select_champion", True)),
                key="pipeline_ml_select_champion",
                help="Ajoute `--select-champion` et permet de servir automatiquement le meilleur modèle éligible.",
            )
            ml_champion_selection_metric = cast(
                str,
                st.selectbox(
                    "Métrique de sélection du champion",
                    options=["selection_score", "business_score", "auc"],
                    index=["selection_score", "business_score", "auc"].index(
                        cast(str, st.session_state.get("pipeline_ml_champion_selection_metric", "selection_score"))
                        if st.session_state.get("pipeline_ml_champion_selection_metric", "selection_score") in {"selection_score", "business_score", "auc"}
                        else "selection_score"
                    ),
                    key="pipeline_ml_champion_selection_metric",
                    disabled=not ml_select_champion,
                ),
            )
            ml_optimize_thresholds = st.checkbox(
                "Optimiser le seuil de décision",
                value=bool(st.session_state.get("pipeline_ml_optimize_thresholds", True)),
                key="pipeline_ml_optimize_thresholds",
                help="Ajoute `--optimize-thresholds` pour sélectionner le meilleur `decision_threshold` sur validation.",
            )
        with ml_opt_col3:
            ml_enable_global_model = st.checkbox(
                "Entraîner aussi un modèle global multi-symboles",
                value=bool(st.session_state.get("pipeline_ml_enable_global_model", False)),
                key="pipeline_ml_enable_global_model",
                help="Ajoute `--enable-global-model`.",
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
            ml_enable_cross_sectional = st.checkbox(
                "Activer les features cross-sectionnelles",
                value=bool(st.session_state.get("pipeline_ml_enable_cross_sectional", False)),
                key="pipeline_ml_enable_cross_sectional",
                help="Ajoute `--enable-cross-sectional` pour enrichir les features séquentielles et le modèle global.",
            )

        ml_adv_col1, ml_adv_col2 = st.columns(2)
        with ml_adv_col1:
            ml_optimize_target = st.checkbox(
                "Optimiser l'horizon / la target swing",
                value=bool(st.session_state.get("pipeline_ml_optimize_target", False)),
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
                    options=["binary", "swing_cash"],
                    index=["binary", "swing_cash"].index(
                        cast(str, st.session_state.get("pipeline_ml_target_mode", DEFAULT_ML_TARGET_MODE))
                        if st.session_state.get("pipeline_ml_target_mode", DEFAULT_ML_TARGET_MODE) in {"binary", "swing_cash"}
                        else DEFAULT_ML_TARGET_MODE
                    ),
                    key="pipeline_ml_target_mode",
                    help="`swing_cash` = cible asymétrique up/down adaptée au swing cash (recommandé).",
                ),
            )
            ml_forecast_horizon = int(
                st.number_input(
                    "Horizon de prédiction (jours)",
                    min_value=1,
                    max_value=30,
                    value=int(st.session_state.get("pipeline_ml_forecast_horizon", DEFAULT_ML_FORECAST_HORIZON)),
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
                    value=float(st.session_state.get("pipeline_ml_target_up_threshold", DEFAULT_ML_TARGET_UP_THRESHOLD)),
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
                    value=float(st.session_state.get("pipeline_ml_target_down_threshold", DEFAULT_ML_TARGET_DOWN_THRESHOLD)),
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
                    value=float(st.session_state.get("pipeline_ml_decision_threshold", DEFAULT_ML_DECISION_THRESHOLD)),
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

        st.markdown("##### Walk-forward")
        ml_wf_col1, ml_wf_col2 = st.columns([1, 4])
        with ml_wf_col1:
            ml_walkforward = st.checkbox(
                "Activer walk-forward",
                value=bool(st.session_state.get("pipeline_ml_walkforward", DEFAULT_ML_WALKFORWARD)),
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
                            value=int(st.session_state.get("pipeline_ml_wf_min_train_size", DEFAULT_ML_WF_MIN_TRAIN_SIZE)),
                            step=21,
                            key="pipeline_ml_wf_min_train_size",
                        )
                    )
                with wf_subcol2:
                    ml_wf_val_size = int(
                        st.number_input(
                            "wf val",
                            min_value=10,
                            value=int(st.session_state.get("pipeline_ml_wf_val_size", DEFAULT_ML_WF_VAL_SIZE)),
                            step=21,
                            key="pipeline_ml_wf_val_size",
                        )
                    )
                with wf_subcol3:
                    ml_wf_test_size = int(
                        st.number_input(
                            "wf test",
                            min_value=10,
                            value=int(st.session_state.get("pipeline_ml_wf_test_size", DEFAULT_ML_WF_TEST_SIZE)),
                            step=21,
                            key="pipeline_ml_wf_test_size",
                        )
                    )
                with wf_subcol4:
                    ml_wf_step_size = int(
                        st.number_input(
                            "wf step",
                            min_value=10,
                            value=int(st.session_state.get("pipeline_ml_wf_step_size", DEFAULT_ML_WF_STEP_SIZE)),
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
                            value=int(st.session_state.get("pipeline_ml_wf_max_splits", DEFAULT_ML_WF_MAX_SPLITS)),
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
                        value=int(st.session_state.get("pipeline_ml_max_workers", DEFAULT_ML_MAX_WORKERS)),
                        step=1,
                        key="pipeline_ml_max_workers",
                    )
                )
                ml_max_epochs = int(
                    st.number_input(
                        "ML — max epochs (LSTM)",
                        min_value=5,
                        max_value=500,
                        value=int(st.session_state.get("pipeline_ml_max_epochs", DEFAULT_ML_MAX_EPOCHS)),
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
                        value=float(st.session_state.get("pipeline_ml_min_action_rate", DEFAULT_ML_MIN_ACTION_RATE)),
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
                        value=float(st.session_state.get("pipeline_ml_max_action_rate", DEFAULT_ML_MAX_ACTION_RATE)),
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
                        value=float(st.session_state.get("pipeline_ml_min_precision_long", DEFAULT_ML_MIN_PRECISION_LONG)),
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
                        value=int(st.session_state.get("pipeline_ml_sequence_length", DEFAULT_ML_SEQUENCE_LENGTH)),
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
                        value=int(st.session_state.get("pipeline_ml_batch_size", DEFAULT_ML_BATCH_SIZE)),
                        step=8,
                        key="pipeline_ml_batch_size",
                    )
                )
                ml_hidden_size = int(
                    st.number_input(
                        "LSTM — hidden size",
                        min_value=8,
                        max_value=1024,
                        value=int(st.session_state.get("pipeline_ml_hidden_size", DEFAULT_ML_HIDDEN_SIZE)),
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
                        help="Partagé entre `ml_train` et `ml_predict`. Défaut : `artifacts/models`.",
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
                        value=int(st.session_state.get("pipeline_ml_cross_sectional_min_universe", DEFAULT_ML_CROSS_SECTIONAL_MIN_UNIVERSE)),
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
                        value=int(st.session_state.get("pipeline_ml_calibration_min_samples", DEFAULT_ML_CALIBRATION_MIN_SAMPLES)),
                        step=8,
                        key="pipeline_ml_calibration_min_samples",
                    )
                )
                ml_calibration_max_iter = int(
                    st.number_input(
                        "Calibration — max iter",
                        min_value=10,
                        max_value=10_000,
                        value=int(st.session_state.get("pipeline_ml_calibration_max_iter", DEFAULT_ML_CALIBRATION_MAX_ITER)),
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
                        value=int(st.session_state.get("pipeline_ml_lgbm_max_depth", DEFAULT_ML_LGBM_MAX_DEPTH)),
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
                        value=int(st.session_state.get("pipeline_ml_lgbm_n_estimators", DEFAULT_ML_LGBM_N_ESTIMATORS)),
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
                        value=float(st.session_state.get("pipeline_ml_lgbm_learning_rate", DEFAULT_ML_LGBM_LEARNING_RATE)),
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
                        value=int(st.session_state.get("pipeline_ml_catboost_depth", DEFAULT_ML_CATBOOST_DEPTH)),
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
                        value=int(st.session_state.get("pipeline_ml_catboost_iterations", DEFAULT_ML_CATBOOST_ITERATIONS)),
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
                        value=float(st.session_state.get("pipeline_ml_catboost_learning_rate", DEFAULT_ML_CATBOOST_LEARNING_RATE)),
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
                        value=float(st.session_state.get("pipeline_ml_min_trades_fraction", DEFAULT_ML_MIN_TRADES_FRACTION)),
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
                    value=int(st.session_state.get("pipeline_selector_chunk_size", DEFAULT_SELECTOR_CHUNK_SIZE)),
                    step=50,
                    key="pipeline_selector_chunk_size",
                )
            )
            selector_selection_size = int(
                st.number_input(
                    "Alpha Scanner — taille de sélection finale",
                    min_value=1,
                    value=int(st.session_state.get("pipeline_selector_selection_size", DEFAULT_SELECTOR_SELECTION_SIZE)),
                    step=5,
                    key="pipeline_selector_selection_size",
                )
            )
            selector_max_workers = int(
                st.number_input(
                    "Alpha Scanner — max workers (0 = auto)",
                    min_value=0,
                    value=int(st.session_state.get("pipeline_selector_max_workers", 0)),
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
                    value=float(st.session_state.get("pipeline_selector_liquidity_threshold", DEFAULT_SELECTOR_LIQUIDITY_THRESHOLD)),
                    step=1_000_000.0,
                    format="%.2f",
                    key="pipeline_selector_liquidity_threshold",
                )
            )
            selector_min_close = float(
                st.number_input(
                    "Alpha Scanner — prix mini",
                    min_value=0.01,
                    value=float(st.session_state.get("pipeline_selector_min_close", DEFAULT_SELECTOR_MIN_CLOSE)),
                    step=1.0,
                    format="%.2f",
                    key="pipeline_selector_min_close",
                )
            )
            selector_max_volatility_ratio = float(
                st.number_input(
                    "Alpha Scanner — volatilité relative max",
                    min_value=0.01,
                    value=float(st.session_state.get("pipeline_selector_max_volatility_ratio", DEFAULT_SELECTOR_MAX_VOLATILITY_RATIO)),
                    step=0.05,
                    format="%.2f",
                    key="pipeline_selector_max_volatility_ratio",
                )
            )
            selector_min_relative_strength_index = float(
                st.number_input(
                    "Alpha Scanner — RS mini",
                    min_value=0.01,
                    value=float(st.session_state.get("pipeline_selector_min_relative_strength_index", DEFAULT_SELECTOR_MIN_RELATIVE_STRENGTH_INDEX)),
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
                    value=float(st.session_state.get("pipeline_selector_min_high_52w_proximity", DEFAULT_SELECTOR_MIN_HIGH_52W_PROXIMITY)),
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
                    value=float(st.session_state.get("pipeline_selector_min_weekly_trend_score", DEFAULT_SELECTOR_MIN_WEEKLY_TREND_SCORE)),
                    step=0.05,
                    format="%.2f",
                    key="pipeline_selector_min_weekly_trend_score",
                )
            )
            selector_min_atr_pct_20 = float(
                st.number_input(
                    "Alpha Scanner — ATR%20 min",
                    min_value=0.0,
                    value=float(st.session_state.get("pipeline_selector_min_atr_pct_20", DEFAULT_SELECTOR_MIN_ATR_PCT_20)),
                    step=0.005,
                    format="%.4f",
                    key="pipeline_selector_min_atr_pct_20",
                )
            )
            selector_max_atr_pct_20 = float(
                st.number_input(
                    "Alpha Scanner — ATR%20 max",
                    min_value=0.0,
                    value=float(st.session_state.get("pipeline_selector_max_atr_pct_20", DEFAULT_SELECTOR_MAX_ATR_PCT_20)),
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
                    value=float(st.session_state.get("pipeline_selector_min_market_cap", DEFAULT_SELECTOR_MIN_MARKET_CAP)),
                    step=100_000_000.0,
                    format="%.2f",
                    key="pipeline_selector_min_market_cap",
                )
            )
            selector_min_beta_126 = float(
                st.number_input(
                    "Alpha Scanner — beta 126 mini",
                    min_value=0.0,
                    value=float(st.session_state.get("pipeline_selector_min_beta_126", DEFAULT_SELECTOR_MIN_BETA_126)),
                    step=0.1,
                    format="%.2f",
                    key="pipeline_selector_min_beta_126",
                )
            )
            selector_max_spread_bps = float(
                st.number_input(
                    "Alpha Scanner — spread max (bps)",
                    min_value=0.0,
                    value=float(st.session_state.get("pipeline_selector_max_spread_bps", DEFAULT_SELECTOR_MAX_SPREAD_BPS)),
                    step=1.0,
                    format="%.2f",
                    key="pipeline_selector_max_spread_bps",
                )
            )
            selector_earnings_blackout_days = int(
                st.number_input(
                    "Alpha Scanner — earnings blackout (jours)",
                    min_value=0,
                    value=int(st.session_state.get("pipeline_selector_earnings_blackout_days", DEFAULT_SELECTOR_EARNINGS_BLACKOUT_DAYS)),
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
                    value=int(st.session_state.get("pipeline_selector_max_anomaly_count", DEFAULT_SELECTOR_MAX_ANOMALY_COUNT)),
                    step=1,
                    key="pipeline_selector_max_anomaly_count",
                )
            )
            selector_require_above_ma200 = st.checkbox(
                "Alpha Scanner — exiger close > MA200 (Minervini stage 2)",
                value=bool(st.session_state.get("pipeline_selector_require_above_ma200", DEFAULT_SELECTOR_REQUIRE_ABOVE_MA200)),
                key="pipeline_selector_require_above_ma200",
                help="Défaut swing : True. Filtre anti-baissière standard trend-following.",
            )
        with selector_adv_col2:
            selector_sector_cap_ratio = float(
                st.number_input(
                    "Alpha Scanner — cap sectoriel",
                    min_value=0.01,
                    max_value=1.0,
                    value=float(st.session_state.get("pipeline_selector_sector_cap_ratio", DEFAULT_SELECTOR_SECTOR_CAP_RATIO)),
                    step=0.01,
                    format="%.2f",
                    key="pipeline_selector_sector_cap_ratio",
                )
            )

        st.markdown("#### Paramètres Event Sentiment")
        st.caption(
            "Ces réglages reflètent les options réellement supportées par `python -m event_sentiment`. "
            "Si les symboles sont laissés vides, le backend consomme automatiquement les candidats `stock_scores.is_candidate=1`."
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

        st.markdown("#### Paramètres Signal Aggregator")
        st.caption(
            "Ces réglages reflètent les options réellement supportées par `python -m event_sentiment.signal_aggregator`. "
            "La `trade date` réutilise le champ global situé en haut du formulaire quand il est renseigné."
        )

        signal_agg_col1, signal_agg_col2, signal_agg_col3 = st.columns(3)
        with signal_agg_col1:
            signal_aggregator_all_symbols = st.checkbox(
                "Signal Aggregator — traiter tous les symboles",
                value=bool(st.session_state.get("pipeline_signal_aggregator_all_symbols", False)),
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
                    value=float(st.session_state.get("pipeline_signal_aggregator_sentiment_weight", DEFAULT_SIGNAL_AGGREGATOR_SENTIMENT_WEIGHT)),
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
                    value=float(st.session_state.get("pipeline_signal_aggregator_macro_weight", DEFAULT_SIGNAL_AGGREGATOR_MACRO_WEIGHT)),
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
                    value=int(st.session_state.get("pipeline_signal_aggregator_lookback_days", DEFAULT_SIGNAL_AGGREGATOR_LOOKBACK_DAYS)),
                    step=1,
                    key="pipeline_signal_aggregator_lookback_days",
                )
            )
            signal_aggregator_min_news_count = int(
                st.number_input(
                    "Signal Aggregator — news mini",
                    min_value=1,
                    value=int(st.session_state.get("pipeline_signal_aggregator_min_news_count", DEFAULT_SIGNAL_AGGREGATOR_MIN_NEWS_COUNT)),
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
                    value=float(st.session_state.get("pipeline_signal_aggregator_time_decay_half_life_days", DEFAULT_SIGNAL_AGGREGATOR_TIME_DECAY_HALF_LIFE_DAYS)),
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
                    value=int(st.session_state.get("pipeline_screener_chunk_size", DEFAULT_SCREENER_CHUNK_SIZE)),
                    step=50,
                    key="pipeline_screener_chunk_size",
                )
            )
            screener_max_workers = int(
                st.number_input(
                    "Screener — max workers (0 = auto)",
                    min_value=0,
                    value=int(st.session_state.get("pipeline_screener_max_workers", 0)),
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
                    value=float(st.session_state.get("pipeline_screener_liquidity_threshold_usd", DEFAULT_SCREENER_LIQUIDITY_THRESHOLD_USD)),
                    step=1_000_000.0,
                    format="%.2f",
                    key="pipeline_screener_liquidity_threshold_usd",
                )
            )
            screener_min_relative_strength_index = float(
                st.number_input(
                    "Screener — RS mini vs benchmark",
                    min_value=0.01,
                    value=float(st.session_state.get("pipeline_screener_min_relative_strength_index", DEFAULT_SCREENER_MIN_RELATIVE_STRENGTH_INDEX)),
                    step=1.0,
                    format="%.2f",
                    key="pipeline_screener_min_relative_strength_index",
                )
            )
            screener_enable_two_pass_loading = st.checkbox(
                "Screener — activer le chargement en 2 passes",
                value=bool(st.session_state.get("pipeline_screener_enable_two_pass_loading", DEFAULT_SCREENER_ENABLE_TWO_PASS_LOADING)),
                key="pipeline_screener_enable_two_pass_loading",
            )
        with screener_col3:
            screener_historical_range_lookback_days = int(
                st.number_input(
                    "Screener — fenêtre range historique (jours)",
                    min_value=2,
                    value=int(st.session_state.get("pipeline_screener_historical_range_lookback_days", DEFAULT_SCREENER_HISTORICAL_RANGE_LOOKBACK_DAYS)),
                    step=21,
                    key="pipeline_screener_historical_range_lookback_days",
                )
            )
            screener_min_historical_range_score = float(
                st.number_input(
                    "Screener — score mini range historique",
                    min_value=0.0,
                    max_value=100.0,
                    value=float(st.session_state.get("pipeline_screener_min_historical_range_score", DEFAULT_SCREENER_MIN_HISTORICAL_RANGE_SCORE)),
                    step=1.0,
                    format="%.2f",
                    key="pipeline_screener_min_historical_range_score",
                )
            )
            screener_first_pass_window_days = int(
                st.number_input(
                    "Screener — fenêtre passe 1 (jours)",
                    min_value=252,
                    value=int(st.session_state.get("pipeline_screener_first_pass_window_days", DEFAULT_SCREENER_FIRST_PASS_WINDOW_DAYS)),
                    step=21,
                    key="pipeline_screener_first_pass_window_days",
                )
            )

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
                    value=int(st.session_state.get("pipeline_data_integrity_quotes_limit", 0)),
                    step=50,
                    key="pipeline_data_integrity_quotes_limit",
                )
            )
            data_integrity_quotes_batch_size = int(
                st.number_input(
                    "Latest Quotes — taille de batch",
                    min_value=1,
                    value=int(st.session_state.get("pipeline_data_integrity_quotes_batch_size", DEFAULT_DATA_INTEGRITY_QUOTES_BATCH_SIZE)),
                    step=25,
                    key="pipeline_data_integrity_quotes_batch_size",
                )
            )
            data_integrity_earnings_limit = int(
                st.number_input(
                    "Earnings — limite optionnelle",
                    min_value=0,
                    value=int(st.session_state.get("pipeline_data_integrity_earnings_limit", 0)),
                    step=25,
                    key="pipeline_data_integrity_earnings_limit",
                )
            )
            data_integrity_earnings_batch_size = int(
                st.number_input(
                    "Earnings — taille de batch (symboles)",
                    min_value=25,
                    max_value=100,
                    value=int(st.session_state.get("pipeline_data_integrity_earnings_batch_size", DEFAULT_DATA_INTEGRITY_EARNINGS_BATCH_SIZE)),
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
                    value=float(st.session_state.get("pipeline_data_integrity_earnings_sleep_seconds", DEFAULT_DATA_INTEGRITY_PROVIDER_SLEEP_SECONDS)),
                    step=0.1,
                    format="%.2f",
                    key="pipeline_data_integrity_earnings_sleep_seconds",
                )
            )
            data_integrity_earnings_log_every = int(
                st.number_input(
                    "Earnings — journaliser tous les N symboles",
                    min_value=0,
                    value=int(st.session_state.get("pipeline_data_integrity_earnings_log_every", DEFAULT_DATA_INTEGRITY_EARNINGS_LOG_EVERY)),
                    step=5,
                    key="pipeline_data_integrity_earnings_log_every",
                    help="0 désactive les logs de progression Finnhub. Défaut : 25, soit environ un log toutes les ~30s avec la pause par défaut.",
                )
            )
            data_integrity_fundamentals_limit = int(
                st.number_input(
                    "Fondamentaux — limite optionnelle",
                    min_value=0,
                    value=int(st.session_state.get("pipeline_data_integrity_fundamentals_limit", 0)),
                    step=25,
                    key="pipeline_data_integrity_fundamentals_limit",
                )
            )
            data_integrity_fundamentals_sleep_seconds = float(
                st.number_input(
                    "Fondamentaux — pause Finnhub (s)",
                    min_value=0.0,
                    value=float(st.session_state.get("pipeline_data_integrity_fundamentals_sleep_seconds", DEFAULT_DATA_INTEGRITY_PROVIDER_SLEEP_SECONDS)),
                    step=0.1,
                    format="%.2f",
                    key="pipeline_data_integrity_fundamentals_sleep_seconds",
                )
            )
        with di_col3:
            data_integrity_fundamentals_log_every = int(
                st.number_input(
                    "Fondamentaux — journaliser tous les N symboles",
                    min_value=1,
                    value=int(st.session_state.get("pipeline_data_integrity_fundamentals_log_every", DEFAULT_DATA_INTEGRITY_FUNDAMENTALS_LOG_EVERY)),
                    step=5,
                    key="pipeline_data_integrity_fundamentals_log_every",
                )
            )
            data_integrity_earnings_resume = st.checkbox(
                "Earnings — reprendre depuis le bookmark local",
                value=bool(st.session_state.get("pipeline_data_integrity_earnings_resume", DEFAULT_DATA_INTEGRITY_EARNINGS_RESUME)),
                key="pipeline_data_integrity_earnings_resume",
                help="Si activé, les symboles déjà commités sont sautés au redémarrage ; sinon le run repart du début et ignore le bookmark existant.",
            )
            data_integrity_earnings_custom_window = st.checkbox(
                "Earnings — utiliser une fenêtre de dates personnalisée",
                value=bool(st.session_state.get(EARNINGS_CUSTOM_WINDOW_KEY, False)),
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

        st.markdown("#### Paramètres Corporate Actions")
        ca_col1, ca_col2, ca_col3 = st.columns([1, 1, 3])
        with ca_col1:
            corporate_actions_skip_existing = st.checkbox(
                "CA Sync — skip existing",
                value=bool(st.session_state.get("pipeline_corporate_actions_skip_existing", DEFAULT_CA_SKIP_EXISTING)),
                key="pipeline_corporate_actions_skip_existing",
                help="Si coché, ignore les symboles déjà présents dans corporate_actions_events (perf, mais peut rater de nouveaux events).",
            )
        with ca_col2:
            corporate_actions_batch_size = int(
                st.number_input(
                    "CA Sync — batch size",
                    min_value=1,
                    max_value=200,
                    value=int(st.session_state.get("pipeline_corporate_actions_batch_size", DEFAULT_CA_BATCH_SIZE)),
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
            value=bool(st.session_state.get("pipeline_corporate_actions_use_custom_window", DEFAULT_CA_USE_CUSTOM_WINDOW)),
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
                    value=int(st.session_state.get("pipeline_eodhd_backfill_years", 30)),
                    step=1,
                    key="pipeline_eodhd_backfill_years",
                    help="30 ans par défaut (profondeur historique maximale EODHD pour robustesse ML/backtest). Coût quota EODHD identique quelle que soit la profondeur (1 appel par symbole).",
                )
            )
            eodhd_backfill_resume = st.checkbox(
                "B3 — reprendre via bookmark",
                value=bool(st.session_state.get("pipeline_eodhd_backfill_resume", True)),
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
                value=bool(st.session_state.get("pipeline_eodhd_backfill_write", True)),
                key="pipeline_eodhd_backfill_write",
                help="Coché par défaut = ajoute `--write` et persiste dans `stock_bars` / `stock_bars_daily`. Décoché = dry-run sans insert DB.",
            )
            if eodhd_backfill_write:
                st.success("B3 sera lancé en mode `write` et insérera dans les tables.")
            else:
                st.warning("B3 sera lancé en mode `dry-run` : appels API réels, mais 0 insert DB.")

        live_confirmed = True
        if execution_mode == "live":
            st.warning("Mode LIVE sélectionné : cette action peut envoyer de vrais ordres chez le broker.")
            live_confirmed = st.checkbox(
                "Je confirme explicitement le lancement en LIVE",
                value=bool(st.session_state.get("pipeline_live_confirmed", False)),
                key="pipeline_live_confirmed",
            )

    return (
        PipelineLaunchOptions(
            account_id=selected_account_id,
            trade_date=trade_date,
            risk_account_equity=float(risk_account_equity),
            execution_mode=cast(Any, execution_mode),
            execution_run_id=execution_run_id,
            allow_outside_rth=bool(allow_outside_rth),
            auto_rebalance=bool(auto_rebalance),
            execution_account_type=cast(Any, execution_account_type),
            execution_pdt_rule=cast(Any, execution_pdt_rule),
            execution_swing_only=bool(execution_swing_only),
            execution_submission_window=cast(Any, execution_submission_window),
            execution_trailing_trigger=cast(Any, execution_trailing_trigger),
            execution_trailing_r_multiple=float(execution_trailing_r_multiple),
            execution_trailing_profit_pct=float(execution_trailing_profit_pct),
            execution_protection_transition_timeout_seconds=int(execution_protection_transition_timeout_seconds),
            execution_protection_transition_poll_interval_seconds=float(execution_protection_transition_poll_interval_seconds),
            execution_debug=bool(execution_debug),
            ml_accelerator=cast(Any, ml_accelerator),
            ml_include_sentiment=bool(ml_include_sentiment),
            ml_enable_lightgbm=bool(ml_enable_lightgbm),
            ml_enable_catboost=bool(ml_enable_catboost),
            ml_enable_global_model=bool(ml_enable_global_model),
            ml_global_model_name=cast(Any, ml_global_model_name),
            ml_enable_cross_sectional=bool(ml_enable_cross_sectional),
            ml_select_champion=bool(ml_select_champion),
            ml_champion_selection_metric=cast(Any, ml_champion_selection_metric),
            ml_optimize_thresholds=bool(ml_optimize_thresholds),
            ml_optimize_target=bool(ml_optimize_target),
            ml_target_mode=cast(Any, ml_target_mode),
            ml_forecast_horizon=int(ml_forecast_horizon),
            ml_target_up_threshold=float(ml_target_up_threshold),
            ml_target_down_threshold=float(ml_target_down_threshold),
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
            ml_min_action_rate=float(ml_min_action_rate),
            ml_max_action_rate=float(ml_max_action_rate),
            ml_min_precision_long=float(ml_min_precision_long),
            ml_sequence_length=int(ml_sequence_length),
            ml_batch_size=int(ml_batch_size),
            ml_hidden_size=int(ml_hidden_size),
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
            risk_score_weight=float(risk_score_weight),
            risk_prediction_weight=float(risk_prediction_weight),
            risk_correlation_threshold=float(risk_correlation_threshold),
            risk_correlation_lookback_days=int(risk_correlation_lookback_days),
            risk_correlation_min_overlap=int(risk_correlation_min_overlap),
            risk_enable_kelly=bool(risk_enable_kelly),
            risk_payoff_ratio=float(risk_payoff_ratio),
            risk_kelly_fraction_multiplier=float(risk_kelly_fraction_multiplier),
            risk_dry_run=bool(risk_dry_run),
            risk_log_level=str(risk_log_level).upper(),
            sentiment_start_utc=sentiment_start_utc or None,
            sentiment_end_utc=sentiment_end_utc or None,
            sentiment_symbols=sentiment_symbols or None,
            selector_chunk_size=int(selector_chunk_size),
            selector_selection_size=int(selector_selection_size),
            selector_max_workers=_to_optional_positive_int(selector_max_workers),
            selector_liquidity_threshold=float(selector_liquidity_threshold),
            selector_min_close=float(selector_min_close),
            selector_max_volatility_ratio=float(selector_max_volatility_ratio),
            selector_min_relative_strength_index=float(selector_min_relative_strength_index),
            selector_min_high_52w_proximity=float(selector_min_high_52w_proximity),
            selector_min_weekly_trend_score=float(selector_min_weekly_trend_score),
            selector_min_atr_pct_20=float(selector_min_atr_pct_20),
            selector_max_atr_pct_20=float(selector_max_atr_pct_20),
            selector_min_market_cap=float(selector_min_market_cap),
            selector_min_beta_126=float(selector_min_beta_126),
            selector_max_spread_bps=float(selector_max_spread_bps),
            selector_earnings_blackout_days=int(selector_earnings_blackout_days),
            selector_max_anomaly_count=int(selector_max_anomaly_count),
            selector_sector_cap_ratio=float(selector_sector_cap_ratio),
            selector_log_level=str(selector_log_level).upper(),
            selector_require_above_ma200=bool(selector_require_above_ma200),
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
            data_integrity_fundamentals_sleep_seconds=float(data_integrity_fundamentals_sleep_seconds),
            data_integrity_fundamentals_log_every=int(data_integrity_fundamentals_log_every),
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
