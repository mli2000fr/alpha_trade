"""Add fail-closed quality lineage to Oracle labels.

Revision ID: 0072_oracle_label_quality
Revises: 0071_widen_prediction_calibration
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0072_oracle_label_quality"
down_revision: str | None = "0071_widen_prediction_calibration"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_SCHEMA = "alpha_trade"
_TABLE = "global_oracle_labels"


def _columns(bind) -> set[str]:
    inspector = sa.inspect(bind)
    if not inspector.has_table(_TABLE, schema=_SCHEMA):
        return set()
    return {
        str(column["name"])
        for column in inspector.get_columns(_TABLE, schema=_SCHEMA)
    }


def upgrade() -> None:
    bind = op.get_bind()
    columns = _columns(bind)
    if not columns:
        return
    additions = (
        sa.Column(
            "future_return_raw",
            sa.Float(),
            nullable=True,
            comment="Rendement brut conserve pour audit, meme si la target est invalide",
        ),
        sa.Column(
            "target_quality_valid",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
            comment="1 uniquement si les deux barres et la continuite du titre sont valides",
        ),
        sa.Column(
            "target_quality_reason",
            sa.String(length=128),
            nullable=True,
            comment="Premier motif deterministe de quarantaine de la target",
        ),
        sa.Column(
            "price_start_source",
            sa.String(length=64),
            nullable=True,
            comment="Source de la barre reellement observee a D",
        ),
        sa.Column(
            "price_end_source",
            sa.String(length=64),
            nullable=True,
            comment="Source de la barre reellement observee a D+H",
        ),
    )
    for column in additions:
        if column.name not in columns:
            op.add_column(_TABLE, column, schema=_SCHEMA)
    inspector = sa.inspect(bind)
    indexes = {index["name"] for index in inspector.get_indexes(_TABLE, schema=_SCHEMA)}
    if "idx_gol_quality_batch" not in indexes:
        op.create_index(
            "idx_gol_quality_batch",
            _TABLE,
            ["batch_id", "horizon", "target_quality_valid", "prediction_date"],
            schema=_SCHEMA,
        )


def downgrade() -> None:
    bind = op.get_bind()
    columns = _columns(bind)
    if not columns:
        return
    inspector = sa.inspect(bind)
    indexes = {index["name"] for index in inspector.get_indexes(_TABLE, schema=_SCHEMA)}
    if "idx_gol_quality_batch" in indexes:
        op.drop_index("idx_gol_quality_batch", table_name=_TABLE, schema=_SCHEMA)
    for name in (
        "price_end_source",
        "price_start_source",
        "target_quality_reason",
        "target_quality_valid",
        "future_return_raw",
    ):
        if name in columns:
            op.drop_column(_TABLE, name, schema=_SCHEMA)
