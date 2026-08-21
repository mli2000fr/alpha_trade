"""Vérifie la progression du backfill H2 2023 par mois (global_rank_history)."""
import sys
sys.path.insert(0, "f:/projets")
from database.connection import get_sqlalchemy_engine
from sqlalchemy import text

eng = get_sqlalchemy_engine()
B = "model-factory-20260811223551-ef2cd0"

with eng.connect() as c:
    q = text(
        "SELECT DATE_FORMAT(date, '%Y-%m') AS m, COUNT(*) AS n, "
        "COUNT(DISTINCT symbol) AS nsym FROM global_rank_history "
        "WHERE batch_id = :b AND date BETWEEN '2023-07-01' AND '2024-12-31' "
        "GROUP BY DATE_FORMAT(date, '%Y-%m') ORDER BY m"
    )
    print("=== global_rank_history par mois (H2 2023 + H2 2024) ===")
    for r in c.execute(q, {"b": B}):
        print(f"  {r.m}: n={r.n} symbols={r.nsym}")
    q2 = text(
        "SELECT date, COUNT(*) AS n, COUNT(DISTINCT symbol) AS nsym "
        "FROM global_rank_history WHERE batch_id = :b "
        "AND date IN ('2023-12-18','2023-12-19','2023-12-20') GROUP BY date"
    )
    print("=== dates récentes backfill ===")
    for r in c.execute(q2, {"b": B}):
        print(f"  {r.date}: n={r.n} symbols={r.nsym}")
