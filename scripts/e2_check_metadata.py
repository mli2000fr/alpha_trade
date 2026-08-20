"""Vérifie la disponibilité PIT de secteur (stock_metadata) pour E2-D."""
from __future__ import annotations

from sqlalchemy import text

from database.connection import get_sqlalchemy_engine

eng = get_sqlalchemy_engine()
with eng.connect() as c:
    # stock_metadata
    try:
        cols = [r[0] for r in c.execute(text(
            "SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA='alpha_trade' "
            "AND TABLE_NAME='stock_metadata'"
        )).fetchall()]
        print("stock_metadata cols:", cols)
        n = c.execute(text("SELECT COUNT(*) FROM stock_metadata")).scalar()
        print("stock_metadata rows:", n)
        if n:
            s = c.execute(text(
                "SELECT provider_sector, COUNT(*) FROM stock_metadata GROUP BY provider_sector ORDER BY 2 DESC LIMIT 15"
            )).fetchall()
            print("sectors:", s)
    except Exception as e:
        print("stock_metadata err:", e)
