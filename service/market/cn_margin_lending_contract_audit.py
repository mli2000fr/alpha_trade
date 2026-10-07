"""Sprint 15-B2: dated eligibility and conservative research-only PIT contract."""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import urlencode

from sqlalchemy import text

from database.router import get_market_engine
from service.market.cn_margin_lending_pilot import (
    CODE,
    _write_json,
    active_equities,
    completed_raw_verified,
    read_xlsx_rows,
    request_bytes,
)

LOG = logging.getLogger(__name__)
FLAGS = ("融资标的", "融券标的", "当日可融资", "当日可融券")


def eligibility_rows(raw: bytes) -> dict[str, dict[str, bool]]:
    rows = read_xlsx_rows(raw)
    result = {}
    for row in rows:
        code = row["证券代码"].zfill(6)
        if not CODE.fullmatch(code) or code in result:
            raise ValueError(f"Invalid/duplicate eligibility code {code}")
        if any(row.get(field) not in {"Y", "N"} for field in FLAGS):
            raise ValueError(f"Unknown eligibility flag for {code}")
        result[code] = {field: row[field] == "Y" for field in FLAGS}
    if not result:
        raise ValueError("Empty eligibility archive")
    return result


def classify_presence(*, observed: bool, eligible: bool | None,
                      all_values_zero: bool = False) -> str:
    if observed:
        if eligible is False:
            return "OBSERVED_OUTSIDE_ELIGIBLE_LIST"
        return "OBSERVED_ZERO" if all_values_zero else "OBSERVED"
    if eligible is None:
        return "UNKNOWN_ELIGIBILITY"
    return "MISSING_SOURCE" if eligible else "INELIGIBLE"


def proxy_available_at(day: date, sessions: list[tuple[date, datetime]]) -> datetime:
    """Second subsequent open session CLOSE, explicitly NOT certified publication."""
    following = [(d, close) for d, close in sessions if d > day]
    if len(following) < 2:
        raise ValueError("Calendar cannot support conservative lag")
    close = following[1][1]
    if close is None:
        raise ValueError("Session close missing")
    if close.tzinfo is None:
        close = close.replace(tzinfo=UTC)
    return close.astimezone(UTC)


def reconcile_eligibility(eligible: dict, detail: list[dict], active: set[str]) -> dict:
    codes = {row["证券代码"].zfill(6) for row in detail}
    target = {code for code, flags in eligible.items() if flags["融资标的"] or flags["融券标的"]}
    return {
        "eligible_rows": len(eligible), "eligible_active": len(target & active),
        "detail_rows": len(detail), "eligible_without_detail": sorted(target - codes),
        "detail_outside_eligible": sorted(codes - target),
        "eligible_active_with_detail": len(target & active & codes),
        "day_financing_disabled": sum(not f["当日可融资"] for f in eligible.values()),
        "day_lending_disabled": sum(not f["当日可融券"] for f in eligible.values()),
    }


def audit_identities(root: Path, session_days: list[date]) -> dict:
    state = json.loads((root / "state.json").read_text(encoding="utf-8"))
    days = sorted(state["dates"])
    for day in days:
        if not completed_raw_verified(root, state["sessions"].get(day, {})):
            raise ValueError(f"Unverified source files: {day}")
    indices = {day.isoformat(): index for index, day in enumerate(session_days)}
    panels = {d: {row["stockCode"]: row for row in json.loads(
        (root / f"{d}_sse.json").read_bytes())["result"]} for d in days}
    residuals = []
    for previous_day, day in zip(days, days[1:], strict=False):
        if previous_day[:4] != day[:4]:
            continue
        if (previous_day not in indices or day not in indices
                or indices[day] != indices[previous_day] + 1):
            raise ValueError(f"Nonconsecutive sampled sessions: {previous_day}/{day}")
        for code, now in panels[day].items():
            old = panels[previous_day].get(code)
            if old is None:
                continue
            financing = int(now["rzye"]) - int(old["rzye"]) - int(now["rzmre"]) + int(now["rzche"])
            lending = int(now["rqyl"]) - int(old["rqyl"]) - int(now["rqmcl"]) + int(now["rqchl"])
            if abs(financing) > 1 or abs(lending) > 1:
                residuals.append({
                    "date": day, "previous_date": previous_day, "code": code,
                    "financing_residual_cny": financing, "lending_residual_units": lending,
                    "quality": "QUARANTINE_UNRECONCILED_TRANSITION",
                })
    return {"residuals": residuals,
            "financing_bad": sum(abs(r["financing_residual_cny"]) > 1 for r in residuals),
            "lending_bad": sum(abs(r["lending_residual_units"]) > 1 for r in residuals)}


def run(*, anchors: Path, weeks: Path, output_root: Path) -> dict:
    engine = get_market_engine("CN_A", database_alias="cn_primary")
    state = json.loads((anchors / "state.json").read_text(encoding="utf-8"))
    for value in state["dates"]:
        if not completed_raw_verified(anchors, state["sessions"].get(value, {})):
            raise ValueError(f"Unverified anchor files: {value}")
    with engine.connect() as conn:
        sessions = conn.execute(text(
            "SELECT session_date,close_at_utc FROM market_sessions "
            "WHERE market_code='CN_A' AND session_status='open' ORDER BY session_date"
        )).all()
    output_root.mkdir(parents=True, exist_ok=True)
    report_path = output_root / "report.json"
    report = {
        "protocol": "CN_MARGIN_LENDING_CONTRACT_AUDIT_V1",
        "market_code": "CN_A", "database_alias": "cn_primary",
        "status": "RUNNING", "dates": {}, "failures": [],
        "pit_status": "PIT_PROXY_NOT_CERTIFIED",
        "proxy_policy": "SECOND_SUBSEQUENT_SESSION_CLOSE",
        "sse_eligibility_status": "UNKNOWN_HISTORICAL_LIST",
        "strict_ml_allowed": False,
    }
    for value in state["dates"]:
        day = date.fromisoformat(value)
        try:
            path = output_root / f"{value}_szse_eligibility.xlsx"
            if not path.exists():
                query = urlencode({
                    "SHOWTYPE": "xlsx", "CATALOGID": "1834_xxpl",
                    "txtDate": value, "TABKEY": "tab1", "tab1PAGENO": "1",
                })
                raw = request_bytes(
                    "https://www.szse.cn/api/report/ShowReport?" + query,
                    referer="https://www.szse.cn/disclosure/margin/object/index.html",
                )
                path.write_bytes(raw)
            raw = path.read_bytes()
            eligible = eligibility_rows(raw)
            detail = read_xlsx_rows((anchors / f"{value}_szse.xlsx").read_bytes())
            item = reconcile_eligibility(eligible, detail, active_equities(engine, day)["szse"])
            item["raw_file"] = path.name
            item["sha256"] = hashlib.sha256(raw).hexdigest()
            item["audited_at"] = datetime.now(UTC).isoformat()
            # Keep actual observation separate from the historical proxy.
            try:
                item["research_available_at_proxy"] = proxy_available_at(day, sessions).isoformat()
            except ValueError:
                item["research_available_at_proxy"] = None
                item["calendar_status"] = "BLOCKED_CALENDAR_END"
            report["dates"][value] = item
            LOG.info("date=%s eligible=%s missing=%s outside=%s", value, len(eligible),
                     len(item["eligible_without_detail"]), len(item["detail_outside_eligible"]))
        except Exception as exc:
            report["failures"].append({"date": value, "error": str(exc)})
            LOG.exception("failed date=%s", value)
        _write_json(report_path, report)
    identities = audit_identities(weeks, [day for day, _ in sessions])
    _write_json(output_root / "quarantined_transitions.json", identities)
    report["identities"] = {k: v for k, v in identities.items() if k != "residuals"}
    report["quarantined_transitions"] = len(identities["residuals"])
    report["status"] = "COMPLETED" if not report["failures"] else "PARTIAL_FAILURE"
    report["verdict"] = "NO_GO_STRICT_PIT_UNRESOLVED_SSE_AND_VINTAGES"
    _write_json(report_path, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--anchors", type=Path, default=Path("artifacts/research/cn_margin_lending/sprint15b1_2018_2025"))
    parser.add_argument("--weeks", type=Path, default=Path("artifacts/research/cn_margin_lending/sprint15b1_june_weeks_2018_2025"))
    parser.add_argument("--output-root", type=Path, default=Path("artifacts/research/cn_margin_lending/sprint15b2_contract"))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    result = run(anchors=args.anchors, weeks=args.weeks, output_root=args.output_root)
    print(f"Sprint 15-B2: {len(result['dates'])} dates; {result['verdict']}; {args.output_root}")
    if result["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
