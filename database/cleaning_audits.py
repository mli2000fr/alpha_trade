"""Phase 3.1.c/d — persistance des audits dédiés quotes & earnings.

Réf. ``prompt/refactor/plan.md`` Phase 3.1 + ``audit_dataIntegrityEngine.md``.

Insert une ligne par exécution dans :

- ``cleaning_audit_quotes_runs`` (sync_latest_quotes)
- ``cleaning_audit_earnings_runs`` (sync_earnings_calendar)

Volontairement minimaliste : un échec d'écriture audit ne doit JAMAIS
faire échouer le run métier (les exceptions sont absorbées + loggées).
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Literal

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from database.connection import get_sqlalchemy_engine

LOGGER = logging.getLogger(__name__)

AuditStatus = Literal["success", "failed", "partial"]

_QUOTES_TABLE = "cleaning_audit_quotes_runs"
_EARNINGS_TABLE = "cleaning_audit_earnings_runs"


def _record_run(
    table: str,
    *,
    run_id: str,
    started_at: datetime,
    finished_at: datetime,
    symbols_requested: int,
    rows_upserted: int,
    status: AuditStatus,
    error_message: str | None,
) -> None:
    duration = round((finished_at - started_at).total_seconds(), 3)
    stmt = text(
        f"""
        INSERT INTO {table}
            (run_id, started_at, finished_at, duration_seconds,
             symbols_requested, rows_upserted, status, error_message)
        VALUES
            (:run_id, :started_at, :finished_at, :duration,
             :symbols_requested, :rows_upserted, :status, :error_message)
        """
    )
    try:
        engine = get_sqlalchemy_engine()
        with engine.begin() as conn:
            conn.execute(
                stmt,
                {
                    "run_id": run_id,
                    "started_at": started_at,
                    "finished_at": finished_at,
                    "duration": duration,
                    "symbols_requested": int(symbols_requested),
                    "rows_upserted": int(rows_upserted),
                    "status": status,
                    "error_message": (error_message or None),
                },
            )
    except (SQLAlchemyError, Exception):  # noqa: BLE001 - best-effort audit.
        # Audit best-effort : ne jamais casser le run métier.
        LOGGER.warning(
            "Echec persistance audit %s | run_id=%s status=%s (audit ignoré).",
            table,
            run_id,
            status,
        )


def record_quotes_audit_run(
    *,
    run_id: str,
    started_at: datetime,
    finished_at: datetime,
    symbols_requested: int,
    rows_upserted: int,
    status: AuditStatus = "success",
    error_message: str | None = None,
) -> None:
    """Phase 3.1.c — insère une ligne dans ``cleaning_audit_quotes_runs``."""
    _record_run(
        _QUOTES_TABLE,
        run_id=run_id,
        started_at=started_at,
        finished_at=finished_at,
        symbols_requested=symbols_requested,
        rows_upserted=rows_upserted,
        status=status,
        error_message=error_message,
    )


def record_earnings_audit_run(
    *,
    run_id: str,
    started_at: datetime,
    finished_at: datetime,
    symbols_requested: int,
    rows_upserted: int,
    status: AuditStatus = "success",
    error_message: str | None = None,
) -> None:
    """Phase 3.1.d — insère une ligne dans ``cleaning_audit_earnings_runs``."""
    _record_run(
        _EARNINGS_TABLE,
        run_id=run_id,
        started_at=started_at,
        finished_at=finished_at,
        symbols_requested=symbols_requested,
        rows_upserted=rows_upserted,
        status=status,
        error_message=error_message,
    )


__all__ = [
    "AuditStatus",
    "record_earnings_audit_run",
    "record_quotes_audit_run",
]

