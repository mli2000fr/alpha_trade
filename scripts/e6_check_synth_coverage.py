"""Vérifie la couverture du run synthétique model_predictions H2 2023/2024."""
import sys
sys.path.insert(0, "f:/projets")
from database.connection import get_sqlalchemy_engine
from sqlalchemy import text

e = get_sqlalchemy_engine()
B = "model-factory-20260811223551-ef2cd0"
RID = f"{B}_globalrank_synth"
q = text(
    "SELECT DATE_FORMAT(prediction_date, '%Y-%m') AS m, COUNT(*) AS n, "
    "COUNT(DISTINCT symbol) AS nsym FROM model_predictions "
    "WHERE run_id = :r AND prediction_date BETWEEN '2023-07-01' AND '2024-12-31' "
    "GROUP BY DATE_FORMAT(prediction_date, '%Y-%m') ORDER BY m"
)
with e.connect() as c:
    rows = c.execute(q, {"r": RID}).fetchall()
print(f"model_predictions run synthétique ({RID}) H2 par mois:")
for r in rows:
    print(f"  {r.m}: n={r.n} symbols={r.nsym}")
if not rows:
    print("  (aucune ligne — run synthétique absent pour H2)")
