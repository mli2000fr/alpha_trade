"""Décision commune des passages de secours conditionnels planifiés."""
from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from database.connection import get_sqlalchemy_engine


def has_recent_success(batch_name: str, lookback_hours: float) -> bool:
    cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=max(0.1, lookback_hours))
    if batch_name == "analyst_snapshot_collection":
        sql = text("""SELECT COUNT(*) FROM analyst_snapshot_collection_run
            WHERE status='COMPLETED' AND finished_at>=:cutoff""")
        params = {"cutoff": cutoff}
    else:
        sql = text("""SELECT COUNT(*) FROM pit_collection_runs
            WHERE batch_name=:batch
              AND status IN ('COMPLETED','COMPLETED_WITH_WARNINGS')
              AND finished_at>=:cutoff""")
        params = {"cutoff": cutoff, "batch": batch_name}
    with get_sqlalchemy_engine().connect() as conn:
        return int(conn.execute(sql, params).scalar() or 0) > 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Gate de rattrapage des batchs")
    parser.add_argument("--batch", required=True)
    parser.add_argument("--lookback-hours", required=True, type=float)
    args = parser.parse_args()
    if has_recent_success(args.batch, args.lookback_hours):
        print("SKIP_RECOVERY_ALREADY_COMPLETED")
        raise SystemExit(10)
    print("RUN_RECOVERY_PRIMARY_MISSING")


if __name__ == "__main__":
    main()
