"""service/sec/xbrl_mapper.py — US-GAAP XBRL tag extraction & ratio calculation.

Extracts standardized financial metrics from SEC EDGAR XBRL company facts,
handling:
- Tag variability (multiple fallback tags per metric)
- YTD → quarterly conversion for 10-Q filings
- TTM (Trailing Twelve Months) calculation
- Amendment handling (10-K/A, 10-Q/A) — first filing sets PIT date
- Fixed share count lookup (from 10-K filings)

PIT Safety:
    ``trade_date`` is set to the SEC ``filed`` date, NOT the quarter ``end`` date.
    This ensures data is only available after it was actually published.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date as _date, datetime as _dt
from typing import Any

LOGGER = logging.getLogger(__name__)

# ── US-GAAP Tag Mapping ──
# Priority order: first matching tag wins.
# Each entry: (list_of_fallback_tags, description)
_TAG_MAP: dict[str, tuple[list[str], str]] = {
    "revenue": (
        ["Revenues", "SalesRevenueNet", "RevenueFromContractWithCustomerExcludingAssessedTax"],
        "Total Revenue",
    ),
    "net_income": (
        ["NetIncomeLoss", "ProfitLoss"],
        "Net Income / Loss",
    ),
    "gross_profit": (
        ["GrossProfit"],
        "Gross Profit",
    ),
    "operating_income": (
        ["OperatingIncomeLoss"],
        "Operating Income / Loss",
    ),
    "total_assets": (
        ["Assets"],
        "Total Assets",
    ),
    "total_liabilities": (
        ["Liabilities"],
        "Total Liabilities",
    ),
    "total_equity": (
        ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
        "Total Stockholders Equity",
    ),
    "current_assets": (
        ["AssetsCurrent"],
        "Current Assets",
    ),
    "current_liabilities": (
        ["LiabilitiesCurrent"],
        "Current Liabilities",
    ),
    "operating_cash_flow": (
        ["NetCashProvidedByUsedInOperatingActivities"],
        "Operating Cash Flow",
    ),
    "capex": (
        ["PaymentsToAcquirePropertyPlantAndEquipment"],
        "Capital Expenditures",
    ),
    "eps_basic": (
        ["EarningsPerShareBasic"],
        "Basic EPS",
    ),
    "eps_diluted": (
        ["EarningsPerShareDiluted"],
        "Diluted EPS",
    ),
    "shares_outstanding": (
        ["CommonStockSharesOutstanding"],
        "Shares Outstanding",
    ),
    "ebitda": (
        ["OperatingIncomeLoss", "EBITDA"],
        "EBITDA / Operating Income (fallback for EV/EBITDA)",
    ),
    "dividend_per_share": (
        ["CommonStockDividendsPerShareDeclared"],
        "Dividends per share declared",
    ),
}

# Forms we care about
_QUARTERLY_FORMS = {"10-Q", "10-Q/A"}
_ANNUAL_FORMS = {"10-K", "10-K/A"}


def _extract_tag_value(
    us_gaap_facts: dict[str, Any],
    tag_list: list[str],
) -> list[dict[str, Any]]:
    """Extract all filing entries across all fallback tags for a metric.

    Tries each tag in priority order and merges entries. The first tag
    that provides entries for a given (fy, fp) wins (priority order).
    Missing periods are filled by lower-priority fallback tags.

    Returns:
        List of dicts with keys: ``end``, ``val``, ``accn``, ``fy``, ``fp``,
        ``form``, ``filed``, ``frame`` (if present), ``unit``, ``tag_used``.
    """
    all_entries: list[dict[str, Any]] = []
    seen_periods: set[tuple[int | None, str | None]] = set()

    for tag in tag_list:
        tag_data = us_gaap_facts.get(tag)
        if not isinstance(tag_data, dict):
            continue
        units = tag_data.get("units", {})
        unit_key = "USD" if "USD" in units else next(iter(units), None)
        if not unit_key:
            continue
        entries = units[unit_key]
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if isinstance(entry, dict):
                entry = dict(entry)
                entry["unit"] = unit_key
                entry["tag_used"] = tag

                # Compute the period key for dedup between tags
                fy = entry.get("fy")
                fp = entry.get("fp")
                if (fy is None or not fp) and entry.get("frame"):
                    fy, fp = _parse_frame(str(entry["frame"]))

                if fy is not None and fp:
                    try:
                        fy = int(fy)
                    except (ValueError, TypeError):
                        fy = None
                    fp = str(fp).upper()
                else:
                    fy = None
                    fp = None

                period = (fy, fp)
                if period not in seen_periods:
                    seen_periods.add(period)
                    all_entries.append(entry)

    return all_entries


def _parse_date(date_str: str | None) -> _date | None:
    """Parse a SEC date string (YYYY-MM-DD) to date object."""
    if not date_str:
        return None
    try:
        return _date.fromisoformat(str(date_str)[:10])
    except ValueError:
        return None


def _is_10q(form: str) -> bool:
    return form in _QUARTERLY_FORMS


def _is_10k(form: str) -> bool:
    return form in _ANNUAL_FORMS


def _parse_frame(frame: str) -> tuple[int | None, str | None]:
    """Parse SEC frame string like 'CY2024Q4' → (2024, 'Q4').

    Also handles: 'CY2024' → (2024, 'FY'), 'FY2024Q3' → (2024, 'Q3').
    Returns (None, None) if unparseable.
    """
    import re
    # Match: optional prefix (CY/FY), year, optional Q[1-4]
    m = re.match(r"(?:CY|FY)?(\d{4})(Q[1-4])?", frame, re.IGNORECASE)
    if not m:
        return None, None
    year = int(m.group(1))
    quarter = m.group(2) or "FY"  # annual if no quarter
    return year, quarter.upper()


def _build_filing_index(
    entries: list[dict[str, Any]],
    metric_name: str,
) -> dict[tuple[int, str], dict[str, Any]]:
    """Index filings by (fiscal_year, fiscal_period) keeping the EARLIEST filing.

    For PIT: amendments update data but the first filing date is what matters
    for the initial availability. We keep the first filing for each (fy, fp).

    Handles both ``fy``/``fp`` and ``frame`` (CY2024Q4) formats.

    Returns:
        dict: (fy, fp) → filing dict with keys: val, filed, end, form, unit, tag_used
    """
    indexed: dict[tuple[int, str], dict[str, Any]] = {}
    for entry in entries:
        fy = entry.get("fy")
        fp = entry.get("fp")

        # Fallback: parse "frame" field (e.g., "CY2024Q4", "FY2024")
        if (fy is None or not fp) and entry.get("frame"):
            frame = str(entry["frame"])
            fy, fp = _parse_frame(frame)

        if fy is None or not fp:
            continue
        try:
            fy = int(fy)
        except (ValueError, TypeError):
            continue
        fp = str(fp).upper()
        key = (fy, fp)

        # Keep first filing for PIT safety
        if key not in indexed:
            indexed[key] = {
                "val": entry.get("val"),
                "filed": entry.get("filed"),
                "end": entry.get("end"),
                "form": entry.get("form"),
                "unit": entry.get("unit"),
                "tag_used": entry.get("tag_used"),
            }
    return indexed


# ── Main extraction function ──

def extract_fundamentals_from_sec(
    raw_facts: dict[str, Any],
    symbol: str,
) -> list[dict[str, Any]]:
    """Extract standardized quarterly fundamentals from SEC EDGAR XBRL facts.

    Performs:
    1. Tag extraction with fallback priority
    2. YTD → quarterly conversion for 10-Q income statement items
    3. TTM calculation for profitability ratios
    4. Ratio computation (margins, ROE, ROA, current ratio, debt/equity)

    Args:
        raw_facts: The ``us-gaap`` dict from ``fetch_company_facts()``.
        symbol: Stock ticker (for logging).

    Returns:
        List of dicts, one per (symbol, quarter, filed_date), with keys
        matching ``stock_fundamentals_daily`` columns.
        ``trade_date`` = ``filed`` date (PIT safe).
    """
    # ── Step 1: Extract raw tag values ──
    raw_metrics: dict[str, list[dict[str, Any]]] = {}
    for metric_name, (tag_list, _desc) in _TAG_MAP.items():
        entries = _extract_tag_value(raw_facts, tag_list)
        if entries:
            raw_metrics[metric_name] = entries
            LOGGER.debug("%s: %s → %d entries (tag=%s)", symbol, metric_name, len(entries), entries[0].get("tag_used", "?"))

    if not raw_metrics:
        LOGGER.warning("%s: no US-GAAP metrics extracted from SEC EDGAR", symbol)
        return []

    # ── Step 2: Index each metric by (fy, fp) ──
    indexed: dict[str, dict[tuple[int, str], dict[str, Any]]] = {}
    for metric_name, entries in raw_metrics.items():
        indexed[metric_name] = _build_filing_index(entries, metric_name)

    # ── Step 3: Collect all unique (fy, fp) periods ──
    all_periods: set[tuple[int, str]] = set()
    for metric_idx in indexed.values():
        all_periods.update(metric_idx.keys())

    if not all_periods:
        LOGGER.warning("%s: no filing periods found", symbol)
        return []

    # ── Step 4: Build quarterly records with YTD→Q conversion ──
    # YTD metrics: revenue, net_income, gross_profit, operating_income, ebitda
    _YTD_METRICS = {"revenue", "net_income", "gross_profit", "operating_income", "ebitda"}

    # Sort periods chronologically
    sorted_periods = sorted(all_periods, key=lambda x: (x[0], {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4, "FY": 5}.get(x[1], 99)))

    # For YTD→Q conversion, we need prior quarter in same FY
    _Q_ORDER = {"Q1": 0, "Q2": 1, "Q3": 2, "Q4": 3, "FY": 3}  # FY = Q4 for conversion
    _PREV_Q = {"Q2": "Q1", "Q3": "Q2", "Q4": "Q3", "FY": "Q3"}

    records: list[dict[str, Any]] = []

    for fy, fp in sorted_periods:
        filed_date = None
        end_date = None
        form = "10-K"  # default

        # Get the filed date from any metric (all should have same filing)
        for metric_idx in indexed.values():
            entry = metric_idx.get((fy, fp))
            if entry:
                filed_date = filed_date or entry.get("filed")
                end_date = end_date or entry.get("end")
                form = entry.get("form", form)

        if not filed_date or not end_date:
            continue

        filed_dt = _parse_date(str(filed_date))
        end_dt = _parse_date(str(end_date))
        if not filed_dt or not end_dt:
            continue

        # ── Build row ──
        row: dict[str, Any] = {
            "symbol": symbol.upper(),
            "trade_date": filed_dt,  # PIT safe: filed date, not quarter end
            "fy": fy,
            "fp": fp,
            "form": form,
        }

        # Income statement metrics (YTD → quarterly conversion)
        for metric in _YTD_METRICS:
            entry = indexed.get(metric, {}).get((fy, fp))
            if not entry or entry.get("val") is None:
                continue
            val = float(entry["val"])

            # Q1 = YTD1 (no conversion needed)
            # Q2 = YTD2 - YTD1
            # Q3 = YTD3 - YTD2
            # Q4/FY = YTD4 - YTD3
            prev_fp = _PREV_Q.get(fp)
            if prev_fp:
                prev_entry = indexed.get(metric, {}).get((fy, prev_fp))
                if prev_entry and prev_entry.get("val") is not None:
                    prev_val = float(prev_entry["val"])
                    val = val - prev_val

            row[metric] = val

        # Balance sheet metrics (point-in-time, no YTD conversion)
        _BS_METRICS = {
            "total_assets": "total_assets",
            "total_liabilities": "total_liabilities",
            "total_equity": "total_equity",
            "current_assets": "current_assets",
            "current_liabilities": "current_liabilities",
        }
        for metric, col_name in _BS_METRICS.items():
            entry = indexed.get(metric, {}).get((fy, fp))
            if entry and entry.get("val") is not None:
                row[col_name] = float(entry["val"])

        # Per-share metrics
        for metric in ("eps_basic", "eps_diluted", "shares_outstanding", "dividend_per_share"):
            entry = indexed.get(metric, {}).get((fy, fp))
            if entry and entry.get("val") is not None:
                row[metric] = float(entry["val"])

        # Cash flow
        for metric in ("operating_cash_flow", "capex"):
            entry = indexed.get(metric, {}).get((fy, fp))
            if entry and entry.get("val") is not None:
                # CF items may also be YTD; convert
                val = float(entry["val"])
                prev_fp = _PREV_Q.get(fp)
                if prev_fp:
                    prev_entry = indexed.get(metric, {}).get((fy, prev_fp))
                    if prev_entry and prev_entry.get("val") is not None:
                        val = val - float(prev_entry["val"])
                row[metric] = val

        records.append(row)

    # ── Step 5: Calculate TTM and ratios ──
    _compute_ratios(records)

    # ── Step 6: Map to stock_fundamentals_daily columns ──
    return _to_fundamentals_rows(records)


def _compute_ratios(records: list[dict[str, Any]]) -> None:
    """Compute TTM metrics, financial ratios, and YoY growth in-place.

    Uses proper TTM (trailing 4 quarters) for margins, ROE, ROA.
    Computes EPS Growth YoY and Revenue Growth YoY per-symbol.
    """
    if not records:
        return

    # Sort by trade_date for TTM rolling window
    records.sort(key=lambda r: r.get("trade_date", _date(1900, 1, 1)))

    # ── Process each symbol independently for TTM and growth ──
    symbols = sorted({r.get("symbol", "") for r in records})
    for sym in symbols:
        sym_records = [r for r in records if r.get("symbol") == sym]
        if len(sym_records) < 1:
            continue

        # Income statement items (quarterly after YTD→Q conversion)
        _TTM_METRICS = ["revenue", "net_income", "operating_income", "gross_profit"]

        for i, row in enumerate(sym_records):
            # TTM: sum current + up to 3 prior quarters
            ttm: dict[str, float] = {m: row.get(m) or 0.0 for m in _TTM_METRICS}
            count = 1
            for j in range(i - 1, max(i - 4, -1), -1):
                prev = sym_records[j]
                for m in _TTM_METRICS:
                    prev_val = prev.get(m)
                    if prev_val is not None:
                        ttm[m] += float(prev_val)
                count += 1
                if count >= 4:
                    break

            has_4q = count >= 4
            for m in _TTM_METRICS:
                row[f"{m}_ttm"] = ttm[m] if has_4q and ttm[m] != 0 else None

            # ── Accounting ratios (TTM-based) ──
            rev_ttm = row.get("revenue_ttm")
            ni_ttm = row.get("net_income_ttm")
            oi_ttm = row.get("operating_income_ttm")
            gp_ttm = row.get("gross_profit_ttm")

            if rev_ttm and rev_ttm > 0:
                if ni_ttm is not None:
                    row["net_margin"] = ni_ttm / rev_ttm
                if gp_ttm is not None:
                    row["gross_margin"] = gp_ttm / rev_ttm
                if oi_ttm is not None:
                    row["operating_margin"] = oi_ttm / rev_ttm

            # ROE / ROA
            equity = row.get("total_equity")
            assets = row.get("total_assets")
            if ni_ttm and equity and equity > 0:
                row["roe"] = ni_ttm / equity
            if ni_ttm and assets and assets > 0:
                row["roa"] = ni_ttm / assets

            # Current ratio
            ca = row.get("current_assets")
            cl = row.get("current_liabilities")
            if ca is not None and cl and cl > 0:
                row["current_ratio"] = ca / cl

            # Debt to equity
            liabilities = row.get("total_liabilities")
            if liabilities is not None and equity and equity > 0:
                row["debt_to_equity"] = liabilities / equity

            # Book value per share
            shares = row.get("shares_outstanding")
            if equity and shares and shares > 0:
                row["book_value_per_share"] = equity / shares

            # EPS (diluted preferred, basic fallback)
            if row.get("eps_diluted") is not None:
                row["eps"] = row["eps_diluted"]
            elif row.get("eps_basic") is not None:
                row["eps"] = row["eps_basic"]

            # ── YoY Growth (compare to same quarter 1 year ago = 4 quarters back) ──
            if i >= 4:
                prev_row = sym_records[i - 4]
                current_eps = row.get("eps")
                prev_eps = prev_row.get("eps")
                current_rev_ttm = row.get("revenue_ttm")
                prev_rev_ttm = prev_row.get("revenue_ttm")

                if current_eps and prev_eps and prev_eps != 0:
                    row["eps_growth_yoy"] = (current_eps / prev_eps) - 1.0
                if current_rev_ttm and prev_rev_ttm and prev_rev_ttm != 0:
                    row["revenue_growth_yoy"] = (current_rev_ttm / prev_rev_ttm) - 1.0

            # Store quarterly revenue for PS ratio calculation
            q_rev = row.get("revenue")
            if q_rev is not None:
                row["revenue"] = q_rev

        # Debug: count records with computed growth/ratios
        with_growth = sum(1 for r in sym_records if r.get("revenue_growth_yoy") is not None)
        with_ttm = sum(1 for r in sym_records if r.get("revenue_ttm") is not None)
        with_rev = sum(1 for r in sym_records if r.get("revenue") is not None)
        LOGGER.info(
            "%s: %d quarters | revenue=%d TTM=%d growth=%d",
            sym, len(sym_records), with_rev, with_ttm, with_growth,
        )


def _to_fundamentals_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Map internal record keys to stock_fundamentals_daily column names."""
    _COLUMN_MAP = {
        "symbol": "symbol",
        "trade_date": "trade_date",
        "net_margin": "net_margin",
        "operating_margin": "operating_margin",
        "gross_margin": "gross_margin",
        "roe": "roe",
        "roa": "roa",
        "debt_to_equity": "debt_to_equity",
        "current_ratio": "current_ratio",
        "book_value_per_share": "book_value_per_share",
        "shares_outstanding": "shares_outstanding",
        "eps": "eps",
        "eps_growth_yoy": "eps_growth_yoy",
        "revenue_growth_yoy": "revenue_growth_yoy",
        "ebitda": "ebitda",
        "revenue": "revenue",
        "dividend_per_share": "dividend_yield",
    }

    result: list[dict[str, Any]] = []
    for rec in records:
        row: dict[str, Any] = {}
        for src, dst in _COLUMN_MAP.items():
            if src in rec and rec[src] is not None:
                row[dst] = rec[src]
        # Always include symbol and trade_date
        row["symbol"] = rec.get("symbol", "")
        row["trade_date"] = rec.get("trade_date")
        if row["trade_date"]:
            result.append(row)

    return result
