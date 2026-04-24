"""Add run_business_summaries table for persisted business-level pipeline summaries.
Revision ID: 0007_add_run_business_summaries_table
Revises: 0006_add_model_governance_table
"""
from alembic import op
import sqlalchemy as sa
revision = "0007_add_run_business_summaries_table"
down_revision = "0006_add_model_governance_table"
branch_labels = None
depends_on = None
def upgrade() -> None:
    op.create_table(
        "run_business_summaries",
        sa.Column("summary_run_id", sa.String(length=96), primary_key=True),
        sa.Column("source_run_id", sa.String(length=96), nullable=True),
        sa.Column("entity_run_id", sa.String(length=96), nullable=True),
        sa.Column("parent_summary_run_id", sa.String(length=96), nullable=True),
        sa.Column("step_key", sa.String(length=64), nullable=False),
        sa.Column("run_kind", sa.String(length=16), nullable=False, server_default=sa.text("'step'")),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("account_id", sa.String(length=64), nullable=True),
        sa.Column("trade_date", sa.Date(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("summary_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("idx_run_business_summaries_step", "run_business_summaries", ["step_key"])
    op.create_index("idx_run_business_summaries_entity", "run_business_summaries", ["entity_run_id"])
    op.create_index("idx_run_business_summaries_source", "run_business_summaries", ["source_run_id"])
    op.create_index("idx_run_business_summaries_run_kind", "run_business_summaries", ["run_kind"])
    op.create_index("idx_run_business_summaries_trade_date", "run_business_summaries", ["trade_date"])
def downgrade() -> None:
    op.drop_index("idx_run_business_summaries_trade_date", table_name="run_business_summaries")
    op.drop_index("idx_run_business_summaries_run_kind", table_name="run_business_summaries")
    op.drop_index("idx_run_business_summaries_source", table_name="run_business_summaries")
    op.drop_index("idx_run_business_summaries_entity", table_name="run_business_summaries")
    op.drop_index("idx_run_business_summaries_step", table_name="run_business_summaries")
    op.drop_table("run_business_summaries")
