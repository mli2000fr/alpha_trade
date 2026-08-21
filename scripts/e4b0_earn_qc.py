"""E4-B0 — contrôle qualité stock_earnings_calendar (surprise calculable)."""
from __future__ import annotations

from sqlalchemy import text

from database.connection import get_sqlalchemy_engine


def main() -> None:
    eng = get_sqlalchemy_engine()
    with eng.connect() as c:
        # échantillon AAPL/MSFT récent
        r = c.execute(text(
            "SELECT symbol, earnings_date, eps_estimate, eps_actual, revenue_estimate, revenue_actual, fiscal_period "
            "FROM stock_earnings_calendar WHERE symbol IN ('AAPL','MSFT') AND earnings_date>='2025-01-01' "
            "ORDER BY symbol, earnings_date LIMIT 12"
        )).fetchall()
        for row in r:
            print(tuple(row))
        print("---")
        # combien ont estimate+actual cohérents (surprise calculable)
        r = c.execute(text(
            "SELECT COUNT(*) n, "
            "SUM(CASE WHEN eps_estimate IS NOT NULL AND eps_actual IS NOT NULL AND eps_estimate<>0 THEN 1 ELSE 0 END) surp_eps, "
            "SUM(CASE WHEN revenue_estimate IS NOT NULL AND revenue_actual IS NOT NULL AND revenue_estimate<>0 THEN 1 ELSE 0 END) surp_rev "
            "FROM stock_earnings_calendar WHERE earnings_date>='2020-01-01'"
        )).fetchone()
        print("2020+ : total, surprise_eps_calc, surprise_rev_calc =", tuple(r))
        # distribution des eps_estimate signes (0 / négatif)
        r = c.execute(text(
            "SELECT COUNT(*) n, SUM(eps_estimate=0) zero, SUM(eps_estimate<0) neg FROM stock_earnings_calendar WHERE earnings_date>='2020-01-01'"
        )).fetchone()
        print("2020+ estimate : n, zero, neg =", tuple(r))


if __name__ == "__main__":
    main()
