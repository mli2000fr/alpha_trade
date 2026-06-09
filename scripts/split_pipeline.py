"""One-shot helper to physically split ihm/pages/pipeline.py into 6 sub-modules.

Phase 6.2 (Backlog L10) — non-destructive split: code is *moved* into
sub-modules; pipeline.py becomes a thin orchestrator with re-exports for
backward compat.

Run once from repo root:  python scripts/split_pipeline.py
The script is idempotent : it always rewrites the 7 files.
"""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "ihm" / "pages" / "pipeline.py"
OUT_DIR = REPO / "ihm" / "pages"

source_lines = SRC.read_text(encoding="utf-8").splitlines()


def slice_(a: int, b: int) -> str:
    """1-indexed inclusive line slice."""
    return "\n".join(source_lines[a - 1 : b])


# ---------------------------------------------------------------------------
# _shared.py — constants + transversal helpers
# ---------------------------------------------------------------------------
SHARED_HEADER = '''"""ihm/pages/_shared.py — Phase 6.2 (Backlog L10).

Constantes ``st.session_state`` et helpers UI partagés entre les sous-modules
extraits de ``ihm/pages/pipeline.py`` (workflow, runtime center, exécution,
data integrity, alpha scanner diagnostics, watcher).

Les noms publics et privés sont ré-exportés par ``ihm.pages.pipeline`` pour
préserver la rétro-compatibilité (``from ihm.pages.pipeline import
TAIL_LINES, _render_run_summary, ...``).
"""
from __future__ import annotations

from typing import cast

import pandas as pd
import streamlit as st

from ihm.components.metrics import format_duration_hhmmss, to_int
from ihm.components.run_summary import render_run_summary_block
from ihm.services.pipeline_runner import (
    PipelineLaunchOptions,
    get_pipeline_auxiliary_steps,
    get_pipeline_steps,
)
from ihm.services.process_registry import start_pipeline_run
from ihm.services.run_summary import build_run_summary_caption, get_run_summary

__all__ = [
    "ALPHA_SCANNER_DEPENDENCY_ACTION_RUNS_KEY",
    "ALPHA_SCANNER_DEPENDENCY_THRESHOLDS_FLASH_KEY",
    "ALPHA_SCANNER_DIAGNOSTIC_THRESHOLDS_CAPTION",
    "ALPHA_SCANNER_DIAGNOSTIC_THRESHOLDS_TITLE",
    "ALPHA_SCANNER_PARAMS_CAPTION",
    "ALPHA_SCANNER_PARAMS_TITLE",
    "COMPARE_RUNS_KEY",
    "EARNINGS_CUSTOM_WINDOW_KEY",
    "EXECUTION_DEFAULTS_ACCOUNT_KEY",
    "IMPORT_NEWS_END_DATE_KEY",
    "IMPORT_NEWS_START_DATE_KEY",
    "LOG_FILTER_KEY",
    "ML_SELECTED_SYMBOL_KEY",
    "NAVIGATION_TARGET_PAGE_KEY",
    "PENDING_COMPARE_RUNS_KEY",
    "PENDING_SELECTED_RUN_KEY",
    "PipelineLaunchOptions",
    "SCREENER_PARAMS_CAPTION",
    "SCREENER_PARAMS_TITLE",
    "SELECTED_RUN_KEY",
    "TAIL_LINES",
    "_is_workflow_run",
    "_launch_pipeline_step",
    "_pipeline_step_label",
    "_record_dependency_action_run",
    "_render_log_block",
    "_render_run_summary",
    "_render_step_result",
    "_sanitize_compare_ids",
    "_status_badge",
    "_tail_text",
    "_to_optional_positive_int",
    "_workflow_progress",
    "build_run_summary_caption",
    "format_duration_hhmmss",
    "get_pipeline_auxiliary_steps",
    "get_pipeline_steps",
    "get_run_summary",
    "render_run_summary_block",
    "start_pipeline_run",
    "to_int",
]


'''

SHARED_BODY = "\n\n\n".join(
    [
        slice_(156, 182),  # constants
        slice_(234, 238),  # _tail_text
        slice_(241, 245),  # _to_optional_positive_int
        slice_(248, 298),  # _render_run_summary
        slice_(301, 311),  # _render_log_block
        slice_(371, 375),  # _pipeline_step_label
        slice_(517, 521),  # _record_dependency_action_run
        slice_(524, 550),  # _launch_pipeline_step
        slice_(2465, 2473),  # _status_badge
        slice_(2476, 2477),  # _is_workflow_run
        slice_(2480, 2488),  # _workflow_progress
        slice_(2517, 2519),  # _sanitize_compare_ids
        slice_(2745, 2768),  # _render_step_result
    ]
)
(OUT_DIR / "_shared.py").write_text(SHARED_HEADER + SHARED_BODY + "\n", encoding="utf-8")

# ---------------------------------------------------------------------------
# _watcher_block.py — watcher handoff panel
# ---------------------------------------------------------------------------
WATCHER_HEADER = '''"""ihm/pages/_watcher_block.py — Phase 6.2 (Backlog L10).

Panneau « 12.bis Watcher post-exécution » extrait de ``pipeline.py``.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from ihm.components.watcher_documentation import render_watcher_documentation_panel
from ihm.services.pipeline_runner import (
    PipelineLaunchOptions,
    format_command_for_display,
)
from ihm.services.watcher_runtime import (
    build_watcher_command,
    build_windows_integration_rows,
)

__all__ = ["_build_watcher_handoff_rows", "_render_watcher_handoff_panel"]


'''
WATCHER_BODY = slice_(185, 231)
(OUT_DIR / "_watcher_block.py").write_text(WATCHER_HEADER + WATCHER_BODY + "\n", encoding="utf-8")

# ---------------------------------------------------------------------------
# _alpha_scanner_diagnostics.py — dependency diagnostic + thresholds editor
# ---------------------------------------------------------------------------
ASD_HEADER = '''"""ihm/pages/_alpha_scanner_diagnostics.py — Phase 6.2 (Backlog L10).

Diagnostic des dépendances Alpha Scanner (quotes / earnings) extrait de
``pipeline.py`` : éditeur de seuils, badges de santé, panneau diagnostic.
"""
from __future__ import annotations

import streamlit as st

from ihm.components.alpha_scanner_dependency import (
    dependency_badge,
    get_dependency_payload,
    render_dependency_metrics,
)
from ihm.pages._shared import (
    ALPHA_SCANNER_DEPENDENCY_ACTION_RUNS_KEY,
    ALPHA_SCANNER_DEPENDENCY_THRESHOLDS_FLASH_KEY,
    ALPHA_SCANNER_DIAGNOSTIC_THRESHOLDS_CAPTION,
    ALPHA_SCANNER_DIAGNOSTIC_THRESHOLDS_TITLE,
    PipelineLaunchOptions,
    _launch_pipeline_step,
    _pipeline_step_label,
)
from ihm.services.db import reset_db_caches
from ihm.services.queries import (
    ALPHA_SCANNER_DEPENDENCY_THRESHOLDS,
    get_alpha_scanner_dependency_diagnostic,
    get_alpha_scanner_dependency_thresholds,
)
from ihm.services.screener_preferences import (
    reset_persisted_alpha_scanner_dependency_thresholds,
    save_persisted_alpha_scanner_dependency_thresholds,
)

__all__ = [
    "_alpha_scanner_dependency_block_reason",
    "_collect_alpha_scanner_dependency_threshold_inputs",
    "_prime_alpha_scanner_dependency_threshold_state",
    "_render_alpha_scanner_dependency_diagnostic",
    "_render_alpha_scanner_dependency_threshold_editor",
    "_render_dependency_action_feedback",
    "_render_dependency_health_inline",
    "_set_alpha_scanner_dependency_threshold_state",
    "_threshold_widget_key",
]


'''

ASD_BODY = "\n\n\n".join(
    [
        slice_(362, 368),  # _alpha_scanner_dependency_block_reason
        slice_(378, 379),  # _threshold_widget_key
        slice_(382, 389),  # _prime_alpha_scanner_dependency_threshold_state
        slice_(392, 399),  # _collect_alpha_scanner_dependency_threshold_inputs
        slice_(402, 405),  # _set_alpha_scanner_dependency_threshold_state
        slice_(408, 514),  # _render_alpha_scanner_dependency_threshold_editor
        slice_(553, 558),  # _render_dependency_health_inline
        slice_(561, 593),  # _render_dependency_action_feedback
        slice_(596, 678),  # _render_alpha_scanner_dependency_diagnostic
    ]
)
(OUT_DIR / "_alpha_scanner_diagnostics.py").write_text(
    ASD_HEADER + ASD_BODY + "\n", encoding="utf-8"
)

# ---------------------------------------------------------------------------
# _execution_center.py — execution prefills + giant _build_launch_options
# ---------------------------------------------------------------------------
EXEC_HEADER = '''"""ihm/pages/_execution_center.py — Phase 6.2 (Backlog L10).

Préfill exécution (compte/swing) + ``_build_launch_options`` (tous les
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
    PipelineExecutionDefaults,
    get_pipeline_execution_defaults,
)
from ihm.services.pipeline_runner import (
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


'''
EXEC_BODY = "\n\n\n".join(
    [
        slice_(314, 344),  # _apply_execution_prefills
        slice_(347, 359),  # _build_execution_prefill_caption
        slice_(681, 2440),  # _build_launch_options
    ]
)
(OUT_DIR / "_execution_center.py").write_text(EXEC_HEADER + EXEC_BODY + "\n", encoding="utf-8")

# ---------------------------------------------------------------------------
# _data_integrity.py — import_news panel
# ---------------------------------------------------------------------------
DI_HEADER = '''"""ihm/pages/_data_integrity.py — Phase 6.2 (Backlog L10).

Panneau « 5.bis Import News » (event_sentiment.importe_news) extrait de
``pipeline.py``.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from typing import cast

import streamlit as st

from ihm.pages._shared import (
    COMPARE_RUNS_KEY,
    IMPORT_NEWS_END_DATE_KEY,
    IMPORT_NEWS_START_DATE_KEY,
    PENDING_COMPARE_RUNS_KEY,
    PENDING_SELECTED_RUN_KEY,
    PipelineLaunchOptions,
    _render_step_result,
    _sanitize_compare_ids,
    start_pipeline_run,
)
from ihm.services.pipeline_runner import (
    build_pipeline_command,
    format_command_for_display,
)
from ihm.services.process_registry import stop_pipeline_run

__all__ = ["_render_import_news_panel"]


'''
DI_BODY = slice_(2791, 2886)
(OUT_DIR / "_data_integrity.py").write_text(DI_HEADER + DI_BODY + "\n", encoding="utf-8")

# ---------------------------------------------------------------------------
# _workflow.py — workflow launcher + runtime center
# ---------------------------------------------------------------------------
WF_HEADER = '''"""ihm/pages/_workflow.py — Phase 6.2 (Backlog L10).

Workflow launcher 1→14 + runtime center (suivi des runs en cours / historique)
extraits de ``pipeline.py``.
"""
from __future__ import annotations

from typing import Any, cast

import pandas as pd
import streamlit as st

from ihm.pages._shared import (
    COMPARE_RUNS_KEY,
    LOG_FILTER_KEY,
    PENDING_COMPARE_RUNS_KEY,
    PENDING_SELECTED_RUN_KEY,
    SELECTED_RUN_KEY,
    PipelineLaunchOptions,
    _is_workflow_run,
    _render_log_block,
    _render_run_summary,
    _sanitize_compare_ids,
    _status_badge,
    _workflow_progress,
    build_run_summary_caption,
    format_duration_hhmmss,
    to_int,
)
from ihm.services.process_registry import (
    build_log_download_name,
    get_pipeline_run_record,
    list_active_pipeline_runs,
    load_pipeline_history,
    read_pipeline_logs,
    start_pipeline_workflow,
    stop_pipeline_run,
)

__all__ = [
    "_build_history_rows",
    "_latest_run_by_step",
    "_merge_runs",
    "_prime_runtime_center_state",
    "_render_runtime_center",
    "_render_workflow_launcher",
]


'''
WF_BODY = "\n\n\n".join(
    [
        slice_(2443, 2453),  # _merge_runs
        slice_(2456, 2462),  # _latest_run_by_step
        slice_(2491, 2514),  # _build_history_rows
        slice_(2522, 2539),  # _prime_runtime_center_state
        slice_(2542, 2585),  # _render_workflow_launcher
        slice_(2587, 2742),  # _render_runtime_center (with @st.fragment)
    ]
)
(OUT_DIR / "_workflow.py").write_text(WF_HEADER + WF_BODY + "\n", encoding="utf-8")

# ---------------------------------------------------------------------------
# pipeline.py — thin orchestrator + re-exports (backward compat)
# ---------------------------------------------------------------------------
PIPELINE_NEW = '''"""ihm/pages/pipeline.py — Vue séquentielle et pilotage asynchrone du pipeline métier.

**Phase 6.2 (Backlog L10)** : ce fichier a été découpé en sous-modules
``_shared``, ``_workflow``, ``_data_integrity``, ``_execution_center``,
``_alpha_scanner_diagnostics`` et ``_watcher_block``. Les imports historiques
``from ihm.pages.pipeline import X`` continuent de fonctionner via les
ré-exports ci-dessous.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

from ihm.pages import run_page_if_standalone
from ihm.pages._alpha_scanner_diagnostics import (
    _alpha_scanner_dependency_block_reason,
    _collect_alpha_scanner_dependency_threshold_inputs,
    _prime_alpha_scanner_dependency_threshold_state,
    _render_alpha_scanner_dependency_diagnostic,
    _render_alpha_scanner_dependency_threshold_editor,
    _render_dependency_action_feedback,
    _render_dependency_health_inline,
    _set_alpha_scanner_dependency_threshold_state,
    _threshold_widget_key,
)
from ihm.pages._data_integrity import _render_import_news_panel
from ihm.pages._execution_center import (
    _apply_execution_prefills,
    _build_execution_prefill_caption,
    _build_launch_options,
)
from ihm.pages._shared import (
    ALPHA_SCANNER_DEPENDENCY_ACTION_RUNS_KEY,
    ALPHA_SCANNER_DEPENDENCY_THRESHOLDS_FLASH_KEY,
    ALPHA_SCANNER_DIAGNOSTIC_THRESHOLDS_CAPTION,
    ALPHA_SCANNER_DIAGNOSTIC_THRESHOLDS_TITLE,
    ALPHA_SCANNER_PARAMS_CAPTION,
    ALPHA_SCANNER_PARAMS_TITLE,
    COMPARE_RUNS_KEY,
    EARNINGS_CUSTOM_WINDOW_KEY,
    EXECUTION_DEFAULTS_ACCOUNT_KEY,
    IMPORT_NEWS_END_DATE_KEY,
    IMPORT_NEWS_START_DATE_KEY,
    LOG_FILTER_KEY,
    ML_SELECTED_SYMBOL_KEY,
    NAVIGATION_TARGET_PAGE_KEY,
    PENDING_COMPARE_RUNS_KEY,
    PENDING_SELECTED_RUN_KEY,
    PipelineLaunchOptions,
    SCREENER_PARAMS_CAPTION,
    SCREENER_PARAMS_TITLE,
    SELECTED_RUN_KEY,
    TAIL_LINES,
    _is_workflow_run,
    _launch_pipeline_step,
    _pipeline_step_label,
    _record_dependency_action_run,
    _render_log_block,
    _render_run_summary,
    _render_step_result,
    _sanitize_compare_ids,
    _status_badge,
    _tail_text,
    _to_optional_positive_int,
    _workflow_progress,
    get_pipeline_auxiliary_steps,
    get_pipeline_steps,
)
from ihm.pages._watcher_block import (
    _build_watcher_handoff_rows,
    _render_watcher_handoff_panel,
)
from ihm.pages._workflow import (
    _build_history_rows,
    _latest_run_by_step,
    _merge_runs,
    _prime_runtime_center_state,
    _render_runtime_center,
    _render_workflow_launcher,
)
from ihm.services.db import get_runtime_db_config
from ihm.services.ml_artifacts import list_ml_artifact_symbols
from ihm.services.pipeline_runner import (
    build_pipeline_command,
    format_command_for_display,
)
from ihm.services.process_registry import stop_pipeline_run
from ihm.services.queries import get_alpha_scanner_dependency_diagnostic


def _render_ml_inspection_link(step_key: str) -> None:
    if step_key not in {"ml_train", "ml_predict"}:
        return
    symbols = list_ml_artifact_symbols()
    if not symbols:
        st.caption("Aucun artefact ML détecté pour proposer une navigation ciblée vers la page ML.")
        return
    inspect_key = f"pipeline_ml_inspect_symbol_{step_key}"
    selected_symbol = st.selectbox(
        "Inspecter un symbole dans la page ML",
        options=symbols,
        format_func=lambda sym: f"{sym} — modèle global" if sym.startswith("__") else sym,
        key=inspect_key,
    )
    if st.button("🔎 Ouvrir dans la page ML", key=f"pipeline_open_ml_{step_key}", use_container_width=True):
        st.session_state[ML_SELECTED_SYMBOL_KEY] = selected_symbol
        st.session_state[NAVIGATION_TARGET_PAGE_KEY] = "ml"
        st.rerun()


'''

PIPELINE_TAIL = "\n\n\n".join(
    [
        slice_(2889, 2986),  # _render_launchable_step_panel
        slice_(2989, 3033),  # _render_step_panels (with @st.fragment)
        slice_(3036, 3045),  # render
        slice_(3048, 3048),  # run_page_if_standalone
    ]
)

# Sanity: pipeline.py must end with run_page_if_standalone call.
SRC.write_text(PIPELINE_NEW + PIPELINE_TAIL + "\n", encoding="utf-8")

print("Split done.")
print(f"  _shared.py            : {(OUT_DIR / '_shared.py').stat().st_size} bytes")
print(f"  _watcher_block.py     : {(OUT_DIR / '_watcher_block.py').stat().st_size} bytes")
print(f"  _alpha_scanner_diag.py: {(OUT_DIR / '_alpha_scanner_diagnostics.py').stat().st_size} bytes")
print(f"  _execution_center.py  : {(OUT_DIR / '_execution_center.py').stat().st_size} bytes")
print(f"  _data_integrity.py    : {(OUT_DIR / '_data_integrity.py').stat().st_size} bytes")
print(f"  _workflow.py          : {(OUT_DIR / '_workflow.py').stat().st_size} bytes")
print(f"  pipeline.py (new)     : {SRC.stat().st_size} bytes")


