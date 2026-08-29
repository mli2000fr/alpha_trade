"""Add `source` column to model_predictions.

Revision ID: 0067_add_model_predictions_source
Revises: 0066_add_model_predictions_run_id_index

But : permettre un filtrage déterministe par ORIGINE de la prédiction au
moment de la LECTURE (plus de dedup "last-wins" ambigu par run_id) et
éviter la jointure lourde `model_training_run` pour savoir ce que représente
chaque ligne (per-symbol / per-sector / synthèse global rank / synthèse oracle).

Valeurs de `source` (convention, non contrainte en DB pour rester souple) :
- ``per_symbol``       : prédiction d'un modèle per-symbol (predict_symbol/predict_batch)
- ``per_sector``       : prédiction d'un modèle per-sector (fallback sectoriel)
- ``global_rank_synth``: synthèse rank-driven depuis global_rank_history
                         (run `{batch}_globalrank_synth`, sentinelle __GLOBAL_RANK_SYNTH__)
- ``oracle_synth``     : synchro Oracle Extreme → model_predictions
                         (run `{batch}_oracle_synth`, sentinelle __ORACLE_SYNTH__)

La colonne est NULLABLE et NON backfillée : les données existantes gardent
NULL (les consumers déduisent alors la source depuis le run_id, rétro-compatible).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0067_add_model_predictions_source"
down_revision: Union[str, None] = "0066_add_model_predictions_run_id_index"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None

_COLUMN_NAME = "source"
_INDEX_NAME = "idx_model_predictions_source"


def _has_table(bind, schema: str, table: str) -> bool:
    inspector = sa.inspect(bind)
    if schema:
        return inspector.has_table(table, schema=schema)
    return inspector.has_table(table)


def _has_column(bind, schema: str, table: str, column: str) -> bool:
    inspector = sa.inspect(bind)
    try:
        cols = inspector.get_columns(table, schema=schema)
    except Exception:
        return False
    return any(c["name"] == column for c in cols)


def _has_index(bind, schema: str, table: str, index: str) -> bool:
    inspector = sa.inspect(bind)
    try:
        indexes = inspector.get_indexes(table, schema=schema)
    except Exception:
        return False
    return any(ix["name"] == index for ix in indexes)


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "alpha_trade", "model_predictions"):
        return
    if not _has_column(bind, "alpha_trade", "model_predictions", _COLUMN_NAME):
        op.add_column(
            "model_predictions",
            sa.Column(
                _COLUMN_NAME,
                sa.String(32),
                nullable=True,
                comment="Origine de la prédiction: per_symbol|per_sector|global_rank_synth|oracle_synth",
            ),
            schema="alpha_trade",
        )
    if not _has_index(bind, "alpha_trade", "model_predictions", _INDEX_NAME):
        op.create_index(
            _INDEX_NAME,
            "model_predictions",
            [_COLUMN_NAME],
            schema="alpha_trade",
        )


def downgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "alpha_trade", "model_predictions"):
        return
    if _has_index(bind, "alpha_trade", "model_predictions", _INDEX_NAME):
        op.drop_index(_INDEX_NAME, table_name="model_predictions", schema="alpha_trade")
    if _has_column(bind, "alpha_trade", "model_predictions", _COLUMN_NAME):
        op.drop_column("model_predictions", _COLUMN_NAME, schema="alpha_trade")
