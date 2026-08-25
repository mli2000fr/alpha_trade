"""Add index on model_predictions.run_id for fast batch cleanup.

Revision ID: 0066_add_model_predictions_run_id_index
Revises: 0065_oracle_extreme_rename

Le ``DELETE FROM model_predictions WHERE run_id IN (...)`` (nettoyage de batch)
faisait un full scan : ``model_predictions`` n'a pas d'index sur ``run_id``
seul (cf. database/sql/ml/model_predictions.sql). Résultat : requête lente +
contention → ``Lock wait timeout exceeded`` (1205).

Cet index rend la suppression par run_id rapide et réduit fortement la
contention. DDL online (ALGORITHM=INPLACE, LOCK=NONE) sur InnoDB/MySQL 8.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0066_add_model_predictions_run_id_index"
down_revision: Union[str, None] = "0065_oracle_extreme_rename"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None

_INDEX_NAME = "idx_model_predictions_run_id"


def _has_index(bind, index: str) -> bool:
    inspector = sa.inspect(bind)
    if not inspector.has_table("model_predictions", schema="alpha_trade"):
        return False
    return any(
        ix["name"] == index
        for ix in inspector.get_indexes("model_predictions", schema="alpha_trade")
    )


def upgrade() -> None:
    bind = op.get_bind()
    if _has_index(bind, _INDEX_NAME):
        return
    op.create_index(
        _INDEX_NAME,
        "model_predictions",
        ["run_id"],
        schema="alpha_trade",
        mysql_engine="InnoDB",
    )


def downgrade() -> None:
    bind = op.get_bind()
    if _has_index(bind, _INDEX_NAME):
        op.drop_index(_INDEX_NAME, table_name="model_predictions", schema="alpha_trade")
