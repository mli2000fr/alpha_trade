"""Sprint S7 compatibility shim - ``selector.alpha_scanner``.

Sprint S7 (A-015) finalized the extraction of the thin orchestrator:

- ``selector.config``       : ``AlphaScannerConfig`` + constants.
- ``selector.run_summary``  : run-summary CLI helpers.
- ``selector.db_io``        : DB I/O (reads, persistence, schema introspection).
- ``selector.scanner``      : ``AlphaScanner`` class (multi-thread orchestration).
- ``selector.cli``          : standalone CLI (``main()``, parser).

This shim re-exports every historically public AND private name
(``apply_filters_with_stats``, ``_summarize_zero_candidate_filters``,
``_utc_now_naive``, ...) so that existing tests, scripts and IHM keep
using ``from selector.alpha_scanner import ...`` unchanged.

Note: the data_source_mix_check telemetry emission (Sprint S2 - A-017,
A-023) is now performed in :mod:`selector.cli` (function ``main``).
"""

from __future__ import annotations

import logging

import pandas as pd

# Pure modules re-exported (Phase 3.3.a - already extracted).
from core.run_summary import attach_schema_version, merge_iex_bias_counters
from selector.cli import _build_arg_parser, _build_config_from_args, main
from selector.config import PRICE_COLUMNS, RUN_SUMMARY_PREFIX, AlphaScannerConfig
from selector.factors import (
    FACTOR_COLUMNS,
    compute_factor_frame,
    winsorize_and_normalize,
)
from selector.filters import (
    ELIGIBLE_HISTORY_STATUSES,
    ETF_NAME_PATTERNS,
    METADATA_COLUMNS,
    apply_filters_with_stats,
    enrich_and_filter_equities,
    log_filter_stats,
    merge_optional_symbol_overlays,
)
from selector.ranking import (
    OUTPUT_COLUMNS,
    PERSISTED_SELECTOR_SCORE_COLUMNS,
    SCORE_COLUMNS,
    apply_factor_neutralization,
    apply_sector_neutrality,
    merge_scores,
    rank_and_select,
)
from selector.run_summary import (
    _build_cli_run_summary,
    _build_run_id,
    _emit_run_summary,
    _summarize_zero_candidate_filters,
    _utc_now_naive,
)
from selector.scanner import AlphaScanner, SelectorDataQualityError

LOGGER = logging.getLogger(__name__)


__all__ = [
    "AlphaScanner",
    "SelectorDataQualityError",
    "AlphaScannerConfig",
    # Constants (preserved for backwards compatibility)
    "FACTOR_COLUMNS",
    "SCORE_COLUMNS",
    "OUTPUT_COLUMNS",
    "PERSISTED_SELECTOR_SCORE_COLUMNS",
    "METADATA_COLUMNS",
    "ETF_NAME_PATTERNS",
    "ELIGIBLE_HISTORY_STATUSES",
    "PRICE_COLUMNS",
    "RUN_SUMMARY_PREFIX",
    # Pure functions re-exported
    "compute_factor_frame",
    "winsorize_and_normalize",
    "apply_filters_with_stats",
    "log_filter_stats",
    "enrich_and_filter_equities",
    "merge_optional_symbol_overlays",
    "merge_scores",
    "apply_factor_neutralization",
    "apply_sector_neutrality",
    "rank_and_select",
    # CLI / run-summary helpers
    "main",
    "_build_arg_parser",
    "_build_config_from_args",
    "_utc_now_naive",
    "_build_run_id",
    "_emit_run_summary",
    "_build_cli_run_summary",
    "_summarize_zero_candidate_filters",
    "attach_schema_version",
    "merge_iex_bias_counters",
    "pd",
]


if __name__ == "__main__":
    main()
