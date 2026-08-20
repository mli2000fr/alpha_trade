"""Compare la couverture short_score sur toutes les fenêtres E5-D (marchées + manquantes)."""
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

windows = [
    ("2022", "2022-01-03", "2022-12-30"),
    ("2023 H1", "2023-01-03", "2023-06-28"),
    ("2023 H2", "2023-07-01", "2023-12-31"),
    ("2024 H1", "2024-01-04", "2024-06-28"),
    ("2024 H2", "2024-07-01", "2024-12-31"),
    ("2025", "2025-01-01", "2025-12-31"),
    ("2026 H1", "2026-01-02", "2026-05-31"),
]

print("=== short_score coverage par fenêtre (sur 400 tickets) ===")
q = text(
    f"SELECT COUNT(DISTINCT symbol) nsym, COUNT(*) n_nonnull "
    f"FROM stock_scores_history WHERE symbol IN ({placeholders}) "
    f"AND snapshot_date BETWEEN :d0 AND :d1 "
    f"AND short_score IS NOT NULL AND short_score != 0"
)
for lbl, d0, d1 in windows:
    with eng.connect() as c:
        r = c.execute(q, {**params, "d0": d0, "d1": d1}).mappings().first()
    pct = 100.0 * r.nsym / len(tickets)
    print(f"  {lbl:8}: {r.nsym:3d}/{len(tickets)} tickets ({pct:4.1f}%) n_nonnull={r.n_nonnull:6d}")

# Aussi : couverture short_score dans stock_scores_history pour les 400 tickets, sans filtre date (max)
print("\n=== max date short_score par fenêtre ===")
q2 = text(
    f"SELECT MAX(snapshot_date) mx FROM stock_scores_history WHERE symbol IN ({placeholders}) AND short_score IS NOT NULL AND short_score != 0"
)
with eng.connect() as c:
    r = c.execute(q2, params).mappings().first()
    print(f"  max snapshot_date avec short_score non-nul: {r.mx}")
