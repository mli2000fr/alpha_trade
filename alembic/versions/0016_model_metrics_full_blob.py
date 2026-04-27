"""Phase 4.2.f — persistance ``metrics.json`` complet en BLOB.

Réf. ``prompt/refactor/plan_phase4.md`` § 4.2.f.

Ajoute une table ``model_metrics_full(run_id PK, symbol, metrics_json
LONGBLOB, created_at)`` pour ne plus dépendre uniquement de
``artifacts/models/<symbol>/metrics.json`` (qui peut être effacé).

La PK = run_id permet un round-trip 1:1 ; ``symbol`` est dénormalisé pour
faciliter les recherches « tous les runs récents d'un symbole ».

Revision ID: 0016_model_metrics_full_blob
Revises: 0015_finbert_model_fingerprint
"""
from alembic import op
import sqlalchemy as sa


revision = "0016_model_metrics_full_blob"
down_revision = "0015_finbert_model_fingerprint"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "model_metrics_full",
        sa.Column("run_id", sa.String(length=64), primary_key=True),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column(
            "metrics_json",
            sa.LargeBinary(length=(2**31) - 1),  # LONGBLOB MySQL
            nullable=False,
            comment="JSON sérialisé de metrics.json (champion only)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        "idx_model_metrics_full_symbol_created_at",
        "model_metrics_full",
        ["symbol", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_model_metrics_full_symbol_created_at", table_name="model_metrics_full")
    op.drop_table("model_metrics_full")

