"""Add model_governance table for challenger/champion audit.

Revision ID: 0006_add_model_governance_table
Revises: 0005_add_model_predictions_audit_fields
"""
from alembic import op
import sqlalchemy as sa


revision = "0006_add_model_governance_table"
down_revision = "0005_add_model_predictions_audit_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "model_governance",
        sa.Column("governance_id", sa.BigInteger().with_variant(sa.BigInteger, "sqlite"), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("model_name", sa.String(length=32), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("is_selected_model", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("selection_mode", sa.String(length=32), nullable=True),
        sa.Column("selection_metric", sa.String(length=32), nullable=True),
        sa.Column("selection_score", sa.Float(), nullable=True),
        sa.Column("model_status", sa.String(length=32), nullable=True),
        sa.Column("selection_eligible", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("eligibility_reason", sa.String(length=64), nullable=True),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("inference_backend", sa.String(length=64), nullable=True),
        sa.Column("backend_model_name", sa.String(length=64), nullable=True),
        sa.Column("calibration_method", sa.String(length=32), nullable=True),
        sa.Column("decision_threshold", sa.Float(), nullable=True),
        sa.Column("artifact_symbol", sa.String(length=32), nullable=True),
        sa.Column("checkpoint_path", sa.String(length=500), nullable=True),
        sa.Column("scaler_path", sa.String(length=500), nullable=True),
        sa.Column("model_path", sa.String(length=500), nullable=True),
        sa.Column("config_path", sa.String(length=500), nullable=True),
        sa.Column("calibrator_path", sa.String(length=500), nullable=True),
        sa.Column("val_auc", sa.Float(), nullable=True),
        sa.Column("test_auc", sa.Float(), nullable=True),
        sa.Column("wf_auc", sa.Float(), nullable=True),
        sa.Column("val_threshold_business_score", sa.Float(), nullable=True),
        sa.Column("test_threshold_business_score", sa.Float(), nullable=True),
        sa.Column("wf_threshold_business_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("run_id", "symbol", "model_name", name="uq_model_governance_run_symbol_model"),
    )
    op.create_index("idx_model_governance_symbol", "model_governance", ["symbol"])
    op.create_index("idx_model_governance_run", "model_governance", ["run_id"])
    op.create_index("idx_model_governance_selected", "model_governance", ["symbol", "is_selected_model"])
    op.create_index("idx_model_governance_rank", "model_governance", ["symbol", "rank"])


def downgrade() -> None:
    op.drop_index("idx_model_governance_rank", table_name="model_governance")
    op.drop_index("idx_model_governance_selected", table_name="model_governance")
    op.drop_index("idx_model_governance_run", table_name="model_governance")
    op.drop_index("idx_model_governance_symbol", table_name="model_governance")
    op.drop_table("model_governance")

