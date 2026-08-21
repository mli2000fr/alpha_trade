"""Vérifie la couverture OHLCV MySQL 2022-2024 (stock_bars_daily) et la couverture
des prédictions B25 par année, pour valider le rejeu historique E5-D."""
import sys
sys.path.insert(0, "f:/projets")
from database.connection import get_sqlalchemy_engine
from sqlalchemy import text

eng = get_sqlalchemy_engine()

print("=== stock_bars_daily 2022-2024 (couverture brute) ===")
q = text(
    "SELECT YEAR(date) AS y, COUNT(*) AS n, COUNT(DISTINCT symbol) AS nsym "
    "FROM stock_bars_daily WHERE date BETWEEN '2022-01-01' AND '2024-12-31' "
    "GROUP BY YEAR(date) ORDER BY y"
)
with eng.connect() as c:
    for row in c.execute(q):
        print(f"  {row.y}: rows={row.n} symbols={row.nsym}")

# Couverture pour les 400 symboles du ticket_recherche
import os
tickets = []
tp = "config/ticket_recherche.txt"
if os.path.exists(tp):
    raw = open(tp, encoding="utf-8").read()
    for tok in raw.replace(",", " ").split():
        tok = tok.strip().upper()
        if tok and not tok.startswith("#"):
            tickets.append(tok)
tickets = sorted(set(tickets))
print(f"\n=== tickets (n={len(tickets)}) ===")
placeholders = ",".join(f":s{i}" for i in range(len(tickets)))
params = {f"s{i}": s for i, s in enumerate(tickets)}
q2 = text(
    f"SELECT YEAR(date) AS y, COUNT(*) AS n, COUNT(DISTINCT symbol) AS nsym "
    f"FROM stock_bars_daily WHERE symbol IN ({placeholders}) "
    f"AND date BETWEEN '2022-01-01' AND '2024-12-31' "
    f"GROUP BY YEAR(date) ORDER BY y"
)
with eng.connect() as c:
    for row in c.execute(q2, params):
        print(f"  {row.y}: rows={row.n} symbols={row.nsym}")

# Prédictions B25 par année (rappel)
print("\n=== predictions B25 par annee (rappel) ===")
q3 = text(
    "SELECT YEAR(p.prediction_date) AS y, COUNT(*) AS n, COUNT(DISTINCT p.symbol) AS nsym "
    "FROM model_predictions p JOIN model_training_run tr ON tr.run_id = p.run_id "
    "WHERE tr.batch_id = :b GROUP BY YEAR(p.prediction_date) ORDER BY y"
)
with eng.connect() as c:
    for row in c.execute(q3, {"b": "model-factory-20260811223551-ef2cd0"}):
        print(f"  {row.y}: rows={row.n} symbols={row.nsym}")
