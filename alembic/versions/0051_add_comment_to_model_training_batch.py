"""Add comment column to model_training_batch.

Revision ID: 0051_add_comment_to_model_training_batch
Revises: 0050_add_model_training_batch
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0051_add_comment_to_model_training_batch"
down_revision = "0050_add_model_training_batch"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("model_training_batch"):
        return

    columns = {col["name"] for col in inspector.get_columns("model_training_batch")}
    if "comment" in columns:
        return

    op.add_column(
        "model_training_batch",
        sa.Column("comment", sa.String(200), nullable=True, comment="Commentaire saisi par l utilisateur dans l IHM"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("model_training_batch"):
        return

    columns = {col["name"] for col in inspector.get_columns("model_training_batch")}
    if "comment" not in columns:
        return

    op.drop_column("model_training_batch", "comment")
