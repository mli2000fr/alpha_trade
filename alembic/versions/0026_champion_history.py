"""Sprint S21.1 — Table ``champion_history``.

Trace des promotions / rétrogradations du champion ML par symbole, alimentée
par ``modelFactory/auto_rollback.py`` (mode non-dry-run). Indispensable pour
auditer un rollback automatique a posteriori.

Revision ID: 0026_champion_history
Revises: 0025_broker_statements
"""
from alembic import op
import sqlalchemy as sa


revision = "0026_champion_history"
down_revision = "0025_broker_statements"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "champion_history",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("model_id", sa.String(length=128), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=True),
        sa.Column(
            "promoted_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("demoted_at", sa.DateTime, nullable=True),
        sa.Column("reason", sa.String(length=256), nullable=False, server_default=""),
        sa.Column(
            "previous_model_id",
            sa.String(length=128),
            nullable=True,
            comment="model_id du champion remplacé (None si premier).",
        ),
        sa.Column("dry_run", sa.Boolean, nullable=False, server_default=sa.text("0")),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        "idx_champion_history_symbol_promoted",
        "champion_history",
        ["symbol", "promoted_at"],
    )
    op.create_index(
        "idx_champion_history_symbol_demoted",
        "champion_history",
        ["symbol", "demoted_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_champion_history_symbol_demoted", table_name="champion_history")
    op.drop_index("idx_champion_history_symbol_promoted", table_name="champion_history")
    op.drop_table("champion_history")

