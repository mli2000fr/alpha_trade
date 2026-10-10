"""Read-only daily integrity gate for the CN prospective D6/D9/D10 pipeline.

D9 remains the sole scheduled owner of canonical CN daily writes. This job
never collects, canonicalizes, trains, serves or reconstructs missed forecasts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import uuid
from contextlib import suppress
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml
from sqlalchemy import text

from database.router import get_market_engine
from service.market.cn_canonicalizer import INDEX_SYMBOLS, read_pilot_manifest
from service.market.cn_dragon_tiger_schedule_15d6 import adjacent_open, is_open, load_calendar
from service.market.cn_oracle_daily_15d9 import _verify_manifest_chunks, verify_published

ROOT = Path(__file__).resolve().parents[2]
SHANGHAI = ZoneInfo("Asia/Shanghai")
BATCH_NAME = "cn_daily_quality_17c"


def _path(base: Path, value: str) -> Path:
    candidate = Path(value)
    return candidate if candidate.is_absolute() else base / candidate


def plan(now: datetime, calendar: dict, *, earliest: time = time(23, 30),
         audit_previous_day_before_open: bool = False) -> dict:
    if now.tzinfo is None:
        raise ValueError("CN quality time must be timezone-aware")
    local = now.astimezone(SHANGHAI)
    # Paris evening is already the following civil day in Shanghai. Audit
    # yesterday only, never an older session substituted across holidays.
    overnight = audit_previous_day_before_open and local.time() < time(9, 15)
    session = local.date() - timedelta(days=1) if overnight else local.date()
    if not is_open(session, calendar):
        return {"status": "SKIP_CLOSED", "session": session.isoformat()}
    if not overnight and local.time() < earliest:
        return {"status": "SKIP_BEFORE_WINDOW", "session": session.isoformat()}
    return {"status": "DUE", "session": session.isoformat(),
            "previous_session": adjacent_open(session, calendar, -1).isoformat(),
            "next_session": adjacent_open(session, calendar, 1).isoformat()}


def _read_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def _digest(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _latest_run(folder: Path, session: str, *, now: datetime) -> dict | None:
    for path in sorted(folder.glob("run-*.json"), reverse=True):
        report = _read_json(path)
        finished = datetime.fromisoformat(report["finished_at_utc"]) if report and report.get("finished_at_utc") else None
        if report and report.get("session") == session and finished and finished <= now.astimezone(UTC):
            return report
    return None


def _snapshot(folder: Path, phase: str, *, next_session: str, now: datetime) -> dict | None:
    for path in sorted(folder.glob("snapshot-*.json"), reverse=True):
        item = _read_json(path)
        context = item.get("collection_context") or {}
        if context.get("phase") != phase or context.get("next_open_session") != next_session:
            continue
        observed = datetime.fromisoformat(item["observed_at_utc"])
        cutoff = datetime.fromisoformat(context["decision_cutoff_shanghai"])
        if observed <= now.astimezone(UTC) and observed < cutoff.astimezone(UTC):
            return item
    return None


def read_evidence(engine, *, cfg: dict, d9_cfg: dict, base: Path,
                  session: date, previous: date, next_session: date,
                  now: datetime) -> dict:
    """Read bounded, indexed CN rows plus immutable research artifacts."""
    if engine.url.database != "alpha_trade_cn":
        raise RuntimeError("CN quality refused outside alpha_trade_cn")
    day = session.isoformat()
    decision = next_session.isoformat()
    manifest = _path(base, d9_cfg["manifest_root"]) / f"canonical_incremental_{day}.txt"
    chunk_root = _path(base, d9_cfg["chunks_root"]) / day
    state = _read_json(_path(base, d9_cfg["collection_root"]) / day / "state.json")
    index = _read_json(chunk_root / "index.json")
    symbols = read_pilot_manifest(manifest) if manifest.is_file() else []
    if index and index.get("symbol_count") != len(symbols):
        raise RuntimeError("CN D9 index/manifest symbol count mismatch")
    chunk_manifest_verified = False
    if manifest.is_file() and index:
        with suppress(OSError, KeyError, ValueError, RuntimeError):
            chunk_manifest_verified = _verify_manifest_chunks(manifest, chunk_root) == int(index["chunk_count"])
    chunk_status = [item.get("status") for item in (state or {}).get("chunks", {}).values()]
    run = _latest_run(_path(base, d9_cfg["output_root"]) / "runs", day, now=now)
    with engine.connect() as conn:
        params = {"market": "CN_A", "day": session, "source": "baostock",
                  "known": now.astimezone(UTC).replace(tzinfo=None),
                  "closed": datetime.combine(session, time(15, 0), SHANGHAI)
                  .astimezone(UTC).replace(tzinfo=None)}
        market_session = conn.execute(text(
            "SELECT session_status,close_at_utc FROM market_sessions "
            "WHERE market_code=:market AND session_date=:day"), params).mappings().first()
        bars = conn.execute(text(
            "SELECT COUNT(*) bars,COUNT(DISTINCT instrument_id) unique_instruments,"
            "SUM(high<low OR high<open OR high<close OR low>open OR low>close OR volume<0 OR amount<0) invalid_ohlc,"
            "SUM(trading_status LIKE 'SUSPENDED%' AND volume>0) suspended_with_volume,"
            "SUM(available_at IS NULL OR source_payload_hash IS NULL) missing_lineage,"
            "SUM(available_at>:known OR observed_at>:known) future_lineage,"
            "SUM(available_at<:closed) preclose_lineage "
            "FROM stock_bars_daily WHERE market_code=:market AND date=:day"), params).mappings().one()
        index_rows = conn.execute(text(
            "SELECT symbol FROM stock_bars_daily WHERE market_code=:market AND date=:day "
            "AND symbol IN ('sh.000001','sz.399001','sh.000300','sz.399006')"), params).scalars().all()
        equity_and_limits = conn.execute(text(
            "SELECT COUNT(*) equity_bars,SUM(l.instrument_id IS NOT NULL) limits_matched,"
            "SUM(l.instrument_id IS NOT NULL AND (l.policy_code IS NULL OR l.policy_code='UNKNOWN')) unknown "
            "FROM stock_bars_daily b JOIN instruments i ON i.instrument_id=b.instrument_id "
            "AND i.instrument_type='equity' LEFT JOIN cn_daily_price_limits l "
            "ON l.instrument_id=b.instrument_id AND l.session_date=b.date "
            "WHERE b.market_code=:market AND b.date=:day"), params).mappings().one()
        staging = {}
        for endpoint in ("daily", "adj_factor", "index_daily"):
            row = conn.execute(text(
                "SELECT COUNT(*) rows_count,COUNT(DISTINCT provider_symbol) symbols "
                "FROM cn_staging_rows WHERE endpoint=:endpoint AND business_date=:day "
                "AND market_code=:market"), {**params, "endpoint": endpoint}).one()
            staging[endpoint] = {"rows": int(row[0]), "symbols": int(row[1])}
        factor_matches = int(conn.execute(text(
            "SELECT COUNT(DISTINCT f.instrument_id) FROM cn_staging_rows s "
            "JOIN instrument_provider_symbols ips ON ips.provider='baostock' "
            "AND ips.provider_symbol=s.provider_symbol "
            "JOIN instrument_adjustment_factors f ON f.instrument_id=ips.instrument_id "
            "AND f.effective_date=:day AND f.provider='baostock' "
            "WHERE s.endpoint='adj_factor' AND s.business_date=:day AND s.market_code=:market"
        ), params).scalar_one())
    oracle_folder = _path(base, d9_cfg["oracle_output_root"]) / decision
    try:
        oracle = verify_published(oracle_folder, decision=next_session)
        oracle_error = None
    except (OSError, KeyError, ValueError, RuntimeError) as exc:
        oracle = None
        oracle_error = f"{type(exc).__name__}: {exc}"
    try:
        current_oracle = verify_published(
            _path(base, d9_cfg["oracle_output_root"]) / day, decision=session)
        current_oracle_error = None
    except (OSError, KeyError, ValueError, RuntimeError) as exc:
        current_oracle = None
        current_oracle_error = f"{type(exc).__name__}: {exc}"
    d6_root = _path(base, cfg["d6_snapshot_root"])
    before = _snapshot(d6_root / previous.isoformat(), "before_open",
                       next_session=day, now=now)
    after = _snapshot(d6_root / day, "after_close",
                      next_session=decision, now=now)
    d10_root = _path(base, cfg["d10_output_root"])
    d10_report_path = d10_root / day / "report.json"
    d10_pairs_path = d10_root / day / "outcome_blind_matches.parquet"
    d10 = _read_json(d10_report_path)
    d10_run = _latest_run(d10_root / "runs", day, now=now)
    return {"session": day, "previous_session": previous.isoformat(),
            "audit_at_utc": now.astimezone(UTC).isoformat(),
            "next_session": decision, "manifest_symbols": len(symbols),
            "chunk_expected": int((index or {}).get("chunk_count") or 0),
            "chunk_recorded": len(chunk_status),
            "chunk_completed": sum(status == "COMPLETED" for status in chunk_status),
            "chunk_failed": sum(status == "FAILED" for status in chunk_status),
            "chunk_manifest_verified": chunk_manifest_verified,
            "d9_run": run, "market_session": dict(market_session) if market_session else None,
            "bars": {key: int(value or 0) for key, value in bars.items()},
            "equity_bars": int(equity_and_limits["equity_bars"] or 0),
            "index_symbols": sorted(index_rows),
            "limits": {"count_rows": int(equity_and_limits["limits_matched"] or 0),
                       "unknown": int(equity_and_limits["unknown"] or 0)},
            "staging": staging, "factor_matches": factor_matches,
            "oracle": oracle, "oracle_error": oracle_error,
            "current_oracle": current_oracle, "current_oracle_error": current_oracle_error,
            "d6_before": before, "d6_after": after, "d10": d10,
            "d10_run": d10_run, "d10_report_sha256": _digest(d10_report_path),
            "d10_pairs_sha256": _digest(d10_pairs_path)}


def evaluate(evidence: dict, *, minimum_bar_ratio: float = 0.995) -> list[dict]:
    """Apply predeclared per-session checks; no source writes or model labels."""
    if not 0 < minimum_bar_ratio <= 1:
        raise ValueError("Invalid minimum bar coverage")
    checks: list[dict] = []

    def add(name: str, ok: bool, value, expected, *, severity="CRITICAL") -> None:
        checks.append({"name": name, "status": "PASS" if ok else severity,
                       "value": value, "expected": expected})

    expected = evidence["manifest_symbols"]
    completed = evidence["chunk_completed"]
    chunks = evidence["chunk_expected"]
    add("manifest_nonempty", expected > 0, expected, ">0")
    add("chunks_complete", chunks > 0 and evidence["chunk_manifest_verified"] and completed == chunks
        and evidence["chunk_recorded"] == chunks and evidence["chunk_failed"] == 0,
        {"expected": chunks, "recorded": evidence["chunk_recorded"], "completed": completed,
         "failed": evidence["chunk_failed"]}, "all COMPLETED")
    run = evidence["d9_run"] or {}
    add("d9_owner_completed", run.get("status") == "COMPLETED_RESEARCH_ONLY"
        and int(run.get("completed_chunks") or 0) == chunks,
        {"status": run.get("status"), "completed_chunks": run.get("completed_chunks")},
        "D9 COMPLETED_RESEARCH_ONLY")
    session = evidence["market_session"] or {}
    add("open_session_canonical", session.get("session_status") == "open"
        and session.get("close_at_utc") is not None, session.get("session_status"), "open")
    bars = evidence["bars"]
    index_count = len(set(evidence["index_symbols"]) & set(INDEX_SYMBOLS))
    equities = evidence["equity_bars"]
    ratio = equities / expected if expected else 0.0
    add("equity_bar_coverage", expected > 0 and ratio >= minimum_bar_ratio,
        {"equity_bars": equities, "expected": expected, "ratio": round(ratio, 6)},
        f">={minimum_bar_ratio:.3f}")
    add("required_indices", index_count == len(INDEX_SYMBOLS), index_count, len(INDEX_SYMBOLS))
    add("unique_bars", bars["bars"] == bars["unique_instruments"],
        bars["unique_instruments"], bars["bars"])
    for name in ("invalid_ohlc", "suspended_with_volume", "missing_lineage",
                 "future_lineage", "preclose_lineage"):
        add(name, bars[name] == 0, bars[name], 0)
    daily = evidence["staging"]["daily"]["symbols"]
    indices = evidence["staging"]["index_daily"]["symbols"]
    factors = evidence["staging"]["adj_factor"]["symbols"]
    add("daily_staging_to_canonical", daily >= equities, daily, f">={equities}")
    add("index_staging_complete", indices >= len(INDEX_SYMBOLS), indices, len(INDEX_SYMBOLS))
    add("factors_promoted", evidence["factor_matches"] == factors,
        evidence["factor_matches"], factors)
    add("limit_coverage", evidence["limits"]["count_rows"] >= equities,
        evidence["limits"]["count_rows"], f">={equities}")
    add("unknown_limit_policies", evidence["limits"]["unknown"] == 0,
        evidence["limits"]["unknown"], 0)
    oracle = evidence["oracle"] or {}
    oracle_timely = bool(oracle) and all(
        datetime.fromisoformat(oracle[key]) <= datetime.fromisoformat(evidence["audit_at_utc"])
        for key in ("score_available_at_utc", "export_published_at_utc")
    )
    add("oracle_next_decision", oracle_timely and oracle.get("previous_session") == evidence["session"]
        and int((oracle.get("quality") or {}).get("top20") or 0) > 0,
        {"decision": oracle.get("decision_date"), "error": evidence["oracle_error"]},
        evidence["next_session"])
    before, after = evidence["d6_before"], evidence["d6_after"]
    add("d6_before_open_snapshot", bool(before) and int((before.get("counts") or {}).get("events") or 0) > 0,
        int((before or {}).get("counts", {}).get("events") or 0), ">0", severity="WARNING")
    add("d6_after_close_snapshot", bool(after) and int((after.get("counts") or {}).get("events") or 0) > 0,
        int((after or {}).get("counts", {}).get("events") or 0), ">0", severity="WARNING")
    d10 = evidence["d10"] or {}
    d10_run = evidence["d10_run"] or {}
    current = evidence["current_oracle"] or {}
    add("d10_outcome_blind_match", bool(current) and d10.get("outcomes_loaded") is False
        and d10.get("database_modified") is False
        and datetime.fromisoformat(current["export_published_at_utc"]) <= datetime.fromisoformat(evidence["audit_at_utc"])
        and d10.get("candidate_sha256") == current.get("candidate_export_sha256")
        and d10.get("status") in {"MATCHING_READY_FOR_SEPARATE_OUTCOME_AUDIT",
                                  "INSUFFICIENT_PROSPECTIVE_MATCHED_SAMPLE",
                                  "INSUFFICIENT_MATCH_BALANCE"}
        and d10_run.get("status") == "COMPLETED_RESEARCH_ONLY"
        and evidence["d10_report_sha256"] is not None
        and evidence["d10_pairs_sha256"] is not None
        and d10_run.get("d7_report_sha256") == evidence["d10_report_sha256"]
        and d10_run.get("d7_pairs_sha256") == evidence["d10_pairs_sha256"],
        {"d10_status": d10.get("status"), "oracle_error": evidence["current_oracle_error"]},
        "outcome-blind D10 report with matching Oracle hash")
    return checks


def execute(*, batch_config: Path = ROOT / "batch_cn.yaml",
            research_config: Path = ROOT / "batch.yaml", now: datetime | None = None,
            dry_run: bool = False) -> dict:
    config = yaml.safe_load(batch_config.read_text(encoding="utf-8")) or {}
    cfg = config.get(BATCH_NAME)
    if not isinstance(cfg, dict):
        raise KeyError(f"Missing {BATCH_NAME} in batch_cn.yaml")
    if not cfg.get("enabled") or cfg.get("status") != "ACTIVE":
        return {"batch": BATCH_NAME, "status": "SKIP_DISABLED"}
    if (cfg.get("market_code") != "CN_A" or cfg.get("database_alias") != "cn_primary"
            or config.get("cn_daily_market_data_sync", {}).get("enabled")):
        raise RuntimeError("Unsafe CN quality route or duplicate canonical collector enabled")
    research = yaml.safe_load(research_config.read_text(encoding="utf-8")) or {}
    legacy_d9 = research.get("cn_oracle_prospective_daily")
    cn_d9 = config.get("cn_oracle_prospective_daily")
    if legacy_d9 is not None and cn_d9 is not None:
        raise RuntimeError("D9 is duplicated in batch.yaml and batch_cn.yaml")
    d9_cfg = cn_d9 or legacy_d9 or {}
    if not d9_cfg.get("enabled") or d9_cfg.get("status") != "RESEARCH_ONLY":
        raise RuntimeError("D9 must remain the sole enabled CN canonical daily owner")
    if cn_d9 and (cn_d9.get("market_code") != "CN_A"
                  or cn_d9.get("database_alias") != "cn_primary"):
        raise RuntimeError("D9 CN catalog route is not cn_primary/CN_A")
    base = batch_config.resolve().parent
    now = now or datetime.now(UTC)
    planned = plan(now, load_calendar(_path(base, cfg["calendar"])),
                   audit_previous_day_before_open=bool(cfg.get("audit_previous_day_before_open", False)))
    if planned["status"] != "DUE":
        return {"batch": BATCH_NAME, **planned}
    if dry_run:
        return {"batch": BATCH_NAME, **planned, "database_modified": False}
    report = {"batch": BATCH_NAME, **planned,
              "market_code": "CN_A", "database_alias": "cn_primary",
              "catalog_path": str(batch_config.resolve()),
              "started_at_utc": datetime.now(UTC).isoformat(),
              "database_modified": False, "training_performed": False,
              "serving_changed": False, "requested_count": 0, "received_count": 0,
              "persisted_count": 0, "failed_count": 0, "warning_count": 0}
    try:
        engine = get_market_engine("CN_A", database_alias="cn_primary")
        try:
            evidence = read_evidence(engine, cfg=cfg, d9_cfg=d9_cfg, base=base,
                                     session=date.fromisoformat(planned["session"]),
                                     previous=date.fromisoformat(planned["previous_session"]),
                                     next_session=date.fromisoformat(planned["next_session"]), now=now)
        finally:
            engine.dispose()
        checks = evaluate(evidence, minimum_bar_ratio=float(cfg["minimum_bar_coverage_ratio"]))
        report["evidence"] = evidence
        report["checks"] = checks
        report["requested_count"] = report["received_count"] = len(checks)
        report["persisted_count"] = sum(item["status"] == "PASS" for item in checks)
        report["failed_count"] = sum(item["status"] == "CRITICAL" for item in checks)
        report["warning_count"] = sum(item["status"] == "WARNING" for item in checks)
        report["status"] = ("FAILED" if report["failed_count"] else
                            "COMPLETED_WITH_WARNINGS" if report["warning_count"] else "COMPLETED")
        if report["failed_count"]:
            report["error_message"] = f"{report['failed_count']} critical CN daily quality checks failed"
    except Exception as exc:
        report.update(status="FAILED", failed_count=max(1, report["failed_count"]),
                      error_message=f"{type(exc).__name__}: {exc}")
    report["finished_at_utc"] = datetime.now(UTC).isoformat()
    root = _path(base, cfg["output_root"]) / "runs"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"run-{datetime.now(UTC):%Y%m%dT%H%M%S%fZ}-{uuid.uuid4().hex[:8]}.json"
    with path.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, default=str)
    report["report_path"] = str(path)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", choices=(BATCH_NAME,), required=True)
    parser.add_argument("--batch-config", type=Path, default=ROOT / "batch_cn.yaml")
    parser.add_argument("--research-config", type=Path, default=ROOT / "batch.yaml")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--probe", action="store_true")
    args = parser.parse_args()
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    result = execute(batch_config=args.batch_config, research_config=args.research_config,
                     dry_run=args.dry_run or args.probe)
    print(json.dumps(result, ensure_ascii=False, default=str))
    if args.probe:
        raise SystemExit(0 if result["status"] == "DUE" else 10)
    if result["status"] in {"COMPLETED", "COMPLETED_WITH_WARNINGS", "FAILED"}:
        summary = {"batch": BATCH_NAME,
                   "status": "FAILED" if result["status"] == "FAILED" else "SUCCESS",
                   "requested": result["requested_count"], "received": result["received_count"],
                   "persisted": result["persisted_count"], "failed": result["failed_count"],
                   "warning_count": result["warning_count"],
                   "error_message": result.get("error_message", "")}
        print("::alpha_trade_run_summary::" + json.dumps(summary, ensure_ascii=False))
    if result["status"] == "FAILED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
