"""Add Yahoo analyst EPS trend and revision PIT snapshots.

Revision ID: 0077_yahoo_analyst_trends
Revises: 0076_finra_short_volume
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import LONGTEXT

revision: str = "0077_yahoo_analyst_trends"
down_revision: str | None = "0076_finra_short_volume"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

SCHEMA = "alpha_trade"


def _create_analysis_table(name: str, value_columns: list[sa.Column]) -> None:
    op.create_table(
        name,
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("provider", sa.String(16), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("observed_at", sa.DateTime(), nullable=False),
        sa.Column("available_at", sa.DateTime(), nullable=False),
        sa.Column("ingestion_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("horizon_raw", sa.String(8), nullable=False),
        sa.Column("horizon_normalized", sa.String(24), nullable=False),
        sa.Column("fiscal_period_end", sa.Date(), nullable=True),
        sa.Column("fiscal_year", sa.SmallInteger(), nullable=True),
        sa.Column("fiscal_quarter", sa.SmallInteger(), nullable=True),
        sa.Column("relative_horizon_only", sa.Boolean(), nullable=False,
                  server_default=sa.text("1")),
        *value_columns,
        sa.Column("raw_payload_json", sa.Text().with_variant(LONGTEXT(), "mysql"), nullable=True),
        sa.Column("raw_hash", sa.String(64), nullable=True),
        sa.Column("provider_schema_version", sa.String(16), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "symbol", "snapshot_date", "horizon_normalized",
                            name=f"uq_{name}_daily_horizon"),
        sa.Index(f"idx_{name}_symbol_date", "symbol", "snapshot_date"),
        sa.Index(f"idx_{name}_available", "symbol", "available_at"),
        schema=SCHEMA,
        mysql_charset="utf8mb4",
    )


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names(schema=SCHEMA))
    if "stock_analyst_eps_trend_history" not in tables:
        _create_analysis_table("stock_analyst_eps_trend_history", [
            sa.Column("current_value", sa.Double(), nullable=True),
            sa.Column("days_7_ago_value", sa.Double(), nullable=True),
            sa.Column("days_30_ago_value", sa.Double(), nullable=True),
            sa.Column("days_60_ago_value", sa.Double(), nullable=True),
            sa.Column("days_90_ago_value", sa.Double(), nullable=True),
        ])
    if "stock_analyst_eps_revision_history" not in tables:
        _create_analysis_table("stock_analyst_eps_revision_history", [
            sa.Column("up_last_7_days", sa.Integer(), nullable=True),
            sa.Column("up_last_30_days", sa.Integer(), nullable=True),
            sa.Column("down_last_7_days", sa.Integer(), nullable=True),
            sa.Column("down_last_30_days", sa.Integer(), nullable=True),
        ])

    run_columns = {
        column["name"] for column in inspector.get_columns(
            "analyst_snapshot_collection_run", schema=SCHEMA
        )
    }
    additions = {
        "eps_trend_rows_inserted": sa.Column("eps_trend_rows_inserted", sa.Integer()),
        "eps_revision_rows_inserted": sa.Column("eps_revision_rows_inserted", sa.Integer()),
        "eps_trend_coverage": sa.Column("eps_trend_coverage", sa.Double()),
        "eps_revision_coverage": sa.Column("eps_revision_coverage", sa.Double()),
    }
    for name, column in additions.items():
        if name not in run_columns:
            op.add_column("analyst_snapshot_collection_run", column, schema=SCHEMA)


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    run_columns = {
        column["name"] for column in inspector.get_columns(
            "analyst_snapshot_collection_run", schema=SCHEMA
        )
    }
    for name in ("eps_revision_coverage", "eps_trend_coverage",
                 "eps_revision_rows_inserted", "eps_trend_rows_inserted"):
        if name in run_columns:
            op.drop_column("analyst_snapshot_collection_run", name, schema=SCHEMA)
    for table in ("stock_analyst_eps_revision_history", "stock_analyst_eps_trend_history"):
        if inspector.has_table(table, schema=SCHEMA):
            op.drop_table(table, schema=SCHEMA)
