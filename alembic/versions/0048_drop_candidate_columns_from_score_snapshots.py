"""Replace candidate schema columns with selection_rank in score snapshots.

Revision ID: 0048_drop_candidate_columns_from_score_snapshots
Revises: 0047_add_selection_rank_to_risk_execution
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0048_drop_candidate_columns_from_score_snapshots"
down_revision = "0047_add_selection_rank_to_risk_execution"
branch_labels = None
depends_on = None


_TABLES = ("stock_scores", "stock_scores_history")


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
            op.execute(sa.text(
                f"UPDATE {table_name} SET selection_rank = candidate_rank "
                "WHERE selection_rank IS NULL"
            ))

    inspector = sa.inspect(bind)
    if inspector.has_table("stock_scores_history"):
        indexes = {index["name"] for index in inspector.get_indexes("stock_scores_history")}
        for index_name in ("idx_history_candidate", "idx_history_preset_candidate"):
            if index_name in indexes:
                op.drop_index(index_name, table_name="stock_scores_history")
        if "idx_history_selection_rank" not in indexes:
            op.create_index(
                "idx_history_selection_rank",
                "stock_scores_history",
                ["snapshot_date", "selection_rank"],
            )
        if "idx_history_preset_selection_rank" not in indexes:
            op.create_index(
                "idx_history_preset_selection_rank",
                "stock_scores_history",
                ["capital_preset_key", "snapshot_date", "selection_rank"],
            )

    inspector = sa.inspect(bind)
    for table_name in _TABLES:
        if not inspector.has_table(table_name):
            continue
        columns = {column["name"] for column in inspector.get_columns(table_name)}
        removable = [column for column in ("is_candidate", "candidate_rank") if column in columns]
        if removable:
            with op.batch_alter_table(table_name) as batch_op:
                for column in removable:
                    batch_op.drop_column(column)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table_name in _TABLES:
        if not inspector.has_table(table_name):
            continue
        columns = {column["name"] for column in inspector.get_columns(table_name)}
        with op.batch_alter_table(table_name) as batch_op:
            if "candidate_rank" not in columns:
                batch_op.add_column(sa.Column("candidate_rank", sa.Integer(), nullable=True))
            if "is_candidate" not in columns:
                batch_op.add_column(sa.Column("is_candidate", sa.Boolean(), nullable=False, server_default=sa.false()))
        op.execute(sa.text(
            f"UPDATE {table_name} SET candidate_rank = selection_rank "
            "WHERE candidate_rank IS NULL"
        ))

    inspector = sa.inspect(bind)
    if inspector.has_table("stock_scores_history"):
        columns = {column["name"] for column in inspector.get_columns("stock_scores_history")}
        if "is_candidate" in columns:
            op.create_index("idx_history_candidate", "stock_scores_history", ["snapshot_date", "is_candidate"])
            op.create_index(
                "idx_history_preset_candidate",
                "stock_scores_history",
                ["capital_preset_key", "snapshot_date", "is_candidate"],
            )
