from __future__ import annotations

import re
from dataclasses import dataclass

BAOSTOCK_SYMBOL_RE = re.compile(r"^(?P<exchange>sh|sz)\.(?P<code>\d{6})$", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class BaoStockSymbol:
    provider_symbol: str
    local_symbol: str
    exchange_code: str
    market_code: str
    board_code: str


def _board(code: str, exchange: str) -> str:
    if exchange == "SH" and code.startswith("688"):
        return "STAR"
    if exchange == "SZ" and code.startswith(("300", "301")):
        return "CHINEXT"
    return "SH_MAIN" if exchange == "SH" else "SZ_MAIN"


def parse_baostock_symbol(value: str) -> BaoStockSymbol:
    normalized = str(value or "").strip().lower()
    match = BAOSTOCK_SYMBOL_RE.fullmatch(normalized)
    if not match:
        raise ValueError(f"Symbole BaoStock invalide : {value!r}")
    exchange = match.group("exchange").upper()
    code = match.group("code")
    return BaoStockSymbol(
        provider_symbol=normalized,
        local_symbol=code,
        exchange_code=exchange,
        market_code="CN_A",
        board_code=_board(code, exchange),
    )


__all__ = ["BaoStockSymbol", "parse_baostock_symbol"]
