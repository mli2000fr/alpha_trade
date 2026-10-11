"""Prospective EODHD consensus, separate from Yahoo relative horizons."""
from pathlib import Path
from alembic import context, op
from sqlalchemy import text

revision = '0099_eodhd_consensus'
down_revision = '0098_intraday_provider'
branch_labels = None
depends_on = None


def _guard():
    if not context.is_offline_mode():
        if op.get_bind().execute(text('SELECT DATABASE()')).scalar() != 'alpha_trade':
            raise RuntimeError('Migration 0099 requires alpha_trade (US)')


def upgrade():
    _guard()
    path = Path(__file__).resolve().parents[2] / 'database/sql/forward_pit/stock_analyst_consensus_eodhd_history.sql'
    op.execute(path.read_text(encoding='utf-8'))


def downgrade():
    _guard()
    op.execute('DROP TABLE alpha_trade.stock_analyst_consensus_eodhd_history')
