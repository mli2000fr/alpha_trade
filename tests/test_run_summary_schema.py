from __future__ import annotations

from core.run_summary import RUN_SUMMARY_SCHEMA_VERSION, attach_schema_version
from database.run_business_summaries import get_run_summaries_table


def test_common_run_summary_schema_matches_canonical_table() -> None:
    table = get_run_summaries_table()

    assert table.name == "run_summaries"
    assert tuple(table.columns.keys()) == (
        "summary_run_id",
        "source_run_id",
        "entity_run_id",
        "parent_summary_run_id",
        "step_key",
        "run_kind",
        "status",
        "account_id",
        "trade_date",
        "started_at",
        "finished_at",
        "summary_json",
        "created_at",
        "updated_at",
    )


def test_attach_schema_version_is_idempotent() -> None:
    payload = attach_schema_version({"run_id": "abc"})

    assert payload["schema_version"] == RUN_SUMMARY_SCHEMA_VERSION
    assert attach_schema_version(payload)["schema_version"] == RUN_SUMMARY_SCHEMA_VERSION

