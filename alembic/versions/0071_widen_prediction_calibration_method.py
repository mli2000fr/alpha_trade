"""Widen model_predictions.calibration_method for directional bundles.

Revision ID: 0071_widen_prediction_calibration
Revises: 0070_training_run_role

A directional bundle records both calibration methods, for example
``long:temperature|short:temperature``.  That valid lineage value is longer
than the historical VARCHAR(32) column.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0071_widen_prediction_calibration"
down_revision: str | None = "0070_training_run_role"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_SCHEMA = "alpha_trade"
_TABLE = "model_predictions"
_COLUMN = "calibration_method"


def _has_column(bind) -> bool:
    inspector = sa.inspect(bind)
    if not inspector.has_table(_TABLE, schema=_SCHEMA):
        return False
    return _COLUMN in {
        str(column["name"])
        for column in inspector.get_columns(_TABLE, schema=_SCHEMA)
    }


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_column(bind):
        return
    op.alter_column(
        _TABLE,
        _COLUMN,
        existing_type=sa.String(length=32),
        type_=sa.String(length=128),
        existing_nullable=True,
        comment="Méthode(s) de calibration appliquée(s) aux probabilités",
        schema=_SCHEMA,
    )


def downgrade() -> None:
    bind = op.get_bind()
    if not _has_column(bind):
        return
    op.alter_column(
        _TABLE,
        _COLUMN,
        existing_type=sa.String(length=128),
        type_=sa.String(length=32),
        existing_nullable=True,
        comment="Méthode de calibration appliquée à la probabilité",
        schema=_SCHEMA,
    )
