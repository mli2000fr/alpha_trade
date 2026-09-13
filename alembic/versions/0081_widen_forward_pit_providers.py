"""Widen every remaining Forward PIT provider column.

Revision ID: 0081_widen_forward_pit_providers
Revises: 0080_widen_pit_run_provider
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0081_widen_forward_pit_providers"
down_revision: str | None = "0080_widen_pit_run_provider"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None
SCHEMA = "alpha_trade"

_COLUMNS: tuple[tuple[str, int, bool], ...] = (
    ("pit_raw_payloads", 32, False),
    ("stock_bars_daily_versions", 32, False),
    ("security_master_snapshots", 32, False),
    ("security_master_changes", 32, False),
    ("corporate_action_source_events", 32, False),
    ("stock_borrow_status_snapshots", 32, False),
    ("stock_analyst_consensus_snapshots", 32, False),
    ("stock_option_snapshots", 32, False),
    ("stock_opening_window_bars", 32, False),
    ("stock_opening_window_bar_versions", 32, False),
    ("macro_vintage_observations", 16, False),
    ("pit_data_quality_metrics", 32, True),
    ("pit_data_quality_issues", 32, True),
    ("stock_short_volume_daily", 32, False),
    ("stock_option_contract_versions", 32, False),
    ("stock_option_bars_delayed", 32, False),
    ("option_contract_adjustments", 32, False),
)


def upgrade() -> None:
    for table_name, original_length, nullable in _COLUMNS:
        op.alter_column(
            table_name,
            "provider",
            schema=SCHEMA,
            existing_type=sa.String(original_length),
            type_=sa.String(255),
            existing_nullable=nullable,
        )


def downgrade() -> None:
    for table_name, original_length, nullable in _COLUMNS:
        op.alter_column(
            table_name,
            "provider",
            schema=SCHEMA,
            existing_type=sa.String(255),
            type_=sa.String(original_length),
            existing_nullable=nullable,
        )
