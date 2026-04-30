"""Phase 5.3.b — table ``corporate_actions_audit_runs``.

Réf. ``prompt/refactor/plan_phase5.md`` § 5.3.b.

Trace chaque exécution de ``python -m corporate_actions {sync,apply,status,run}``
afin de surveiller volume, anomalies, divergences cross-check (Phase 5.3.c).

Sur le modèle des tables d'audit ``cleaning_audit_runs`` (Phase 3.1).

Revision ID: 0018_corporate_actions_audit_runs
Revises: 0017_execution_kill_switch_runs
"""
from alembic import op
import sqlalchemy as sa


revision = "0018_corporate_actions_audit_runs"
down_revision = "0017_execution_kill_switch_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "corporate_actions_audit_runs",
        sa.Column("run_id", sa.String(length=64), primary_key=True),
        sa.Column(
            "run_kind",
            sa.String(length=16),
            nullable=False,
            comment="sync | apply | reconcile | run",
        ),
        sa.Column("account_id", sa.String(length=64), nullable=True),
        sa.Column("started_at", sa.DateTime, nullable=False),
        sa.Column("finished_at", sa.DateTime, nullable=False),
        sa.Column("duration_seconds", sa.Float, nullable=False, server_default="0"),
        sa.Column("fetched", sa.Integer, nullable=False, server_default="0"),
        sa.Column("inserted", sa.Integer, nullable=False, server_default="0"),
        sa.Column("duplicates", sa.Integer, nullable=False, server_default="0"),
        sa.Column("invalid", sa.Integer, nullable=False, server_default="0"),
        sa.Column("applied", sa.Integer, nullable=False, server_default="0"),
        sa.Column("skipped", sa.Integer, nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("reconcile_diffs", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "anomalies_json",
            sa.Text,
            nullable=True,
            comment="JSON : anomalies détectées (cross-check Yahoo Phase 5.3.c, divergences ratios, etc.)",
        ),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="completed"),
        sa.Column(
            "summary_json",
            sa.LargeBinary(length=(2**31) - 1),
            nullable=True,
            comment="JSON sérialisé du run_summary émis par le CLI",
        ),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        "idx_corporate_actions_audit_runs_kind_started",
        "corporate_actions_audit_runs",
        ["run_kind", "started_at"],
    )
    op.create_index(
        "idx_corporate_actions_audit_runs_account",
        "corporate_actions_audit_runs",
        ["account_id", "started_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_corporate_actions_audit_runs_account", table_name="corporate_actions_audit_runs")
    op.drop_index("idx_corporate_actions_audit_runs_kind_started", table_name="corporate_actions_audit_runs")
    op.drop_table("corporate_actions_audit_runs")

