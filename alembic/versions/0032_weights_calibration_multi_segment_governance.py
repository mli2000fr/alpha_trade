"""Extend calibration runs with horizon/window governance and add segment drifts.

Revision ID: 0032_weights_calibration_multi_segment_governance
Revises: 0031_weights_calibration_runs_regime_segmentation
"""

import sqlalchemy as sa

from alembic import op

revision = "0032_weights_calibration_multi_segment_governance"
down_revision = "0031_weights_calibration_runs_regime_segmentation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("weights_calibration_runs") as batch_op:
        batch_op.add_column(sa.Column("calibration_batch_id", sa.String(length=40), nullable=True))
        batch_op.add_column(sa.Column("segment_key", sa.String(length=160), nullable=True))
        batch_op.add_column(sa.Column("horizon_days", sa.Integer(), nullable=False, server_default="5"))
        batch_op.add_column(sa.Column("lookback_months", sa.Integer(), nullable=False, server_default="12"))
        batch_op.add_column(sa.Column("distinct_snapshot_days", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("distinct_symbols", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("eligible_for_live", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("eligibility_reason", sa.String(length=255), nullable=True))
        batch_op.create_index(
            "ix_weights_cal_batch_segment",
            ["calibration_batch_id", "segment_key"],
            unique=False,
        )
        batch_op.create_index(
            "ix_weights_cal_live_promotion",
            ["scope", "horizon_days", "lookback_months", "market_regime_mode", "eligible_for_live", "window_end"],
            unique=False,
        )

    op.create_table(
        "weights_calibration_segment_drifts",
        sa.Column("run_id", sa.String(length=40), primary_key=True),
        sa.Column("compared_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column(
            "comparison_kind",
            sa.String(length=48),
            nullable=False,
            comment="vs_all_same_horizon_window | vs_reference_live_segment",
        ),
        sa.Column("calibration_batch_id", sa.String(length=40), nullable=True),
        sa.Column("source_run_id", sa.String(length=40), nullable=True),
        sa.Column("target_run_id", sa.String(length=40), nullable=True),
        sa.Column("source_segment_key", sa.String(length=160), nullable=True),
        sa.Column("target_segment_key", sa.String(length=160), nullable=True),
        sa.Column("metric_name", sa.String(length=32), nullable=True),
        sa.Column("metric_delta", sa.Float(), nullable=True),
        sa.Column("final_value_drift_pct", sa.Float(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_index(
        "ix_weights_cal_seg_drift_batch",
        "weights_calibration_segment_drifts",
        ["calibration_batch_id", "compared_at"],
        unique=False,
    )
    op.create_index(
        "ix_weights_cal_seg_drift_source",
        "weights_calibration_segment_drifts",
        ["source_run_id", "comparison_kind"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_weights_cal_seg_drift_source", table_name="weights_calibration_segment_drifts")
    op.drop_index("ix_weights_cal_seg_drift_batch", table_name="weights_calibration_segment_drifts")
    op.drop_table("weights_calibration_segment_drifts")

    with op.batch_alter_table("weights_calibration_runs") as batch_op:
        batch_op.drop_index("ix_weights_cal_live_promotion")
        batch_op.drop_index("ix_weights_cal_batch_segment")
        batch_op.drop_column("eligibility_reason")
        batch_op.drop_column("eligible_for_live")
        batch_op.drop_column("distinct_symbols")
        batch_op.drop_column("distinct_snapshot_days")
        batch_op.drop_column("lookback_months")
        batch_op.drop_column("horizon_days")
        batch_op.drop_column("segment_key")
        batch_op.drop_column("calibration_batch_id")

