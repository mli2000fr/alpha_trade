"""Separate raw intraday equity bars (US)."""
from pathlib import Path
from alembic import context, op
from sqlalchemy import text

revision = '0097_stock_bars_intraday'
down_revision = '0096_public_macro_versions'
branch_labels = None
depends_on = None


def _guard():
    if not context.is_offline_mode() and op.get_bind().execute(text('SELECT DATABASE()')).scalar() != 'alpha_trade':
        raise RuntimeError('Migration 0097 requires alpha_trade (US)')


def upgrade():
    _guard()
    op.execute((Path(__file__).resolve().parents[2]/'database/sql/stock/stock_bars_intraday.sql').read_text(encoding='utf-8'))


def downgrade():
    _guard()
    op.execute('DROP TABLE alpha_trade.stock_bars_intraday')
