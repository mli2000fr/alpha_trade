"""E4-B0 — vérif couverture récente stock_earnings_calendar."""
from __future__ import annotations

from sqlalchemy import text

from database.connection import get_sqlalchemy_engine


def main() -> None:
    eng = get_sqlalchemy_engine()
    with eng.connect() as c:
        r = c.execute(text(
            "SELECT YEAR(earnings_date) y, COUNT(*) n FROM stock_earnings_calendar GROUP BY y ORDER BY y"
        )).fetchall()
        print("par année:", [tuple(x) for x in r])
        r = c.execute(text(
            "SELECT symbol, COUNT(*) n, MIN(earnings_date) mn, MAX(earnings_date) mx "
            "FROM stock_earnings_calendar WHERE symbol IN ('AAPL','MSFT','AMD','TSLA','JPM') GROUP BY symbol"
        )).fetchall()
        for row in r:
            print("sym", tuple(row))
        # date la plus récente de AAPL
        r = c.execute(text(
            "SELECT earnings_date, eps_estimate, eps_actual, revenue_estimate, revenue_actual, fiscal_period "
            "FROM stock_earnings_calendar WHERE symbol='AAPL' ORDER BY earnings_date DESC LIMIT 5"
        )).fetchall()
        print("AAPL 5 plus récentes:", [tuple(x) for x in r])
        # provenance : y a-t-il un champ source? non. Vérifions la densité 2025
        r = c.execute(text(
            "SELECT COUNT(*) n, COUNT(DISTINCT symbol) ns FROM stock_earnings_calendar WHERE earnings_date>='2025-01-01'"
        )).fetchall()
        print("2025+: n, sym =", tuple(r[0]))


if __name__ == "__main__":
    main()
