"""Sprint 15-B1: audit read-only of historical SSE/SZSE margin detail.

This is deliberately a research collector. It writes raw response artifacts,
never production tables or model features. curl.exe uses Windows Schannel so
TLS verification remains enabled on the workstation used for this pilot.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import logging
import re
import subprocess
import time
import zipfile
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import urlencode
from xml.etree import ElementTree as ET

from sqlalchemy import text

from database.router import get_market_engine

LOG = logging.getLogger(__name__)
SSE_URL = "https://query.sse.com.cn/marketdata/tradedata/queryMargin.do"
SZSE_URL = "https://www.szse.cn/api/report/ShowReport"
SSE_FIELDS = ("rzye", "rzmre", "rzche", "rqyl", "rqmcl", "rqchl")
SZSE_FIELDS = ("融资买入额", "融资余额", "融券卖出量", "融券余量", "融券余额", "融资融券余额")
CODE = re.compile(r"^\d{6}$")
CELL_COLUMN = re.compile(r"^[A-Z]+")
XLSX_NS = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def selected_sessions(engine, start_year: int, end_year: int, sample_mode: str = "anchors") -> list[date]:
    """Yearly June/December anchors, or the last five June sessions per year."""
    if sample_mode not in {"anchors", "june_week"}:
        raise ValueError(f"Mode d'échantillon inconnu: {sample_mode}")
    with engine.connect() as conn:
        if sample_mode == "anchors":
            rows = conn.execute(text(
                "SELECT MAX(session_date) FROM market_sessions "
                "WHERE market_code='CN_A' AND session_status='open' "
                "AND YEAR(session_date) BETWEEN :first AND :last "
                "AND MONTH(session_date) IN (6,12) "
                "GROUP BY YEAR(session_date), MONTH(session_date) "
                "ORDER BY YEAR(session_date), MONTH(session_date)"
            ), {"first": start_year, "last": end_year}).all()
            dates = [row[0] for row in rows if row[0] is not None]
            expected = 2 * (end_year - start_year + 1)
        else:
            rows = conn.execute(text(
                "SELECT session_date FROM market_sessions "
                "WHERE market_code='CN_A' AND session_status='open' "
                "AND YEAR(session_date) BETWEEN :first AND :last AND MONTH(session_date)=6 "
                "ORDER BY session_date"
            ), {"first": start_year, "last": end_year}).all()
            by_year: dict[int, list[date]] = {}
            for (session,) in rows:
                by_year.setdefault(session.year, []).append(session)
            dates = [day for year in range(start_year, end_year + 1)
                     for day in by_year.get(year, [])[-5:]]
            expected = 5 * (end_year - start_year + 1)
    if len(dates) != expected:
        raise ValueError(f"Calendrier CN incomplet: {len(dates)} séances au lieu de {expected}")
    return dates


def active_equities(engine, day: date) -> dict[str, set[str]]:
    """Historical denominator, not an assertion of margin eligibility."""
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT exchange_mic,local_symbol FROM instruments "
            "WHERE market_code='CN_A' AND instrument_type='equity' "
            "AND listing_date<=:day AND (delisting_date IS NULL OR delisting_date>=:day) "
            "AND exchange_mic IN ('XSHG','XSHE')"
        ), {"day": day}).all()
    result = {"sse": set(), "szse": set()}
    for mic, code in rows:
        if CODE.fullmatch(str(code)):
            result["sse" if mic == "XSHG" else "szse"].add(str(code))
    return result


def request_bytes(url: str, *, referer: str, timeout: int = 30, retries: int = 2) -> bytes:
    """Verified HTTPS, with bounded retries; no insecure fallback."""
    for attempt in range(retries + 1):
        result = subprocess.run(
            ["curl.exe", "--fail", "--silent", "--show-error", "--location",
             "--max-time", str(timeout), "--header", f"Referer: {referer}",
             "--header", "User-Agent: Mozilla/5.0", url],
            capture_output=True, check=False,
        )
        if result.returncode == 0 and result.stdout:
            return result.stdout
        if attempt < retries:
            time.sleep(min(2 ** attempt, 4))
    detail = result.stderr.decode("utf-8", errors="replace").strip()
    raise RuntimeError(f"HTTPS failed after {retries + 1} attempts: {detail[:300]}")


def sse_request(day: date) -> bytes:
    params = {
        "isPagination": "true", "tabType": "mxtype",
        "detailsDate": day.strftime("%Y%m%d"), "stockCode": "",
        "beginDate": "", "endDate": "",
        "pageHelp.pageSize": "5000", "pageHelp.pageNo": "1",
        "pageHelp.beginPage": "1", "pageHelp.cacheSize": "1",
    }
    return request_bytes(f"{SSE_URL}?{urlencode(params)}", referer="https://www.sse.com.cn/")


def szse_request(day: date) -> bytes:
    params = {
        "SHOWTYPE": "xlsx", "CATALOGID": "1837_xxpl",
        "txtDate": day.isoformat(), "tab2PAGENO": "1", "TABKEY": "tab2",
    }
    return request_bytes(
        f"{SZSE_URL}?{urlencode(params)}",
        referer="https://www.szse.cn/disclosure/margin/margin/index.html",
    )


def analyse_sse(raw: bytes, day: date, active: set[str]) -> dict:
    payload = json.loads(raw)
    rows = payload.get("result")
    if not isinstance(rows, list):
        raise ValueError("SSE result absent ou invalide")
    codes, duplicates, date_errors, negatives = set(), 0, 0, 0
    for row in rows:
        code = str(row.get("stockCode") or "").zfill(6)
        if not CODE.fullmatch(code):
            raise ValueError(f"Code SSE invalide: {code}")
        if code in codes:
            duplicates += 1
        codes.add(code)
        if str(row.get("opDate")) != day.strftime("%Y%m%d"):
            date_errors += 1
        for key in SSE_FIELDS:
            value = row.get(key)
            if value is not None and float(value) < 0:
                negatives += 1
    page = payload.get("pageHelp") or {}
    total = page.get("total")
    if total is not None and int(total) > len(rows):
        raise ValueError(f"SSE pagination incomplète: {len(rows)}/{total}")
    return {
        "rows": len(rows), "distinct_codes": len(codes),
        "duplicate_codes": duplicates, "date_errors": date_errors,
        "negative_values": negatives, "active_equities": len(active),
        "active_matched": len(codes & active),
        "active_coverage_pct": round(100 * len(codes & active) / len(active), 2) if active else None,
        "non_equity_or_outside_universe": len(codes - active),
        "sample_missing_active_codes": sorted(active - codes)[:8],
        "source_page_total": total,
    }


def read_xlsx_rows(raw: bytes) -> list[dict[str, str]]:
    """Read the small official SZSE workbook without adding a dependency."""
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            shared = ["".join(t.text or "" for t in si.findall(".//x:t", XLSX_NS))
                      for si in root.findall("x:si", XLSX_NS)]
        sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
    parsed = []
    for row in sheet.findall(".//x:sheetData/x:row", XLSX_NS):
        values = {}
        for cell in row.findall("x:c", XLSX_NS):
            ref = cell.get("r") or ""
            match = CELL_COLUMN.match(ref)
            if not match:
                continue
            value = cell.find("x:v", XLSX_NS)
            if cell.get("t") == "inlineStr":
                content = "".join(t.text or "" for t in cell.findall(".//x:t", XLSX_NS))
            elif value is None:
                content = ""
            elif cell.get("t") == "s":
                content = shared[int(value.text or "0")]
            else:
                content = value.text or ""
            values[match.group()] = content.strip()
        parsed.append(values)
    header_index = next(
        (index for index, row in enumerate(parsed[:20]) if "证券代码" in row.values()), None
    )
    if header_index is None:
        raise ValueError("En-tête 证券代码 introuvable dans le classeur SZSE")
    headers = {
        column: name.split("(")[0].split("（")[0].strip()
        for column, name in parsed[header_index].items()
    }
    result = []
    for row in parsed[header_index + 1:]:
        mapped = {name: row.get(column, "") for column, name in headers.items()}
        if mapped.get("证券代码"):
            result.append(mapped)
    return result


def analyse_szse(raw: bytes, active: set[str]) -> dict:
    rows = read_xlsx_rows(raw)
    required = {"证券代码", *SZSE_FIELDS}
    if not rows or not required.issubset(rows[0]):
        raise ValueError(f"Colonnes SZSE absentes: {sorted(required - set(rows[0] if rows else {}))}")
    codes, negatives, missing = [], 0, 0
    for row in rows:
        code = row["证券代码"].strip().zfill(6)
        if not CODE.fullmatch(code):
            raise ValueError(f"Code SZSE invalide: {code}")
        codes.append(code)
        for field in SZSE_FIELDS:
            value = row.get(field, "").replace(",", "").strip()
            if not value:
                missing += 1
            elif float(value) < 0:
                negatives += 1
    codes_set = set(codes)
    # SZSE does not expose a session column inside this dated workbook.
    return {
        "rows": len(rows), "distinct_codes": len(codes_set),
        "duplicate_codes": len(rows) - len(codes_set),
        "negative_values": negatives,
        "missing_numeric_cells": missing,
        "active_equities": len(active), "active_matched": len(codes_set & active),
        "active_coverage_pct": round(100 * len(codes_set & active) / len(active), 2) if active else None,
        "non_equity_or_outside_universe": len(codes_set - active),
        "sample_missing_active_codes": sorted(active - codes_set)[:8],
    }


def _write_json(path: Path, payload: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    temporary.replace(path)


def completed_raw_verified(root: Path, session: dict) -> bool:
    """A completed date is resumable only while both raw files retain their hashes."""
    for source in ("sse", "szse"):
        item = session.get(source) or {}
        path = root / str(item.get("raw_file") or "")
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != item.get("sha256"):
            return False
    return True


def run(*, output_root: Path, start_year: int = 2018, end_year: int = 2025,
        pause_seconds: float = 0.5, sample_mode: str = "anchors") -> dict:
    if end_year < start_year or pause_seconds < 0:
        raise ValueError("Fenêtre ou pause invalide")
    engine = get_market_engine("CN_A", database_alias="cn_primary")
    days = selected_sessions(engine, start_year, end_year, sample_mode)
    output_root.mkdir(parents=True, exist_ok=True)
    state_path = output_root / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {
        "protocol": "CN_SPRINT15B1_MARGIN_LENDING_PILOT_V1",
        "market_code": "CN_A", "database_alias": "cn_primary",
        "sample_mode": sample_mode, "dates": [day.isoformat() for day in days], "sessions": {},
    }
    if state["dates"] != [day.isoformat() for day in days]:
        raise ValueError("Échantillon différent du state existant; utiliser un autre output_root")
    for day in days:
        key = day.isoformat()
        if state["sessions"].get(key, {}).get("status") == "COMPLETED":
            if not completed_raw_verified(output_root, state["sessions"][key]):
                raise ValueError(f"Fichiers bruts absents ou altérés pour la date terminée {key}")
            LOG.info("skip completed date=%s", key)
            continue
        active = active_equities(engine, day)
        current = {"status": "RUNNING", "started_at": datetime.now(UTC).isoformat()}
        state["sessions"][key] = current
        _write_json(state_path, state)
        try:
            for source, fetch in (("sse", sse_request), ("szse", szse_request)):
                suffix = "json" if source == "sse" else "xlsx"
                raw_path = output_root / f"{day.isoformat()}_{source}.{suffix}"
                if raw_path.exists():
                    raw = raw_path.read_bytes()
                else:
                    raw = fetch(day)
                    raw_path.write_bytes(raw)
                    time.sleep(pause_seconds)
                current[source] = (
                    analyse_sse(raw, day, active["sse"])
                    if source == "sse" else analyse_szse(raw, active["szse"])
                )
                current[source]["raw_file"] = raw_path.name
                current[source]["sha256"] = hashlib.sha256(raw).hexdigest()
                current[source]["observed_at"] = datetime.now(UTC).isoformat()
                _write_json(state_path, state)
            current["status"] = "COMPLETED"
            current["finished_at"] = datetime.now(UTC).isoformat()
            LOG.info("completed date=%s sse=%s szse=%s", key, current["sse"]["rows"], current["szse"]["rows"])
        except Exception as exc:
            current["status"] = "FAILED"
            current["error"] = f"{type(exc).__name__}: {exc}"
            LOG.exception("failed date=%s", key)
        _write_json(state_path, state)
    state["completed"] = sum(x["status"] == "COMPLETED" for x in state["sessions"].values())
    state["failed"] = sum(x["status"] == "FAILED" for x in state["sessions"].values())
    _write_json(state_path, state)
    return state


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=Path("artifacts/research/cn_margin_lending/sprint15b1_2018_2025"))
    parser.add_argument("--start-year", type=int, default=2018)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--sample-mode", choices=("anchors", "june_week"), default="anchors")
    parser.add_argument("--pause-seconds", type=float, default=0.5)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper()), format="%(asctime)s %(levelname)s %(message)s")
    result = run(output_root=args.output_root, start_year=args.start_year,
                 end_year=args.end_year, pause_seconds=args.pause_seconds,
                 sample_mode=args.sample_mode)
    print(f"Sprint 15-B1: {result['completed']}/{len(result['dates'])} dates, "
          f"{result['failed']} échec(s), état: {args.output_root / 'state.json'}")
    if result["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
