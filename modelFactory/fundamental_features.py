"""modelFactory/fundamental_features.py — Fundamental features for ML models.

Loads point-in-time fundamentals from ``stock_fundamentals_daily``,
forward-fills between fetches, and derives feature columns for the
Global Ranking Model and per-symbol stacking.

Data sources
------------
- EODHD ``/fundamentals/{symbol}`` (current snapshot, fetched weekly)
- Stored in ``stock_fundamentals_daily`` with ``trade_date`` = fetch date
- Forward-filled between fetches (fundamentals change slowly — quarterly)

PIT safety
----------
- Each row has ``trade_date`` (when the snapshot was taken)
- Forward-fill ensures we never leak future information
- ``fetched_at`` tracks the actual API call timestamp for audit
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

LOGGER = logging.getLogger(__name__)

# ── Fundamental feature columns (derived from stock_fundamentals_daily) ──

FUNDAMENTAL_FEATURE_COLUMNS: list[str] = [
    # Valuation
    "fund_pe_ratio",
    "fund_forward_pe",
    "fund_peg_ratio",
    "fund_pb_ratio",
    "fund_ps_ratio",
    "fund_ev_to_ebitda",
    # Profitability
    "fund_roe",
    "fund_roa",
    "fund_net_margin",
    "fund_operating_margin",
    "fund_gross_margin",
    # Growth
    "fund_eps_growth_yoy",
    "fund_revenue_growth_yoy",
    # Health
    "fund_debt_to_equity",
    "fund_current_ratio",
    # Yield
    "fund_dividend_yield",
    # Market
    "fund_market_cap_log",
    "fund_beta",
    # Estimates
    "fund_eps_estimate_current",
    "fund_eps_estimate_next",
    # Derived
    "fund_eps_to_price",
    "fund_estimate_revision",
]

# ── DB column → feature column mapping ──

_DB_TO_FEATURE: dict[str, str] = {
    "pe_ratio": "fund_pe_ratio",
    "forward_pe": "fund_forward_pe",
    "peg_ratio": "fund_peg_ratio",
    "pb_ratio": "fund_pb_ratio",
    "ps_ratio": "fund_ps_ratio",
    "ev_to_ebitda": "fund_ev_to_ebitda",
    "roe": "fund_roe",
    "roa": "fund_roa",
    "net_margin": "fund_net_margin",
    "operating_margin": "fund_operating_margin",
    "gross_margin": "fund_gross_margin",
    "eps_growth_yoy": "fund_eps_growth_yoy",
    "revenue_growth_yoy": "fund_revenue_growth_yoy",
    "debt_to_equity": "fund_debt_to_equity",
    "current_ratio": "fund_current_ratio",
    "dividend_yield": "fund_dividend_yield",
    "market_cap": "fund_market_cap_log",  # transformed to log
    "beta": "fund_beta",
    "eps": "fund_eps_to_price",  # transformed: eps / price
    "eps_estimate_current": "fund_eps_estimate_current",
    "eps_estimate_next": "fund_eps_estimate_next",
}

# DB source columns needed from the table
_DB_SOURCE_COLUMNS: list[str] = [
    "symbol", "trade_date",
    "pe_ratio", "forward_pe", "peg_ratio", "pb_ratio", "ps_ratio",
    "ev_to_ebitda", "roe", "roa", "net_margin", "operating_margin",
    "gross_margin", "eps_growth_yoy", "revenue_growth_yoy",
    "debt_to_equity", "current_ratio",
    "dividend_yield", "market_cap", "beta", "eps",
    "book_value_per_share", "ebitda",
    "eps_estimate_current", "eps_estimate_next",
]

# Default fill values for each feature (neutral / no-signal)
FUNDAMENTAL_DEFAULTS: dict[str, float] = {
    "fund_pe_ratio": -1.0,           # -1 = no data (PE > 0 normally)
    "fund_forward_pe": -1.0,
    "fund_peg_ratio": -1.0,
    "fund_pb_ratio": -1.0,
    "fund_ps_ratio": -1.0,
    "fund_ev_to_ebitda": -1.0,
    "fund_roe": 0.0,                 # 0 = neutral
    "fund_roa": 0.0,
    "fund_net_margin": 0.0,
    "fund_operating_margin": 0.0,
    "fund_gross_margin": 0.0,
    "fund_eps_growth_yoy": 0.0,
    "fund_revenue_growth_yoy": 0.0,
    "fund_debt_to_equity": 0.0,
    "fund_current_ratio": 1.0,        # 1.0 = neutral
    "fund_dividend_yield": 0.0,
    "fund_market_cap_log": 0.0,
    "fund_beta": 1.0,               # 1.0 = market neutral
    "fund_eps_to_price": 0.0,
    "fund_eps_estimate_current": 0.0,
    "fund_eps_estimate_next": 0.0,
    "fund_estimate_revision": 0.0,
}


def load_fundamentals_from_db(
    symbols: list[str],
    start_date: str | pd.Timestamp,
    end_date: str | pd.Timestamp,
    *,
    engine=None,
) -> pd.DataFrame:
    """Load fundamental data from ``stock_fundamentals_daily`` for a set of symbols.

    Parameters
    ----------
    symbols : list[str]
        Stock symbols to load.
    start_date : str or pd.Timestamp
        Earliest date (inclusive).
    end_date : str or pd.Timestamp
        Latest date (inclusive).
    engine : SQLAlchemy Engine, optional
        If None, uses ``get_sqlalchemy_engine()``.

    Returns
    -------
    pd.DataFrame
        Columns: [symbol, trade_date, fetched_at, + all fundamental columns].
        Empty DataFrame if table doesn't exist or no data.
    """
    try:
        from sqlalchemy import select as _sa_select, and_
        from database.connection import get_sqlalchemy_engine

        resolved_engine = engine or get_sqlalchemy_engine()

        # Check if table exists
        from sqlalchemy import inspect as _sa_inspect
        inspector = _sa_inspect(resolved_engine)
        if "stock_fundamentals_daily" not in inspector.get_table_names():
            LOGGER.info("load_fundamentals_from_db: stock_fundamentals_daily table not found")
            return pd.DataFrame()

        from sqlalchemy import Table, MetaData
        table = Table(
            "stock_fundamentals_daily",
            MetaData(),
            autoload_with=resolved_engine,
        )

        cols_to_select = [
            getattr(table.c, col) for col in _DB_SOURCE_COLUMNS
            if col in table.c
        ]

        if not cols_to_select:
            return pd.DataFrame()

        query = (
            _sa_select(*cols_to_select)
            .where(and_(
                table.c.symbol.in_(sorted(set(symbols))),
                table.c.trade_date >= pd.Timestamp(start_date).date(),
                table.c.trade_date <= pd.Timestamp(end_date).date(),
            ))
            .order_by(table.c.symbol.asc(), table.c.trade_date.asc())
        )

        with resolved_engine.connect() as conn:
            df = pd.read_sql_query(query, conn)

        if df.empty:
            return df

        # Normalize
        df["trade_date"] = pd.to_datetime(df["trade_date"])
        return df.reset_index(drop=True)

    except Exception:
        LOGGER.warning("load_fundamentals_from_db failed, returning empty", exc_info=True)
        return pd.DataFrame()


def forward_fill_fundamentals(
    fund_df: pd.DataFrame,
    date_range: pd.DatetimeIndex,
) -> pd.DataFrame:
    """Forward-fill fundamental data across a date range.

    For each symbol, the latest known fundamental values (as of each
    ``trade_date``) are forward-filled to all subsequent dates in
    ``date_range``. This is PIT-safe because we only use values known
    on or before each date.

    Parameters
    ----------
    fund_df : pd.DataFrame
        Raw data from ``load_fundamentals_from_db``.
    date_range : pd.DatetimeIndex
        The full trading calendar to fill.

    Returns
    -------
    pd.DataFrame
        Columns: [symbol, date, + feature columns], one row per (symbol, date).
    """
    if fund_df.empty:
        return pd.DataFrame()

    # Pivot: symbol × trade_date → feature columns
    value_cols = [
        c for c in fund_df.columns
        if c not in ("symbol", "trade_date", "fetched_at")
    ]
    if not value_cols:
        return pd.DataFrame()

    # Build a complete symbol × date grid
    symbols = sorted(fund_df["symbol"].unique())
    grid = pd.MultiIndex.from_product(
        [symbols, date_range],
        names=["symbol", "date"],
    ).to_frame(index=False)

    # Merge known fundamentals into the grid
    pivot = fund_df.pivot_table(
        index=["symbol", "trade_date"],
        values=value_cols,
        aggfunc="last",
    ).reset_index()
    pivot = pivot.rename(columns={"trade_date": "date"})
    pivot["date"] = pd.to_datetime(pivot["date"])

    merged = grid.merge(pivot, on=["symbol", "date"], how="left")

    # Forward-fill within each symbol group
    merged = merged.sort_values(["symbol", "date"]).reset_index(drop=True)
    for col in value_cols:
        merged[col] = merged.groupby("symbol")[col].ffill()

    return merged


def derive_features(df: pd.DataFrame) -> pd.DataFrame:
    """Transform raw DB columns into ML-ready fundamental features.

    Transformations:
    - market_cap → fund_market_cap_log (log10)
    - eps → fund_eps_to_price (earnings yield = eps / price)
    - eps_estimate_current/next → fund_estimate_revision (next vs current)

    Also applies the column renaming from ``_DB_TO_FEATURE``.
    """
    result = df.copy()

    # ── Rename DB columns to feature names ──
    rename_map = {
        db_col: feature_col
        for db_col, feature_col in _DB_TO_FEATURE.items()
        if db_col in result.columns
    }
    result = result.rename(columns=rename_map)

    # ── Transform: market_cap → log10 ──
    if "fund_market_cap_log" in result.columns:
        cap = result["fund_market_cap_log"].astype(float).clip(lower=1.0)
        result["fund_market_cap_log"] = np.log10(cap)

    # ── We need close price for eps_to_price — computed externally ──
    # The caller merges with bars data first, then calls this.
    # If "close" column is present, derive eps_to_price.
    if "close" in result.columns and "fund_eps_to_price" in result.columns:
        price = result["close"].astype(float).clip(lower=1e-8)
        result["fund_eps_to_price"] = (
            result["fund_eps_to_price"].astype(float) / price
        ).fillna(0.0)

    # ── Derived: estimate revision (next_year / current_year - 1) ──
    if "fund_eps_estimate_current" in result.columns and "fund_eps_estimate_next" in result.columns:
        current = result["fund_eps_estimate_current"].astype(float)
        next_est = result["fund_eps_estimate_next"].astype(float)
        result["fund_estimate_revision"] = np.where(
            current.abs() > 1e-8,
            (next_est / current) - 1.0,
            0.0,
        )

    # ── Fill missing features with defaults ──
    for col, default in FUNDAMENTAL_DEFAULTS.items():
        if col not in result.columns:
            result[col] = default
        else:
            result[col] = result[col].fillna(default).astype(float)
            result[col] = result[col].replace([np.inf, -np.inf], default)

    return result


def merge_fundamentals(
    bars_df: pd.DataFrame,
    *,
    engine=None,
    fundamental_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Merge fundamental features into bars data.

    This is the main entry point called from ``compute_features()`` or
    ``prepare_symbol_frame()``.

    Parameters
    ----------
    bars_df : pd.DataFrame
        Must have columns: [symbol, date, close, ...].
    engine : SQLAlchemy Engine, optional
        Used to load fundamentals from DB if ``fundamental_df`` is None.
    fundamental_df : pd.DataFrame, optional
        Pre-loaded fundamentals (from orchestrator cache). If None,
        loads from DB.

    Returns
    -------
    pd.DataFrame
        ``bars_df`` with ``FUNDAMENTAL_FEATURE_COLUMNS`` merged on
        (symbol, date), forward-filled, and defaulted.
    """
    if "symbol" not in bars_df.columns or "date" not in bars_df.columns:
        LOGGER.warning("merge_fundamentals: missing symbol/date columns, returning unchanged")
        return bars_df

    symbols = sorted(bars_df["symbol"].unique())
    date_min = bars_df["date"].min()
    date_max = bars_df["date"].max()

    # ── Load fundamentals ──
    if fundamental_df is None or fundamental_df.empty:
        fund_raw = load_fundamentals_from_db(
            symbols,
            start_date=date_min,
            end_date=date_max,
            engine=engine,
        )
    else:
        fund_raw = fundamental_df.copy()

    if fund_raw.empty:
        LOGGER.info("merge_fundamentals: no fundamentals data, filling defaults")
        for col, default in FUNDAMENTAL_DEFAULTS.items():
            bars_df[col] = default
        return bars_df

    # ── Forward-fill across the bars date range ──
    date_range = pd.date_range(
        pd.Timestamp(date_min),
        pd.Timestamp(date_max),
        freq="D",
    )
    fund_ffilled = forward_fill_fundamentals(fund_raw, date_range)

    if fund_ffilled.empty:
        for col, default in FUNDAMENTAL_DEFAULTS.items():
            bars_df[col] = default
        return bars_df

    # ── Merge on (symbol, date) ──
    fund_ffilled["date"] = pd.to_datetime(fund_ffilled["date"])
    bars_df["date"] = pd.to_datetime(bars_df["date"])

    merged = bars_df.merge(
        fund_ffilled,
        on=["symbol", "date"],
        how="left",
    )

    # ── Derive transformed features ──
    result = derive_features(merged)

    return result


# ── EODHD fundamentals populator (used by CLI / scheduled job) ──

def fetch_and_store_fundamentals(
    symbols: list[str],
    *,
    engine=None,
    session=None,
    provider: str = "eodhd",
) -> dict[str, Any]:
    """Fetch fundamentals from EODHD and store in ``stock_fundamentals_daily``.

    With a paid EODHD subscription, extracts **historical quarterly data**
    from the ``Financials`` section (Income_Statement, Balance_Sheet,
    Cash_Flow) and stores one row per (symbol, quarter_date).
    Fallback: if ``Financials`` is not available, stores a single row
    with ``trade_date`` = today (snapshot mode).

    Parameters
    ----------
    symbols : list[str]
        Symbols to fetch.
    engine : SQLAlchemy Engine, optional
    session : requests.Session, optional
    provider : str
        "eodhd" (default), "finnhub", or "yahoo_finance".

    Returns
    -------
    dict with keys: stored (int), failed (int), errors (list[str])
    """
    import time
    from datetime import date as _date, datetime as _dt, timezone

    try:
        from sqlalchemy import text as _sa_text
        from database.connection import get_sqlalchemy_engine
        resolved_engine = engine or get_sqlalchemy_engine()
    except Exception as exc:
        return {"stored": 0, "failed": len(symbols), "errors": [f"engine: {exc}"]}

    now_utc = _dt.now(timezone.utc).replace(tzinfo=None)
    stored = 0
    failed = 0
    errors: list[str] = []

    for symbol in symbols:
        try:
            normalized = str(symbol).strip().upper()

            if provider == "eodhd":
                from service.eodhd.clientEodhd import fetch_fundamentals
                raw = fetch_fundamentals(normalized, session=session)

                # Try to extract historical quarterly data (paid subscription)
                quarterly_rows = _extract_quarterly_fundamentals(normalized, raw)

                if quarterly_rows:
                    for row in quarterly_rows:
                        row["fetched_at"] = now_utc
                        row["source"] = "EODHD"
                        _upsert_fundamentals_row(resolved_engine, **row)
                    stored += len(quarterly_rows)
                    LOGGER.info(
                        "fetch_and_store_fundamentals %s: %d quarters stored (historical mode)",
                        normalized, len(quarterly_rows),
                    )
                else:
                    # Fallback: no Financials data → snapshot mode
                    record = _fetch_fundamentals_record(normalized, session=session)
                    _upsert_fundamentals_row(
                        resolved_engine,
                        symbol=normalized,
                        trade_date=_date.today(),
                        fetched_at=now_utc,
                        record=record,
                        source=record.get("source", "EODHD"),
                    )
                    stored += 1
                    LOGGER.info(
                        "fetch_and_store_fundamentals %s: snapshot stored (no Financials)",
                        normalized,
                    )
            else:
                # Finnhub / Yahoo → single snapshot
                record = _fetch_fundamentals_record(normalized, provider=provider, session=session)
                _upsert_fundamentals_row(
                    resolved_engine,
                    symbol=normalized,
                    trade_date=_date.today(),
                    fetched_at=now_utc,
                    record=record,
                    source=record.get("source", provider.upper()),
                )
                stored += 1

        except Exception as exc:
            failed += 1
            errors.append(f"{symbol}: {exc}")
            LOGGER.warning("fetch_and_store_fundamentals failed for %s: %s", symbol, exc)

        # Respect rate limits
        time.sleep(0.25)

    LOGGER.info(
        "fetch_and_store_fundamentals done: stored=%d failed=%d symbols=%d",
        stored, failed, len(symbols),
    )
    return {"stored": stored, "failed": failed, "errors": errors}


def _extract_quarterly_fundamentals(
    symbol: str,
    raw_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    """Extract historical quarterly fundamentals from EODHD Financials.

    Parses ``Income_Statement.quarterly``, ``Balance_Sheet.quarterly``,
    ``Cash_Flow.quarterly`` and ``Highlights`` to reconstruct fundamental
    ratios for each historical quarter.

    Returns a list of dicts, each with keys matching
    ``stock_fundamentals_daily`` columns. Empty list if no Financials
    data is available (free tier).
    """
    financials = raw_payload.get("Financials") if isinstance(raw_payload.get("Financials"), dict) else {}
    if not financials:
        LOGGER.info("_extract_quarterly_fundamentals %s: no Financials section", symbol)
        return []

    income = financials.get("Income_Statement", {}) if isinstance(financials.get("Income_Statement"), dict) else {}
    balance = financials.get("Balance_Sheet", {}) if isinstance(financials.get("Balance_Sheet"), dict) else {}
    cashflow = financials.get("Cash_Flow", {}) if isinstance(financials.get("Cash_Flow"), dict) else {}
    highlights = raw_payload.get("Highlights") if isinstance(raw_payload.get("Highlights"), dict) else {}
    valuation = raw_payload.get("Valuation") if isinstance(raw_payload.get("Valuation"), dict) else {}
    technicals = raw_payload.get("Technicals") if isinstance(raw_payload.get("Technicals"), dict) else {}
    general = raw_payload.get("General") if isinstance(raw_payload.get("General"), dict) else {}

    # ── Collect all quarter dates from income statement ──
    quarterly_income = income.get("quarterly", {}) if isinstance(income.get("quarterly"), dict) else {}
    if not quarterly_income:
        LOGGER.info("_extract_quarterly_fundamentals %s: no quarterly income data", symbol)
        return []

    quarters = sorted(quarterly_income.keys(), reverse=True)

    # ── Current snapshot values (same for all quarters) ──
    _sf = lambda v: float(v) if v not in (None, "", "N/A") and str(v).strip() else None

    snapshot = {
        "beta": _sf(technicals.get("Beta")),
        "dividend_yield": _sf(highlights.get("DividendYield")),
        "eps_estimate_current": _sf(highlights.get("EPSEstimateCurrentYear")),
        "eps_estimate_next": _sf(highlights.get("EPSEstimateNextYear")),
        "forward_pe": _sf(valuation.get("ForwardPE")),
    }

    # Market cap from General or Highlights
    mkt_cap = _sf(general.get("MarketCapitalization")) or _sf(highlights.get("MarketCapitalization"))

    rows: list[dict[str, Any]] = []
    for quarter_date in quarters:
        q_income = quarterly_income.get(quarter_date, {}) if isinstance(quarterly_income.get(quarter_date), dict) else {}
        q_balance = (balance.get("quarterly", {}) or {}).get(quarter_date, {}) if isinstance(balance.get("quarterly"), dict) else {}
        q_cf = (cashflow.get("quarterly", {}) or {}).get(quarter_date, {}) if isinstance(cashflow.get("quarterly"), dict) else {}

        # ── Income statement ──
        revenue = _sf(q_income.get("totalRevenue")) or _sf(q_income.get("revenue"))
        gross_profit = _sf(q_income.get("grossProfit"))
        operating_income = _sf(q_income.get("operatingIncome")) or _sf(q_income.get("ebit"))
        net_income = _sf(q_income.get("netIncome"))
        eps_q = _sf(q_income.get("eps")) or _sf(q_income.get("dilutedEPS"))
        ebitda_q = _sf(q_income.get("ebitda"))

        # ── Balance sheet ──
        total_assets = _sf(q_balance.get("totalAssets"))
        total_equity = _sf(q_balance.get("totalStockholderEquity")) or _sf(q_balance.get("totalEquity"))
        total_debt = _sf(q_balance.get("totalDebt")) or _sf(q_balance.get("longTermDebt"))
        total_current_assets = _sf(q_balance.get("totalCurrentAssets"))
        total_current_liabilities = _sf(q_balance.get("totalCurrentLiabilities"))

        # ── Derived ratios ──
        # PE: market_cap / net_income (annualized)
        pe_ratio = None
        if mkt_cap and net_income and net_income > 0:
            pe_ratio = mkt_cap / (net_income * 4)  # quarterly → annualized

        pb_ratio = None
        if mkt_cap and total_equity and total_equity > 0:
            pb_ratio = mkt_cap / total_equity

        ps_ratio = None
        if mkt_cap and revenue and revenue > 0:
            ps_ratio = mkt_cap / (revenue * 4)

        roe = None
        if net_income and total_equity and total_equity > 0:
            roe = (net_income * 4) / total_equity

        roa = None
        if net_income and total_assets and total_assets > 0:
            roa = (net_income * 4) / total_assets

        gross_margin = None
        if gross_profit and revenue and revenue > 0:
            gross_margin = gross_profit / revenue

        net_margin = None
        if net_income and revenue and revenue > 0:
            net_margin = net_income / revenue

        operating_margin = None
        if operating_income and revenue and revenue > 0:
            operating_margin = operating_income / revenue

        debt_to_equity = None
        if total_debt and total_equity and total_equity > 0:
            debt_to_equity = total_debt / total_equity

        current_ratio = None
        if total_current_assets and total_current_liabilities and total_current_liabilities > 0:
            current_ratio = total_current_assets / total_current_liabilities

        # ── Growth: compare to same quarter last year ──
        eps_growth_yoy = None
        revenue_growth_yoy = None
        prev_year_q = _get_prev_year_quarter(quarter_date)
        if prev_year_q and prev_year_q in quarterly_income:
            prev_income = quarterly_income[prev_year_q] if isinstance(quarterly_income.get(prev_year_q), dict) else {}
            prev_eps = _sf(prev_income.get("eps")) or _sf(prev_income.get("dilutedEPS"))
            prev_rev = _sf(prev_income.get("totalRevenue")) or _sf(prev_income.get("revenue"))
            if eps_q and prev_eps and prev_eps != 0:
                eps_growth_yoy = (eps_q / prev_eps) - 1.0
            if revenue and prev_rev and prev_rev != 0:
                revenue_growth_yoy = (revenue / prev_rev) - 1.0

        # ── EV/EBITDA ──
        ev_to_ebitda = None
        enterprise_value = _sf(valuation.get("EnterpriseValue"))
        if enterprise_value and ebitda_q and ebitda_q > 0:
            ev_to_ebitda = enterprise_value / (ebitda_q * 4)
        elif mkt_cap and total_debt and ebitda_q and ebitda_q > 0:
            # Approximate EV = market cap + total debt
            ev_to_ebitda = (mkt_cap + (total_debt or 0)) / (ebitda_q * 4)

        row: dict[str, Any] = {
            "symbol": symbol,
            "trade_date": quarter_date,
            "pe_ratio": pe_ratio,
            "pb_ratio": pb_ratio,
            "ps_ratio": ps_ratio,
            "ev_to_ebitda": ev_to_ebitda,
            "roe": roe,
            "roa": roa,
            "gross_margin": gross_margin,
            "net_margin": net_margin,
            "operating_margin": operating_margin,
            "eps": eps_q,
            "eps_growth_yoy": eps_growth_yoy,
            "revenue_growth_yoy": revenue_growth_yoy,
            "debt_to_equity": debt_to_equity,
            "current_ratio": current_ratio,
            "market_cap": mkt_cap,
            "ebitda": ebitda_q,
            "book_value_per_share": _sf(q_balance.get("bookValuePerShare")),
            **snapshot,
        }
        rows.append(row)

    LOGGER.info(
        "_extract_quarterly_fundamentals %s: %d quarters extracted (%s → %s)",
        symbol, len(rows), quarters[-1] if quarters else "N/A", quarters[0] if quarters else "N/A",
    )
    return rows


def _get_prev_year_quarter(quarter_date: str) -> str | None:
    """Given '2025-06-30', return '2024-06-30'."""
    try:
        from datetime import date as _dt_date, timedelta
        d = _dt_date.fromisoformat(quarter_date)
        # Try same day previous year
        prev = d.replace(year=d.year - 1)
        return prev.isoformat()
    except (ValueError, TypeError):
        return None


def _fetch_fundamentals_record(
    symbol: str,
    *,
    provider: str = "eodhd",
    session=None,
) -> dict[str, Any]:
    """Fetch normalized fundamental record from a provider."""
    provider_lower = provider.lower().strip()

    if provider_lower == "eodhd":
        from service.eodhd.clientEodhd import (
            fetch_fundamentals,
            fetch_symbol_fundamentals_record as eodhd_record,
        )
        # Get both the normalized record AND the raw profile
        record = eodhd_record(symbol, session=session)
        # Extract additional fields from raw_profile
        raw = record.get("raw_profile", {})
        highlights = (raw.get("Highlights") if isinstance(raw.get("Highlights"), dict) else {})
        valuation = (raw.get("Valuation") if isinstance(raw.get("Valuation"), dict) else {})
        technicals = (raw.get("Technicals") if isinstance(raw.get("Technicals"), dict) else {})

        record.update(_extract_eodhd_highlights(highlights))
        record.update(_extract_eodhd_valuation(valuation))
        record.update(_extract_eodhd_technicals(technicals))
        return record

    elif provider_lower in ("finnhub", "yahoo_finance", "yahoo"):
        # Limited — just sector + market_cap
        if provider_lower == "finnhub":
            from service.finnhub.clientFinnhub import fetch_symbol_fundamentals_record as fn_record
            return fn_record(symbol, session=session)
        else:
            from service.yahoo.clientYahooFinance import fetch_symbol_fundamentals_record as yf_record
            return yf_record(symbol, session=session)
    else:
        raise ValueError(f"Unknown provider: {provider}")


def _extract_eodhd_highlights(highlights: dict) -> dict[str, Any]:
    """Extract normalized fundamental values from EODHD Highlights section."""
    result: dict[str, Any] = {}

    _safe_float = lambda v: float(v) if v not in (None, "", "N/A") and str(v).strip() else None

    result["market_cap"] = _safe_float(highlights.get("MarketCapitalization"))
    result["pe_ratio"] = _safe_float(highlights.get("PERatio"))
    result["peg_ratio"] = _safe_float(highlights.get("PEGRatio"))
    result["eps"] = _safe_float(highlights.get("EarningsShare"))
    result["book_value_per_share"] = _safe_float(highlights.get("BookValue"))
    result["ebitda"] = _safe_float(highlights.get("EBITDA"))
    result["dividend_yield"] = _safe_float(highlights.get("DividendYield"))

    result["roe"] = _safe_float(highlights.get("ReturnOnEquityTTM"))
    result["roa"] = _safe_float(highlights.get("ReturnOnAssetsTTM"))
    result["net_margin"] = _safe_float(highlights.get("ProfitMargin"))
    result["operating_margin"] = _safe_float(highlights.get("OperatingMarginTTM"))

    result["eps_growth_yoy"] = _safe_float(highlights.get("QuarterlyEarningsGrowthYOY"))
    result["revenue_growth_yoy"] = _safe_float(highlights.get("QuarterlyRevenueGrowthYOY"))

    result["eps_estimate_current"] = _safe_float(highlights.get("EPSEstimateCurrentYear"))
    result["eps_estimate_next"] = _safe_float(highlights.get("EPSEstimateNextYear"))

    # Derived: gross margin
    gross_profit = _safe_float(highlights.get("GrossProfitTTM"))
    revenue = _safe_float(highlights.get("RevenueTTM"))
    if gross_profit is not None and revenue is not None and revenue > 0:
        result["gross_margin"] = gross_profit / revenue
    else:
        result["gross_margin"] = None

    return result


def _extract_eodhd_valuation(valuation: dict) -> dict[str, Any]:
    """Extract normalized fundamental values from EODHD Valuation section."""
    result: dict[str, Any] = {}
    _safe_float = lambda v: float(v) if v not in (None, "", "N/A") and str(v).strip() else None

    result["forward_pe"] = _safe_float(valuation.get("ForwardPE"))
    result["pb_ratio"] = _safe_float(valuation.get("PriceBookMRQ"))
    result["ps_ratio"] = _safe_float(valuation.get("PriceSalesTTM"))
    result["ev_to_ebitda"] = _safe_float(valuation.get("EnterpriseValueEbitda"))

    return result


def _extract_eodhd_technicals(technicals: dict) -> dict[str, Any]:
    """Extract beta from EODHD Technicals section."""
    result: dict[str, Any] = {}
    _safe_float = lambda v: float(v) if v not in (None, "", "N/A") and str(v).strip() else None

    result["beta"] = _safe_float(technicals.get("Beta"))
    return result


def _upsert_fundamentals_row(
    engine: Any,
    symbol: str,
    trade_date: Any,
    fetched_at: Any,
    record: dict[str, Any],
    source: str = "EODHD",
) -> None:
    """Insert or update a row in stock_fundamentals_daily."""
    from sqlalchemy import text as _sa_text

    column_map = {
        "pe_ratio", "forward_pe", "peg_ratio", "pb_ratio", "ps_ratio",
        "ev_to_ebitda", "roe", "roa", "net_margin", "operating_margin",
        "gross_margin", "eps_growth_yoy", "revenue_growth_yoy",
        "debt_to_equity", "current_ratio",
        "dividend_yield", "market_cap", "beta", "eps",
        "book_value_per_share", "ebitda",
        "eps_estimate_current", "eps_estimate_next",
    }

    set_clauses: list[str] = ["fetched_at = :fetched_at", "source = :source"]
    params: dict[str, Any] = {
        "symbol": symbol,
        "trade_date": trade_date,
        "fetched_at": fetched_at,
        "source": source,
    }

    for col in sorted(column_map):
        val = record.get(col)
        if val is not None:
            set_clauses.append(f"{col} = :{col}")
            params[col] = float(val)

    if len(set_clauses) <= 2:
        # No data to store
        return

    upsert_sql = f"""
        INSERT INTO stock_fundamentals_daily
            (symbol, trade_date, fetched_at, source, {', '.join(p for p in params if p not in ('symbol', 'trade_date', 'fetched_at', 'source'))})
        VALUES
            (:symbol, :trade_date, :fetched_at, :source, {', '.join(f':{p}' for p in params if p not in ('symbol', 'trade_date', 'fetched_at', 'source'))})
        ON DUPLICATE KEY UPDATE
            {', '.join(set_clauses)}
    """

    with engine.begin() as conn:
        conn.execute(_sa_text(upsert_sql), params)


__all__ = [
    "FUNDAMENTAL_FEATURE_COLUMNS",
    "FUNDAMENTAL_DEFAULTS",
    "load_fundamentals_from_db",
    "forward_fill_fundamentals",
    "derive_features",
    "merge_fundamentals",
    "fetch_and_store_fundamentals",
]
