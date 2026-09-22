"""CLI du pilote Sprint 7-A : sélection, collecte, promotion et audit."""

from __future__ import annotations

import argparse
import json
import logging
import uuid
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path

from database.router import get_market_engine
from service.baostock.client import BaoStockClient
from service.baostock.ingestion import BaoStockIngestionService
from service.market.cn_canonicalizer import (
    audit_pilot,
    promote_pilot,
    read_pilot_manifest,
    select_pilot_symbols,
    write_pilot_manifest,
)
from service.tushare.ingestion import IngestionCounters
from service.tushare.storage import finish_run, start_run

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "config" / "univers_cn" / "sprint7a_pilot_80.txt"
DEFAULT_REPORT_ROOT = ROOT / "artifacts" / "cn" / "sprint7a"


def collect(
    engine,
    *,
    manifest: Path,
    start: date,
    end: date,
    endpoints: tuple[str, ...],
    include_inactive: bool = False,
    resume: bool = False,
    state_key: str | None = None,
    batch_name: str = "cn_sprint7a_pilot_collect",
) -> dict[str, object]:
    symbols = read_pilot_manifest(manifest)
    run_id = f"{batch_name}-{datetime.now(UTC):%Y%m%d%H%M%S}-{uuid.uuid4().hex[:8]}"
    counters = IngestionCounters(details={"pilot_symbols": len(symbols), "start": start, "end": end})
    client = BaoStockClient()
    start_run(engine, run_id=run_id, batch_name=batch_name, market_code="CN_A", database_alias="cn_primary", provider="baostock")
    try:
        client.connect()
        service = BaoStockIngestionService(client=client, engine=engine, run_id=run_id, symbols=symbols, state_key=state_key or run_id)
        for endpoint in endpoints:
            counters.merge(service.collect_endpoint(endpoint, start_date=start, end_date=end, resume=resume, include_inactive=include_inactive))
        finish_run(engine, run_id=run_id, status="COMPLETED", counters=counters.to_dict(), quota_calls=client.calls)
        return {"run_id": run_id, **counters.to_dict(), "provider_calls": client.calls}
    except Exception as exc:
        counters.failed += 1
        finish_run(engine, run_id=run_id, status="FAILED", counters=counters.to_dict(), quota_calls=client.calls, error_message=str(exc))
        raise
    finally:
        client.close()


def _write_report(payload: dict[str, object]) -> Path:
    directory = DEFAULT_REPORT_ROOT / f"sprint7a-{datetime.now(UTC):%Y%m%d%H%M%S}"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "report.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Pilote canonique CN Sprint 7-A")
    parser.add_argument("action", choices=("select", "collect", "promote", "audit", "all"))
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--start-date", type=date.fromisoformat, default=date(2018, 1, 1))
    parser.add_argument("--end-date", type=date.fromisoformat, default=date(2025, 12, 31))
    parser.add_argument("--endpoints", default="trade_cal,daily,adj_factor,index_daily")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper()), format="%(asctime)s %(levelname)s %(name)s %(message)s")
    engine = get_market_engine("CN_A", database_alias="cn_primary")
    payload: dict[str, object] = {"action": args.action, "manifest": str(args.manifest), "started_at": datetime.now(UTC)}
    try:
        if args.action in {"select", "all"}:
            symbols = select_pilot_symbols(engine, as_of=args.end_date, history_start=args.start_date)
            payload["manifest_hash"] = write_pilot_manifest(symbols, args.manifest)
            payload["selected_symbols"] = len(symbols)
        if args.action in {"collect", "all"}:
            payload["collection"] = collect(engine, manifest=args.manifest, start=args.start_date, end=args.end_date, endpoints=tuple(value.strip() for value in args.endpoints.split(",") if value.strip()))
        if args.action in {"promote", "all"}:
            payload["promotion"] = asdict(promote_pilot(engine, manifest_path=args.manifest))
        if args.action in {"audit", "all"}:
            payload["audit"] = audit_pilot(engine, manifest_path=args.manifest)
        payload["finished_at"] = datetime.now(UTC)
        report = _write_report(payload)
        print(json.dumps({**payload, "report_path": str(report)}, ensure_ascii=False, indent=2, default=str))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()

