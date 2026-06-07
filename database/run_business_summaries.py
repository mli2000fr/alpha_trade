from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from functools import lru_cache
from typing import Any, Mapping
from uuid import uuid4

from sqlalchemy import Column, Date, DateTime, MetaData, String, Table, Text, inspect, select

from database.connection import get_sqlalchemy_engine

# Phase 1 refactor : tous les payloads run_summary doivent porter
# ``schema_version`` (helper transverse).
from core.run_summary import attach_schema_version

LOGGER = logging.getLogger(__name__)
RUN_SUMMARY_PREFIX = "::alpha_trade_run_summary::"
PRIMARY_SUMMARY_TABLE_NAME = "run_summaries"
LEGACY_SUMMARY_TABLE_NAME = "run_business_summaries"


@lru_cache(maxsize=2)
def _build_summary_table(table_name: str) -> Table:
    metadata = MetaData()
    return Table(
        table_name,
        metadata,
        Column("summary_run_id", String(96), primary_key=True),
        Column("source_run_id", String(96), nullable=True),
        Column("entity_run_id", String(96), nullable=True),
        Column("parent_summary_run_id", String(96), nullable=True),
        Column("step_key", String(64), nullable=False),
        Column("run_kind", String(16), nullable=False),
        Column("status", String(32), nullable=True),
        Column("account_id", String(64), nullable=True),
        Column("trade_date", Date, nullable=True),
        Column("started_at", DateTime, nullable=True),
        Column("finished_at", DateTime, nullable=True),
        Column("summary_json", Text, nullable=False),
        Column("created_at", DateTime, nullable=True),
        Column("updated_at", DateTime, nullable=True),
    )


def get_run_summaries_table() -> Table:
    return _build_summary_table(PRIMARY_SUMMARY_TABLE_NAME)


def get_run_business_summaries_table() -> Table:
    return _build_summary_table(LEGACY_SUMMARY_TABLE_NAME)


def build_summary_run_id(prefix: str) -> str:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    return f"{prefix}-{now.strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6]}"


def emit_run_summary(summary: Mapping[str, Any]) -> None:
    payload = attach_schema_version(summary)
    print(
        f"{RUN_SUMMARY_PREFIX}{json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)}",
        flush=True,
    )


def _coerce_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        try:
            return datetime.fromisoformat(cleaned.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            return None
    return None


def _coerce_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        try:
            return date.fromisoformat(cleaned[:10])
        except ValueError:
            return None
    return None


def _table_exists(engine, table_name: str) -> bool:
    try:
        return inspect(engine).has_table(table_name)
    except Exception:
        return False


def _resolve_summary_tables(engine) -> tuple[Table, ...]:
    tables: list[Table] = []
    if _table_exists(engine, PRIMARY_SUMMARY_TABLE_NAME):
        tables.append(get_run_summaries_table())
    if _table_exists(engine, LEGACY_SUMMARY_TABLE_NAME):
        legacy_table = get_run_business_summaries_table()
        if not tables or legacy_table.name != tables[0].name:
            tables.append(legacy_table)
    return tuple(tables)


def _serialize_summary(summary: Mapping[str, Any]) -> str:
    return json.dumps(attach_schema_version(summary), ensure_ascii=False, sort_keys=True, default=str)


def persist_run_business_summary(
    *,
    summary: Mapping[str, Any],
    step_key: str,
    run_kind: str = "step",
    status: str | None = None,
    summary_run_id: str | None = None,
    source_run_id: str | None = None,
    entity_run_id: str | None = None,
    parent_summary_run_id: str | None = None,
    account_id: str | None = None,
    trade_date: Any = None,
    started_at: Any = None,
    finished_at: Any = None,
    engine=None,
) -> int:
    if not summary:
        return 0

    resolved_engine = engine or get_sqlalchemy_engine()
    target_tables = _resolve_summary_tables(resolved_engine)
    if not target_tables:
        LOGGER.debug("Table run_business_summaries absente ; persistance du résumé ignorée.")
        return 0

    resolved_summary_run_id = summary_run_id or source_run_id or entity_run_id or build_summary_run_id(step_key)
    payload = {
        "summary_run_id": resolved_summary_run_id,
        "source_run_id": source_run_id,
        "entity_run_id": entity_run_id,
        "parent_summary_run_id": parent_summary_run_id,
        "step_key": step_key,
        "run_kind": run_kind,
        "status": status,
        "account_id": account_id,
        "trade_date": _coerce_date(trade_date),
        "started_at": _coerce_datetime(started_at),
        "finished_at": _coerce_datetime(finished_at),
        "summary_json": _serialize_summary(summary),
    }

    with resolved_engine.begin() as conn:
        for table in target_tables:
            exists = conn.execute(
                select(table.c.summary_run_id).where(table.c.summary_run_id == resolved_summary_run_id).limit(1)
            ).scalar_one_or_none()
            if exists is None:
                conn.execute(table.insert().values(**payload))
            else:
                conn.execute(
                    table.update().where(table.c.summary_run_id == resolved_summary_run_id).values(**payload)
                )
    return 1


def persist_pipeline_run_record_summary(record: Mapping[str, Any], *, engine=None) -> int:
    summary = record.get("run_summary")
    if not isinstance(summary, Mapping) or not summary:
        return 0

    source_run_id = str(record.get("run_id", "") or "") or None
    summary_run_id = source_run_id or None
    entity_run_id_raw = summary.get("run_id")
    entity_run_id = str(entity_run_id_raw).strip() if entity_run_id_raw not in (None, "") else source_run_id
    trade_date = summary.get("trade_date") or summary.get("market_date")

    return persist_run_business_summary(
        summary=summary,
        step_key=str(record.get("step_key", "") or "unknown"),
        run_kind=str(record.get("run_kind", "step") or "step"),
        status=str(record.get("status", "") or "") or None,
        summary_run_id=summary_run_id,
        source_run_id=source_run_id,
        entity_run_id=entity_run_id,
        parent_summary_run_id=str(record.get("parent_run_id", "") or "") or None,
        account_id=str(record.get("account_id", "") or "") or None,
        trade_date=trade_date,
        started_at=record.get("executed_at") or summary.get("started_at"),
        finished_at=record.get("finished_at") or summary.get("finished_at"),
        engine=engine,
    )


def parse_summary_json(raw_value: Any) -> dict[str, Any]:
    if isinstance(raw_value, Mapping):
        return dict(raw_value)
    if not isinstance(raw_value, str) or not raw_value.strip():
        return {}
    try:
        parsed = json.loads(raw_value)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}

