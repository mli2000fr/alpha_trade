"""Canonical market scope attached to parent runs and artifact manifests."""
from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from common.config_loader import resolve_market_context

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RunMarketScope:
    market_code: str
    calendar_id: str
    base_currency: str
    benchmark_symbol: str
    sector_taxonomy: str
    market_context_fingerprint: str

    def as_manifest(self) -> dict[str, str]:
        return {
            "market_code": self.market_code,
            "calendar_id": self.calendar_id,
            "base_currency": self.base_currency,
            "benchmark_symbol": self.benchmark_symbol,
            "sector_taxonomy": self.sector_taxonomy,
            "market_context_fingerprint": self.market_context_fingerprint,
        }


def resolve_run_market_scope(
    market_code: str | None = None,
    *,
    require_enabled: bool = False,
) -> RunMarketScope:
    context = resolve_market_context(market_code, require_enabled=require_enabled)
    return RunMarketScope(
        market_code=context.market_code.value,
        calendar_id=context.calendar_id,
        base_currency=context.currency,
        benchmark_symbol=context.benchmark_instrument,
        sector_taxonomy=context.sector_taxonomy,
        market_context_fingerprint=context.fingerprint,
    )


def compute_scope_universe_fingerprint(
    *,
    market_code: str,
    symbol_source: str,
    universe_date: Any = None,
    symbols: Iterable[str] | None = None,
) -> str:
    payload = {
        "market_code": str(market_code).strip().upper(),
        "symbol_source": str(symbol_source or "").strip(),
        "universe_date": str(universe_date or ""),
        "symbols": sorted({str(value).strip().upper() for value in symbols or () if str(value).strip()}),
    }
    encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def read_manifest_market_scope(payload: dict[str, Any]) -> RunMarketScope:
    nested = payload.get("market_context")
    if isinstance(nested, dict) and nested.get("market_code"):
        return RunMarketScope(
            market_code=str(nested["market_code"]),
            calendar_id=str(nested["calendar_id"]),
            base_currency=str(nested["base_currency"]),
            benchmark_symbol=str(nested["benchmark_symbol"]),
            sector_taxonomy=str(nested["sector_taxonomy"]),
            market_context_fingerprint=str(nested["market_context_fingerprint"]),
        )
    LOGGER.warning("Manifest legacy sans market_context: lecture contrôlée en US_EQ")
    return resolve_run_market_scope(None)


__all__ = [
    "RunMarketScope",
    "compute_scope_universe_fingerprint",
    "read_manifest_market_scope",
    "resolve_run_market_scope",
]
