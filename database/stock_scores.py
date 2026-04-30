from __future__ import annotations

from sqlalchemy import Boolean, Column, Float, Integer, MetaData, String, Table, select

from database.connection import get_sqlalchemy_engine


def get_stock_scores_table(*, engine=None) -> Table:
    resolved_engine = engine or get_sqlalchemy_engine()
    return Table(
        "stock_scores",
        MetaData(),
        Column("symbol", String(20), primary_key=True),
        Column("is_candidate", Boolean),
        Column("total_score", Float),
        Column("final_score_sentiment", Float),
        Column("anomaly_count", Integer),
        Column("missing_days_count", Integer),
        autoload_with=resolved_engine,
    )


def list_candidate_symbols(
    *,
    engine=None,
    stock_scores: Table | None = None,
    limit: int | None = None,
) -> list[str]:
    if limit is not None and limit < 1:
        raise ValueError("limit doit être supérieur ou égal à 1.")

    resolved_engine = engine or get_sqlalchemy_engine()
    resolved_table = stock_scores if stock_scores is not None else get_stock_scores_table(engine=resolved_engine)
    if "is_candidate" not in resolved_table.c:
        raise RuntimeError("La colonne stock_scores.is_candidate est absente du schéma SQL courant.")

    stmt = select(resolved_table.c.symbol).where(resolved_table.c.is_candidate == 1)
    if "total_score" in resolved_table.c:
        stmt = stmt.order_by(resolved_table.c.total_score.desc())
    stmt = stmt.order_by(resolved_table.c.symbol.asc())
    if limit is not None:
        stmt = stmt.limit(limit)

    with resolved_engine.connect() as conn:
        rows = conn.execute(stmt).scalars().all()
    return [str(symbol).strip().upper() for symbol in rows if str(symbol).strip()]


