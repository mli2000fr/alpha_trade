"""Vérifie le backfill oracle_extreme10 après migration 0065."""
from __future__ import annotations

from sqlalchemy import text

from database.connection import get_sqlalchemy_engine

eng = get_sqlalchemy_engine()
with eng.connect() as c:
    rows = c.execute(text(
        "SELECT oracle_extreme10, COUNT(*) FROM global_oracle_labels GROUP BY oracle_extreme10 ORDER BY 1"
    )).fetchall()
    print("oracle_extreme10 cross-tab:")
    for r in rows:
        print(f"  {r[0]}: {r[1]:,}")
    tot = sum(r[1] for r in rows)
    pct = {r[0]: 100.0 * r[1] / tot for r in rows}
    print(f"  total: {tot:,} | extreme=1 -> {pct.get(1, 0.0):.1f}% | extreme=0 -> {pct.get(0, 0.0):.1f}%")
    # sanity: extreme10 cohérent avec pct_rank (top>=0.90 ou bottom<=0.10)
    bad = c.execute(text(
        "SELECT COUNT(*) FROM global_oracle_labels "
        "WHERE oracle_extreme10 = 1 AND oracle_pct_rank > 0.10 AND oracle_pct_rank < 0.90"
    )).scalar()
    top = c.execute(text(
        "SELECT COUNT(*) FROM global_oracle_labels WHERE oracle_extreme10 = 1 AND oracle_pct_rank >= 0.90"
    )).scalar()
    bot = c.execute(text(
        "SELECT COUNT(*) FROM global_oracle_labels WHERE oracle_extreme10 = 1 AND oracle_pct_rank <= 0.10"
    )).scalar()
    print(f"  [sanity] extreme=1 hors zone centrale (0.10<pct<0.90) : {bad:,} (attendu 0)")
    print(f"  [sanity] extreme=1 & pct>=0.90 (TOP)   : {top:,}")
    print(f"  [sanity] extreme=1 & pct<=0.10 (BOTTOM): {bot:,}")
