import sys
sys.path.insert(0, "f:/projets")
from ihm.services.db import get_engine
from sqlalchemy import text

e = get_engine()
with e.connect() as conn:
    r = conn.execute(text("DELETE FROM model_predictions WHERE run_id IN ('lightgbm', 'catboost')"))
    conn.commit()
    print(f"Deleted {r.rowcount} rows with bad run_id")
    r = conn.execute(text("SELECT COUNT(*) FROM model_predictions"))
    print(f"Remaining: {r.scalar()}")
