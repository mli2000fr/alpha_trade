from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine


@dataclass(frozen=True, slots=True)
class QualityResult:
    endpoint: str
    metric_name: str
    value: float | None
    threshold: float | None
    status: str
    details: dict[str, Any]


def audit_staging(
    engine: Engine,
    *,
    run_id: str,
    endpoints: list[str],
    max_age_days: int = 5,
) -> list[QualityResult]:
    results: list[QualityResult] = []
    with engine.begin() as conn:
        for endpoint in endpoints:
            row = conn.execute(
                text(
                    """SELECT COUNT(*) AS rows_count,COUNT(DISTINCT payload_hash) AS hashes,
                    DATEDIFF(UTC_DATE(),DATE(MAX(observed_at))) AS age_days
                    FROM tushare_staging_rows WHERE endpoint=:endpoint"""
                ),
                {"endpoint": endpoint},
            ).mappings().one()
            count = int(row["rows_count"] or 0)
            age = float(row["age_days"]) if row["age_days"] is not None else None
            checks = [
                QualityResult(endpoint, "row_count", float(count), 1.0, "OK" if count else "CRITICAL", {}),
                QualityResult(
                    endpoint,
                    "age_days",
                    age,
                    float(max_age_days),
                    "OK" if age is not None and age <= max_age_days else "CRITICAL",
                    {},
                ),
            ]
            for result in checks:
                conn.execute(
                    text(
                        """INSERT INTO cn_staging_quality_metrics
                        (run_id,metric_date,endpoint,metric_name,metric_value,threshold_value,status,details_json)
                        VALUES (:run,:day,:endpoint,:name,:value,:threshold,:status,:details)"""
                    ),
                    {
                        "run": run_id,
                        "day": date.today(),
                        "endpoint": result.endpoint,
                        "name": result.metric_name,
                        "value": result.value,
                        "threshold": result.threshold,
                        "status": result.status,
                        "details": json.dumps(result.details),
                    },
                )
            results.extend(checks)
    return results


__all__ = ["QualityResult", "audit_staging"]
