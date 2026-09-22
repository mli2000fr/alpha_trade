"""Généralisation canonique CN, couverture et enrichissements du Sprint 7-B."""

from __future__ import annotations

import json
import uuid
from collections import Counter, defaultdict
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import bindparam, text
from sqlalchemy.engine import Engine

from service.baostock.symbols import parse_baostock_symbol
from service.market.cn_canonicalizer import _json, _latest, read_pilot_manifest, write_pilot_manifest

CENT = Decimal("0.01")


def select_full_universe(engine: Engine, *, start: date, end: date) -> list[str]:
    """Actions A ayant chevauché la fenêtre, actifs et délistés compris."""
    with engine.connect() as conn:
        rows = [dict(row) for row in conn.execute(text(
            "SELECT staging_id,provider_symbol,status_code,list_date,delist_date,available_at,raw_payload "
            "FROM cn_staging_rows WHERE provider='baostock' AND endpoint='stock_basic' "
            "ORDER BY available_at,staging_id"
        )).mappings()]
    latest, _ = _latest(rows, ("provider_symbol",))
    selected: list[str] = []
    for row in latest:
        payload = _json(row.get("raw_payload"))
        symbol = str(row.get("provider_symbol") or "").lower()
        if payload.get("type") != "1" or not row.get("list_date") or row["list_date"] > end:
            continue
        if row.get("delist_date") and row["delist_date"] < start:
            continue
        try:
            parse_baostock_symbol(symbol)
        except ValueError:
            continue
        selected.append(symbol)
    return sorted(set(selected))


def write_chunks(symbols: list[str], root: Path, *, chunk_size: int) -> list[Path]:
    if chunk_size < 1:
        raise ValueError("chunk_size doit être positif")
    root.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for index, offset in enumerate(range(0, len(symbols), chunk_size)):
        path = root / f"chunk_{index:04d}.txt"
        write_pilot_manifest(symbols[offset : offset + chunk_size], path)
        paths.append(path)
    index_payload = {
        "symbol_count": len(symbols),
        "chunk_size": chunk_size,
        "chunk_count": len(paths),
        "chunks": [path.name for path in paths],
    }
    (root / "index.json").write_text(json.dumps(index_payload, indent=2), encoding="utf-8")
    return paths


def price_limit_policy(*, board: str, session_date: date, is_st: bool, observed_number: int) -> tuple[str, Decimal | None, bool]:
    """Politique conservatrice ; les cinq premières observations restent sans bornes."""
    if observed_number <= 5:
        return "IPO_FIRST_5_OBS_NO_LIMIT_CONSERVATIVE", None, True
    if is_st:
        return "CN_ST_5PCT_V1", Decimal("0.05"), False
    if board == "STAR":
        return "CN_STAR_20PCT_V1", Decimal("0.20"), False
    if board == "CHINEXT" and session_date >= date(2020, 8, 24):
        return "CN_CHINEXT_20PCT_POST_20200824_V1", Decimal("0.20"), False
    return "CN_MAIN_10PCT_V1", Decimal("0.10"), False


def _rounded(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def enrich_manifest(engine: Engine, *, manifest_path: Path) -> dict[str, int]:
    symbols = read_pilot_manifest(manifest_path)
    if not symbols:
        return {"limits": 0, "corporate_actions": 0}
    expanding = bindparam("symbols", expanding=True)
    bars_stmt = text(
        "SELECT b.*,ips.provider_symbol,COALESCE(s.board_code,'UNKNOWN') board_code "
        "FROM stock_bars_daily b JOIN instrument_provider_symbols ips ON ips.instrument_id=b.instrument_id "
        "LEFT JOIN instrument_status_history s ON s.instrument_id=b.instrument_id AND s.valid_from=b.date "
        "AND s.source='baostock_daily' WHERE ips.provider='baostock' AND ips.provider_symbol IN :symbols "
        "ORDER BY b.instrument_id,b.date"
    ).bindparams(expanding)
    factors_stmt = text(
        "SELECT f.*,ips.provider_symbol FROM instrument_adjustment_factors f "
        "JOIN instrument_provider_symbols ips ON ips.instrument_id=f.instrument_id "
        "WHERE ips.provider='baostock' AND ips.provider_symbol IN :symbols "
        "ORDER BY f.instrument_id,f.effective_date"
    ).bindparams(expanding)
    with engine.connect() as conn:
        bars = [dict(row) for row in conn.execute(bars_stmt, {"symbols": symbols}).mappings()]
        factors = [dict(row) for row in conn.execute(factors_stmt, {"symbols": symbols}).mappings()]
    limit_rows: list[dict[str, Any]] = []
    observed_numbers: Counter[int] = Counter()
    for row in bars:
        instrument_id = int(row["instrument_id"])
        observed_numbers[instrument_id] += 1
        pre_close = Decimal(str(row["pre_close"])) if row.get("pre_close") not in (None, 0) else None
        policy, pct, exception = price_limit_policy(
            board=str(row.get("board_code") or "UNKNOWN"),
            session_date=row["date"],
            is_st=bool(row.get("is_special_treatment")),
            observed_number=observed_numbers[instrument_id],
        )
        up = _rounded(pre_close * (1 + pct)) if pre_close is not None and pct is not None else None
        down = _rounded(pre_close * (1 - pct)) if pre_close is not None and pct is not None else None
        high = Decimal(str(row["high"]))
        low = Decimal(str(row["low"]))
        tolerance = Decimal("0.005")
        limit_rows.append({
            "id": instrument_id, "date": row["date"], "reference": pre_close,
            "up": up, "down": down, "pct": pct, "policy": policy,
            "exception": exception or pre_close is None,
            "reached_up": None if up is None else high >= up - tolerance,
            "reached_down": None if down is None else low <= down + tolerance,
            "locked_up": None if up is None else low >= up - tolerance,
            "locked_down": None if down is None else high <= down + tolerance,
            "observed": row["observed_at"], "available": row["available_at"],
        })
    action_rows: list[dict[str, Any]] = []
    previous: dict[int, Decimal] = {}
    for row in factors:
        instrument_id = int(row["instrument_id"])
        value = Decimal(str(row["adjustment_factor"]))
        before = previous.get(instrument_id)
        previous[instrument_id] = value
        if before is None or value == before:
            continue
        action_rows.append({
            "id": instrument_id, "date": row["effective_date"], "value": value,
            "before": before, "hash": row["source_payload_hash"],
            "observed": row["observed_at"], "available": row["available_at"],
        })
    limit_sql = text(
        "INSERT INTO cn_daily_price_limits(instrument_id,session_date,reference_close,limit_up,limit_down,limit_pct,policy_code,derivation_method,is_rule_exception,reached_up,reached_down,locked_up,locked_down,source,observed_at,available_at) "
        "VALUES (:id,:date,:reference,:up,:down,:pct,:policy,'board_rule_v1',:exception,:reached_up,:reached_down,:locked_up,:locked_down,'alpha_trade_derived',:observed,:available) "
        "ON DUPLICATE KEY UPDATE reference_close=VALUES(reference_close),limit_up=VALUES(limit_up),limit_down=VALUES(limit_down),limit_pct=VALUES(limit_pct),policy_code=VALUES(policy_code),is_rule_exception=VALUES(is_rule_exception),reached_up=VALUES(reached_up),reached_down=VALUES(reached_down),locked_up=VALUES(locked_up),locked_down=VALUES(locked_down),observed_at=VALUES(observed_at),available_at=VALUES(available_at)"
    )
    action_sql = text(
        "INSERT INTO cn_corporate_actions(instrument_id,action_type,ex_date,factor_value,previous_factor_value,classification_status,source,source_payload_hash,observed_at,available_at) "
        "VALUES (:id,'adjustment_factor_change',:date,:value,:before,'UNCLASSIFIED_FACTOR_EVENT','baostock',:hash,:observed,:available) "
        "ON DUPLICATE KEY UPDATE factor_value=VALUES(factor_value),previous_factor_value=VALUES(previous_factor_value),observed_at=VALUES(observed_at),available_at=VALUES(available_at)"
    )
    with engine.begin() as conn:
        if limit_rows:
            conn.execute(limit_sql, limit_rows)
        if action_rows:
            conn.execute(action_sql, action_rows)
    return {"limits": len(limit_rows), "corporate_actions": len(action_rows)}


def measure_coverage(engine: Engine, *, manifest_path: Path, start: date, end: date) -> dict[str, Any]:
    symbols = read_pilot_manifest(manifest_path)
    expanding = bindparam("symbols", expanding=True)
    instrument_stmt = text(
        "SELECT i.instrument_id,i.listing_date,i.delisting_date,ips.provider_symbol "
        "FROM instruments i JOIN instrument_provider_symbols ips ON ips.instrument_id=i.instrument_id "
        "WHERE i.instrument_type='equity' AND ips.provider='baostock' AND ips.provider_symbol IN :symbols"
    ).bindparams(expanding)
    bars_stmt = text(
        "SELECT b.instrument_id,YEAR(b.date) y,COUNT(*) n,SUM(b.trading_status LIKE 'SUSPENDED%') suspended "
        "FROM stock_bars_daily b JOIN instrument_provider_symbols ips ON ips.instrument_id=b.instrument_id "
        "WHERE ips.provider='baostock' AND ips.provider_symbol IN :symbols AND b.date BETWEEN :start AND :end "
        "GROUP BY b.instrument_id,YEAR(b.date)"
    ).bindparams(expanding)
    factor_stmt = text(
        "SELECT f.instrument_id,YEAR(f.effective_date) y,COUNT(*) n FROM instrument_adjustment_factors f "
        "JOIN instrument_provider_symbols ips ON ips.instrument_id=f.instrument_id "
        "WHERE ips.provider='baostock' AND ips.provider_symbol IN :symbols AND f.effective_date BETWEEN :start AND :end "
        "GROUP BY f.instrument_id,YEAR(f.effective_date)"
    ).bindparams(expanding)
    with engine.connect() as conn:
        instruments = [dict(row) for row in conn.execute(instrument_stmt, {"symbols": symbols}).mappings()]
        sessions = [row[0] for row in conn.execute(text(
            "SELECT session_date FROM market_sessions WHERE market_code='CN_A' AND session_status='open' "
            "AND session_date BETWEEN :start AND :end ORDER BY session_date"
        ), {"start": start, "end": end})]
        observed = {(int(row.instrument_id), int(row.y)): (int(row.n), int(row.suspended or 0)) for row in conn.execute(bars_stmt, {"symbols": symbols, "start": start, "end": end})}
        factors = {(int(row.instrument_id), int(row.y)): int(row.n) for row in conn.execute(factor_stmt, {"symbols": symbols, "start": start, "end": end})}
    aggregates: dict[tuple[str, int], dict[str, Any]] = defaultdict(lambda: {"instruments": set(), "expected": 0, "observed": 0, "suspended": 0, "factors": 0})
    for item in instruments:
        board = parse_baostock_symbol(item["provider_symbol"]).board_code
        listing = item["listing_date"] or start
        delisting = item["delisting_date"] or end
        for year in range(max(start.year, listing.year), min(end.year, delisting.year) + 1):
            key = (board, year)
            bucket = aggregates[key]
            bucket["instruments"].add(int(item["instrument_id"]))
            bucket["expected"] += sum(1 for value in sessions if value.year == year and listing <= value <= delisting)
            count, suspended = observed.get((int(item["instrument_id"]), year), (0, 0))
            bucket["observed"] += count
            bucket["suspended"] += suspended
            bucket["factors"] += factors.get((int(item["instrument_id"]), year), 0)
    run_id = f"cn-s7b-coverage-{datetime.now(UTC):%Y%m%d%H%M%S}-{uuid.uuid4().hex[:8]}"
    rows: list[dict[str, Any]] = []
    for (board, year), values in sorted(aggregates.items()):
        expected = int(values["expected"])
        observed_count = int(values["observed"])
        ratio = Decimal(observed_count) / Decimal(expected) if expected else None
        status = "PASS" if ratio is not None and ratio >= Decimal("0.95") else "INCOMPLETE"
        rows.append({
            "run": run_id, "board": board, "year": year, "instruments": len(values["instruments"]),
            "expected": expected, "observed": observed_count, "suspended": int(values["suspended"]),
            "factors": int(values["factors"]), "ratio": ratio, "status": status,
            "details": json.dumps({"threshold": 0.95, "scope_symbols": len(symbols)}),
            "measured": datetime.now(UTC).replace(tzinfo=None),
        })
    insert = text(
        "INSERT INTO cn_canonical_coverage_metrics(coverage_run_id,market_code,board_code,calendar_year,instrument_count,expected_bar_count,observed_bar_count,explicit_suspension_count,factor_event_count,coverage_ratio,status,details_json,measured_at) "
        "VALUES (:run,'CN_A',:board,:year,:instruments,:expected,:observed,:suspended,:factors,:ratio,:status,:details,:measured)"
    )
    with engine.begin() as conn:
        if rows:
            conn.execute(insert, rows)
    return {"coverage_run_id": run_id, "rows": len(rows), "pass": sum(row["status"] == "PASS" for row in rows), "incomplete": sum(row["status"] != "PASS" for row in rows)}


def audit_full(engine: Engine, *, manifest_path: Path) -> dict[str, Any]:
    symbols = read_pilot_manifest(manifest_path)
    expanding = bindparam("symbols", expanding=True)
    stmt = text(
        "SELECT COUNT(DISTINCT ips.provider_symbol) mapped,COUNT(DISTINCT CASE WHEN b.instrument_id IS NOT NULL THEN ips.provider_symbol END) with_bars "
        "FROM instrument_provider_symbols ips JOIN instruments i ON i.instrument_id=ips.instrument_id "
        "LEFT JOIN stock_bars_daily b ON b.instrument_id=i.instrument_id "
        "WHERE ips.provider='baostock' AND ips.provider_symbol IN :symbols"
    ).bindparams(expanding)
    with engine.connect() as conn:
        row = conn.execute(stmt, {"symbols": symbols}).mappings().one()
        counts = {
            "limits": int(conn.execute(text("SELECT COUNT(*) FROM cn_daily_price_limits")).scalar() or 0),
            "corporate_actions": int(conn.execute(text("SELECT COUNT(*) FROM cn_corporate_actions")).scalar() or 0),
            "coverage_metrics": int(conn.execute(text("SELECT COUNT(*) FROM cn_canonical_coverage_metrics")).scalar() or 0),
        }
    mapped = int(row["mapped"] or 0)
    with_bars = int(row["with_bars"] or 0)
    status = "PASS" if mapped == len(symbols) and with_bars == len(symbols) else "IN_PROGRESS"
    return {"status": status, "manifest_symbols": len(symbols), "mapped": mapped, "with_bars": with_bars, **counts}


__all__ = ["audit_full", "enrich_manifest", "measure_coverage", "price_limit_policy", "select_full_universe", "write_chunks"]
