"""Phase 5.2.c — table ``execution_kill_switch_runs``.

Réf. ``prompt/refactor/plan_phase5.md`` § 5.2.c.

Trace chaque exécution de la sous-commande
``python -m execution_engine cancel-all --account <id>`` afin d'auditer
qui a déclenché un kill switch global, sur quel compte, en quel mode et
combien d'ordres ont été annulés vs en échec.

Revision ID: 0017_execution_kill_switch_runs
Revises: 0016_model_metrics_full_blob
"""
from alembic import op
import sqlalchemy as sa


revision = "0017_execution_kill_switch_runs"
down_revision = "0016_model_metrics_full_blob"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "execution_kill_switch_runs",
        sa.Column("run_id", sa.String(length=64), primary_key=True),
        sa.Column("account_id", sa.String(length=64), nullable=False),
        sa.Column("broker_mode", sa.String(length=16), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("total_open", sa.Integer, nullable=False, server_default="0"),
        sa.Column("canceled", sa.Integer, nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("dry_run", sa.Boolean, nullable=False, server_default=sa.text("0")),
        sa.Column("started_at", sa.DateTime, nullable=False),
        sa.Column("finished_at", sa.DateTime, nullable=False),
        sa.Column(
            "results_json",
            sa.Text,
            nullable=True,
            comment="JSON sérialisé list[CancelResult] (broker_order_id, symbol, canceled, error)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        "idx_execution_kill_switch_runs_account_created",
        "execution_kill_switch_runs",
        ["account_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_execution_kill_switch_runs_account_created",
        table_name="execution_kill_switch_runs",
    )
    op.drop_table("execution_kill_switch_runs")

