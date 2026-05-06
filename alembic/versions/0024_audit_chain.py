"""Sprint S12.2 — Table ``audit_chain_events`` (chaînage HMAC SOX-like).

Référence : ``prompt/tod/22_plan_10_10.md`` §S12.2.

Chaque événement critique (run execution, run risk, corporate action audit
run) ajoute une ligne signée HMAC-SHA256 chaînée au précédent hash, ce qui
rend toute modification *a posteriori* détectable par
``scripts/verify_audit_chain.py``.

Revision ID: 0024_audit_chain
Revises: 0023_stock_scores_history_capital_preset
"""
from alembic import op
import sqlalchemy as sa


revision = "0024_audit_chain"
down_revision = "0023_stock_scores_history_capital_preset"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_chain_events",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "run_kind",
            sa.String(length=32),
            nullable=False,
            comment="execution_runs | risk_runs | corporate_action_runs | …",
        ),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column(
            "payload_canonical_json",
            sa.Text,
            nullable=False,
            comment="JSON canonique (sort_keys=True) signé.",
        ),
        sa.Column(
            "prev_hash",
            sa.String(length=64),
            nullable=False,
            server_default="",
            comment="HMAC du précédent maillon de la chaîne (par run_kind).",
        ),
        sa.Column(
            "hmac_sha256",
            sa.String(length=64),
            nullable=False,
            comment="HMAC-SHA256(key_version, prev_hash || payload_canonical_json).",
        ),
        sa.Column("key_version", sa.Integer, nullable=False, server_default="1"),
        sa.Column(
            "signed_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        "idx_audit_chain_events_kind_signed",
        "audit_chain_events",
        ["run_kind", "signed_at"],
    )
    op.create_index(
        "idx_audit_chain_events_kind_run",
        "audit_chain_events",
        ["run_kind", "run_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_audit_chain_events_kind_run", table_name="audit_chain_events")
    op.drop_index("idx_audit_chain_events_kind_signed", table_name="audit_chain_events")
    op.drop_table("audit_chain_events")

