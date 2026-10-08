"""Auditable prospective Oracle/Web LLM filter (US only)."""
from alembic import context, op
from sqlalchemy import text
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import mysql
from service.llm_directional.repository import metadata

revision = '0093_llm_directional'
down_revision = '0092_oracle_atr_movements'
branch_labels = None
depends_on = None


def _guard():
    if not context.is_offline_mode() and op.get_bind().execute(text('SELECT DATABASE()')).scalar() != 'alpha_trade':
        raise RuntimeError('Migration 0093 réservée à alpha_trade (US)')


def upgrade():
    _guard()
    if context.is_offline_mode():
        op.execute('USE alpha_trade')
        for table in metadata.sorted_tables:
            op.execute(str(CreateTable(table).compile(dialect=mysql.dialect())))
    else:
        metadata.create_all(op.get_bind(), checkfirst=True)


def downgrade():
    _guard()
    for table in reversed(metadata.sorted_tables):
        op.drop_table(table.name)
