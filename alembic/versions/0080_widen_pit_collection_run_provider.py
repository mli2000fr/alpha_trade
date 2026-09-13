"""Widen the provider lineage stored for forward PIT collection runs.

Revision ID: 0080_widen_pit_run_provider
Revises: 0079_delayed_options_occ
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0080_widen_pit_run_provider"
down_revision: str | None = "0079_delayed_options_occ"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None
SCHEMA = "alpha_trade"


def upgrade() -> None:
    op.alter_column(
        "pit_collection_runs",
        "provider",
        schema=SCHEMA,
        existing_type=sa.String(32),
        type_=sa.String(255),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "pit_collection_runs",
        "provider",
        schema=SCHEMA,
        existing_type=sa.String(255),
        type_=sa.String(32),
        existing_nullable=True,
    )
