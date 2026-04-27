"""Phase 7.7 — Table ``shadow_drift_runs``.

Persistance des comparaisons offline ``live_run_id`` vs ``simulated_run_id``
(cf. ``risk_management/shadow_compare.py``).

Le mode "shadow live continu" reste **backlog Long terme** (cf.
``prompt/refactor/backlog_long_terme.md``) — cette table sert uniquement aux
comparaisons offline post-mortem.

Revision ID: 0022_shadow_drift_runs
Revises: 0021_ml_drift_runs
"""
from alembic import op
import sqlalchemy as sa


revision = "0022_shadow_drift_runs"
down_revision = "0021_ml_drift_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shadow_drift_runs",
        sa.Column("run_id", sa.String(length=40), primary_key=True),
        sa.Column("compared_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("live_run_id", sa.String(length=40), nullable=False),
        sa.Column("simulated_run_id", sa.String(length=40), nullable=False),
        sa.Column("symbols_only_in_live", sa.JSON(), nullable=True),
        sa.Column("symbols_only_in_sim", sa.JSON(), nullable=True),
        sa.Column("avg_qty_drift_pct", sa.Float(), nullable=True),
        sa.Column("avg_price_drift_pct", sa.Float(), nullable=True),
        sa.Column("avg_conviction_drift", sa.Float(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_index("ix_shadow_drift_compared_at", "shadow_drift_runs", ["compared_at"])


def downgrade() -> None:
    op.drop_index("ix_shadow_drift_compared_at", table_name="shadow_drift_runs")
    op.drop_table("shadow_drift_runs")

