"""Sprint 15-B3: bounded, read-only qualification of margin/lending blockers."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import logging
import re
import time
import zipfile
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import urlencode, urljoin
from xml.etree import ElementTree as ET

from service.market.cn_margin_lending_contract_audit import eligibility_rows
from service.market.cn_margin_lending_pilot import (
    SSE_FIELDS,
    SSE_URL,
    SZSE_FIELDS,
    XLSX_NS,
    _write_json,
    completed_raw_verified,
    read_xlsx_rows,
    request_bytes,
    sse_request,
)

LOG = logging.getLogger(__name__)
ROOT = Path("artifacts/research/cn_margin_lending")
EPISODES = [("2019-06-25", "2019-06-26"), ("2020-06-29", "2020-06-30"),
            ("2021-06-24", "2021-06-25"), ("2022-06-28", "2022-06-29")]
PAGES = {
    "sse_2018q2": "https://www.sse.com.cn/lawandrules/sselawsrules2025/repeal/rules/c/c_20180706_10784918.shtml",
    "sse_2019q4": "https://www.sse.com.cn/lawandrules/sselawsrules/repeal/rules/c/c_20210531_5478095.shtml",
    "sse_removal_2021": "https://www.sse.com.cn/disclosure/magin/announcement/ssereport/c/c_20210430_5448906.shtml",
    "szse_guide_2023": "https://docs.static.szse.cn/www/marketServices/deal/finance/busRules/W020230901534859402978.pdf",
}


def economic_panel(raw: bytes, day: str) -> dict:
    payload = json.loads(raw)
    rows = payload.get("result")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Empty SSE detail")
    panel = {}
    for row in rows:
        code = row["stockCode"]
        if code in panel or row["opDate"] != day.replace("-", ""):
            raise ValueError("Duplicate or wrong SSE date")
        panel[code] = tuple(int(row[field]) for field in SSE_FIELDS)
    if payload.get("pageHelp", {}).get("total", len(rows)) != len(rows):
        raise ValueError("Incomplete SSE response")
    return panel


def compare_panels(old: dict, new: dict) -> dict:
    shared = old.keys() & new.keys()
    return {"old_rows": len(old), "new_rows": len(new),
            "added": sorted(new.keys() - old.keys()), "removed": sorted(old.keys() - new.keys()),
            "economic_rows_changed": sum(old[code] != new[code] for code in shared)}


def eligibility_match(raw: bytes, detail_raw: bytes) -> dict:
    flags = eligibility_rows(raw)
    target = {code for code, item in flags.items() if item["融资标的"] or item["融券标的"]}
    detail = {row["证券代码"].zfill(6) for row in read_xlsx_rows(detail_raw)}
    return {"eligible": len(target), "observed": len(detail),
            "missing": sorted(target - detail), "outside": sorted(detail - target)}


def szse_summary(raw: bytes) -> dict:
    """Read the separate one-row summary, retaining the CNY/unit headers."""
    with zipfile.ZipFile(io.BytesIO(raw)) as workbook:
        shared = []
        if "xl/sharedStrings.xml" in workbook.namelist():
            root = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
            shared = ["".join(t.text or "" for t in si.findall(".//x:t", XLSX_NS))
                      for si in root.findall("x:si", XLSX_NS)]
        sheet = ET.fromstring(workbook.read("xl/worksheets/sheet1.xml"))
    rows = []
    for row in sheet.findall(".//x:sheetData/x:row", XLSX_NS):
        values = {}
        for cell in row.findall("x:c", XLSX_NS):
            column = re.sub(r"\d", "", cell.get("r", ""))
            value = cell.find("x:v", XLSX_NS)
            if cell.get("t") == "inlineStr":
                content = "".join(t.text or "" for t in cell.findall(".//x:t", XLSX_NS))
            elif cell.get("t") == "s":
                content = shared[int(value.text)]
            else:
                content = value.text if value is not None else ""
            values[column] = content
        rows.append(values)
    if len(rows) != 2:
        raise ValueError("Unexpected SZSE summary shape")
    for label in rows[0].values():
        field = label.split("(")[0]
        unit = "股/份" if field in {"融券卖出量", "融券余量"} else "元"
        if label != f"{field}({unit})":
            raise ValueError(f"Unexpected SZSE unit: {label}")
    result = {label.split("(")[0]: int(rows[1][column].replace(",", ""))
              for column, label in rows[0].items()}
    if set(result) != set(SZSE_FIELDS):
        raise ValueError("Unexpected SZSE summary fields")
    return result


def archive(root: Path, name: str, url: str, report: dict) -> bytes:
    """Cache one immutable observation; reject altered bytes on subsequent runs."""
    path = root / name
    receipt = root / (name + ".receipt.json")
    if path.exists() != receipt.exists():
        raise ValueError(f"Incomplete cached observation: {name}")
    if path.exists():
        raw = path.read_bytes()
        item = json.loads(receipt.read_text(encoding="utf-8"))
        if item["url"] != url or item["sha256"] != hashlib.sha256(raw).hexdigest():
            raise ValueError(f"Altered cached observation: {name}")
    else:
        raw = request_bytes(url, referer="https://www.sse.com.cn/" if "sse.com.cn" in url
                            else "https://www.szse.cn/")
        item = {"url": url, "sha256": hashlib.sha256(raw).hexdigest(),
                "observed_at": datetime.now(UTC).isoformat(), "raw_file": name,
                "historical_vintage_proven": False}
        path.write_bytes(raw)
        _write_json(receipt, item)
    report["sources"][name] = item
    return raw


def run(output_root: Path) -> dict:
    output_root.mkdir(parents=True, exist_ok=True)
    report = {"protocol": "CN_15B3_BLOCKER_AUDIT_V1", "status": "RUNNING",
              "sources": {}, "failures": [], "sse_rechecks": {}, "sse_summaries": {},
              "szse_eligibility": {}, "strict_ml_allowed": False}
    report_path = output_root / "report.json"

    def checkpoint():
        for attempt in range(6):
            try:
                _write_json(report_path, report)
                return
            except PermissionError:
                if attempt == 5:
                    raise
                time.sleep(0.2)

    for key, url in PAGES.items():
        try:
            suffix = ".pdf" if url.endswith(".pdf") else ".html"
            raw = archive(output_root, key + suffix, url, report)
            if suffix == ".html":
                attachments = sorted(set(re.findall(
                    r'href=["\x27]([^"\x27]+\.(?:docx?|xlsx?|pdf))',
                    raw.decode("utf-8"), flags=re.I)))
                for index, link in enumerate(attachments):
                    resolved = urljoin(url, link)
                    archive(output_root, f"{key}_attachment_{index}{Path(link).suffix}",
                            resolved, report)
        except Exception as exc:
            report["failures"].append({"source": key, "error": str(exc)})
        checkpoint()

    weeks = ROOT / "sprint15b1_june_weeks_2018_2025"
    state = json.loads((weeks / "state.json").read_text(encoding="utf-8"))
    for previous, day in EPISODES:
        for value in (previous, day):
            try:
                if not completed_raw_verified(weeks, state["sessions"].get(value, {})):
                    raise ValueError("Unverified B1 source")
                # Same public source, different collection time; not independent corroboration.
                name = f"{value}_sse_recheck.json"
                path = output_root / name
                receipt = output_root / (name + ".receipt.json")
                if not path.exists():
                    raw = sse_request(date.fromisoformat(value))
                    path.write_bytes(raw)
                    _write_json(receipt, {"sha256": hashlib.sha256(raw).hexdigest(),
                                         "observed_at": datetime.now(UTC).isoformat()})
                raw = path.read_bytes()
                meta = json.loads(receipt.read_text(encoding="utf-8"))
                if hashlib.sha256(raw).hexdigest() != meta["sha256"]:
                    raise ValueError("Altered recheck observation")
                report["sse_rechecks"][value] = compare_panels(
                    economic_panel((weeks / f"{value}_sse.json").read_bytes(), value),
                    economic_panel(raw, value))
                report["sse_rechecks"][value]["observation"] = meta
            except Exception as exc:
                report["failures"].append({"source": f"recheck/{value}", "error": str(exc)})
            checkpoint()
        try:
            q = {"isPagination": "true", "tabType": "rzrqjyzl",
                 "beginDate": previous.replace("-", ""), "endDate": day.replace("-", ""),
                 "pageHelp.pageSize": "100", "pageHelp.pageNo": "1"}
            raw = archive(output_root, f"{day}_sse_summary.json",
                          SSE_URL + "?" + urlencode(q), report)
            rows = json.loads(raw).get("result", [])
            selected = {r["opDate"]: r for r in rows}
            a, b = selected[previous.replace("-", "")], selected[day.replace("-", "")]
            report["sse_summaries"][day] = {
                "financing_residual_cny": int(b["rzye"]) - int(a["rzye"])
                - int(b["rzmre"]) + int(b["rzche"])}
        except Exception as exc:
            report["failures"].append({"source": f"summary/{day}", "error": str(exc)})
        checkpoint()

    for value in state["dates"]:
        try:
            if not completed_raw_verified(weeks, state["sessions"].get(value, {})):
                raise ValueError("Unverified weekly source")
            q = {"SHOWTYPE": "xlsx", "CATALOGID": "1834_xxpl",
                 "txtDate": value, "TABKEY": "tab1"}
            raw = archive(output_root, f"{value}_szse_eligibility.xlsx",
                          "https://www.szse.cn/api/report/ShowReport?" + urlencode(q), report)
            report["szse_eligibility"][value] = eligibility_match(
                raw, (weeks / f"{value}_szse.xlsx").read_bytes())
            LOG.info("SZSE eligibility date=%s %s", value, report["szse_eligibility"][value])
        except Exception as exc:
            report["failures"].append({"source": f"eligibility/{value}", "error": str(exc)})
        checkpoint()
    try:
        url = ("https://www.szse.cn/api/report/ShowReport?SHOWTYPE=xlsx"
               "&CATALOGID=1837_xxpl&txtDate=2025-06-30&TABKEY=tab1")
        summary = szse_summary(archive(output_root, "2025-06-30_szse_summary.xlsx", url, report))
        detail = read_xlsx_rows((weeks / "2025-06-30_szse.xlsx").read_bytes())
        report["szse_summary_reconciliation"] = {
            field: {"summary": summary[field],
                    "detail": sum(int(row[field].replace(",", "")) for row in detail),
                    "summary_minus_detail": summary[field]
                    - sum(int(row[field].replace(",", "")) for row in detail)}
            for field in SZSE_FIELDS}
    except Exception as exc:
        report["failures"].append({"source": "szse_summary", "error": str(exc)})
    report["status"] = "COMPLETED" if not report["failures"] else "PARTIAL_FAILURE"
    report["verdict"] = "NO_GO_STRICT_PIT_PROXY_RESEARCH_REQUIRES_PREREGISTRATION"
    checkpoint()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=ROOT / "sprint15b3_blockers")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    report = run(args.output_root)
    print(f"15-B3: {report['status']}; {report['verdict']}; {args.output_root}")
    if report["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
