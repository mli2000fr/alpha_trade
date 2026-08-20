from database.connection import get_sqlalchemy_engine
from sqlalchemy import text

eng = get_sqlalchemy_engine()
with eng.connect() as c:
    for prefix in ["%_20260818_1619%", "%_20260818_1626%", "%_20260818_1605%"]:
        n = c.execute(text("SELECT COUNT(*) FROM model_predictions WHERE run_id LIKE :p"), {"p": prefix}).fetchone()[0]
        print("preds run_id LIKE", prefix, ":", n)
    recent = c.execute(
        text("SELECT symbol, prediction_date, selected_model, run_id, created_at FROM model_predictions ORDER BY created_at DESC LIMIT 5")
    ).fetchall()
    print("\n5 prédictions les plus récentes (toutes sources):")
    for r in recent:
        print(" ", r)
