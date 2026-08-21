"""État de alembic_version + tables existantes clés."""
from __future__ import annotations

from sqlalchemy import text

from database.connection import get_sqlalchemy_engine

eng = get_sqlalchemy_engine()
with eng.connect() as c:
    try:
        v = c.execute(text("SELECT version_num FROM alembic_version")).fetchall()
        print("alembic_version:", [r[0] for r in v])
    except Exception as e:
        print("alembic_version erreur:", e)
    # colonnes de global_oracle_labels
    cols = [r[0] for r in c.execute(text(
        "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA='alpha_trade' AND TABLE_NAME='global_oracle_labels'"
    )).fetchall()]
    print("global_oracle_labels cols:", cols)
    # vérifier si la colonne oracle_extreme10 existe déjà
    print("has oracle_extreme10:", "oracle_extreme10" in cols)
    print("has oracle_top10:", "oracle_top10" in cols)
    print("has oracle_bottom10:", "oracle_bottom10" in cols)
    # tables de migrations déjà appliquées (repères)
    for t in ["execution_runs", "model_training_batch", "global_rank_history"]:
        try:
            has = c.execute(text(
                "SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA='alpha_trade' AND TABLE_NAME=:t"
            ), {"t": t}).scalar()
            print(f"table {t}: {'OK' if has else 'ABSENTE'}")
        except Exception as e:
            print(f"table {t}: erreur {e}")
