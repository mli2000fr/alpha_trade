from __future__ import annotations

from sqlalchemy import create_engine, text

from database.run_business_summaries import persist_run_business_summary


DDL = """
CREATE TABLE {table_name} (
    summary_run_id VARCHAR(96) PRIMARY KEY,
    source_run_id VARCHAR(96),
    entity_run_id VARCHAR(96),
    parent_summary_run_id VARCHAR(96),
    step_key VARCHAR(64) NOT NULL,
    run_kind VARCHAR(16) NOT NULL,
    status VARCHAR(32),
    account_id VARCHAR(64),
    trade_date DATE,
    started_at DATETIME,
    finished_at DATETIME,
    summary_json TEXT NOT NULL,
    created_at DATETIME,
    updated_at DATETIME
)
"""


def _create_tables(engine) -> None:
    with engine.begin() as conn:
        conn.execute(text(DDL.format(table_name="run_summaries")))
        conn.execute(text(DDL.format(table_name="run_business_summaries")))


def test_run_summary_persistence_populates_canonical_and_legacy_tables() -> None:
    engine = create_engine("sqlite:///:memory:")
    _create_tables(engine)

    persisted = persist_run_business_summary(
        summary={"run_id": "risk-42", "status": "completed", "target_positions": 3},
        step_key="risk_management",
        run_kind="step",
        status="completed",
        summary_run_id="risk-42",
        entity_run_id="risk-42",
        account_id="acct-1",
        trade_date="2026-05-07",
        started_at="2026-05-07T07:00:00",
        finished_at="2026-05-07T07:05:00",
        engine=engine,
    )

    with engine.connect() as conn:
        canonical = conn.execute(
            text("SELECT step_key, run_kind, summary_json FROM run_summaries WHERE summary_run_id = 'risk-42'")
        ).first()
        legacy = conn.execute(
            text("SELECT step_key, run_kind, summary_json FROM run_business_summaries WHERE summary_run_id = 'risk-42'")
        ).first()

    assert persisted == 1
    assert canonical is not None
    assert legacy is not None
    assert canonical[0] == "risk_management"
    assert canonical[1] == "step"
    assert '"schema_version": 1' in canonical[2]
    assert legacy[0] == "risk_management"
    assert legacy[1] == "step"
    assert '"schema_version": 1' in legacy[2]

