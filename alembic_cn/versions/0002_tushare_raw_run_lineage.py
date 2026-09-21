"""Conserve une preuve brute distincte pour chaque run.

Revision ID: 0002_tushare_raw_run_lineage
Revises: 0001_tushare_raw_staging
"""

from alembic import op

revision = "0002_tushare_raw_run_lineage"
down_revision = "0001_tushare_raw_staging"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    database = connection.exec_driver_sql("SELECT DATABASE()").scalar()
    if database != "alpha_trade_cn":
        raise RuntimeError(f"Migration CN refusée sur {database!r}")
    op.execute("ALTER TABLE tushare_raw_payloads DROP INDEX uq_tushare_raw_page")
    op.execute(
        "ALTER TABLE tushare_raw_payloads ADD UNIQUE KEY uq_tushare_raw_run_page "
        "(run_id,endpoint,request_hash,page_key)"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE tushare_raw_payloads DROP INDEX uq_tushare_raw_run_page")
    op.execute(
        "ALTER TABLE tushare_raw_payloads ADD UNIQUE KEY uq_tushare_raw_page "
        "(endpoint,request_hash,page_key,payload_hash)"
    )
