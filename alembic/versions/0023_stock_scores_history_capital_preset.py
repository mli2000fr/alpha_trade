"""Versionnage `stock_scores_history` par preset capital.

Ajoute `capital_preset_key` et `config_fingerprint`, puis fait évoluer
l'unicité logique vers `(snapshot_date, capital_preset_key, symbol)`.

Revision ID: 0023_stock_scores_history_capital_preset
Revises: 0022_shadow_drift_runs
"""
from alembic import op
import sqlalchemy as sa


revision = "0023_stock_scores_history_capital_preset"
down_revision = "0022_shadow_drift_runs"
branch_labels = None
depends_on = None

DEFAULT_PRESET_KEY = "capital_0_2000"


def _has_column(bind, table: str, column: str) -> bool:
    insp = sa.inspect(bind)
    if not insp.has_table(table):
        return False
    return any(col["name"] == column for col in insp.get_columns(table))


def _has_index(bind, table: str, index_name: str) -> bool:
    insp = sa.inspect(bind)
    if not insp.has_table(table):
        return False
    return any(idx.get("name") == index_name for idx in insp.get_indexes(table))


def _has_unique(bind, table: str, constraint_name: str) -> bool:
    insp = sa.inspect(bind)
    if not insp.has_table(table):
        return False
    return any(uk.get("name") == constraint_name for uk in insp.get_unique_constraints(table))


def upgrade() -> None:
    bind = op.get_bind()
    if not bind.dialect.has_table(bind, "stock_scores_history"):
        return

    if not _has_column(bind, "stock_scores_history", "capital_preset_key"):
        op.add_column(
            "stock_scores_history",
            sa.Column(
                "capital_preset_key",
                sa.String(length=64),
                nullable=False,
                server_default=sa.text(f"'{DEFAULT_PRESET_KEY}'"),
            ),
        )
    if not _has_column(bind, "stock_scores_history", "config_fingerprint"):
        op.add_column(
            "stock_scores_history",
            sa.Column("config_fingerprint", sa.String(length=32), nullable=True),
        )

    if _has_unique(bind, "stock_scores_history", "uk_snapshot_symbol"):
        try:
            op.drop_constraint("uk_snapshot_symbol", "stock_scores_history", type_="unique")
        except Exception:
            op.execute("ALTER TABLE stock_scores_history DROP INDEX uk_snapshot_symbol")

    if not _has_unique(bind, "stock_scores_history", "uk_snapshot_preset_symbol"):
        op.create_unique_constraint(
            "uk_snapshot_preset_symbol",
            "stock_scores_history",
            ["snapshot_date", "capital_preset_key", "symbol"],
        )

    if not _has_index(bind, "stock_scores_history", "idx_history_preset_candidate"):
        op.create_index(
            "idx_history_preset_candidate",
            "stock_scores_history",
            ["capital_preset_key", "snapshot_date", "is_candidate"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    if not bind.dialect.has_table(bind, "stock_scores_history"):
        return

    if _has_index(bind, "stock_scores_history", "idx_history_preset_candidate"):
        op.drop_index("idx_history_preset_candidate", table_name="stock_scores_history")

    if _has_unique(bind, "stock_scores_history", "uk_snapshot_preset_symbol"):
        op.drop_constraint("uk_snapshot_preset_symbol", "stock_scores_history", type_="unique")

    if not _has_unique(bind, "stock_scores_history", "uk_snapshot_symbol"):
        op.create_unique_constraint(
            "uk_snapshot_symbol",
            "stock_scores_history",
            ["snapshot_date", "symbol"],
        )

    if _has_column(bind, "stock_scores_history", "config_fingerprint"):
        op.drop_column("stock_scores_history", "config_fingerprint")
    if _has_column(bind, "stock_scores_history", "capital_preset_key"):
        op.drop_column("stock_scores_history", "capital_preset_key")

