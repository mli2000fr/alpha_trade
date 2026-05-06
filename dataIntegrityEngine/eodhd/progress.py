"""Helpers progress / run_summary pour l'ingestion EODHD."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from core.run_summary import attach_schema_version


RUN_SUMMARY_PREFIX = "::alpha_trade_run_summary::"
PROGRESS_LOG_FIRST_SYMBOLS = 10
PROGRESS_LOG_EVERY = 100


def utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def build_run_id(prefix: str = "import-eodhd") -> str:
    return f"{prefix}-{utc_now_naive().strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6]}"


def emit_run_summary(summary: dict[str, Any]) -> None:
    print(
        f"{RUN_SUMMARY_PREFIX}{json.dumps(summary, ensure_ascii=False, sort_keys=True, default=str)}",
        flush=True,
    )


def emit_live_progress_summary(summary: dict[str, Any]) -> None:
    live_summary = dict(summary)
    emit_run_summary(attach_schema_version(live_summary))


def should_log_symbol_progress(index: int, total: int) -> bool:
    if total <= 0 or index <= 0:
        return False
    return (
        index <= min(PROGRESS_LOG_FIRST_SYMBOLS, total)
        or index % PROGRESS_LOG_EVERY == 0
        or index == total
    )


__all__ = [
    "RUN_SUMMARY_PREFIX",
    "PROGRESS_LOG_FIRST_SYMBOLS",
    "PROGRESS_LOG_EVERY",
    "utc_now_naive",
    "build_run_id",
    "emit_run_summary",
    "emit_live_progress_summary",
    "should_log_symbol_progress",
]

