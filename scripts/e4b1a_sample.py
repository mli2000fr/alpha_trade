"""E4-B1a — échantillon pour déterminer la provenance SEC vs Finnhub."""
from __future__ import annotations

from sqlalchemy import text

from database.connection import get_sqlalchemy_engine


def main() -> None:
    eng = get_sqlalchemy_engine()
    with eng.connect() as c:
        # formats de fiscal_period distincts
        r = c.execute(text(
            "SELECT fiscal_period, COUNT(*) n FROM stock_earnings_calendar GROUP BY fiscal_period "
            "ORDER BY n DESC LIMIT 25"
        )).fetchall()
        print("fiscal_period les plus fréquents:")
        for row in r:
            print("   ", tuple(row))
        # échantillon par années récentes
        r = c.execute(text(
            "SELECT symbol, earnings_date, eps_estimate, eps_actual, revenue_estimate, revenue_actual, fiscal_period "
            "FROM stock_earnings_calendar WHERE earnings_date BETWEEN '2025-01-01' AND '2025-06-30' "
            "AND symbol IN ('AAPL','MSFT','TSLA','AMD','JPM','NVDA') ORDER BY earnings_date LIMIT 20"
        )).fetchall()
        print("échantillon H1 2025 (méga caps — normalement Finnhub):")
        for row in r:
            print("   ", tuple(row))
        r = c.execute(text(
            "SELECT symbol, earnings_date, eps_estimate, eps_actual, revenue_estimate, revenue_actual, fiscal_period "
            "FROM stock_earnings_calendar WHERE symbol='TSCO' ORDER BY earnings_date LIMIT 12"
        )).fetchall()
        print("TSCO (dans univers 400):")
        for row in r:
            print("   ", tuple(row))


if __name__ == "__main__":
    main()
