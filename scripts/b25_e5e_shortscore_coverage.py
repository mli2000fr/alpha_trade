"""Vérifie short_score (feature ranking B25) dans stock_scores_history sur H2 2023/2024."""
import sys
sys.path.insert(0, "f:/projets")
from database.connection import get_sqlalchemy_engine
from sqlalchemy import text

eng = get_sqlalchemy_engine()

with eng.connect() as c:
    cols = [r[0] for r in c.execute(text("SHOW COLUMNS FROM stock_scores_history"))]
    print("stock_scores_history cols (short_score present?):", "short_score" in cols)
    if "short_score" not in cols:
        sys.exit(0)
    q = text(
        "SELECT COUNT(DISTINCT symbol) nsym, COUNT(*) n_nonnull "
        "FROM stock_scores_history WHERE snapshot_date BETWEEN :d0 AND :d1 "
        "AND short_score IS NOT NULL AND short_score != 0"
    )
    for lbl, d0, d1 in (("H2 2023", "2023-07-01", "2023-12-31"), ("H2 2024", "2024-07-01", "2024-12-31")):
        r = c.execute(q, {"d0": d0, "d1": d1}).mappings().first()
        print(f"  {lbl}: {r.nsym} symboles avec short_score non-nul, n={r.n_nonnull}")

# aussi regarder quelle table fournit short_score au runtime (peut-être stock_scores)
for t in ("stock_scores",):
    with eng.connect() as c:
        cols = [r[0] for r in c.execute(text(f"SHOW COLUMNS FROM {t}"))]
        print(f"{t}: short_score present?", "short_score" in cols)
