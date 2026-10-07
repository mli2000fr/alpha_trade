"""Orchestrateur reprenable de canonicalisation complète CN (Sprint 7-B)."""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from database.router import get_market_engine
from dataIntegrityEngine.cn_sprint7a_pilot import collect
from service.market.cn_canonical_full import (
    audit_full,
    enrich_manifest,
    measure_coverage,
    remediate_historical_quality,
    select_full_universe,
    write_chunks,
)
from service.market.cn_canonicalizer import promote_pilot, write_pilot_manifest

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "config" / "univers_cn" / "canonical_full_2018_2025.txt"
DEFAULT_CHUNKS = ROOT / "config" / "univers_cn" / "sprint7b_chunks_2018_2025"
DEFAULT_ARTIFACTS = ROOT / "artifacts" / "cn" / "sprint7b"


class Sprint7BState:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"chunks": {}}

    def status(self, index: int) -> str | None:
        return self.payload.get("chunks", {}).get(str(index), {}).get("status")

    def update(self, index: int, *, status: str, details: dict[str, Any] | None = None) -> None:
        self.payload.setdefault("chunks", {})[str(index)] = {
            "status": status,
            "updated_at": datetime.now(UTC).isoformat(),
            "details": details or {},
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        temporary.replace(self.path)


def _chunk_path(root: Path, index: int) -> Path:
    path = root / f"chunk_{index:04d}.txt"
    if not path.exists():
        raise FileNotFoundError(f"Lot Sprint 7-B absent : {path}")
    return path


def run_chunk(
    engine,
    *,
    index: int,
    chunks_root: Path,
    start: date,
    end: date,
    state: Sprint7BState,
    force: bool = False,
) -> dict[str, Any]:
    if state.status(index) == "COMPLETED" and not force:
        return {"chunk": index, "status": "SKIPPED_COMPLETED"}
    manifest = _chunk_path(chunks_root, index)
    state.update(index, status="RUNNING", details={"manifest": str(manifest)})
    try:
        collection = collect(
            engine,
            manifest=manifest,
            start=start,
            end=end,
            endpoints=("daily", "adj_factor"),
            include_inactive=True,
            resume=True,
            state_key=f"cn_sprint7b_{start}_{end}_chunk_{index:04d}",
            batch_name="cn_sprint7b_full_collect",
        )
        promotion = asdict(promote_pilot(engine, manifest_path=manifest))
        enrichment = enrich_manifest(engine, manifest_path=manifest)
        result = {"chunk": index, "status": "COMPLETED", "collection": collection, "promotion": promotion, "enrichment": enrichment}
        state.update(index, status="COMPLETED", details=result)
        return result
    except Exception as exc:
        state.update(index, status="FAILED", details={"error": str(exc), "manifest": str(manifest)})
        raise


def _write_report(payload: dict[str, Any]) -> Path:
    directory = DEFAULT_ARTIFACTS / f"sprint7b-{datetime.now(UTC):%Y%m%d%H%M%S}"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "report.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Canonicalisation complète CN Sprint 7-B")
    parser.add_argument("action", choices=("prepare", "run-chunk", "run-all", "promote", "enrich", "coverage", "audit", "remediate-quality"))
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--chunks-root", type=Path, default=DEFAULT_CHUNKS)
    parser.add_argument("--state", type=Path, default=DEFAULT_ARTIFACTS / "state.json")
    parser.add_argument("--start-date", type=date.fromisoformat, default=date(2018, 1, 1))
    parser.add_argument("--end-date", type=date.fromisoformat, default=date(2025, 12, 31))
    parser.add_argument("--chunk-size", type=int, default=25)
    parser.add_argument("--chunk-index", type=int)
    parser.add_argument("--start-chunk", type=int, default=0)
    parser.add_argument("--max-chunks", type=int)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--apply", action="store_true", help="Confirme la remédiation historique CN")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper()), format="%(asctime)s %(levelname)s %(name)s %(message)s")
    engine = get_market_engine("CN_A", database_alias="cn_primary")
    payload: dict[str, Any] = {"action": args.action, "started_at": datetime.now(UTC), "start": args.start_date, "end": args.end_date}
    state = Sprint7BState(args.state)
    try:
        if args.action == "prepare":
            symbols = select_full_universe(engine, start=args.start_date, end=args.end_date)
            payload["manifest_hash"] = write_pilot_manifest(symbols, args.manifest)
            chunks = write_chunks(symbols, args.chunks_root, chunk_size=args.chunk_size)
            payload.update({"symbols": len(symbols), "chunks": len(chunks), "chunk_size": args.chunk_size})
        elif args.action in {"run-chunk", "promote", "enrich"}:
            if args.action == "run-chunk" and args.chunk_index is None:
                parser.error("--chunk-index est obligatoire pour run-chunk")
            manifest = (
                _chunk_path(args.chunks_root, args.chunk_index)
                if args.chunk_index is not None
                else args.manifest
            )
            if args.action == "run-chunk":
                payload["result"] = run_chunk(engine, index=args.chunk_index, chunks_root=args.chunks_root, start=args.start_date, end=args.end_date, state=state, force=args.force)
            elif args.action == "promote":
                payload["promotion"] = asdict(promote_pilot(engine, manifest_path=manifest))
            else:
                payload["enrichment"] = enrich_manifest(engine, manifest_path=manifest)
        elif args.action == "run-all":
            index_data = json.loads((args.chunks_root / "index.json").read_text(encoding="utf-8"))
            stop = int(index_data["chunk_count"])
            if args.max_chunks is not None:
                stop = min(stop, args.start_chunk + args.max_chunks)
            results = []
            for index in range(args.start_chunk, stop):
                results.append(run_chunk(engine, index=index, chunks_root=args.chunks_root, start=args.start_date, end=args.end_date, state=state, force=args.force))
            payload["results"] = results
        elif args.action == "coverage":
            payload["coverage"] = measure_coverage(engine, manifest_path=args.manifest, start=args.start_date, end=args.end_date)
        elif args.action == "audit":
            payload["audit"] = audit_full(engine, manifest_path=args.manifest)
        elif args.action == "remediate-quality":
            if not args.apply:
                parser.error("remediate-quality exige --apply")
            payload["quality_remediation"] = remediate_historical_quality(
                engine, start=args.start_date, end=args.end_date
            )
        payload["finished_at"] = datetime.now(UTC)
        report = _write_report(payload)
        print(json.dumps({**payload, "report_path": str(report)}, ensure_ascii=False, indent=2, default=str))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
