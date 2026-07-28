"""service/sec/clientEdgar.py — SEC EDGAR Company Facts API client.

Fetches historical XBRL financial data from the SEC EDGAR API (free, unlimited).
Uses the /xbrl/companyfacts endpoint which returns ALL historical filings
for a given CIK in a single JSON response.

Key design decisions (PIT safety):
- ``trade_date`` = ``filed`` date (when the report was actually submitted to SEC)
- NOT ``end`` date (quarter end) — this eliminates look-ahead bias
- Amendments (10-K/A) are tracked: first filing sets the initial PIT date,
  subsequent amendments update the data at their filing date

API constraints:
- User-Agent header REQUIRED (SEC blocks requests without it) — format:
  ``CompanyName/Version (contact@domain.com)``
- Rate limit: 10 requests/second (SEC fair access policy)
- Free, no API key required
"""
from __future__ import annotations

import json
import logging
import time
from datetime import date as _date, datetime as _dt
from pathlib import Path
from typing import Any

import requests

LOGGER = logging.getLogger(__name__)

# ── Constants ──
_SEC_USER_AGENT = "AlphaTradeML/1.0 (alphatrade@example.com)"
_SEC_BASE_URL = "https://data.sec.gov/api/xbrl/companyfacts"
_SEC_CIK_MAPPING_URL = "https://www.sec.gov/files/company_tickers.json"
_SEC_CIK_CACHE_DIR = Path("artifacts/sec_cache")
_SEC_CIK_CACHE_FILE = _SEC_CIK_CACHE_DIR / "company_tickers.json"
_MIN_REQUEST_INTERVAL_S = 0.12  # ~8 req/s, well under 10/s limit

_LAST_REQUEST_TS: float = 0.0
_CIK_MAPPING: dict[str, str] | None = None  # ticker → CIK (10-digit padded)


class EdgarError(RuntimeError):
    """Base error for SEC EDGAR API issues."""


class EdgarSymbolNotFound(EdgarError):
    """Ticker not found in SEC CIK mapping."""


# ── Rate limiting ──

def _rate_limit() -> None:
    global _LAST_REQUEST_TS
    elapsed = time.monotonic() - _LAST_REQUEST_TS
    if elapsed < _MIN_REQUEST_INTERVAL_S:
        time.sleep(_MIN_REQUEST_INTERVAL_S - elapsed)
    _LAST_REQUEST_TS = time.monotonic()


# ── CIK mapping ──

def _load_cik_mapping(force_refresh: bool = False) -> dict[str, str]:
    """Load ticker→CIK mapping from SEC, cached to disk.

    Returns:
        dict: ticker (upper) → CIK (10-digit zero-padded string)
    """
    global _CIK_MAPPING
    if _CIK_MAPPING is not None and not force_refresh:
        return _CIK_MAPPING

    # Try cache first
    _SEC_CIK_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if _SEC_CIK_CACHE_FILE.exists() and not force_refresh:
        cache_age = time.time() - _SEC_CIK_CACHE_FILE.stat().st_mtime
        if cache_age < 86400:  # 24h cache
            try:
                raw = json.loads(_SEC_CIK_CACHE_FILE.read_text(encoding="utf-8"))
                _CIK_MAPPING = {
                    str(v["ticker"]).upper(): str(v["cik_str"]).zfill(10)
                    for v in raw.values()
                }
                LOGGER.info("CIK mapping loaded from cache: %d tickers", len(_CIK_MAPPING))
                return _CIK_MAPPING
            except (json.JSONDecodeError, KeyError):
                LOGGER.warning("CIK cache corrupted, re-fetching")
                pass

    # Fetch from SEC
    LOGGER.info("Fetching CIK mapping from SEC...")
    _rate_limit()
    try:
        resp = requests.get(
            _SEC_CIK_MAPPING_URL,
            headers={"User-Agent": _SEC_USER_AGENT},
            timeout=30,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise EdgarError(f"Failed to fetch CIK mapping: {exc}") from exc

    data = resp.json()
    _SEC_CIK_CACHE_FILE.write_text(json.dumps(data), encoding="utf-8")

    _CIK_MAPPING = {
        str(v["ticker"]).upper(): str(v["cik_str"]).zfill(10)
        for v in data.values()
    }
    LOGGER.info("CIK mapping loaded: %d tickers", len(_CIK_MAPPING))
    return _CIK_MAPPING


def ticker_to_cik(ticker: str) -> str:
    """Convert a stock ticker to its 10-digit zero-padded CIK.

    Raises:
        EdgarSymbolNotFound: if ticker not found in SEC mapping.
    """
    mapping = _load_cik_mapping()
    cik = mapping.get(ticker.upper())
    if not cik:
        raise EdgarSymbolNotFound(f"Ticker '{ticker}' not found in SEC CIK mapping")
    return cik


# ── Company Facts API ──

def fetch_company_facts(cik: str) -> dict[str, Any]:
    """Fetch the complete XBRL company facts JSON from SEC EDGAR.

    Args:
        cik: 10-digit zero-padded CIK string (e.g., '0000320193' for AAPL).

    Returns:
        Parsed JSON dict with keys: ``cik``, ``entityName``, ``facts``.
        ``facts['us-gaap']`` contains all US-GAAP tagged financial data.

    Raises:
        EdgarError: on network/API errors.
    """
    url = f"{_SEC_BASE_URL}/CIK{cik}.json"
    _rate_limit()
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": _SEC_USER_AGENT},
            timeout=60,
        )
        if resp.status_code == 404:
            raise EdgarSymbolNotFound(f"CIK {cik} not found in SEC EDGAR")
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise EdgarError(f"SEC API request failed for CIK {cik}: {exc}") from exc

    try:
        return resp.json()
    except ValueError as exc:
        raise EdgarError(f"Invalid JSON response for CIK {cik}") from exc


def fetch_symbol_fundamentals_record(
    symbol: str,
    session: Any = None,  # unused, kept for interface compatibility
) -> dict[str, Any]:
    """Fetch raw SEC EDGAR fundamentals for a symbol.

    Returns a dict with the raw company facts JSON (to be processed
    by xbrl_mapper.py for tag extraction and ratio calculation).

    Returns:
        dict with keys: ``symbol``, ``cik``, ``entity_name``,
        ``raw_facts`` (the full us-gaap facts dict), ``source`` = 'SEC_EDGAR'.
    """
    normalized = str(symbol).strip().upper()
    cik = ticker_to_cik(normalized)
    data = fetch_company_facts(cik)

    facts = data.get("facts", {})
    us_gaap = facts.get("us-gaap", {})

    return {
        "symbol": normalized,
        "cik": cik,
        "entity_name": data.get("entityName", ""),
        "raw_facts": us_gaap,
        "source": "SEC_EDGAR",
    }
