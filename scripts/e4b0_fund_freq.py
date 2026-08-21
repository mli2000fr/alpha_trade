"""E4-B0 — vérif fréquence réelle stock_fundamentals_daily."""
from __future__ import annotations

from sqlalchemy import text

from database.connection import get_sqlalchemy_engine


def main() -> None:
    eng = get_sqlalchemy_engine()
    with eng.connect() as c:
        r = c.execute(text(
            "SELECT symbol, COUNT(*) n, MIN(trade_date) mn, MAX(trade_date) mx "
            "FROM stock_fundamentals_daily WHERE symbol IN ('AAPL','MSFT','AMD','TSLA','JPM') GROUP BY symbol"
        )).fetchall()
        for row in r:
            print("sym", tuple(row))
        r = c.execute(text(
            "SELECT DATE_FORMAT(trade_date, '%Y-%m') m, COUNT(*) n "
            "FROM stock_fundamentals_daily WHERE symbol='AAPL' AND trade_date>='2024-01-01' "
            "GROUP BY m ORDER BY m LIMIT 14"
        )).fetchall()
        print("AAPL 2024 mensuel:", [tuple(x) for x in r])
        r = c.execute(text(
            "SELECT COUNT(*) n, COUNT(pe_ratio) pe, COUNT(roe) roe, COUNT(market_cap) mc, "
            "COUNT(revenue_growth_yoy) rg, COUNT(eps_growth_yoy) eg "
            "FROM stock_fundamentals_daily WHERE trade_date>='2024-01-01' "
            "AND symbol IN ('AAPL','MSFT','AMD','TSLA','JPM')"
        )).fetchone()
        print("2024 sample non-null:", tuple(r))


if __name__ == "__main__":
    main()
