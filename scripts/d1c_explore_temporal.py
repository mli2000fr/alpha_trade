"""Explore : étendue temporelle des prédictions Oracle TOP + couverture stock_scores_history par période 2026."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from sqlalchemy import text

from database.connection import get_sqlalchemy_engine

ROOT = Path(__file__).resolve().parents[1]
TOP_PQ = ROOT / "artifacts" / "models" / "oracle" / "oracle-wf-20260818021140" / "oos_predictions.parquet"


def main() -> None:
    top = pd.read_parquet(TOP_PQ)
    top["date"] = pd.to_datetime(top["date"])
    top["year"] = top["date"].dt.year
    top["month"] = top["date"].dt.month
    print(f"Oracle TOP: {len(top):,} lignes | {top['date'].min().date()} -> {top['date'].max().date()}")
    print(f"future_return non-null: {top['future_return'].notna().mean()*100:.1f}%")
    print("\n=== par mois 2026 (N, future_return non-null) ===")
    m26 = top[top["year"] == 2026]
    for m, g in m26.groupby("month"):
        print(f"  2026-{m:02d}: N={len(g):,}  fut_ret_nonnull={g['future_return'].notna().mean()*100:.1f}%")
    # N par an
    print("\n=== N par an ===")
    for y, g in top.groupby("year"):
        print(f"  {y}: {len(g):,}  fut_ret_nonnull={g['future_return'].notna().mean()*100:.1f}%")

    # Couverture stock_scores_history en 2026H1 / 2026H2 (avant forward-fill)
    eng = get_sqlalchemy_engine()
    with eng.connect() as c:
        q = text(
            "SELECT YEAR(snapshot_date), QUARTER(snapshot_date), COUNT(*), COUNT(DISTINCT symbol), "
            "SUM(short_score IS NOT NULL), SUM(total_score IS NOT NULL) "
            "FROM stock_scores_history WHERE snapshot_date >= '2026-01-01' "
            "GROUP BY YEAR(snapshot_date), QUARTER(snapshot_date) ORDER BY 1,2"
        )
        rows = c.execute(q).fetchall()
    print("\n=== stock_scores_history 2026 par trimestre (brut) ===")
    for r in rows:
        print(f"  {r[0]}-Q{r[1]}: N={r[2]:,} sym={r[3]} short={r[4]:,} total={r[5]:,}")
    # dernières dates
    with eng.connect() as c:
        d = c.execute(text("SELECT MAX(snapshot_date), COUNT(DISTINCT snapshot_date) FROM stock_scores_history WHERE snapshot_date >= '2026-01-01'")).fetchone()
    print(f"\n  Max snapshot 2026: {d[0]} | nb dates distinctes 2026: {d[1]}")


if __name__ == "__main__":
    main()
