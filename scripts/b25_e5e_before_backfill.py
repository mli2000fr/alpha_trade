"""Vérifie l'état actuel des prédictions/rangs B25 sur H2 2023 / H2 2024 avant backfill."""
import sys
sys.path.insert(0, "f:/projets")
from database.connection import get_sqlalchemy_engine
from sqlalchemy import text

eng = get_sqlalchemy_engine()
B = "model-factory-20260811223551-ef2cd0"

# Prédictions B25 par semestre
print("=== model_predictions B25 par semestre ===")
q = text("""
SELECT YEAR(p.prediction_date) AS y, QUARTER(p.prediction_date) AS q, COUNT(*) AS n,
       COUNT(DISTINCT p.symbol) AS nsym, COUNT(DISTINCT p.run_id) AS nrun
FROM model_predictions p JOIN model_training_run tr ON tr.run_id = p.run_id
WHERE tr.batch_id = :b AND p.prediction_date BETWEEN '2023-01-01' AND '2024-12-31'
GROUP BY y, q ORDER BY y, q
""")
with eng.connect() as c:
    for row in c.execute(q, {"b": B}):
        print(f"  {row.y} Q{row.q}: n={row.n} symbols={row.nsym} runs={row.nrun}")

# global_rank_history par semestre
print("\n=== global_rank_history B25 par semestre ===")
q2 = text("""
SELECT YEAR(date) AS y, QUARTER(date) AS q, COUNT(*) AS n, COUNT(DISTINCT symbol) AS nsym
FROM global_rank_history WHERE batch_id = :b AND date BETWEEN '2023-01-01' AND '2024-12-31'
GROUP BY y, q ORDER BY y, q
""")
with eng.connect() as c:
    for row in c.execute(q2, {"b": B}):
        print(f"  {row.y} Q{row.q}: n={row.n} symbols={row.nsym}")
