"""Add neutral selection ranks to risk and execution snapshots.

Revision ID: 0047_add_selection_rank_to_risk_execution
Revises: 0046_add_tradable_universe_history
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0047_add_selection_rank_to_risk_execution"
down_revision = "0046_add_tradable_universe_history"
branch_labels = None
depends_on = None


_TABLES = ("risk_decisions", "portfolio_targets", "execution_targets_snapshot")


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table_name in _TABLES:
        if not inspector.has_table(table_name):
            continue
        columns = {column["name"] for column in inspector.get_columns(table_name)}
        if "selection_rank" not in columns:
            with op.batch_alter_table(table_name) as batch_op:
                batch_op.add_column(sa.Column("selection_rank", sa.Integer(), nullable=True))
        if "candidate_rank" in columns:
            op.execute(
                sa.text(
                    f"UPDATE {table_name} "
                    "SET selection_rank = candidate_rank "
                    "WHERE selection_rank IS NULL"
                )
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table_name in _TABLES:
        if not inspector.has_table(table_name):
            continue
        columns = {column["name"] for column in inspector.get_columns(table_name)}
        if "selection_rank" in columns:
            with op.batch_alter_table(table_name) as batch_op:
                batch_op.drop_column("selection_rank")
