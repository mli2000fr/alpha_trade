"""Add event sentiment stage timestamps to news checkpoints.

Revision ID: 0033_news_checkpoint_stage_timestamps
Revises: 0032_weights_calibration_multi_segment_governance
"""

# noinspection PyUnresolvedReferences
import sqlalchemy as sa

from alembic import op

revision = "0033_news_checkpoint_stage_timestamps"
down_revision = "0032_weights_calibration_multi_segment_governance"
branch_labels = None
depends_on = None

_TABLE = "news_ingestion_checkpoint"
_COLUMNS: tuple[str, ...] = (
    "news_ingested_at",
    "relevance_backfill_at",
    "contextual_scoring_at",
    "features_aggregated_at",
)


def upgrade() -> None:
    with op.batch_alter_table(_TABLE) as batch_op:
        for column_name in _COLUMNS:
            batch_op.add_column(sa.Column(column_name, sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table(_TABLE) as batch_op:
        for column_name in reversed(_COLUMNS):
            batch_op.drop_column(column_name)


