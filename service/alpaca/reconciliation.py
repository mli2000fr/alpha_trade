"""Sprint S12.3 — Réconciliation broker statements ↔ fills internes.

Pipeline :

1. ``persist_statements`` : upsert idempotent (par ``activity_id``) des
   activities Alpaca dans ``broker_statements``.
2. ``reconcile`` : compare ``broker_statements`` (FILL/PFILL) vs
   ``execution_fills`` sur la fenêtre temporelle demandée et retourne la
   liste des divergences.
"""
from __future__ import annotations

import csv
import io
import json
import logging
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable, Mapping

from sqlalchemy import text
from sqlalchemy.engine import Engine

LOGGER = logging.getLogger(__name__)

_CSV_ALIASES: dict[str, tuple[str, ...]] = {
    "activity_id": ("activity_id", "id", "activity id", "activityid"),
    "activity_type": ("activity_type", "type", "activity type", "activitytype"),
    "symbol": ("symbol", "ticker"),
    "side": ("side", "transaction side"),
    "qty": ("qty", "quantity", "filled_qty", "filled quantity"),
    "price": ("price", "net_price", "filled_avg_price", "avg_fill_price", "average price"),
    "transaction_time": (
        "transaction_time",
        "transaction time",
        "filled_at",
        "fill_time",
        "timestamp",
        "date",
    ),
}

DIFF_TYPE_MISSING_INTERNAL = "missing_internal"
DIFF_TYPE_MISSING_BROKER = "missing_broker"
DIFF_TYPE_QTY_MISMATCH = "qty_mismatch"
DIFF_TYPE_PRICE_MISMATCH = "price_mismatch"

# Tolérances de réconciliation (configurable plus tard via ExecutionConfig).
QTY_ABS_TOL = Decimal("1e-6")
PRICE_REL_TOL = Decimal("0.001")  # 10 bps


@dataclass(frozen=True, slots=True)
class StatementDiff:
    diff_type: str
    symbol: str
    activity_id: str | None
    broker_qty: float | None
    internal_qty: float | None
    broker_price: float | None
    internal_price: float | None
    transaction_time: str | None
    detail: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _read_csv_text(csv_source: str | Path | io.TextIOBase) -> str:
    if isinstance(csv_source, io.TextIOBase):
        return csv_source.read()
    if isinstance(csv_source, Path):
        return csv_source.read_text(encoding="utf-8-sig")
    candidate = Path(str(csv_source))
    if candidate.exists() and candidate.is_file():
        return candidate.read_text(encoding="utf-8-sig")
    return str(csv_source)


def _normalize_csv_key(value: object) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _pick_csv_value(row: Mapping[str, Any], logical_key: str) -> Any:
    normalized = {_normalize_csv_key(key): value for key, value in row.items()}
    for alias in _CSV_ALIASES.get(logical_key, (logical_key,)):
        value = normalized.get(_normalize_csv_key(alias))
        if value not in (None, ""):
            return value
    return None


def parse_statement_csv(csv_source: str | Path | io.TextIOBase) -> list[dict[str, Any]]:
    """Parse un export CSV Alpaca J+1 vers le format ``persist_statements``.

    Le mapping est volontairement tolérant sur les noms de colonnes pour accepter
    les variantes d'exports opérateur (camelCase, titres lisibles, alias legacy).
    """
    raw_text = _read_csv_text(csv_source)
    if not raw_text.strip():
        return []
    reader = csv.DictReader(io.StringIO(raw_text))
    rows: list[dict[str, Any]] = []
    for raw_row in reader:
        activity_id = _pick_csv_value(raw_row, "activity_id")
        activity_type = _pick_csv_value(raw_row, "activity_type") or "FILL"
        if activity_id in (None, "") and _pick_csv_value(raw_row, "symbol") in (None, ""):
            continue
        rows.append(
            {
                "id": str(activity_id or "").strip(),
                "activity_type": str(activity_type or "FILL").strip().upper(),
                "symbol": _pick_csv_value(raw_row, "symbol"),
                "side": _pick_csv_value(raw_row, "side"),
                "qty": _pick_csv_value(raw_row, "qty"),
                "price": _pick_csv_value(raw_row, "price"),
                "transaction_time": _pick_csv_value(raw_row, "transaction_time"),
            }
        )
    return rows


def build_reconciliation_summary(
    *,
    account_id: str,
    trade_date: date,
    diffs: Iterable[StatementDiff],
    source_kind: str,
    activity_count: int,
    inserted: int,
    fetched_from_api: bool,
    statement_path: str | None = None,
) -> dict[str, Any]:
    diff_rows = [diff.to_dict() for diff in diffs]
    diff_types: dict[str, int] = {}
    symbols: set[str] = set()
    for diff in diff_rows:
        diff_type = str(diff.get("diff_type") or "unknown")
        diff_types[diff_type] = diff_types.get(diff_type, 0) + 1
        symbol = str(diff.get("symbol") or "").strip().upper()
        if symbol:
            symbols.add(symbol)
    return {
        "run_id": f"j1-reconcile-{account_id}-{trade_date.isoformat()}",
        "account_id": account_id,
        "trade_date": trade_date.isoformat(),
        "source_kind": source_kind,
        "statement_path": statement_path,
        "fetched_from_api": bool(fetched_from_api),
        "activity_count": int(activity_count),
        "inserted": int(inserted),
        "diff_count": len(diff_rows),
        "diff_types": diff_types,
        "distinct_symbols": sorted(symbols),
        "status": "SUCCESS" if not diff_rows else "WARNING",
        "diffs": diff_rows,
    }


# ---------------------------------------------------------------------------
# Persistance
# ---------------------------------------------------------------------------


def persist_statements(
    engine: Engine,
    account_id: str,
    activities: Iterable[Mapping[str, Any]],
) -> int:
    """Upsert idempotent des activities. Retourne le nombre inséré."""
    rows = list(activities)
    if not rows:
        return 0
    stmt = text(
        "INSERT INTO broker_statements "
        "(account_id, activity_id, activity_type, symbol, side, qty, price, "
        " transaction_time, raw_json) "
        "VALUES (:account_id, :activity_id, :activity_type, :symbol, :side, "
        "        :qty, :price, :transaction_time, :raw_json)"
    )
    inserted = 0
    with engine.begin() as conn:
        for r in rows:
            try:
                conn.execute(stmt, _normalize(account_id, r))
                inserted += 1
            except Exception as exc:  # noqa: BLE001 — duplicate UNIQUE etc.
                LOGGER.debug("persist_statements skip activity_id=%s err=%s",
                             r.get("id"), exc)
    return inserted


def _normalize(account_id: str, r: Mapping[str, Any]) -> dict[str, Any]:
    tx_time = r.get("transaction_time") or r.get("timestamp")
    if isinstance(tx_time, str):
        try:
            tx_time = datetime.fromisoformat(tx_time.replace("Z", "+00:00"))
        except ValueError:
            tx_time = None
    return {
        "account_id": account_id,
        "activity_id": str(r.get("id") or ""),
        "activity_type": str(r.get("activity_type") or "UNKNOWN"),
        "symbol": (r.get("symbol") or None),
        "side": (r.get("side") or None),
        # Cast en str pour compatibilité SQLite (NUMERIC accepte string).
        "qty": (str(r["qty"]) if r.get("qty") is not None else None),
        "price": (str(r["price"]) if r.get("price") is not None else None),
        "transaction_time": tx_time,
        "raw_json": json.dumps(dict(r), default=str, sort_keys=True),
    }


# ---------------------------------------------------------------------------
# Réconciliation
# ---------------------------------------------------------------------------


def reconcile(
    engine: Engine,
    *,
    account_id: str,
    trade_date: date,
) -> list[StatementDiff]:
    """Compare broker_statements vs execution_fills sur ``trade_date``.

    Best-effort : si l'une des tables manque, log et retourne ``[]``.
    """
    try:
        broker_rows = _load_broker_fills(engine, account_id, trade_date)
        internal_rows = _load_internal_fills(engine, account_id, trade_date)
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("reconcile: source unavailable: %s", exc)
        return []

    broker_idx: dict[tuple[str, str], dict[str, Any]] = {}
    for row in broker_rows:
        key = (row["symbol"] or "", row.get("activity_id") or "")
        broker_idx[key] = row

    internal_idx: dict[str, list[dict[str, Any]]] = {}
    for row in internal_rows:
        internal_idx.setdefault(row["symbol"] or "", []).append(row)

    diffs: list[StatementDiff] = []
    matched_internal: set[int] = set()

    for (symbol, activity_id), b in broker_idx.items():
        candidates = internal_idx.get(symbol, [])
        match = None
        for idx, c in enumerate(candidates):
            if id(c) in matched_internal:
                continue
            if _qty_match(b.get("qty"), c.get("qty")):
                match = (idx, c)
                break
        if match is None:
            diffs.append(_diff_missing_internal(b))
            continue
        _, c = match
        matched_internal.add(id(c))
        if not _qty_match(b.get("qty"), c.get("qty")):
            diffs.append(_diff_qty(b, c))
        if not _price_match(b.get("price"), c.get("price")):
            diffs.append(_diff_price(b, c))

    for symbol, rows in internal_idx.items():
        for c in rows:
            if id(c) not in matched_internal:
                diffs.append(_diff_missing_broker(c))

    return diffs


def _load_broker_fills(engine: Engine, account_id: str, trade_date: date) -> list[dict[str, Any]]:
    stmt = text(
        "SELECT activity_id, symbol, side, qty, price, transaction_time "
        "FROM broker_statements "
        "WHERE account_id = :acct "
        "  AND activity_type IN ('FILL','PFILL') "
        "  AND DATE(transaction_time) = :td"
    )
    with engine.connect() as conn:
        return [dict(r._mapping) for r in conn.execute(stmt, {"acct": account_id, "td": trade_date})]


def _load_internal_fills(engine: Engine, account_id: str, trade_date: date) -> list[dict[str, Any]]:
    # ``execution_fills`` est créée par 0009/0010 ; colonnes ``filled_qty``
    # et ``filled_avg_price`` selon le schema execution Sprint 2.
    stmt = text(
        "SELECT f.symbol, f.side, f.filled_qty AS qty, f.filled_avg_price AS price, "
        "       f.fill_time AS transaction_time "
        "FROM execution_fills f "
        "INNER JOIN execution_runs r ON r.exec_run_id = f.exec_run_id "
        "WHERE r.account_id = :acct AND r.trade_date = :td"
    )
    with engine.connect() as conn:
        return [dict(r._mapping) for r in conn.execute(stmt, {"acct": account_id, "td": trade_date})]


def _qty_match(a: Any, b: Any) -> bool:
    if a is None or b is None:
        return False
    return abs(Decimal(str(a)) - Decimal(str(b))) <= QTY_ABS_TOL


def _price_match(a: Any, b: Any) -> bool:
    if a is None or b is None:
        return False
    da, db = Decimal(str(a)), Decimal(str(b))
    if db == 0:
        return da == 0
    return abs(da - db) / db <= PRICE_REL_TOL


def _diff_missing_internal(b: Mapping[str, Any]) -> StatementDiff:
    return StatementDiff(
        diff_type=DIFF_TYPE_MISSING_INTERNAL,
        symbol=str(b.get("symbol") or ""),
        activity_id=str(b.get("activity_id") or ""),
        broker_qty=_to_float(b.get("qty")),
        internal_qty=None,
        broker_price=_to_float(b.get("price")),
        internal_price=None,
        transaction_time=_iso(b.get("transaction_time")),
        detail="Aucun fill interne ne correspond à cette activity broker.",
    )


def _diff_missing_broker(c: Mapping[str, Any]) -> StatementDiff:
    return StatementDiff(
        diff_type=DIFF_TYPE_MISSING_BROKER,
        symbol=str(c.get("symbol") or ""),
        activity_id=None,
        broker_qty=None,
        internal_qty=_to_float(c.get("qty")),
        broker_price=None,
        internal_price=_to_float(c.get("price")),
        transaction_time=_iso(c.get("transaction_time")),
        detail="Fill interne sans activity broker correspondante.",
    )


def _diff_qty(b: Mapping[str, Any], c: Mapping[str, Any]) -> StatementDiff:
    return StatementDiff(
        diff_type=DIFF_TYPE_QTY_MISMATCH,
        symbol=str(b.get("symbol") or ""),
        activity_id=str(b.get("activity_id") or ""),
        broker_qty=_to_float(b.get("qty")),
        internal_qty=_to_float(c.get("qty")),
        broker_price=_to_float(b.get("price")),
        internal_price=_to_float(c.get("price")),
        transaction_time=_iso(b.get("transaction_time")),
        detail="Quantités divergentes.",
    )


def _diff_price(b: Mapping[str, Any], c: Mapping[str, Any]) -> StatementDiff:
    return StatementDiff(
        diff_type=DIFF_TYPE_PRICE_MISMATCH,
        symbol=str(b.get("symbol") or ""),
        activity_id=str(b.get("activity_id") or ""),
        broker_qty=_to_float(b.get("qty")),
        internal_qty=_to_float(c.get("qty")),
        broker_price=_to_float(b.get("price")),
        internal_price=_to_float(c.get("price")),
        transaction_time=_iso(b.get("transaction_time")),
        detail="Prix divergent (> 10 bps).",
    )


def _to_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _iso(v: Any) -> str | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.replace(tzinfo=v.tzinfo or timezone.utc).isoformat()
    return str(v)


__all__ = [
    "StatementDiff",
    "build_reconciliation_summary",
    "persist_statements",
    "parse_statement_csv",
    "reconcile",
    "DIFF_TYPE_MISSING_INTERNAL",
    "DIFF_TYPE_MISSING_BROKER",
    "DIFF_TYPE_QTY_MISMATCH",
    "DIFF_TYPE_PRICE_MISMATCH",
]


