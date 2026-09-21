from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from service.tushare.adapters import canonical_json, payload_hash
from service.tushare.models import TusharePage

STAGING_INSERT = text(
    """INSERT IGNORE INTO tushare_staging_rows
    (run_id,raw_id,provider,endpoint,market_code,provider_symbol,entity_key,
     business_date,payload_hash,observed_at,available_at,source_revision,name,
     exchange_code,board_code,status_code,open_price,high_price,low_price,
     close_price,pre_close,volume,amount,adjustment_factor,limit_up,limit_down,
     is_open,list_date,delist_date,reason_text,raw_payload)
    VALUES
    (:run_id,:raw_id,:provider,:endpoint,:market_code,:provider_symbol,:entity_key,
     :business_date,:payload_hash,:observed_at,:available_at,:source_revision,:name,
     :exchange_code,:board_code,:status_code,:open_price,:high_price,:low_price,
     :close_price,:pre_close,:volume,:amount,:adjustment_factor,:limit_up,:limit_down,
     :is_open,:list_date,:delist_date,:reason_text,:raw_payload)"""
)


def utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def start_run(
    engine: Engine,
    *,
    run_id: str,
    batch_name: str,
    market_code: str,
    database_alias: str,
) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """INSERT INTO cn_ingestion_runs
                (run_id,batch_name,market_code,database_alias,provider,status,started_at)
                VALUES (:run,:batch,:market,:alias,'tushare','RUNNING',:started)"""
            ),
            {
                "run": run_id,
                "batch": batch_name,
                "market": market_code,
                "alias": database_alias,
                "started": utcnow_naive(),
            },
        )


def finish_run(
    engine: Engine,
    *,
    run_id: str,
    status: str,
    counters: dict[str, Any],
    quota_calls: int,
    error_message: str | None = None,
) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """UPDATE cn_ingestion_runs SET
                status=:status,finished_at=:finished,requested_count=:requested,
                received_count=:received,persisted_count=:persisted,
                empty_count=:empty,failed_count=:failed,warning_count=:warnings,
                quota_calls=:quota,error_message=:error,details_json=:details
                WHERE run_id=:run"""
            ),
            {
                "status": status,
                "finished": utcnow_naive(),
                "requested": int(counters.get("requested", 0)),
                "received": int(counters.get("received", 0)),
                "persisted": int(counters.get("persisted", 0)),
                "empty": int(counters.get("empty", 0)),
                "failed": int(counters.get("failed", 0)),
                "warnings": len(counters.get("warnings", [])),
                "quota": int(quota_calls),
                "error": str(error_message)[:65535] if error_message else None,
                "details": json.dumps(counters.get("details", {}), ensure_ascii=False, default=str),
                "run": run_id,
            },
        )


def persist_page(
    engine: Engine,
    *,
    page: TusharePage,
    page_key: str,
    run_id: str,
    observed_at: datetime,
    available_at: datetime,
    adapted_rows: list[dict[str, Any]],
) -> tuple[int, int]:
    request_hash = payload_hash(page.request_payload)
    raw_hash = payload_hash(page.response_payload)
    raw_payload = canonical_json(page.response_payload)
    source_revision = max(
        (str(row.get("source_revision")) for row in adapted_rows if row.get("source_revision")),
        default=None,
    )
    with engine.begin() as conn:
        raw_result = conn.execute(
            text(
                """INSERT IGNORE INTO tushare_raw_payloads
                (run_id,provider,endpoint,request_hash,page_key,payload_hash,http_status,
                 provider_code,observed_at,available_at,source_revision,raw_payload)
                VALUES (:run,'tushare',:endpoint,:request_hash,:page_key,:payload_hash,
                        :http_status,:provider_code,:observed,:available,:revision,:payload)"""
            ),
            {
                "run": run_id,
                "endpoint": page.endpoint,
                "request_hash": request_hash,
                "page_key": page_key,
                "payload_hash": raw_hash,
                "http_status": page.http_status,
                "provider_code": page.provider_code,
                "observed": observed_at,
                "available": available_at,
                "revision": source_revision,
                "payload": raw_payload,
            },
        )
        raw_id = conn.execute(
            text(
                """SELECT raw_id FROM tushare_raw_payloads
                WHERE run_id=:run AND endpoint=:endpoint AND request_hash=:request_hash
                  AND page_key=:page_key"""
            ),
            {
                "run": run_id,
                "endpoint": page.endpoint,
                "request_hash": request_hash,
                "page_key": page_key,
                "payload_hash": raw_hash,
            },
        ).scalar_one()
        persisted = 0
        for row in adapted_rows:
            row["raw_id"] = raw_id
            persisted += max(0, conn.execute(STAGING_INSERT, row).rowcount)
    return max(0, raw_result.rowcount), persisted


__all__ = ["finish_run", "persist_page", "start_run", "utcnow_naive"]
