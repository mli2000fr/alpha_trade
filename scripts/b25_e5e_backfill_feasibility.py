"""Vérifie la faisabilité du predict de rattrapage B25 pour H2 2023 / H2 2024.

Le batch B25 n'a de prédictions persistées que jusqu'à 2024-06-28.
Pour combler H2 2023 (2023-07-01 → 2023-12-31) et H2 2024 (2024-07-01 → 2024-12-31),
il faut vérifier que les features nécessaires au predict per_sector existent en base
sur ces fenêtres : OHLCV, scores, sentiment, fondamentaux.
"""
import sys
sys.path.insert(0, "f:/projets")
from database.connection import get_sqlalchemy_engine
from sqlalchemy import text

eng = get_sqlalchemy_engine()

# 1. Couverture OHLCV (stock_bars_daily) — déjà vérifiée, mais rappel pour H2
print("=== stock_bars_daily H2 2023 / H2 2024 ===")
q = text(
    "SELECT YEAR(date) AS y, MONTH(date) AS m, COUNT(*) AS n, COUNT(DISTINCT symbol) AS nsym "
    "FROM stock_bars_daily WHERE date BETWEEN '2023-07-01' AND '2024-12-31' "
    "GROUP BY YEAR(date), MONTH(date) HAVING m > 6 ORDER BY y, m"
)
with eng.connect() as c:
    for row in c.execute(q):
        print(f"  {row.y}-{row.m:02d}: rows={row.n} symbols={row.nsym}")

# 2. Tables de features candidates — regarder celles qui ont une colonne date
print("\n=== tables features (date range par table) ===")
tables = [
    "stock_scores", "stock_scores_all", "ticker_daily_sentiment_features",
    "sector_daily_sentiment_features", "tradable_universe_history",
]
for t in tables:
    try:
        cols = [r[0] for r in eng.connect().execute(text(f"SHOW COLUMNS FROM {t}"))]
        date_col = None
        for cand in ("date", "trade_date", "as_of_date", "snapshot_date", "score_date"):
            if cand in cols:
                date_col = cand
                break
        if date_col is None:
            print(f"  {t}: pas de colonne date (cols={cols[:8]}...)")
            continue
        q2 = text(
            f"SELECT MIN({date_col}) AS mn, MAX({date_col}) AS mx, COUNT(*) AS n "
            f"FROM {t} WHERE {date_col} BETWEEN '2023-07-01' AND '2024-12-31'"
        )
        r = eng.connect().execute(q2).mappings().first()
        print(f"  {t}: [{r.mn} → {r.mx}] n={r.n} (date_col={date_col})")
    except Exception as e:
        print(f"  {t}: ERR {str(e)[:80]}")
