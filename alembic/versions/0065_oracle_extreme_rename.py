"""Add oracle_extreme10, drop oracle_top10/oracle_bottom10 — Oracle Extreme refactor.

Revision ID: 0065_oracle_extreme_rename
Revises: 0064_add_global_oracle_labels

Le modèle Oracle TOP est renommé **Oracle Extreme** : sa cible devient
``oracle_extreme10 = oracle_top10 OR oracle_bottom10`` (TOP 10 % ∪ BOTTOM 10 %
cross-sectionnel du jour = détection de gros mouvement H20, PAS la direction —
cf. E0/D0/D1/D1d). Le modèle Oracle BOTTOM est supprimé (redondant avec TOP, cf. E0b).

Cette migration :
1. Ajoute ``oracle_extreme10`` (Boolean) ;
2. Recalcule ``oracle_extreme10 = oracle_top10 OR oracle_bottom10`` sur les lignes
   existantes (data backfill) ;
3. Supprime ``oracle_top10`` et ``oracle_bottom10``.

Note : ``oracle_pct_rank`` et ``oracle_decile`` sont conservés — ils permettent de
dériver top/bottom localement (audit) sans colonnes dédiées.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0065_oracle_extreme_rename"
down_revision: Union[str, None] = "0064_add_global_oracle_labels"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def _has_column(bind, table: str, column: str) -> bool:
    insp = sa.inspect(bind)
    if not insp.has_table(table, schema="alpha_trade"):
        return False
    return any(col["name"] == column for col in insp.get_columns(table, schema="alpha_trade"))


def upgrade() -> None:
    bind = op.get_bind()
    if not bind.dialect.has_table(bind, "global_oracle_labels", schema="alpha_trade"):
        return

    if not _has_column(bind, "global_oracle_labels", "oracle_extreme10"):
        op.add_column(
            "global_oracle_labels",
            sa.Column("oracle_extreme10", sa.Boolean(), nullable=True,
                      comment="1 si TOP 10% OU BOTTOM 10% cross-sectionnel du jour (gros mouvement H20)"),
            schema="alpha_trade",
        )

    # Backfill : oracle_extreme10 = oracle_top10 OR oracle_bottom10
    has_top = _has_column(bind, "global_oracle_labels", "oracle_top10")
    has_bottom = _has_column(bind, "global_oracle_labels", "oracle_bottom10")
    if has_top or has_bottom:
        if has_top and has_bottom:
            op.execute(
                "UPDATE alpha_trade.global_oracle_labels "
                "SET oracle_extreme10 = (oracle_top10 = 1 OR oracle_bottom10 = 1)"
            )
        elif has_top:
            op.execute(
                "UPDATE alpha_trade.global_oracle_labels SET oracle_extreme10 = oracle_top10"
            )
        else:
            op.execute(
                "UPDATE alpha_trade.global_oracle_labels SET oracle_extreme10 = oracle_bottom10"
            )

    # Suppression des anciennes colonnes
    if _has_column(bind, "global_oracle_labels", "oracle_top10"):
        op.drop_column("global_oracle_labels", "oracle_top10", schema="alpha_trade")
    if _has_column(bind, "global_oracle_labels", "oracle_bottom10"):
        op.drop_column("global_oracle_labels", "oracle_bottom10", schema="alpha_trade")


def downgrade() -> None:
    bind = op.get_bind()
    if not bind.dialect.has_table(bind, "global_oracle_labels", schema="alpha_trade"):
        return

    # Restaurer oracle_top10 / oracle_bottom10 (dérivés depuis pct_rank si possible)
    if not _has_column(bind, "global_oracle_labels", "oracle_top10"):
        op.add_column(
            "global_oracle_labels",
            sa.Column("oracle_top10", sa.Boolean(), nullable=True,
                      comment="1 si le titre est dans le TOP 10% cross-sectionnel du jour"),
            schema="alpha_trade",
        )
    if not _has_column(bind, "global_oracle_labels", "oracle_bottom10"):
        op.add_column(
            "global_oracle_labels",
            sa.Column("oracle_bottom10", sa.Boolean(), nullable=True,
                      comment="1 si le titre est dans le BOTTOM 10% cross-sectionnel du jour"),
            schema="alpha_trade",
        )
    # Best-effort : reconstruction top/bottom depuis pct_rank (définition cross-sectionnelle)
    if _has_column(bind, "global_oracle_labels", "oracle_pct_rank"):
        op.execute(
            "UPDATE alpha_trade.global_oracle_labels SET "
            "oracle_top10 = CASE WHEN oracle_pct_rank >= 0.90 THEN 1 ELSE 0 END, "
            "oracle_bottom10 = CASE WHEN oracle_pct_rank <= 0.10 THEN 1 ELSE 0 END "
            "WHERE oracle_pct_rank IS NOT NULL"
        )

    if _has_column(bind, "global_oracle_labels", "oracle_extreme10"):
        op.drop_column("global_oracle_labels", "oracle_extreme10", schema="alpha_trade")
