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


