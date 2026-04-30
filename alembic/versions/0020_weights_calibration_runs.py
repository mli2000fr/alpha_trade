"""Phase 7.2 — Table ``weights_calibration_runs``.

Persistance des résultats de calibration empirique des poids
``ConvictionWeights`` et ``SentimentFusionWeights`` (cf.
``backtesting/weights_calibration.py``).

Réf. ``prompt/refactor/plan.md`` Phase 7 + audit_global §7.2.

Revision ID: 0020_weights_calibration_runs
Revises: 0019_corporate_actions_account_idempotency
"""
from alembic import op
import sqlalchemy as sa


revision = "0020_weights_calibration_runs"
down_revision = "0019_corporate_actions_account_idempotency"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "weights_calibration_runs",
        sa.Column("run_id", sa.String(length=40), primary_key=True),
        sa.Column("calibrated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("scope", sa.String(length=16), nullable=False, comment="conviction | sentiment"),
        sa.Column("window_start", sa.Date(), nullable=False),
        sa.Column("window_end", sa.Date(), nullable=False),
        sa.Column("metric_name", sa.String(length=32), nullable=False, comment="sharpe | hit_rate | ic"),
        sa.Column("metric_value", sa.Float(), nullable=False),
        sa.Column("best_weights", sa.JSON(), nullable=False),
        sa.Column("candidates", sa.JSON(), nullable=True, comment="Grille testée + métriques."),
        sa.Column("git_sha", sa.String(length=40), nullable=True),
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint("scope IN ('conviction','sentiment')", name="chk_weights_cal_scope"),
    )
    op.create_index(
        "ix_weights_cal_scope_calibrated_at",
        "weights_calibration_runs",
        ["scope", "calibrated_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_weights_cal_scope_calibrated_at", table_name="weights_calibration_runs")
    op.drop_table("weights_calibration_runs")

