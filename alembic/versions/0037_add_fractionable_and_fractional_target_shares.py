"""Add stock_metadata.fractionable and relax execution target shares type.

Revision ID: 0037_add_fractionable_and_fractional_target_shares
Revises: 0036_expand_sizing_method_column
"""
from __future__ import annotations

import alembic.op as op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0037_add_fractionable_and_fractional_target_shares"
down_revision = "0036_expand_sizing_method_column"
branch_labels = None
depends_on = None


def _has_table(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    return any(column.get("name") == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    if _has_table("execution_targets_snapshot") and _has_column("execution_targets_snapshot", "target_shares"):
        with op.batch_alter_table("execution_targets_snapshot") as batch_op:
            batch_op.alter_column(
                "target_shares",
                existing_type=sa.Integer(),
                type_=sa.Float(),
                existing_nullable=False,
                nullable=False,
            )

    if _has_table("stock_metadata") and not _has_column("stock_metadata", "fractionable"):
        op.add_column(
            "stock_metadata",
            sa.Column("fractionable", sa.Boolean(), nullable=True, server_default=sa.text("0")),
        )


def downgrade() -> None:
    if _has_table("stock_metadata") and _has_column("stock_metadata", "fractionable"):
        op.drop_column("stock_metadata", "fractionable")

    if _has_table("execution_targets_snapshot") and _has_column("execution_targets_snapshot", "target_shares"):
        with op.batch_alter_table("execution_targets_snapshot") as batch_op:
            batch_op.alter_column(
                "target_shares",
                existing_type=sa.Float(),
                type_=sa.Integer(),
                existing_nullable=False,
                nullable=False,
            )


