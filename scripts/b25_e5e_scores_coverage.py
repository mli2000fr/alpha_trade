"""Check stock_scores_history + tradable_universe_history coverage H2 2023/2024."""
import sys
sys.path.insert(0, "f:/projets")
from database.connection import get_sqlalchemy_engine
from sqlalchemy import text

eng = get_sqlalchemy_engine()

for t in ("stock_scores_history", "tradable_universe_history"):
    try:
        with eng.connect() as c:
            cols = [r[0] for r in c.execute(text(f"SHOW COLUMNS FROM {t}"))]
            date_col = next((x for x in ("trade_date", "date", "as_of_date", "snapshot_date") if x in cols), None)
            if date_col is None:
                print(f"{t}: no date col ({cols[:10]})")
                continue
            q = text(
                f"SELECT MIN({date_col}) mn, MAX({date_col}) mx, COUNT(*) n, "
                f"COUNT(DISTINCT symbol) nsym FROM {t} "
                f"WHERE {date_col} BETWEEN '2023-07-01' AND '2024-12-31'"
            )
            r = c.execute(q).mappings().first()
            print(f"{t}: [{r.mn} -> {r.mx}] n={r.n} symbols={r.nsym} (date_col={date_col})")
    except Exception as e:
        print(f"{t}: ERR {str(e)[:100]}")
