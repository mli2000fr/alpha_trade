"""Resume-safe CN 2026 staging and insert-only canonical catch-up.

All canonical writes are bounded to completed sessions from 2026 onwards.
Historical 2018-2025 rows are never updated by this runner.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import msvcrt
import time
import uuid
from dataclasses import asdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from database.router import get_market_engine
from dataIntegrityEngine.cn_sprint7a_pilot import collect
from service.baostock.client import BaoStockError
from service.market.cn_canonical_full import enrich_manifest, select_full_universe, write_chunks
from service.market.cn_canonicalizer import promote_pilot, read_pilot_manifest, write_pilot_manifest
from service.market.cn_completed_session_guard import require_completed_session_end

LOG = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "artifacts" / "cn" / "sprint7c_2026"
DEFAULT_MANIFEST = ROOT / "config" / "univers_cn" / "canonical_incremental_2026.txt"
DEFAULT_CHUNKS = ROOT / "config" / "univers_cn" / "sprint7c_chunks_2026"


def verify_bounds(start: date, end: date, *, allow_same_day_after_close: bool = False) -> None:
    if start < date(2026, 1, 1) or end < start:
        raise ValueError("Sprint 7-C requires a 2026-or-later nonempty interval")
    require_completed_session_end(end, allow_same_day_after_close=allow_same_day_after_close)


def _write_new_report(root: Path, action: str, payload: dict) -> Path:
    folder = root / "reports"
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    path = folder / f"{action}-{stamp}.json"
    with path.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, default=str)
    return path


def prepare(engine, *, start: date, end: date, manifest: Path,
            chunks_root: Path, chunk_size: int, seed_manifest: Path,
            allow_same_day_after_close: bool = False) -> dict:
    verify_bounds(start, end, allow_same_day_after_close=allow_same_day_after_close)
    if manifest.exists() or chunks_root.exists():
        raise FileExistsError("2026 manifest/chunks already exist; refuse overwrite")
    if chunk_size < 1:
        raise ValueError("chunk-size must be positive")
    # Stock master and calendar are fetched once, using the existing staging pipeline.
    source = collect(engine, manifest=seed_manifest, start=start, end=end,
                     endpoints=("stock_basic", "trade_cal", "index_daily"),
                     include_inactive=True, resume=True,
                     state_key=f"cn_s7c_2026_master_calendar_{start}_{end}",
                     batch_name="cn_sprint7c_prepare")
    symbols = select_full_universe(engine, start=start, end=end)
    if not symbols:
        raise RuntimeError("No CN equities selected for incremental 2026 manifest")
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest_hash = write_pilot_manifest(symbols, manifest)
    chunks = write_chunks(symbols, chunks_root, chunk_size=chunk_size)
    return {"status": "PREPARED", "start": start, "end": end,
            "symbols": len(symbols), "chunks": len(chunks),
            "manifest": str(manifest), "manifest_hash": manifest_hash,
            "source_collection": source}


def run_chunk(engine, *, start: date, end: date, manifest: Path,
              collect_source: bool = True, allow_same_day_after_close: bool = False) -> dict:
    verify_bounds(start, end, allow_same_day_after_close=allow_same_day_after_close)
    symbols = read_pilot_manifest(manifest)
    if not symbols:
        raise ValueError("Empty CN incremental chunk")
    source = None
    if collect_source:
        source = _collect_chunk_with_network_retry(engine, manifest=manifest,
                                                   start=start, end=end)
    promotion = asdict(promote_pilot(
        engine, manifest_path=manifest,
        business_start_date=start, business_end_date=end,
        allow_same_day_after_close=allow_same_day_after_close,
    ))
    enrichment = enrich_manifest(
        engine, manifest_path=manifest,
        business_start_date=start, business_end_date=end,
        allow_same_day_after_close=allow_same_day_after_close,
    )
    return {"status": "COMPLETED_WITH_WARNINGS" if promotion["status"] != "PASS" else "COMPLETED",
            "start": start, "end": end, "manifest": str(manifest),
            "symbols": len(symbols), "source_collection": source,
            "promotion": promotion, "enrichment": enrichment}


def _atomic_state(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Windows readers (including antivirus/indexers) may hold state.json briefly.
    # A unique candidate avoids reusing an orphan from an interrupted prior run.
    temporary = path.with_name(f"{path.stem}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    for attempt in range(12):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if attempt == 11:
                raise
            delay = min(0.1 * (2 ** attempt), 2.0)
            LOG.warning("cn_s7c state replace temporarily denied attempt=%d/12 retry_in=%.1fs",
                        attempt + 1, delay)
            time.sleep(delay)


def _retryable_baostock_failure(exc: Exception) -> bool:
    """Retry only transport/login failures, never canonicalization or data errors."""
    pending = [exc]
    seen: set[int] = set()
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        if isinstance(current, (TimeoutError, ConnectionError, UnicodeEncodeError)):
            return True
        if isinstance(current, OSError) and getattr(current, "winerror", None) in {10053, 10054, 10060, 10061}:
            return True
        if isinstance(current, BaoStockError):
            message = str(current).lower()
            if any(term in message for term in (
                "connexion baostock", "connection", "connect", "timeout", "timed out",
                "socket", "network", "服务器连接失败",
            )):
                return True
        pending.extend(cause for cause in (current.__cause__, current.__context__) if cause is not None)
    return False


def _collect_chunk_with_network_retry(engine, *, start: date, end: date,
                                      manifest: Path, max_attempts: int = 5) -> dict:
    if max_attempts < 1:
        raise ValueError("max_attempts must be positive")
    for attempt in range(1, max_attempts + 1):
        try:
            return collect(engine, manifest=manifest, start=start, end=end,
                           endpoints=("daily", "adj_factor"),
                           include_inactive=True, resume=True,
                           state_key=f"cn_s7c_2026_{start}_{end}_{manifest.stem}",
                           batch_name="cn_sprint7c_chunk_collect")
        except Exception as exc:
            if attempt == max_attempts or not _retryable_baostock_failure(exc):
                raise
            delay = min(15 * (2 ** (attempt - 1)), 120)
            LOG.warning("cn_s7c transient BaoStock failure attempt=%d/%d retry_in=%ds: %s",
                        attempt, max_attempts, delay, exc)
            time.sleep(delay)
    raise AssertionError("unreachable")


def run_all(engine, *, start: date, end: date, chunks_root: Path,
            output_root: Path, start_chunk: int = 0, max_chunks: int | None = None,
            allow_same_day_after_close: bool = False) -> dict:
    verify_bounds(start, end, allow_same_day_after_close=allow_same_day_after_close)
    index_path = chunks_root / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    total = int(index["chunk_count"])
    if total < 1 or len(index["chunks"]) != total:
        raise ValueError("Invalid incremental chunk index")
    if start_chunk < 0 or start_chunk >= total or (max_chunks is not None and max_chunks < 1):
        raise ValueError("Invalid incremental chunk range")
    stop = min(total, start_chunk + max_chunks) if max_chunks else total
    index_hash = hashlib.sha256(index_path.read_bytes()).hexdigest()
    state_path = output_root / "state.json"
    state = (json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists()
             else {"start": str(start), "end": str(end), "index_sha256": index_hash,
                   "chunk_count": total, "chunks": {}})
    if (state["start"], state["end"], state["index_sha256"]) != (str(start), str(end), index_hash):
        raise ValueError("Incremental resume state belongs to another campaign")
    output_root.mkdir(parents=True, exist_ok=True)
    lock_path = output_root / "run-all.lock"
    with lock_path.open("a+b") as lock:
        lock.seek(0, 2)
        if lock.tell() == 0:
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            raise RuntimeError("Another CN Sprint 7-C catch-up is running") from exc
        try:
            for index_number in range(start_chunk, stop):
                key = str(index_number)
                if state["chunks"].get(key, {}).get("status") in {"COMPLETED", "COMPLETED_WITH_WARNINGS"}:
                    continue
                manifest = chunks_root / index["chunks"][index_number]
                if manifest.resolve().parent != chunks_root.resolve():
                    raise ValueError("Chunk path escapes configured directory")
                state["chunks"][key] = {"status": "RUNNING", "started_at_utc": datetime.now(UTC).isoformat()}
                _atomic_state(state_path, state)
                LOG.info("cn_s7c chunk=%d/%d symbols=%d", index_number + 1, total,
                         len(read_pilot_manifest(manifest)))
                try:
                    chunk_kwargs = {"allow_same_day_after_close": True} if allow_same_day_after_close else {}
                    result = run_chunk(engine, start=start, end=end, manifest=manifest, **chunk_kwargs)
                    report_path = _write_new_report(output_root, f"chunk-{index_number:04d}", result)
                    state["chunks"][key] = {"status": result["status"],
                                            "report": str(report_path),
                                            "finished_at_utc": datetime.now(UTC).isoformat()}
                except Exception as exc:
                    state["chunks"][key] = {"status": "FAILED", "error": f"{type(exc).__name__}: {exc}",
                                            "finished_at_utc": datetime.now(UTC).isoformat()}
                    _atomic_state(state_path, state)
                    raise
                _atomic_state(state_path, state)
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
    completed = sum(item["status"] in {"COMPLETED", "COMPLETED_WITH_WARNINGS"}
                    for item in state["chunks"].values())
    return {"status": "COMPLETED" if completed == total else "PARTIAL",
            "completed_chunks": completed, "total_chunks": total,
            "state": str(state_path)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "run-chunk", "run-all"))
    parser.add_argument("--start-date", type=date.fromisoformat, default=date(2026, 1, 1))
    parser.add_argument("--end-date", type=date.fromisoformat,
                        default=datetime.now(ZoneInfo("Asia/Shanghai")).date() - timedelta(days=1))
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--seed-manifest", type=Path,
                        default=ROOT / "config" / "univers_cn" / "canonical_full_2018_2025.txt")
    parser.add_argument("--chunks-root", type=Path, default=DEFAULT_CHUNKS)
    parser.add_argument("--chunk-size", type=int, default=25)
    parser.add_argument("--start-chunk", type=int, default=0)
    parser.add_argument("--max-chunks", type=int)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--skip-collect", action="store_true",
                        help="Only promote already collected staging rows, never downloads")
    parser.add_argument("--allow-same-day-after-close", action="store_true",
                        help="Explicitly accept today's CN session only after 18:00 Asia/Shanghai")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper()),
                        format="%(asctime)s %(levelname)s %(message)s")
    verify_bounds(args.start_date, args.end_date,
                  allow_same_day_after_close=args.allow_same_day_after_close)
    engine = get_market_engine("CN_A", database_alias="cn_primary")
    if engine.url.database != "alpha_trade_cn":
        raise RuntimeError("Sprint 7-C refused outside alpha_trade_cn")
    try:
        if args.action == "prepare":
            payload = prepare(engine, start=args.start_date, end=args.end_date,
                              manifest=args.manifest or DEFAULT_MANIFEST,
                              chunks_root=args.chunks_root,
                              chunk_size=args.chunk_size,
                              seed_manifest=args.seed_manifest,
                              allow_same_day_after_close=args.allow_same_day_after_close)
        elif args.action == "run-chunk":
            if args.manifest is None:
                parser.error("run-chunk requires --manifest")
            payload = run_chunk(engine, start=args.start_date, end=args.end_date,
                                manifest=args.manifest,
                                collect_source=not args.skip_collect,
                                allow_same_day_after_close=args.allow_same_day_after_close)
        else:
            if args.skip_collect:
                parser.error("run-all does not accept --skip-collect")
            payload = run_all(engine, start=args.start_date, end=args.end_date,
                              chunks_root=args.chunks_root, output_root=args.output_root,
                              start_chunk=args.start_chunk, max_chunks=args.max_chunks,
                              allow_same_day_after_close=args.allow_same_day_after_close)
        report_path = _write_new_report(args.output_root, args.action, payload)
        print(json.dumps({"status": payload["status"], "report": str(report_path),
                          "symbols": payload.get("symbols"),
                          "completed_chunks": payload.get("completed_chunks"),
                          "total_chunks": payload.get("total_chunks")}, ensure_ascii=False))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
