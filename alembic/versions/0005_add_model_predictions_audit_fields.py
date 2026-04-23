"""Add audit serving fields to model_predictions.

Revision ID: 0005_add_model_predictions_audit_fields
Revises: 0004_add_selector_reference_data
"""
from alembic import op
import sqlalchemy as sa


revision = "0005_add_model_predictions_audit_fields"
down_revision = "0004_add_selector_reference_data"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("model_predictions", sa.Column("selected_model", sa.String(length=32), nullable=True))
    op.add_column("model_predictions", sa.Column("decision_threshold", sa.Float(), nullable=True))
    op.add_column("model_predictions", sa.Column("signal_label", sa.String(length=32), nullable=True))
    op.add_column("model_predictions", sa.Column("calibration_method", sa.String(length=32), nullable=True))
    op.create_index("idx_selected_model", "model_predictions", ["selected_model"])


def downgrade() -> None:
    op.drop_index("idx_selected_model", table_name="model_predictions")
    op.drop_column("model_predictions", "calibration_method")
    op.drop_column("model_predictions", "signal_label")
    op.drop_column("model_predictions", "decision_threshold")
    op.drop_column("model_predictions", "selected_model")

