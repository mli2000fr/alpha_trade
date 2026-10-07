"""Renomme le staging Tushare en staging multi-fournisseurs.

Revision ID: 0003_provider_neutral_staging
Revises: 0002_tushare_raw_run_lineage
"""

from __future__ import annotations

from alembic import op

revision = "0003_provider_neutral_staging"
down_revision = "0002_tushare_raw_run_lineage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    database = connection.exec_driver_sql("SELECT DATABASE()").scalar()
    if database != "alpha_trade_cn":
        raise RuntimeError(f"Migration CN refusée sur {database!r}")
    op.execute("RENAME TABLE tushare_raw_payloads TO cn_raw_payloads")
    op.execute("RENAME TABLE tushare_staging_rows TO cn_staging_rows")


def downgrade() -> None:
    op.execute("RENAME TABLE cn_staging_rows TO tushare_staging_rows")
    op.execute("RENAME TABLE cn_raw_payloads TO tushare_raw_payloads")
