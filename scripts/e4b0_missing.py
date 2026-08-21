"""E4-B0 — symboles de l'univers 400 absents de chaque table candidate."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import text

from database.connection import get_sqlalchemy_engine

TICKET = Path("config/ticket_recherche.txt")

TABLES = [
    ("stock_earnings_calendar", "symbol"),
    ("stock_fundamentals_daily", "symbol"),
    ("ticker_daily_sentiment_features", "symbol"),
    ("global_rank_history", "symbol"),
]


def main() -> None:
    syms = sorted({s.strip().upper() for s in TICKET.read_text(encoding="utf-8").split(",") if s.strip()})
    print(f"univers 400: {len(syms)}")
    eng = get_sqlalchemy_engine()
    with eng.connect() as c:
        for table, col in TABLES:
            q = f"SELECT DISTINCT {col} FROM {table} WHERE {col} IN ({','.join([':s%d' % i for i in range(len(syms))])})"
            rows = c.execute(text(q), {f"s{i}": s for i, s in enumerate(syms)}).fetchall()
            found = {r[0] for r in rows}
            missing = sorted(set(syms) - found)
            print(f"{table}: présents={len(found)}/400, manquants={len(missing)} -> {missing[:15]}")


if __name__ == "__main__":
    main()
