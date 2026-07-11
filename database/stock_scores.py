from __future__ import annotations

import pandas as pd
from sqlalchemy import Column, Float, Integer, MetaData, String, Table, select

from database.connection import get_sqlalchemy_engine

SCORE_CONTEXT_COLUMNS = (
    "trend_score",
    "vcp_score",
    "final_score",
    "market_cap",
    "beta_126",
    "spread_bps",
    "earnings_date",
    "days_to_earnings",
    "earnings_blackout",
    "selection_rank",
    "raw_final_score",
    "normalized_total_score",
    "normalized_rsi",
    "total_score_neutralized",
    "relative_strength_index_neutralized",
    "trend_vcp_component",
    "total_score_component",
    "rsi_component",
    "atr_pct_20",
    "weekly_trend_score",
    "high_52w_proximity",
    "volatility_ratio",
    "selector_signal_mode",
    "selection_explanation",
)


def get_stock_scores_table(*, engine=None) -> Table:
    resolved_engine = engine or get_sqlalchemy_engine()
    return Table(
        "stock_scores",
        MetaData(),
        Column("symbol", String(20), primary_key=True),
        Column("total_score", Float),
        Column("final_score_sentiment", Float),
        Column("anomaly_count", Integer),
        Column("missing_days_count", Integer),
        autoload_with=resolved_engine,
    )


def list_scored_symbols(
    *,
    engine=None,
    stock_scores: Table | None = None,
    limit: int | None = None,
) -> list[str]:
    if limit is not None and limit < 1:
        raise ValueError("limit doit être supérieur ou égal à 1.")

    resolved_engine = engine or get_sqlalchemy_engine()
    resolved_table = stock_scores if stock_scores is not None else get_stock_scores_table(engine=resolved_engine)
    stmt = select(resolved_table.c.symbol).where(resolved_table.c.symbol.is_not(None))
    if "total_score" in resolved_table.c:
        stmt = stmt.order_by(resolved_table.c.total_score.desc())
    stmt = stmt.order_by(resolved_table.c.symbol.asc())
    if limit is not None:
        stmt = stmt.limit(limit)

    with resolved_engine.connect() as conn:
        rows = conn.execute(stmt).scalars().all()
    return [str(symbol).strip().upper() for symbol in rows if str(symbol).strip()]


def load_score_context(
    *,
    engine=None,
    stock_scores: Table | None = None,
    limit: int | None = None,
) -> pd.DataFrame:
    if limit is not None and limit < 1:
        raise ValueError("limit doit être supérieur ou égal à 1.")

    resolved_engine = engine or get_sqlalchemy_engine()
    resolved_table = stock_scores if stock_scores is not None else get_stock_scores_table(engine=resolved_engine)
    selected_columns = ["symbol"]
    selected_expressions = [resolved_table.c.symbol]
    for column in SCORE_CONTEXT_COLUMNS:
        if column in resolved_table.c:
            selected_columns.append(column)
            selected_expressions.append(resolved_table.c[column])

    stmt = select(*selected_expressions).where(
        resolved_table.c.symbol.is_not(None)
    )
    if "total_score" in resolved_table.c:
        stmt = stmt.order_by(resolved_table.c.total_score.desc())
    stmt = stmt.order_by(resolved_table.c.symbol.asc())
    if limit is not None:
        stmt = stmt.limit(limit)

    with resolved_engine.connect() as conn:
        rows = conn.execute(stmt).mappings().all()
    if not rows:
        return pd.DataFrame(columns=selected_columns)

    frame = pd.DataFrame(rows)
    frame["symbol"] = frame["symbol"].astype(str).str.strip().str.upper()
    frame = frame[frame["symbol"] != ""].reset_index(drop=True)
    return frame.loc[:, selected_columns].copy()


