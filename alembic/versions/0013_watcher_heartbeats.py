"""Phase 1 refactor — heartbeat persistant watcher (audit_watcher.md, audit_global.md §6.8).

Crée la table ``watcher_heartbeats`` qui matérialise l'état vivant du
``execution_protection_watcher`` (et tout autre watcher transverse) :

- ``watcher_name`` : identifiant logique du watcher.
- ``hostname`` / ``pid`` : identification physique.
- ``account_id`` : compte broker surveillé (NULL si transverse).
- ``last_heartbeat_at`` : timestamp UTC du dernier ping ; un consommateur
  (IHM, monitoring) peut alerter si > N minutes.
- ``status`` : ``RUNNING`` | ``IDLE`` | ``STOPPED`` | ``ERROR``.
- ``last_error`` : dernière erreur connue (texte court).

La PK ``(watcher_name, account_id)`` permet une élection de leader simple
en complément de ``execution_locks`` : un seul watcher actif par couple.

Revision ID: 0013_watcher_heartbeats
Revises: 0012_market_data_provenance_and_check
"""
from alembic import op
import sqlalchemy as sa


revision = "0013_watcher_heartbeats"
down_revision = "0012_market_data_provenance_and_check"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "watcher_heartbeats",
        sa.Column("watcher_name", sa.String(length=64), nullable=False),
        sa.Column("account_id", sa.String(length=32), nullable=False, server_default=sa.text("'default'")),
        sa.Column("hostname", sa.String(length=128), nullable=True),
        sa.Column("pid", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'RUNNING'")),
        sa.Column("last_heartbeat_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("started_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("last_error", sa.String(length=512), nullable=True),
        sa.PrimaryKeyConstraint("watcher_name", "account_id", name="pk_watcher_heartbeats"),
    )
    op.create_index(
        "idx_watcher_heartbeats_last_heartbeat",
        "watcher_heartbeats",
        ["last_heartbeat_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_watcher_heartbeats_last_heartbeat", table_name="watcher_heartbeats")
    op.drop_table("watcher_heartbeats")

