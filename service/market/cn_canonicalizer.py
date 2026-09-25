"""Promotion contrôlée du staging BaoStock vers le canonique CN (Sprint 7-A)."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import bindparam, text
from sqlalchemy.engine import Engine

from database.repositories.instruments import build_instrument_uid
from service.baostock.symbols import parse_baostock_symbol

INDEX_SYMBOLS = ("sh.000001", "sz.399001", "sh.000300", "sz.399006")
INDEX_NAMES = {
    "sh.000001": "SSE Composite",
    "sz.399001": "Shenzhen Component",
    "sh.000300": "CSI 300",
    "sz.399006": "ChiNext Index",
}
PILOT_QUOTAS = {"SH_MAIN": 25, "SZ_MAIN": 25, "STAR": 15, "CHINEXT": 15}
SHANGHAI = ZoneInfo("Asia/Shanghai")


@dataclass(slots=True)
class CanonicalizationReport:
    run_id: str
    selected_equities: int = 0
    selected_indices: int = 0
    instruments: int = 0
    provider_mappings: int = 0
    sessions: int = 0
    bars: int = 0
    factors: int = 0
    statuses: int = 0
    rejected_rows: int = 0
    duplicate_source_revisions: int = 0
    missing_equity_bars: list[str] | None = None
    board_counts: dict[str, int] | None = None
    status: str = "RUNNING"


def _json(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if value in (None, ""):
        return {}
    return json.loads(str(value))


def _latest(rows: Iterable[dict[str, Any]], key_fields: tuple[str, ...]) -> tuple[list[dict[str, Any]], int]:
    selected: dict[tuple[Any, ...], dict[str, Any]] = {}
    duplicates = 0
    for row in rows:
        key = tuple(row.get(field) for field in key_fields)
        current = selected.get(key)
        if current is not None:
            duplicates += 1
        if current is None or (row.get("available_at"), row.get("staging_id")) > (
            current.get("available_at"), current.get("staging_id")
        ):
            selected[key] = row
    return list(selected.values()), duplicates


def _spread_pick(values: list[str], count: int) -> list[str]:
    values = sorted(set(values))
    if len(values) <= count:
        return values
    if count <= 1:
        return [values[len(values) // 2]]
    indexes = [round(index * (len(values) - 1) / (count - 1)) for index in range(count)]
    return [values[index] for index in indexes]


def select_pilot_symbols(
    engine: Engine,
    *,
    quotas: dict[str, int] | None = None,
    as_of: date | None = None,
    history_start: date | None = None,
) -> list[str]:
    """Sélection stratifiée sans rendement futur, avec remplacement des IPO futures."""
    quotas = dict(quotas or PILOT_QUOTAS)
    as_of = as_of or date.today()
    history_start = history_start or as_of
    with engine.connect() as conn:
        rows = [dict(row) for row in conn.execute(text(
            "SELECT staging_id,provider_symbol,board_code,status_code,list_date,delist_date,available_at,raw_payload "
            "FROM cn_staging_rows WHERE provider='baostock' AND endpoint='stock_basic' "
            "ORDER BY available_at,staging_id"
        )).mappings()]
    latest, _ = _latest(rows, ("provider_symbol",))
    by_board: dict[str, list[str]] = defaultdict(list)
    list_dates: dict[str, date] = {}
    for row in latest:
        symbol = str(row.get("provider_symbol") or "").lower()
        payload = _json(row.get("raw_payload"))
        if (
            payload.get("type") != "1"
            or str(row.get("status_code") or payload.get("status")) != "1"
            or not row.get("list_date")
        ):
            continue
        try:
            parsed = parse_baostock_symbol(symbol)
        except ValueError:
            continue
        if parsed.board_code in quotas:
            by_board[parsed.board_code].append(symbol)
            list_dates[symbol] = row["list_date"]
    selected: list[str] = []
    for board, count in quotas.items():
        candidates = by_board.get(board, [])
        if len(candidates) < count:
            raise RuntimeError(f"Pilote impossible : {board} contient {len(candidates)} titres, attendu={count}")
        board_selection = _spread_pick(candidates, count)
        replacements = iter(sorted((
            symbol for symbol in candidates
            if list_dates[symbol] <= history_start and symbol not in board_selection
        ), reverse=True))
        selected.extend(
            symbol if list_dates[symbol] <= as_of else next(replacements)
            for symbol in board_selection
        )
    return sorted(selected)


def write_pilot_manifest(symbols: list[str], path: Path) -> str:
    normalized = sorted(set(symbols))
    content = ",".join(normalized) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def read_pilot_manifest(path: Path) -> list[str]:
    return sorted({value.strip().lower() for value in path.read_text(encoding="utf-8").replace("\n", ",").split(",") if value.strip()})


def _mic(exchange: str) -> str:
    return {"SH": "XSHG", "SZ": "XSHE"}[str(exchange).upper()]


def _utc_session(session_date: date) -> tuple[datetime, datetime, str]:
    morning_open = datetime.combine(session_date, time(9, 30), SHANGHAI)
    morning_close = datetime.combine(session_date, time(11, 30), SHANGHAI)
    afternoon_open = datetime.combine(session_date, time(13, 0), SHANGHAI)
    afternoon_close = datetime.combine(session_date, time(15, 0), SHANGHAI)
    def utc_naive(value: datetime) -> datetime:
        return value.astimezone(UTC).replace(tzinfo=None)
    segments = json.dumps([
        {"name": "continuous_am", "open_at_utc": utc_naive(morning_open).isoformat(), "close_at_utc": utc_naive(morning_close).isoformat()},
        {"name": "continuous_pm", "open_at_utc": utc_naive(afternoon_open).isoformat(), "close_at_utc": utc_naive(afternoon_close).isoformat()},
    ], separators=(",", ":"), sort_keys=True)
    return utc_naive(morning_open), utc_naive(afternoon_close), segments


def _pit_close(session_date: date) -> datetime:
    """Instant économique où une barre quotidienne CN devient connaissable."""
    return datetime.combine(session_date, time(15, 0), SHANGHAI).astimezone(UTC).replace(tzinfo=None)


def _valid_bar(row: dict[str, Any]) -> bool:
    values = [row.get(name) for name in ("open_price", "high_price", "low_price", "close_price")]
    if any(value is None for value in values):
        return False
    opn, high, low, close = (Decimal(str(value)) for value in values)
    volume = row.get("volume")
    amount = row.get("amount")
    return (
        min(opn, high, low, close) >= 0
        and high >= max(opn, close, low)
        and low <= min(opn, close, high)
        and (volume is None or Decimal(str(volume)) >= 0)
        and (amount is None or Decimal(str(amount)) >= 0)
    )


def canonical_trading_status(raw_status: str, volume: Any, amount: Any) -> str:
    """Signale une suspension contradictoire sans inventer une séance tradable."""
    status = str(raw_status or "TRADE")
    if (
        status.startswith("SUSPENDED")
        and not status.endswith("|SOURCE_CONFLICT")
        and any(value is not None and Decimal(str(value)) > 0 for value in (volume, amount))
    ):
        return f"{status}|SOURCE_CONFLICT"
    return status


def promote_pilot(engine: Engine, *, manifest_path: Path, staging_cutoff: datetime | None = None) -> CanonicalizationReport:
    symbols = read_pilot_manifest(manifest_path)
    manifest_hash = hashlib.sha256((",".join(symbols) + "\n").encode()).hexdigest()
    cutoff = staging_cutoff or datetime.now(UTC).replace(tzinfo=None)
    run_id = f"cn-s7a-{datetime.now(UTC):%Y%m%d%H%M%S}-{uuid.uuid4().hex[:8]}"
    report = CanonicalizationReport(run_id, len(symbols), len(INDEX_SYMBOLS), missing_equity_bars=[])
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO cn_canonicalization_runs(canonicalization_run_id,staging_cutoff,pilot_manifest_hash,status,selected_instruments,started_at) "
            "VALUES (:run,:cutoff,:hash,'RUNNING',:selected,:started)"
        ), {"run": run_id, "cutoff": cutoff, "hash": manifest_hash, "selected": len(symbols) + len(INDEX_SYMBOLS), "started": datetime.now(UTC).replace(tzinfo=None)})
    try:
        wanted = set(symbols) | set(INDEX_SYMBOLS)
        wanted_values = sorted(wanted)
        symbol_filter = bindparam("wanted", expanding=True)
        master_statement = text(
            "SELECT * FROM cn_staging_rows WHERE provider='baostock' AND available_at<=:cutoff "
            "AND endpoint='stock_basic' AND provider_symbol IN :wanted ORDER BY available_at,staging_id"
        ).bindparams(symbol_filter)
        data_statement = text(
            "SELECT * FROM cn_staging_rows WHERE provider='baostock' AND available_at<=:cutoff "
            "AND endpoint IN ('daily','index_daily','adj_factor') AND provider_symbol IN :wanted "
            "ORDER BY available_at,staging_id"
        ).bindparams(symbol_filter)
        with engine.connect() as conn:
            rows = [dict(row) for row in conn.execute(master_statement, {"cutoff": cutoff, "wanted": wanted_values}).mappings()]
            rows.extend(dict(row) for row in conn.execute(text(
                "SELECT * FROM cn_staging_rows WHERE provider='baostock' AND available_at<=:cutoff "
                "AND endpoint='trade_cal' ORDER BY available_at,staging_id"
            ), {"cutoff": cutoff}).mappings())
            rows.extend(dict(row) for row in conn.execute(data_statement, {"cutoff": cutoff, "wanted": wanted_values}).mappings())
        master, dup_master = _latest((row for row in rows if row["endpoint"] == "stock_basic"), ("provider_symbol",))
        sessions, dup_sessions = _latest((row for row in rows if row["endpoint"] == "trade_cal"), ("business_date",))
        bars, dup_bars = _latest((row for row in rows if row["endpoint"] in {"daily", "index_daily"} and row.get("provider_symbol") in wanted), ("provider_symbol", "business_date"))
        factors, dup_factors = _latest((row for row in rows if row["endpoint"] == "adj_factor" and row.get("provider_symbol") in symbols), ("provider_symbol", "business_date"))
        report.duplicate_source_revisions = dup_master + dup_sessions + dup_bars + dup_factors
        master_by_symbol = {str(row["provider_symbol"]).lower(): row for row in master if row.get("provider_symbol")}
        instrument_rows: list[dict[str, Any]] = []
        for symbol in sorted(wanted):
            parsed = parse_baostock_symbol(symbol)
            source = master_by_symbol.get(symbol, {})
            is_index = symbol in INDEX_SYMBOLS
            listing = None if is_index else source.get("list_date")
            identity = f"baostock:{symbol}:{listing or 'unknown'}:{'index' if is_index else 'equity'}"
            instrument_rows.append({
                "uid": build_instrument_uid("CN_A", _mic(parsed.exchange_code), identity),
                "market": "CN_A", "mic": _mic(parsed.exchange_code), "symbol": parsed.local_symbol,
                "name": INDEX_NAMES.get(symbol) or source.get("name"), "type": "index" if is_index else "equity",
                "listing": listing, "delisting": None if is_index else source.get("delist_date"),
                "active": True if is_index else str(source.get("status_code") or "1") == "1", "provider_symbol": symbol,
                "board": "INDEX" if is_index else parsed.board_code,
            })
        with engine.begin() as conn:
            for item in instrument_rows:
                conn.execute(text(
                    "INSERT INTO instruments(instrument_uid,market_code,exchange_mic,local_symbol,display_name,instrument_type,currency,listing_date,delisting_date,mapping_status,is_active) "
                    "VALUES (:uid,:market,:mic,:symbol,:name,:type,'CNY',:listing,:delisting,'mapped',:active) "
                    "ON DUPLICATE KEY UPDATE display_name=VALUES(display_name),listing_date=VALUES(listing_date),delisting_date=VALUES(delisting_date),is_active=VALUES(is_active)"
                ), item)
            ids = {row.provider_symbol: int(row.instrument_id) for row in conn.execute(text(
                "SELECT i.instrument_id,ips.provider_symbol FROM instruments i JOIN instrument_provider_symbols ips ON ips.instrument_id=i.instrument_id WHERE 1=0"
            ))} if False else {}
            canonical = {row.local_symbol + '|' + row.exchange_mic: int(row.instrument_id) for row in conn.execute(text("SELECT instrument_id,local_symbol,exchange_mic FROM instruments WHERE market_code='CN_A'"))}
            for item in instrument_rows:
                instrument_id = canonical[item["symbol"] + "|" + item["mic"]]
                ids[item["provider_symbol"]] = instrument_id
                valid_from = item["listing"] or date(1990, 1, 1)
                conn.execute(text(
                    "INSERT INTO instrument_provider_symbols(instrument_id,provider,provider_symbol,provider_exchange,valid_from,valid_to,is_primary) "
                    "VALUES (:id,'baostock',:provider_symbol,:exchange,:valid_from,:valid_to,TRUE) "
                    "ON DUPLICATE KEY UPDATE provider_exchange=VALUES(provider_exchange),valid_to=VALUES(valid_to),is_primary=TRUE"
                ), {"id": instrument_id, "provider_symbol": item["provider_symbol"], "exchange": item["mic"], "valid_from": valid_from, "valid_to": item["delisting"]})
            report.instruments = len(instrument_rows)
            report.provider_mappings = len(instrument_rows)
            for row in sessions:
                session_date = row.get("business_date")
                if not session_date:
                    report.rejected_rows += 1
                    continue
                is_open = bool(row.get("is_open"))
                opn, close, segments = _utc_session(session_date) if is_open else (None, None, None)
                conn.execute(text(
                    "INSERT INTO market_sessions(market_code,session_date,session_status,open_at_utc,close_at_utc,session_segments_json,source,observed_at,available_at) "
                    "VALUES ('CN_A',:date,:status,:open,:close,:segments,'baostock_trade_cal+cn_a_schedule_v1',:observed,:available) "
                    "ON DUPLICATE KEY UPDATE session_status=VALUES(session_status),open_at_utc=VALUES(open_at_utc),close_at_utc=VALUES(close_at_utc),session_segments_json=VALUES(session_segments_json),observed_at=VALUES(observed_at),available_at=VALUES(available_at)"
                ), {"date": session_date, "status": "open" if is_open else "closed", "open": opn, "close": close, "segments": segments, "observed": _pit_close(session_date), "available": _pit_close(session_date)})
                report.sessions += 1
            seen_bar_symbols: set[str] = set()
            for row in bars:
                symbol = str(row.get("provider_symbol") or "").lower()
                if symbol not in ids or not _valid_bar(row):
                    report.rejected_rows += 1
                    continue
                seen_bar_symbols.add(symbol)
                close = Decimal(str(row["close_price"]))
                pre = Decimal(str(row["pre_close"])) if row.get("pre_close") not in (None, 0) else None
                daily_return = (close / pre - 1) if pre and pre != 0 else None
                status = canonical_trading_status(
                    str(row.get("status_code") or "TRADE"), row.get("volume"), row.get("amount")
                )
                conn.execute(text(
                    "INSERT INTO stock_bars_daily(instrument_id,symbol,market_code,date,open,high,low,close,pre_close,adj_close,volume,amount,daily_return,trading_status,is_special_treatment,data_adjustment,data_source,source_payload_hash,observed_at,available_at) "
                    "VALUES (:id,:symbol,'CN_A',:date,:open,:high,:low,:close,:pre,:close,:volume,:amount,:ret,:status,:st,'raw','baostock',:hash,:observed,:available) "
                    "ON DUPLICATE KEY UPDATE symbol=VALUES(symbol),open=VALUES(open),high=VALUES(high),low=VALUES(low),close=VALUES(close),pre_close=VALUES(pre_close),adj_close=VALUES(adj_close),volume=VALUES(volume),amount=VALUES(amount),daily_return=VALUES(daily_return),trading_status=VALUES(trading_status),is_special_treatment=VALUES(is_special_treatment),source_payload_hash=VALUES(source_payload_hash),observed_at=VALUES(observed_at),available_at=VALUES(available_at)"
                ), {"id": ids[symbol], "symbol": symbol, "date": row["business_date"], "open": row["open_price"], "high": row["high_price"], "low": row["low_price"], "close": close, "pre": pre, "volume": row.get("volume"), "amount": row.get("amount"), "ret": daily_return, "status": status, "st": "ST" in status, "hash": row["payload_hash"], "observed": _pit_close(row["business_date"]), "available": _pit_close(row["business_date"])})
                conn.execute(text(
                    "INSERT INTO instrument_status_history(instrument_id,valid_from,valid_to,listing_status,trading_status,is_tradable,is_special_treatment,board_code,source,observed_at,available_at) "
                    "VALUES (:id,:date,:date,'listed',:status,:tradable,:st,:board,'baostock_daily',:observed,:available) "
                    "ON DUPLICATE KEY UPDATE trading_status=VALUES(trading_status),is_tradable=VALUES(is_tradable),is_special_treatment=VALUES(is_special_treatment),board_code=VALUES(board_code),observed_at=VALUES(observed_at),available_at=VALUES(available_at)"
                ), {"id": ids[symbol], "date": row["business_date"], "status": status, "tradable": status.startswith("TRADE"), "st": "ST" in status, "board": "INDEX" if symbol in INDEX_SYMBOLS else parse_baostock_symbol(symbol).board_code, "observed": _pit_close(row["business_date"]), "available": _pit_close(row["business_date"])})
                report.bars += 1
                report.statuses += 1
            report.missing_equity_bars = sorted(set(symbols) - seen_bar_symbols)
            for row in factors:
                symbol = str(row.get("provider_symbol") or "").lower()
                factor = row.get("adjustment_factor")
                if symbol not in ids or factor is None or Decimal(str(factor)) <= 0 or row.get("business_date") is None:
                    report.rejected_rows += 1
                    continue
                conn.execute(text(
                    "INSERT INTO instrument_adjustment_factors(instrument_id,effective_date,provider,adjustment_factor,source_payload_hash,observed_at,available_at) "
                    "VALUES (:id,:date,'baostock',:factor,:hash,:observed,:available) "
                    "ON DUPLICATE KEY UPDATE adjustment_factor=VALUES(adjustment_factor),source_payload_hash=VALUES(source_payload_hash),observed_at=VALUES(observed_at),available_at=VALUES(available_at)"
                ), {"id": ids[symbol], "date": row["business_date"], "factor": factor, "hash": row["payload_hash"], "observed": _pit_close(row["business_date"]), "available": _pit_close(row["business_date"])})
                report.factors += 1
        report.board_counts = dict(Counter(parse_baostock_symbol(symbol).board_code for symbol in symbols))
        report.status = "PASS" if not report.missing_equity_bars and report.rejected_rows == 0 else "PASS_WITH_WARNINGS"
    except Exception:
        report.status = "FAILED"
        raise
    finally:
        with engine.begin() as conn:
            conn.execute(text(
                "UPDATE cn_canonicalization_runs SET status=:status,promoted_instruments=:instruments,promoted_sessions=:sessions,promoted_bars=:bars,promoted_factors=:factors,rejected_rows=:rejected,details_json=:details,finished_at=:finished WHERE canonicalization_run_id=:run"
            ), {"status": report.status, "instruments": report.instruments, "sessions": report.sessions, "bars": report.bars, "factors": report.factors, "rejected": report.rejected_rows, "details": json.dumps(asdict(report), default=str, ensure_ascii=False), "finished": datetime.now(UTC).replace(tzinfo=None), "run": run_id})
    return report


def audit_pilot(engine: Engine, *, manifest_path: Path) -> dict[str, Any]:
    symbols = read_pilot_manifest(manifest_path)
    with engine.connect() as conn:
        counts = {name: int(conn.execute(text(f"SELECT COUNT(*) FROM `{name}`")).scalar() or 0) for name in ("instruments", "instrument_provider_symbols", "market_sessions", "stock_bars_daily", "instrument_adjustment_factors", "instrument_status_history")}
        invalid_ohlc = int(conn.execute(text("SELECT COUNT(*) FROM stock_bars_daily WHERE high<low OR high<open OR high<close OR low>open OR low>close OR volume<0 OR amount<0")).scalar() or 0)
        duplicate_bars = int(conn.execute(text("SELECT COUNT(*) FROM (SELECT instrument_id,date,COUNT(*) c FROM stock_bars_daily GROUP BY instrument_id,date HAVING c>1) x")).scalar() or 0)
        pit_timestamp_errors = int(conn.execute(text("SELECT COUNT(*) FROM stock_bars_daily WHERE DATE(available_at)<>date OR HOUR(available_at)<>7 OR MINUTE(available_at)<>0 OR SECOND(available_at)<>0" )).scalar() or 0)
        bars_without_open_session = int(conn.execute(text("SELECT COUNT(*) FROM stock_bars_daily b LEFT JOIN market_sessions s ON s.market_code=b.market_code AND s.session_date=b.date WHERE s.session_date IS NULL OR s.session_status<>'open'" )).scalar() or 0)
        missing = [str(row[0]) for row in conn.execute(text(
            "SELECT ips.provider_symbol FROM instrument_provider_symbols ips LEFT JOIN stock_bars_daily b ON b.instrument_id=ips.instrument_id WHERE ips.provider='baostock' AND ips.provider_symbol NOT LIKE 'sh.000001' AND ips.provider_symbol NOT LIKE 'sh.000300' AND ips.provider_symbol NOT LIKE 'sz.399001' AND ips.provider_symbol NOT LIKE 'sz.399006' GROUP BY ips.provider_symbol HAVING COUNT(b.date)=0 ORDER BY ips.provider_symbol"
        ))]
        wrong_database = str(conn.execute(text("SELECT DATABASE()" )).scalar()) != "alpha_trade_cn"
    status = "PASS" if not wrong_database and invalid_ohlc == 0 and duplicate_bars == 0 and pit_timestamp_errors == 0 and bars_without_open_session == 0 and not missing and counts["instruments"] >= len(symbols) + 4 else "FAIL"
    return {"status": status, "database": "alpha_trade_cn", "manifest_equities": len(symbols), "counts": counts, "invalid_ohlc": invalid_ohlc, "duplicate_bars": duplicate_bars, "pit_timestamp_errors": pit_timestamp_errors, "bars_without_open_session": bars_without_open_session, "missing_equity_bars": missing, "wrong_database": wrong_database}


__all__ = ["CanonicalizationReport", "INDEX_SYMBOLS", "PILOT_QUOTAS", "audit_pilot", "promote_pilot", "read_pilot_manifest", "select_pilot_symbols", "write_pilot_manifest"]

