"""service/fmp/clientFmp.py — Financial Modeling Prep API client.

FMP free tier endpoints used:
- ``/api/v3/profile/{symbol}`` — company profile, sector, market cap, beta
- ``/api/v3/ratios-ttm/{symbol}`` — TTM ratios: PE, PB, PS, ROE, ROA, margins
- ``/api/v3/key-metrics-ttm/{symbol}`` — TTM metrics: EV/EBITDA, book value
- ``/api/v3/financial-growth/{symbol}?limit=1`` — YoY growth: EPS, revenue

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

    Returns dict with: symbol, price, beta, mktCap, sector, industry,
    exchange, companyName, etc.  None if symbol not found.
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


def fetch_ratios_ttm(symbol: str) -> dict[str, Any] | None:
    """Fetch TTM ratios from FMP.

    Returns dict with: peRatioTTM, pegRatioTTM, priceToBookRatioTTM,
    priceToSalesRatioTTM, returnOnEquityTTM, returnOnAssetsTTM,
    netProfitMarginTTM, operatingProfitMarginTTM, grossProfitMarginTTM,
    debtEquityRatioTTM, currentRatioTTM, dividendYielPercentageTTM, etc.
    None if not available.
    """
    try:
        data = _do_get(f"ratios-ttm/{symbol.upper()}")
    except FmpError:
        LOGGER.warning("FMP ratios-ttm fetch failed for %s", symbol)
        return None

    if not isinstance(data, list) or len(data) == 0:
        LOGGER.info("FMP: no ratios-ttm for %s", symbol)
        return None
    return data[0]


def fetch_key_metrics_ttm(symbol: str) -> dict[str, Any] | None:
    """Fetch TTM key metrics from FMP.

    Returns dict with: enterpriseValueMultipleTTM, bookValuePerShareTTM,
    peRatioTTM, marketCapTTM, etc.
    None if not available.
    """
    try:
        data = _do_get(f"key-metrics-ttm/{symbol.upper()}")
    except FmpError:
        LOGGER.warning("FMP key-metrics-ttm fetch failed for %s", symbol)
        return None

    if not isinstance(data, list) or len(data) == 0:
        LOGGER.info("FMP: no key-metrics-ttm for %s", symbol)
        return None
    return data[0]


def fetch_financial_growth(symbol: str) -> dict[str, Any] | None:
    """Fetch latest financial growth YoY from FMP.

    Returns dict with: epsgrowth, revenueGrowth, etc.
    None if not available.
    """
    try:
        data = _do_get(f"financial-growth/{symbol.upper()}", {"limit": "1"})
    except FmpError:
        LOGGER.warning("FMP financial-growth fetch failed for %s", symbol)
        return None

    if not isinstance(data, list) or len(data) == 0:
        LOGGER.info("FMP: no financial-growth for %s", symbol)
        return None
    return data[0]


def fetch_symbol_fundamentals_record(
    symbol: str,
    session: Any = None,  # unused, kept for interface compatibility
) -> dict[str, Any]:
    """Retourne un enregistrement normalisé FMP prêt pour stock_fundamentals_daily.

    Utilise 4 endpoints FMP (3 calls ratio + 1 call profile).
    Mapping exact des champs FMP → colonnes MySQL.

    Returns:
        dict with keys: symbol, sector, market_cap, source, pe_ratio,
        forward_pe, peg_ratio, pb_ratio, ps_ratio, ev_to_ebitda, roe, roa,
        net_margin, operating_margin, gross_margin, eps_growth_yoy,
        revenue_growth_yoy, debt_to_equity, current_ratio, dividend_yield,
        beta, eps, book_value_per_share, ebitda, raw_profile.
    """
    normalized_symbol = str(symbol).strip().upper()
    if not normalized_symbol:
        raise ValueError("symbol ne peut pas être vide.")

    _sf = lambda v: float(v) if v not in (None, "", 0) else None

    # ── Fetch all FMP endpoints ──
    profile = fetch_profile(normalized_symbol)
    ratios = fetch_ratios_ttm(normalized_symbol) or {}
    metrics = fetch_key_metrics_ttm(normalized_symbol) or {}
    growth = fetch_financial_growth(normalized_symbol) or {}

    # ── Extract from profile ──
    sector = None
    market_cap = None
    beta = None
    if profile:
        sector = profile.get("sector") or profile.get("industry")
        # FMP profile uses "mktCap" (int or float)
        market_cap = _sf(profile.get("mktCap"))
        beta = _sf(profile.get("beta"))

    # ── Build normalized record ──
    record: dict[str, Any] = {
        "symbol": normalized_symbol,
        "sector": str(sector).strip() if sector else None,
        "market_cap": market_cap or _sf(metrics.get("marketCapTTM")),
        "source": "FMP",
        "raw_profile": profile,
        # Valuation (ratios-ttm)
        "pe_ratio": _sf(ratios.get("peRatioTTM")),
        "forward_pe": _sf(metrics.get("peRatioTTM")),  # approximation
        "peg_ratio": _sf(ratios.get("pegRatioTTM")),
        "pb_ratio": _sf(ratios.get("priceToBookRatioTTM")),
        "ps_ratio": _sf(ratios.get("priceToSalesRatioTTM")),
        "ev_to_ebitda": _sf(metrics.get("enterpriseValueMultipleTTM")),
        # Profitability (ratios-ttm)
        "roe": _sf(ratios.get("returnOnEquityTTM")),
        "roa": _sf(ratios.get("returnOnAssetsTTM")),
        "net_margin": _sf(ratios.get("netProfitMarginTTM")),
        "operating_margin": _sf(ratios.get("operatingProfitMarginTTM")),
        "gross_margin": _sf(ratios.get("grossProfitMarginTTM")),
        # Growth (financial-growth)
        "eps_growth_yoy": _sf(growth.get("epsgrowth")),
        "revenue_growth_yoy": _sf(growth.get("revenueGrowth")),
        # Health (ratios-ttm)
        "debt_to_equity": _sf(ratios.get("debtEquityRatioTTM")),
        "current_ratio": _sf(ratios.get("currentRatioTTM")),
        # Yield (ratios-ttm)
        "dividend_yield": _sf(ratios.get("dividendYielPercentageTTM")),
        # Market
        "beta": beta,
        "eps": _sf(ratios.get("cashPerShareTTM")),
        "book_value_per_share": _sf(metrics.get("bookValuePerShareTTM")),
        "ebitda": None,  # FMP free tier — income-statement-ttm requires paid plan
        # Estimates (FMP free tier — analyst-estimates requires paid plan)
        "eps_estimate_current": None,
        "eps_estimate_next": None,
    }

    return record


__all__ = [
    "FmpError",
    "FmpRateLimitError",
    "FmpSymbolNotFound",
    "fetch_profile",
    "fetch_ratios_ttm",
    "fetch_key_metrics_ttm",
    "fetch_financial_growth",
    "fetch_symbol_fundamentals_record",
]

    "fetch_symbol_fundamentals_record",
]
