"""Analyse la couverture temporelle des prédictions B25 par année pour comprendre
pourquoi 2023/2024 échouent au gate (45% < 90%) alors que 2022/2025 passent."""
import sys
sys.path.insert(0, "f:/projets")
from database.connection import get_sqlalchemy_engine
from sqlalchemy import text

eng = get_sqlalchemy_engine()
B = "model-factory-20260811223551-ef2cd0"

# Nombre de jours couverts par symbole, par année (via une sous-requête simple)
print("=== jours couverts par an (moy/min/max par symbole) ===")
q = text("""
SELECT y, COUNT(*) AS nsym, ROUND(AVG(jours),1) AS avg_days,
       MIN(jours) AS min_days, MAX(jours) AS max_days
FROM (
  SELECT p.symbol, YEAR(p.prediction_date) AS y, COUNT(DISTINCT p.prediction_date) AS jours
  FROM model_predictions p
  JOIN model_training_run tr ON tr.run_id = p.run_id
  WHERE tr.batch_id = :b
  GROUP BY p.symbol, YEAR(p.prediction_date)
) t
GROUP BY y ORDER BY y
""")
with eng.connect() as c:
    for row in c.execute(q, {"b": B}):
        print(f"  {row.y}: symbols={row.nsym} avg_jours={row.avg_days} min={row.min_days} max={row.max_days}")

# Distribution mensuelle 2023 et 2024
for an in (2023, 2024):
    print(f"\n=== distributions mensuelles {an} ===")
    qm = text("""
    SELECT MONTH(p.prediction_date) AS m, COUNT(DISTINCT p.symbol) AS nsym,
           COUNT(*) AS n
    FROM model_predictions p
    JOIN model_training_run tr ON tr.run_id = p.run_id
    WHERE tr.batch_id = :b AND YEAR(p.prediction_date) = :an
    GROUP BY MONTH(p.prediction_date) ORDER BY m
    """)
    with eng.connect() as c:
        for row in c.execute(qm, {"b": B, "an": an}):
            print(f"  mois {row.m:02d}: lignes={row.n:6d} symbols={row.nsym}")

# Comparaison : MIN/MAX dates 2022 vs 2023 vs 2024
print("\n=== min/max par an ===")
q2 = text("""
SELECT YEAR(p.prediction_date) AS y, MIN(p.prediction_date) AS mn, MAX(p.prediction_date) AS mx
FROM model_predictions p
JOIN model_training_run tr ON tr.run_id = p.run_id
WHERE tr.batch_id = :b
GROUP BY YEAR(p.prediction_date) ORDER BY y
""")
with eng.connect() as c:
    for row in c.execute(q2, {"b": B}):
        print(f"  {row.y}: {row.mn} -> {row.mx}")
