"""Explicit intraday provider, additive upgrade of the existing US table."""
from alembic import op
from sqlalchemy import inspect, text

revision='0098_intraday_provider'
down_revision='0097_stock_bars_intraday'
branch_labels=None
depends_on=None


def upgrade():
    conn=op.get_bind()
    if conn.execute(text('SELECT DATABASE()')).scalar()!='alpha_trade':
        raise RuntimeError('Migration 0098 requires alpha_trade (US)')
    if 'provider' not in {c['name'] for c in inspect(conn).get_columns('stock_bars_intraday')}:
        op.execute("ALTER TABLE alpha_trade.stock_bars_intraday ADD COLUMN provider VARCHAR(16) "
                   "NOT NULL DEFAULT 'eodhd' AFTER data_source")


def downgrade():
    conn=op.get_bind()
    if conn.execute(text('SELECT DATABASE()')).scalar()!='alpha_trade':
        raise RuntimeError('Migration 0098 requires alpha_trade (US)')
    op.drop_column('stock_bars_intraday','provider')
