"""Widen symbol columns for per-sector training (sector names up to 24 chars).

Revision ID: 0061_widen_symbol_columns_for_sector_names
Revises: 0060_add_shares_outstanding_to_fundamentals
"""
from __future__ import annotations

from alembic import op


revision = "0061_widen_symbol_columns_for_sector_names"
down_revision = "0060_add_shares_outstanding_to_fundamentals"
branch_labels = None
depends_on = None

# Tables touched by _persist_sector_metrics / per-sector training
# where symbol column holds a sector name (max 24 chars:
# "Consumer Discretionary") but column was VARCHAR(20).
TABLES = [
    "model_registry",
    "model_training_run",
    "model_metrics",
    "model_governance",
    "model_batch_diagnostics",
]


def upgrade() -> None:
    for table in TABLES:
        op.execute(
            f"ALTER TABLE {table} MODIFY COLUMN symbol VARCHAR(50) NOT NULL"
        )


def downgrade() -> None:
    for table in TABLES:
        op.execute(
            f"ALTER TABLE {table} MODIFY COLUMN symbol VARCHAR(20) NOT NULL"
        )
