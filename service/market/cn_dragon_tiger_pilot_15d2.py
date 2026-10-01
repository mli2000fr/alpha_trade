"""Bounded, read-only CN Dragon/Tiger exchange reconciliation pilot.

Official SSE/SZSE event identities are compared with an Eastmoney archive.
No future-return fields or vendor success-rate text are persisted. These
historical archives do not certify the original publication timestamp.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LOG = logging.getLogger(__name__)
SAMPLE_DATES = ("2024-01-31", "2024-07-31", "2025-07-31", "2025-12-31")
SSE_URL = "https://query.sse.com.cn/marketdata/tradedata/queryAllTradeOpenDate.do"
SSE_STAR_URL = "https://query.sse.com.cn/marketdata/tradedata/queryKCBTradeInfo.do"
SZSE_URL = "https://www.szse.cn/api/report/ShowReport/data"
EASTMONEY_URL = "https://datacenter.eastmoney.com/securities/api/data/v1/get"
SZSE_CATALOG = "1842_xxpl_after"
SZSE_RETURNED_CATALOGS = frozenset({"1842_xxpl", "1842_xxpl_after"})
VENDOR_ALLOWED = frozenset(
    {"TRADE_DATE", "SECURITY_CODE", "MARKET", "EXPLANATION", "CHANGE_TYPE"}
)
VENDOR_FORBIDDEN = frozenset({"EXPLAIN", "FREE_MARKET_CAP", "SECURITY_INNER_CODE"})


def _get(url: str, params: dict[str, str], referer: str, *, attempts: int = 3) -> bytes:
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(
        f"{url}?{query}",
        headers={"User-Agent": "Mozilla/5.0", "Referer": referer},
    )
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read()
        except OSError:
            if attempt + 1 == attempts:
                raise
            time.sleep(min(2 ** attempt, 4))
    raise AssertionError("unreachable")


def _json(raw: bytes) -> Any:
    return json.loads(raw.decode("utf-8-sig"))


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _code(value: Any) -> str:
    code = str(value or "").zfill(6)
    if not re.fullmatch(r"\d{6}", code):
        raise ValueError(f"Invalid security code: {value!r}")
    return code


def is_cn_a_equity_code(market: str, code: str) -> bool:
    """Research-sample security-type filter; not a replacement for PIT master."""
    return (market == "SH" and code.startswith(("60", "68"))) or (
        market == "SZ" and code.startswith(("00", "30"))
    )


def official_sse(day: str) -> tuple[list[dict[str, str]], dict[str, Any]]:
    rows = []
    provenance = {}
    for board, url in (("MAIN", SSE_URL), ("STAR", SSE_STAR_URL)):
        params = {"tradeDate": day.replace("-", ""),
                  "flag": "1", "jsonCallBack": "alphaTrade15D2"}
        if board == "MAIN":
            params["token"] = "QUERY"
        raw = _get(url, params,
                   "https://www.sse.com.cn/disclosure/diclosure/public/dailydata/index.shtml")
        content = raw.decode("utf-8-sig")
        if not content.startswith("alphaTrade15D2(") or not content.endswith(")"):
            raise RuntimeError(f"Unexpected SSE {board} JSONP response for {day}")
        response = json.loads(content[len("alphaTrade15D2("):-1])
        data = (response.get("pageHelp") or {}).get("data")
        if not isinstance(data, list):
            raise RuntimeError(f"Missing SSE {board} data for {day}")
        included = 0
        for item in data:
            if item.get("tradeDate") != day.replace("-", ""):
                raise RuntimeError(f"SSE date mismatch: {item.get('tradeDate')} != {day}")
            code = _code(item.get("secCode"))
            if item.get("secType") != "A" or not is_cn_a_equity_code("SH", code):
                continue
            rows.append({"code": code, "date": day,
                         "reason_code": str(item.get("refType") or ""),
                         "exchange": "SSE", "board": board,
                         "buy_seat_names": str(item.get("branchNameB" if board == "MAIN" else "deptNameB") or ""),
                         "buy_seat_amounts": str(item.get("branchTxAmtB" if board == "MAIN" else "deptTxAmtB") or ""),
                         "sell_seat_names": str(item.get("branchNameS" if board == "MAIN" else "deptNameS") or ""),
                         "sell_seat_amounts": str(item.get("branchTxAmtS" if board == "MAIN" else "deptTxAmtS") or "")})
            included += 1
        provenance[board] = {"sha256": _digest(raw), "returned_rows": len(data),
                             "a_equity_rows": included}
    return rows, {"boards": provenance, "a_equity_rows": len(rows),
                  "published_at_present": False}


def parse_szse_page(response: Any, day: str, expected_page: int) -> tuple[list[dict[str, str]], dict[str, int]]:
    if not isinstance(response, list) or len(response) != 1:
        raise RuntimeError("Unexpected SZSE response shape")
    block = response[0]
    meta = block.get("metadata") or {}
    if (meta.get("catalogid") not in SZSE_RETURNED_CATALOGS
            or int(meta.get("pageno") or 0) != expected_page):
        raise RuntimeError("SZSE catalog or page mismatch")
    data = block.get("data")
    if not isinstance(data, list) or block.get("error"):
        raise RuntimeError(f"SZSE page error: {block.get('error')}")
    rows = []
    for item in data:
        if item.get("dqrq") != day:
            raise RuntimeError(f"SZSE date mismatch: {item.get('dqrq')} != {day}")
        code = _code(item.get("zqdm"))
        if is_cn_a_equity_code("SZ", code):
            detail = re.search(r"ZBDM=([0-9A-Za-z]+)", str(item.get("bz") or ""))
            rows.append({"code": code, "date": day,
                         "reason": str(item.get("plyy") or ""), "exchange": "SZSE",
                         "detail_reason_code": detail.group(1) if detail else ""})
    return rows, {"page": expected_page, "pages": int(meta.get("pagecount") or 0),
                  "reported_rows": int(meta.get("recordcount") or 0),
                  "unfiltered_rows": len(data)}


def official_szse(day: str) -> tuple[list[dict[str, str]], dict[str, Any]]:
    rows = []
    hashes = []
    reported_rows = None
    pages = None
    page = 1
    unfiltered_rows = 0
    while pages is None or page <= pages:
        params = {"SHOWTYPE": "JSON", "CATALOGID": SZSE_CATALOG,
                  "TABKEY": "tab1", "txtStart": day, "txtEnd": day,
                  "PAGENO": str(page)}
        raw = _get(SZSE_URL, params,
                   "https://www.szse.cn/disclosure/deal/public/index.html")
        part, meta = parse_szse_page(_json(raw), day, page)
        if pages is None:
            pages, reported_rows = meta["pages"], meta["reported_rows"]
            if pages > 30:
                raise RuntimeError(f"SZSE {day}: unexpectedly many pages: {pages}")
        elif (pages, reported_rows) != (meta["pages"], meta["reported_rows"]):
            raise RuntimeError(f"SZSE {day}: pagination changed during read")
        rows.extend(part)
        unfiltered_rows += meta["unfiltered_rows"]
        hashes.append(_digest(raw))
        page += 1
    if unfiltered_rows != reported_rows:
        raise RuntimeError(f"SZSE {day}: fetched {unfiltered_rows} != reported {reported_rows}")
    return rows, {"page_sha256": hashes, "pages": pages, "returned_rows": len(rows),
                  "reported_all_security_rows": reported_rows,
                  "published_at_present": False}


def sanitize_vendor(row: dict[str, Any], day: str) -> dict[str, str] | None:
    if str(row.get("TRADE_DATE") or "")[:10] != day:
        raise RuntimeError("Eastmoney date mismatch")
    market = str(row.get("MARKET") or "")
    code = _code(row.get("SECURITY_CODE"))
    if not is_cn_a_equity_code(market, code):
        return None
    # The aggregate also contains financing/short-sale threshold notices from
    # another exchange disclosure family. They are not Dragon/Tiger events.
    if re.search(r"融资买入数量|融券卖出数量", str(row.get("EXPLANATION") or "")):
        return None
    return {key.lower(): str(row.get(key) or "") for key in sorted(VENDOR_ALLOWED)}


def vendor_eastmoney(day: str) -> tuple[list[dict[str, str]], dict[str, Any]]:
    params = {"reportName": "RPT_DAILYBILLBOARD_DETAILSNEW", "columns": "ALL",
              "pageSize": "500", "pageNumber": "1",
              "sortColumns": "TRADE_DATE,SECURITY_CODE", "sortTypes": "-1,-1",
              "filter": f"(TRADE_DATE='{day}')"}
    rows = []
    hashes = []
    columns = set()
    count = None
    pages = None
    page = 1
    unfiltered_rows = 0
    while pages is None or page <= pages:
        params["pageNumber"] = str(page)
        raw = _get(EASTMONEY_URL, params, "https://data.eastmoney.com/stock/lhb.html")
        response = _json(raw)
        result = response.get("result") or {}
        data = result.get("data")
        if response.get("success") is not True or not isinstance(data, list):
            raise RuntimeError(f"Invalid Eastmoney response for {day} page {page}")
        if pages is None:
            pages, count = int(result.get("pages") or 0), int(result.get("count") or 0)
            if pages > 10:
                raise RuntimeError(f"Eastmoney {day}: unexpectedly many pages: {pages}")
        elif (pages, count) != (int(result.get("pages") or 0), int(result.get("count") or 0)):
            raise RuntimeError(f"Eastmoney {day}: pagination changed during read")
        unfiltered_rows += len(data)
        for item in data:
            columns.update(item)
            safe = sanitize_vendor(item, day)
            if safe is not None:
                rows.append(safe)
        hashes.append(_digest(raw))
        page += 1
    if unfiltered_rows != count:
        raise RuntimeError(f"Eastmoney {day}: fetched {unfiltered_rows} != reported {count}")
    if not rows and count:
        raise RuntimeError(f"Eastmoney {day}: no SH/SZ rows despite {count} records")
    leaked = sorted(k for k in columns if re.fullmatch(r"D\d+_CLOSE_ADJCHRATE", k))
    return rows, {"page_sha256": hashes, "pages": pages, "reported_all_market_rows": count,
                  "cn_a_rows": len(rows), "forbidden_future_return_columns": leaked,
                  "other_excluded_columns": sorted(columns - VENDOR_ALLOWED - set(leaked)),
                  "published_at_present": False}


def compare(day: str, sse: list[dict[str, str]],
            szse: list[dict[str, str]], vendor: list[dict[str, str]]) -> dict[str, Any]:
    official = {("SH" if row["exchange"] == "SSE" else "SZ", row["code"])
                for row in sse + szse}
    archive = {(row["market"], row["security_code"]) for row in vendor}
    return {
        "date": day, "official_rows": len(sse) + len(szse),
        "official_unique_symbol_exchanges": len(official),
        "vendor_rows": len(vendor), "vendor_unique_symbol_exchanges": len(archive),
        "matched_symbol_exchanges": len(official & archive),
        "official_only": [list(item) for item in sorted(official - archive)],
        "vendor_only": [list(item) for item in sorted(archive - official)],
        "reason_level_comparable": False,
    }


def run(output: Path, dates: tuple[str, ...] = SAMPLE_DATES) -> dict[str, Any]:
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Refusing to overwrite nonempty output: {output}")
    output.mkdir(parents=True, exist_ok=True)
    comparisons = []
    provenance = {}
    official_rows = []
    vendor_rows = []
    for day in dates:
        datetime.strptime(day, "%Y-%m-%d")
        sse, sse_meta = official_sse(day)
        szse, szse_meta = official_szse(day)
        archive, vendor_meta = vendor_eastmoney(day)
        comparisons.append(compare(day, sse, szse, archive))
        provenance[day] = {"sse": sse_meta, "szse": szse_meta, "eastmoney": vendor_meta}
        official_rows.extend(sse + szse)
        vendor_rows.extend(archive)
        LOG.info("15D2 %s official=%d vendor=%d matched=%d",
                 day, comparisons[-1]["official_unique_symbol_exchanges"],
                 comparisons[-1]["vendor_unique_symbol_exchanges"],
                 comparisons[-1]["matched_symbol_exchanges"])
    (output / "official_event_sample.json").write_text(
        json.dumps(official_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "eastmoney_sanitized_sample.json").write_text(
        json.dumps(vendor_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    report = {
        "status": "HISTORICAL_PROXY_ONLY_NO_ML_GO",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "dates": list(dates), "comparisons": comparisons, "provenance": provenance,
        "vendor_persisted_allowlist": sorted(VENDOR_ALLOWED),
        "vendor_explicitly_forbidden": sorted(VENDOR_FORBIDDEN),
        "vendor_raw_persisted": False, "training_performed": False,
        "database_modified": False, "serving_changed": False,
        "pit_warning": "Official archives contain trade date but no proven historical publication timestamp; use only after J close, at earliest J+1 as research proxy.",
    }
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=Path("artifacts/research/cn_dragon_tiger_15d2/pilot-20260929"))
    parser.add_argument("--dates", default=",".join(SAMPLE_DATES))
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper()))
    run(args.output, tuple(day.strip() for day in args.dates.split(",") if day.strip()))


if __name__ == "__main__":
    main()
