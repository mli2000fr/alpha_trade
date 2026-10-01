"""Bounded CN earnings-guidance research pilot; no database writes or ML training.

Eastmoney is used only to discover dated issuer-report candidates at universe
scale. CNINFO PDF announcements are the primary-document verification sample.
Neither current archive is claimed to be a certified historical PIT vintage.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import re
import shutil
import subprocess
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import text

from database.router import get_market_engine

LOG = logging.getLogger(__name__)
EASTMONEY_URL = "https://datacenter.eastmoney.com/securities/api/data/v1/get"
CNINFO_URL = "https://www.cninfo.com.cn"
PDF_URL = "https://static.cninfo.com.cn/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; AlphaTradeResearch/15-D1)",
    "Referer": "https://www.cninfo.com.cn/new/index",
    "X-Requested-With": "XMLHttpRequest",
}
SEMESTERS = ("2024H1", "2024H2", "2025H1", "2025H2")
PERIODS = tuple(f"{year}-{month:02d}-{'31' if month in (3, 12) else '30'}"
                for year in (2023, 2024, 2025)
                for month in (3, 6, 9, 12)
                if (year, month) <= (2025, 9))
SAMPLE_CODES = ("605081", "300054", "000603", "600519")
SAMPLE_PDF_IDS = ("1222428933", "1223214895", "1222342396", "1220455425")
MAX_PDF_BYTES = 12_000_000


def _request_json(url: str, params: dict[str, Any], *, post: bool = False,
                  attempts: int = 3) -> dict[str, Any] | list[dict[str, Any]]:
    payload = urllib.parse.urlencode(params).encode("utf-8")
    request = urllib.request.Request(
        url if post else f"{url}?{payload.decode('ascii')}",
        data=payload if post else None,
        headers=HEADERS,
    )
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except (OSError, ValueError):
            if attempt + 1 == attempts:
                raise
            time.sleep(min(2 ** attempt, 4))
    raise AssertionError("unreachable")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def discover_eastmoney(*, max_pages_per_period: int = 40) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Get report identifiers/dates only; never create numeric ML features."""
    if max_pages_per_period < 1:
        raise ValueError("max_pages_per_period must be positive")
    rows: list[dict[str, Any]] = []
    provenance: list[dict[str, Any]] = []
    for period in PERIODS:
        params = {
            "sortColumns": "NOTICE_DATE,SECURITY_CODE", "sortTypes": "-1,-1",
            "pageSize": "500", "pageNumber": "1",
            "reportName": "RPT_PUBLIC_OP_NEWPREDICT", "columns": "ALL",
            "filter": f"(REPORT_DATE='{period}')",
        }
        first = _request_json(EASTMONEY_URL, params)
        result = first.get("result") or {}
        if first.get("success") is not True or not isinstance(result.get("data"), list):
            raise RuntimeError(f"Eastmoney response invalid for {period}")
        pages = int(result.get("pages") or 0)
        if pages > max_pages_per_period:
            raise RuntimeError(f"Eastmoney {period}: {pages} pages exceeds cap {max_pages_per_period}; no partial coverage")
        count = 0
        for page in range(1, pages + 1):
            params["pageNumber"] = str(page)
            data = result["data"] if page == 1 else (_request_json(EASTMONEY_URL, params).get("result") or {}).get("data")
            if not isinstance(data, list):
                raise RuntimeError(f"Eastmoney {period} page {page}: missing data")
            for row in data:
                code = str(row.get("SECURITY_CODE") or "").zfill(6)
                if re.fullmatch(r"\d{6}", code) and row.get("NOTICE_DATE"):
                    rows.append({
                        "local_symbol": code,
                        "notice_date": str(row["NOTICE_DATE"])[:10],
                        "report_period": period,
                        "metric_code": str(row.get("PREDICT_FINANCE_CODE") or ""),
                        "market": str(row.get("TRADE_MARKET") or ""),
                    })
            count += len(data)
        if count != int(result.get("count") or 0):
            raise RuntimeError(f"Eastmoney {period}: paginated {count} != reported {result.get('count')}")
        provenance.append({"period": period, "reported_rows": count, "pages": pages})
        LOG.info("guidance_discovery period=%s rows=%d pages=%d", period, count, pages)
    frame = pd.DataFrame(rows, columns=["local_symbol", "notice_date", "report_period", "metric_code", "market"])
    return frame, provenance


def select_top20(frame: pd.DataFrame, top_pct: float = 0.20) -> pd.DataFrame:
    """Exactly mirror cn_oracle_walk_forward._top_rows on paired valid rows."""
    if not 0 < top_pct <= 1:
        raise ValueError("top_pct must be in (0, 1]")
    valid = frame.loc[frame["target_quality_valid"] & frame["baseline_score"].notna()].copy()
    ordered = valid.sort_values(
        ["session_date", "oracle_score", "instrument_id"],
        ascending=[True, False, True], kind="stable",
    )
    rank = ordered.groupby("session_date", sort=False).cumcount()
    size = ordered.groupby("session_date", sort=False)["instrument_id"].transform("size")
    return ordered.loc[rank < size.mul(top_pct).apply(math.ceil).clip(lower=1)].copy()


def load_oracle_top20(oracle_root: Path) -> tuple[pd.DataFrame, list[dict[str, str]]]:
    selected = []
    sources = []
    columns = ["session_date", "instrument_id", "board_code", "target_quality_valid",
               "baseline_score", "oracle_score", "oracle_decile", "oracle_extreme20"]
    for semester in SEMESTERS:
        matches = sorted(oracle_root.glob(f"*/h20/{semester}/lightgbm/predictions.parquet"))
        if len(matches) != 1:
            raise RuntimeError(f"Expected exactly one H20 LightGBM OOF file for {semester}, found {len(matches)}")
        path = matches[0]
        part = pd.read_parquet(path, columns=columns)
        part["session_date"] = pd.to_datetime(part["session_date"]).dt.normalize()
        top = select_top20(part)
        top["semester"] = semester
        selected.append(top[["session_date", "instrument_id", "board_code", "oracle_decile",
                             "oracle_extreme20", "semester"]])
        sources.append({"semester": semester, "path": str(path), "sha256": _sha256(path),
                        "rows": int(len(part)), "top20_rows": int(len(top))})
        LOG.info("oracle_top20 semester=%s rows=%d selected=%d", semester, len(part), len(top))
    top = pd.concat(selected, ignore_index=True)
    engine = get_market_engine("CN_A", database_alias="cn_primary")
    with engine.connect() as connection:
        mapping = pd.read_sql(text("SELECT instrument_id,local_symbol FROM instruments WHERE market_code='CN_A'"), connection)
    if mapping["instrument_id"].duplicated().any():
        raise RuntimeError("Duplicate instrument_id in CN instrument mapping")
    top = top.merge(mapping, on="instrument_id", how="left", validate="many_to_one")
    if top["local_symbol"].isna().any():
        raise RuntimeError(f"Unmapped Oracle instruments: {top['local_symbol'].isna().sum()}")
    top["local_symbol"] = top["local_symbol"].astype(str).str.zfill(6)
    return top, sources


def join_prior_announcements(top: pd.DataFrame, discovery: pd.DataFrame) -> pd.DataFrame:
    """Conservative metadata-only as-of join; no same-day or future event."""
    events = discovery[["local_symbol", "notice_date"]].copy()
    events["notice_date"] = pd.to_datetime(events["notice_date"], errors="coerce").dt.normalize()
    events = events.dropna().drop_duplicates()
    events = events.sort_values(["notice_date", "local_symbol"])
    left = top.sort_values(["session_date", "local_symbol"])
    result = pd.merge_asof(left, events, left_on="session_date", right_on="notice_date",
                           by="local_symbol", direction="backward", allow_exact_matches=False)
    result["age_calendar_days"] = (result["session_date"] - result["notice_date"]).dt.days
    return result


def coverage_summary(joined: pd.DataFrame) -> dict[str, Any]:
    def metrics(group: pd.DataFrame) -> dict[str, Any]:
        age = group["age_calendar_days"]
        return {"rows": int(len(group)), "symbols": int(group["local_symbol"].nunique()),
                "any_prior": int(age.notna().sum()),
                "within_20d": int(age.le(20).sum()), "within_90d": int(age.le(90).sum()),
                "within_365d": int(age.le(365).sum())}
    return {"overall": metrics(joined),
            "by_semester": {str(key): metrics(part) for key, part in joined.groupby("semester")},
            "by_board": {str(key): metrics(part) for key, part in joined.groupby("board_code")},
            "by_realized_decile": {str(key): metrics(part) for key, part in joined.groupby("oracle_decile")}}


def classify_document(title: str, text_content: str) -> dict[str, Any]:
    """Identify document structure, but quarantine numeric extraction pending review."""
    first = re.sub(r"\s+", "", (title or "") + " " + (text_content or "")[:1200])
    fiscal = re.search(r"(20\d{2})(?:年)?(年度|半年度|前三季度|第一季度)", first)
    correction = bool(re.search(r"更正|修正|补充", title or ""))
    old_heading = bool(re.search(r"前次业绩预告|原预计|原预告", text_content or ""))
    new_heading = bool(re.search(r"更正后|修正后|本次业绩预告", text_content or ""))
    return {"fiscal_year": int(fiscal.group(1)) if fiscal else None,
            "fiscal_period": fiscal.group(2) if fiscal else None,
            "correction": correction, "has_prior_section": old_heading,
            "has_new_section": new_heading,
            "extraction_status": "MANUAL_REVIEW_REQUIRED"}


def _cninfo_post(path: str, values: dict[str, Any]) -> Any:
    return _request_json(CNINFO_URL + path, values, post=True)


def cninfo_sample(out: Path, *, max_pdfs: int = 8) -> list[dict[str, Any]]:
    if max_pdfs < 0:
        raise ValueError("max_pdfs must be nonnegative")
    results = []
    for code in SAMPLE_CODES:
        found = _cninfo_post("/new/information/topSearch/query", {"keyWord": code, "maxNum": 10})
        matches = found if isinstance(found, list) else [found]
        match = next((row for row in matches if row.get("code") == code), None)
        if not match:
            raise RuntimeError(f"CNINFO orgId missing for {code}")
        params = {"pageNum": 1, "pageSize": 30,
                  "column": "sse" if code.startswith(("6", "9")) else "szse",
                  "tabName": "fulltext", "stock": f"{code},{match['orgId']}",
                  "category": "category_yjygjxz_szsh", "seDate": "2024-01-01~2025-12-31"}
        response = _cninfo_post("/new/hisAnnouncement/query", params)
        notices = response.get("announcements") or []
        total = int(response.get("totalAnnouncement") or 0)
        for page in range(2, math.ceil(total / 30) + 1):
            params["pageNum"] = page
            notices.extend((_cninfo_post("/new/hisAnnouncement/query", params).get("announcements") or []))
        if len(notices) != total:
            raise RuntimeError(f"CNINFO {code}: pagination {len(notices)} != {total}")
        for item in notices:
            if item.get("announcementId") and item.get("adjunctUrl"):
                results.append({"code": code, "announcement_id": str(item["announcementId"]),
                                "title": str(item.get("announcementTitle") or ""),
                                "announcement_time_ms": item.get("announcementTime"),
                                "pdf_url": urllib.parse.urljoin(PDF_URL, str(item["adjunctUrl"])),
                                "org_id": match["orgId"]})
        LOG.info("cninfo_sample code=%s notices=%d", code, total)
    selected = [row for identifier in SAMPLE_PDF_IDS
                for row in results if row["announcement_id"] == identifier]
    if len(selected) < min(max_pdfs, len(SAMPLE_PDF_IDS)):
        raise RuntimeError("Pre-registered original/correction PDF pair not found in CNINFO archive")
    remainder = [row for row in sorted(results, key=lambda r: (r["code"], r["announcement_id"]))
                 if row not in selected]
    selected = (selected + remainder)[:max_pdfs]
    pdf_root = out / "sample_pdfs"
    pdf_root.mkdir(parents=True, exist_ok=True)
    text_bin = shutil.which("pdftotext")
    for row in selected:
        target = pdf_root / f"{row['code']}-{row['announcement_id']}.pdf"
        request = urllib.request.Request(row["pdf_url"], headers=HEADERS)
        with urllib.request.urlopen(request, timeout=30) as response:
            data = response.read(MAX_PDF_BYTES + 1)
        if len(data) > MAX_PDF_BYTES or not data.startswith(b"%PDF-"):
            raise RuntimeError(f"Invalid/oversized PDF {row['pdf_url']}")
        target.write_bytes(data)
        row["pdf_path"] = str(target)
        row["pdf_sha256"] = _sha256(target)
        row["pdf_bytes"] = len(data)
        if text_bin:
            extracted = target.with_suffix(".txt")
            process = subprocess.run([text_bin, "-layout", str(target), str(extracted)],
                                     capture_output=True, text=True, timeout=30)
            if process.returncode != 0:
                raise RuntimeError(f"pdftotext failed for {target}: {process.stderr[:250]}")
            row["text_path"] = str(extracted)
            row["text_sha256"] = _sha256(extracted)
            row.update(classify_document(row["title"], extracted.read_text(encoding="utf-8", errors="replace")))
        else:
            row["extraction_status"] = "NO_PDFTOTEXT_MANUAL_REVIEW_REQUIRED"
    return selected


def run(*, output: Path, max_pages_per_period: int = 40, max_pdfs: int = 8,
        oracle_root: Path = Path("artifacts/cn/oracle/sprint10b")) -> dict[str, Any]:
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Refusing to overwrite nonempty output: {output}")
    output.mkdir(parents=True, exist_ok=True)
    discovery, provider_pages = discover_eastmoney(max_pages_per_period=max_pages_per_period)
    discovery.to_parquet(output / "eastmoney_discovery_metadata.parquet", index=False)
    top, oracle_sources = load_oracle_top20(oracle_root)
    joined = join_prior_announcements(top, discovery)
    joined.to_parquet(output / "oracle_top20_guidance_coverage.parquet", index=False)
    samples = cninfo_sample(output, max_pdfs=max_pdfs)
    report = {"status": "RESEARCH_PROXY_ONLY", "generated_at_utc": datetime.now(timezone.utc).isoformat(),
              "market_code": "CN_A", "oracle_horizon": 20, "oracle_model": "lightgbm",
              "periods": list(PERIODS), "provider_pages": provider_pages,
              "discovery_rows": int(len(discovery)),
              "distinct_discovery_symbol_dates": int(len(discovery[["local_symbol", "notice_date"]].drop_duplicates())),
              "oracle_sources": oracle_sources, "coverage": coverage_summary(joined),
              "cninfo_samples": samples,
              "pit_warning": "Current Eastmoney/CNINFO archives are not certified historical vintages; date-only strictly prior, numeric extraction quarantined.",
              "serving_changed": False, "training_performed": False}
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("artifacts/research/cn_guidance_15d1/pilot-20260929"))
    parser.add_argument("--max-pages-per-period", type=int, default=40)
    parser.add_argument("--max-pdfs", type=int, default=8)
    parser.add_argument("--oracle-root", type=Path, default=Path("artifacts/cn/oracle/sprint10b"))
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper()))
    report = run(output=args.output, max_pages_per_period=args.max_pages_per_period,
                 max_pdfs=args.max_pdfs, oracle_root=args.oracle_root)
    LOG.info("Sprint 15-D1 complete: %s coverage=%s", args.output, report["coverage"]["overall"])


if __name__ == "__main__":
    main()
