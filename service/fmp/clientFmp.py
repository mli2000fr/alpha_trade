"""service/fmp/clientFmp.py — Financial Modeling Prep API client.

FMP free tier provides:
- ``/api/v3/profile/{symbol}`` — company profile, sector, market cap, beta
- ``/api/v3/key-metrics/{symbol}?limit=1`` — ROE, ROA, PE, debt/equity, etc.

Rate limit: 250 requests/day (free tier).
"""
from __future__ import annotations

import logging
import time
from typing import Any

import requests

LOGGER = logging.getLogger(__name__)

_FMP_BASE_URL = "https://financialmodelingprep.com/api/v3"

# Shared session (connection pooling)
_SESSION: requests.Session | None = None
_LAST_REQUEST_TS: float = 0.0
_MIN_INTERVAL_S = 0.30  # ~200 req/min max, stay well under free tier limit


class FmpError(RuntimeError):
    """Base error for FMP API issues."""


class FmpRateLimitError(FmpError):
    """FMP rate limit exceeded (HTTP 429)."""


class FmpSymbolNotFound(FmpError):
    """Symbol not found in FMP (empty response)."""


def _get_session() -> requests.Session:
    global _SESSION
    if _SESSION is None:
        _SESSION = requests.Session()
        _SESSION.headers.update({
            "Accept": "application/json",
            "User-Agent": "AlphaTrade/1.0",
        })
    return _SESSION


def _rate_limit() -> None:
    """Enforce minimum interval between requests."""
    global _LAST_REQUEST_TS
    elapsed = time.monotonic() - _LAST_REQUEST_TS
    if elapsed < _MIN_INTERVAL_S:
        time.sleep(_MIN_INTERVAL_S - elapsed)
    _LAST_REQUEST_TS = time.monotonic()


def _get_api_key() -> str:
    """Read FMP API key from FMP_TOKEN environment variable."""
    import os
    _key = os.getenv("FMP_TOKEN", "").strip()
    if not _key:
        raise FmpError("FMP_TOKEN environment variable required")
    return _key


def _do_get(endpoint: str, params: dict[str, Any] | None = None) -> Any:
    """Execute a GET request to the FMP API."""
    _rate_limit()
    _params = {"apikey": _get_api_key()}
    if params:
        _params.update(params)
    url = f"{_FMP_BASE_URL}/{endpoint.lstrip('/')}"
    session = _get_session()

    try:
        resp = session.get(url, params=_params, timeout=30)
    except requests.RequestException as exc:
        raise FmpError(f"FMP request failed: {exc}") from exc

    if resp.status_code == 429:
        raise FmpRateLimitError("FMP rate limit exceeded (429)")
    if resp.status_code in (401, 403):
        raise FmpError(f"FMP authentication failed ({resp.status_code})")
    if resp.status_code != 200:
        raise FmpError(f"FMP HTTP {resp.status_code}: {resp.text[:200]}")

    try:
        return resp.json()
    except ValueError as exc:
        raise FmpError(f"FMP invalid JSON response") from exc


def fetch_profile(symbol: str) -> dict[str, Any] | None:
    """Fetch company profile from FMP.

    Returns:
        dict with keys: symbol, price, beta, marketCap, sector, industry,
        exchange, companyName, mktCap, range, changes, volAvg, etc.
        None if symbol not found.
    """
    try:
        data = _do_get(f"profile/{symbol.upper()}")
    except FmpError:
        LOGGER.warning("FMP profile fetch failed for %s", symbol)
        return None

    if not isinstance(data, list) or len(data) == 0:
        LOGGER.info("FMP: no profile data for %s", symbol)
        return None
    return data[0]


def fetch_key_metrics(symbol: str) -> dict[str, Any] | None:
    """Fetch latest key metrics TTM from FMP.

    Returns:
        dict with keys: roe, roa, peRatio, pbRatio, debtToEquity,
        currentRatio, netProfitMargin, revenueGrowth, earningsGrowth,
        dividendYield, marketCap, enterpriseValue, etc.
        None if not available.
    """
    try:
        data = _do_get(f"key-metrics/{symbol.upper()}", {"limit": "1"})
    except FmpError:
        LOGGER.warning("FMP key-metrics fetch failed for %s", symbol)
        return None

    if not isinstance(data, list) or len(data) == 0:
        LOGGER.info("FMP: no key metrics for %s", symbol)
        return None
    return data[0]


def fetch_symbol_fundamentals_record(
    symbol: str,
    session: Any = None,  # unused, kept for interface compatibility
) -> dict[str, Any]:
    """Retourne un enregistrement normalisé contenant les fondamentaux FMP.

    Returns:
        dict with keys: symbol, sector, market_cap, source,
        + all normalized financial ratios ready for stock_fundamentals_daily.
    """
    normalized_symbol = str(symbol).strip().upper()
    if not normalized_symbol:
        raise ValueError("symbol ne peut pas être vide.")

    profile = fetch_profile(normalized_symbol)
    metrics = fetch_key_metrics(normalized_symbol)

    _sf = lambda v: float(v) if v not in (None, "", 0) else None

    # ── Extract from profile ──
    sector = None
    market_cap = None
    beta = None
    if profile:
        sector = profile.get("sector") or profile.get("industry")
        market_cap = _sf(profile.get("mktCap"))
        beta = _sf(profile.get("beta"))

    # ── Extract from key metrics ──
    record: dict[str, Any] = {
        "symbol": normalized_symbol,
        "sector": str(sector).strip() if sector else None,
        "market_cap": market_cap,
        "source": "FMP",
        "raw_profile": profile,
        # Valuation
        "pe_ratio": _sf((metrics or {}).get("peRatio")),
        "pb_ratio": _sf((metrics or {}).get("pbRatio")),
        "ps_ratio": _sf((metrics or {}).get("priceToSalesRatio")),
        "ev_to_ebitda": _sf((metrics or {}).get("enterpriseValueOverEBITDA")),
        "peg_ratio": None,  # FMP free tier doesn't provide PEG
        "forward_pe": None,  # FMP free tier doesn't provide forward PE
        # Profitability
        "roe": _sf((metrics or {}).get("roe")),
        "roa": _sf((metrics or {}).get("returnOnTangibleAssets")),
        "net_margin": _sf((metrics or {}).get("netProfitMargin")),
        "operating_margin": _sf((metrics or {}).get("operatingProfitMargin")),
        "gross_margin": _sf((metrics or {}).get("grossProfitMargin")),
        # Growth
        "eps_growth_yoy": _sf((metrics or {}).get("earningsGrowth")),
        "revenue_growth_yoy": _sf((metrics or {}).get("revenueGrowth")),
        # Health
        "debt_to_equity": _sf((metrics or {}).get("debtToEquity")),
        "current_ratio": _sf((metrics or {}).get("currentRatio")),
        # Yield
        "dividend_yield": _sf((metrics or {}).get("dividendYield")),
        # Market
        "beta": beta,
        "eps": _sf((metrics or {}).get("netIncomePerShare")),
        "book_value_per_share": _sf((metrics or {}).get("bookValuePerShare")),
        "ebitda": _sf((metrics or {}).get("enterpriseValue")) / (_sf((metrics or {}).get("enterpriseValueOverEBITDA")) or 1) if _sf((metrics or {}).get("enterpriseValue")) and _sf((metrics or {}).get("enterpriseValueOverEBITDA")) else None,
        # Estimates (FMP free tier doesn't provide these)
        "eps_estimate_current": None,
        "eps_estimate_next": None,
    }

    return record


__all__ = [
    "FmpError",
    "FmpRateLimitError",
    "FmpSymbolNotFound",
    "fetch_profile",
    "fetch_key_metrics",
    "fetch_symbol_fundamentals_record",
]
