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
    if board == "STAR":
        return "CN_STAR_20PCT_V1", Decimal("0.20"), False
    if board == "CHINEXT" and session_date >= date(2020, 8, 24):
        return "CN_CHINEXT_20PCT_POST_20200824_V1", Decimal("0.20"), False
    if is_st and board in {"SH_MAIN", "SZ_MAIN"} and session_date >= date(2026, 7, 6):
        return "CN_MAIN_ST_10PCT_POST_20260706_V1", Decimal("0.10"), False
    if is_st:
        return "CN_ST_5PCT_V1", Decimal("0.05"), False
    return "CN_MAIN_10PCT_V1", Decimal("0.10"), False


def _rounded(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def derived_limit_for_bar(*, board: str, session_date: date, is_st: bool, observed_number: int,
                          pre_close: Decimal | None, high: Decimal, low: Decimal) -> dict[str, Any]:
    """Ne publie pas une borne démentie par l'OHLC connu à la clôture.

    Le contrôle de cohérence est disponible seulement après la séance. Une
    borne ainsi invalidée ne peut pas servir de preuve PIT d'exécutabilité
    pendant cette même séance.
    """
    policy, pct, exception = price_limit_policy(
        board=board, session_date=session_date, is_st=is_st,
        observed_number=observed_number,
    )
    up = _rounded(pre_close * (1 + pct)) if pre_close is not None and pct is not None else None
    down = _rounded(pre_close * (1 - pct)) if pre_close is not None and pct is not None else None
    tolerance = Decimal("0.005")
    if up is not None and down is not None and (high > up + tolerance or low < down - tolerance):
        return {
            "policy": "OBSERVED_OUTSIDE_DERIVED_LIMIT_V1", "derivation": "observed_break_v1",
            "pct": None, "up": None, "down": None, "exception": True,
            "reached_up": None, "reached_down": None, "locked_up": None, "locked_down": None,
        }
    return {
        "policy": policy, "derivation": "board_rule_v2", "pct": pct,
        "up": up, "down": down, "exception": exception or pre_close is None,
        "reached_up": None if up is None else high >= up - tolerance,
        "reached_down": None if down is None else low <= down + tolerance,
        "locked_up": None if up is None else low >= up - tolerance,
        "locked_down": None if down is None else high <= down + tolerance,
    }


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
        derived = derived_limit_for_bar(
            board=str(row.get("board_code") or "UNKNOWN"),
            session_date=row["date"],
            is_st=bool(row.get("is_special_treatment")),
            observed_number=observed_numbers[instrument_id],
            pre_close=pre_close,
            high=Decimal(str(row["high"])),
            low=Decimal(str(row["low"])),
        )
        limit_rows.append({
            "id": instrument_id, "date": row["date"], "reference": pre_close,
            **derived,
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
        "VALUES (:id,:date,:reference,:up,:down,:pct,:policy,:derivation,:exception,:reached_up,:reached_down,:locked_up,:locked_down,'alpha_trade_derived',:observed,:available) "
        "ON DUPLICATE KEY UPDATE reference_close=VALUES(reference_close),limit_up=VALUES(limit_up),limit_down=VALUES(limit_down),limit_pct=VALUES(limit_pct),policy_code=VALUES(policy_code),derivation_method=VALUES(derivation_method),is_rule_exception=VALUES(is_rule_exception),reached_up=VALUES(reached_up),reached_down=VALUES(reached_down),locked_up=VALUES(locked_up),locked_down=VALUES(locked_down),observed_at=VALUES(observed_at),available_at=VALUES(available_at)"
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


def remediate_historical_quality(engine: Engine, *, start: date, end: date) -> dict[str, int]:
    """Répare les limites dérivées et signale les statuts contradictoires.

    Ne modifie ni le staging, ni les OHLC, ni les données US. Les journées dont
    l'OHLC contredit encore la règle après correction restent sans borne fiable.
    Les flags fondés sur l'OHLC ne deviennent connaissables qu'à la clôture.
    """
    params = {"start": start, "end": end}
    growth_st = text(
        "UPDATE cn_daily_price_limits l "
        "JOIN stock_bars_daily b ON b.instrument_id=l.instrument_id AND b.date=l.session_date "
        "JOIN instrument_status_history s ON s.instrument_id=b.instrument_id AND s.valid_from=b.date "
        "AND s.source='baostock_daily' "
        "SET l.reference_close=b.pre_close,l.limit_up=ROUND(b.pre_close*1.20,2),"
        "l.limit_down=ROUND(b.pre_close*0.80,2),l.limit_pct=0.20,"
        "l.policy_code=CASE WHEN s.board_code='STAR' THEN 'CN_STAR_20PCT_V1' "
        "ELSE 'CN_CHINEXT_20PCT_POST_20200824_V1' END,"
        "l.derivation_method='board_rule_v2',"
        "l.reached_up=(b.high>=ROUND(b.pre_close*1.20,2)-0.005),"
        "l.reached_down=(b.low<=ROUND(b.pre_close*0.80,2)+0.005),"
        "l.locked_up=(b.low>=ROUND(b.pre_close*1.20,2)-0.005),"
        "l.locked_down=(b.high<=ROUND(b.pre_close*0.80,2)+0.005) "
        "WHERE b.market_code='CN_A' AND l.session_date BETWEEN :start AND :end "
        "AND l.policy_code='CN_ST_5PCT_V1' AND l.is_rule_exception=0 "
        "AND (s.board_code='STAR' OR (s.board_code='CHINEXT' AND l.session_date>='2020-08-24'))"
    )
    unverified = text(
        "UPDATE cn_daily_price_limits l "
        "JOIN stock_bars_daily b ON b.instrument_id=l.instrument_id AND b.date=l.session_date "
        "SET l.limit_up=NULL,l.limit_down=NULL,l.limit_pct=NULL,"
        "l.policy_code='OBSERVED_OUTSIDE_DERIVED_LIMIT_V1',"
        "l.derivation_method='observed_break_v1',l.is_rule_exception=1,"
        "l.reached_up=NULL,l.reached_down=NULL,l.locked_up=NULL,l.locked_down=NULL "
        "WHERE b.market_code='CN_A' AND l.session_date BETWEEN :start AND :end "
        "AND l.is_rule_exception=0 AND l.limit_up IS NOT NULL AND l.limit_down IS NOT NULL "
        "AND (b.high>l.limit_up+0.005 OR b.low<l.limit_down-0.005)"
    )
    conflicted_statuses = text(
        "UPDATE instrument_status_history s "
        "JOIN stock_bars_daily b ON b.instrument_id=s.instrument_id AND b.date=s.valid_from "
        "SET s.trading_status=CONCAT(s.trading_status,'|SOURCE_CONFLICT'),s.is_tradable=0 "
        "WHERE b.market_code='CN_A' AND b.date BETWEEN :start AND :end "
        "AND s.source='baostock_daily' AND b.trading_status LIKE 'SUSPENDED%' "
        "AND (b.volume>0 OR b.amount>0) "
        "AND s.trading_status NOT LIKE '%|SOURCE_CONFLICT'"
    )
    conflicted_bars = text(
        "UPDATE stock_bars_daily SET trading_status=CONCAT(trading_status,'|SOURCE_CONFLICT') "
        "WHERE market_code='CN_A' AND date BETWEEN :start AND :end "
        "AND trading_status LIKE 'SUSPENDED%' AND (volume>0 OR amount>0) "
        "AND trading_status NOT LIKE '%|SOURCE_CONFLICT'"
    )
    with engine.begin() as conn:
        result = {
            "growth_st_reclassified": conn.execute(growth_st, params).rowcount,
            "unverified_limits": conn.execute(unverified, params).rowcount,
            "conflicted_statuses": conn.execute(conflicted_statuses, params).rowcount,
            "conflicted_bars": conn.execute(conflicted_bars, params).rowcount,
        }
    return result


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
    terminal_stmt = text(
        "SELECT ips.provider_symbol,i.delisting_date "
        "FROM instruments i JOIN instrument_provider_symbols ips ON ips.instrument_id=i.instrument_id "
        "JOIN market_sessions s ON s.market_code='CN_A' AND s.session_date=i.delisting_date "
        "AND s.session_status='open' "
        "LEFT JOIN stock_bars_daily b ON b.instrument_id=i.instrument_id AND b.date=i.delisting_date "
        "WHERE i.market_code='CN_A' AND i.instrument_type='equity' AND ips.provider='baostock' "
        "AND ips.provider_symbol IN :symbols AND i.delisting_date BETWEEN :start AND :end "
        "AND b.instrument_id IS NULL"
    ).bindparams(expanding)
    with engine.connect() as conn:
        instruments = [dict(row) for row in conn.execute(instrument_stmt, {"symbols": symbols}).mappings()]
        sessions = [row[0] for row in conn.execute(text(
            "SELECT session_date FROM market_sessions WHERE market_code='CN_A' AND session_status='open' "
            "AND session_date BETWEEN :start AND :end ORDER BY session_date"
        ), {"start": start, "end": end})]
        observed = {(int(row.instrument_id), int(row.y)): (int(row.n), int(row.suspended or 0)) for row in conn.execute(bars_stmt, {"symbols": symbols, "start": start, "end": end})}
        factors = {(int(row.instrument_id), int(row.y)): int(row.n) for row in conn.execute(factor_stmt, {"symbols": symbols, "start": start, "end": end})}
        terminal_absences = [dict(row) for row in conn.execute(
            terminal_stmt, {"symbols": symbols, "start": start, "end": end}
        ).mappings()]
    accepted_terminal = Counter(
        (parse_baostock_symbol(row["provider_symbol"]).board_code, row["delisting_date"].year)
        for row in terminal_absences
    )
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
        terminal_count = accepted_terminal.get((board, year), 0)
        unexplained = max(0, expected - observed_count - terminal_count)
        ratio = Decimal(observed_count) / Decimal(expected) if expected else None
        status = "PASS" if ratio is not None and ratio >= Decimal("0.95") and unexplained == 0 else "INCOMPLETE"
        rows.append({
            "run": run_id, "board": board, "year": year, "instruments": len(values["instruments"]),
            "expected": expected, "observed": observed_count, "suspended": int(values["suspended"]),
            "factors": int(values["factors"]), "ratio": ratio, "status": status,
            "details": json.dumps({
                "threshold": 0.95, "scope_symbols": len(symbols),
                "delisting_day_no_bar": terminal_count,
                "unexplained_missing": unexplained,
                "delisting_date_inclusive": True,
            }),
            "measured": datetime.now(UTC).replace(tzinfo=None),
        })
    insert = text(
        "INSERT INTO cn_canonical_coverage_metrics(coverage_run_id,market_code,board_code,calendar_year,instrument_count,expected_bar_count,observed_bar_count,explicit_suspension_count,factor_event_count,coverage_ratio,status,details_json,measured_at) "
        "VALUES (:run,'CN_A',:board,:year,:instruments,:expected,:observed,:suspended,:factors,:ratio,:status,:details,:measured)"
    )
    with engine.begin() as conn:
        if rows:
            conn.execute(insert, rows)
    return {
        "coverage_run_id": run_id, "rows": len(rows),
        "pass": sum(row["status"] == "PASS" for row in rows),
        "incomplete": sum(row["status"] != "PASS" for row in rows),
        "delisting_day_no_bar": sum(accepted_terminal.values()),
        "unexplained_missing": sum(json.loads(row["details"])["unexplained_missing"] for row in rows),
    }


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


__all__ = ["audit_full", "derived_limit_for_bar", "enrich_manifest", "measure_coverage", "price_limit_policy", "remediate_historical_quality", "select_full_universe", "write_chunks"]
