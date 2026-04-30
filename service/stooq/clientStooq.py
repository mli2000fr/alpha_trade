"""Phase 7.3 — Client Stooq minimal (audit_global §7.3).

Récupère l'OHLCV daily consolidé depuis Stooq (https://stooq.com/q/d/l/) au
format CSV. Aucune dépendance externe : ``urllib`` + ``csv`` standard.

Best-effort : toute exception est convertie en log warning + retour vide pour
ne pas casser le pipeline principal.

Format de retour aligné sur :class:`core.interfaces.MarketDataPort.fetch_bars`
(``list[dict]`` avec clés ``date``, ``open``, ``high``, ``low``, ``close``,
``volume``).
"""
from __future__ import annotations

import csv
import io
import logging
from datetime import date, datetime
from typing import Any
from urllib import error, parse, request

LOGGER = logging.getLogger(__name__)

STOOQ_DAILY_URL = "https://stooq.com/q/d/l/"
DEFAULT_TIMEOUT_SECONDS = 10


def _stooq_symbol(symbol: str) -> str:
    """Stooq utilise un suffixe ``.us`` pour les actions US."""
    s = symbol.lower().strip()
    if "." in s:
        return s
    return f"{s}.us"


def fetch_daily_bars(
    symbol: str,
    *,
    start: date | None = None,
    end: date | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> list[dict[str, Any]]:
    """Récupère les bars OHLCV daily Stooq pour ``symbol``.

    Si Stooq répond 404 / format inattendu, retourne ``[]`` (jamais d'exception
    propagée).
    """
    params = {"s": _stooq_symbol(symbol), "i": "d"}
    if start:
        params["d1"] = start.strftime("%Y%m%d")
    if end:
        params["d2"] = end.strftime("%Y%m%d")
    url = f"{STOOQ_DAILY_URL}?{parse.urlencode(params)}"
    try:
        req = request.Request(url, headers={"User-Agent": "alpha-trade-cross-check/0.1"})
        with request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - URL contrôlée
            raw = resp.read().decode("utf-8", errors="replace")
    except (error.URLError, TimeoutError, OSError) as exc:
        LOGGER.warning("Stooq fetch failed for %s : %s", symbol, exc)
        return []
    return _parse_csv(raw)


def _parse_csv(raw: str) -> list[dict[str, Any]]:
    if not raw or raw.strip().lower().startswith("no data"):
        return []
    bars: list[dict[str, Any]] = []
    reader = csv.DictReader(io.StringIO(raw))
    for row in reader:
        try:
            bars.append(
                {
                    "date": datetime.strptime(row["Date"], "%Y-%m-%d").date(),
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": float(row.get("Volume") or 0.0),
                }
            )
        except (KeyError, ValueError, TypeError):
            # Ligne malformée : ignore silencieusement.
            continue
    return bars


__all__ = ["fetch_daily_bars"]

