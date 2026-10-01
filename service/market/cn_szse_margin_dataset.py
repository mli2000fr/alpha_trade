"""15-B4: resumable SZSE-only daily dataset; research artifacts, no DB writes."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import logging
import os
import time
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlencode

import yaml
from sqlalchemy import text

from database.router import get_market_engine
from service.market.cn_margin_lending_blocker_audit import archive
from service.market.cn_margin_lending_contract_audit import eligibility_rows, proxy_available_at
from service.market.cn_margin_lending_pilot import (
    SZSE_FIELDS,
    _write_json,
    read_xlsx_rows,
)

LOG = logging.getLogger(__name__)
CONFIG = Path("config/research_cn/sprint15b4_szse_margin.yaml")
OUTPUT = Path("artifacts/research/cn_margin_lending/sprint15b4_szse_daily")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checkpoint(path: Path, obj: dict) -> None:
    for attempt in range(6):
        try:
            _write_json(path, obj)
            return
        except PermissionError:
            if attempt == 5:
                raise
            time.sleep(0.2)


def integer_value(value: str) -> int:
    parsed = Decimal(value.replace(",", ""))
    if not parsed.is_finite() or parsed < 0 or parsed != parsed.to_integral_value():
        raise ValueError(f"Invalid whole monetary/quantity value: {value}")
    return int(parsed)


def fetch_day(output: Path, key: str, catalog: str, tab: str, name: str, sources: dict) -> bytes:
    q = {"SHOWTYPE": "xlsx", "CATALOGID": catalog, "txtDate": key, "TABKEY": tab}
    return archive(output, key + name, "https://www.szse.cn/api/report/ShowReport?"
                   + urlencode(q), sources)


def reference_snapshot(instruments: list[dict], sessions: list) -> dict:
    return {
        "instruments": [{**item,
                         "listing_date": item["listing_date"].isoformat() if item["listing_date"] else None,
                         "delisting_date": item["delisting_date"].isoformat() if item["delisting_date"] else None}
                        for item in instruments],
        "sessions": [[d.isoformat(), t.isoformat() if t else None] for d, t in sessions],
    }


def dated_equities(instruments: list[dict], day: date) -> dict:
    result = {}
    for item in instruments:
        if item["listing_date"] is None or item["listing_date"] > day:
            continue
        if item["delisting_date"] is not None and item["delisting_date"] < day:
            continue
        code = item["local_symbol"]
        if code in result:
            raise ValueError(f"Ambiguous historical instrument: {code}/{day}")
        result[code] = item["instrument_id"]
    return result


def build_rows(day: date, eligible_raw: bytes, detail_raw: bytes,
               active: dict, bars: dict, proxy: str | None) -> tuple[list[dict], dict]:
    flags = eligibility_rows(eligible_raw)
    details = {}
    for row in read_xlsx_rows(detail_raw):
        code = row["证券代码"].zfill(6)
        if code in details:
            raise ValueError(f"Duplicate detail: {code}")
        details[code] = {field: integer_value(row[field]) for field in SZSE_FIELDS}
        if details[code]["融资余额"] + details[code]["融券余额"] != details[code]["融资融券余额"]:
            raise ValueError(f"Unreconciled combined balance: {code}")
    rows = []
    target = {code for code, f in flags.items() if f["融资标的"] or f["融券标的"]}
    for code in sorted(target & active.keys()):
        observed = details.get(code)
        bar = bars.get(active[code])
        amount = float(bar["amount"]) if bar and bar["amount"] is not None else None
        reasons = []
        if observed is None:
            reasons.append("ELIGIBLE_WITHOUT_OBSERVATION")
        if proxy is None:
            reasons.append("CALENDAR_PROXY_UNAVAILABLE")
        if amount is None or amount <= 0 or not bar["trading_status"].startswith("TRADE"):
            reasons.append("BAR_AMOUNT_UNAVAILABLE_OR_NOT_TRADING")
        intensity = observed["融资买入额"] / amount if observed and amount and amount > 0 else None
        if reasons:
            intensity = None
        rows.append({
            "market_code": "CN_A", "exchange_mic": "XSHE", "source_session": day.isoformat(),
            "instrument_id": active[code], "local_symbol": code, **flags[code],
            "observation_status": "ELIGIBLE_WITHOUT_OBSERVATION" if observed is None else
            "OBSERVED_ZERO" if not any(observed.values()) else "OBSERVED",
            "measures": observed, "amount_cny": amount,
            "financing_buy_to_amount": intensity,
            "bar_observed_at": str(bar["observed_at"]) if bar else None,
            "bar_available_at_recorded": str(bar["available_at"]) if bar else None,
            "research_available_at_proxy": proxy, "quality_reasons": reasons,
            "historical_vintage_proven": False, "strict_ml_allowed": False,
        })
    return rows, {
        "eligible_equities": len(target & active.keys()),
        "observed_equities": sum(r["measures"] is not None for r in rows),
        "valid_feature_rows": sum(not r["quality_reasons"] for r in rows),
        "non_equity_or_outside_reference": len((target | details.keys()) - active.keys()),
        "detail_outside_eligible": sorted(details.keys() - target),
        "missing_eligible": sorted((target & active.keys()) - details.keys()),
        "source_detail_rows": len(details),
    }


def run(*, config: Path, output: Path, start: date | None, end: date | None,
        pause: float, plan_only: bool = False) -> dict:
    cfg = yaml.safe_load(config.read_text(encoding="utf-8"))
    if (cfg["experiment"] != "cn_sprint15b4_szse_margin_proxy_v1"
            or cfg["exchange_mic"] != "XSHE" or cfg["market_code"] != "CN_A"
            or cfg["database_alias"] != "cn_primary"
            or cfg["strict_ml_allowed"] is not False or cfg["proxy_lag_sessions"] != 2):
        raise ValueError("Invalid locked research protocol")
    first = start or date.fromisoformat(cfg["start"])
    last = end or date.fromisoformat(cfg["end"])
    if first < date.fromisoformat(cfg["start"]) or last > date.fromisoformat(cfg["end"]) or last < first:
        raise ValueError("Dates outside preregistered range")
    if pause < 0:
        raise ValueError("Negative pause")
    engine = get_market_engine("CN_A", database_alias="cn_primary")
    with engine.connect() as conn:
        sessions = conn.execute(text(
            "SELECT session_date,close_at_utc FROM market_sessions WHERE market_code='CN_A' "
            "AND session_status='open' ORDER BY session_date")).all()
        instruments = [dict(r) for r in conn.execute(text(
            "SELECT instrument_id,local_symbol,listing_date,delisting_date FROM instruments "
            "WHERE market_code='CN_A' AND exchange_mic='XSHE' AND instrument_type='equity'"
        )).mappings()]
    days = [d for d, _ in sessions if first <= d <= last]
    if not days or any(year not in {d.year for d in days} for year in range(first.year, last.year + 1)):
        raise ValueError("Missing requested calendar years/sessions")
    plan = {"planned_sessions": len(days), "maximum_new_requests": 2 * len(days),
            "start": first.isoformat(), "end": last.isoformat()}
    if plan_only:
        return plan
    output.mkdir(parents=True, exist_ok=True)
    lock = output / ".lock"
    with lock.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps({"pid": os.getpid(), "started_at": datetime.now(UTC).isoformat()}))
    try:
        state_path = output / "state.json"
        contract = {**plan, "config_sha256": sha(config),
                    "implementation_sha256": sha(Path(__file__)),
                    "session_dates": [d.isoformat() for d in days]}
        state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {
            "contract": contract, "status": "RUNNING", "sessions": {},
            "strict_ml_allowed": False, "historical_vintage_proven": False}
        if state["contract"] != contract:
            raise ValueError("Existing dataset contract differs; choose another output root")
        snapshot_path = output / "reference_snapshot.json"
        if snapshot_path.exists():
            if sha(snapshot_path) != state.get("reference_sha256"):
                raise ValueError("Altered reference snapshot")
            frozen = json.loads(snapshot_path.read_text(encoding="utf-8"))
            instruments = frozen["instruments"]
            for item in instruments:
                for field in ("listing_date", "delisting_date"):
                    item[field] = date.fromisoformat(item[field]) if item[field] else None
            sessions = [(date.fromisoformat(d), datetime.fromisoformat(t) if t else None)
                        for d, t in frozen["sessions"]]
        else:
            checkpoint(snapshot_path, reference_snapshot(instruments, sessions))
            state["reference_sha256"] = sha(snapshot_path)
        checkpoint(state_path, state)
        for day in days:
            key = day.isoformat()
            old = state["sessions"].get(key, {})
            partition = output / f"{key}.jsonl.gz"
            if old.get("status") == "COMPLETED":
                if sha(partition) != old["partition_sha256"]:
                    raise ValueError(f"Altered completed partition: {key}")
                for name, item in old["sources"].items():
                    if sha(output / name) != item["sha256"]:
                        raise ValueError(f"Altered completed raw: {key}")
                continue
            state["status"] = "RUNNING"
            state["sessions"][key] = {"status": "RUNNING", "started_at": datetime.now(UTC).isoformat()}
            checkpoint(state_path, state)
            try:
                sources = {"sources": {}}
                eligible = fetch_day(output, key, "1834_xxpl", "tab1", "_eligible.xlsx", sources)
                time.sleep(pause)
                detail = fetch_day(output, key, "1837_xxpl", "tab2", "_detail.xlsx", sources)
                try:
                    proxy = proxy_available_at(day, sessions).isoformat()
                except ValueError:
                    proxy = None
                with engine.connect() as conn:
                    bars = {r["instrument_id"]: dict(r) for r in conn.execute(text(
                        "SELECT instrument_id,amount,trading_status,observed_at,available_at "
                        "FROM stock_bars_daily WHERE market_code='CN_A' AND date=:day"
                    ), {"day": day}).mappings()}
                rows, stats = build_rows(day, eligible, detail, dated_equities(instruments, day), bars, proxy)
                raw = "\n".join(json.dumps(r, ensure_ascii=False) for r in rows).encode("utf-8")
                temp = partition.with_suffix(".tmp")
                temp.write_bytes(gzip.compress(raw, mtime=0))
                temp.replace(partition)
                state["sessions"][key] = {
                    "status": "COMPLETED", **stats, "partition_sha256": sha(partition),
                    "sources": sources["sources"], "finished_at": datetime.now(UTC).isoformat(),
                    "proxy_missing": proxy is None}
                LOG.info("%s completed %s/%s equities; feature_rows=%s", key,
                         stats["observed_equities"], stats["eligible_equities"], stats["valid_feature_rows"])
            except Exception as exc:
                state["sessions"][key] = {"status": "FAILED", "error": str(exc)}
                LOG.exception("failed date=%s", key)
            checkpoint(state_path, state)
            time.sleep(pause)
        complete = [r for r in state["sessions"].values() if r["status"] == "COMPLETED"]
        failed = sum(r["status"] == "FAILED" for r in state["sessions"].values())
        state["status"] = "COMPLETED_COLLECTION_PROXY_ONLY" if not failed else "PARTIAL_FAILURE"
        state["summary"] = {"completed": len(complete), "failed": failed,
                            "rows": sum(r["eligible_equities"] for r in complete),
                            "observed": sum(r["observed_equities"] for r in complete),
                            "valid_feature_rows": sum(r["valid_feature_rows"] for r in complete),
                            "proxy_missing_days": sum(r["proxy_missing"] for r in complete)}
        threshold = cfg["data_gates"]["min_eligible_equity_coverage"]
        good_days = sum(r["eligible_equities"] > 0 and not r["detail_outside_eligible"]
                        and r["observed_equities"] / r["eligible_equities"] >= threshold
                        for r in complete)
        state["summary"]["valid_coverage_day_fraction"] = good_days / len(days)
        state["data_coverage_gate_passed"] = (
            failed == 0 and len(complete) == len(days)
            and good_days / len(days) >= cfg["data_gates"]["min_valid_day_fraction"])
        state["training_ready"] = False  # Joining labels/rolling features is a separate audited step.
        checkpoint(state_path, state)
        return state
    finally:
        lock.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--output-root", type=Path, default=OUTPUT)
    parser.add_argument("--start-date", type=date.fromisoformat)
    parser.add_argument("--end-date", type=date.fromisoformat)
    parser.add_argument("--pause-seconds", type=float, default=0.5)
    parser.add_argument("--plan-only", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    result = run(config=args.config, output=args.output_root, start=args.start_date,
                 end=args.end_date, pause=args.pause_seconds, plan_only=args.plan_only)
    print(json.dumps(result.get("summary", result.get("contract", result)), default=str))
    if result.get("status") == "PARTIAL_FAILURE":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
