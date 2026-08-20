"""E4-B0 — vérif format symboles stock_earnings_calendar."""
from __future__ import annotations

from sqlalchemy import text

from database.connection import get_sqlalchemy_engine


def main() -> None:
    eng = get_sqlalchemy_engine()
    with eng.connect() as c:
        r = c.execute(text("SELECT DISTINCT symbol FROM stock_earnings_calendar WHERE symbol LIKE '%AAPL%' LIMIT 20")).fetchall()
        print("LIKE AAPL:", [x[0] for x in r])
        r = c.execute(text("SELECT DISTINCT symbol FROM stock_earnings_calendar ORDER BY symbol LIMIT 25")).fetchall()
        print("premiers symboles:", [x[0] for x in r])
        r = c.execute(text(
            "SELECT symbol, earnings_date, eps_estimate, eps_actual, fiscal_period "
            "FROM stock_earnings_calendar WHERE earnings_date>='2025-06-01' ORDER BY earnings_date DESC LIMIT 8"
        )).fetchall()
        print("2025+ récent:", [tuple(x) for x in r])


if __name__ == "__main__":
    main()
