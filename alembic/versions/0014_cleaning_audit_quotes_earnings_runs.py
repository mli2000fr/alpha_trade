"""Phase 3.1.c/d refactor — audits dédiés quotes/earnings.

Réf. ``audit_dataIntegrityEngine.md`` + ``prompt/refactor/plan.md`` Phase 3.1.

Sépare la traçabilité des syncs quotes / earnings de la table générique
``cleaning_audit_runs`` (réservée aux daily bars) :

- ``cleaning_audit_quotes_runs`` : un run par exécution de
  ``dataIntegrityEngine.sync_latest_quotes`` (volume agrégé + statut).
- ``cleaning_audit_earnings_runs`` : un run par exécution de
  ``dataIntegrityEngine.sync_earnings_calendar``.

Les colonnes sont volontairement légères (1 ligne par run, pas par symbole)
parce que ces flux sont des batchs : la granularité par symbole reste
implicite via le ``run_summary`` JSON archivé côté IHM.

Revision ID: 0014_cleaning_audit_quotes_earnings_runs
Revises: 0013_watcher_heartbeats
"""
from alembic import op
import sqlalchemy as sa


revision = "0014_cleaning_audit_quotes_earnings_runs"
down_revision = "0013_watcher_heartbeats"
branch_labels = None
depends_on = None


def _create_audit_table(table_name: str) -> None:
    op.create_table(
        table_name,
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("symbols_requested", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("rows_upserted", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'success'"),
            comment="success | failed | partial",
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        f"idx_{table_name}_run_id",
        table_name,
        ["run_id"],
        unique=True,
    )
    op.create_index(
        f"idx_{table_name}_status_created_at",
        table_name,
        ["status", "created_at"],
    )


def upgrade() -> None:
    _create_audit_table("cleaning_audit_quotes_runs")
    _create_audit_table("cleaning_audit_earnings_runs")


def downgrade() -> None:
    for table_name in ("cleaning_audit_earnings_runs", "cleaning_audit_quotes_runs"):
        op.drop_index(f"idx_{table_name}_status_created_at", table_name=table_name)
        op.drop_index(f"idx_{table_name}_run_id", table_name=table_name)
        op.drop_table(table_name)

