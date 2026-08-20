"""Explore le schéma réel des tables de scores (stock_scores / stock_scores_history) + couverture."""
from __future__ import annotations

from sqlalchemy import text

from database.connection import get_sqlalchemy_engine


def main() -> None:
    eng = get_sqlalchemy_engine()
    with eng.connect() as c:
        # liste des tables candidates
        tables = [r[0] for r in c.execute(text(
            "SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA='alpha_trade' "
            "AND (TABLE_NAME LIKE 'stock_scores%' OR TABLE_NAME LIKE '%score%') ORDER BY TABLE_NAME"
        )).fetchall()]
        print("=== tables candidates ===")
        for t in tables:
            print(" ", t)

        for tbl in ["stock_scores", "stock_scores_history"]:
            cols = c.execute(text(
                "SELECT COLUMN_NAME, DATA_TYPE FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA='alpha_trade' AND TABLE_NAME=:t ORDER BY ORDINAL_POSITION"
            ), {"t": tbl}).fetchall()
            print(f"\n=== {tbl} ===")
            for r in cols:
                print(f"  {r[0]} ({r[1]})")
            if not cols:
                continue
            cnt = c.execute(text(f"SELECT COUNT(*) FROM `{tbl}`")).scalar()
            print(f"  -> {cnt:,} lignes")
            # date col candidates
            date_cols = [r[0] for r in cols if "date" in r[0].lower() or "updated" in r[0].lower() or "scan" in r[0].lower()]
            for dc in date_cols:
                try:
                    dmin, dmax = c.execute(text(f"SELECT MIN(`{dc}`), MAX(`{dc}`) FROM `{tbl}`")).fetchone()
                    print(f"  -> {dc}: {dmin} -> {dmax}")
                except Exception:
                    pass
            nsym = c.execute(text(f"SELECT COUNT(DISTINCT symbol) FROM `{tbl}`")).scalar()
            print(f"  -> {nsym} symboles distincts")


if __name__ == "__main__":
    main()
