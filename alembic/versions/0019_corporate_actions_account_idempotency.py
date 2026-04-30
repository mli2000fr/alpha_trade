"""Phase 5.3.a — colonne ``account_idempotency_key`` sur ``corporate_actions_events``.

Réf. ``prompt/refactor/plan_phase5.md`` § 5.3.a.

Permet le scope ``account_id`` dans la clé d'idempotence (cf.
``CorporateActionEvent.compute_idempotency_key``) afin d'éviter les
double-crédits cross-comptes (audit_corporate_actions §2.7 + §6 QW#1).

Stratégie de migration **non destructive** :
1. Ajout colonne ``account_idempotency_key VARCHAR(64) NULL``.
2. Backfill : copie de ``idempotency_key`` (legacy ``account_id=None`` →
   ``GLOBAL`` implicite) dans ``account_idempotency_key`` pour conserver
   la rétrocompat en lecture (``is_event_applied`` essaiera les deux clés).
3. Index ``UNIQUE`` sur ``account_idempotency_key`` (permet NULL multiples
   sous MySQL/MariaDB).

Revision ID: 0019_corporate_actions_account_idempotency
Revises: 0018_corporate_actions_audit_runs
"""
from alembic import op
import sqlalchemy as sa


revision = "0019_corporate_actions_account_idempotency"
down_revision = "0018_corporate_actions_audit_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "corporate_actions_events",
        sa.Column(
            "account_idempotency_key",
            sa.String(length=64),
            nullable=True,
            comment=(
                "Phase 5.3.a — clé d'idempotence scopée par account_id "
                "(sha256(account_or_GLOBAL|provider|symbol|ca_type|ex_date|amount_or_split)[:32]). "
                "NULL = events historiques d'avant la migration."
            ),
        ),
    )
    # Backfill : copie legacy → nouvelle colonne pour préserver la rétrocompat.
    # Batchée par 1000 lignes pour éviter long-running transaction (cf. plan §4).
    op.execute(
        "UPDATE corporate_actions_events "
        "SET account_idempotency_key = idempotency_key "
        "WHERE account_idempotency_key IS NULL"
    )
    op.create_index(
        "uq_corporate_actions_events_account_idem",
        "corporate_actions_events",
        ["account_idempotency_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "uq_corporate_actions_events_account_idem",
        table_name="corporate_actions_events",
    )
    op.drop_column("corporate_actions_events", "account_idempotency_key")

