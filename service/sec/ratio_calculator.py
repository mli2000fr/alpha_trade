"""service/sec/ratio_calculator.py — Market-based ratios from stock_bars_daily + SEC fundamentals.

Computes PE, PB, PS, Market Cap, EV/EBITDA, Dividend Yield, and Beta
using daily closing prices from ``stock_bars_daily`` and accounting data
from ``stock_fundamentals_daily`` (populated by SEC EDGAR).

PIT Safety:
    All calculations use ``trade_date`` closing price (same-day),
    combined with fundamental data available ON or BEFORE that date
    (forward-filled from SEC ``filed`` dates).
    No look-ahead: if fundamentals aren't available yet, the ratio is NULL.

Usage:
    >>> from service.sec.ratio_calculator import enrich_with_market_ratios
    >>> enrich_with_market_ratios(engine, symbols, start_date='2018-01-01')
"""
from __future__ import annotations

import logging
from datetime import date as _date, timedelta
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import text as _sa_text

LOGGER = logging.getLogger(__name__)

# Beta: rolling window size (trading days)
_BETA_WINDOW = 60

# Columns that this module can fill
_MARKET_RATIO_COLUMNS = [
    "pe_ratio",
    "pb_ratio",
    "ps_ratio",
    "market_cap",
    "ev_to_ebitda",
    "dividend_yield",
    "beta",
]


def enrich_with_market_ratios(
    engine: Any,
    symbols: list[str],
    *,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, int]:
    """Enrich stock_fundamentals_daily with market-based ratios.

    For each (symbol, trade_date) that has SEC fundamental data but
    missing market ratios, fetches the closing price from stock_bars_daily
    and computes PE, PB, PS, Market Cap, EV/EBITDA, Dividend Yield, Beta.

    Args:
        engine: SQLAlchemy engine.
        symbols: List of symbols to process.
        start_date: Optional start date filter (YYYY-MM-DD).
        end_date: Optional end date filter (YYYY-MM-DD).

    Returns:
        dict with ``updated`` (int) count of rows enriched.
    """
    if not symbols:
        return {"updated": 0}

    symbol_list = ", ".join(f":sym_{i}" for i in range(len(symbols)))
    symbol_params = {f"sym_{i}": s.upper() for i, s in enumerate(symbols)}

    # ── Step 1: Load SEC fundamental data ──
    fund_query = f"""
        SELECT
            sfd.id,
            sfd.symbol,
            sfd.trade_date,
            sfd.eps,
            sfd.book_value_per_share,
            sfd.shares_outstanding,
            sfd.revenue,
            sfd.dividend_yield AS sec_dividend,
            sfd.ebitda,
            sfd.pe_ratio,
            sfd.pb_ratio,
            sfd.ps_ratio,
            sfd.market_cap,
            sfd.ev_to_ebitda,
            sfd.beta
        FROM stock_fundamentals_daily sfd
        WHERE sfd.symbol IN ({symbol_list})
          AND sfd.source = 'SEC_EDGAR'
    """
    params: dict[str, Any] = dict(symbol_params)
    date_cond = ""
    if start_date:
        date_cond += " AND sfd.trade_date >= :start_date"
        params["start_date"] = start_date
    if end_date:
        date_cond += " AND sfd.trade_date <= :end_date"
        params["end_date"] = end_date
    fund_query += date_cond + " ORDER BY sfd.symbol, sfd.trade_date"

    fund_df = pd.read_sql_query(_sa_text(fund_query), engine, params=params)
    if fund_df.empty:
        LOGGER.info("No SEC EDGAR fundamentals found for enrichment.")
        return {"updated": 0}

    # Only process rows where at least one market ratio is missing
    fund_df["_needs_enrich"] = (
        fund_df["pe_ratio"].isna()
        | fund_df["pb_ratio"].isna()
        | fund_df["market_cap"].isna()
        | fund_df["beta"].isna()
    )
    needs_enrich = fund_df[fund_df["_needs_enrich"]]
    if needs_enrich.empty:
        LOGGER.info("All market ratios already populated — nothing to enrich.")
        return {"updated": 0}

    LOGGER.info(
        "Enriching %d/%d rows with market ratios for %d symbols",
        len(needs_enrich), len(fund_df), len(symbols),
    )

    # ── Step 2: Fetch stock prices from stock_bars_daily ──
    min_date = str(needs_enrich["trade_date"].min())
    max_date = str(needs_enrich["trade_date"].max())

    # Also need SPY prices for beta
    all_symbols_for_prices = list(set(symbols) | {"SPY"})
    price_params: dict[str, Any] = {
        "min_date": min_date,
        "max_date": max_date,
    }
    price_symbol_list = ", ".join(f":psym_{i}" for i in range(len(all_symbols_for_prices)))
    for i, s in enumerate(all_symbols_for_prices):
        price_params[f"psym_{i}"] = s.upper()

    price_query = f"""
        SELECT symbol, date, adj_close AS close, volume
        FROM stock_bars_daily
        WHERE symbol IN ({price_symbol_list})
          AND date BETWEEN :min_date AND :max_date
        ORDER BY symbol, date
    """
    price_df = pd.read_sql_query(_sa_text(price_query), engine, params=price_params)
    price_df["date"] = pd.to_datetime(price_df["date"])

    if price_df.empty:
        LOGGER.warning("No price data found in stock_bars_daily for enrichment.")
        return {"updated": 0}

    # Pivot SPY prices for beta calculation
    spy_prices = (
        price_df[price_df["symbol"] == "SPY"]
        .set_index("date")["close"]
        .sort_index()
    )
    # Daily SPY returns
    spy_returns = spy_prices.pct_change().dropna()

    # Pivot stock prices
    stock_prices = price_df[price_df["symbol"] != "SPY"].copy()
    stock_prices["date"] = pd.to_datetime(stock_prices["date"])

    # ── Step 3: Forward-fill fundamental data to each trade_date ──
    fund_df["trade_date"] = pd.to_datetime(fund_df["trade_date"])

    # Merge price at trade_date
    enriched_rows: list[dict[str, Any]] = []
    updated = 0

    for symbol in needs_enrich["symbol"].unique():
        sym_fund = needs_enrich[needs_enrich["symbol"] == symbol].copy()
        sym_prices = stock_prices[stock_prices["symbol"] == symbol].set_index("date").sort_index()

        if sym_prices.empty:
            continue

        # Forward-fill EPS, BVPS, shares, revenue within this symbol
        sym_fund = sym_fund.sort_values("trade_date")
        for col in ["eps", "book_value_per_share", "shares_outstanding", "revenue", "ebitda"]:
            if col in sym_fund.columns:
                sym_fund[col] = sym_fund[col].ffill()

        for _, row in sym_fund.iterrows():
            td = row["trade_date"]
            td_ts = pd.Timestamp(td)

            if td_ts not in sym_prices.index:
                continue
            close_price = float(sym_prices.loc[td_ts, "close"])

            shares = row.get("shares_outstanding")
            updates: dict[str, Any] = {"id": row["id"]}

            # Market Cap = close × shares_outstanding
            if shares and shares > 0 and close_price > 0:
                updates["market_cap"] = close_price * shares

            # PE Ratio = close / (EPS × 4)
            eps = row.get("eps")
            if eps and eps > 0 and close_price > 0:
                annual_eps = eps * 4
                if annual_eps > 0:
                    updates["pe_ratio"] = close_price / annual_eps

            # PB Ratio = close / book_value_per_share
            bvps = row.get("book_value_per_share")
            if bvps and bvps > 0 and close_price > 0:
                updates["pb_ratio"] = close_price / bvps

            # PS Ratio = market_cap / (revenue × 4) — revenue is quarterly
            revenue = row.get("revenue")
            if revenue and revenue > 0 and shares and shares > 0:
                market_cap_val = updates.get("market_cap") or (close_price * shares)
                annual_rev = revenue * 4
                if annual_rev > 0:
                    updates["ps_ratio"] = market_cap_val / annual_rev

            # EV/EBITDA — approximate
            ebitda = row.get("ebitda")
            market_cap_val = updates.get("market_cap") or (close_price * shares if shares else None)
            if ebitda and ebitda > 0 and market_cap_val:
                updates["ev_to_ebitda"] = market_cap_val / (ebitda * 4)

            # Beta
            if td_ts in sym_prices.index and len(spy_returns) >= _BETA_WINDOW:
                beta = _compute_beta(sym_prices, spy_returns, td_ts, _BETA_WINDOW)
                if beta is not None:
                    updates["beta"] = beta

            # Dividend yield = dividend_per_share / close_price
            dps = row.get("sec_dividend")  # stored as dividend_yield from SEC (raw $ amount)
            if dps is not None and dps > 0 and close_price > 0:
                updates["dividend_yield"] = dps / close_price

            if len(updates) > 1:
                enriched_rows.append(updates)

        updated += len([r for r in enriched_rows if len(r) > 1])

    # ── Step 4: Batch UPDATE existing rows ──
    if enriched_rows:
        _batch_update_market_ratios(engine, enriched_rows)
        LOGGER.info("Market ratio enrichment complete: %d rows updated.", len(enriched_rows))
    else:
        LOGGER.info("No rows needed enrichment.")

    return {"updated": len(enriched_rows)}


def _compute_beta(
    sym_prices: pd.DataFrame,
    spy_returns: pd.Series,
    ref_date: pd.Timestamp,
    window: int = _BETA_WINDOW,
) -> float | None:
    """Compute rolling beta (stock vs SPY) over a window of trading days.

    PIT-safe: only uses data up to and including ``ref_date``.

    Beta = Cov(stock_returns, spy_returns) / Var(spy_returns)
    """
    # Get stock prices up to ref_date
    hist = sym_prices[sym_prices.index <= ref_date].tail(window + 1)
    if len(hist) < 2:
        return None

    stock_returns = hist["close"].pct_change().dropna()
    if len(stock_returns) < 2:
        return None

    # Align with SPY returns
    spy_window = spy_returns[spy_returns.index <= ref_date].tail(len(stock_returns))
    if len(spy_window) < 2:
        return None

    # Align indices
    common = stock_returns.index.intersection(spy_window.index)
    if len(common) < 2:
        return None

    x = spy_window[common].values
    y = stock_returns[common].values

    # Beta = Cov(x,y) / Var(x)
    cov = np.cov(x, y)[0, 1]
    var = np.var(x)
    if var == 0:
        return None

    return float(cov / var)


def _batch_update_market_ratios(
    engine: Any,
    rows: list[dict[str, Any]],
) -> None:
    """Batch UPDATE stock_fundamentals_daily with market ratio columns."""
    if not rows:
        return

    # Determine which columns to update
    all_keys: set[str] = set()
    for row in rows:
        all_keys.update(k for k in row if k != "id")
    if not all_keys:
        return

    set_clause = ", ".join(f"{col} = :new_{col}" for col in sorted(all_keys))
    sql = f"UPDATE stock_fundamentals_daily SET {set_clause} WHERE id = :row_id"

    with engine.begin() as conn:
        for row in rows:
            params: dict[str, Any] = {"row_id": row["id"]}
            for col in all_keys:
                val = row.get(col)
                # MySQL rejects NaN/Inf — replace with NULL
                if val is not None and isinstance(val, float) and not np.isfinite(val):
                    val = None
                params[f"new_{col}"] = val
            conn.execute(_sa_text(sql), params)
