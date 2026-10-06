from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database.router import get_market_engine  # noqa: E402
from service.tushare.adapters import adapt_staging_row  # noqa: E402
from service.tushare.models import TusharePage  # noqa: E402
from service.tushare.storage import finish_run, persist_page, start_run  # noqa: E402

DEFAULT_OUTPUT = ROOT / "artifacts" / "audits" / "market_integration" / "sprint_06" / "synthetic_smoke.json"


def _page(close_price: str) -> TusharePage:
    row = {
        "ts_code": "600000.SH",
        "trade_date": "20260918",
        "open": "10.00",
        "high": "10.80",
        "low": "9.90",
        "close": close_price,
        "pre_close": "10.00",
        "change": str(float(close_price) - 10.0),
        "pct_chg": str((float(close_price) / 10.0 - 1.0) * 100.0),
        "vol": "123456.00",
        "amount": "130000.00",
    }
    return TusharePage(
        endpoint="daily",
        fields=tuple(row),
        rows=(row,),
        request_payload={"api_name": "daily", "params": {"trade_date": "20260918"}, "token": "***"},
        response_payload={"code": 0, "data": {"fields": list(row), "items": [list(row.values())]}},
        http_status=200,
        provider_code=0,
    )


def run(output_path: Path) -> dict[str, Any]:
    engine = get_market_engine("CN_A", database_alias="cn_primary")
    suffix = uuid.uuid4().hex[:8]
    run_ids = [f"sprint6-smoke-{suffix}-{index}" for index in range(1, 4)]
    closes = ["10.60", "10.60", "10.70"]
    persisted_by_run: list[int] = []
    observed_at = datetime.now(UTC).replace(tzinfo=None)
    try:
        for run_id, close_price in zip(run_ids, closes, strict=True):
            start_run(
                engine,
                run_id=run_id,
                batch_name="sprint6_synthetic_smoke",
                market_code="CN_A",
                database_alias="cn_primary",
            )
            page = _page(close_price)
            adapted = [
                adapt_staging_row(
                    "daily",
                    page.rows[0],
                    run_id=run_id,
                    raw_id=None,
                    observed_at=observed_at,
                    available_at=observed_at,
                )
            ]
            _raw_count, persisted = persist_page(
                engine,
                page=page,
                page_key="0:0",
                run_id=run_id,
                observed_at=observed_at,
                available_at=observed_at,
                adapted_rows=adapted,
            )
            persisted_by_run.append(persisted)
            finish_run(
                engine,
                run_id=run_id,
                status="COMPLETED",
                counters={"requested": 1, "received": 1, "persisted": persisted, "empty": 0, "failed": 0, "warnings": [], "details": {}},
                quota_calls=1,
            )
        with engine.connect() as connection:
            placeholders = ",".join(f":run{index}" for index in range(len(run_ids)))
            parameters = {f"run{index}": value for index, value in enumerate(run_ids)}
            raw_proofs = int(
                connection.execute(
                    text(f"SELECT COUNT(*) FROM cn_raw_payloads WHERE run_id IN ({placeholders})"),
                    parameters,
                ).scalar()
                or 0
            )
            business_revisions = int(
                connection.execute(
                    text(
                        "SELECT COUNT(DISTINCT payload_hash) FROM cn_staging_rows "
                        "WHERE endpoint='daily' AND provider_symbol='600000.SH' "
                        f"AND business_date='2026-09-18' AND run_id IN ({placeholders})"
                    ),
                    parameters,
                ).scalar()
                or 0
            )
        status = "PASS" if persisted_by_run == [1, 0, 1] and raw_proofs == 3 and business_revisions == 2 else "FAIL"
        report = {
            "status": status,
            "scenario": "identical replay then provider correction",
            "symbol": "600000.SH",
            "persisted_by_run": persisted_by_run,
            "raw_proofs": raw_proofs,
            "business_revisions": business_revisions,
            "canonical_writes": 0,
            "generated_at": datetime.now(UTC).isoformat(),
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return report
    finally:
        with engine.begin() as connection:
            placeholders = ",".join(f":run{index}" for index in range(len(run_ids)))
            parameters = {f"run{index}": value for index, value in enumerate(run_ids)}
            connection.execute(text(f"DELETE FROM cn_staging_rows WHERE run_id IN ({placeholders})"), parameters)
            connection.execute(text(f"DELETE FROM cn_raw_payloads WHERE run_id IN ({placeholders})"), parameters)
            connection.execute(text(f"DELETE FROM cn_ingestion_runs WHERE run_id IN ({placeholders})"), parameters)
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke synthétique idempotence/correction du staging CN")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(run(args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
