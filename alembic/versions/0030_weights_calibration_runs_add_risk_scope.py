"""Extend ``weights_calibration_runs`` to support ``scope='risk'``.

Revision ID: 0030_weights_calibration_runs_add_risk_scope
Revises: 0029_selector_explainability_persistence
"""
from alembic import op


revision = "0030_weights_calibration_runs_add_risk_scope"
down_revision = "0029_selector_explainability_persistence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("weights_calibration_runs") as batch_op:
        batch_op.drop_constraint("chk_weights_cal_scope", type_="check")
        batch_op.create_check_constraint(
            "chk_weights_cal_scope",
            "scope IN ('conviction','sentiment','risk')",
        )


def downgrade() -> None:
    with op.batch_alter_table("weights_calibration_runs") as batch_op:
        batch_op.drop_constraint("chk_weights_cal_scope", type_="check")
        batch_op.create_check_constraint(
            "chk_weights_cal_scope",
            "scope IN ('conviction','sentiment')",
        )

