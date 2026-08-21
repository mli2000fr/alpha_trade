"""Vérifie la couverture de global_oracle_labels H2 2023/2024 (après backfill)."""
import sys
sys.path.insert(0, "f:/projets")
from database.connection import get_sqlalchemy_engine
from sqlalchemy import text

e = get_sqlalchemy_engine()
B = "model-factory-20260811223551-ef2cd0"
q = text(
    "SELECT DATE_FORMAT(prediction_date, '%Y-%m') AS m, COUNT(*) AS n, "
    "COUNT(DISTINCT symbol) AS nsym FROM global_oracle_labels "
    "WHERE batch_id = :b AND horizon = 20 "
    "AND prediction_date BETWEEN '2023-07-01' AND '2024-12-31' "
    "GROUP BY DATE_FORMAT(prediction_date, '%Y-%m') ORDER BY m"
)
with e.connect() as c:
    rows = c.execute(q, {"b": B}).fetchall()
print("global_oracle_labels H2 2023/2024 par mois:")
for r in rows:
    print(f"  {r.m}: n={r.n} symbols={r.nsym}")
