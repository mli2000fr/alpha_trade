from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any, Optional, cast

LOGGER = logging.getLogger(__name__)

_YFINANCE_MODULE: Any | None = None


def _normalize_symbol(symbol: str) -> str:
    normalized = (symbol or "").strip().upper()
    if not normalized:
        raise ValueError("symbol ne peut pas être vide.")
    return normalized


def _import_yfinance() -> Any:
    global _YFINANCE_MODULE
    if _YFINANCE_MODULE is not None:
        return _YFINANCE_MODULE
    try:
        import yfinance  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "yfinance n'est pas installé. Installer via `pip install yfinance>=0.2` "
            "ou en réinstallant les dépendances runtime du projet."
        ) from exc
    _YFINANCE_MODULE = yfinance
    return _YFINANCE_MODULE


def _coerce_mapping(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    items = getattr(value, "items", None)
    if callable(items):
        try:
            pairs = cast(Iterable[tuple[object, Any]], items())
            return {str(key): item for key, item in pairs}
        except Exception:
            return {}
    try:
        return cast(dict[str, Any], dict(cast(Any, value)))
    except Exception:
        return {}


def _normalize_text(value: Any) -> str | None:
    normalized = str(value or "").strip()
    if not normalized or normalized.upper() == "N/A":
        return None
    return normalized


def _normalize_market_cap(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        market_cap = float(value)
    except (TypeError, ValueError):
        return None
    if market_cap <= 0:
        return None
    return market_cap


def fetch_symbol_fundamentals_record(symbol: str, session: Optional[object] = None) -> dict[str, Any]:
    """Retourne un enregistrement normalisé contenant le secteur et la market cap Yahoo Finance."""
    del session  # conservé pour homogénéité d'interface avec les autres providers

    normalized_symbol = _normalize_symbol(symbol)
    yf = _import_yfinance()
    ticker = yf.Ticker(normalized_symbol)
    info = _coerce_mapping(getattr(ticker, "info", None))
    fast_info = _coerce_mapping(getattr(ticker, "fast_info", None))

    sector = _normalize_text(info.get("sector") or info.get("sectorDisp") or info.get("category"))
    market_cap = _normalize_market_cap(
        info.get("marketCap")
        or info.get("market_cap")
        or fast_info.get("marketCap")
        or fast_info.get("market_cap")
    )

    LOGGER.info(
        "Yahoo Finance fundamentals | symbol=%s sector=%s market_cap=%s",
        normalized_symbol,
        sector,
        market_cap,
    )
    return {
        "symbol": normalized_symbol,
        "sector": sector,
        "market_cap": market_cap,
        "source": "Yahoo Finance",
        "raw_profile": info,
        "raw_fast_info": fast_info,
    }


def fetch_latest_quotes_yahoo(
    symbols: list[str],
    *,
    session: Any = None,
    account_id: str | None = None,
    max_workers: int = 8,
    per_symbol_timeout: float = 5.0,
) -> dict[str, dict[str, Any]]:
    """Récupère les dernières quotes (bid/ask) depuis Yahoo Finance.

    Contrairement à Alpaca, Yahoo Finance ne propose pas d'endpoint batch :
    chaque symbole nécessite un appel individuel à ``Ticker.info``. Pour
    limiter la latence, les appels sont parallélisés via ``ThreadPoolExecutor``.

    Returns
    -------
    dict[symbol, quote]
        Même contrat que :func:`~service.alpaca.clientAlpaca.fetch_latest_quotes` :
        chaque quote est un dict avec les clés ``bp``, ``ap``, ``bs``, ``as``, ``t``.
        Les symboles sans quote (erreur réseau, ticker invalide, ni bid ni ask)
        sont absents du dict retourné.
    """
    del session, account_id  # homogénéité d'interface

    if not symbols:
        return {}

    from concurrent.futures import ThreadPoolExecutor, as_completed
    from datetime import datetime, timezone

    yf = _import_yfinance()
    results: dict[str, dict[str, Any]] = {}
    now_iso = datetime.now(timezone.utc).isoformat()

    def _fetch_one(symbol: str) -> tuple[str, dict[str, Any] | None]:
        try:
            ticker = yf.Ticker(symbol)
            info = _coerce_mapping(getattr(ticker, "info", None))
            bid = info.get("bid")
            ask = info.get("ask")
            # Si ni bid ni ask, on ignore ce symbole
            if bid is None and ask is None:
                return symbol, None
            return symbol, {
                "bp": float(bid) if bid is not None else None,
                "ap": float(ask) if ask is not None else None,
                "bs": (
                    float(info["bidSize"]) * 100.0
                    if info.get("bidSize") is not None
                    else None
                ),
                "as": (
                    float(info["askSize"]) * 100.0
                    if info.get("askSize") is not None
                    else None
                ),
                "t": now_iso,
            }
        except Exception:
            LOGGER.debug(
                "Yahoo Finance quote indisponible pour %s", symbol, exc_info=True
            )
            return symbol, None

    workers = min(max_workers, len(symbols))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_map = {
            executor.submit(_fetch_one, s): s
            for s in symbols
        }
        for future in as_completed(future_map):
            symbol, quote = future.result()
            if quote is not None:
                results[symbol] = quote

    LOGGER.info(
        "Yahoo Finance latest quotes | requested=%s resolved=%s",
        len(symbols),
        len(results),
    )
    return results
