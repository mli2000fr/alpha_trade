from __future__ import annotations

import re
from dataclasses import dataclass

SYMBOL_RE = re.compile(r"^(?P<code>\d{6})\.(?P<exchange>SH|SZ|BJ)$")


@dataclass(frozen=True, slots=True)
class TushareSymbol:
    provider_symbol: str
    local_symbol: str
    exchange_code: str
    market_code: str
    board_code: str


def _board(code: str, exchange: str) -> str:
    if exchange == "BJ":
        return "BSE"
    if exchange == "SH" and code.startswith("688"):
        return "STAR"
    if exchange == "SZ" and code.startswith(("300", "301")):
        return "CHINEXT"
    if exchange == "SH":
        return "SH_MAIN"
    return "SZ_MAIN"


def parse_tushare_symbol(value: str) -> TushareSymbol:
    normalized = str(value or "").strip().upper()
    match = SYMBOL_RE.fullmatch(normalized)
    if not match:
        raise ValueError(f"Symbole Tushare invalide : {value!r}")
    code = match.group("code")
    exchange = match.group("exchange")
    return TushareSymbol(
        provider_symbol=normalized,
        local_symbol=code,
        exchange_code=exchange,
        market_code="CN_BJ" if exchange == "BJ" else "CN_A",
        board_code=_board(code, exchange),
    )


__all__ = ["TushareSymbol", "parse_tushare_symbol"]
