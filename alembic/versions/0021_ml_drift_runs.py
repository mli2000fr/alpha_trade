"""Phase 7.4 — Table ``ml_drift_runs``.

Persistance des runs de drift monitoring ML (cf.
``modelFactory/drift_monitor.py``). Une ligne par calcul de drift (souvent
quotidien, après ``run_predict``).

Réf. ``prompt/refactor/plan.md`` Phase 7 + audit_global §7.4.

Revision ID: 0021_ml_drift_runs
Revises: 0020_weights_calibration_runs
"""
from alembic import op
import sqlalchemy as sa


revision = "0021_ml_drift_runs"
down_revision = "0020_weights_calibration_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ml_drift_runs",
        sa.Column("run_id", sa.String(length=40), primary_key=True),
        sa.Column("computed_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("model_id", sa.String(length=64), nullable=False),
        sa.Column("ks_stat", sa.Float(), nullable=True),
        sa.Column("ks_pvalue", sa.Float(), nullable=True),
        sa.Column("psi", sa.Float(), nullable=True),
        sa.Column("n_samples", sa.Integer(), nullable=False),
        sa.Column("n_baseline", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=8), nullable=False, comment="OK | WARN | ALERT"),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint("status IN ('OK','WARN','ALERT')", name="chk_ml_drift_status"),
    )
    op.create_index("ix_ml_drift_model_at", "ml_drift_runs", ["model_id", "computed_at"])


def downgrade() -> None:
    op.drop_index("ix_ml_drift_model_at", table_name="ml_drift_runs")
    op.drop_table("ml_drift_runs")

