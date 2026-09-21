from __future__ import annotations

import argparse
import json
import logging
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

from database.router import get_market_engine, resolve_database_route
from service.tushare.accounts import load_account
from service.tushare.client import TushareClient
from service.tushare.ingestion import IngestionCounters, TushareIngestionService
from service.tushare.quality import audit_staging
from service.tushare.quota import QuotaBudget
from service.tushare.storage import finish_run, start_run

LOGGER = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[1]
SUMMARY_PREFIX = "::alpha_trade_run_summary::"


class CnBatchRunError(RuntimeError):
    """Conserve les compteurs partiels pour les notifications d'échec."""

    def __init__(self, message: str, counters: IngestionCounters) -> None:
        super().__init__(message)
        self.counters = counters


def _parse_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    return date.fromisoformat(str(value))


def load_job(path: Path, job_name: str) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    defaults = payload.get("defaults") or {}
    job = payload.get(job_name)
    if not isinstance(job, dict):
        raise KeyError(f"Batch CN absent : {job_name}")
    return {**defaults, **job}


def execute(
    job_name: str,
    *,
    config_path: Path,
    force: bool = False,
    dry_run: bool = False,
    start_date: date | None = None,
    end_date: date | None = None,
) -> tuple[str, IngestionCounters]:
    cfg = load_job(config_path, job_name)
    if not cfg.get("enabled", False) and not force:
        return "SKIPPED_DISABLED", IngestionCounters(details={"reason": "disabled"})
    if cfg.get("canonical_writes_enabled", False):
        raise RuntimeError("Sprint 6 interdit toute écriture canonique CN")
    market_code = str(cfg.get("market_code") or "CN_A")
    database_alias = str(cfg.get("database_alias") or "cn_primary")
    resolve_database_route(database_alias, market_code)
    engine = get_market_engine(market_code, database_alias=database_alias)
    timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    run_id = f"{job_name}-{timestamp}-{uuid.uuid4().hex[:8]}"
    counters = IngestionCounters(details={"market_code": market_code, "database_alias": database_alias})
    client: TushareClient | None = None
    if not dry_run:
        start_run(
            engine,
            run_id=run_id,
            batch_name=job_name,
            market_code=market_code,
            database_alias=database_alias,
        )
    try:
        if job_name == "cn_staging_quality_daily":
            results = audit_staging(
                engine,
                run_id=run_id,
                endpoints=list(cfg.get("endpoints") or []),
                max_age_days=int(cfg.get("max_age_days", 5)),
            ) if not dry_run else []
            counters.requested = len(results)
            counters.received = len(results)
            counters.persisted = len(results)
            counters.failed = sum(result.status == "CRITICAL" for result in results)
            counters.details["critical"] = counters.failed
        else:
            account = load_account(str(cfg.get("token_env") or "TUSHARE_TOKEN"))
            quota = QuotaBudget(
                max_calls_per_minute=int(cfg.get("max_calls_per_minute", 180)),
                max_calls_per_run=int(cfg.get("max_calls_per_run", 10_000)),
            )
            client = TushareClient(account.token, quota=quota)
            service = TushareIngestionService(
                client=client,
                engine=engine,
                run_id=run_id,
                page_limit=int(cfg.get("page_limit", 5000)),
                state_key=job_name,
            )
            effective_end = end_date or _parse_date(cfg.get("end_date")) or date.today()
            effective_start = start_date or _parse_date(cfg.get("start_date"))
            if effective_start is None and cfg.get("lookback_days") is not None:
                effective_start = effective_end - timedelta(days=int(cfg["lookback_days"]))
            for endpoint in cfg.get("endpoints") or []:
                counters.merge(
                    service.collect_endpoint(
                        str(endpoint),
                        start_date=effective_start,
                        end_date=effective_end,
                        dry_run=dry_run,
                    )
                )
            counters.details["token_fingerprint"] = account.fingerprint
        if counters.failed and not counters.warnings:
            counters.warnings.append(f"{counters.failed} contrôle(s) ou élément(s) en échec")
        status = "DRY_RUN" if dry_run else ("COMPLETED_WITH_WARNINGS" if counters.warnings else "COMPLETED")
        if not dry_run:
            finish_run(
                engine,
                run_id=run_id,
                status=status,
                counters=counters.to_dict(),
                quota_calls=client.quota.calls if client else 0,
            )
        return status, counters
    except Exception as exc:
        counters.failed = max(1, counters.failed)
        if not dry_run:
            finish_run(
                engine,
                run_id=run_id,
                status="FAILED",
                counters=counters.to_dict(),
                quota_calls=client.quota.calls if client else 0,
                error_message=str(exc),
            )
        if isinstance(exc, CnBatchRunError):
            raise
        raise CnBatchRunError(str(exc), counters) from exc
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingestion brute Tushare vers alpha_trade_cn")
    parser.add_argument("--job", required=True)
    parser.add_argument("--batch-config", type=Path, default=ROOT / "batch_cn.yaml")
    parser.add_argument("--force", action="store_true", help="Autorise un lancement manuel d'un job désactivé")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--start-date", type=date.fromisoformat)
    parser.add_argument("--end-date", type=date.fromisoformat)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    try:
        status, counters = execute(
            args.job,
            config_path=args.batch_config,
            force=args.force,
            dry_run=args.dry_run,
            start_date=args.start_date,
            end_date=args.end_date,
        )
    except Exception as exc:
        counters = exc.counters if isinstance(exc, CnBatchRunError) else IngestionCounters(failed=1)
        summary = {
            "batch": args.job,
            "status": "FAILED",
            **counters.to_dict(),
            "warning_count": len(counters.warnings),
            "error_message": str(exc),
        }
        print(SUMMARY_PREFIX + json.dumps(summary, ensure_ascii=False, default=str), flush=True)
        raise
    summary = {"batch": args.job, "status": status, **counters.to_dict()}
    print(SUMMARY_PREFIX + json.dumps(summary, ensure_ascii=False, default=str), flush=True)


if __name__ == "__main__":
    main()
