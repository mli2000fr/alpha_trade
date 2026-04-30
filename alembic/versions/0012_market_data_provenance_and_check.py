"""Phase 1 refactor — durcissement schéma marché.

Ajoute :
- ``stock_bars.data_adjustment`` + CHECK 'split' (convention canonique projet).
- ``stock_bars_daily.data_adjustment`` + CHECK 'split'.
- ``stock_bars.data_source`` (préparation cross-source Alpaca/Stooq/Yahoo).
- ``stock_bars_daily.data_source``.
- ``stock_metadata.data_source``.
- ``stock_metadata.market_cap_refreshed_at`` (TTL filtre selector).
- ``stock_metadata.metadata_synced_at`` (TTL provenance Finnhub).

Référence : ``prompt/refactor/audit_global.md`` §6 quick wins 1-3,
``prompt/refactor/plan.md`` Phase 1.1.

Revision ID: 0012_market_data_provenance_and_check
Revises: 0011_add_execution_sprint5_reconciliation
"""
from alembic import op
import sqlalchemy as sa


revision = "0012_market_data_provenance_and_check"
down_revision = "0011_add_execution_sprint5_reconciliation"
branch_labels = None
depends_on = None


def _has_column(bind, table: str, column: str) -> bool:
    insp = sa.inspect(bind)
    if not insp.has_table(table):
        return False
    return any(col["name"] == column for col in insp.get_columns(table))


def upgrade() -> None:
    bind = op.get_bind()

    # --- stock_bars ---
    if bind.dialect.has_table(bind, "stock_bars"):
        if not _has_column(bind, "stock_bars", "data_adjustment"):
            op.add_column(
                "stock_bars",
                sa.Column(
                    "data_adjustment",
                    sa.String(length=16),
                    nullable=False,
                    server_default=sa.text("'split'"),
                ),
            )
        if not _has_column(bind, "stock_bars", "data_source"):
            op.add_column(
                "stock_bars",
                sa.Column(
                    "data_source",
                    sa.String(length=16),
                    nullable=False,
                    server_default=sa.text("'alpaca_iex'"),
                ),
            )
        # CHECK constraint (MySQL 8.0+ supporté nativement).
        try:
            op.create_check_constraint(
                "chk_bars_adj",
                "stock_bars",
                "data_adjustment = 'split'",
            )
        except Exception:
            # Idempotent : la contrainte peut déjà exister.
            pass

    # --- stock_bars_daily ---
    if bind.dialect.has_table(bind, "stock_bars_daily"):
        if not _has_column(bind, "stock_bars_daily", "data_adjustment"):
            op.add_column(
                "stock_bars_daily",
                sa.Column(
                    "data_adjustment",
                    sa.String(length=16),
                    nullable=False,
                    server_default=sa.text("'split'"),
                ),
            )
        if not _has_column(bind, "stock_bars_daily", "data_source"):
            op.add_column(
                "stock_bars_daily",
                sa.Column(
                    "data_source",
                    sa.String(length=16),
                    nullable=False,
                    server_default=sa.text("'alpaca_iex'"),
                ),
            )
        try:
            op.create_check_constraint(
                "chk_daily_adj",
                "stock_bars_daily",
                "data_adjustment = 'split'",
            )
        except Exception:
            pass

    # --- stock_metadata ---
    if bind.dialect.has_table(bind, "stock_metadata"):
        if not _has_column(bind, "stock_metadata", "data_source"):
            op.add_column(
                "stock_metadata",
                sa.Column("data_source", sa.String(length=16), nullable=True),
            )
        if not _has_column(bind, "stock_metadata", "market_cap_refreshed_at"):
            op.add_column(
                "stock_metadata",
                sa.Column("market_cap_refreshed_at", sa.DateTime(), nullable=True),
            )
        if not _has_column(bind, "stock_metadata", "metadata_synced_at"):
            op.add_column(
                "stock_metadata",
                sa.Column("metadata_synced_at", sa.DateTime(), nullable=True),
            )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.has_table(bind, "stock_metadata"):
        for col in ("metadata_synced_at", "market_cap_refreshed_at", "data_source"):
            if _has_column(bind, "stock_metadata", col):
                op.drop_column("stock_metadata", col)
    for table in ("stock_bars_daily", "stock_bars"):
        if not bind.dialect.has_table(bind, table):
            continue
        check_name = "chk_daily_adj" if table == "stock_bars_daily" else "chk_bars_adj"
        try:
            op.drop_constraint(check_name, table, type_="check")
        except Exception:
            pass
        for col in ("data_source", "data_adjustment"):
            if _has_column(bind, table, col):
                op.drop_column(table, col)

