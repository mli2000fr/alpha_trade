"""Add LONG/SHORT bundle lineage to model_predictions.

Revision ID: 0069_directional_bundle_lineage
Revises: 0068_analyst_snapshot_collection

Les probabilités LONG et SHORT d'un bundle proviennent de deux champions
distincts. Ces colonnes rendent cette double provenance auditable sans casser
les prédictions historiques : tous les nouveaux champs sont NULLABLE.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0069_directional_bundle_lineage"
down_revision: Union[str, None] = "0068_analyst_snapshot_collection"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None

_SCHEMA = "alpha_trade"
_TABLE = "model_predictions"
_COLUMNS = (
    ("model_role", sa.String(32), "Rôle de la ligne: directional_bundle ou NULL pour le contrat historique"),
    ("direction_long_run_id", sa.String(128), "Run ayant produit proba_long"),
    ("direction_short_run_id", sa.String(128), "Run ayant produit proba_short"),
    ("direction_long_model", sa.String(64), "Champion servi pour la branche LONG"),
    ("direction_short_model", sa.String(64), "Champion servi pour la branche SHORT"),
)
_INDEXES = (
    ("idx_model_predictions_long_run", "direction_long_run_id"),
    ("idx_model_predictions_short_run", "direction_short_run_id"),
)


def _has_table(bind) -> bool:
    return sa.inspect(bind).has_table(_TABLE, schema=_SCHEMA)


def _column_names(bind) -> set[str]:
    return {str(col["name"]) for col in sa.inspect(bind).get_columns(_TABLE, schema=_SCHEMA)}


def _index_names(bind) -> set[str]:
    return {str(index["name"]) for index in sa.inspect(bind).get_indexes(_TABLE, schema=_SCHEMA)}


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind):
        return
    existing_columns = _column_names(bind)
    for name, column_type, comment in _COLUMNS:
        if name not in existing_columns:
            op.add_column(_TABLE, sa.Column(name, column_type, nullable=True, comment=comment), schema=_SCHEMA)
    existing_indexes = _index_names(bind)
    for index_name, column_name in _INDEXES:
        if index_name not in existing_indexes:
            op.create_index(index_name, _TABLE, [column_name], schema=_SCHEMA)


def downgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind):
        return
    existing_indexes = _index_names(bind)
    for index_name, _ in reversed(_INDEXES):
        if index_name in existing_indexes:
            op.drop_index(index_name, table_name=_TABLE, schema=_SCHEMA)
    existing_columns = _column_names(bind)
    for name, _, _ in reversed(_COLUMNS):
        if name in existing_columns:
            op.drop_column(_TABLE, name, schema=_SCHEMA)
