"""Phase C / S16.1 — Génération + signature HMAC d'un rapport mensuel.

Conçu pour être agnostique de la source de données : on fournit
``MonthlyReportInputs`` agrégé en amont (depuis ``broker_statements``,
``lots``, ``fills``, ``corporate_action_runs``), et on obtient un
``MonthlyReport`` JSON-sérialisable + signature HMAC-SHA256.

L'agrégation SQL est laissée à ``scripts/run_monthly_broker_report.py``
qui consomme le ``database/`` existant.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import asdict, dataclass, field
from datetime import date

from reporting.json_schema import SCHEMA_VERSION


@dataclass(frozen=True, slots=True)
class FillRow:
    fill_id: str
    symbol: str
    qty: float
    price: float
    expected_price: float
    fees: float = 0.0


@dataclass(frozen=True, slots=True)
class CashEvent:
    event_id: str
    symbol: str
    kind: str  # "dividend" | "withholding" | "fee" | "interest"
    amount: float


@dataclass(frozen=True, slots=True)
class MonthlyReportInputs:
    account_id: str
    period_start: date
    period_end: date
    fills: list[FillRow] = field(default_factory=list)
    cash_events: list[CashEvent] = field(default_factory=list)
    realized_pnl: float = 0.0  # calculé en amont (FIFO lots)
    trades_count: int = 0


@dataclass(frozen=True, slots=True)
class MonthlyReport:
    schema_version: str
    account_id: str
    period_start: str
    period_end: str
    realized_pnl: float
    dividends: float
    withholding_tax: float
    fees: float
    average_slippage_bps: float
    fills_count: int
    trades_count: int
    signature: dict

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)


def _slippage_bps(fill: FillRow) -> float:
    if fill.expected_price <= 0:
        return 0.0
    return ((fill.price - fill.expected_price) / fill.expected_price) * 10_000.0


def _canonical_payload(d: dict) -> bytes:
    """Représentation canonique pour signature (sans champ signature)."""
    payload = {k: v for k, v in d.items() if k != "signature"}
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_report(report: dict, secret: bytes) -> dict:
    """Retourne le dict de signature ``{algorithm, value}``."""
    sig = hmac.new(secret, _canonical_payload(report), hashlib.sha256).hexdigest()
    return {"algorithm": "HMAC-SHA256", "value": sig}


def verify_signature(report_dict: dict, secret: bytes) -> bool:
    sig = report_dict.get("signature") or {}
    if sig.get("algorithm") != "HMAC-SHA256":
        return False
    expected = hmac.new(
        secret, _canonical_payload(report_dict), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, sig.get("value", ""))


def build_monthly_report(
    inputs: MonthlyReportInputs,
    *,
    secret: bytes,
) -> MonthlyReport:
    """Agrège les inputs et retourne un ``MonthlyReport`` signé."""
    fills = inputs.fills
    cash = inputs.cash_events

    dividends = sum(c.amount for c in cash if c.kind == "dividend")
    withholding_tax = sum(c.amount for c in cash if c.kind == "withholding")
    cash_fees = sum(c.amount for c in cash if c.kind == "fee")
    fill_fees = sum(f.fees for f in fills)
    fees = cash_fees + fill_fees

    if fills:
        slippage = sum(_slippage_bps(f) for f in fills) / len(fills)
    else:
        slippage = 0.0

    payload = {
        "schema_version": SCHEMA_VERSION,
        "account_id": inputs.account_id,
        "period_start": inputs.period_start.isoformat(),
        "period_end": inputs.period_end.isoformat(),
        "realized_pnl": round(inputs.realized_pnl, 6),
        "dividends": round(dividends, 6),
        "withholding_tax": round(withholding_tax, 6),
        "fees": round(fees, 6),
        "average_slippage_bps": round(slippage, 6),
        "fills_count": len(fills),
        "trades_count": int(inputs.trades_count),
    }
    payload["signature"] = sign_report(payload, secret)
    return MonthlyReport(**payload)

