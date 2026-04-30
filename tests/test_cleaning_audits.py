"""Phase 3.1.c/d — tests des audits dédiés quotes/earnings.

Vérifie :
- ``record_quotes_audit_run`` insère bien une ligne dans
  ``cleaning_audit_quotes_runs``.
- ``record_earnings_audit_run`` insère bien une ligne dans
  ``cleaning_audit_earnings_runs``.
- Une erreur DB côté audit ne propage pas (best-effort).
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine, text


@pytest.fixture
def sqlite_engine_with_audit_tables(monkeypatch):
    engine = create_engine("sqlite://", future=True)
    with engine.begin() as conn:
        for table in ("cleaning_audit_quotes_runs", "cleaning_audit_earnings_runs"):
            conn.execute(
                text(
                    f"""
                    CREATE TABLE {table} (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        run_id TEXT NOT NULL UNIQUE,
                        started_at TEXT NOT NULL,
                        finished_at TEXT,
                        duration_seconds REAL,
                        symbols_requested INTEGER NOT NULL DEFAULT 0,
                        rows_upserted INTEGER NOT NULL DEFAULT 0,
                        status TEXT NOT NULL DEFAULT 'success',
                        error_message TEXT,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )

    from database import cleaning_audits

    monkeypatch.setattr(cleaning_audits, "get_sqlalchemy_engine", lambda: engine)
    return engine


def test_record_quotes_audit_run_persists_row(sqlite_engine_with_audit_tables) -> None:
    from database.cleaning_audits import record_quotes_audit_run

    started = datetime(2026, 4, 27, 12, 0, 0)
    finished = started + timedelta(seconds=15)
    record_quotes_audit_run(
        run_id="quotes-test-001",
        started_at=started,
        finished_at=finished,
        symbols_requested=120,
        rows_upserted=118,
        status="success",
    )

    with sqlite_engine_with_audit_tables.connect() as conn:
        row = conn.execute(
            text(
                "SELECT run_id, symbols_requested, rows_upserted, status, duration_seconds "
                "FROM cleaning_audit_quotes_runs"
            )
        ).fetchone()
    assert row is not None
    assert row[0] == "quotes-test-001"
    assert row[1] == 120
    assert row[2] == 118
    assert row[3] == "success"
    assert row[4] == pytest.approx(15.0, abs=0.001)


def test_record_earnings_audit_run_persists_failure(sqlite_engine_with_audit_tables) -> None:
    from database.cleaning_audits import record_earnings_audit_run

    started = datetime(2026, 4, 27, 13, 0, 0)
    finished = started + timedelta(seconds=4)
    record_earnings_audit_run(
        run_id="earnings-test-002",
        started_at=started,
        finished_at=finished,
        symbols_requested=50,
        rows_upserted=0,
        status="failed",
        error_message="Finnhub 429 rate limit",
    )

    with sqlite_engine_with_audit_tables.connect() as conn:
        row = conn.execute(
            text(
                "SELECT run_id, status, rows_upserted, error_message "
                "FROM cleaning_audit_earnings_runs"
            )
        ).fetchone()
    assert row == ("earnings-test-002", "failed", 0, "Finnhub 429 rate limit")


def test_record_quotes_audit_run_swallows_db_errors(monkeypatch) -> None:
    """Phase 3.1.c — un échec DB sur l'audit ne doit pas casser le run métier."""
    from database import cleaning_audits

    class _BrokenEngine:
        def begin(self):  # pragma: no cover - stub
            raise RuntimeError("engine indisponible")

    monkeypatch.setattr(cleaning_audits, "get_sqlalchemy_engine", lambda: _BrokenEngine())

    started = datetime(2026, 4, 27, 14, 0, 0)
    # Doit retourner sans lever (même si l'engine est cassé).
    cleaning_audits.record_quotes_audit_run(
        run_id="quotes-test-fail",
        started_at=started,
        finished_at=started + timedelta(seconds=1),
        symbols_requested=10,
        rows_upserted=0,
        status="failed",
        error_message="boom",
    )

