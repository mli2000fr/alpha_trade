"""E4-B0 — étape 1 : inventaire brut des tables de la base alpha_trade."""
from __future__ import annotations

from sqlalchemy import text

from database.connection import get_sqlalchemy_engine


def main() -> None:
    eng = get_sqlalchemy_engine()
    with eng.connect() as c:
        # toutes les tables non-vues
        tables = c.execute(text(
            "SELECT TABLE_NAME, TABLE_ROWS, TABLE_COLLATION "
            "FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_TYPE='BASE TABLE' "
            "ORDER BY TABLE_NAME"
        )).fetchall()
    print(f"{'table':<50} {'rows (approx)':>14}  collation")
    print("-" * 90)
    for name, rows, coll in tables:
        print(f"{name:<50} {int(rows or 0):>14,}  {coll}")


if __name__ == "__main__":
    main()
