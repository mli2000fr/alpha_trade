"""Expand sizing_method column to VARCHAR(50) to accommodate longer enum values.

Revision ID: 0036
Revises: 0035_drop_equity_simulated
"""
from alembic import op
import sqlalchemy as sa


revision = "0036_expand_sizing_method_column"
down_revision = "0035_drop_equity_simulated"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Expand sizing_method column in risk_decisions and portfolio_targets tables."""
    # Modify risk_decisions table
    op.alter_column(
        'risk_decisions',
        'sizing_method',
        existing_type=sa.String(20),
        type_=sa.String(50),
        existing_nullable=True,
        nullable=True
    )

    # Modify portfolio_targets table
    op.alter_column(
        'portfolio_targets',
        'sizing_method',
        existing_type=sa.String(20),
        type_=sa.String(50),
        existing_nullable=True,
        nullable=True
    )


def downgrade() -> None:
    """Revert sizing_method column size."""
    # Modify portfolio_targets table
    op.alter_column(
        'portfolio_targets',
        'sizing_method',
        existing_type=sa.String(50),
        type_=sa.String(20),
        existing_nullable=True,
        nullable=True
    )

    # Modify risk_decisions table
    op.alter_column(
        'risk_decisions',
        'sizing_method',
        existing_type=sa.String(50),
        type_=sa.String(20),
        existing_nullable=True,
        nullable=True
    )

