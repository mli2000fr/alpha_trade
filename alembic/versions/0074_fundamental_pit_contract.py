"""Add conservative availability and SEC lineage to fundamentals.

Revision ID: 0074_fundamental_pit_contract
Revises: 0073_fundamentals_multi_provider
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0074_fundamental_pit_contract"
down_revision: str | None = "0073_fundamentals_multi_provider"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_SCHEMA = "alpha_trade"
_TABLE = "stock_fundamentals_daily"
_INDEX = "idx_sfd_symbol_available_date"


def _column_names(bind) -> set[str]:
    inspector = sa.inspect(bind)
    if not inspector.has_table(_TABLE, schema=_SCHEMA):
        return set()
    return {str(column["name"]) for column in inspector.get_columns(_TABLE, schema=_SCHEMA)}


def upgrade() -> None:
    bind = op.get_bind()
    columns = _column_names(bind)
    if not columns:
        return
    additions = (
        ("available_date", sa.Date(), "First calendar date at which this row may be consumed"),
        ("fiscal_period_end", sa.Date(), "Fiscal period represented by the filing"),
        ("form", sa.String(length=16), "SEC form, for example 10-Q or 10-K"),
        ("accession_number", sa.String(length=32), "SEC filing accession number"),
        ("dividend_per_share", sa.Float(), "Dividend per share; never a dividend yield"),
    )
    for name, type_, comment in additions:
        if name not in columns:
            op.add_column(
                _TABLE, sa.Column(name, type_, nullable=True, comment=comment), schema=_SCHEMA
            )

    # Existing SEC rows are archival filings and are usable no earlier than J+1.
    # Other providers are snapshots and therefore cannot predate their fetch.
    op.execute(sa.text(
        "UPDATE alpha_trade.stock_fundamentals_daily "
        "SET available_date = CASE "
        "WHEN UPPER(source) = 'SEC_EDGAR' THEN DATE_ADD(trade_date, INTERVAL 1 DAY) "
        "ELSE DATE_ADD(DATE(fetched_at), INTERVAL 1 DAY) END "
        "WHERE available_date IS NULL"
    ))
    op.alter_column(
        _TABLE, "available_date", existing_type=sa.Date(), nullable=False, schema=_SCHEMA
    )
    indexes = {index["name"] for index in sa.inspect(bind).get_indexes(_TABLE, schema=_SCHEMA)}
    if _INDEX not in indexes:
        op.create_index(
            _INDEX, _TABLE, ["symbol", "available_date"], unique=False, schema=_SCHEMA
        )


def downgrade() -> None:
    bind = op.get_bind()
    columns = _column_names(bind)
    if not columns:
        return
    indexes = {index["name"] for index in sa.inspect(bind).get_indexes(_TABLE, schema=_SCHEMA)}
    if _INDEX in indexes:
        op.drop_index(_INDEX, table_name=_TABLE, schema=_SCHEMA)
    for name in (
        "dividend_per_share", "accession_number", "form",
        "fiscal_period_end", "available_date",
    ):
        if name in columns:
            op.drop_column(_TABLE, name, schema=_SCHEMA)
