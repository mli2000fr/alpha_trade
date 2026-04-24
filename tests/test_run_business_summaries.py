from __future__ import annotations

from sqlalchemy import create_engine, text

from database.run_business_summaries import parse_summary_json, persist_run_business_summary


def _create_table(engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE run_business_summaries (
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
        """))


def test_persist_run_business_summary_inserts_and_updates() -> None:
    engine = create_engine("sqlite:///:memory:")
    _create_table(engine)

    inserted = persist_run_business_summary(
        summary={"run_id": "risk-1", "targeted_symbols": 5},
        step_key="risk_management",
        run_kind="step",
        status="completed",
        summary_run_id="risk-1",
        entity_run_id="risk-1",
        engine=engine,
    )
    updated = persist_run_business_summary(
        summary={"run_id": "risk-1", "targeted_symbols": 7},
        step_key="risk_management",
        run_kind="step",
        status="completed",
        summary_run_id="risk-1",
        entity_run_id="risk-1",
        engine=engine,
    )

    with engine.connect() as conn:
        row = conn.execute(text("SELECT summary_json FROM run_business_summaries WHERE summary_run_id = 'risk-1'"))
        payload = row.scalar_one()

    assert inserted == 1
    assert updated == 1
    assert '"targeted_symbols": 7' in payload


def test_parse_summary_json_handles_invalid_payload() -> None:
    assert parse_summary_json('{"ok": 1}') == {"ok": 1}
    assert parse_summary_json("{broken") == {}
    assert parse_summary_json(None) == {}

