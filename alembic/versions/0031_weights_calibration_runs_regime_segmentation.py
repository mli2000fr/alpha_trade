"""Extend ``weights_calibration_runs`` for regime segmentation and governance fields.

Revision ID: 0031_weights_calibration_runs_regime_segmentation
Revises: 0030_weights_calibration_runs_add_risk_scope
"""
import sqlalchemy as sa

from alembic import op

revision = "0031_weights_calibration_runs_regime_segmentation"
down_revision = "0030_weights_calibration_runs_add_risk_scope"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("weights_calibration_runs") as batch_op:
        batch_op.add_column(
            sa.Column(
                "market_regime_mode",
                sa.String(length=32),
                nullable=False,
                server_default="all",
                comment="all | normal | capital_preservation | close_only | cash_only",
            )
        )
        batch_op.add_column(sa.Column("observations_evaluated", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("scenarios_evaluated", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("latest_best_scenario_name", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("final_value", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("total_return_pct", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("sharpe_ratio", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("max_drawdown_pct", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("artifact_dir", sa.String(length=512), nullable=True))
        batch_op.alter_column("schema_version", existing_type=sa.Integer(), server_default="2")
        batch_op.create_index(
            "ix_weights_cal_scope_regime_window",
            ["scope", "market_regime_mode", "window_end", "calibrated_at"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("weights_calibration_runs") as batch_op:
        batch_op.drop_index("ix_weights_cal_scope_regime_window")
        batch_op.drop_column("artifact_dir")
        batch_op.drop_column("max_drawdown_pct")
        batch_op.drop_column("sharpe_ratio")
        batch_op.drop_column("total_return_pct")
        batch_op.drop_column("final_value")
        batch_op.drop_column("latest_best_scenario_name")
        batch_op.drop_column("scenarios_evaluated")
        batch_op.drop_column("observations_evaluated")
        batch_op.drop_column("market_regime_mode")
        batch_op.alter_column("schema_version", existing_type=sa.Integer(), server_default="1")


