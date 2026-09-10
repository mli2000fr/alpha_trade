"""Keep SEC EDGAR and EODHD fundamentals independently.

Revision ID: 0073_fundamentals_multi_provider
Revises: 0072_oracle_label_quality
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0073_fundamentals_multi_provider"
down_revision: str | None = "0072_oracle_label_quality"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_SCHEMA = "alpha_trade"
_TABLE = "stock_fundamentals_daily"
_OLD_UNIQUE = "uq_symbol_date"
_NEW_UNIQUE = "uq_sfd_symbol_date_source"


def _unique_names(bind) -> set[str]:
    inspector = sa.inspect(bind)
    if not inspector.has_table(_TABLE, schema=_SCHEMA):
        return set()
    return {
        str(constraint["name"])
        for constraint in inspector.get_unique_constraints(_TABLE, schema=_SCHEMA)
        if constraint.get("name")
    }


def upgrade() -> None:
    bind = op.get_bind()
    names = _unique_names(bind)
    if not names and not sa.inspect(bind).has_table(_TABLE, schema=_SCHEMA):
        return
    if _OLD_UNIQUE in names:
        op.drop_constraint(_OLD_UNIQUE, _TABLE, type_="unique", schema=_SCHEMA)
    if _NEW_UNIQUE not in names:
        op.create_unique_constraint(
            _NEW_UNIQUE,
            _TABLE,
            ["symbol", "trade_date", "source"],
            schema=_SCHEMA,
        )


def downgrade() -> None:
    bind = op.get_bind()
    names = _unique_names(bind)
    if not names and not sa.inspect(bind).has_table(_TABLE, schema=_SCHEMA):
        return
    if _NEW_UNIQUE in names:
        op.drop_constraint(_NEW_UNIQUE, _TABLE, type_="unique", schema=_SCHEMA)
    if _OLD_UNIQUE not in names:
        op.create_unique_constraint(
            _OLD_UNIQUE,
            _TABLE,
            ["symbol", "trade_date"],
            schema=_SCHEMA,
        )
