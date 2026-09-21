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
from service.baostock.client import BaoStockClient
from service.baostock.ingestion import BaoStockIngestionService
from service.tushare.accounts import load_account
from service.tushare.client import TushareClient
from service.tushare.ingestion import IngestionCounters, TushareIngestionService
from service.tushare.quality import audit_staging
from service.tushare.quota import QuotaBudget
from service.tushare.storage import finish_run, start_run

LOGGER = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[1]
SUMMARY_PREFIX = "::alpha_trade_run_summary::"
SUPPORTED_PROVIDERS = {"baostock", "tushare"}


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


def _collect_baostock(
    cfg: dict[str, Any],
    *,
    engine: Any,
    run_id: str,
    start: date | None,
    end: date,
    dry_run: bool,
) -> tuple[IngestionCounters, int]:
    counters = IngestionCounters(details={"provider": "baostock"})
    client = BaoStockClient()
    try:
        client.connect()
        service = BaoStockIngestionService(
            client=client,
            engine=engine,
            run_id=run_id,
            state_key=str(cfg.get("state_key") or run_id),
            max_symbols=int(cfg["max_symbols"]) if cfg.get("max_symbols") else None,
        )
        for endpoint in cfg.get("endpoints") or []:
            counters.merge(
                service.collect_endpoint(
                    str(endpoint),
                    start_date=start,
                    end_date=end,
                    dry_run=dry_run,
                    include_inactive=bool(cfg.get("include_inactive", False)),
                )
            )
        return counters, client.calls
    finally:
        client.close()


def _collect_tushare(
    cfg: dict[str, Any],
    *,
    engine: Any,
    run_id: str,
    start: date | None,
    end: date,
    dry_run: bool,
) -> tuple[IngestionCounters, int]:
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
        state_key=str(cfg.get("state_key") or run_id),
    )
    counters = IngestionCounters(details={"provider": "tushare", "token_fingerprint": account.fingerprint})
    for endpoint in cfg.get("endpoints") or []:
        counters.merge(
            service.collect_endpoint(
                str(endpoint), start_date=start, end_date=end, dry_run=dry_run
            )
        )
    return counters, quota.calls


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
    provider = str(cfg.get("provider") or "baostock").strip().lower()
    if provider not in SUPPORTED_PROVIDERS and job_name != "cn_staging_quality_daily":
        raise RuntimeError(f"Fournisseur CN non pris en charge : {provider}")
    market_code = str(cfg.get("market_code") or "CN_A")
    database_alias = str(cfg.get("database_alias") or "cn_primary")
    resolve_database_route(database_alias, market_code)
    engine = get_market_engine(market_code, database_alias=database_alias)
    run_id = f"{job_name}-{datetime.now(UTC):%Y%m%d%H%M%S}-{uuid.uuid4().hex[:8]}"
    counters = IngestionCounters(details={"market_code": market_code, "database_alias": database_alias})
    calls = 0
    if not dry_run:
        start_run(
            engine,
            run_id=run_id,
            batch_name=job_name,
            market_code=market_code,
            database_alias=database_alias,
            provider="quality" if job_name == "cn_staging_quality_daily" else provider,
        )
    try:
        if job_name == "cn_staging_quality_daily":
            results = (
                audit_staging(
                    engine,
                    run_id=run_id,
                    endpoints=list(cfg.get("endpoints") or []),
                    max_age_days=int(cfg.get("max_age_days", 5)),
                )
                if not dry_run
                else []
            )
            counters.requested = counters.received = counters.persisted = len(results)
            counters.failed = sum(result.status == "CRITICAL" for result in results)
            counters.details["critical"] = counters.failed
        else:
            effective_end = end_date or _parse_date(cfg.get("end_date")) or date.today()
            effective_start = start_date or _parse_date(cfg.get("start_date"))
            if effective_start is None and cfg.get("lookback_days") is not None:
                effective_start = effective_end - timedelta(days=int(cfg["lookback_days"]))
            if provider == "baostock":
                counters, calls = _collect_baostock(
                    cfg,
                    engine=engine,
                    run_id=run_id,
                    start=effective_start,
                    end=effective_end,
                    dry_run=dry_run,
                )
            else:
                counters, calls = _collect_tushare(
                    cfg,
                    engine=engine,
                    run_id=run_id,
                    start=effective_start,
                    end=effective_end,
                    dry_run=dry_run,
                )
        if counters.failed and not counters.warnings:
            counters.warnings.append(f"{counters.failed} contrôle(s) ou élément(s) en échec")
        status = "DRY_RUN" if dry_run else ("COMPLETED_WITH_WARNINGS" if counters.warnings else "COMPLETED")
        if not dry_run:
            finish_run(engine, run_id=run_id, status=status, counters=counters.to_dict(), quota_calls=calls)
        return status, counters
    except Exception as exc:
        counters.failed = max(1, counters.failed)
        if not dry_run:
            finish_run(
                engine,
                run_id=run_id,
                status="FAILED",
                counters=counters.to_dict(),
                quota_calls=calls,
                error_message=str(exc),
            )
        raise CnBatchRunError(str(exc), counters) from exc
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingestion multi-fournisseurs vers le staging alpha_trade_cn")
    parser.add_argument("--job", required=True)
    parser.add_argument("--batch-config", type=Path, default=ROOT / "batch_cn.yaml")
    parser.add_argument("--force", action="store_true")
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
    print(
        SUMMARY_PREFIX
        + json.dumps({"batch": args.job, "status": status, **counters.to_dict()}, ensure_ascii=False, default=str),
        flush=True,
    )


if __name__ == "__main__":
    main()
