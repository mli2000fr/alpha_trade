"""Vérifie la couverture des features (scores + sentiment) pour les 400 tickets
sur H2 2023 / H2 2024 — point faible potentiel du backfill predict."""
import sys
sys.path.insert(0, "f:/projets")
from database.connection import get_sqlalchemy_engine
from sqlalchemy import text

eng = get_sqlalchemy_engine()

# 400 tickets
tickets = []
raw = open("config/ticket_recherche.txt", encoding="utf-8").read()
for tok in raw.replace(",", " ").split():
    tok = tok.strip().upper()
    if tok and not tok.startswith("#"):
        tickets.append(tok)
tickets = sorted(set(tickets))
placeholders = ",".join(f":s{i}" for i in range(len(tickets)))
params = {f"s{i}": s for i, s in enumerate(tickets)}

# stock_scores_history par symbole ticket sur la fenêtre
for t, dcol in (("stock_scores_history", "snapshot_date"), ("ticker_daily_sentiment_features", "trade_date")):
    try:
        q = text(
            f"SELECT COUNT(DISTINCT symbol) nsym, COUNT(DISTINCT {dcol}) ndays "
            f"FROM {t} WHERE symbol IN ({placeholders}) "
            f"AND {dcol} BETWEEN '2023-07-01' AND '2024-12-31'"
        )
        with eng.connect() as c:
            r = c.execute(q, params).mappings().first()
        print(f"{t}: {r.nsym}/{len(tickets)} tickets couverts, {r.ndays} jours")
        # par semestre
        for lbl, d0, d1 in (("H2 2023", "2023-07-01", "2023-12-31"), ("H2 2024", "2024-07-01", "2024-12-31")):
            q2 = text(
                f"SELECT COUNT(DISTINCT symbol) nsym, COUNT(DISTINCT {dcol}) ndays "
                f"FROM {t} WHERE symbol IN ({placeholders}) "
                f"AND {dcol} BETWEEN :d0 AND :d1"
            )
            with eng.connect() as c:
                r2 = c.execute(q2, {**params, "d0": d0, "d1": d1}).mappings().first()
            print(f"   {lbl}: {r2.nsym} tickets, {r2.ndays} jours")
    except Exception as e:
        print(f"{t}: ERR {str(e)[:100]}")
