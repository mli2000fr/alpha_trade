"""15-D3 historical breadth and seat-structure audit, without ML or DB writes."""

from __future__ import annotations

import argparse
import json
import logging
import re
import urllib.parse
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import text

from database.router import get_market_engine
from service.market.cn_dragon_tiger_pilot_15d2 import (
    SZSE_URL, _get, _json, run as reconcile,
)

LOG = logging.getLogger(__name__)
YEARS = tuple(range(2018, 2026))


def choose_dates(sessions: list[str]) -> tuple[str, str]:
    """Fixed calendar terciles; deterministic and independent of outcomes."""
    if len(sessions) < 3 or sessions != sorted(set(sessions)):
        raise ValueError("Need at least three sorted, distinct sessions")
    return sessions[len(sessions) // 3], sessions[(2 * len(sessions)) // 3]


def selected_calendar_dates() -> tuple[str, ...]:
    engine = get_market_engine("CN_A", database_alias="cn_primary")
    result = []
    with engine.connect() as connection:
        for year in YEARS:
            sessions = [
                row[0].isoformat() if isinstance(row[0], date) else str(row[0])[:10]
                for row in connection.execute(
                    text("SELECT session_date FROM market_sessions "
                         "WHERE market_code='CN_A' AND session_status='open' "
                         "AND session_date BETWEEN :start AND :end ORDER BY session_date"),
                    {"start": f"{year}-01-01", "end": f"{year}-12-31"},
                )
            ]
            result.extend(choose_dates(sessions))
    return tuple(result)


def _parts(value: str) -> list[str]:
    return [part.strip() for part in (value or "").split(",") if part.strip()]


def seat_integrity(row: dict[str, str]) -> dict[str, Any]:
    if row.get("exchange") != "SSE":
        raise ValueError("SSE seat integrity only")
    details = {}
    for side in ("buy", "sell"):
        names = _parts(row.get(f"{side}_seat_names", ""))
        amounts = _parts(row.get(f"{side}_seat_amounts", ""))
        numeric = []
        for value in amounts:
            try:
                numeric.append(float(value.replace(",", "")))
            except ValueError:
                pass
        details[side] = {
            "names": len(names), "amounts": len(amounts),
            "all_amounts_numeric": len(numeric) == len(amounts),
            "all_amounts_nonnegative": all(value >= 0 for value in numeric),
            "count_match": len(names) == len(amounts),
        }
    return details


def szse_detail(day: str, code: str, reason_code: str) -> dict[str, Any]:
    params = {"SHOWTYPE": "JSON", "CATALOGID": "1842_detal",
              "TABKEY": "tab1,tab2", "DQRQ": day,
              "ZQDM": code, "ZBDM": reason_code}
    raw = _get(SZSE_URL, params,
               "https://www.szse.cn/disclosure/deal/public/index.html")
    response = _json(raw)
    if not isinstance(response, list) or len(response) != 2:
        raise RuntimeError(f"SZSE detail shape unexpected: {day}/{code}/{reason_code}")
    meta, seats = response
    if (meta.get("metadata") or {}).get("catalogid") != "1842_detal":
        raise RuntimeError("SZSE detail catalog mismatch")
    headers = meta.get("data") or []
    entries = seats.get("data") or []
    if len(headers) != 1 or headers[0].get("dqrq") != day:
        raise RuntimeError("SZSE detail header date mismatch")
    if code not in str(headers[0].get("zqjc") or ""):
        raise RuntimeError("SZSE detail header code mismatch")
    if seats.get("error") or not isinstance(entries, list):
        raise RuntimeError("SZSE detail seats unavailable")
    invalid = []
    for entry in entries:
        for key in ("mrje", "mcje"):
            value = str(entry.get(key) or "").replace(",", "").strip()
            if value and not re.fullmatch(r"\d+(?:\.\d+)?", value):
                invalid.append(key)
    return {
        "date": day, "code": code, "reason_code": reason_code,
        "reason": str(headers[0].get("plyy") or ""),
        "seat_rows": len(entries), "invalid_amount_fields": invalid,
        "side_labels": sorted({str(item.get("mmlb") or "")[:1] for item in entries}),
        "published_at_present": False,
    }


def run(output: Path) -> dict[str, Any]:
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Refusing to overwrite nonempty output: {output}")
    output.mkdir(parents=True, exist_ok=True)
    dates = selected_calendar_dates()
    (output / "preregistered_dates.json").write_text(
        json.dumps({"selection": "open-session terciles by year", "dates": dates,
                    "years": YEARS}, indent=2), encoding="utf-8")
    reconciled = reconcile(output / "reconciliation", dates)
    official = json.loads(
        (output / "reconciliation" / "official_event_sample.json").read_text(encoding="utf-8"))
    checks = [seat_integrity(row) for row in official if row["exchange"] == "SSE"]
    empty_seat_lists = [
        row for row in official
        if row["exchange"] == "SSE"
        and (not row.get("buy_seat_names") or not row.get("sell_seat_names"))
    ]
    seat_anomalies = [
        check for check in checks
        if any(not (side["all_amounts_numeric"] and side["all_amounts_nonnegative"]
                    and side["count_match"]) for side in check.values())
    ]
    sample_details = []
    for day in dates:
        eligible = sorted(
            (row for row in official
             if row["date"] == day and row["exchange"] == "SZSE"
             and row.get("detail_reason_code")),
            key=lambda row: (row["code"], row["detail_reason_code"]),
        )
        if not eligible:
            sample_details.append({"date": day, "status": "NO_SZSE_DETAIL_CANDIDATE"})
            continue
        row = eligible[0]
        detail = szse_detail(day, row["code"], row["detail_reason_code"])
        detail["listing_reason_match"] = detail["reason"] == row["reason"]
        sample_details.append(detail)
        LOG.info("15D3 detail %s/%s seats=%d", day, row["code"], detail["seat_rows"])
    by_year = defaultdict(list)
    for item in reconciled["comparisons"]:
        by_year[item["date"][:4]].append(item)
    summary = {
        year: {
            "dates": len(items),
            "official_unique": sum(item["official_unique_symbol_exchanges"] for item in items),
            "matched": sum(item["matched_symbol_exchanges"] for item in items),
            "official_only": sum(len(item["official_only"]) for item in items),
            "vendor_only": sum(len(item["vendor_only"]) for item in items),
        }
        for year, items in sorted(by_year.items())
    }
    report = {
        "status": "SOURCE_ROBUSTNESS_AUDIT_ONLY_NO_ML_GO",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "dates": dates, "by_year": summary,
        "sse_reason_rows_checked": len(checks),
        "sse_reason_rows_missing_one_or_both_seat_lists": len(empty_seat_lists),
        "sse_seat_structure_anomalies": len(seat_anomalies),
        "szse_detail_samples": sample_details,
        "historical_publication_time_proven": False,
        "reason_and_amount_vendor_reconciled": False,
        "training_performed": False, "database_modified": False, "serving_changed": False,
        "warning": "Only sampled date/code identity and internal seat structure; no PIT or directional-performance claim.",
    }
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=Path("artifacts/research/cn_dragon_tiger_15d3/pilot-20260929"))
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper()))
    report = run(args.output)
    LOG.info("15D3 complete years=%s", report["by_year"])


if __name__ == "__main__":
    main()
