"""Dragon/Tiger historical Oracle coverage; read-only research proxy, never PIT-certified."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from database.router import get_market_engine
from service.market.cn_dragon_tiger_pilot_15d2 import (
    EASTMONEY_URL, _get, _json, sanitize_vendor,
)
from service.market.cn_guidance_pilot_15d1 import load_oracle_top20

LOG = logging.getLogger(__name__)
PERIODS = (
    ("warmup", "2023-11-01", "2023-12-31"),
    ("2024H1", "2024-01-01", "2024-06-30"),
    ("2024H2", "2024-07-01", "2024-12-31"),
    ("2025H1", "2025-01-01", "2025-06-30"),
    ("2025H2", "2025-07-01", "2025-12-31"),
)


def collect_sanitized(*, max_pages: int = 80) -> tuple[pd.DataFrame, list[dict]]:
    """Never retain the raw vendor payload or its hindsight D1-D30/EXPLAIN fields."""
    if max_pages < 1:
        raise ValueError("max_pages must be positive")
    safe_rows, provenance = [], []
    for name, start, end in PERIODS:
        params = {
            "reportName": "RPT_DAILYBILLBOARD_DETAILSNEW", "columns": "ALL",
            "pageSize": "500", "pageNumber": "1",
            "sortColumns": "TRADE_DATE,SECURITY_CODE", "sortTypes": "-1,-1",
            "filter": f"(TRADE_DATE>='{start}')(TRADE_DATE<='{end}')",
        }
        pages = count = total = None
        digests = []
        for page in range(1, max_pages + 2):
            params["pageNumber"] = str(page)
            raw = _get(EASTMONEY_URL, params, "https://data.eastmoney.com/stock/lhb.html")
            response = _json(raw)
            result = response.get("result") or {}
            data = result.get("data")
            if response.get("success") is not True or not isinstance(data, list):
                raise RuntimeError(f"Eastmoney invalid {name} page {page}")
            current = (int(result.get("pages") or 0), int(result.get("count") or 0))
            if pages is None:
                pages, count = current
                if pages < 1 or pages > max_pages:
                    raise RuntimeError(f"Eastmoney {name} pages={pages} exceeds cap={max_pages}")
                total = 0
            elif current != (pages, count):
                raise RuntimeError(f"Eastmoney pagination changed for {name}")
            total += len(data)
            digests.append(hashlib.sha256(raw).hexdigest())
            for row in data:
                day = str(row.get("TRADE_DATE") or "")[:10]
                if not start <= day <= end:
                    raise RuntimeError(f"Eastmoney period mismatch: {day}")
                safe = sanitize_vendor(row, day)
                if safe is not None:
                    safe_rows.append(safe)
            if page == pages:
                break
        if total != count:
            raise RuntimeError(f"Eastmoney incomplete {name}: {total}/{count}")
        provenance.append({"period": name, "rows_reported": count, "pages": pages,
                           "page_sha256": digests})
        LOG.info("15D4 %s rows=%s pages=%s", name, count, pages)
    return pd.DataFrame(safe_rows), provenance


def resolve_events(rows: pd.DataFrame, mappings: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    if rows.empty:
        raise RuntimeError("No sanitized historical events")
    events = rows[["trade_date", "security_code", "market"]].drop_duplicates().copy()
    events["trade_date"] = pd.to_datetime(events["trade_date"]).dt.normalize()
    events["provider_symbol"] = events["market"].map({"SH": "sh.", "SZ": "sz."}) + events["security_code"]
    mapped = events.merge(mappings, on="provider_symbol", how="left")
    mapped["valid_from"] = pd.to_datetime(mapped["valid_from"])
    mapped["valid_to"] = pd.to_datetime(mapped["valid_to"])
    eligible = mapped["instrument_id"].notna() & mapped["trade_date"].ge(mapped["valid_from"]) & (
        mapped["valid_to"].isna() | mapped["trade_date"].le(mapped["valid_to"])
    )
    good = mapped.loc[eligible, ["trade_date", "provider_symbol", "instrument_id"]].copy()
    good["instrument_id"] = good["instrument_id"].astype("int64")
    if good.duplicated(["trade_date", "provider_symbol"]).any():
        raise RuntimeError("Ambiguous historical instrument mapping")
    unmatched = events.merge(good[["trade_date", "provider_symbol"]],
                             on=["trade_date", "provider_symbol"], how="left", indicator=True)
    missing = unmatched.loc[unmatched["_merge"].eq("left_only")]
    stats = {"unique_events": int(len(events)), "mapped_events": int(len(good)),
             "unmapped_events": int(len(missing)),
             "unmapped_sample": missing[["trade_date", "provider_symbol"]]
             .head(20).astype(str).to_dict("records")}
    return good[["trade_date", "instrument_id"]].drop_duplicates(), stats


def assign_availability(events: pd.DataFrame, sessions: pd.DatetimeIndex,
                        lag: int) -> pd.DataFrame:
    if lag < 1:
        raise ValueError("Same-day Dragon/Tiger availability is forbidden")
    session_index = pd.Index(sessions)
    result = events.copy()
    indexes = session_index.get_indexer(result["trade_date"])
    if (indexes < 0).any():
        raise RuntimeError("Dragon/Tiger event outside open CN sessions")
    future = indexes + lag
    result = result.loc[future < len(sessions)].copy()
    result["available_session"] = sessions[future[future < len(sessions)]]
    result["event_session_index"] = indexes[future < len(sessions)]
    return result


def join_coverage(top: pd.DataFrame, events: pd.DataFrame,
                  sessions: pd.DatetimeIndex, lag: int) -> pd.DataFrame:
    available = assign_availability(events, sessions, lag)
    left = top.copy()
    left["session_date"] = pd.to_datetime(left["session_date"]).dt.normalize()
    left["instrument_id"] = left["instrument_id"].astype("int64")
    left = left.sort_values(["session_date", "instrument_id"])
    right = available.sort_values(["available_session", "instrument_id"])
    joined = pd.merge_asof(
        left, right, left_on="session_date", right_on="available_session",
        by="instrument_id", direction="backward", allow_exact_matches=True,
    )
    index = pd.Index(sessions).get_indexer(joined["session_date"])
    if (index < 0).any():
        raise RuntimeError("Oracle session outside CN calendar")
    joined["age_sessions"] = index - joined["event_session_index"]
    # The age is measured from event day, not the availability day.
    return joined


def summarize(joined: pd.DataFrame, lag: int) -> dict:
    def count(group: pd.DataFrame) -> dict:
        ages = group["age_sessions"]
        return {"oracle_top20_rows": int(len(group)),
                "event_available_ever": int(ages.notna().sum()),
                "event_within_5_sessions": int(ages.between(lag, 5).sum()),
                "event_within_20_sessions": int(ages.between(lag, 20).sum()),
                "within_5_pct": round(100 * ages.between(lag, 5).mean(), 3),
                "within_20_pct": round(100 * ages.between(lag, 20).mean(), 3)}
    return {"lag_sessions": lag, "overall": count(joined),
            "semesters": {str(k): count(v) for k, v in joined.groupby("semester")},
            "boards": {str(k): count(v) for k, v in joined.groupby("board_code")},
            "realized_deciles": {str(k): count(v) for k, v in joined.groupby("oracle_decile")}}


def run(output: Path, oracle_root: Path, *, max_pages: int = 80) -> dict:
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Refusing overwrite: {output}")
    top, sources = load_oracle_top20(oracle_root)
    engine = get_market_engine("CN_A", database_alias="cn_primary")
    with engine.connect() as conn:
        mappings = pd.read_sql(text(
            "SELECT ips.instrument_id,ips.provider_symbol,ips.valid_from,ips.valid_to "
            "FROM instrument_provider_symbols ips JOIN instruments i ON i.instrument_id=ips.instrument_id "
            "WHERE i.market_code='CN_A' AND i.instrument_type='equity' AND ips.provider='baostock'"
        ), conn)
        calendar = pd.read_sql(text(
            "SELECT session_date FROM market_sessions WHERE market_code='CN_A' "
            "AND session_status='open' AND session_date BETWEEN '2023-11-01' AND '2025-12-31' "
            "ORDER BY session_date"
        ), conn)
    sessions = pd.DatetimeIndex(pd.to_datetime(calendar["session_date"])).normalize()
    vendor, provenance = collect_sanitized(max_pages=max_pages)
    events, mapping_stats = resolve_events(vendor, mappings)
    report = {"status": "COVERAGE_PROXY_ONLY_NO_ML_GO",
              "generated_at_utc": datetime.now(timezone.utc).isoformat(),
              "source_periods": [list(p) for p in PERIODS],
              "source_provenance": provenance, "oracle_sources": sources,
              "mapping": mapping_stats, "sanitized_reason_rows": int(len(vendor)),
              "unique_mapped_event_days": int(events["trade_date"].nunique()),
              "coverage": {},
              "pit_warning": "Historical publication times and vintages unproven. J+1/J+2 are research proxies, not PIT certification.",
              "same_day_event_used": False, "raw_vendor_payload_persisted": False,
              "training_performed": False, "database_modified": False,
              "serving_changed": False}
    for lag in (1, 2):
        joined = join_coverage(top, events, sessions, lag)
        report["coverage"][f"JPLUS{lag}"] = summarize(joined, lag)
    output.mkdir(parents=True, exist_ok=True)
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--oracle-root", type=Path, default=Path("artifacts/cn/oracle/sprint10b"))
    parser.add_argument("--max-pages", type=int, default=80)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper()))
    result = run(args.output, args.oracle_root, max_pages=args.max_pages)
    print(json.dumps({"status": result["status"], "mapping": result["mapping"],
                      "coverage": {k: v["overall"] for k, v in result["coverage"].items()}},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
