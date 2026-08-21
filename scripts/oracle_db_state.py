"""État de la table global_oracle_labels (avant refactor oracle_top -> oracle_extreme)."""
from __future__ import annotations

from sqlalchemy import text

from database.connection import get_sqlalchemy_engine

eng = get_sqlalchemy_engine()
with eng.connect() as c:
    cnt = c.execute(text("SELECT COUNT(*) FROM global_oracle_labels")).scalar()
    print("global_oracle_labels rows:", cnt)
    cols = [r[0] for r in c.execute(text(
        "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA='alpha_trade' AND TABLE_NAME='global_oracle_labels'"
    )).fetchall()]
    print("cols:", cols)
    if cnt:
        rows = c.execute(text(
            "SELECT oracle_top10, oracle_bottom10, COUNT(*) FROM global_oracle_labels "
            "GROUP BY oracle_top10, oracle_bottom10"
        )).fetchall()
        print("cross-tab top/bottom:", rows)
        b = c.execute(text(
            "SELECT batch_id, COUNT(DISTINCT prediction_date), COUNT(DISTINCT symbol) "
            "FROM global_oracle_labels GROUP BY batch_id"
        )).fetchall()
        print("batch:", b)
