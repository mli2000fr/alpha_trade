"""Vérifie la couverture effective des prédictions B25 sur les fenêtres H1 2023/2024
pour rejouer E5-D sur H1 (seule partie couverte par le batch)."""
import sys
sys.path.insert(0, "f:/projets")
from database.connection import get_sqlalchemy_engine
from sqlalchemy import text

eng = get_sqlalchemy_engine()
B = "model-factory-20260811223551-ef2cd0"

# Charger les 400 tickets
tickets = []
raw = open("config/ticket_recherche.txt", encoding="utf-8").read()
for tok in raw.replace(",", " ").split():
    tok = tok.strip().upper()
    if tok and not tok.startswith("#"):
        tickets.append(tok)
tickets = sorted(set(tickets))
placeholders = ",".join(f":s{i}" for i in range(len(tickets)))
params = {f"s{i}": s for i, s in enumerate(tickets)}
params["b"] = B

# Fenêtres candidates
windows = [
    ("2022 FULL", "2022-01-03", "2022-12-30"),
    ("2023 H1", "2023-01-03", "2023-06-28"),
    ("2024 H1", "2024-01-04", "2024-06-28"),
    ("2025 FULL", "2025-01-01", "2025-12-31"),
    ("2026 H1", "2026-01-02", "2026-05-31"),
]

print("=== couverture prédictions B25 par fenêtre (symboles tickets) ===")
for label, d0, d1 in windows:
    q = text(f"""
    SELECT COUNT(DISTINCT p.symbol) AS nsym
    FROM model_predictions p
    JOIN model_training_run tr ON tr.run_id = p.run_id
    WHERE tr.batch_id = :b AND p.symbol IN ({placeholders})
      AND p.prediction_date BETWEEN :d0 AND :d1
    """)
    p2 = dict(params, d0=d0, d1=d1)
    with eng.connect() as c:
        r = c.execute(q, p2).mappings().first()
    pct = 100.0 * r["nsym"] / len(tickets) if tickets else 0
    print(f"  {label:10} [{d0} -> {d1}] : {r['nsym']}/{len(tickets)} symboles = {pct:.1f}%")

# Aussi vérifier combien de jours par symbole sur H1 (pour confirmer complétude)
print("\n=== jours par symbole sur H1 2023 / H1 2024 (avg sur tickets) ===")
for label, d0, d1 in windows[1:3]:
    q2 = text(f"""
    SELECT ROUND(AVG(j),1) AS avg_j, MIN(j) AS min_j, MAX(j) AS max_j
    FROM (
      SELECT p.symbol, COUNT(DISTINCT p.prediction_date) AS j
      FROM model_predictions p
      JOIN model_training_run tr ON tr.run_id = p.run_id
      WHERE tr.batch_id = :b AND p.symbol IN ({placeholders})
        AND p.prediction_date BETWEEN :d0 AND :d1
      GROUP BY p.symbol
    ) t
    """)
    p2 = dict(params, d0=d0, d1=d1)
    with eng.connect() as c:
        r = c.execute(q2, p2).mappings().first()
    print(f"  {label}: avg_jours={r.avg_j} min={r.min_j} max={r.max_j}")
