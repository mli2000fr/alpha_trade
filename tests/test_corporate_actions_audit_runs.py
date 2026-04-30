"""Phase 5.3.b — Tests audit dédié `corporate_actions_audit_runs`.

Réf. ``prompt/refactor/plan_phase5.md`` § 5.3.b.
"""
from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import create_engine, text

from corporate_actions.db_io import CorporateActionRepository


SQLITE_AUDIT_SCHEMA = """
    CREATE TABLE corporate_actions_audit_runs (
        run_id VARCHAR(64) PRIMARY KEY,
        run_kind VARCHAR(16) NOT NULL,
        account_id VARCHAR(64),
        started_at TIMESTAMP NOT NULL,
        finished_at TIMESTAMP NOT NULL,
        duration_seconds REAL DEFAULT 0,
        fetched INT DEFAULT 0,
        inserted INT DEFAULT 0,
        duplicates INT DEFAULT 0,
        invalid INT DEFAULT 0,
        applied INT DEFAULT 0,
        skipped INT DEFAULT 0,
        failed INT DEFAULT 0,
        reconcile_diffs INT DEFAULT 0,
        anomalies_json TEXT,
        status VARCHAR(16) DEFAULT 'completed',
        summary_json BLOB,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
"""


@pytest.fixture()
def repo() -> CorporateActionRepository:
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text(SQLITE_AUDIT_SCHEMA))
    return CorporateActionRepository(engine=engine)


def test_persist_audit_run_inserts_row(repo: CorporateActionRepository) -> None:
    started = datetime(2026, 4, 26, 10, 0, 0)
    finished = datetime(2026, 4, 26, 10, 0, 30)
    repo.persist_audit_run(
        run_id="ca-sync-001",
        run_kind="sync",
        account_id="live1",
        started_at=started,
        finished_at=finished,
        stats={"fetched": 12, "inserted": 10, "duplicates": 2, "invalid": 0},
        anomalies=[{"symbol": "AAPL", "kind": "missing_in_yahoo"}],
        status="completed",
        summary={"foo": "bar"},
    )
    with repo.engine.connect() as conn:
        row = conn.execute(text("SELECT * FROM corporate_actions_audit_runs WHERE run_id=:r"), {"r": "ca-sync-001"}).mappings().one()
    assert row["run_kind"] == "sync"
    assert row["account_id"] == "live1"
    assert int(row["fetched"]) == 12
    assert int(row["inserted"]) == 10
    assert float(row["duration_seconds"]) == pytest.approx(30.0)
    assert "missing_in_yahoo" in str(row["anomalies_json"])
    assert row["summary_json"] is not None


def test_persist_audit_run_no_table_is_silent(tmp_path) -> None:
    """Best-effort : si la table n'existe pas, l'erreur est avalée."""
    engine = create_engine("sqlite:///:memory:")
    repo = CorporateActionRepository(engine=engine)
    # Ne doit pas lever malgré l'absence de la table.
    repo.persist_audit_run(
        run_id="ghost",
        run_kind="sync",
        account_id=None,
        started_at=datetime.now(),
        finished_at=datetime.now(),
    )

