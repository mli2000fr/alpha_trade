"""Add the directional model role to model_training_run.

Revision ID: 0070_training_run_role
Revises: 0069_directional_bundle_lineage

The combined Oracle + per-symbol LONG/SHORT contract creates two training
runs for the same batch and symbol.  Persisting the role makes diagnostics,
governance joins and serving lineage unambiguous.  Historical rows remain
nullable; bundle rows already identifiable from their run id are backfilled.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0070_training_run_role"
down_revision: Union[str, None] = "0069_directional_bundle_lineage"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None

_SCHEMA = "alpha_trade"
_TABLE = "model_training_run"
_COLUMN = "model_role"
_INDEX = "idx_batch_role_symbol"


def _has_table(bind) -> bool:
    return sa.inspect(bind).has_table(_TABLE, schema=_SCHEMA)


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind):
        return
    inspector = sa.inspect(bind)
    columns = {str(column["name"]) for column in inspector.get_columns(_TABLE, schema=_SCHEMA)}
    if _COLUMN not in columns:
        op.add_column(
            _TABLE,
            sa.Column(
                _COLUMN,
                sa.String(32),
                nullable=True,
                comment="Rôle du modèle: direction_legacy|direction_long|direction_short",
            ),
            schema=_SCHEMA,
        )

    # Runs created by the first directional-bundle implementation already
    # encode their role in the immutable run id.
    op.execute(
        sa.text(
            "UPDATE alpha_trade.model_training_run "
            "SET model_role = 'direction_long' "
            "WHERE model_role IS NULL AND LOCATE('_direction_long_', run_id) > 0"
        )
    )
    op.execute(
        sa.text(
            "UPDATE alpha_trade.model_training_run "
            "SET model_role = 'direction_short' "
            "WHERE model_role IS NULL AND LOCATE('_direction_short_', run_id) > 0"
        )
    )

    indexes = {str(index["name"]) for index in sa.inspect(bind).get_indexes(_TABLE, schema=_SCHEMA)}
    if _INDEX not in indexes:
        op.create_index(_INDEX, _TABLE, ["batch_id", "model_role", "symbol"], schema=_SCHEMA)


def downgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind):
        return
    inspector = sa.inspect(bind)
    indexes = {str(index["name"]) for index in inspector.get_indexes(_TABLE, schema=_SCHEMA)}
    if _INDEX in indexes:
        op.drop_index(_INDEX, table_name=_TABLE, schema=_SCHEMA)
    columns = {str(column["name"]) for column in sa.inspect(bind).get_columns(_TABLE, schema=_SCHEMA)}
    if _COLUMN in columns:
        op.drop_column(_TABLE, _COLUMN, schema=_SCHEMA)
